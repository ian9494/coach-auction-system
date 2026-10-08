"""Single authority: serialized copy-on-write commands, durable ACKs and recovery."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import random
from typing import Callable
from uuid import uuid4

from final_project.domain import transitions
from final_project.domain.errors import DomainError
from final_project.domain.models import AuctionState, AuctionStatus
from final_project.storage.repository import RepositoryError, Snapshot, SQLiteRepository
from .commands import Command, CommandKind, CommandResult
from .timer import Clock, DeadlineTimer


class AuctionService:
    """Use open() in one event loop; callers only receive defensive snapshot copies.

    asyncio.Lock is the single serialization path (including timer callbacks).
    No await occurs between candidate construction, DB commit and memory swap.
    SQLiteRepository and timer ownership remain explicit; close service before DB.
    """

    def __init__(self, repository: SQLiteRepository, snapshot: Snapshot, clock: Clock,
                 rng: Callable[[], float], timer: DeadlineTimer, round_factory: Callable[[], str]):
        self._repository = repository
        self._snapshot = deepcopy(snapshot)
        self._clock = clock
        self._rng = rng
        self._timer = timer
        self._round_factory = round_factory
        self._lock = asyncio.Lock()
        self._deadline_mono: float | None = None
        self._closed = False

    @classmethod
    async def open(cls, repository: SQLiteRepository, initial: AuctionState, *,
                   clock: Clock | None = None, rng: Callable[[], float] = random.random,
                   timer: DeadlineTimer | None = None,
                   round_factory: Callable[[], str] = lambda: str(uuid4())) -> "AuctionService":
        clock = clock or Clock()
        snapshot = repository.load()
        if snapshot is None:
            snapshot = Snapshot(deepcopy(initial))
            repository.commit(snapshot)
        elif snapshot.state.coaches != initial.coaches or snapshot.state.roster != initial.roster:
            raise RepositoryError("Persisted roster differs from configured roster")
        service = cls(repository, snapshot, clock, rng, timer or DeadlineTimer(clock), round_factory)
        if snapshot.state.status == AuctionStatus.RUNNING:
            remaining = max(0.0, snapshot.deadline_utc - clock.utc())
            service._deadline_mono = clock.monotonic() + remaining
            if remaining == 0:
                result = await service.execute(service._timeout_command())
                if not result.ok:
                    await service.close()
                    raise RepositoryError("Expired-round recovery could not commit")
            else:
                service._schedule()
        return service

    def snapshot(self) -> Snapshot:
        result = deepcopy(self._snapshot)
        if result.state.status == AuctionStatus.RUNNING:
            result.remaining = max(0.0, self._deadline_mono - self._clock.monotonic())
            result.state.time_left = math.ceil(result.remaining)
        return result

    def _result(self, ok: bool, code: str | None = None, *, changed: bool = False,
                snapshot: Snapshot | None = None) -> CommandResult:
        snap = snapshot or self._snapshot
        return CommandResult(ok, code, "OK" if ok else code, snap.version, snap.round_id, {"changed": changed})

    def _timeout_command(self) -> Command:
        snap = self._snapshot
        return Command(CommandKind.TIMEOUT, f"timeout:{snap.round_id}:{snap.deadline_utc}",
                       snap.round_id, {"deadline_utc": snap.deadline_utc})

    def _schedule(self) -> None:
        self._timer.cancel()
        if self._snapshot.state.status != AuctionStatus.RUNNING or self._closed:
            return
        command = self._timeout_command()

        async def timeout() -> bool:
            result = await self.execute(command)
            return result.ok or result.error_code not in ("PERSISTENCE_ERROR", "TIMEOUT_NOT_DUE")

        self._timer.schedule(self._deadline_mono, timeout)

    async def execute(self, command: Command) -> CommandResult:
        # Freeze caller-owned dictionaries before waiting for the authority lock.
        command = deepcopy(command)
        async with self._lock:
            if self._closed:
                return self._result(False, "SERVICE_CLOSED")
            return self._execute_locked(command)

    def _execute_locked(self, command: Command) -> CommandResult:
        try:
            kind = CommandKind(command.kind)
            if not isinstance(command.request_id, str) or not command.request_id or command.request_id.startswith("timeout:") and kind != CommandKind.TIMEOUT:
                return self._result(False, "INVALID_REQUEST")
            if not isinstance(command.payload, dict) or (command.round_id is not None and not isinstance(command.round_id, str)):
                return self._result(False, "INVALID_REQUEST")
            encoded = json.dumps({"kind": kind.value, "round_id": command.round_id, "payload": command.payload},
                                 sort_keys=True, allow_nan=False, separators=(",", ":"))
            fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        except (AttributeError, TypeError, ValueError):
            return self._result(False, "INVALID_REQUEST")
        old = self._snapshot.processed.get(command.request_id)
        if old is not None:
            if old["fingerprint"] != fingerprint:
                return self._result(False, "REQUEST_ID_CONFLICT")
            return CommandResult(**deepcopy(old["result"]))
        if kind != CommandKind.START and (command.round_id is None or command.round_id != self._snapshot.round_id):
            return self._remember(command, fingerprint, self._result(False, "STALE_ROUND"))
        if kind == CommandKind.TIMEOUT:
            if command.payload != {"deadline_utc": self._snapshot.deadline_utc}:
                return self._result(False, "STALE_TIMER")
            if self._snapshot.state.status == AuctionStatus.RUNNING and self._clock.monotonic() < self._deadline_mono:
                return self._result(False, "TIMEOUT_NOT_DUE")
        due = self._snapshot.state.status == AuctionStatus.RUNNING and self._clock.monotonic() >= self._deadline_mono
        if due and kind not in (CommandKind.END, CommandKind.TIMEOUT):
            settled = self._execute_locked(self._timeout_command())
            if not settled.ok:
                return self._result(False, "PERSISTENCE_ERROR")
            if kind == CommandKind.SUBMIT_BID:
                return self._remember(command, fingerprint, self._result(False, "DEADLINE_PASSED"))

        candidate = deepcopy(self._snapshot)
        deadline_mono = self._deadline_mono
        before = deepcopy(candidate)
        try:
            state = candidate.state
            payload = command.payload
            allowed = {
                CommandKind.START: {"player_name", "duration"}, CommandKind.SUBMIT_BID: {"coach_id", "amount"},
                CommandKind.SET_MINIMUM_BID: {"amount"}, CommandKind.TIMEOUT: {"deadline_utc"},
            }.get(kind, set())
            if not set(payload).issubset(allowed):
                raise DomainError("invalid_command")
            if kind == CommandKind.START:
                candidate.state = transitions.start_auction(state, **payload)
                candidate.round_id = self._round_factory()
                if not isinstance(candidate.round_id, str) or not candidate.round_id or candidate.round_id == self._snapshot.round_id:
                    raise DomainError("invalid_round_identity")
                candidate.settled_round_id = None
                candidate.remaining = float(candidate.state.duration)
                candidate.deadline_utc = self._clock.utc() + candidate.remaining
                deadline_mono = self._clock.monotonic() + candidate.remaining
            elif kind == CommandKind.PAUSE:
                if state.status != AuctionStatus.RUNNING:
                    raise DomainError("not_running")
                candidate.remaining = max(0.0, deadline_mono - self._clock.monotonic())
                candidate.state = transitions.pause_auction(state)
                candidate.state.time_left = math.ceil(candidate.remaining)
                candidate.deadline_utc = deadline_mono = None
            elif kind == CommandKind.RESUME:
                if state.status != AuctionStatus.PAUSED:
                    raise DomainError("not_paused")
                candidate.state = transitions.resume_auction(state)
                candidate.deadline_utc = self._clock.utc() + candidate.remaining
                deadline_mono = self._clock.monotonic() + candidate.remaining
            elif kind == CommandKind.SUBMIT_BID:
                candidate.state = transitions.submit_bid(state, **payload)
            elif kind == CommandKind.SET_MINIMUM_BID:
                candidate.state = transitions.set_minimum_bid(state, **payload)
            elif kind in (CommandKind.END, CommandKind.TIMEOUT):
                candidate.state = transitions.end_auction(state, rng=self._rng, clock=lambda:
                    datetime.fromtimestamp(self._clock.utc(), timezone.utc).isoformat())
                if candidate.state != state:
                    candidate.settled_round_id = candidate.round_id
                    candidate.remaining = 0.0
                    candidate.deadline_utc = deadline_mono = None
            elif kind == CommandKind.UNDO:
                candidate.state = transitions.undo_last_award(state)
                candidate.remaining = 0.0
                candidate.deadline_utc = deadline_mono = None
        except DomainError as error:
            code = {"invalid_coach": "UNKNOWN_COACH", "not_running": "INVALID_STATE", "not_paused": "INVALID_STATE",
                    "auction_active": "INVALID_STATE", "nothing_to_undo": "INVALID_STATE", "undo_history_mismatch": "INVALID_STATE",
                    "invalid_command": "INVALID_COMMAND", "invalid_duration": "INVALID_COMMAND", "invalid_player": "INVALID_COMMAND",
                    "invalid_round_identity": "INVALID_COMMAND"}.get(error.code, "INVALID_BID")
            return self._remember(command, fingerprint, self._result(False, code))
        except (TypeError, ValueError, KeyError):
            return self._remember(command, fingerprint, self._result(False, "INVALID_COMMAND"))
        changed = candidate != before
        if changed:
            candidate.version += 1
        # time_left is a display snapshot; updating it never independently increments version.
        if candidate.state.status == AuctionStatus.RUNNING:
            candidate.remaining = max(0.0, deadline_mono - self._clock.monotonic())
            candidate.state.time_left = math.ceil(candidate.remaining)
        result = self._result(True, changed=changed, snapshot=candidate)
        candidate.processed[command.request_id] = {"fingerprint": fingerprint, "result": asdict(result)}
        try:
            self._repository.commit(candidate)
        except RepositoryError:
            return self._result(False, "PERSISTENCE_ERROR")
        timer_changed = (self._snapshot.state.status, self._deadline_mono) != (candidate.state.status, deadline_mono)
        self._snapshot = candidate
        self._deadline_mono = deadline_mono
        if timer_changed:
            self._schedule()
        return deepcopy(result)

    def _remember(self, command: Command, fingerprint: str, result: CommandResult) -> CommandResult:
        candidate = deepcopy(self._snapshot)
        candidate.processed[command.request_id] = {"fingerprint": fingerprint, "result": asdict(result)}
        try:
            self._repository.commit(candidate)
        except RepositoryError:
            return self._result(False, "PERSISTENCE_ERROR")
        self._snapshot = candidate
        return deepcopy(result)

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            await self._timer.close()
