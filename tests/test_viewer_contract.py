import asyncio
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from .transport_support import running_app,client,request
from .test_projections import FORBIDDEN,keys

ROOT=Path(__file__).resolve().parents[1]


def test_viewer_registered_transport_sealed_until_end(tmp_path):
    async def run():
        async with running_app(tmp_path) as (app,auth,clock,timer):
            admin,_=await client(app,'admin','admin',auth)
            coach,_=await client(app,'coach','coach',auth)
            viewer,_=await client(app,'viewer','viewer',auth)
            await admin.call('start_auction',{'request_id':'start','playerName':'Player01'})
            await coach.call('submit_bid',request(app,'bid',amount=317))
            await app.transport.broadcast(app.runtime.service.snapshot())
            frames=[data for sid,event,data in app.test_io.emissions if sid=='viewer']
            assert frames and all(not keys(frame)&FORBIDDEN for frame in frames)
            assert all('317' not in json.dumps(frame) for frame in frames)
            assert frames[-1]['winner'] is None and frames[-1]['winning_amount'] is None
            await admin.call('end_auction',request(app,'end'))
            await app.transport.broadcast(app.runtime.service.snapshot())
            ended=[data for sid,event,data in app.test_io.emissions if sid=='viewer'][-1]
            assert ended['winner']=='coach01' and ended['winning_amount']==317
    asyncio.run(run())


def test_javascript_allowlist_countdown_and_versions():
    node=shutil.which('node')
    if not node: pytest.skip('Node unavailable for JS contract check')
    script=r"""
const assert=require('node:assert/strict');
require('./public/final-project/viewer.js');
const {ViewerModel,publicSnapshot}=global.FinalProjectViewer;
let now=1000; const m=new ViewerModel(()=>now);
const state={version:12,status:'running',coaches:[{id:'c',name:'<b>Coach</b>',token:'private'}],
  teams:{c:['<img src=x>']},budgets:{c:1000},current_player:'Player01',time_left:90,
  remaining_seconds:90,deadline_utc:1090,winner:'c',winning_amount:317,
  bids:{c:317},allBids:{c:317},myBid:317,leader:'c',highestBid:317,processed:{secret:'private'}};
assert(m.apply(state)); assert.equal(m.countdown(),90);
assert(!JSON.stringify(m.state).includes('317')); assert(!JSON.stringify(m.state).includes('private'));
assert.equal(m.state.coaches[0].name,'<b>Coach</b>');
assert.equal(m.state.winner,null); assert.equal(m.state.winning_amount,null);
now=1100; assert.equal(m.countdown(),0); assert.equal(m.state.status,'running');
assert(!m.apply({...state,version:11,status:'ended'})); assert.equal(m.latest_version,12);
assert(m.apply({...state,version:13,status:'ended'})); assert.equal(m.state.winning_amount,317);
assert(m.apply({...state,version:14,round_id:'new',current_player:'Player02'})); assert.equal(m.state.winner,null);
assert(m.apply({...state,version:15,status:'paused',remaining_seconds:30}));
now=5000; assert.equal(m.countdown(),30);
assert(!m.apply({version:true,status:'running'}));
const fallback=new ViewerModel(()=>now);
assert(fallback.apply({...state,deadline_utc:null,version:1})); now+=5; assert.equal(fallback.countdown(),85);
assert(!fallback.apply({...state,version:1,remaining_seconds:91}));
console.log('Viewer public contract passed');
"""
    result=subprocess.run([node,'-e',script],cwd=ROOT,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_viewer_source_rejoins_on_connect_without_private_fields():
    source=(ROOT/'public/final-project/viewer.js').read_text(encoding='utf-8')
    for field in ('bids','allBids','highestBid','highestBidder','leader','myBid','bidRules'):
        assert field not in source
    assert "socket.on('connect', () =>" in source
    assert "emit('join_viewer', {}" in source
    assert "socket.on('viewer_state', accept)" in source
