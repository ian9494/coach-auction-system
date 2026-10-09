"""In-process registered-handler tests; real ASGI/network coverage is separate."""
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
import shutil
from uuid import uuid4

from final_project.config import ProjectConfig
from final_project.server.app import create_app
from final_project.server.auth import AuthConfig
from .fixture_adapter import ROOT
from .service_support import FakeClock, FakeTimer


def config_and_auth(tmp_path):
    shutil.copytree(ROOT/'examples/final_project', tmp_path/'examples/final_project')
    return ProjectConfig(project_root=tmp_path), AuthConfig(uuid4().hex,
        {f'coach{i:02d}': uuid4().hex for i in range(1,9)})


class FakeIO:
    def __init__(self):
        self.sessions, self.rooms, self.emissions = {}, {}, []

    async def save_session(self, sid, data): self.sessions[sid]=deepcopy(data)
    async def get_session(self, sid): return deepcopy(self.sessions[sid])
    async def enter_room(self, sid, room): self.rooms.setdefault(room,set()).add(sid)
    async def emit(self, event, data, *, to=None, room=None):
        recipients={to} if to is not None else self.rooms.get(room,set())
        for sid in recipients: self.emissions.append((sid,event,deepcopy(data)))


class Client:
    def __init__(self, app, sid): self.app,self.sid=app,sid
    async def connect(self): return await self.app.sio.handlers['/']['connect'](self.sid,{},None)
    async def call(self,event,data=None):
        handler=self.app.sio.handlers['/'].get(event)
        return await handler(self.sid,data) if handler else await self.app.sio.handlers['/']['*'](event,self.sid,data)
    async def disconnect(self):
        await self.app.sio.handlers['/']['disconnect'](self.sid)
        io=self.app.test_io
        io.sessions.pop(self.sid,None)
        for members in io.rooms.values(): members.discard(self.sid)


@asynccontextmanager
async def running_app(tmp_path, *, tick_interval=10):
    config,auth=config_and_auth(tmp_path)
    clock,timer=FakeClock(),FakeTimer()
    app=create_app(config,auth,clock=clock.clock(),timer=timer,rng=lambda:0.0,tick_interval=tick_interval)
    io=FakeIO(); app.test_io=io
    for name in ('save_session','get_session','enter_room','emit'): setattr(app.sio,name,getattr(io,name))
    async with app.http.router.lifespan_context(app.http):
        yield app,auth,clock,timer


async def client(app,sid,role,auth,coach_id='coach01'):
    c=Client(app,sid); assert await c.connect()
    payload={} if role=='viewer' else {'token':auth.admin_token} if role=='admin' else {'coachId':coach_id,'token':auth.coach_tokens[coach_id]}
    joined=await c.call('join_'+role,payload)
    assert joined['ok']
    return c,joined


def request(app,request_id,**fields):
    return {'request_id':request_id,'round_id':app.runtime.service.snapshot().round_id,**fields}
