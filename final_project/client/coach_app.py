"""Tkinter Coach desktop client. All widgets live exclusively on the main thread."""
from queue import Empty
import tkinter as tk
from tkinter import ttk

from .transport import ClientTransport, Credentials
from .coach_viewmodel import CoachViewModel, parse_amount
from .registration import RegistrationWorker
from .theme import apply_theme, Card, LoginPanel, create_header, create_body
from final_project.storage.accounts import valid_account


class CoachApp:
    def __init__(self, root):
        self.root = root
        self.transport = None
        self.model = CoachViewModel()
        self.closing = False
        self.registration = None
        apply_theme(root)
        root.title('期末專題 · Coach 競標客戶端')
        root.geometry('1100x760')
        root.minsize(1000, 720)
        root.protocol('WM_DELETE_WINDOW', self.close)
        body = create_body(root, padding=16)
        self.identity = tk.StringVar(value='Coach01 · 教練席位')
        create_header(body, self.identity, 'COACH AUCTION  /  登入後即可出價 · 註冊帳號會綁定教練席位')
        self.login_panel = LoginPanel(body, '連線與帳號')
        self.login_panel.pack(fill='x')
        login = self.login_panel.content
        self.url = tk.StringVar(value='http://127.0.0.1:3001')
        self.coach_id = tk.StringVar(value='coach01')
        self.token = tk.StringVar()
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.confirm_password = tk.StringVar()
        server = ttk.Frame(login)
        server.pack(fill='x', pady=(0,8))
        ttk.Label(server, text='Server URL').pack(side='left')
        ttk.Entry(server, textvariable=self.url, width=40).pack(side='left', padx=10)
        self.auth_tabs = ttk.Notebook(login)
        self.auth_tabs.pack(fill='x')
        self.login_tab = ttk.Frame(self.auth_tabs, padding=10)
        self.registration_tab = ttk.Frame(self.auth_tabs, padding=10)
        self.token_tab = ttk.Frame(self.auth_tabs, padding=10)
        self.auth_tabs.add(self.login_tab, text='帳密登入')
        self.auth_tabs.add(self.registration_tab, text='首次註冊')
        self.auth_tabs.add(self.token_tab, text='快速 Demo（未註冊席位）')
        def fields(frame, items):
            for column, (label, variable, secret) in enumerate(items):
                ttk.Label(frame, text=label).grid(row=0, column=column, sticky='w', padx=5)
                ttk.Entry(frame, textvariable=variable, show='*' if secret else '', width=23).grid(row=1, column=column, sticky='ew', padx=5, pady=5)
                frame.columnconfigure(column, weight=1)
        fields(self.login_tab, [('帳號',self.username,False), ('密碼',self.password,True)])
        ttk.Label(self.login_tab, text='已註冊的帳號只需帳密；席位由 Server 判定。', style='Muted.TLabel').grid(row=2,column=0,columnspan=2,sticky='w',padx=5)
        fields(self.registration_tab, [('Coach ID',self.coach_id,False), ('席位邀請碼',self.token,True), ('帳號',self.username,False)])
        for column, (label, variable) in enumerate([('密碼', self.password), ('確認密碼', self.confirm_password)]):
            ttk.Label(self.registration_tab, text=label).grid(row=2,column=column,sticky='w',padx=5)
            ttk.Entry(self.registration_tab,textvariable=variable,show='*',width=23).grid(row=3,column=column,sticky='ew',padx=5,pady=5)
        self.register_button = ttk.Button(self.registration_tab, text='註冊教練席位', command=self.register_account, style='Primary.TButton')
        self.register_button.grid(row=3,column=2,padx=5,pady=5,sticky='ew')
        ttk.Label(self.registration_tab, text='帳號 4–32 位英數／底線；密碼 10–128 字元。註冊成功後切回帳密登入。', style='Muted.TLabel').grid(row=4,column=0,columnspan=3,sticky='w',padx=5)
        fields(self.token_tab, [('Coach ID',self.coach_id,False), ('邀請碼／舊 Token',self.token,True)])
        ttk.Label(self.token_tab, text='僅限未註冊席位；使用此方式時，帳密登入分頁的帳號需留空。', style='Muted.TLabel').grid(row=2,column=0,columnspan=2,sticky='w',padx=5)
        actions = ttk.Frame(login)
        actions.pack(fill='x', pady=(10,0))
        self.connect_button = ttk.Button(actions, text='登入', command=self.connect, style='Primary.TButton')
        self.connect_button.pack(side='left')
        self.disconnect_button = ttk.Button(actions, text='離線', command=self.disconnect, state='disabled')
        self.disconnect_button.pack(side='left', padx=8)
        self.connection = tk.StringVar(value='離線')
        self.connection_label = ttk.Label(body, textvariable=self.connection, style='Offline.TLabel')
        self.connection_label.pack(anchor='w', pady=(4, 8))
        def update_seat(*_):
            if self.model.connection != 'connected':
                seat = self.coach_id.get().upper()
                root.title(f'{seat} · 教練競標')
                self.identity.set(f'{seat} · 教練席位')
        self.coach_id.trace_add('write', update_seat)
        update_seat()
        middle = ttk.Frame(body)
        middle.pack(fill='x', pady=12)
        auction = Card(middle, text='當前競標', padding=12)
        auction.pack(side='left', fill='both', expand=True)
        info = Card(middle, text='我的預算與規則', padding=12)
        info.pack(side='left', fill='both', expand=True, padx=(12,0))
        self.auction_text = tk.StringVar(value='等待競標資訊')
        self.rules_text = tk.StringVar(value='登入後取得資訊')
        ttk.Label(auction, textvariable=self.auction_text, justify='left', style='Hero.TLabel').pack(anchor='w')
        ttk.Label(info, textvariable=self.rules_text, justify='left').pack(anchor='w')
        bid = ttk.Frame(auction)
        bid.pack(anchor='w', pady=12)
        self.amount = tk.StringVar()
        ttk.Entry(bid, textvariable=self.amount, width=15).pack(side='left')
        self.submit_button = ttk.Button(bid, text='送出／修改出價', command=self.submit, state='disabled', style='Primary.TButton')
        self.submit_button.pack(side='left', padx=8)
        self.bid_status = tk.StringVar(value='尚未出價')
        ttk.Label(auction, textvariable=self.bid_status).pack(anchor='w')
        bottom = ttk.Frame(body)
        bottom.pack(fill='both', expand=True)
        team = Card(bottom, text='我的隊伍', padding=8)
        team.pack(side='left', fill='both', expand=True)
        summary = Card(bottom, text='公開教練資訊', padding=8)
        summary.pack(side='left', fill='both', expand=True, padx=(12,0))
        self.team = ttk.Treeview(team, columns=('player',), show='headings', height=4)
        self.team.heading('player', text='已獲得選手')
        self.team.pack(fill='both', expand=True)
        self.summary = ttk.Treeview(summary, columns=('name','budget','count'), show='headings', height=4)
        for key, title in (('name','教練'),('budget','剩餘預算'),('count','隊伍人數')):
            self.summary.heading(key, text=title)
            self.summary.column(key, width=110)
        self.summary.pack(fill='both', expand=True)
        self.message = tk.StringVar()
        ttk.Label(body, textvariable=self.message, wraplength=950).pack(anchor='w', pady=12)
        self._rendered = None
        root.after(50, self.poll)

    def connect(self):
        if self.transport is not None or self.registration is not None:
            return
        transport = ClientTransport()
        try:
            username = self.username.get().strip()
            if username and not valid_account(username, self.password.get()):
                raise ValueError('INVALID_ACCOUNT')
            credentials = Credentials(self.url.get().strip(), 'coach', self.coach_id.get().strip(), self.token.get(),
                                      username, self.password.get())
            transport.connect(credentials)
        except (ValueError, RuntimeError):
            self.message.set('請確認 URL、帳號密碼，或未註冊席位的教練 ID 與 Token。')
            return
        self.model = CoachViewModel()
        self._rendered = None
        self.transport = transport
        self.token.set('')
        self.password.set('')
        self.confirm_password.set('')
        self.register_button.configure(state='disabled')
        self.connect_button.configure(state='disabled')
        self.disconnect_button.configure(state='normal')

    def register_account(self):
        if self.transport is not None or self.registration is not None: return
        username, password = self.username.get().strip(), self.password.get()
        if not valid_account(username, password) or password != self.confirm_password.get():
            self.model.message = '請確認帳號格式、密碼長度及兩次密碼一致。'
            return
        try:
            worker = RegistrationWorker(self.url.get().strip(), self.coach_id.get().strip(), self.token.get(), username, password)
            worker.start()
        except (ValueError, RuntimeError):
            self.model.message = '請確認 Server URL。'
            return
        self.registration = worker
        self.register_button.configure(state='disabled')
        self.connect_button.configure(state='disabled')
        self.model.message = '註冊中，等待 Server 確認…'

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
        if self.registration is not None:
            try:
                result = self.registration.events.get_nowait()
            except Empty:
                pass
            else:
                self.registration = None
                self.connect_button.configure(state='normal')
                self.register_button.configure(state='normal')
                messages = {'INVALID_INVITE':'邀請碼錯誤，請確認教練席位。',
                    'ACCOUNT_OR_SEAT_TAKEN':'帳號或席位已被註冊，請登入或聯絡管理員。',
                    'INVALID_ACCOUNT':'帳號或密碼格式不正確。',
                    'REGISTRATION_UNCONFIRMED':'未確認註冊結果；請先嘗試登入，不自動重送註冊。'}
                self.model.message = '註冊完成，請按登入。' if result.get('ok') else messages.get(result.get('error_code'), '註冊失敗，請確認 Server。')
                if result.get('ok'):
                    self.auth_tabs.select(self.login_tab)
                    self.token.set('')
                    self.confirm_password.set('')
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
                self.register_button.configure(state='normal')
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
        self.login_panel.set_connected(self.model.connection == 'connected')
        self.connection_label.configure(style='Online.TLabel' if self.model.connection == 'connected' else 'Offline.TLabel')
        if coach.get('id') and self.model.connection == 'connected':
            title = f"{coach['id'].upper()} · {coach.get('name', '')}"
            self.identity.set(title)
            self.root.title(title + ' · 教練競標')
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


def main(argv=None):
    import argparse
    import os
    parser = argparse.ArgumentParser(description='Auction GUI login prefill')
    parser.add_argument('--server', default='http://127.0.0.1:3001')
    parser.add_argument('--coach-id', default='coach01')
    parser.add_argument('--token')
    args = parser.parse_args(argv)
    root = tk.Tk()
    app = CoachApp(root)
    app.url.set(args.server)
    app.coach_id.set(args.coach_id)
    app.token.set(args.token if args.token is not None else os.environ.get(
        'FINAL_PROJECT_COACH_TOKEN_' + args.coach_id.upper(), ''))
    root.mainloop()


if __name__ == '__main__':
    main()
