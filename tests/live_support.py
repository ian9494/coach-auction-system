"""Real localhost ephemeral transport with deterministic time and bounded cleanup."""
import asyncio
from contextlib import asynccontextmanager
import socket

import socketio
import uvicorn
from final_project.server.app import create_app
from .service_support import FakeClock, FakeTimer


async def eventually(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.005)


class Live:
    async def join(self, role, coach_id='coach01'):
        c = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
        self.clients.append(c)
        c.frames = []
        c.on(role + '_state', lambda data: c.frames.append(data))
        await c.connect(self.url, transports=['websocket'], wait_timeout=5)
        payload = {} if role == 'viewer' else {'token': self.auth.admin_token} if role == 'admin' else {
            'coachId': coach_id, 'token': self.auth.coach_tokens[coach_id]}
        ack = await c.call('join_' + role, payload, timeout=5)
        assert ack['ok']
        return c, ack['payload']['snapshot']

    async def command(self, c, event, request_id, **fields):
        payload = {'request_id': request_id, **fields}
        if event != 'start_auction':
            payload.setdefault('round_id', self.app.runtime.service.snapshot().round_id)
        return await c.call(event, payload, timeout=5)


@asynccontextmanager
async def live(config, auth, clock=None, rng=lambda: 0.0):
    rig = Live()
    rig.auth, rig.clock, rig.timer, rig.clients = auth, clock or FakeClock(), FakeTimer(), []
    rig.app = create_app(config, auth, clock=rig.clock.clock(), timer=rig.timer, rng=rng, tick_interval=0.02)
    server = uvicorn.Server(uvicorn.Config(rig.app, host='127.0.0.1', port=0, log_level='warning',
        access_log=False, timeout_graceful_shutdown=2))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    sock.setblocking(False)
    rig.url = f'http://127.0.0.1:{sock.getsockname()[1]}'
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        await eventually(lambda: server.started or task.done())
        assert server.started
        yield rig
    finally:
        try:
            for c in rig.clients:
                if c.connected:
                    await asyncio.wait_for(c.disconnect(), 5)
                await c.shutdown()
        finally:
            server.should_exit = True
            try:
                await asyncio.wait_for(task, 5)
            finally:
                sock.close()
        assert rig.app.runtime.service is None and not rig.app.runtime.ready
        assert rig.timer.callback is None
