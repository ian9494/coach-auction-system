"""Socket.IO adapter; identity comes from a fixed session, mutations from service."""
import asyncio
from dataclasses import asdict
import hashlib
import json
import logging

from .commands import Command
from .projections import admin_projection, coach_projection, viewer_projection
from .schemas import EVENTS, PayloadError, mutation_payload, request_id_of

logger = logging.getLogger(__name__)


class SocketTransport:
    def __init__(self, sio, runtime):
        self.sio, self.runtime = sio, runtime
        self._session_locks = {}
        self._broadcast_lock = asyncio.Lock()
        self._last_version = -1
        self._last_remaining = None
        self.register()

    def error(self, code, request_id=None):
        service = self.runtime.service
        snapshot = service.snapshot() if service else None
        return {'ok': False, 'error_code': code, 'message': code,
                'version': snapshot.version if snapshot else 0,
                'round_id': snapshot.round_id if snapshot else None,
                'request_id': request_id, 'payload': {}}

    async def broadcast(self, snapshot):
        async with self._broadcast_lock:
            if snapshot.version < self._last_version:
                return
            if (snapshot.version == self._last_version and snapshot.state.status == 'running'
                    and self._last_remaining is not None and snapshot.remaining > self._last_remaining):
                return
            self._last_version = snapshot.version
            self._last_remaining = snapshot.remaining
            await self._emit_room('viewer_state', viewer_projection(snapshot), 'viewer')
            await self._emit_room('admin_state', admin_projection(snapshot), 'admin')
            for coach in snapshot.state.coaches:
                await self._emit_room('coach_state', coach_projection(snapshot, coach.id), f'coach:{coach.id}')

    async def _emit_room(self, event, projection, room):
        try:
            await self.sio.emit(event, projection, room=room)
        except Exception:
            # A failed recipient must not suppress updates to other roles.
            # Full snapshots on rejoin recover missed delivery; commit remains authoritative.
            logger.warning('Socket room broadcast failed event=%s version=%s', event, projection['version'])

    async def join(self, sid, role, data):
        if not self.runtime.ready:
            return self.error('SERVICE_NOT_READY')
        if data is None and role == 'viewer':
            data = {}
        if not isinstance(data, dict):
            return self.error('INVALID_PAYLOAD')
        expected = set() if role == 'viewer' else {'token'} if role == 'admin' else {'token', 'coachId'}
        if set(data) != expected or (role != 'viewer' and not isinstance(data.get('token'), str)):
            return self.error('INVALID_PAYLOAD')
        coach_id = data.get('coachId') if role == 'coach' else None
        if role == 'coach' and (not isinstance(coach_id, str) or coach_id not in self.runtime.auth.coach_tokens):
            return self.error('UNKNOWN_COACH')
        lock = self._session_locks.get(sid)
        if lock is None:
            return self.error('UNAUTHORIZED')
        async with lock:
            session = await self.sio.get_session(sid)
            if session['joined'] and (session['role'], session['coach_id']) != (role, coach_id):
                return self.error('FORBIDDEN')
            if role != 'viewer' and not self.runtime.auth.check(role, data['token'], coach_id):
                return self.error('UNAUTHORIZED')
            await self.sio.save_session(sid, {'role': role, 'coach_id': coach_id,
                'authenticated': True, 'joined': True})
            room = f'coach:{coach_id}' if role == 'coach' else role
            await self.sio.enter_room(sid, room)
            snapshot = self.runtime.service.snapshot()
            projection = coach_projection(snapshot, coach_id) if role == 'coach' else admin_projection(snapshot) if role == 'admin' else viewer_projection(snapshot)
            await self.sio.emit(f'{role}_state', projection, to=sid)
            return {'ok': True, 'error_code': None, 'message': 'OK', 'version': snapshot.version,
                'round_id': snapshot.round_id, 'request_id': None,
                'payload': {'role': role, 'snapshot': projection}}

    async def mutation(self, event, sid, data):
        request_id = request_id_of(data)
        if not self.runtime.ready:
            return self.error('SERVICE_NOT_READY', request_id)
        lock = self._session_locks.get(sid)
        if lock is None:
            return self.error('UNAUTHORIZED', request_id)
        async with lock:
            session = await self.sio.get_session(sid)
            if not session['authenticated'] or not session['joined']:
                return self.error('UNAUTHORIZED', request_id)
            required = 'coach' if event == 'submit_bid' else 'admin'
            if session['role'] != required:
                return self.error('FORBIDDEN', request_id)
            if event in ('add_all_budgets', 'reset_auction'):
                return self.error('NOT_IMPLEMENTED', request_id)
            try:
                request_id, round_id, payload = mutation_payload(event, data)
            except PayloadError:
                return self.error('INVALID_PAYLOAD', request_id)
            if event == 'submit_bid':
                payload['coach_id'] = session['coach_id']
            # Principal namespace survives reconnect/restart and prevents cross-role ID collisions.
            principal = json.dumps([session['role'], session['coach_id']], separators=(',', ':'))
            internal_id = f"client:{hashlib.sha256(principal.encode()).hexdigest()}:{request_id}"
            result = await self.runtime.service.execute(Command(EVENTS[event], internal_id, round_id, payload))
            return {**asdict(result), 'request_id': request_id}

    def register(self):
        @self.sio.on('connect')
        async def connect(sid, environ, auth=None):
            if not self.runtime.ready:
                return False
            self._session_locks[sid] = asyncio.Lock()
            await self.sio.save_session(sid, {'role': None, 'coach_id': None, 'authenticated': False, 'joined': False})
            return True

        @self.sio.on('disconnect')
        async def disconnect(sid, reason=None):
            self._session_locks.pop(sid, None)

        def safe_join(role):
            async def handler(sid, data=None, *extra):
                if extra:
                    return self.error('INVALID_PAYLOAD')
                try:
                    return await self.join(sid, role, data)
                except Exception:
                    logger.warning('Socket join failed')
                    return self.error('INTERNAL_ERROR')
            return handler

        for role in ('viewer', 'admin', 'coach'):
            self.sio.on(f'join_{role}', handler=safe_join(role))

        def safe_mutation(event):
            async def handler(sid, data=None, *extra):
                if extra:
                    return self.error('INVALID_PAYLOAD')
                try:
                    return await self.mutation(event, sid, data)
                except Exception:
                    logger.warning('Socket command failed')
                    return self.error('INTERNAL_ERROR', request_id_of(data))
            return handler

        for event in (*EVENTS, 'add_all_budgets', 'reset_auction'):
            self.sio.on(event, handler=safe_mutation(event))

        @self.sio.on('*')
        async def unknown(event, sid, *data):
            return self.error('UNKNOWN_EVENT', request_id_of(data[0]) if data else None)
