"""Tkinter Coach desktop client. All widgets live exclusively on the main thread."""
from queue import Empty
import tkinter as tk
from tkinter import ttk

from .transport import ClientTransport, Credentials
from .coach_viewmodel import CoachViewModel, parse_amount


class CoachApp:
    def __init__(self, root):
        self.root = root
        self.transport = None
        self.model = CoachViewModel()
        self.closing = False
        root.title('期末專題 · Coach 競標客戶端')
        root.geometry('1000x720')
        root.minsize(850, 600)
        root.protocol('WM_DELETE_WINDOW', self.close)
        body = ttk.Frame(root, padding=16)
        body.pack(fill='both', expand=True)
        login = ttk.LabelFrame(body, text='連線與驗證', padding=10)
        login.pack(fill='x')
        self.url = tk.StringVar(value='http://127.0.0.1:3001')
        self.coach_id = tk.StringVar(value='coach01')
        self.token = tk.StringVar()
        for index, (label, value, width) in enumerate((('Server URL',self.url,32),('Coach ID',self.coach_id,12),('Token',self.token,24))):
            ttk.Label(login, text=label).grid(row=0, column=index*2, padx=4)
            ttk.Entry(login, textvariable=value, width=width, show='*' if label == 'Token' else '').grid(row=0, column=index*2+1, padx=4)
        self.connect_button = ttk.Button(login, text='連線', command=self.connect)
        self.connect_button.grid(row=1, column=0, pady=8)
        self.disconnect_button = ttk.Button(login, text='離線', command=self.disconnect, state='disabled')
        self.disconnect_button.grid(row=1, column=1, sticky='w')
        self.connection = tk.StringVar(value='離線')
        ttk.Label(login, textvariable=self.connection).grid(row=1, column=2, columnspan=4, sticky='w')
        middle = ttk.Frame(body)
        middle.pack(fill='x', pady=12)
        auction = ttk.LabelFrame(middle, text='當前競標', padding=12)
        auction.pack(side='left', fill='both', expand=True)
        info = ttk.LabelFrame(middle, text='我的預算與規則', padding=12)
        info.pack(side='left', fill='both', expand=True, padx=(12,0))
        self.auction_text = tk.StringVar(value='等待競標資訊')
        self.rules_text = tk.StringVar(value='登入後取得資訊')
        ttk.Label(auction, textvariable=self.auction_text, justify='left', font=('',12)).pack(anchor='w')
        ttk.Label(info, textvariable=self.rules_text, justify='left').pack(anchor='w')
        bid = ttk.Frame(auction)
        bid.pack(anchor='w', pady=12)
        self.amount = tk.StringVar()
        ttk.Entry(bid, textvariable=self.amount, width=15).pack(side='left')
        self.submit_button = ttk.Button(bid, text='送出／修改出價', command=self.submit, state='disabled')
        self.submit_button.pack(side='left', padx=8)
        self.bid_status = tk.StringVar(value='尚未出價')
        ttk.Label(auction, textvariable=self.bid_status).pack(anchor='w')
        bottom = ttk.Frame(body)
        bottom.pack(fill='both', expand=True)
        team = ttk.LabelFrame(bottom, text='我的隊伍', padding=8)
        team.pack(side='left', fill='both', expand=True)
        summary = ttk.LabelFrame(bottom, text='公開教練資訊', padding=8)
        summary.pack(side='left', fill='both', expand=True, padx=(12,0))
        self.team = ttk.Treeview(team, columns=('player',), show='headings', height=8)
        self.team.heading('player', text='已獲得選手')
        self.team.pack(fill='both', expand=True)
        self.summary = ttk.Treeview(summary, columns=('name','budget','count'), show='headings', height=8)
        for key, title in (('name','教練'),('budget','剩餘預算'),('count','隊伍人數')):
            self.summary.heading(key, text=title)
            self.summary.column(key, width=110)
        self.summary.pack(fill='both', expand=True)
        self.message = tk.StringVar()
        ttk.Label(body, textvariable=self.message, wraplength=950).pack(anchor='w', pady=12)
        self._rendered = None
        root.after(50, self.poll)

    def connect(self):
        if self.transport is not None:
            return
        transport = ClientTransport()
        try:
            credentials = Credentials(self.url.get().strip(), 'coach', self.coach_id.get().strip(), self.token.get())
            transport.connect(credentials)
        except (ValueError, RuntimeError):
            self.message.set('請確認 URL、教練 ID 與 Token 已填寫。')
            return
        self.model = CoachViewModel()
        self._rendered = None
        self.transport = transport
        self.token.set('')
        self.connect_button.configure(state='disabled')
        self.disconnect_button.configure(state='normal')

    def disconnect(self):
        if self.transport:
            self.transport.disconnect()

    def submit(self):
        if not self.transport or not self.model.bid_enabled:
            return
        try:
            amount = parse_amount(self.amount.get())
        except ValueError as error:
            self.model.message = str(error)
            return
        self.transport.send_command('submit_bid', round_id=self.model.snapshot['round_id'], amount=amount)
        self.model.message = '送出中，等待 Server 確認…'

    def poll(self):
        if self.transport:
            # Bound work per UI tick so a busy inbound queue cannot freeze widgets.
            for _ in range(100):
                try:
                    self.model.handle(self.transport.events.get_nowait())
                except Empty:
                    break
            if self.transport.join(0):
                self.transport = None
                self.connect_button.configure(state='normal')
                self.disconnect_button.configure(state='disabled')
        if self.closing:
            if self.transport is None:
                self.root.destroy()
                return
        self.render()
        self.root.after(50, self.poll)

    def render(self):
        connection = {'offline':'離線','connecting':'連線中','reconnecting':'重連中','connected':'已連線'}
        s = self.model.snapshot or {}
        coach = s.get('coach', {})
        self.connection.set(f"{connection.get(self.model.connection, '離線')} · {coach.get('name','')} {coach.get('id','')}")
        status = {'idle':'等待','running':'競標中','paused':'競標暫停','ended':'已結束'}
        text = f"選手：{s.get('current_player') or '—'}\n狀態：{status.get(s.get('status'),'等待')}\n倒數：{self.model.countdown} 秒\nMinimum Bid：{s.get('minimum_bid',0)}"
        if s.get('status') == 'ended':
            text += f"\n得標：{s.get('winner') or '無'} · 成交價：{s.get('winning_amount')}"
        self.auction_text.set(text)
        rules = s.get('bidRules', {})
        cid = coach.get('id')
        own_team = s.get('teams', {}).get(cid, [])
        self.rules_text.set(f"剩餘預算：{s.get('budgets',{}).get(cid,'—')}\n合法出價：{rules.get('min_bid','—')} ～ {rules.get('max_bid','—')}\n後續名額預留：{rules.get('reserve_for_remaining','—')}\n隊伍人數：{len(own_team)} / 5\nZone 限制：{'已達上限' if rules.get('zone_limit_reached') else '依 Server 判定'}")
        self.bid_status.set(self.model.bid_text)
        self.message.set(self.model.message)
        self.submit_button.configure(state='normal' if self.model.bid_enabled and not self.closing else 'disabled')
        if self._rendered != s:
            self.team.delete(*self.team.get_children())
            for player in own_team:
                self.team.insert('', 'end', values=(player,))
            self.summary.delete(*self.summary.get_children())
            for c in s.get('coaches', []):
                self.summary.insert('', 'end', values=(c['name'],s.get('budgets',{}).get(c['id'],0),len(s.get('teams',{}).get(c['id'],[]))))
            self._rendered = s

    def close(self):
        self.closing = True
        self.disconnect()


def main():
    root = tk.Tk()
    CoachApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
