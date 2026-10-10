from copy import deepcopy
import pytest
from final_project.client.admin_viewmodel import AdminViewModel
from final_project.client.transport import ConnectionChanged, SnapshotReceived, CommandAckReceived, TransportError, HttpDataReceived
from final_project.client.results_export import export_results


def state(**changes):
    return {'status':'idle','version':12,'round_id':None,'current_player':None,'deadline_utc':None,
        'remaining_seconds':90,'time_left':90,'minimum_bid':0,'winner':None,'winning_amount':None,
        'coaches':[{'id':'coach01','name':'Coach01'},{'id':'coach02','name':'Coach02'}],
        'allBids':{'coach01':None,'coach02':0},'budgets':{'coach01':1000,'coach02':1000},
        'teams':{'coach01':[],'coach02':[]},'canUndo':False,**changes}


def model(**changes):
    m=AdminViewModel(now=lambda:1000)
    m.handle(SnapshotReceived(state(**changes)))
    m.handle(ConnectionChanged('connected'))
    m.handle(HttpDataReceived('members',['Player01','Player02']))
    return m


@pytest.mark.parametrize('status,enabled',[
    ('idle',{'start_auction'}),('running',{'pause_auction','end_auction'}),
    ('paused',{'resume_auction','end_auction'}),('ended',{'start_auction'})])
def test_control_status(status,enabled):
    m=model(status=status)
    for event in ('start_auction','pause_auction','resume_auction','end_auction'):
        assert m.enabled(event)==(event in enabled)
    m.handle(ConnectionChanged('offline'))
    assert not any(m.enabled(e) for e in (*enabled,'add_all_budgets','undo_last_award'))


@pytest.mark.parametrize('duration',['','0','-1','1.5','True','86401'])
def test_invalid_duration(duration):
    with pytest.raises(ValueError): model().payload('start_auction','Player01',duration)


def test_start_payload_and_sold_selection_filter():
    m=model()
    assert m.payload('start_auction','Player01','5')=={'playerName':'Player01','duration':5}
    with pytest.raises(ValueError): m.payload('start_auction','','5')
    m.selected_player='Player01'
    m.handle(SnapshotReceived(state(version=13,status='ended',teams={'coach01':['Player01']})))
    assert m.available_players==['Player02'] and not m.selected_player
    with pytest.raises(ValueError): m.payload('start_auction','Player01','5')
    # Delayed HTTP members cannot make a sold player selectable again.
    m.handle(HttpDataReceived('members',['Player01','Player02']))
    assert m.available_players==['Player02']


def test_bid_none_zero_minimum_budget_team_winner_and_undo():
    m=model()
    assert m.bid_rows[0][2]=='—' and m.bid_rows[1][2]=='0'
    assert not m.enabled('undo_last_award')
    m.handle(SnapshotReceived(state(version=13,status='ended',round_id='r',minimum_bid=300,
        allBids={'coach01':None,'coach02':350},budgets={'coach01':1000,'coach02':650},
        teams={'coach01':[],'coach02':['Player01']},winner='coach02',winning_amount=350,canUndo=True)))
    assert m.bid_rows[1][2:5]==('350',650,1)
    assert m.snapshot['minimum_bid']==300 and m.snapshot['winner']=='coach02'
    assert m.enabled('undo_last_award')
    assert m.payload('set_minimum_bid','400')=={'round_id':'r','amount':400}


def test_pending_click_guard_ack_and_snapshot_order():
    m=model()
    m.mark_pending('req','start_auction')
    with pytest.raises(ValueError): m.payload('start_auction','Player02','90')
    m.handle(CommandAckReceived({'request_id':'req','ok':True,'version':13}))
    assert m.pending and m.latest_version==12 and m.snapshot['status']=='idle'
    m.handle(SnapshotReceived(state(version=13,status='running',round_id='r')))
    assert m.pending is None and m.enabled('pause_auction')
    before=deepcopy(m.snapshot)
    m.handle(CommandAckReceived({'request_id':'old','ok':True,'version':11,'payload':{'status':'ended'}}))
    m.handle(SnapshotReceived(state(version=11)))
    assert m.snapshot==before and m.latest_version==13
    m.mark_pending('req2','pause_auction')
    m.handle(SnapshotReceived(state(version=14,status='paused',round_id='r')))
    m.handle(CommandAckReceived({'request_id':'req2','ok':True,'version':14}))
    assert m.pending is None


def test_reconnect_preserves_then_replaces_state_and_errors():
    m=model(status='running',round_id='r',deadline_utc=1090)
    before=deepcopy(m.snapshot)
    m.handle(ConnectionChanged('reconnecting'))
    assert m.snapshot==before and not m.enabled('end_auction')
    for code in ('AUTH_FAILED','CONNECTION_FAILED','PERSISTENCE_ERROR'):
        m.handle(TransportError(code)); assert m.message and m.snapshot==before
    m.handle(SnapshotReceived(state(version=15,status='ended',round_id='r',canUndo=True)))
    m.handle(ConnectionChanged('connected'))
    assert m.enabled('undo_last_award') and m.enabled('start_auction')
    m.handle(CommandAckReceived({'ok':False,'error_code':'INVALID_STATE','message':'secret traceback'}))
    assert 'secret' not in m.message


@pytest.mark.parametrize('value',['0','-1','1.5',''])
def test_add_budget_validation(value):
    with pytest.raises(ValueError): model().payload('add_all_budgets',value)


def test_export_results_encoding_columns_and_no_local_state(tmp_path):
    path=tmp_path/'results.csv'
    export_results(path,[{'playerName':'Player01','coachId':'coach01','amount':0}])
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')
    assert path.read_text(encoding='utf-8-sig').splitlines()==['playerName,coachId,amount','Player01,coach01,0']
    export_results(path,[{'playerName':'=FORMULA','coachId':'coach01','amount':100}])
    assert "'=FORMULA" in path.read_text(encoding='utf-8-sig')
    with pytest.raises(ValueError): export_results(path,[{'amount':100}])


def test_countdown_cannot_disable_force_end():
    m=model(status='running',round_id='r',deadline_utc=999)
    assert m.countdown==0 and m.enabled('end_auction')
