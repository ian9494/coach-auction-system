"""Deterministic test clocks/timers; all DBs use a temporary isolated root."""
from dataclasses import dataclass
from final_project.config import ProjectConfig
from final_project.server.commands import Command, CommandKind
from final_project.server.service import AuctionService
from final_project.server.timer import Clock
from final_project.storage.repository import SQLiteRepository
from .fixture_adapter import COACHES, ROSTER
from final_project.domain.models import AuctionState


@dataclass
class FakeClock:
    wall: float = 1000.0
    mono: float = 100.0

    def clock(self):
        return Clock(lambda: self.wall, lambda: self.mono)

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


class FakeTimer:
    def __init__(self):
        self.deadline = None
        self.callback = None
        self.cancel_count = 0

    def cancel(self):
        self.deadline = self.callback = None
        self.cancel_count += 1

    def schedule(self, deadline, callback):
        self.deadline, self.callback = deadline, callback

    async def close(self):
        self.cancel()


def initial():
    return AuctionState(COACHES, ROSTER)


async def create(tmp_path, *, clock=None, rng=lambda: 0.0):
    clock = clock or FakeClock()
    repo = SQLiteRepository(ProjectConfig(project_root=tmp_path))
    timer = FakeTimer()
    service = await AuctionService.open(repo, initial(), clock=clock.clock(), timer=timer, rng=rng)
    return service, repo, clock, timer


async def command(service, kind, request_id, **payload):
    return await service.execute(Command(CommandKind(kind), request_id,
        None if kind == 'start' else service.snapshot().round_id, payload))


async def dispose(service, repo):
    await service.close()
    repo.close()
