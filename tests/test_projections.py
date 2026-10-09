import json
from final_project.server.projections import viewer_projection,coach_projection,admin_projection
from final_project.storage.repository import Snapshot
from final_project.domain import transitions
from .service_support import initial


FORBIDDEN={'bids','allBids','highest_bidder','highestBidder','leading_coach','leader','highest_amount',
           'ticker','processed','last_award_undo','myBid','bidRules'}


def keys(value):
    if isinstance(value,dict):
        return set(value)|set().union(*(keys(v) for v in value.values()))
    if isinstance(value,list): return set().union(*(keys(v) for v in value)) if value else set()
    return set()


def active():
    state=transitions.start_auction(initial(),'Player17')
    state=transitions.submit_bid(state,'coach01',213)
    state=transitions.submit_bid(state,'coach02',317)
    return Snapshot(state,version=3,round_id='round',remaining=90,deadline_utc=1090)


def test_viewer_allowlist_has_no_sensitive_fields_or_amounts():
    snapshot=active(); projected=viewer_projection(snapshot)
    assert not keys(projected)&FORBIDDEN
    assert '213' not in json.dumps(projected) and '317' not in json.dumps(projected)
    assert projected['winner'] is None and projected['winning_amount'] is None
    assert projected['version']==3 and projected['round_id']=='round'


def test_coach_only_own_bid_and_rules():
    snapshot=active()
    for cid,own,other in [('coach01',213,317),('coach02',317,213)]:
        projected=coach_projection(snapshot,cid)
        assert projected['myBid']==own and projected['coach']['id']==cid
        assert str(other) not in json.dumps(projected)
        assert not keys(projected)&(FORBIDDEN-{'myBid','bidRules'})
        assert projected['eligible'] is True


def test_admin_has_all_bids_and_ended_viewer_result():
    snapshot=active()
    assert admin_projection(snapshot)['allBids']['coach02']==317
    snapshot.state=transitions.end_auction(snapshot.state,rng=lambda:0,clock=lambda:'TEST')
    assert viewer_projection(snapshot)['winner']=='coach02'
    assert viewer_projection(snapshot)['winning_amount']==317
    assert not keys(viewer_projection(snapshot))&FORBIDDEN
    assert admin_projection(snapshot)['canUndo'] is True


def test_projection_is_copy_not_authority():
    snapshot=active(); p=admin_projection(snapshot)
    p['allBids']['coach01']=0; p['budgets']['coach01']=0
    assert snapshot.state.bids['coach01']==213 and snapshot.state.budgets['coach01']==1000
