from copy import deepcopy
import pytest
from final_project.domain.models import Player, Award
from final_project.domain import rules
from .fixture_adapter import FIXTURE,state_from

def fresh(): return state_from(FIXTURE['cases'][0]['initial'])

@pytest.mark.parametrize('index,zone',[(1,1),(8,1),(9,2),(16,2),(17,3),(40,3),(41,None)])
def test_zone_boundaries(index,zone):
    s=fresh(); s.roster+= (Player('Player41'),)
    z=rules.get_player_zone(s,f'Player{index:02d}')
    assert (z.id if z else None)==zone

def test_unknown_zone(): assert rules.get_player_zone(fresh(),'unknown') is None

@pytest.mark.parametrize('value',[True,False,1.0,'100',None,-1,float('nan')])
def test_strict_amount(value): assert rules.get_bid_error(fresh(),'coach01',value)=='invalid_amount'

def test_invalid_coach(): assert rules.get_bid_error(fresh(),'invalid',100)=='invalid_coach'

@pytest.mark.parametrize('case',[c for c in FIXTURE['cases'] if c['steps'][0]['operation']=='validate_bid'],ids=lambda c:c['id'])
def test_validation_cases(case):
    s=state_from(case['initial']); a=case['steps'][0]['args']
    assert (rules.get_bid_error(s,a['coachId'],a['amount']) is None)==case['expected']['valid']

def test_auto_excludes_full_zone_and_unaffordable():
    s=fresh(); s.current_player='Player02'; s.history=[Award('Player01','coach01',200)]
    s.budgets['coach02']=50; s.minimum_bid=100
    bids=rules.apply_auto_minimum_bids(s)
    assert 'coach01' not in bids and 'coach02' not in bids and bids['coach03']==100

def test_legacy_zero_allowed_when_budget_below_reserve():
    s=fresh(); s.budgets['coach01']=50
    assert rules.get_bid_rules(s,'coach01').max_bid==0
    assert rules.get_bid_error(s,'coach01',0) is None

def test_invalid_rng():
    s=fresh(); s.bids={'coach01':0}
    for value in [True,-0.1,1,float('nan')]:
        with pytest.raises(ValueError): rules.get_winner(s,lambda:value)

def test_rules_no_mutation():
    s=fresh(); s.bids={'coach01':100}; before=deepcopy(s)
    rules.get_bid_rules(s,'coach01'); rules.prune_invalid_bids(s); rules.apply_auto_minimum_bids(s)
    assert s==before
