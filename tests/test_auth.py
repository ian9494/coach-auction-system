import asyncio
import pytest
from final_project.server.auth import AuthConfig
from .transport_support import running_app,Client,client,request


def test_auth_env_and_repr():
    env={'FINAL_PROJECT_ADMIN_TOKEN':'local-only-admin-16','FINAL_PROJECT_COACH_TOKEN_COACH01':'local-only-coach-16'}
    config=AuthConfig.from_env(['coach01'],env)
    assert config.check('admin',env['FINAL_PROJECT_ADMIN_TOKEN'])
    assert config.check('coach',env['FINAL_PROJECT_COACH_TOKEN_COACH01'],'coach01')
    assert 'local-only' not in repr(config)
    assert not config.check('admin',True)
    assert not config.check('coach','wrong','coach01')


@pytest.mark.parametrize('admin,mapping',[
    ('',{'coach01':'enough-long-coach-token'}),
    ('REPLACE_WITH_PLACEHOLDER',{'coach01':'enough-long-coach-token'}),
    ('same-token-over16chars',{'coach01':'same-token-over16chars'}),
])
def test_missing_placeholder_duplicate_tokens_fail(admin,mapping):
    with pytest.raises(ValueError): AuthConfig(admin,mapping)


def test_wrong_tokens_fixed_roles_and_unjoined_mutation(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            anonymous=Client(app,'unjoined'); await anonymous.connect()
            assert (await anonymous.call('start_auction',{'request_id':'a','playerName':'Player17'}))['error_code']=='UNAUTHORIZED'
            assert (await anonymous.call('join_admin',{'token':'wrong'}))['error_code']=='UNAUTHORIZED'
            assert (await anonymous.call('join_coach',{'coachId':'coach01','token':'wrong'}))['error_code']=='UNAUTHORIZED'
            coach,join=await client(app,'coach','coach',auth)
            assert join['payload']['snapshot']['coach']['id']=='coach01'
            assert (await coach.call('join_coach',{'coachId':'coach02','token':auth.coach_tokens['coach02']}))['error_code']=='FORBIDDEN'
            assert (await coach.call('join_admin',{'token':auth.admin_token}))['error_code']=='FORBIDDEN'
            assert (await coach.call('join_viewer',{}))['error_code']=='FORBIDDEN'
            assert (await coach.call('start_auction',{'request_id':'s','playerName':'Player17'}))['error_code']=='FORBIDDEN'
            viewer,_=await client(app,'viewer','viewer',auth)
            assert (await viewer.call('join_admin',{'token':auth.admin_token}))['error_code']=='FORBIDDEN'
            assert (await viewer.call('submit_bid',{}))['error_code']=='FORBIDDEN'
            assert not app.runtime.service.snapshot().processed
    asyncio.run(run())


def test_concurrent_join_cannot_change_principal(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            socket=Client(app,'race'); await socket.connect()
            joins=await asyncio.gather(socket.call('join_coach',{'coachId':'coach01','token':auth.coach_tokens['coach01']}),
                socket.call('join_admin',{'token':auth.admin_token}))
            assert sum(j['ok'] for j in joins)==1
            assert sum(j['error_code']=='FORBIDDEN' for j in joins)==1
            assert sum('race' in s for s in app.test_io.rooms.values())==1
    asyncio.run(run())


def test_tokens_not_in_auth_errors_or_logs(tmp_path,caplog):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            socket=Client(app,'bad'); await socket.connect()
            result=await socket.call('join_admin',{'token':auth.coach_tokens['coach01']})
            assert result['error_code']=='UNAUTHORIZED'
            for secret in [auth.admin_token,*auth.coach_tokens.values()]:
                assert secret not in str(result) and secret not in caplog.text
    asyncio.run(run())


def test_auth_not_persisted_with_commands(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,c,t):
            admin,_=await client(app,'admin','admin',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player17'})
            document=app.runtime.service._repository._connection.execute('SELECT document FROM snapshot').fetchone()[0]
            for secret in [auth.admin_token,*auth.coach_tokens.values()]: assert secret not in document
            assert 'token' not in document
            session=app.test_io.sessions['admin']
            assert set(session)=={'role','coach_id','authenticated','joined'}
    asyncio.run(run())
