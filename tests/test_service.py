import asyncio
from copy import deepcopy
import pytest
from final_project.server.commands import Command, CommandKind
from .service_support import create, command, dispose


def test_full_lifecycle_persistence_versions_and_undo(tmp_path):
    async def run():
        s,r,c,t = await create(tmp_path)
        try:
            start = await command(s,'start','start',player_name='Player17',duration=90)
            assert start.ok and start.version==1 and start.round_id
            assert r.load()==s._snapshot
            assert t.deadline==190
            bid = await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
            assert bid.ok and bid.version==2 and r.load().state.bids['coach01']==200
            c.advance(10.25)
            pause = await command(s,'pause','pause')
            assert pause.ok and pause.version==3
            assert r.load().remaining==79.75 and r.load().state.time_left==80
            assert t.deadline is None and r.load().deadline_utc is None
            c.advance(100)
            assert s.snapshot().remaining==79.75
            assert (await command(s,'submit_bid','paused-bid',coach_id='coach01',amount=300)).error_code=='INVALID_STATE'
            resume = await command(s,'resume','resume')
            assert resume.ok and resume.version==4 and t.deadline==290
            assert r.load().deadline_utc==1190
            minimum = await command(s,'set_minimum_bid','minimum',amount=100)
            assert minimum.ok and minimum.version==5
            end = await command(s,'end','end')
            assert end.ok and end.version==6 and r.load().state.budgets['coach01']==800
            assert r.load().settled_round_id==start.round_id and t.deadline is None
            assert r.load().state.last_award_undo is not None
            undo = await command(s,'undo','undo')
            assert undo.ok and undo.version==7 and r.load().state.budgets['coach01']==1000
            assert r.load().state.history==[] and r.load().state.last_award_undo is None
            assert (await command(s,'undo','undo'))==undo
            again = await command(s,'start','next',player_name='Player18')
            assert again.ok and again.round_id!=start.round_id and again.version==8
        finally: await dispose(s,r)
    asyncio.run(run())


def test_stale_duplicate_conflict_and_defensive_copy(tmp_path):
    async def run():
        s,r,c,t = await create(tmp_path)
        try:
            started=await command(s,'start','start',player_name='Player17')
            result=await command(s,'submit_bid','bid',coach_id='coach01',amount=100)
            assert await command(s,'submit_bid','bid',coach_id='coach01',amount=100)==result
            assert (await command(s,'submit_bid','bid',coach_id='coach01',amount=200)).error_code=='REQUEST_ID_CONFLICT'
            stale=await s.execute(Command(CommandKind.SUBMIT_BID,'stale','old',{'coach_id':'coach01','amount':200}))
            assert stale.error_code=='STALE_ROUND' and stale.version==2
            missing=await s.execute(Command(CommandKind.SUBMIT_BID,'missing',None,{'coach_id':'coach01','amount':200}))
            assert missing.error_code=='STALE_ROUND'
            view=s.snapshot(); view.state.budgets['coach01']=0
            result.payload['changed']=False
            assert s.snapshot().state.budgets['coach01']==1000
            assert (await command(s,'submit_bid','bid',coach_id='coach01',amount=100)).payload['changed'] is True
        finally: await dispose(s,r)
    asyncio.run(run())


