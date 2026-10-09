"""Failure injection over real sockets; deterministic serialization through handlers."""
import asyncio
import pytest

from final_project.storage.repository import RepositoryError
from .live_support import live, eventually
from .transport_support import config_and_auth, running_app, client, request


def test_live_commit_room_payload_and_abrupt_disconnect_failures(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            admin, _ = await r.join('admin')
            viewer, _ = await r.join('viewer')
            coach, _ = await r.join('coach')
            await r.command(admin, 'start_auction', 'start', playerName='Player17', duration=90)
            service = r.app.runtime.service
            await eventually(lambda: viewer.frames[-1]['version'] == service.snapshot().version)
            before = service.snapshot()
            repository = service._repository
            commit = repository.commit
            def fail(snapshot):
                raise RepositoryError('synthetic commit failure')
            repository.commit = fail
            try:
                ack = await r.command(coach, 'submit_bid', 'retry', amount=300)
                assert ack['error_code'] == 'PERSISTENCE_ERROR'
                assert service.snapshot() == before
                assert all(f['version'] <= before.version for f in viewer.frames)
            finally:
                repository.commit = commit
            emit = r.app.sio.emit
            failures = []
            async def fail_viewer(event, data, **kwargs):
                if kwargs.get('room') == 'viewer':
                    failures.append(data['version'])
                    raise RuntimeError('synthetic room failure')
                return await emit(event, data, **kwargs)
            r.app.sio.emit = fail_viewer
            try:
                accepted = await r.command(coach, 'submit_bid', 'retry', amount=300)
                assert accepted['ok']
                await eventually(lambda: admin.frames[-1]['version'] == accepted['version'] and failures)
                await eventually(lambda: coach.frames[-1]['myBid'] == 300)
                assert repository.load().state.bids['coach01'] == 300
                recovered, snapshot = await r.join('viewer')
                assert snapshot['version'] == accepted['version']
            finally:
                r.app.sio.emit = emit
            for malformed in (None, [], {'request_id':'bad','amount':True}, {'request_id':'bad','round_id':before.round_id,'amount':200,'coachId':'coach08'}):
                assert not (await coach.call('submit_bid', malformed, timeout=5))['ok']
            assert (await r.command(coach, 'submit_bid', 'healthy', amount=310))['ok']
            # Close underlying websocket without a Socket.IO disconnect message.
            await coach.eio.ws.close()
            await eventually(lambda: not coach.connected)
            clock_remaining = service.snapshot().remaining
            r.clock.advance(3)
            assert service.snapshot().remaining == clock_remaining - 3
            new_coach, own = await r.join('coach')
            assert own['myBid'] == 310
            assert (await r.command(admin, 'end_auction', 'end'))['ok']
            assert len(repository.load().state.history) == 1
    asyncio.run(asyncio.wait_for(run(), 30))


@pytest.mark.parametrize('event', ['submit_bid', 'end_auction', 'pause_auction'])
@pytest.mark.parametrize('timeout_first', [False, True])
def test_deadline_serialization(tmp_path, event, timeout_first):
    async def run():
        async with running_app(tmp_path) as (app, auth, clock, timer):
            admin, _ = await client(app, 'admin', 'admin', auth)
            coach, _ = await client(app, 'coach', 'coach', auth)
            await admin.call('start_auction', {'request_id':'start','playerName':'Player17','duration':90})
            clock.advance(89.999)
            assert (await coach.call('submit_bid', request(app, 'early', amount=200)))['ok']
            callback = timer.callback
            clock.advance(0.002)
            service = app.runtime.service
            target = coach if event == 'submit_bid' else admin
            payload = request(app, 'boundary', **({'amount':300} if event == 'submit_bid' else {}))
            # Hold authority lock so both requests queue in a known order.
            await service._lock.acquire()
            try:
                operations = [callback, lambda: target.call(event, payload)]
                if not timeout_first:
                    operations.reverse()
                tasks = []
                for operation in operations:
                    tasks.append(asyncio.create_task(operation()))
                    await asyncio.sleep(0)
            finally:
                service._lock.release()
            results = await asyncio.gather(*tasks)
            ack = next(result for result in results if isinstance(result, dict))
            if event == 'end_auction':
                assert ack['ok']
            else:
                assert not ack['ok']
            snap = service.snapshot()
            assert snap.state.status == 'ended' and len(snap.state.history) == 1
            assert snap.state.winning_amount == 200
            assert service._repository.load().state == snap.state
            assert await callback()
            assert service.snapshot().version == snap.version
    asyncio.run(run())


@pytest.mark.parametrize('start_first', [False, True])
def test_rejoined_old_round_request_vs_new_start(tmp_path, start_first):
    async def run():
        async with running_app(tmp_path) as (app, auth, clock, timer):
            admin, _ = await client(app, 'admin', 'admin', auth)
            coach, _ = await client(app, 'coach', 'coach', auth)
            await admin.call('start_auction', {'request_id':'start','playerName':'Player17','duration':90})
            old = request(app, 'old-new-id', amount=300)
            await admin.call('end_auction', request(app, 'end'))
            await coach.disconnect()
            coach, _ = await client(app, 'rejoined', 'coach', auth)
            service = app.runtime.service
            await service._lock.acquire()
            try:
                operations = [lambda: admin.call('start_auction', {'request_id':'next','playerName':'Player18','duration':90}),
                              lambda: coach.call('submit_bid', old)]
                if not start_first:
                    operations.reverse()
                tasks = []
                for operation in operations:
                    tasks.append(asyncio.create_task(operation()))
                    await asyncio.sleep(0)
            finally:
                service._lock.release()
            results = await asyncio.gather(*tasks)
            rejection = next(result for result in results if not result['ok'])
            assert rejection['error_code'] == ('STALE_ROUND' if start_first else 'INVALID_STATE')
            assert service.snapshot().round_id != old['round_id']
            assert service.snapshot().state.bids['coach01'] == 301
            assert all(value == 0 for cid, value in service.snapshot().state.bids.items() if cid != 'coach01')
            assert len(service.snapshot().state.history) == 1
    asyncio.run(run())
