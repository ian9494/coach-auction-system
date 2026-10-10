"""Transport-independent commands and serializable ACK values."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandKind(str, Enum):
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    SUBMIT_BID = "submit_bid"
    SET_MINIMUM_BID = "set_minimum_bid"
    END = "end"
    UNDO = "undo"
    TIMEOUT = "timeout"
    ADD_ALL_BUDGETS = "add_all_budgets"


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    request_id: str
    round_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    error_code: str | None
    message: str
    version: int
    round_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)