def test_duplicate_end_undo_and_noop_versions(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17')
            await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
            same=await command(s,'submit_bid','same',coach_id='coach01',amount=200)
            assert same.version==2 and same.payload['changed'] is False
            end=await command(s,'end','end')
            assert await command(s,'end','end')==end
            assert (await command(s,'end','other-end')).version==3
            assert len(s.snapshot().state.history)==1 and s.snapshot().state.budgets['coach01']==800
            await command(s,'undo','undo')
            assert (await command(s,'end','after-undo')).version==4
            assert not s.snapshot().state.history
        finally: await dispose(s,r)
    asyncio.run(run())


def test_deadline_late_bid_and_repeated_timeout(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17',duration=5)
            await command(s,'submit_bid','bid',coach_id='coach01',amount=250)
            callback=t.callback
            c.advance(5)
            late=await command(s,'submit_bid','late',coach_id='coach02',amount=500)
            assert late.error_code=='DEADLINE_PASSED'
            assert s.snapshot().state.winner=='coach01' and len(s.snapshot().state.history)==1
            assert await callback() is True
            assert await callback() is True
            assert s.snapshot().version==3 and r.load().state.budgets['coach01']==750
        finally: await dispose(s,r)
    asyncio.run(run())


def test_pause_invalidates_old_timer_and_resume_deadline(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17',duration=10)
            old=t.callback
            c.advance(3)
            await command(s,'pause','pause')
            c.advance(30)
            assert await old() is True
            assert s.snapshot().state.status=='paused'
            await command(s,'resume','resume')
            assert t.deadline==140
            assert await old() is True
            c.advance(7)
            assert await t.callback() is True
            assert s.snapshot().state.status=='ended'
        finally: await dispose(s,r)
    asyncio.run(run())


def test_monotonic_live_deadline_survives_wall_clock_jump(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17',duration=10)
            c.wall+=10000
            assert (await command(s,'submit_bid','bid',coach_id='coach01',amount=200)).ok
            c.mono+=10
            assert (await command(s,'submit_bid','late',coach_id='coach01',amount=300)).error_code=='DEADLINE_PASSED'
        finally: await dispose(s,r)
    asyncio.run(run())


def test_persistence_failure_memory_db_and_timer_unchanged(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17')
            before=deepcopy(s._snapshot); timer_deadline=t.deadline
            r._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT,'failure'); END")
            for kind,payload in [('submit_bid',{'coach_id':'coach01','amount':200}),('pause',{}),('end',{})]:
                result=await command(s,kind,'failed-'+kind,**payload)
                assert result.error_code=='PERSISTENCE_ERROR' and not result.ok
                assert s._snapshot==before and r.load()==before and t.deadline==timer_deadline
            r._connection.execute('DROP TRIGGER fail_update')
            assert (await command(s,'submit_bid','failed-submit_bid',coach_id='coach01',amount=200)).ok
        finally: await dispose(s,r)
    asyncio.run(run())


def test_timeout_persistence_failure_can_retry(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17',duration=1)
            callback=t.callback; c.advance(1)
            r._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT,'failure'); END")
            assert await callback() is False
            assert s.snapshot().state.status=='running' and r.load().state.status=='running'
            r._connection.execute('DROP TRIGGER fail_update')
            assert await callback() is True
            assert s.snapshot().state.status=='ended' and len(r.load().state.history)==1
        finally: await dispose(s,r)
    asyncio.run(run())


def test_eight_coaches_concurrent_bid_updates_tie(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path,rng=lambda:0.99)
        try:
            await command(s,'start','start',player_name='Player17')
            results=await asyncio.gather(*(command(s,'submit_bid',f'bid-{i}-{n}',coach_id=f'coach{i:02d}',amount=n)
                for n in (100,200,300) for i in range(1,9)))
            assert all(x.ok for x in results)
            assert s.snapshot().version==25
            assert all(v==300 for v in s.snapshot().state.bids.values())
            await asyncio.gather(command(s,'end','end-a'),command(s,'end','end-b'))
            assert s.snapshot().state.winner=='coach08'
            assert len(r.load().state.history)==1 and r.load().state.budgets['coach08']==700
        finally: await dispose(s,r)
    asyncio.run(run())


@pytest.mark.parametrize('kind,payload,error',[
    ('submit_bid',{'coach_id':'missing','amount':100},'UNKNOWN_COACH'),
    ('submit_bid',{'coach_id':'coach01','amount':True},'INVALID_BID'),
    ('submit_bid',{'coach_id':'coach01','amount':501},'INVALID_BID'),
    ('submit_bid',{'coach_id':'coach01'},'INVALID_COMMAND'),
    ('pause',{'unexpected':True},'INVALID_COMMAND'),
])
def test_stable_errors(tmp_path,kind,payload,error):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17')
            result=await command(s,kind,'bad',**payload)
            assert not result.ok and result.error_code==error and result.version==1
            assert await command(s,kind,'bad',**payload)==result
        finally: await dispose(s,r)
    asyncio.run(run())


def test_start_commit_failure_keeps_idle_and_no_timer(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            before=s.snapshot()
            r._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT,'failure'); END")
            result=await command(s,'start','start',player_name='Player17')
            assert result.error_code=='PERSISTENCE_ERROR'
            assert s.snapshot()==before and r.load()==before and t.callback is None
            r._connection.execute('DROP TRIGGER fail_update')
            assert (await command(s,'start','start',player_name='Player17')).ok
        finally: await dispose(s,r)
    asyncio.run(run())


def test_timeout_and_manual_end_race_share_serial_path(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17',duration=1)
            await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
            timeout=t.callback; c.advance(1)
            await asyncio.gather(timeout(),command(s,'end','manual-end'))
            assert s.snapshot().version==3 and len(r.load().state.history)==1
            assert r.load().state.budgets['coach01']==800
        finally: await dispose(s,r)
    asyncio.run(run())


def test_no_op_time_display_does_not_increment_version(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        try:
            await command(s,'start','start',player_name='Player17')
            await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
            c.advance(2)
            result=await command(s,'submit_bid','same',coach_id='coach01',amount=200)
            assert result.version==2 and result.payload['changed'] is False
            assert r.load().state.time_left==88
        finally: await dispose(s,r)
    asyncio.run(run())


def test_closed_service_returns_error(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        await s.close()
        assert (await command(s,'start','start',player_name='Player17')).error_code=='SERVICE_CLOSED'
        assert not r.load().processed
        r.close()
    asyncio.run(run())
