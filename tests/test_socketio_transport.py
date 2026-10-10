import asyncio
import pytest
from .transport_support import running_app,client,Client,request
from .test_projections import keys,FORBIDDEN

ACK_KEYS={'ok','error_code','message','version','round_id','request_id','payload'}


def test_events_ack_reconnect_and_authority(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            coach,_=await client(app,'c','coach',auth)
            viewer,_=await client(app,'v','viewer',auth)
            start=await admin.call('start_auction',{'request_id':'start','playerName':'Player17','duration':90})
            assert start['ok'] and set(start)==ACK_KEYS and start['request_id']=='start' and start['round_id']
            bid_data=request(app,'bid',amount=213)
            bid=await coach.call('submit_bid',bid_data)
            assert bid['ok'] and bid['version']==2 and bid['round_id']==start['round_id']
            assert await coach.call('submit_bid',bid_data)==bid
            modified=await coach.call('submit_bid',request(app,'modified',amount=250))
            assert modified['ok'] and modified['version']==3
            assert (await coach.call('submit_bid',{**request(app,'fake',amount=300),'coachId':'coach02'}))['error_code']=='INVALID_PAYLOAD'
            assert app.runtime.service.snapshot().state.bids['coach01']==250
            assert app.runtime.service.snapshot().state.bids['coach02']==0
            stale=await coach.call('submit_bid',{'request_id':'stale','round_id':'old','amount':300})
            assert stale['error_code']=='STALE_ROUND' and set(stale)==ACK_KEYS
            assert (await admin.call('pause_auction',request(app,'pause')))['ok']
            assert (await coach.call('submit_bid',request(app,'paused',amount=300)))['error_code']=='INVALID_STATE'
            assert (await admin.call('resume_auction',request(app,'resume')))['ok']
            assert (await coach.call('submit_bid',request(app,'after-resume',amount=300)))['ok']
            await coach.disconnect()
            reconnect,joined=await client(app,'new-sid','coach',auth)
            latest=joined['payload']['snapshot']
            assert latest['myBid']==300 and latest['round_id']==start['round_id']
            assert latest['version']==app.runtime.service.snapshot().version
            assert await reconnect.call('submit_bid',bid_data)==bid
            await viewer.disconnect()
            viewer,joined=await client(app,'new-viewer','viewer',auth)
            assert not keys(joined['payload']['snapshot'])&FORBIDDEN
            end=await admin.call('end_auction',request(app,'end'))
            assert end['ok'] and app.runtime.service.snapshot().state.winner=='coach01'
            assert (await admin.call('undo_last_award',request(app,'undo')))['ok']
            assert not app.runtime.service.snapshot().state.history
            for event in ('reset_auction',):
                assert (await admin.call(event,request(app,'unsupported')))['error_code']=='NOT_IMPLEMENTED'
                assert (await viewer.call(event,request(app,'forbidden')))['error_code']=='FORBIDDEN'
            assert (await admin.call('add_all_budgets',request(app,'missing-budget')))['error_code']=='INVALID_PAYLOAD'
    asyncio.run(run())


@pytest.mark.parametrize('data',[
    None,[],123,True,{'amount':100},
    {'request_id':'x','amount':100},
    {'request_id':'x','round_id':'r','amount':True},
    {'request_id':'x','round_id':'r','amount':1.0},
    {'request_id':'x','round_id':'r','amount':'100'},
    {'request_id':'x','round_id':'r','amount':float('nan')},
    {'request_id':'x','round_id':'r'},
    {'request_id':'timeout:bad','round_id':'r','amount':100},
])
def test_bad_payload_does_not_crash(tmp_path,data):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            coach,_=await client(app,'c','coach',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
            result=await coach.call('submit_bid',data)
            assert result['error_code']=='INVALID_PAYLOAD' and set(result)==ACK_KEYS
            assert app.runtime.service.snapshot().version==1
            assert (await coach.call('submit_bid',request(app,'good',amount=200)))['ok']
    asyncio.run(run())


def test_unknown_event_and_unexpected_exception_sanitized(tmp_path,caplog):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            assert (await admin.call('unknown_event',{'request_id':'unknown'}))['error_code']=='UNKNOWN_EVENT'
            original=app.runtime.service.execute
            async def broken(cmd): raise RuntimeError('private-path '+auth.admin_token)
            app.runtime.service.execute=broken
            error=await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
            assert error['error_code']=='INTERNAL_ERROR'
            assert auth.admin_token not in str(error)+caplog.text and 'private-path' not in str(error)+caplog.text
            app.runtime.service.execute=original
            assert (await admin.call('start_auction',{'request_id':'start','playerName':'Player17'}))['ok']
    asyncio.run(run())


def test_request_namespace_and_eight_concurrent_coaches(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            coaches=[(await client(app,f'c{i}','coach',auth,f'coach{i:02d}'))[0] for i in range(1,9)]
            await admin.call('start_auction',{'request_id':'same-id','playerName':'Player17'})
            results=await asyncio.gather(*(coach.call('submit_bid',request(app,'same-id',amount=100+i*10)) for i,coach in enumerate(coaches,1)))
            assert all(r['ok'] for r in results)
            modified=await asyncio.gather(*(coach.call('submit_bid',request(app,'next',amount=200+i*10)) for i,coach in enumerate(coaches,1)))
            assert all(r['ok'] for r in modified) and app.runtime.service.snapshot().version==17
            await admin.call('end_auction',request(app,'end'))
            state=app.runtime.service.snapshot().state
            assert state.winner=='coach08' and state.winning_amount==280 and state.budgets['coach08']==720
    asyncio.run(run())


def test_room_projections_timeout_broadcast_and_tick_no_db_writes(tmp_path):
    async def run():
        async with running_app(tmp_path,tick_interval=0.01) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            coach,_=await client(app,'c','coach',auth)
            viewer,_=await client(app,'v','viewer',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player17','duration':10})
            await coach.call('submit_bid',request(app,'bid',amount=213))
            await asyncio.sleep(0.02)
            before=app.runtime.service._repository.load()
            c.advance(2)
            await asyncio.sleep(0.03)
            assert app.runtime.service._repository.load()==before
            emissions=app.test_io.emissions
            assert any(sid=='v' and data['time_left']==8 for sid,event,data in emissions)
            for sid,event,data in emissions:
                if sid=='v': assert event=='viewer_state' and not keys(data)&FORBIDDEN
                if sid=='c': assert event=='coach_state' and 'allBids' not in data
                if sid=='a': assert event=='admin_state' and 'allBids' in data
            c.advance(8)
            assert await t.callback() is True
            await asyncio.sleep(0.02)
            assert any(sid=='v' and data['status']=='ended' and data['winning_amount']==213 for sid,event,data in emissions)
            assert app.runtime.service._repository.load().state.status=='ended'
    asyncio.run(run())


def test_persistence_failure_ack_and_no_candidate_broadcast(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
            await asyncio.sleep(0)
            before=len(app.test_io.emissions)
            repo=app.runtime.service._repository
            repo._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT,'failure'); END")
            result=await admin.call('pause_auction',request(app,'pause'))
            assert result['error_code']=='PERSISTENCE_ERROR'
            await asyncio.sleep(0)
            assert len(app.test_io.emissions)==before and app.runtime.service.snapshot().state.status=='running'
    asyncio.run(run())


def test_restarted_app_keeps_principal_namespaced_ack(tmp_path):
    async def run():
        from final_project.config import ProjectConfig
        from final_project.server.app import create_app
        from .transport_support import FakeIO
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            coach,_=await client(app,'c','coach',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
            data=request(app,'bid',amount=213)
            ack=await coach.call('submit_bid',data)
        app=create_app(ProjectConfig(project_root=tmp_path),auth,clock=c.clock(),timer=t,rng=lambda:0)
        io=FakeIO(); app.test_io=io
        for name in ('save_session','get_session','enter_room','emit'): setattr(app.sio,name,getattr(io,name))
        async with app.http.router.lifespan_context(app.http):
            coach,joined=await client(app,'new-sid','coach',auth)
            assert joined['payload']['snapshot']['myBid']==213
            assert await coach.call('submit_bid',data)==ack
            assert app.runtime.service.snapshot().version==2
    asyncio.run(run())


def test_broadcast_drops_old_version_and_same_version_old_countdown(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'a','admin',auth)
            viewer,_=await client(app,'v','viewer',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
            old=app.runtime.service.snapshot()
            c.advance(2)
            await app.transport.broadcast(app.runtime.service.snapshot())
            before=len(app.test_io.emissions)
            await app.transport.broadcast(old)
            assert len(app.test_io.emissions)==before
            await admin.call('pause_auction',request(app,'pause'))
            await app.transport.broadcast(app.runtime.service.snapshot())
            before=len(app.test_io.emissions)
            await app.transport.broadcast(old)
            assert len(app.test_io.emissions)==before
    asyncio.run(run())
