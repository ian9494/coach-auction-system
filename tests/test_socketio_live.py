"""One real localhost:0 ASGI integration, with a temp DB and synthetic tokens."""
import asyncio
import socket

import socketio
import uvicorn
from final_project.server.app import create_app
from .transport_support import config_and_auth
from .test_projections import FORBIDDEN,keys


def test_real_socketio_asgi_clients_reconnect_and_http(tmp_path):
    async def run():
        import httpx
        config,auth=config_and_auth(tmp_path)
        app=create_app(config,auth,tick_interval=0.05)
        # Polling disconnect may await its outstanding GET until heartbeat expiry.
        # Short test-only window keeps cleanup bounded; application defaults stay unchanged.
        app.sio.eio.ping_interval=1
        app.sio.eio.ping_timeout=1
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_level='warning',access_log=False,
                                            timeout_graceful_shutdown=2))
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.bind(('127.0.0.1',0)); sock.listen(128); sock.setblocking(False)
        url=f'http://127.0.0.1:{sock.getsockname()[1]}'
        task=asyncio.create_task(server.serve(sockets=[sock]))
        clients=[]
        async def connection(transports=None):
            c=socketio.AsyncClient(reconnection=False,logger=False,engineio_logger=False)
            clients.append(c)
            await c.connect(url,transports=transports or ['websocket'],wait_timeout=5)
            return c
        try:
            for _ in range(500):
                if server.started: break
                if task.done(): await task
                await asyncio.sleep(0.01)
            assert server.started
            admin=await connection()
            assert (await admin.call('join_admin',{'token':'wrong'},timeout=5))['error_code']=='UNAUTHORIZED'
            assert (await admin.call('join_admin',{'token':auth.admin_token},timeout=5))['ok']
            viewer=await connection(); frames=[]
            viewer.on('viewer_state',lambda data:frames.append(data))
            assert (await viewer.call('join_viewer',{},timeout=5))['ok']
            polling=await connection(['polling'])
            assert (await polling.call('join_viewer',{},timeout=5))['ok']
            await polling.disconnect()
            coaches=[]
            for i in range(1,9):
                c=await connection(); cid=f'coach{i:02d}'
                join=await c.call('join_coach',{'coachId':cid,'token':auth.coach_tokens[cid]},timeout=5)
                assert join['ok'] and join['payload']['snapshot']['coach']['id']==cid
                coaches.append(c)
            start=await admin.call('start_auction',{'request_id':'start','playerName':'Player17','duration':90},timeout=5)
            assert start['ok']; round_id=start['round_id']
            bids=await asyncio.gather(*(c.call('submit_bid',{'request_id':'bid','round_id':round_id,'amount':200+i*10},timeout=5)
                                       for i,c in enumerate(coaches,1)))
            assert all(b['ok'] for b in bids)
            assert (await viewer.call('end_auction',{'request_id':'forbidden','round_id':round_id},timeout=5))['error_code']=='FORBIDDEN'
            assert (await coaches[0].call('submit_bid',{'request_id':'fake','round_id':round_id,'amount':300,'coachId':'coach08'},timeout=5))['error_code']=='INVALID_PAYLOAD'
            for value in (True, 1.0, '100'):
                assert (await coaches[0].call('submit_bid',{'request_id':'bad','round_id':round_id,'amount':value},timeout=5))['error_code']=='INVALID_PAYLOAD'
            assert (await coaches[0].call('join_admin',{'token':auth.admin_token},timeout=5))['error_code']=='FORBIDDEN'
            await coaches[0].disconnect()
            reconnect=await connection()
            joined=await reconnect.call('join_coach',{'coachId':'coach01','token':auth.coach_tokens['coach01']},timeout=5)
            assert joined['payload']['snapshot']['myBid']==210
            duplicate=await reconnect.call('submit_bid',{'request_id':'bid','round_id':round_id,'amount':210},timeout=5)
            assert duplicate==bids[0]
            assert (await admin.call('unknown_event',{'request_id':'unknown'},timeout=5))['error_code']=='UNKNOWN_EVENT'
            async with httpx.AsyncClient(base_url=url) as http:
                assert (await http.get('/health')).json()['ready'] is True
                view=(await http.get('/api/state/viewer')).json()
                assert view['version']==9 and not keys(view)&FORBIDDEN
                assert len((await http.get('/api/coaches')).json())==8
                assert (await admin.call('end_auction',{'request_id':'end','round_id':round_id},timeout=5))['ok']
                assert (await http.get('/api/results')).json()==[{'playerName':'Player17','coachId':'coach08','amount':280}]
            await asyncio.sleep(0.1)
            assert frames and any(f['status']=='ended' and f['winner']=='coach08' for f in frames)
            assert all(not keys(f)&FORBIDDEN for f in frames)
        finally:
            for c in clients:
                if c.connected: await c.disconnect()
                await c.shutdown()
            server.should_exit=True
            try: await asyncio.wait_for(task,5)
            finally: sock.close()
        assert app.runtime.ready is False and app.runtime.service is None
    asyncio.run(asyncio.wait_for(run(),30))
