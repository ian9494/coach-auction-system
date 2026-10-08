import asyncio
from final_project.server.timer import Clock, DeadlineTimer
from .service_support import initial
from final_project.config import ProjectConfig
from final_project.storage.repository import SQLiteRepository
from final_project.server.service import AuctionService
from final_project.server.commands import Command, CommandKind


def test_real_asyncio_timer_retry_and_cancel():
    async def run():
        clock=Clock()
        timer=DeadlineTimer(clock)
        fired=asyncio.Event(); calls=[]
        async def callback():
            calls.append(1)
            if len(calls)==2:
                fired.set()
                return True
            return False
        timer.schedule(clock.monotonic(),callback)
        await asyncio.wait_for(fired.wait(),1)
        await timer.close()
        assert len(calls)==2
        timer.schedule(clock.monotonic()+100,callback)
        await timer.close()
        assert len(calls)==2
    asyncio.run(run())


def test_real_timer_runs_through_service_without_port(tmp_path):
    async def run():
        class ControlledClock:
            wall=1000.0
            mono=100.0
        c=ControlledClock(); clock=Clock(lambda:c.wall,lambda:c.mono)
        repo=SQLiteRepository(ProjectConfig(project_root=tmp_path))
        service=await AuctionService.open(repo,initial(),clock=clock,rng=lambda:0)
        try:
            result=await service.execute(Command(CommandKind.START,'start',payload={'player_name':'Player17','duration':1}))
            c.wall+=1; c.mono+=1
            # Let the actual scheduled task observe the advanced clock.
            for _ in range(10):
                await asyncio.sleep(0)
                if service.snapshot().state.status=='ended': break
            assert service.snapshot().state.status=='ended'
            assert len(repo.load().state.history)==1
        finally:
            await service.close(); repo.close()
    asyncio.run(run())
