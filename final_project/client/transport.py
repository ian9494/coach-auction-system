"""Reusable threaded Socket.IO transport. No UI calls and no command replay."""
import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from queue import Queue, Empty
import threading
from urllib.parse import urlparse
from uuid import uuid4

import socketio
import aiohttp


@dataclass(frozen=True)
class ConnectionChanged:
    state: str


@dataclass(frozen=True)
class SnapshotReceived:
    snapshot: dict


@dataclass(frozen=True)
class CommandAckReceived:
    ack: dict


@dataclass(frozen=True)
class TransportError:
    code: str


@dataclass(frozen=True)
class Credentials:
    url: str
    role: str
    coach_id: str = ''
    token: str = field(default='', repr=False)

    def validate(self):
        parsed = urlparse(self.url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('INVALID_LOGIN')
        if self.role not in ('coach', 'admin', 'viewer') or (self.role != 'viewer' and not self.token):
            raise ValueError('INVALID_LOGIN')
        if self.role == 'coach' and not self.coach_id.strip():
            raise ValueError('INVALID_LOGIN')


class ClientTransport:
    """One worker owns AsyncClient; public methods return without network waits.

    Automatic reconnect repeats authentication, never pending commands. Queue items
    retain their original round. Commands lost at disconnect require user review.
    """
    def __init__(self, *, retry_delay=2.0, ack_timeout=5.0):
        self.events = Queue()
        self._outbound = Queue()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self._loop = self._task = None
        self.retry_delay, self.ack_timeout = retry_delay, ack_timeout

    def connect(self, credentials):
        credentials.validate()
        if self._thread is not None:
            raise RuntimeError('TRANSPORT_ALREADY_STARTED')
        self._thread = threading.Thread(target=self._worker, args=(credentials,), daemon=True,
                                        name='auction-network')
        self._thread.start()

    def send_command(self, event, *, round_id=None, **fields):
        request_id = uuid4().hex
        payload = {'request_id':request_id, **deepcopy(fields)}
        if round_id is not None:
            payload['round_id'] = round_id
        if not self._ready.is_set():
            self.events.put(TransportError('OFFLINE'))
            return None
        self._outbound.put((event, payload))
        return request_id

    def disconnect(self):
        self._ready.clear()
        self._stop.set()
        loop, task = self._loop, self._task
        if loop is not None and task is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)

    def join(self, timeout=None):
        if self._thread:
            self._thread.join(timeout)
        return self._thread is None or not self._thread.is_alive()

    def _worker(self, credentials):
        asyncio.run(self._run(credentials))

    async def _run(self, credentials):
        self._loop, self._task = asyncio.get_running_loop(), asyncio.current_task()
        session = aiohttp.ClientSession()
        c = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False, http_session=session)

        @c.on(credentials.role + '_state')
        async def snapshot(data):
            if isinstance(data, dict):
                self.events.put(SnapshotReceived(deepcopy(data)))

        @c.on('disconnect')
        async def disconnected(*args):
            self._ready.clear()
            self._discard_pending()
            if not self._stop.is_set():
                self.events.put(ConnectionChanged('reconnecting'))

        first = True
        try:
            while not self._stop.is_set():
                if not c.connected:
                    self.events.put(ConnectionChanged('connecting' if first else 'reconnecting'))
                    first = False
                    try:
                        await c.connect(credentials.url, transports=['websocket'], wait_timeout=self.ack_timeout)
                        data = {} if credentials.role == 'viewer' else {'token':credentials.token}
                        if credentials.role == 'coach':
                            data['coachId'] = credentials.coach_id
                        ack = await c.call('join_' + credentials.role, data, timeout=self.ack_timeout)
                        if not ack.get('ok'):
                            self.events.put(TransportError('AUTH_FAILED'))
                            break
                        self.events.put(SnapshotReceived(deepcopy(ack['payload']['snapshot'])))
                        self._ready.set()
                        self.events.put(ConnectionChanged('connected'))
                    except Exception:
                        self.events.put(TransportError('CONNECTION_FAILED'))
                        if c.connected:
                            await c.disconnect()
                        await asyncio.sleep(self.retry_delay)
                        continue
                try:
                    event, payload = self._outbound.get_nowait()
                except Empty:
                    await asyncio.sleep(0.02)
                    continue
                if not self._ready.is_set():
                    self.events.put(TransportError('UNCONFIRMED'))
                    continue
                try:
                    ack = await c.call(event, payload, timeout=self.ack_timeout)
                    self.events.put(CommandAckReceived(deepcopy(ack)))
                except Exception:
                    self.events.put(TransportError('UNCONFIRMED'))
        except asyncio.CancelledError:
            pass
        finally:
            self._ready.clear()
            self._discard_pending()
            try:
                if c.connected:
                    await c.disconnect()
                await c.shutdown()
            finally:
                await session.close()
                self.events.put(ConnectionChanged('offline'))

    def _discard_pending(self):
        discarded = False
        while True:
            try:
                self._outbound.get_nowait()
                discarded = True
            except Empty:
                break
        if discarded:
            self.events.put(TransportError('UNCONFIRMED'))
