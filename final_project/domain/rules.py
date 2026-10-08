"""Pure rules ported from server.js. RNG is supplied by the caller."""
from dataclasses import dataclass
from typing import Callable
from .models import AuctionState, Zone

ZONES = (Zone(1, 8, 1), Zone(2, 8, 1), Zone(3, 24, 3))


def get_player_zone(state: AuctionState, name: str | None) -> Zone | None:
    index = next((i for i, p in enumerate(state.roster) if p.name == name), -1)
    if index < 0:
        return None
    start = 0
    for zone in ZONES:
        if start <= index < start + zone.size:
            return zone
        start += zone.size
    return None


def get_coach_player_count(state: AuctionState, coach_id: str) -> int:
    return sum(h.coach_id == coach_id for h in state.history)


def get_coach_spent(state: AuctionState, coach_id: str) -> int:
    return sum(h.amount for h in state.history if h.coach_id == coach_id)


def get_coach_zone_player_count(state: AuctionState, coach_id: str, zone_id: int) -> int:
    return sum(h.coach_id == coach_id and (z := get_player_zone(state, h.player)) is not None
               and z.id == zone_id for h in state.history)


@dataclass(frozen=True)
class BidRules:
    player_count: int
    min_bid: int
    max_bid: int
    player_zone: Zone | None
    zone_player_count: int
    zone_limit: int | None
    zone_limit_reached: bool
    remaining_slots_after_win: int
    reserve_for_remaining: int


def get_bid_rules(state: AuctionState, coach_id: str) -> BidRules:
    count = get_coach_player_count(state, coach_id)
    zone = get_player_zone(state, state.current_player)
    zone_count = get_coach_zone_player_count(state, coach_id, zone.id) if zone else 0
    reached = zone is not None and zone_count >= zone.coach_limit
    slots = max(5 - count - 1, 0)
    minimum = max(state.minimum_bid, 301 - get_coach_spent(state, coach_id) if count == 1 else 0, 0)
    maximum = 0 if reached else min(500, max(0, state.budgets.get(coach_id, 0) - slots * 100))
    return BidRules(count, minimum, maximum, zone, zone_count,
                    zone.coach_limit if zone else None, reached, slots, slots * 100)


def get_bid_error(state: AuctionState, coach_id: str, amount: object) -> str | None:
    if coach_id not in {c.id for c in state.coaches}:
        return "invalid_coach"
    if type(amount) is not int or amount < 0:
        return "invalid_amount"
    if amount < state.minimum_bid:
        return "below_minimum"
    if amount > state.budgets[coach_id]:
        return "above_budget"
    rules = get_bid_rules(state, coach_id)
    if rules.zone_limit_reached:
        return "zone_limit"
    if rules.player_count >= 5:
        return "team_full"
    if amount < rules.min_bid:
        return "second_player_minimum"
    if amount > rules.max_bid:
        return "above_rule_max"
    return None


def prune_invalid_bids(state: AuctionState) -> dict[str, int | None]:
    return {cid: None if bid is not None and get_bid_error(state, cid, bid) else bid
            for cid, bid in state.bids.items()}


def apply_auto_minimum_bids(state: AuctionState) -> dict[str, int | None]:
    bids = dict(state.bids)
    for coach in state.coaches:
        minimum = get_bid_rules(state, coach.id).min_bid
        if get_bid_error(state, coach.id, minimum) is None:
            bids[coach.id] = minimum
    return bids


@dataclass(frozen=True)
class WinnerResult:
    winner: str | None
    winning_amount: int | None
    candidates: tuple[str, ...]


def get_winner(state: AuctionState, rng: Callable[[], float]) -> WinnerResult:
    eligible = [(cid, bid) for cid, bid in state.bids.items()
                if bid is not None and get_bid_error(state, cid, bid) is None]
    if not eligible:
        return WinnerResult(None, None, ())
    maximum = max(bid for _, bid in eligible)
    candidates = tuple(cid for cid, bid in eligible if bid == maximum)
    value = rng()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1:
        raise ValueError("RNG must return a value in [0, 1)")
    return WinnerResult(candidates[int(value * len(candidates))], maximum, candidates)
