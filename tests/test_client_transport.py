import asyncio
from queue import Empty
import socket
import threading

from final_project.client.transport import (ClientTransport, Credentials, ConnectionChanged,
    SnapshotReceived, CommandAckReceived, TransportError)
from final_project.client.coach_viewmodel import CoachViewModel
from .live_support import live, eventually
from .transport_support import config_and_auth


async def receive(t, kind, predicate=lambda event:True):
    # ACK and snapshot delivery order is deliberately unspecified. Preserve other
    # events rather than silently losing an ended snapshot while waiting for ACK.
    pending = getattr(t, '_test_pending_events', None)
    if pending is None:
        pending = t._test_pending_events = []
    for index, event in enumerate(pending):
        if isinstance(event, kind) and predicate(event):
            return pending.pop(index)
    async with asyncio.timeout(8):
        while True:
            try:
                event=t.events.get_nowait()
                if isinstance(event,kind) and predicate(event): return event
                pending.append(event)
            except Empty:
                await asyncio.sleep(0.005)


def test_threaded_transport_live_auth_bid_ack_and_reconnect(tmp_path):
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            admin,_=await r.join('admin')
            t=ClientTransport(retry_delay=0.05,ack_timeout=2)
            try:
                t.connect(Credentials(r.url,'coach','coach01',auth.coach_tokens['coach01']))
                await receive(t,ConnectionChanged,lambda e:e.state=='connected')
                await r.command(admin,'start_auction','start',playerName='Player17',duration=90)
                frame=await receive(t,SnapshotReceived,lambda e:e.snapshot['status']=='running')
                assert frame.snapshot['coach']['id']=='coach01'
                request=t.send_command('submit_bid',round_id=frame.snapshot['round_id'],amount=250)
                assert len(request)==32
                ack=await receive(t,CommandAckReceived)
                assert ack.ack['ok'] and ack.ack['request_id']==request
                own=await receive(t,SnapshotReceived,lambda e:e.snapshot['myBid']==250)
                assert 'allBids' not in own.snapshot
                # Actual server disconnect; worker creates a new socket and reauthenticates.
                sid=next(iter(r.app.sio.manager.get_participants('/','coach:coach01')))[0]
                await r.app.sio.disconnect(sid)
                await receive(t,ConnectionChanged,lambda e:e.state=='reconnecting')
                rejoined=await receive(t,SnapshotReceived,lambda e:e.snapshot['myBid']==250)
                await receive(t,ConnectionChanged,lambda e:e.state=='connected')
                assert rejoined.snapshot['version']==r.app.runtime.service.snapshot().version
                assert r.app.runtime.service.snapshot().state.bids['coach01']==250
                # ACK ordering is handled by the same model the GUI consumes.
                m=CoachViewModel(now=lambda:1000)
                m.handle(SnapshotReceived({**own.snapshot,'version':12}))
                m.handle(CommandAckReceived({**ack.ack,'version':11}))
                assert m.latest_version==12 and m.snapshot['myBid']==250
            finally:
                t.disconnect()
                assert await asyncio.to_thread(t.join,5)
            assert not t._ready.is_set()
    asyncio.run(asyncio.wait_for(run(),25))


def test_auth_failure_shuts_worker_without_exposing_token(tmp_path):
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            t=ClientTransport(ack_timeout=2)
            creds=Credentials(r.url,'coach','coach01','synthetic-wrong-token')
            assert creds.token not in repr(creds)
            try:
                t.connect(creds)
                error=await receive(t,TransportError)
                assert error.code=='AUTH_FAILED' and creds.token not in repr(error)
                assert await asyncio.to_thread(t.join,5)
            finally:
                t.disconnect()
                assert await asyncio.to_thread(t.join,5)
    asyncio.run(run())


def test_unavailable_server_and_offline_send_cleanup():
    async def run():
        sock=socket.socket()
        sock.bind(('127.0.0.1',0))  # Reserved ephemeral port with no listener.
        t=ClientTransport(retry_delay=0.05,ack_timeout=0.2)
        try:
            assert t.send_command('submit_bid',round_id='old',amount=100) is None
            assert (await receive(t,TransportError)).code=='OFFLINE'
            t.connect(Credentials(f'http://127.0.0.1:{sock.getsockname()[1]}','viewer'))
            assert (await receive(t,TransportError)).code=='CONNECTION_FAILED'
        finally:
            t.disconnect()
            assert await asyncio.to_thread(t.join,5)
            sock.close()
    asyncio.run(run())


def test_queue_multiple_producers():
    t=ClientTransport()
    def producer(i):
        for n in range(100): t.events.put(ConnectionChanged(f'{i}-{n}'))
    threads=[threading.Thread(target=producer,args=(i,)) for i in range(4)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    events=[t.events.get_nowait().state for _ in range(400)]
    assert len(set(events))==400 and t.events.empty()


def test_ack_timeout_does_not_automatically_resend(tmp_path):
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            admin,_=await r.join('admin')
            t=ClientTransport(ack_timeout=2)
            try:
                t.connect(Credentials(r.url,'coach','coach01',auth.coach_tokens['coach01']))
                await receive(t,ConnectionChanged,lambda e:e.state=='connected')
                await r.command(admin,'start_auction','start',playerName='Player17',duration=90)
                frame=await receive(t,SnapshotReceived,lambda e:e.snapshot['status']=='running')
                original=r.app.sio.handlers['/']['submit_bid']
                calls=[]
                async def delayed(sid,data):
                    calls.append(data['request_id'])
                    result=await original(sid,data)
                    await asyncio.sleep(0.4)
                    return result
                r.app.sio.handlers['/']['submit_bid']=delayed
                t.ack_timeout=0.1
                request=t.send_command('submit_bid',round_id=frame.snapshot['round_id'],amount=275)
                assert (await receive(t,TransportError)).code=='UNCONFIRMED'
                await asyncio.sleep(0.5)
                assert calls==[request]
                assert r.app.runtime.service.snapshot().state.bids['coach01']==275
            finally:
                t.disconnect()
                assert await asyncio.to_thread(t.join,5)
    asyncio.run(run())
