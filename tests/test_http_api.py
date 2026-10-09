import asyncio
import httpx
import pytest
from .transport_support import running_app,client,request,config_and_auth
from .test_projections import keys,FORBIDDEN
from final_project.server.app import create_app


def test_http_read_api_no_private_state_and_lifecycle(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as http:
                assert (await http.get('/health')).json()=={'status':'ok','ready':True}
                coaches=(await http.get('/api/coaches')).json()
                assert len(coaches)==8 and coaches[0]=={'id':'coach01','name':'Coach01'}
                assert len((await http.get('/api/members')).json())==40
                assert (await http.get('/api/results')).json()==[]
                admin,_=await client(app,'a','admin',auth)
                coach,_=await client(app,'c','coach',auth)
                await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
                await coach.call('submit_bid',request(app,'bid',amount=213))
                view=(await http.get('/api/state/viewer')).json()
                assert view['status']=='running' and not keys(view)&FORBIDDEN
                assert '213' not in str(view)
                await admin.call('end_auction',request(app,'end'))
                assert (await http.get('/api/results')).json()==[{'playerName':'Player17','coachId':'coach01','amount':213}]
                assert 'Player17' not in (await http.get('/api/members')).json()
                for path in ['/api/state/admin','/api/bids','/api/state','/admin.html','/data/state.json']:
                    assert (await http.get(path)).status_code==404
                assert (await http.post('/api/admin/reset-auctions')).status_code==404
        assert app.runtime.ready is False and app.runtime.service is None
    asyncio.run(run())


def test_not_ready_health_and_import_factory_no_database(tmp_path):
    async def run():
        config,auth=config_and_auth(tmp_path); app=create_app(config,auth)
        assert not config.path(config.sqlite_file).exists()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as http:
            assert (await http.get('/health')).json()['ready'] is False
            assert (await http.get('/api/results')).status_code==503
        assert await app.sio.handlers['/']['connect']('sid',{}) is False
    asyncio.run(run())


def test_http_errors_do_not_expose_paths_or_secrets(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            original=app.runtime.service.snapshot
            def broken(): raise RuntimeError('private-path '+auth.admin_token)
            app.runtime.service.snapshot=broken
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://test') as http:
                result=await http.get('/api/results')
                assert result.status_code==500 and result.json()=={'error_code':'INTERNAL_ERROR'}
                assert auth.admin_token not in result.text
            app.runtime.service.snapshot=original
    asyncio.run(run())


def test_missing_auth_config_startup_fails_before_database(tmp_path,monkeypatch):
    async def run():
        config,auth=config_and_auth(tmp_path)
        monkeypatch.delenv('FINAL_PROJECT_ADMIN_TOKEN',raising=False)
        app=create_app(config)
        with pytest.raises(ValueError,match='authentication'):
            async with app.http.router.lifespan_context(app.http): pass
        assert not config.path(config.sqlite_file).exists()
    asyncio.run(run())
