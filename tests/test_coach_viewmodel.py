from copy import deepcopy
import pytest
from final_project.client.coach_viewmodel import CoachViewModel, parse_amount
from final_project.client.transport import ConnectionChanged, SnapshotReceived, CommandAckReceived, TransportError


def snapshot(**changes):
    return {'version':12, 'round_id':'r1', 'status':'running','current_player':'Player17',
        'time_left':90,'remaining_seconds':90,'deadline_utc':1090,'eligible':True,
        'coach':{'id':'coach01','name':'Coach01'}, 'myBid':200,'minimum_bid':100,
        'budgets':{'coach01':1000,'coach02':900},'teams':{'coach01':[],'coach02':[]},
        'coaches':[{'id':'coach01','name':'Coach01'}],
        'bidRules':{'min_bid':100,'max_bid':500,'reserve_for_remaining':400}, **changes}


def model(**changes):
    m = CoachViewModel(now=lambda:1000)
    m.handle(SnapshotReceived(snapshot(**changes)))
    m.handle(ConnectionChanged('connected'))
    return m


@pytest.mark.parametrize('connection,status,eligible,enabled',[
    ('offline','running',True,False),('reconnecting','running',True,False),
    ('connected','running',True,True),('connected','paused',True,False),
    ('connected','ended',True,False),('connected','idle',True,False),
    ('connected','running',False,False)])
def test_bid_enable_mapping(connection,status,eligible,enabled):
    m=model(status=status,eligible=eligible)
    m.handle(ConnectionChanged(connection))
    assert m.bid_enabled is enabled


@pytest.mark.parametrize('text',['',' ','-1','1.0','1e2','True','+1','１２','9007199254740992'])
def test_integer_validation_rejects(text):
    with pytest.raises(ValueError): parse_amount(text)


@pytest.mark.parametrize('text,amount',[('0',0),(' 200 ',200),('001',1)])
def test_integer_validation_accepts(text,amount):
    assert parse_amount(text)==amount


def test_snapshot_fields_budget_team_rules_and_privacy():
    m=model(allBids={'coach02':317},bids={'coach02':317},leader='coach02')
    assert not {'allBids','bids','leader'} & m.snapshot.keys()
    assert m.snapshot['current_player']=='Player17' and m.bid_text=='已出價 200'
    assert m.snapshot['minimum_bid']==100 and m.snapshot['bidRules']['max_bid']==500
    m.handle(SnapshotReceived(snapshot(version=13,budgets={'coach01':750},teams={'coach01':['Player17']})))
    assert m.snapshot['budgets']['coach01']==750
    assert m.snapshot['teams']['coach01']==['Player17']


def test_reconnect_preserves_then_replaces_and_stale_ack_cannot_regress():
    m=model()
    before=deepcopy(m.snapshot)
    m.handle(ConnectionChanged('reconnecting'))
    assert m.snapshot==before and not m.bid_enabled
    m.handle(CommandAckReceived({'ok':True,'version':11,'payload':{'myBid':99}}))
    assert m.latest_version==12 and m.snapshot==before
    m.handle(CommandAckReceived({'ok':True,'version':15}))
    assert m.latest_version==12 and m.snapshot==before
    m.handle(SnapshotReceived(snapshot(version=11,current_player='OLD')))
    assert m.snapshot==before
    m.handle(SnapshotReceived(snapshot(version=13,round_id='r2',current_player='Player18',myBid=None)))
    m.handle(ConnectionChanged('connected'))
    assert m.snapshot['current_player']=='Player18' and m.bid_text=='尚未出價' and m.bid_enabled


@pytest.mark.parametrize('event',[
    TransportError('AUTH_FAILED'),TransportError('CONNECTION_FAILED'),TransportError('UNCONFIRMED'),
    CommandAckReceived({'ok':False,'error_code':'INVALID_BID','message':'secret traceback'}),
    CommandAckReceived({'ok':False,'error_code':'unknown','message':'secret traceback'})])
def test_errors_are_friendly_and_preserve_state(event):
    m=model(); before=deepcopy(m.snapshot)
    m.handle(event)
    assert m.message and 'secret' not in m.message and m.snapshot==before


def test_countdown_deadline_fallback_pause_and_zero():
    m=model(); assert m.countdown==90
    m.now=lambda:1091
    assert m.countdown==0 and not m.bid_enabled
    m=model(deadline_utc=None,time_left=40)
    m.now=lambda:1007
    assert m.countdown==33
    m=model(status='paused',remaining_seconds=30)
    m.now=lambda:2000
    assert m.countdown==30


def test_zero_bid_is_not_missing_and_snapshot_is_copied():
    data=snapshot(myBid=0)
    m=CoachViewModel(now=lambda:1000)
    m.handle(SnapshotReceived(data)); data['budgets']['coach01']=0
    assert m.bid_text=='已出價 0' and m.snapshot['budgets']['coach01']==1000
