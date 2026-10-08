"""Typed domain values; no transport, persistence or timer ownership."""
from dataclasses import dataclass, field
from enum import Enum


class AuctionStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ENDED = "ended"


@dataclass(frozen=True)
class Coach:
    id: str
    name: str


@dataclass(frozen=True)
class Player:
    name: str


@dataclass(frozen=True)
class Zone:
    id: int
    size: int
    coach_limit: int


@dataclass(frozen=True)
class Bid:
    coach_id: str
    amount: int

    def __post_init__(self):
        if type(self.amount) is not int or self.amount < 0:
            raise ValueError("Bid amount must be a non-negative int")


@dataclass(frozen=True)
class Award:
    player: str
    coach_id: str
    amount: int
    time: str | None = None

    def __post_init__(self):
        if type(self.amount) is not int or self.amount < 0:
            raise ValueError("Award amount must be a non-negative int")


@dataclass
class UndoAward:
    award: Award
    bids: dict[str, int | None]


@dataclass
class AuctionState:
    coaches: tuple[Coach, ...]
    roster: tuple[Player, ...]
    status: AuctionStatus = AuctionStatus.IDLE
    current_player: str | None = None
    duration: int = 90
    time_left: int = 0
    minimum_bid: int = 0
    bids: dict[str, int | None] = field(default_factory=dict)
    budgets: dict[str, int] = field(default_factory=dict)
    history: list[Award] = field(default_factory=list)
    winner: str | None = None
    winning_amount: int | None = None
    last_award_undo: UndoAward | None = None

    def __post_init__(self):
        self.status = AuctionStatus(self.status)
        ids = [c.id for c in self.coaches]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate coach ID")
        for value in [self.duration, self.time_left, self.minimum_bid, *self.budgets.values()]:
            if type(value) is not int or value < 0:
                raise ValueError("State monetary/time values must be non-negative ints")
        for value in self.bids.values():
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("State bids must be int or None")
        if self.winning_amount is not None and (type(self.winning_amount) is not int or self.winning_amount < 0):
            raise ValueError("winning_amount must be int or None")
        if not set(self.bids).issubset(ids) or not set(self.budgets).issubset(ids):
            raise ValueError("Unknown coach in state maps")
        self.bids = dict(self.bids)
        self.budgets = dict(self.budgets)
        self.history = list(self.history)
        for coach_id in ids:
            self.budgets.setdefault(coach_id, 1000)
