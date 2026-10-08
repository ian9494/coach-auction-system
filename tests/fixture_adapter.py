"""Test-only JSON adapter, keeping fixture serialization out of domain code."""
import csv
import json
from dataclasses import asdict
from pathlib import Path
from final_project.domain.models import AuctionState, AuctionStatus, Coach, Player, Award, UndoAward
from final_project.domain import rules, transitions

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT/'tests/fixtures/auction_cases.json').read_text(encoding='utf-8'))
COACHES = tuple(Coach(*row) for row in csv.reader((ROOT/FIXTURE['roster']['coach_file']).read_text().splitlines()))
ROSTER = tuple(Player(n) for n in (ROOT/FIXTURE['roster']['member_file']).read_text().splitlines())

def award(row):
    return Award(row['playerName'],row['winner'],row['amount'],row.get('time'))

def state_from(row):
    undo=row.get('lastAwardUndo')
    return AuctionState(COACHES,ROSTER,status=AuctionStatus(row['status']),current_player=row['currentPlayer'],
        duration=row['duration'],time_left=row['timeLeft'],minimum_bid=row['minimumBid'],bids=row['bids'],budgets=row['budgets'],
        history=[award(h) for h in row['history']],winner=row['winner'],winning_amount=row['winningAmount'],
        last_award_undo=UndoAward(award(undo),undo['bids']) if undo else None)

def snapshot(state):
    return {'status':state.status.value,'currentPlayer':state.current_player,'timeLeft':state.time_left,
        'duration':state.duration,'minimumBid':state.minimum_bid,'bids':state.bids,'budgets':state.budgets,
        'history':[{'playerName':h.player,'winner':h.coach_id,'amount':h.amount,**({'time':h.time} if h.time is not None else {})} for h in state.history],
        'winner':state.winner,'winningAmount':state.winning_amount,'canUndo':state.last_award_undo is not None}

def run_case(case):
    state=state_from(case['initial'])
    values=iter(case.get('rng_values',[0]))
    rng=lambda:next(values)
    result=None
    for step in case['steps']:
        op,a=step['operation'],step['args']
        if op=='validate_bid':
            error=rules.get_bid_error(state,a['coachId'],a['amount']); r=rules.get_bid_rules(state,a['coachId'])
            result={'valid':error is None,'error_category':error,'playerCount':r.player_count,'minBid':r.min_bid,
                'maxBid':r.max_bid,'playerZone':{'id':r.player_zone.id,'size':r.player_zone.size,'coachLimit':r.player_zone.coach_limit} if r.player_zone else None,
                'zonePlayerCount':r.zone_player_count,'zoneLimit':r.zone_limit,'zoneLimitReached':r.zone_limit_reached,
                'remainingSlotsAfterWin':r.remaining_slots_after_win,'reserveForRemaining':r.reserve_for_remaining}
        elif op=='select_winner':
            w=rules.get_winner(state,rng); result={'winner':w.winner,'winningAmount':w.winning_amount,'candidates':list(w.candidates)}
        elif op=='submit_bid': state=transitions.submit_bid(state,a['coachId'],a['amount'])
        elif op=='set_minimum_bid': state=transitions.set_minimum_bid(state,a['amount'])
        elif op=='start_auction': state=transitions.start_auction(state,a['playerName'],a['duration'])
        elif op=='pause': state=transitions.pause_auction(state)
        elif op=='resume': state=transitions.resume_auction(state)
        elif op=='undo_last_award': state=transitions.undo_last_award(state)
        elif op=='end_auction': state=transitions.end_auction(state,rng=rng,clock=lambda:'TEST_CLOCK')
        else: raise AssertionError(op)
    return result if result is not None else snapshot(state)

def assert_partial(actual, expected):
    if isinstance(expected,dict):
        for key,value in expected.items():
            assert key in actual
            assert_partial(actual[key],value)
    elif isinstance(expected,list):
        assert len(actual)==len(expected)
        for a,e in zip(actual,expected): assert_partial(a,e)
    else: assert actual==expected
