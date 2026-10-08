"""Copy-on-transition domain API; caller owns clock, RNG and side effects."""
from copy import deepcopy
from typing import Callable
from .errors import DomainError
from .models import AuctionState, AuctionStatus, Award, UndoAward
from .rules import apply_auto_minimum_bids, get_bid_error, get_winner, prune_invalid_bids


def start_auction(state: AuctionState, player_name: str, duration: int = 90) -> AuctionState:
    if state.status in (AuctionStatus.RUNNING, AuctionStatus.PAUSED):
        raise DomainError("auction_active")
    if not isinstance(player_name, str) or not player_name.strip():
        raise DomainError("invalid_player")
    if type(duration) is not int or duration <= 0:
        raise DomainError("invalid_duration")
    new = deepcopy(state)
    new.status = AuctionStatus.RUNNING
    new.current_player = player_name.strip()
    new.duration = new.time_left = duration
    new.winner = new.winning_amount = new.last_award_undo = None
    new.bids = {c.id: None for c in new.coaches}
    new.bids = apply_auto_minimum_bids(new)
    return new


def pause_auction(state: AuctionState) -> AuctionState:
    new = deepcopy(state)
    if new.status == AuctionStatus.RUNNING:
        new.status = AuctionStatus.PAUSED
    return new


def resume_auction(state: AuctionState) -> AuctionState:
    new = deepcopy(state)
    if new.status == AuctionStatus.PAUSED:
        new.status = AuctionStatus.RUNNING
    return new


def submit_bid(state: AuctionState, coach_id: str, amount: object) -> AuctionState:
    if state.status != AuctionStatus.RUNNING:
        raise DomainError("not_running")
    error = get_bid_error(state, coach_id, amount)
    if error is not None:
        raise DomainError(error)
    new = deepcopy(state)
    new.bids[coach_id] = amount
    return new


def set_minimum_bid(state: AuctionState, amount: object) -> AuctionState:
    if type(amount) is not int or amount < 0:
        raise DomainError("invalid_amount")
    new = deepcopy(state)
    new.minimum_bid = amount
    new.bids = prune_invalid_bids(new)
    return new


def end_auction(state: AuctionState, *, rng: Callable[[], float], clock: Callable[[], str]) -> AuctionState:
    new = deepcopy(state)
    if new.status not in (AuctionStatus.RUNNING, AuctionStatus.PAUSED):
        return new  # idempotent for already-ended state; no RNG or clock call
    new.bids = prune_invalid_bids(new)
    result = get_winner(new, rng)
    new.status = AuctionStatus.ENDED
    new.time_left = 0
    new.winner, new.winning_amount = result.winner, result.winning_amount
    if result.winner is not None:
        award = Award(new.current_player, result.winner, result.winning_amount, clock())
        new.last_award_undo = UndoAward(award, dict(new.bids))
        new.budgets[result.winner] -= result.winning_amount
        new.history.append(award)
    return new


def undo_last_award(state: AuctionState) -> AuctionState:
    new = deepcopy(state)
    undo = new.last_award_undo
    if undo is None:
        raise DomainError("nothing_to_undo")
    if not new.history or (new.history[-1].player, new.history[-1].coach_id, new.history[-1].amount) != (
            undo.award.player, undo.award.coach_id, undo.award.amount):
        raise DomainError("undo_history_mismatch")
    new.history.pop()
    new.budgets[undo.award.coach_id] += undo.award.amount
    new.status = AuctionStatus.ENDED
    new.current_player = undo.award.player
    new.time_left = 0
    new.bids = dict(undo.bids)
    new.winner = new.winning_amount = new.last_award_undo = None
    return new
