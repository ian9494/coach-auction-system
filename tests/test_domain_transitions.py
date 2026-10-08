from copy import deepcopy
import pytest
from final_project.domain import transitions as t
from final_project.domain.models import AuctionStatus, Award
from final_project.domain.errors import DomainError
from .fixture_adapter import FIXTURE,state_from

def fresh(): return state_from(FIXTURE['cases'][0]['initial'])

@pytest.mark.parametrize('status',[AuctionStatus.PAUSED,AuctionStatus.ENDED,AuctionStatus.IDLE])
def test_not_running_rejects(status):
    s=fresh(); s.status=status
    with pytest.raises(DomainError,match='not_running'): t.submit_bid(s,'coach01',100)

def test_modify_and_reject_preserves_old_state():
    s=fresh(); a=t.submit_bid(s,'coach01',200); b=t.submit_bid(a,'coach01',150)
    assert not s.bids and a.bids['coach01']==200 and b.bids['coach01']==150
    with pytest.raises(DomainError): t.submit_bid(b,'coach01',501)
    assert b.bids['coach01']==150

def test_minimum_prunes_without_refilling():
    s=fresh(); s.bids={'coach01':100,'coach02':None,'coach03':200}
    n=t.set_minimum_bid(s,150)
    assert n.bids=={'coach01':None,'coach02':None,'coach03':200}
    assert t.set_minimum_bid(n,0).bids==n.bids

def test_start_auto_and_pause_resume():
    s=fresh(); s.status=AuctionStatus.IDLE
    n=t.start_auction(s,'Player17'); p=t.pause_auction(n); r=t.resume_auction(p)
    assert n.bids=={c.id:0 for c in s.coaches}
    assert p.status==AuctionStatus.PAUSED and r.status==AuctionStatus.RUNNING
    assert n.time_left==p.time_left==r.time_left==90
    assert s.status==AuctionStatus.IDLE

def test_settlement_once_and_undo():
    s=fresh(); s.bids={'coach01':250,'coach02':250,'coach03':200}; before=deepcopy(s)
    n=t.end_auction(s,rng=lambda:0.75,clock=lambda:'FIXED')
    assert n.winner=='coach02' and n.budgets['coach02']==750 and len(n.history)==1
    assert n.history[0].time=='FIXED' and s==before
    def forbidden(): raise AssertionError('repeat must not consume RNG or clock')
    repeat=t.end_auction(n,rng=forbidden,clock=forbidden)
    assert repeat==n
    undone=t.undo_last_award(n)
    assert undone.budgets['coach02']==1000 and undone.history==[] and undone.bids==s.bids
    assert undone.status==AuctionStatus.ENDED and undone.winner is None
    with pytest.raises(DomainError): t.undo_last_award(undone)

def test_invalid_bids_pruned_on_end():
    s=fresh(); s.bids={'coach01':501,'coach02':100}
    n=t.end_auction(s,rng=lambda:0,clock=lambda:'FIXED')
    assert n.winner=='coach02' and n.bids['coach01'] is None and s.bids['coach01']==501

def test_no_bid_end():
    s=fresh(); s.bids={'coach01':None}
    n=t.end_auction(s,rng=lambda:0,clock=lambda:'FIXED')
    assert n.winner is None and n.history==[] and n.status==AuctionStatus.ENDED

def test_undo_mismatch_and_new_round_clears_metadata():
    s=fresh(); s.bids={'coach01':200}
    n=t.end_auction(s,rng=lambda:0,clock=lambda:'FIXED')
    bad=deepcopy(n); bad.history.append(Award('Player18','coach02',100))
    with pytest.raises(DomainError,match='undo_history_mismatch'): t.undo_last_award(bad)
    assert len(bad.history)==2
    assert t.start_auction(n,'Player18').last_award_undo is None

@pytest.mark.parametrize('value',[True,1.0,'100',None,-1])
def test_strict_transition_amount(value):
    with pytest.raises(DomainError): t.submit_bid(fresh(),'coach01',value)
    with pytest.raises(DomainError): t.set_minimum_bid(fresh(),value)

@pytest.mark.parametrize('duration',[True,0,-1,1.5,'90'])
def test_bad_duration(duration):
    s=fresh(); s.status=AuctionStatus.IDLE
    with pytest.raises(DomainError): t.start_auction(s,'Player17',duration)

def test_active_start_rejected():
    with pytest.raises(DomainError): t.start_auction(fresh(),'Player17')

def test_blank_player_rejected():
    s=fresh(); s.status=AuctionStatus.IDLE
    with pytest.raises(DomainError): t.start_auction(s,' ')
