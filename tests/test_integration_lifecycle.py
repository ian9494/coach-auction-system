"""Classroom-scale E2E, reconnection, durable replay and fresh-app recovery."""
import asyncio
import httpx
import pytest

from .live_support import live, eventually
from .transport_support import config_and_auth
from .service_support import FakeClock
from .test_projections import FORBIDDEN, keys


def test_e2e_reconnect_stress_and_ack_loss(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            admin, _ = await r.join('admin')
            viewer, _ = await r.join('viewer')
            coaches = [(await r.join('coach', f'coach{i:02d}'))[0] for i in range(1, 9)]
            start = await r.command(admin, 'start_auction', 'start', playerName='Player17', duration=90)
            round_id = start['round_id']
            await eventually(lambda: all(c.frames[-1]['round_id'] == round_id for c in coaches))
            async def bids(index, c):
                for n in range(12):
                    ack = await r.command(c, 'submit_bid', f'b{n}', amount=110 + index * 20 + n)
                    assert ack['ok']
                return ack
            acks = await asyncio.gather(*(bids(i, c) for i, c in enumerate(coaches)))
            service = r.app.runtime.service
            snap = service.snapshot()
            assert [snap.state.bids[f'coach{i:02d}'] for i in range(1, 9)] == [121+i*20 for i in range(8)]
            assert service._repository.load().state == snap.state
            await eventually(lambda: all(c.frames[-1]['version'] == snap.version for c in [admin, viewer, *coaches]))
            for c in [admin, viewer, *coaches]:
                assert [f['version'] for f in c.frames] == sorted(f['version'] for f in c.frames)
            assert admin.frames[-1]['allBids'] == snap.state.bids
            assert all(not keys(f) & FORBIDDEN for f in viewer.frames)
            assert all(f['winner'] is None and f['winning_amount'] is None for f in viewer.frames)
            for i, c in enumerate(coaches):
                assert c.frames[-1]['myBid'] == 121+i*20
                assert 'allBids' not in keys(c.frames[-1]) and 'bids' not in keys(c.frames[-1])
            await coaches[0].disconnect()
            await viewer.disconnect()
            await admin.disconnect()
            r.clock.advance(7)
            coaches[0], own = await r.join('coach')
            viewer, public = await r.join('viewer')
            admin, management = await r.join('admin')
            assert own['myBid'] == 121 and own['remaining_seconds'] == 83
            assert public['version'] == management['version'] == service.snapshot().version
            assert not keys(public) & FORBIDDEN
            assert (await r.command(coaches[0], 'submit_bid', 'b11', amount=121)) == acks[0]
            assert (await r.command(coaches[0], 'submit_bid', 'b11', amount=122))['error_code'] == 'REQUEST_ID_CONFLICT'
            assert (await r.command(admin, 'pause_auction', 'pause'))['ok']
            version = service.snapshot().version
            assert not (await r.command(coaches[0], 'submit_bid', 'paused', amount=300))['ok']
            assert service.snapshot().version == version
            r.clock.advance(20)
            assert service.snapshot().remaining == 83
            assert (await r.command(admin, 'resume_auction', 'resume'))['ok']
            # Send without a callback: the command commits but its ACK is deliberately unobserved.
            lost_bid = {'request_id': 'lostbid', 'round_id': round_id, 'amount': 300}
            await coaches[0].emit('submit_bid', lost_bid)
            await eventually(lambda: service.snapshot().state.bids['coach01'] == 300)
            version = service.snapshot().version
            replay = await coaches[0].call('submit_bid', lost_bid, timeout=5)
            assert replay['ok'] and replay['version'] == version == service.snapshot().version
            lost_end = {'request_id': 'lostend', 'round_id': round_id}
            await admin.emit('end_auction', lost_end)
            await eventually(lambda: len(service.snapshot().state.history) == 1)
            settled = service.snapshot()
            assert settled.state.winner == 'coach01' and settled.state.winning_amount == 300
            assert settled.state.budgets['coach01'] == snap.state.budgets['coach01'] - 300
            assert (await admin.call('end_auction', lost_end, timeout=5))['version'] == settled.version
            await eventually(lambda: viewer.frames[-1]['status'] == 'ended')
            async with httpx.AsyncClient(base_url=r.url) as http:
                assert (await http.get('/api/state/viewer')).json() == viewer.frames[-1]
                assert (await http.get('/api/results')).json() == [{'playerName':'Player17','coachId':'coach01','amount':300}]
            lost_undo = {'request_id': 'lostundo', 'round_id': round_id}
            await admin.emit('undo_last_award', lost_undo)
            await eventually(lambda: not service.snapshot().state.history)
            undone = service.snapshot()
            assert (await admin.call('undo_last_award', lost_undo, timeout=5))['version'] == undone.version
            assert service.snapshot().state.budgets == snap.state.budgets
            next_round = await r.command(admin, 'start_auction', 'next', playerName='Player18', duration=90)
            assert next_round['round_id'] != round_id
            assert service.snapshot().state.winner is None and set(service.snapshot().state.bids.values()) == {0}
            # New request targeting the old round cannot mutate the next round.
            assert (await r.command(coaches[0], 'submit_bid', 'stale', round_id=round_id, amount=400))['error_code'] == 'STALE_ROUND'
    asyncio.run(asyncio.wait_for(run(), 40))


@pytest.mark.parametrize('mode', ['running', 'expired', 'paused', 'ended'])
def test_fresh_app_restart_and_durable_replays(tmp_path, mode):
    async def run():
        config, auth = config_and_auth(tmp_path)
        clock = FakeClock()
        async with live(config, auth, clock) as r:
            admin, _ = await r.join('admin')
            coach, _ = await r.join('coach')
            await r.command(admin, 'start_auction', 'start', playerName='Player17', duration=90)
            payload = {'request_id':'bid', 'round_id':r.app.runtime.service.snapshot().round_id, 'amount':250}
            original = await coach.call('submit_bid', payload, timeout=5)
            other, _ = await r.join('coach', 'coach02')
            assert (await r.command(other, 'submit_bid', 'tie', amount=250))['ok']
            clock.advance(10)
            if mode == 'paused':
                assert (await r.command(admin, 'pause_auction', 'pause'))['ok']
            elif mode == 'ended':
                assert (await r.command(admin, 'end_auction', 'end'))['ok']
            before = r.app.runtime.service.snapshot()
        clock.advance(100 if mode in ('expired', 'paused') else 5)
        async with live(config, auth, clock) as r:
            coach, own = await r.join('coach')
            viewer, public = await r.join('viewer')
            admin, _ = await r.join('admin')
            assert (await coach.call('submit_bid', payload, timeout=5)) == original
            restored = r.app.runtime.service.snapshot()
            assert restored.round_id == before.round_id
            assert own['myBid'] == 250 and not keys(public) & FORBIDDEN
            if mode == 'running':
                assert restored.state.status == 'running' and restored.remaining == 75
                assert r.timer.callback is not None
            elif mode == 'paused':
                assert restored.state.status == 'paused' and restored.remaining == 80
                assert r.timer.callback is None
            else:
                assert restored.state.status == 'ended' and len(restored.state.history) == 1
                assert restored.state.winner == 'coach01' and restored.state.winning_amount == 250
                assert restored.state.budgets['coach01'] == before.state.budgets['coach01'] - (250 if mode == 'expired' else 0)
            persistent = r.app.runtime.service._repository.load()
        # Another fresh app must never redraw or apply the award again.
        async with live(config, auth, clock, rng=lambda: 0.99) as r:
            assert r.app.runtime.service._repository.load() == persistent
            await r.join('viewer')
    asyncio.run(asyncio.wait_for(run(), 30))


def test_restart_replays_end_and_undo_without_reapplying(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        clock = FakeClock()
        async with live(config, auth, clock) as r:
            admin, _ = await r.join('admin')
            coach, _ = await r.join('coach')
            await r.command(admin, 'start_auction', 'start', playerName='Player17', duration=90)
            await r.command(coach, 'submit_bid', 'bid', amount=250)
            end = {'request_id':'end', 'round_id':r.app.runtime.service.snapshot().round_id}
            await admin.emit('end_auction', end)
            await eventually(lambda: len(r.app.runtime.service.snapshot().state.history) == 1)
            settled = r.app.runtime.service.snapshot()
        async with live(config, auth, clock) as r:
            admin, _ = await r.join('admin')
            assert (await admin.call('end_auction', end, timeout=5))['version'] == settled.version
            assert r.app.runtime.service.snapshot() == settled
            conflict = {**end, 'request_id':'end', 'round_id':'different-round'}
            assert (await admin.call('end_auction', conflict, timeout=5))['error_code'] == 'REQUEST_ID_CONFLICT'
            undo = {**end, 'request_id':'undo'}
            await admin.emit('undo_last_award', undo)
            await eventually(lambda: not r.app.runtime.service.snapshot().state.history)
            undone = r.app.runtime.service.snapshot()
        async with live(config, auth, clock) as r:
            admin, _ = await r.join('admin')
            assert (await admin.call('undo_last_award', undo, timeout=5))['version'] == undone.version
            assert r.app.runtime.service.snapshot() == undone
    asyncio.run(asyncio.wait_for(run(), 30))
