"""Account ownership, durable credentials and real client/server registration."""
import asyncio
import sqlite3
import socketio
import pytest

from final_project.client.registration import RegistrationWorker
from final_project.client.transport import ClientTransport, Credentials, ConnectionChanged, SnapshotReceived
from .transport_support import config_and_auth
from .live_support import live, eventually
from .test_client_transport import receive

PASSWORD = 'test-only-password-2026'


async def anonymous(r):
    c = socketio.AsyncClient(reconnection=False)
    r.clients.append(c)
    await c.connect(r.url, transports=['websocket'])
    return c


def registration(auth, **overrides):
    return {'coachId': 'coach01', 'invite': auth.coach_tokens['coach01'],
            'username': 'demo_user', 'password': PASSWORD, **overrides}


def test_registration_login_reconnect_restart_and_token_revocation(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            old, _ = await r.join('coach')
            c = await anonymous(r)
            assert (await c.call('register_coach', registration(auth)))['ok']
            await eventually(lambda: not old.connected)
            assert (await c.call('join_coach', {'coachId':'coach01', 'token':auth.coach_tokens['coach01']}))['error_code'] == 'UNAUTHORIZED'
            assert not (await c.call('join_coach', {'username':'demo_user', 'password':'wrong-password'}))['ok']
            joined = await c.call('join_coach', {'username':'DEMO_USER', 'password':PASSWORD})
            assert joined['ok'] and joined['payload']['snapshot']['coach']['id'] == 'coach01'
            assert (await c.call('register_coach', registration(auth)))['error_code'] == 'FORBIDDEN'
            admin, _ = await r.join('admin')
            start = await r.command(admin, 'start_auction', 'start', playerName='Player17', duration=90)
            assert (await c.call('submit_bid', {'request_id':'bid', 'round_id':start['round_id'], 'amount':250}))['ok']
            assert not (await c.call('end_auction', {'request_id':'bad', 'round_id':start['round_id']}))['ok']
            await c.disconnect()
            c = await anonymous(r)
            joined = await c.call('join_coach', {'username':'demo_user', 'password':PASSWORD})
            assert joined['payload']['snapshot']['myBid'] == 250
            viewer, public = await r.join('viewer')
            assert 'password' not in str(public) and 'username' not in str(public)
        async with live(config, auth) as r:
            c = await anonymous(r)
            joined = await c.call('join_coach', {'username':'demo_user', 'password':PASSWORD})
            assert joined['ok'] and joined['payload']['snapshot']['myBid'] == 250
        with sqlite3.connect(config.path(config.sqlite_file)) as db:
            row = db.execute('SELECT salt,password_hash FROM coach_accounts').fetchone()
            assert len(row[0]) == 16 and len(row[1]) == 64
        assert PASSWORD.encode() not in config.path(config.sqlite_file).read_bytes()
    asyncio.run(asyncio.wait_for(run(), 25))


@pytest.mark.parametrize('override,code', [
    ({'invite':'bad'}, 'INVALID_INVITE'), ({'coachId':'admin'}, 'INVALID_INVITE'),
    ({'username':'a'}, 'INVALID_ACCOUNT'), ({'username':['demo']}, 'INVALID_ACCOUNT'),
    ({'password':'short'}, 'INVALID_ACCOUNT'), ({'password':'a'*129}, 'INVALID_ACCOUNT'),
    ({'username':'x; DROP TABLE snapshot'}, 'INVALID_ACCOUNT'),
])
def test_invalid_registration_has_no_auction_side_effects(tmp_path, override, code):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            c = await anonymous(r)
            before = r.app.runtime.service.snapshot()
            assert (await c.call('register_coach', registration(auth, **override)))['error_code'] == code
            assert r.app.runtime.service.snapshot() == before
            assert not r.app.runtime.accounts.claimed('coach01')
    asyncio.run(run())


def test_registration_races_cannot_share_username_or_seat(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            clients = [await anonymous(r) for _ in range(3)]
            results = await asyncio.gather(*(c.call('register_coach', registration(auth, username=f'user{i}')) for i,c in enumerate(clients)))
            assert sum(bool(a['ok']) for a in results) == 1
            winner = next(i for i,a in enumerate(results) if a['ok'])
            duplicate = await clients[(winner+1)%3].call('register_coach', registration(auth,
                coachId='coach02', invite=auth.coach_tokens['coach02'], username=f'USER{winner}'))
            assert duplicate['error_code'] == 'ACCOUNT_OR_SEAT_TAKEN'
            assert not r.app.runtime.accounts.claimed('coach02')
            assert (await clients[0].call('register_coach', {**registration(auth), 'role':'admin'}))['error_code'] == 'INVALID_PAYLOAD'
    asyncio.run(run())


def test_worker_registers_then_threaded_transport_logs_in(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            worker = RegistrationWorker(r.url, 'coach01', auth.coach_tokens['coach01'], 'worker_user', PASSWORD)
            worker.start()
            result = await asyncio.to_thread(worker.events.get, True, 10)
            assert result['ok']
            await asyncio.to_thread(worker.thread.join, 5)
            assert not worker.thread.is_alive()
            credentials = Credentials(r.url, 'coach', username='worker_user', password=PASSWORD)
            assert PASSWORD not in repr(credentials)
            t = ClientTransport(retry_delay=.05)
            try:
                t.connect(credentials)
                async with asyncio.timeout(10):
                    while True:
                        event = await asyncio.to_thread(t.events.get, True, 5)
                        if isinstance(event, SnapshotReceived):
                            assert event.snapshot['coach']['id'] == 'coach01'
                        if isinstance(event, ConnectionChanged) and event.state == 'connected': break
                assert t._ready.is_set()
                sid = next(iter(r.app.sio.manager.get_participants('/', 'coach:coach01')))[0]
                await r.app.sio.disconnect(sid)
                await receive(t, ConnectionChanged, lambda event: event.state == 'reconnecting')
                await receive(t, ConnectionChanged, lambda event: event.state == 'connected')
                assert t._ready.is_set()
            finally:
                t.disconnect()
                assert await asyncio.to_thread(t.join, 5)
    asyncio.run(asyncio.wait_for(run(), 25))
