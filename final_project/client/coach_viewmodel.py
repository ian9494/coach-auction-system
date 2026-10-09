"""Display-only Coach state; snapshots are authoritative, ACKs only report results."""
from copy import deepcopy
import math
import re
import time

from .transport import ConnectionChanged, SnapshotReceived, CommandAckReceived, TransportError

MESSAGES = {
    'AUTH_FAILED':'認證失敗，請確認教練 ID 與 Token。',
    'CONNECTION_FAILED':'連線失敗，正在嘗試重新連線。',
    'OFFLINE':'目前離線，請先連線。',
    'UNCONFIRMED':'尚未確認送出結果，請重新連線後查看目前出價。',
    'INVALID_BID':'出價不符合預算、金額或名額規則。',
    'INVALID_STATE':'此輪目前無法出價，可能已暫停或結束。',
    'STALE_ROUND':'此輪已更換，請查看最新競標資訊。',
    'DEADLINE_PASSED':'此輪競標已截止。',
    'PERSISTENCE_ERROR':'Server 暫時無法儲存，請稍後再試。',
    'UNAUTHORIZED':'認證失敗，請重新連線。',
    'REQUEST_ID_CONFLICT':'操作識別碼衝突，請重新操作。',
}


def parse_amount(text):
    text = text.strip()
    if not re.fullmatch(r'[0-9]{1,16}', text):
        raise ValueError('請輸入非負整數金額。')
    amount = int(text)
    if amount > 2**53 - 1:
        raise ValueError('金額過大。')
    return amount


class CoachViewModel:
    def __init__(self, now=time.time):
        self.now = now
        self.connection = 'offline'
        self.latest_version = -1
        self.snapshot = None
        self.message = ''
        self._received_at = 0

    def handle(self, event):
        if isinstance(event, ConnectionChanged):
            self.connection = event.state
        elif isinstance(event, TransportError):
            self.message = MESSAGES.get(event.code, 'Server 暫時無法處理，請稍後再試。')
        elif isinstance(event, CommandAckReceived):
            # Never reconstruct snapshot or advance latest_version from an ACK.
            self.message = '出價已確認／修改成功，狀態以 Server 畫面為準。' if event.ack.get('ok') else MESSAGES.get(
                event.ack.get('error_code'), 'Server 暫時無法處理此出價。')
        elif isinstance(event, SnapshotReceived):
            data = event.snapshot
            version = data.get('version')
            if type(version) is not int or version < self.latest_version or not isinstance(data.get('coach'), dict):
                return
            # Allowlist even if an unexpected server payload contains private fields.
            fields = ('status','current_player','time_left','remaining_seconds','deadline_utc','minimum_bid',
                      'coaches','budgets','teams','winner','winning_amount','version','round_id','coach',
                      'myBid','bidRules','eligible')
            self.snapshot = deepcopy({key:data[key] for key in fields if key in data})
            self.latest_version = version
            self._received_at = self.now()

    @property
    def countdown(self):
        s = self.snapshot or {}
        if s.get('status') != 'running':
            return math.ceil(max(0, s.get('remaining_seconds', s.get('time_left', 0))))
        deadline = s.get('deadline_utc')
        remaining = deadline - self.now() if deadline is not None else s.get('time_left', 0) - (self.now() - self._received_at)
        return math.ceil(max(0, remaining))

    @property
    def bid_enabled(self):
        s = self.snapshot or {}
        return self.connection == 'connected' and s.get('status') == 'running' and bool(s.get('eligible')) and self.countdown > 0

    @property
    def bid_text(self):
        bid = (self.snapshot or {}).get('myBid')
        return '尚未出價' if bid is None else f'已出價 {bid}'
