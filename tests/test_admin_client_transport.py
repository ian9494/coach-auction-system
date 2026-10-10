import asyncio
import socket
import threading
import pytest
from final_project.client.transport import ClientTransport, Credentials, ConnectionChanged, SnapshotReceived, CommandAckReceived, HttpDataReceived, TransportError
from final_project.client.admin_viewmodel import AdminViewModel
from .live_support import live
from .transport_support import config_and_auth
from .test_client_transport import receive


def test_admin_thread_transport_http_commands_minimum_reconnect_export(tmp_path):
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            coach,_=await r.join('coach')
            t=ClientTransport(retry_delay=0.05,ack_timeout=2)
            try:
                t.connect(Credentials(r.url,'admin',token=auth.admin_token))
                await receive(t,ConnectionChanged,lambda e:e.state=='connected')
                assert t.fetch('members')
                members=await receive(t,HttpDataReceived)
                assert members.resource=='members' and len(members.data)==40
                start=t.send_command('start_auction',playerName='Player01',duration=5)
                assert (await receive(t,CommandAckReceived)).ack['request_id']==start
                running=await receive(t,SnapshotReceived,lambda e:e.snapshot['status']=='running')
                rid=running.snapshot['round_id']
                await r.command(coach,'submit_bid','bid',amount=200)
                bid=await receive(t,SnapshotReceived,lambda e:e.snapshot['allBids']['coach01']==200)
                assert bid.snapshot['allBids']['coach02']==0
                t.send_command('set_minimum_bid',round_id=rid,amount=250)
                assert (await receive(t,CommandAckReceived)).ack['ok']
                pruned=await receive(t,SnapshotReceived,lambda e:e.snapshot['minimum_bid']==250)
                assert pruned.snapshot['allBids']['coach01'] is None
                t.send_command('add_all_budgets',round_id=rid,amount=100)
                assert (await receive(t,CommandAckReceived)).ack['ok']
                raised=await receive(t,SnapshotReceived,lambda e:e.snapshot['budgets']['coach01']==1100)
                await r.command(coach,'submit_bid','new',amount=300)
                sid=next(iter(r.app.sio.manager.get_participants('/','admin')))[0]
                await r.app.sio.disconnect(sid)
                await receive(t,ConnectionChanged,lambda e:e.state=='reconnecting')
                rejoined=await receive(t,SnapshotReceived,lambda e:e.snapshot['allBids']['coach01']==300)
                await receive(t,ConnectionChanged,lambda e:e.state=='connected')
                m=AdminViewModel(now=lambda:1000)
                m.handle(rejoined); m.handle(ConnectionChanged('connected'))
                m.handle(CommandAckReceived({'ok':True,'version':1}))
                assert m.latest_version==rejoined.snapshot['version'] and m.snapshot['allBids']['coach01']==300
                t.send_command('end_auction',round_id=rid)
                assert (await receive(t,CommandAckReceived)).ack['ok']
                ended=await receive(t,SnapshotReceived,lambda e:e.snapshot['status']=='ended')
                assert ended.snapshot['winner']=='coach01'
                assert t.fetch('members')
                assert 'Player01' not in (await receive(t,HttpDataReceived)).data
                assert t.fetch('results')
                assert (await receive(t,HttpDataReceived)).data==[{'playerName':'Player01','coachId':'coach01','amount':300}]
            finally:
                t.disconnect(); assert await asyncio.to_thread(t.join,5)
    asyncio.run(asyncio.wait_for(run(),25))


def test_admin_auth_failure(tmp_path):
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            t=ClientTransport(ack_timeout=2)
            try:
                t.connect(Credentials(r.url,'admin',token='synthetic-wrong-token'))
                assert (await receive(t,TransportError)).code=='AUTH_FAILED'
            finally:
                t.disconnect(); assert await asyncio.to_thread(t.join,5)
    asyncio.run(run())


def test_http_resource_allowlist_and_offline():
    t=ClientTransport()
    with pytest.raises(ValueError): t.fetch('../state.json')
    assert not t.fetch('members')
    assert t.events.get_nowait().code=='OFFLINE'


def test_admin_server_unavailable():
    async def run():
        sock=socket.socket()
        sock.bind(('127.0.0.1',0))
        t=ClientTransport(retry_delay=0.05,ack_timeout=0.2)
        try:
            t.connect(Credentials(f'http://127.0.0.1:{sock.getsockname()[1]}','admin',token='synthetic-admin-test-token'))
            assert (await receive(t,TransportError)).code=='CONNECTION_FAILED'
        finally:
            t.disconnect(); assert await asyncio.to_thread(t.join,5)
            sock.close()
    asyncio.run(run())


def test_auth_failure_stop_during_cleanup_is_not_cancelled(monkeypatch):
    """Force the exact auth-error/UI-disconnect race without relying on timing."""
    closing=threading.Event()
    release=threading.Event()
    clients=[]
    class Client:
        connected=False
        def __init__(self,**kwargs):
            self.session=kwargs['http_session']
            clients.append(self)
        def on(self,event): return lambda callback:callback
        async def connect(self,*args,**kwargs): self.connected=True
        async def call(self,*args,**kwargs): return {'ok':False}
        async def disconnect(self):
            closing.set()
            while not release.is_set(): await asyncio.sleep(0.005)
            self.connected=False
        async def shutdown(self): pass
    monkeypatch.setattr('final_project.client.transport.socketio.AsyncClient',Client)
    async def run():
        t=ClientTransport()
        try:
            t.connect(Credentials('http://127.0.0.1','admin',token='synthetic-admin-test-token'))
            assert (await receive(t,TransportError)).code=='AUTH_FAILED'
            assert await asyncio.to_thread(closing.wait,2)
            t.disconnect(); t.disconnect()
            await asyncio.sleep(0.02)
        finally:
            release.set()
            assert await asyncio.to_thread(t.join,5)
        assert clients[0].session.closed
    asyncio.run(run())
