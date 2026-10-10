"""Strict event payload schemas, preserving int/float/bool distinctions."""
import re
from .commands import CommandKind

EVENTS = {
    'start_auction': CommandKind.START, 'pause_auction': CommandKind.PAUSE,
    'resume_auction': CommandKind.RESUME, 'end_auction': CommandKind.END,
    'set_minimum_bid': CommandKind.SET_MINIMUM_BID, 'submit_bid': CommandKind.SUBMIT_BID,
    'undo_last_award': CommandKind.UNDO,
    'add_all_budgets': CommandKind.ADD_ALL_BUDGETS,
}


class PayloadError(ValueError):
    pass


def request_id_of(data: object) -> str | None:
    value = data.get('request_id') if isinstance(data, dict) else None
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) else None


def mutation_payload(event: str, data: object) -> tuple[str, str | None, dict]:
    if not isinstance(data, dict) or request_id_of(data) is None:
        raise PayloadError('Invalid request')
    round_id = data.get('round_id')
    if event not in ('start_auction', 'add_all_budgets') and (not isinstance(round_id, str) or not 1 <= len(round_id) <= 128):
        raise PayloadError('Missing round')
    if event == 'add_all_budgets' and round_id is not None and (not isinstance(round_id, str) or not 1 <= len(round_id) <= 128):
        raise PayloadError('Invalid round')
    if event == 'start_auction' and round_id is not None:
        raise PayloadError('Start must not target an existing round')
    fields = {'request_id', 'round_id'}
    payload = {}
    if event == 'start_auction':
        fields |= {'playerName', 'duration'}
        name, duration = data.get('playerName'), data.get('duration', 90)
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or type(duration) is not int or not 1 <= duration <= 86400:
            raise PayloadError('Invalid start')
        payload = {'player_name': name, 'duration': duration}
    elif event in ('submit_bid', 'set_minimum_bid', 'add_all_budgets'):
        fields.add('amount')
        amount = data.get('amount')
        if type(amount) is not int or amount < 0 or amount > 2**53 - 1:
            raise PayloadError('Invalid amount')
        if event == 'add_all_budgets' and amount == 0:
            raise PayloadError('Invalid amount')
        payload = {'amount': amount}
    if not set(data).issubset(fields):
        # coachId is deliberately rejected, never used as an identity hint.
        raise PayloadError('Unexpected fields')
    return data['request_id'], round_id, payload
