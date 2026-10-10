import asyncio
import pytest
from final_project.domain.transitions import add_all_budgets
from final_project.domain.errors import DomainError
from final_project.server.service import AuctionService
from final_project.server.commands import Command, CommandKind
from .service_support import initial, create, command, dispose, FakeTimer
from .transport_support import running_app, client, request


@pytest.mark.parametrize('amount',[0,-1,True,1.0,'100',2**53])
def test_domain_budget_rejects_without_mutation(amount):
    state=initial(); before=dict(state.budgets)
    with pytest.raises(DomainError): add_all_budgets(state,amount)
    assert state.budgets==before


@pytest.mark.parametrize('status',['idle','running','paused','ended'])
def test_budget_atomic_idempotent_recoverable_and_timer_stays(tmp_path,status):
    async def run():
        service,repo,clock,timer=await create(tmp_path)
        try:
            if status!='idle': await command(service,'start','start',player_name='Player01',duration=90)
            if status=='paused': await command(service,'pause','pause')
            if status=='ended': await command(service,'end','end')
            before=service.snapshot(); deadline=timer.deadline
            cmd=Command(CommandKind.ADD_ALL_BUDGETS,'budget',before.round_id,{'amount':100})
            ack=await service.execute(cmd)
            assert ack.ok and ack.version==before.version+1
            snap=service.snapshot()
            assert all(snap.state.budgets[cid]==value+100 for cid,value in before.state.budgets.items())
            assert snap.state.bids==before.state.bids and snap.state.history==before.state.history
            assert snap.state.status==before.state.status and timer.deadline==deadline
            assert await service.execute(cmd)==ack and service.snapshot()==snap
            assert (await service.execute(Command(cmd.kind,cmd.request_id,cmd.round_id,{'amount':101}))).error_code=='REQUEST_ID_CONFLICT'
            await service.close()
            service=await AuctionService.open(repo,initial(),clock=clock.clock(),timer=FakeTimer())
            assert await service.execute(cmd)==ack and service.snapshot()==snap
            repo._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT,'failure'); END")
            failed=await command(service,'add_all_budgets','fail',amount=100)
            assert failed.error_code=='PERSISTENCE_ERROR' and service.snapshot()==snap
            assert repo.load()==snap
        finally: await dispose(service,repo)
    asyncio.run(run())


def test_transport_budget_auth_stale_round_and_player_validation(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,clock,timer):
            admin,_=await client(app,'admin','admin',auth)
            coach,_=await client(app,'coach','coach',auth)
            assert (await coach.call('add_all_budgets',{'request_id':'forbidden','amount':100}))['error_code']=='FORBIDDEN'
            for amount in (0,-1,True,1.0,'100'):
                assert (await admin.call('add_all_budgets',{'request_id':'bad','amount':amount}))['error_code']=='INVALID_PAYLOAD'
            assert (await admin.call('add_all_budgets',{'request_id':'idle-add','amount':100}))['ok']
            assert (await admin.call('start_auction',{'request_id':'unknown','playerName':'UNKNOWN'}))['error_code']=='INVALID_COMMAND'
            await admin.call('start_auction',{'request_id':'start','playerName':'Player01'})
            assert (await admin.call('add_all_budgets',{'request_id':'stale','round_id':'old','amount':100}))['error_code']=='STALE_ROUND'
            await coach.call('submit_bid',request(app,'bid',amount=200))
            await admin.call('end_auction',request(app,'end'))
            assert (await admin.call('start_auction',{'request_id':'sold','playerName':'Player01'}))['error_code']=='INVALID_COMMAND'
            assert (await admin.call('undo_last_award',request(app,'undo')))['ok']
            assert (await admin.call('start_auction',{'request_id':'resale','playerName':'Player01'}))['ok']
    asyncio.run(run())
