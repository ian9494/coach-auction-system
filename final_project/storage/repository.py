"""Versioned JSON snapshot in one SQLite transaction; no pickle or CSV authority."""
from dataclasses import asdict, dataclass, field, fields
import json
import math
import sqlite3
from typing import Any

from final_project.config import ProjectConfig
from final_project.domain.models import AuctionState, AuctionStatus, Award, Coach, Player, UndoAward
from final_project.server.commands import CommandResult

SCHEMA_VERSION = 1


class RepositoryError(RuntimeError):
    pass


@dataclass
class Snapshot:
    state: AuctionState
    version: int = 0
    round_id: str | None = None
    remaining: float = 0.0
    deadline_utc: float | None = None
    settled_round_id: str | None = None
    processed: dict[str, dict[str, Any]] = field(default_factory=dict)


def _nonnegative(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def decode_snapshot(raw: dict[str, Any]) -> Snapshot:
    """Reject malformed/corrupt state, never silently initialize a fresh auction."""
    try:
        if type(raw["schema_version"]) is not int or raw["schema_version"] != SCHEMA_VERSION:
            raise ValueError("Unsupported snapshot schema")
        data = dict(raw["state"])
        if set(data) != {f.name for f in fields(AuctionState)}:
            raise ValueError("Incomplete/unknown state fields")
        data["coaches"] = tuple(Coach(**c) for c in data["coaches"])
        data["roster"] = tuple(Player(**p) for p in data["roster"])
        data["history"] = [Award(**a) for a in data["history"]]
        undo = data["last_award_undo"]
        data["last_award_undo"] = UndoAward(Award(**undo["award"]), undo["bids"]) if undo else None
        ids = {c.id for c in data["coaches"]}
        if not ids or any(not isinstance(c.id, str) or not c.id or not isinstance(c.name, str) for c in data["coaches"]):
            raise ValueError("Invalid coaches")
        if any(not isinstance(p.name, str) or not p.name for p in data["roster"]):
            raise ValueError("Invalid roster")
        if set(data["budgets"]) != ids:
            raise ValueError("Missing/unknown budgets")
        state = AuctionState(**data)
        if state.current_player is not None and not isinstance(state.current_player, str):
            raise ValueError("Invalid player")
        for award in state.history + ([state.last_award_undo.award] if state.last_award_undo else []):
            if award.coach_id not in ids or not isinstance(award.player, str) or not award.player:
                raise ValueError("Invalid history reference")
            if award.time is not None and not isinstance(award.time, str):
                raise ValueError("Invalid history time")
        if state.last_award_undo:
            bids = state.last_award_undo.bids
            if not isinstance(bids, dict) or not set(bids).issubset(ids) or any(
                v is not None and (type(v) is not int or v < 0) for v in bids.values()
            ):
                raise ValueError("Invalid undo bids")
        if (state.winner is None) != (state.winning_amount is None) or (state.winner is not None and state.winner not in ids):
            raise ValueError("Invalid winner")
        metadata = raw["metadata"]
        snap = Snapshot(state=state, **metadata)
        if type(snap.version) is not int or snap.version < 0 or not _nonnegative(snap.remaining):
            raise ValueError("Invalid version/remaining")
        for value in (snap.round_id, snap.settled_round_id):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError("Invalid round identity")
        if state.status == AuctionStatus.RUNNING:
            if not _nonnegative(snap.deadline_utc) or snap.round_id is None or not state.current_player:
                raise ValueError("Running state requires deadline/player/round")
        elif snap.deadline_utc is not None:
            raise ValueError("Inactive state cannot have deadline")
        if state.status in (AuctionStatus.RUNNING, AuctionStatus.PAUSED) and state.duration <= 0:
            raise ValueError("Active duration must be positive")
        if state.status == AuctionStatus.PAUSED and (snap.round_id is None or not state.current_player):
            raise ValueError("Paused state requires round/player")
        if state.status in (AuctionStatus.RUNNING, AuctionStatus.PAUSED) and snap.settled_round_id == snap.round_id:
            raise ValueError("Active round already settled")
        if snap.settled_round_id is not None and snap.settled_round_id != snap.round_id:
            raise ValueError("Settlement identity does not match round")
        if not isinstance(snap.processed, dict):
            raise ValueError("Invalid processed requests")
        for request_id, item in snap.processed.items():
            if not isinstance(request_id, str) or not request_id or not isinstance(item["fingerprint"], str):
                raise ValueError("Invalid request record")
            result = CommandResult(**item["result"])
            if type(result.ok) is not bool or type(result.version) is not int or not 0 <= result.version <= snap.version:
                raise ValueError("Invalid ACK version")
            if not isinstance(result.payload, dict) or not isinstance(result.message, str):
                raise ValueError("Invalid ACK fields")
            if (result.error_code is not None and not isinstance(result.error_code, str)) or (result.round_id is not None and not isinstance(result.round_id, str)):
                raise ValueError("Invalid ACK identity")
        return snap
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise RepositoryError(f"Invalid snapshot: {error}") from error


def encode_snapshot(snapshot: Snapshot) -> str:
    data = asdict(snapshot)
    raw = {"schema_version": SCHEMA_VERSION, "state": data.pop("state"), "metadata": data}
    decode_snapshot(raw)
    try:
        return json.dumps(raw, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise RepositoryError("Snapshot is not valid JSON") from error


class SQLiteRepository:
    """One authority per DB. Construction is explicit and paths are config-validated."""

    def __init__(self, config: ProjectConfig):
        # Revalidate even if caller bypassed frozen dataclass validation.
        config = ProjectConfig(**vars(config))
        self.path = config.path(config.sqlite_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        try:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise RepositoryError(f"Unsupported database schema {version}")
            tables = self._connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if version == 0 and tables:
                raise RepositoryError("Unversioned nonempty database")
            with self._connection:
                self._connection.execute("CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL, document TEXT NOT NULL)")
                self._connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        except Exception:
            self._connection.close()
            raise

    def load(self) -> Snapshot | None:
        try:
            row = self._connection.execute("SELECT schema_version, document FROM snapshot WHERE id=1").fetchone()
            if row is None:
                return None
            if row[0] != SCHEMA_VERSION:
                raise RepositoryError("Unsupported row schema")
            return decode_snapshot(json.loads(row[1], parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))))
        except (sqlite3.Error, ValueError, TypeError) as error:
            raise RepositoryError("Cannot load snapshot") from error

    def commit(self, snapshot: Snapshot) -> None:
        document = encode_snapshot(snapshot)
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO snapshot VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version, document=excluded.document",
                    (SCHEMA_VERSION, document),
                )
        except sqlite3.Error as error:
            raise RepositoryError("Snapshot transaction failed") from error

    def close(self) -> None:
        self._connection.close()
