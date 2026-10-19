"""One-shot anonymous registration, outside the Tk thread. Never retry a lost ACK."""
import asyncio
from queue import Queue
import threading
import socketio
from .transport import Credentials


class RegistrationWorker:
    def __init__(self, url, coach_id, invite, username, password):
        Credentials(url, 'viewer').validate()
        self.events = Queue()
        self.thread = threading.Thread(target=self._worker,
            args=(url, {'coachId': coach_id, 'invite': invite, 'username': username, 'password': password}),
            daemon=True, name='coach-registration')

    def start(self):
        self.thread.start()

    def _worker(self, url, data):
        asyncio.run(self._run(url, data))

    async def _run(self, url, data):
        c = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
        result = {'ok': False, 'error_code': 'REGISTRATION_UNCONFIRMED'}
        try:
            await c.connect(url, transports=['websocket'], wait_timeout=5)
            result = await c.call('register_coach', data, timeout=10)
        except Exception:
            pass
        finally:
            try:
                if c.connected: await c.disconnect()
                await c.shutdown()
            finally:
                self.events.put(result)
