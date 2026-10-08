import asyncio
import pytest
from final_project.config import ProjectConfig
from final_project.domain.models import AuctionStatus, Player
from final_project.server.service import AuctionService
from final_project.storage.repository import SQLiteRepository, RepositoryError
from .service_support import create, command, dispose, initial, FakeTimer


async def reopen(tmp_path, clock, *, rng=lambda:0.0):
    repo=SQLiteRepository(ProjectConfig(project_root=tmp_path))
    timer=FakeTimer()
    service=await AuctionService.open(repo,initial(),clock=clock.clock(),timer=timer,rng=rng)
    return service,repo,timer


def test_idle_restart(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        before=s.snapshot()
        await dispose(s,r)
        s,r,t=await reopen(tmp_path,c)
        try: assert s.snapshot()==before and t.deadline is None
        finally: await dispose(s,r)
    asyncio.run(run())


def test_paused_restart_remaining_undo_persists(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        await command(s,'start','start',player_name='Player17',duration=10)
        await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
        c.advance(2.5)
        await command(s,'pause','pause')
        await dispose(s,r); c.advance(100)
        s,r,t=await reopen(tmp_path,c)
        assert s.snapshot().state.status==AuctionStatus.PAUSED and s.snapshot().remaining==7.5
        assert t.deadline is None
        await command(s,'end','end')
        await dispose(s,r)
        s,r,t=await reopen(tmp_path,c)
        try:
            assert (await command(s,'undo','undo')).ok
            assert not r.load().state.history and r.load().state.budgets['coach01']==1000
        finally: await dispose(s,r)
    asyncio.run(run())


def test_running_restart_before_deadline(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        await command(s,'start','start',player_name='Player17',duration=10)
        await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
        await dispose(s,r); c.advance(4)
        # monotonic origin changes across processes; UTC stays durable.
        c.mono=0
        s,r,t=await reopen(tmp_path,c)
        try:
            assert s.snapshot().state.status==AuctionStatus.RUNNING
            assert s.snapshot().remaining==6 and t.deadline==6 and s.snapshot().version==2
            c.advance(6)
            assert await t.callback() is True
            assert r.load().state.winner=='coach01' and r.load().state.budgets['coach01']==800
        finally: await dispose(s,r)
    asyncio.run(run())


def test_expired_recovery_once_and_dedup_after_restart(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        start=await command(s,'start','start',player_name='Player17',duration=5)
        bid=await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
        await dispose(s,r); c.advance(5)
        s,r,t=await reopen(tmp_path,c)
        assert s.snapshot().version==3 and r.load().state.budgets['coach01']==800
        assert r.load().settled_round_id==start.round_id and len(r.load().state.history)==1
        assert await command(s,'submit_bid','bid',coach_id='coach01',amount=200)==bid
        await dispose(s,r)
        def forbidden(): raise AssertionError('Settled restart cannot redraw')
        s,r,t=await reopen(tmp_path,c,rng=forbidden)
        try:
            assert s.snapshot().version==3 and len(r.load().state.history)==1
            assert r._connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert (await command(s,'end','another-end')).ok
            undo=await command(s,'undo','undo')
            await dispose(s,r)
            s,r,t=await reopen(tmp_path,c)
            assert await command(s,'undo','undo')==undo
            assert r.load().state.budgets['coach01']==1000 and r.load().state.history==[]
        finally: await dispose(s,r)
    asyncio.run(run())


def test_expired_recovery_commit_failure_is_not_silent(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        await command(s,'start','start',player_name='Player17',duration=1)
        r._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT,'failure'); END")
        await dispose(s,r); c.advance(2)
        repo=SQLiteRepository(ProjectConfig(project_root=tmp_path))
        try:
            with pytest.raises(RepositoryError,match='recovery'):
                await AuctionService.open(repo,initial(),clock=c.clock(),timer=FakeTimer())
            assert repo.load().state.status=='running' and repo.load().state.history==[]
            repo._connection.execute('DROP TRIGGER fail_update')
            s=await AuctionService.open(repo,initial(),clock=c.clock(),timer=FakeTimer())
            assert len(repo.load().state.history)==1
            await s.close()
        finally: repo.close()
    asyncio.run(run())


def test_roster_mismatch_rejected(tmp_path):
    async def run():
        s,r,c,t=await create(tmp_path)
        await dispose(s,r)
        repo=SQLiteRepository(ProjectConfig(project_root=tmp_path))
        wrong=initial(); wrong.roster+=(Player('New'),)
        try:
            with pytest.raises(RepositoryError,match='roster'):
                await AuctionService.open(repo,wrong,clock=c.clock(),timer=FakeTimer())
        finally: repo.close()
    asyncio.run(run())


def test_old_success_ack_stays_original_in_new_round(tmp_path):
    async def run():
        from final_project.server.commands import Command, CommandKind
        s,r,c,t=await create(tmp_path)
        first=await command(s,'start','start',player_name='Player17')
        bid=await command(s,'submit_bid','bid',coach_id='coach01',amount=200)
        await command(s,'end','end')
        second=await command(s,'start','second',player_name='Player18')
        await dispose(s,r)
        s,r,t=await reopen(tmp_path,c)
        try:
            old=await s.execute(Command(CommandKind.SUBMIT_BID,'bid',first.round_id,{'coach_id':'coach01','amount':200}))
            assert old==bid
            assert s.snapshot().round_id==second.round_id and s.snapshot().version==4
            assert s.snapshot().state.bids['coach01']!=200
        finally: await dispose(s,r)
    asyncio.run(run())
