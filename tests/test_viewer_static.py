import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest
from final_project.server.app import create_app
from .transport_support import config_and_auth

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('path,content_type',[
    ('/final-project/viewer.html','text/html'),('/final-project/viewer-transparent.html','text/html'),
    ('/final-project/viewer-colored.html','text/html'),('/final-project/results.html','text/html'),
    ('/final-project/viewer.js','javascript'),('/final-project/results.js','javascript'),
    ('/final-project/viewer.css','text/css'),('/vendor/socket.io.min.js','javascript'),
    ('/final-project/fallback-avatar.svg','image/svg+xml'),('/assets/coaches/qoq.jpg','image/jpeg'),
    ('/assets/frames/frame-lines.png','image/png')])
def test_asgi_serves_isolated_public_files_without_database(tmp_path,path,content_type):
    async def run():
        config,auth=config_and_auth(tmp_path)
        app=create_app(config,auth)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as http:
            response=await http.get(path)
            assert response.status_code==200 and content_type in response.headers['content-type']
            assert response.content
        assert not config.path(config.sqlite_file).exists()
    asyncio.run(run())


@pytest.mark.parametrize('path',[
    '/viewer.html','/admin.html','/coach.html','/auction-overlay-redesign.html',
    '/data/state.json','/data/coach.csv','/server.js','/package.json','/.env',
    '/assets/%2e%2e/%2e%2e/server.js','/final-project/%2e%2e/%2e%2e/.env',
    '/vendor/%2e%2e/%2e%2e/data/coach.csv','/socket.io/socket.io.js'])
def test_static_never_mounts_repository_or_legacy(tmp_path,path):
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(config,auth)),base_url='http://test') as http:
            assert (await http.get(path)).status_code in (400,404)
    asyncio.run(run())


def test_viewer_pages_local_dependencies_and_transparent_mode():
    for name,mode in [('viewer.html','normal'),('viewer-transparent.html','transparent'),('viewer-colored.html','colored')]:
        html=(ROOT/'public/final-project'/name).read_text(encoding='utf-8')
        assert f'body class="{mode}"' in html
        assert '/vendor/socket.io.min.js' in html and '/final-project/viewer.js' in html
        assert '/socket.io/socket.io.js' not in html and 'https://' not in html
    css=(ROOT/'public/final-project/viewer.css').read_text()
    assert '.transparent, .transparent .viewer-stage, .transparent .feed-zone { background: transparent; }' in css
    js=(ROOT/'public/final-project/viewer.js').read_text(encoding='utf-8')
    assert '/final-project/fallback-avatar.svg' in js
    assert 'innerHTML' not in js and 'textContent' in js


def test_vendor_pinned_license_and_hash():
    vendor=ROOT/'public/vendor'
    js=(vendor/'socket.io.min.js').read_bytes()
    assert b'Socket.IO v4.8.1' in js and b'MIT License' in js[:200]
    assert hashlib.sha256(js).hexdigest()=='b0e735814f8dcfecd6cdb8a7ce95a297a7e1e5f2727a29e6f5901801d52fa0c5'
    assert 'MIT' in (vendor/'socket.io.LICENSE').read_text()
