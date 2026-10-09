"""Allowlisted role projections. No full Snapshot ever crosses transport."""
from dataclasses import asdict
from final_project.domain.models import AuctionStatus
from final_project.domain.rules import get_bid_error, get_bid_rules
from final_project.storage.repository import Snapshot


def viewer_projection(snapshot: Snapshot) -> dict:
    state = snapshot.state
    ended = state.status == AuctionStatus.ENDED
    return {
        'status': state.status.value, 'current_player': state.current_player,
        'duration': state.duration, 'time_left': state.time_left, 'remaining_seconds': snapshot.remaining,
        'deadline_utc': snapshot.deadline_utc, 'minimum_bid': state.minimum_bid,
        'coaches': [asdict(c) for c in state.coaches], 'budgets': dict(state.budgets),
        'teams': {c.id: [h.player for h in state.history if h.coach_id == c.id] for c in state.coaches},
        'winner': state.winner if ended else None,
        'winning_amount': state.winning_amount if ended else None,
        'version': snapshot.version, 'round_id': snapshot.round_id,
    }


def coach_projection(snapshot: Snapshot, coach_id: str) -> dict:
    state = snapshot.state
    coach = next(c for c in state.coaches if c.id == coach_id)
    rules = get_bid_rules(state, coach_id)
    return {**viewer_projection(snapshot), 'coach': asdict(coach), 'myBid': state.bids.get(coach_id),
            'bidRules': asdict(rules),
            'eligible': state.status == AuctionStatus.RUNNING and snapshot.remaining > 0 and get_bid_error(state, coach_id, rules.min_bid) is None}


def admin_projection(snapshot: Snapshot) -> dict:
    return {**viewer_projection(snapshot), 'allBids': dict(snapshot.state.bids),
            'canUndo': snapshot.state.last_award_undo is not None}
