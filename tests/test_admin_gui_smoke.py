"""Optional hidden Tk smoke; headless platforms skip without blocking core tests."""
import asyncio
import pytest


def test_hidden_admin_gui_full_round_and_confirmation(tmp_path,monkeypatch):
    tk=pytest.importorskip('tkinter')
    try:
        root=tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable; presenter and transport tests remain headless')
    root.withdraw()
    from final_project.client.admin_app import AdminApp
    from .live_support import live
    from .transport_support import config_and_auth
    confirmations=[]
    answer=[True]
    def confirm(title,text,**kwargs):
        confirmations.append(text)
        return answer[0]
    gui=AdminApp(root,confirm=confirm)
    monkeypatch.setattr('final_project.client.admin_app.filedialog.asksaveasfilename',lambda **kwargs:str(tmp_path/'export.csv'))
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            async def wait(predicate):
                async with asyncio.timeout(8):
                    while not predicate():
                        root.update()
                        await asyncio.sleep(0.01)
            try:
                c1,_=await r.join('coach')
                c2,_=await r.join('coach','coach02')
                gui.url.set(r.url); gui.token.set(auth.admin_token); gui.connect()
                gui.model.now=lambda:r.clock.wall
                await wait(lambda:gui.model.connection=='connected' and len(gui.model.members)==40)
                gui.player.set('Player01'); gui.duration.set('5')
                gui.buttons['start_auction'].invoke()
                gui.command('start_auction')  # Pending guards a repeated click.
                await wait(lambda:gui.model.snapshot['status']=='running' and not gui.model.pending)
                await r.command(c1,'submit_bid','c1',amount=200)
                await r.command(c2,'submit_bid','c2',amount=250)
                await wait(lambda:gui.model.snapshot['allBids']['coach02']==250)
                assert gui.bids.item('coach01','values')[1]=='200'
                assert gui.bids.item('coach02','values')[1]=='250'
                gui.buttons['pause_auction'].invoke()
                await wait(lambda:gui.model.snapshot['status']=='paused' and not gui.model.pending)
                gui.buttons['resume_auction'].invoke()
                await wait(lambda:gui.model.snapshot['status']=='running' and not gui.model.pending)
                answer[0]=False
                gui.buttons['end_auction'].invoke()
                assert not gui.model.pending and r.app.runtime.service.snapshot().state.status=='running'
                answer[0]=True
                gui.buttons['end_auction'].invoke()
                await wait(lambda:gui.model.snapshot['status']=='ended' and not gui.model.pending)
                assert gui.model.snapshot['winner']=='coach02'
                assert gui.model.snapshot['teams']['coach02']==['Player01']
                assert 'Player01' not in gui.model.available_players
                gui.request_export()
                await wait(lambda:(tmp_path/'export.csv').exists())
                assert 'Player01,coach02,250' in (tmp_path/'export.csv').read_text(encoding='utf-8-sig')
                answer[0]=False
                gui.buttons['undo_last_award'].invoke()
                assert r.app.runtime.service.snapshot().state.budgets['coach02']==750
                answer[0]=True
                gui.buttons['undo_last_award'].invoke()
                await wait(lambda:not gui.model.snapshot['canUndo'] and not gui.model.pending)
                assert gui.model.snapshot['budgets']['coach02']==1000
                gui.budget.set('100')
                answer[0]=False; gui.buttons['add_all_budgets'].invoke()
                assert r.app.runtime.service.snapshot().state.budgets['coach01']==1000
                answer[0]=True; gui.buttons['add_all_budgets'].invoke()
                await wait(lambda:gui.model.snapshot['budgets']['coach01']==1100 and not gui.model.pending)
                await wait(lambda:'Player01' in gui.model.available_players)
                gui.player.set('Player01'); gui.buttons['start_auction'].invoke()
                await wait(lambda:gui.model.snapshot['status']=='running' and not gui.model.pending)
                assert len(confirmations)==6
            finally:
                gui.close()
                if gui.transport: assert await asyncio.to_thread(gui.transport.join,5)
                gui.poll()
    asyncio.run(asyncio.wait_for(run(),30))
