"""Headless Admin presenter: snapshots own state, commands own only pending UX."""
from copy import deepcopy
import math
import time

from .coach_viewmodel import parse_amount
from .transport import ConnectionChanged, SnapshotReceived, CommandAckReceived, TransportError, HttpDataReceived

ERRORS = {
    'AUTH_FAILED':'Admin 認證失敗，請確認 Token。', 'CONNECTION_FAILED':'連線失敗，正在重連。',
    'OFFLINE':'Server 離線，無法操作。', 'UNCONFIRMED':'操作尚未確認，請重新連線查看狀態後再決定。',
    'HTTP_FAILED':'無法取得名單／結果，請稍後重新整理。',
    'INVALID_STATE':'目前競標狀態不允許此操作。', 'INVALID_COMMAND':'選手、時間或操作參數不合法。',
    'INVALID_BID':'金額不符合規則。', 'INVALID_PAYLOAD':'輸入格式不正確。',
    'PERSISTENCE_ERROR':'Server 暫時無法儲存，請稍後再試。', 'STALE_ROUND':'競標輪次已變更，請查看最新畫面。',
    'UNAUTHORIZED':'認證失敗，請重新登入。', 'REQUEST_ID_CONFLICT':'操作識別碼衝突，請重新操作。',
}


class AdminViewModel:
    def __init__(self, now=time.time):
        self.now = now
        self.connection = 'offline'
        self.latest_version = -1
        self.snapshot = None
        self.members = []
        self.selected_player = ''
        self.message = ''
        self.pending = None
        self._ack_version = None
        self._received_at = 0

    def handle(self, event):
        if isinstance(event, ConnectionChanged):
            self.connection = event.state
            if event.state != 'connected':
                self.pending = self._ack_version = None
        elif isinstance(event, TransportError):
            self.message = ERRORS.get(event.code, 'Server 暫時無法處理。')
            if event.code != 'HTTP_FAILED':
                self.pending = self._ack_version = None
        elif isinstance(event, HttpDataReceived) and event.resource == 'members':
            if all(isinstance(name, str) and name for name in event.data):
                self.members = list(dict.fromkeys(event.data))
                self._filter_selection()
        elif isinstance(event, SnapshotReceived):
            data = event.snapshot
            version = data.get('version')
            if type(version) is not int or version < self.latest_version or 'allBids' not in data:
                return
            fields = ('status','current_player','duration','time_left','remaining_seconds','deadline_utc',
                      'minimum_bid','coaches','budgets','teams','winner','winning_amount','version','round_id',
                      'allBids','canUndo')
            self.snapshot = deepcopy({key:data[key] for key in fields if key in data})
            self.latest_version = version
            self._received_at = self.now()
            self._filter_selection()
            if self._ack_version is not None and version >= self._ack_version:
                self.pending = self._ack_version = None
        elif isinstance(event, CommandAckReceived):
            ack = event.ack
            self.message = '操作成功，畫面以 Server snapshot 為準。' if ack.get('ok') else ERRORS.get(
                ack.get('error_code'), 'Server 拒絕此操作。')
            if self.pending and self.pending[0] == ack.get('request_id'):
                version = ack.get('version', -1)
                if not ack.get('ok') or version <= self.latest_version:
                    self.pending = self._ack_version = None
                else:
                    self._ack_version = version

    def _filter_selection(self):
        if self.selected_player not in self.available_players:
            self.selected_player = ''

    @property
    def available_players(self):
        sold = {name for names in (self.snapshot or {}).get('teams', {}).values() for name in names}
        return [name for name in self.members if name not in sold]

    @property
    def countdown(self):
        s = self.snapshot or {}
        remaining = s.get('remaining_seconds', s.get('time_left', 0))
        if s.get('status') == 'running':
            deadline = s.get('deadline_utc')
            remaining = deadline-self.now() if deadline is not None else remaining-(self.now()-self._received_at)
        return math.ceil(max(0, remaining))

    def enabled(self, event):
        if self.connection != 'connected' or self.snapshot is None or self.pending:
            return False
        status = self.snapshot.get('status')
        if event == 'start_auction': return status in ('idle','ended')
        if event == 'pause_auction': return status == 'running'
        if event == 'resume_auction': return status == 'paused'
        if event == 'end_auction': return status in ('running','paused')
        if event == 'undo_last_award': return bool(self.snapshot.get('canUndo'))
        if event == 'set_minimum_bid': return self.snapshot.get('round_id') is not None
        return event == 'add_all_budgets'

    def payload(self, event, value='', duration='90'):
        if not self.enabled(event):
            raise ValueError('目前狀態或待確認操作不允許此操作。')
        if event == 'start_auction':
            if value not in self.available_players:
                raise ValueError('請選擇尚未售出的有效選手。')
            seconds = parse_amount(duration)
            if not 1 <= seconds <= 86400:
                raise ValueError('時間必須是 1～86400 的正整數。')
            return {'playerName':value, 'duration':seconds}
        payload = {'round_id':self.snapshot.get('round_id')}
        if event in ('set_minimum_bid','add_all_budgets'):
            amount = parse_amount(value)
            if event == 'add_all_budgets' and amount == 0:
                raise ValueError('增加預算必須大於 0。')
            payload['amount'] = amount
        return payload

    def mark_pending(self, request_id, event):
        if request_id:
            self.pending = (request_id, event)
            self.message = '操作送出中，等待 Server 確認…'

    @property
    def bid_rows(self):
        s = self.snapshot or {}
        return [(c['id'],c['name'], '—' if s.get('allBids',{}).get(c['id']) is None else str(s['allBids'][c['id']]),
                 s.get('budgets',{}).get(c['id'],0),len(s.get('teams',{}).get(c['id'],[])),
                 '依 Server 判定') for c in s.get('coaches',[])]
