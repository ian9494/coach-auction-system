"""Run with a fresh wheel-installed venv, outside the repository import path."""
import asyncio
import hashlib
from pathlib import Path
import socket
import secrets
import sys
import tempfile

import aiohttp
import socketio
import uvicorn
import final_project
from final_project.config import load_launch_config
from final_project.demo import prepare_demo, demo_auth
from final_project.resources import resource_root
from final_project.server.app import create_app


async def run(root):
    prefix = Path(sys.prefix).resolve()
    assert Path(final_project.__file__).resolve().is_relative_to(prefix), 'Must use installed wheel'
    resources = resource_root()
    assert resources.is_relative_to(prefix), 'Must use installed assets'
    vendor = resources / 'public/vendor/socket.io.min.js'
    assert hashlib.sha256(vendor.read_bytes()).hexdigest() == 'b0e735814f8dcfecd6cdb8a7ce95a297a7e1e5f2727a29e6f5901801d52fa0c5'
    prepare_demo(root)
    config = load_launch_config(root / 'config.json', project_root=root, environ={})
    auth = demo_auth(root)
    app = create_app(config, auth, tick_interval=.05)
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False, timeout_graceful_shutdown=2))
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0)); sock.listen(128); sock.setblocking(False)
    url = f'http://127.0.0.1:{sock.getsockname()[1]}'
    task = asyncio.create_task(server.serve(sockets=[sock]))
    clients = []
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done(): await task; raise RuntimeError('Server startup failed')
                await asyncio.sleep(.01)
        async with aiohttp.ClientSession() as http:
            images = [next((resources / 'public/assets' / group).glob('*')) for group in ['coaches', 'players', 'frames']]
            paths = ['/health', '/final-project/viewer.html', '/final-project/viewer-transparent.html',
                     '/final-project/results.html', '/vendor/socket.io.min.js', '/final-project/fallback-avatar.svg']
            paths.extend('/' + image.relative_to(resources / 'public').as_posix() for image in images)
            for path in paths:
                async with http.get(url + path) as response:
                    assert response.status == 200, path
                    assert await response.read()
            for role in ['admin', 'coach', 'coach', 'viewer']:
                c = socketio.AsyncClient(reconnection=False)
                clients.append(c)
                await c.connect(url, transports=['websocket'])
                coach_id = 'coach01' if len(clients) == 2 else 'coach02'
                payload = {} if role == 'viewer' else {'token': auth.admin_token} if role == 'admin' else {
                    'coachId': coach_id, 'token': auth.coach_tokens[coach_id]}
                if role == 'coach' and len(clients) == 2:
                    password = secrets.token_urlsafe(24)
                    registered = await c.call('register_coach', {'coachId':coach_id,
                        'invite':auth.coach_tokens[coach_id], 'username':'wheel_coach', 'password':password})
                    assert registered['ok']
                    payload = {'username':'wheel_coach', 'password':password}
                assert (await c.call('join_' + role, payload))['ok']
            start = await clients[0].call('start_auction', {'request_id':'start', 'playerName':'Player17', 'duration':10})
            assert start['ok']
            round_id = start['round_id']
            for c, amount in zip(clients[1:3], [210, 320]):
                assert (await c.call('submit_bid', {'request_id':'bid', 'round_id':round_id, 'amount':amount}))['ok']
            async with http.get(url + '/api/state/viewer') as response:
                public = await response.json()
                assert public['winner'] is None and 'bids' not in public and 'allBids' not in public
            assert (await clients[0].call('end_auction', {'request_id':'end', 'round_id':round_id}))['ok']
            async with http.get(url + '/api/results') as response:
                assert await response.json() == [{'playerName':'Player17', 'coachId':'coach02', 'amount':320}]
            assert config.path(config.sqlite_file).is_file()
    finally:
        for c in clients:
            if c.connected: await c.disconnect()
            await c.shutdown()
        server.should_exit = True
        try: await asyncio.wait_for(task, 10)
        finally: sock.close()
    assert app.runtime.service is None
    print('PASS: wheel imports, installed assets/vendor hash, ephemeral server, registration/login, auth, sealed bids, settlement, HTTP results and isolated SQLite')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='final-project-wheel-') as temporary:
        asyncio.run(asyncio.wait_for(run(Path(temporary) / 'session'), 30))
