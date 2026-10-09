"""ASGI factory; import never opens DB/port or reads credentials."""
import asyncio
from contextlib import asynccontextmanager
import csv
from dataclasses import dataclass
import logging
import random
import re

from fastapi import FastAPI
import socketio
from final_project.config import ProjectConfig
from final_project.domain.models import AuctionState, Coach, Player
from final_project.storage.repository import SQLiteRepository
from .auth import AuthConfig
from .events import SocketTransport
from .http_api import register_http
from .service import AuctionService

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    service: AuctionService | None = None
    auth: AuthConfig | None = None
    ready: bool = False


def load_roster(config: ProjectConfig) -> AuctionState:
    with config.path(config.coach_file).open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.reader(file))
    if not rows or any(len(row) != 2 or not re.fullmatch(r'[A-Za-z0-9_-]+', row[0]) or not row[1].strip() for row in rows):
        raise ValueError('Invalid project coach roster')
    coaches = tuple(Coach(row[0], row[1].strip()) for row in rows)
    with config.path(config.member_file).open(encoding='utf-8-sig', newline='') as file:
        names = list(csv.reader(file))
    if not names or any(len(row) != 1 or not row[0].strip() for row in names):
        raise ValueError('Invalid project player roster')
    roster = tuple(Player(row[0].strip()) for row in names)
    if len({p.name for p in roster}) != len(roster):
        raise ValueError('Duplicate project player name')
    return AuctionState(coaches, roster)


def create_app(config: ProjectConfig | None = None, auth: AuthConfig | None = None, *,
               clock=None, timer=None, rng=random.random, tick_interval: float = 1.0):
    config = config or ProjectConfig()
    if tick_interval <= 0:
        raise ValueError('tick_interval must be positive')
    runtime = Runtime()
    sio = socketio.AsyncServer(async_mode='asgi', logger=False, engineio_logger=False,
                              max_http_buffer_size=65536)  # default same-origin CORS
    transport = SocketTransport(sio, runtime)

    @asynccontextmanager
    async def lifespan(http):
        initial = load_roster(config)
        runtime.auth = auth or AuthConfig.from_env([c.id for c in initial.coaches])
        if set(runtime.auth.coach_tokens) != {c.id for c in initial.coaches}:
            raise ValueError('Authentication mapping differs from project roster')
        repository = SQLiteRepository(config)
        tasks, queue = [], None
        try:
            runtime.service = await AuctionService.open(repository, initial, clock=clock, timer=timer, rng=rng)
            queue = runtime.service.subscribe()
            runtime.ready = True

            async def broadcast_changes():
                while True:
                    snapshot = await queue.get()
                    try:
                        await transport.broadcast(snapshot)
                    except Exception:
                        logger.warning('State broadcast failed')

            async def display_ticks():
                while True:
                    await asyncio.sleep(tick_interval)
                    snapshot = runtime.service.snapshot()
                    if snapshot.state.status == 'running':
                        try:
                            await transport.broadcast(snapshot)
                        except Exception:
                            logger.warning('Display broadcast failed')

            tasks = [asyncio.create_task(broadcast_changes(), name='auction-broadcast'),
                     asyncio.create_task(display_ticks(), name='auction-display')]
            yield
        finally:
            runtime.ready = False
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                if runtime.service is not None:
                    if queue is not None: runtime.service.unsubscribe(queue)
                    await runtime.service.close()
            finally:
                try:
                    await sio.shutdown()
                finally:
                    repository.close()
                    runtime.service = None

    http = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    register_http(http, runtime)
    app = socketio.ASGIApp(sio, other_asgi_app=http)
    # Explicit handles for in-process tests / orderly lifecycle inspection.
    app.http, app.sio, app.runtime, app.transport = http, sio, runtime, transport
    return app


def main():
    import uvicorn
    config = ProjectConfig()
    uvicorn.run(create_app(config), host=config.host, port=config.port, workers=1,
                access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
