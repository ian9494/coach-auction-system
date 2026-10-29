"""Tkinter Admin client, sharing the Coach transport and authority protocol."""
from queue import Empty
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .transport import ClientTransport, Credentials, ConnectionChanged, SnapshotReceived, HttpDataReceived, TransportError
from .admin_viewmodel import AdminViewModel
from .results_export import export_results


class AdminApp:
    def __init__(self, root, confirm=None):
        self.root, self.confirm = root, confirm or messagebox.askyesno
        self.transport = None
        self.model = AdminViewModel()
        self.closing = False
        self._members_signature = None
        self._rendered = None
        self._export_requested = False
        root.title('期末專題 · Admin 競標管理')
        root.geometry('1150x800')
        root.minsize(1000,700)
        root.protocol('WM_DELETE_WINDOW', self.close)
        body = ttk.Frame(root,padding=12)
        body.pack(fill='both',expand=True)
        login = ttk.LabelFrame(body,text='Admin 登入',padding=8)
        login.pack(fill='x')
        self.url = tk.StringVar(value='http://127.0.0.1:3001')
        self.token = tk.StringVar()
        ttk.Label(login,text='Server URL').pack(side='left')
        ttk.Entry(login,textvariable=self.url,width=32).pack(side='left',padx=8)
        ttk.Label(login,text='Admin Token').pack(side='left')
        ttk.Entry(login,textvariable=self.token,show='*',width=28).pack(side='left',padx=8)
        self.connect_button = ttk.Button(login,text='連線',command=self.connect)
        self.connect_button.pack(side='left')
        self.disconnect_button = ttk.Button(login,text='離線',command=self.disconnect,state='disabled')
        self.disconnect_button.pack(side='left',padx=8)
        self.connection = tk.StringVar(value='離線')
        ttk.Label(body,textvariable=self.connection).pack(anchor='w',pady=6)
        middle = ttk.Frame(body)
        middle.pack(fill='both',expand=True)
        control = ttk.LabelFrame(middle,text='競標控制',padding=10)
        control.pack(side='left',fill='y')
        auction = ttk.LabelFrame(middle,text='目前競標',padding=10)
        auction.pack(side='left',fill='both',expand=True,padx=8)
        monitor = ttk.LabelFrame(middle,text='全部教練出價監看',padding=8)
        monitor.pack(side='left',fill='both',expand=True)
        self.player = tk.StringVar()
        self.player_box = ttk.Combobox(control,textvariable=self.player,state='readonly',width=22)
        self.player_box.pack(fill='x')
        self.refresh_button = ttk.Button(control,text='重新整理選手',command=self.refresh_members,state='disabled')
        self.refresh_button.pack(fill='x',pady=4)
        self.duration = tk.StringVar(value='90')
        ttk.Label(control,text='競標秒數（1～86400）').pack(anchor='w')
        ttk.Entry(control,textvariable=self.duration,width=12).pack(fill='x')
        self.buttons = {}
        for event,label in (('start_auction','開始競標'),('pause_auction','暫停'),('resume_auction','繼續'),('end_auction','強制結算')):
            button = ttk.Button(control,text=label,command=lambda e=event:self.command(e),state='disabled')
            button.pack(fill='x',pady=4)
            self.buttons[event] = button
        self.minimum = tk.StringVar(value='0')
        self.budget = tk.StringVar(value='100')
        for event,label,value in (('set_minimum_bid','套用 Minimum Bid',self.minimum),('add_all_budgets','全體增加預算',self.budget)):
            ttk.Entry(control,textvariable=value,width=12).pack(fill='x',pady=(8,0))
            button = ttk.Button(control,text=label,command=lambda e=event:self.command(e),state='disabled')
            button.pack(fill='x',pady=4)
            self.buttons[event] = button
        undo = ttk.Button(control,text='撤銷上一筆得標',command=lambda:self.command('undo_last_award'),state='disabled')
        undo.pack(fill='x',pady=8)
        self.buttons['undo_last_award'] = undo
        ttk.Label(control,text='Reset／匯入：留待後續階段').pack(anchor='w')
        self.auction_text = tk.StringVar(value='等待 Server 資訊')
        ttk.Label(auction,textvariable=self.auction_text,justify='left',wraplength=240,font=('',11)).pack(anchor='w')
        self.bids = ttk.Treeview(monitor,columns=('coach','bid','budget','count','status'),show='headings',height=10)
        for key,title,width in (('coach','教練',85),('bid','出價',55),('budget','預算',65),('count','人數',45),('status','規則狀態',100)):
            self.bids.heading(key,text=title)
            self.bids.column(key,width=width)
        self.bids.pack(fill='both',expand=True)
        teams = ttk.LabelFrame(body,text='隊伍／結果摘要',padding=8)
        teams.pack(fill='both',expand=True,pady=8)
        self.teams = ttk.Treeview(teams,columns=('coach','players','budget','count'),show='headings',height=5)
        for key,title,width in (('coach','教練',120),('players','已得標玩家',550),('budget','剩餘預算',120),('count','人數',80)):
            self.teams.heading(key,text=title)
            self.teams.column(key,width=width)
        self.teams.pack(fill='both',expand=True)
        self.export_button = ttk.Button(body,text='匯出 Server 結果 CSV',command=self.request_export,state='disabled')
        self.export_button.pack(anchor='w')
        self.message = tk.StringVar()
        ttk.Label(body,textvariable=self.message,wraplength=1080).pack(anchor='w',pady=8)
        root.after(50,self.poll)

    def connect(self):
        if self.transport: return
        transport = ClientTransport()
        try:
            transport.connect(Credentials(self.url.get().strip(),'admin',token=self.token.get()))
        except (ValueError,RuntimeError):
            self.message.set('請確認 URL 與 Admin Token。')
            return
        self.model = AdminViewModel()
        self._members_signature = self._rendered = None
        self.transport = transport
        self.token.set('')
        self.connect_button.configure(state='disabled')
        self.disconnect_button.configure(state='normal')

    def disconnect(self):
        if self.transport: self.transport.disconnect()

    def refresh_members(self):
        if self.transport: self.transport.fetch('members')

    def command(self,event):
        if not self.transport: return
        value = self.player.get() if event == 'start_auction' else self.minimum.get() if event == 'set_minimum_bid' else self.budget.get()
        try:
            payload = self.model.payload(event,value,self.duration.get())
        except ValueError as error:
            self.model.message = str(error)
            return
        question = None
        if event == 'end_auction' and self.model.countdown > 0:
            question = '競標尚有時間，確定立即強制結算？'
        elif event == 'add_all_budgets':
            question = f"確定要為所有教練增加 {payload['amount']} 預算嗎？"
        elif event == 'undo_last_award':
            question = '確定撤銷上一筆得標？預算與隊伍將恢復。'
        if question and not self.confirm('確認 Admin 操作',question,parent=self.root): return
        request_id = self.transport.send_command(event,**payload)
        self.model.mark_pending(request_id,event)
        self.render()

    def request_export(self):
        if self.transport and not self._export_requested:
            self._export_requested = self.transport.fetch('results')

    def _save_export(self,results):
        path = filedialog.asksaveasfilename(parent=self.root,title='匯出競標結果',defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if not path: return
        try:
            export_results(path,results)
            self.model.message = 'CSV 結果已匯出。'
        except (OSError,ValueError):
            self.model.message = '無法匯出 CSV，請確認資料與存檔位置。'

    def poll(self):
        if self.transport:
            for _ in range(100):
                try: event = self.transport.events.get_nowait()
                except Empty: break
                self.model.handle(event)
                if isinstance(event,ConnectionChanged):
                    if event.state == 'connected': self.refresh_members()
                    else: self._export_requested = False
                if isinstance(event,SnapshotReceived) and self.model.snapshot:
                    signature = tuple((cid,tuple(players)) for cid,players in self.model.snapshot.get('teams',{}).items())
                    if signature != self._members_signature:
                        self._members_signature = signature
                        self.refresh_members()
                if isinstance(event,HttpDataReceived) and event.resource == 'results' and self._export_requested:
                    self._export_requested = False
                    if not self.closing: self._save_export(event.data)
                if isinstance(event,TransportError) and event.code == 'HTTP_FAILED': self._export_requested = False
            if self.transport.join(0):
                self.transport = None
                self.connect_button.configure(state='normal')
                self.disconnect_button.configure(state='disabled')
        if self.closing and self.transport is None:
            self.root.destroy()
            return
        self.render()
        self.root.after(50,self.poll)

    def render(self):
        s = self.model.snapshot or {}
        state = {'connected':'已連線','connecting':'連線中','reconnecting':'重連中','offline':'離線'}.get(self.model.connection,'離線')
        self.connection.set(f"Admin · {state} · version {self.model.latest_version} · round {s.get('round_id') or '—'}")
        status = {'idle':'等待','running':'競標中','paused':'暫停','ended':'已結束'}.get(s.get('status'),'等待')
        self.auction_text.set(f"選手：{s.get('current_player') or '—'}\n狀態：{status}\n倒數：{self.model.countdown} 秒\nMinimum Bid：{s.get('minimum_bid',0)}\n得標：{s.get('winner') or '—'}\n成交價：{s.get('winning_amount') if s.get('winning_amount') is not None else '—'}")
        for event,button in self.buttons.items():
            button.configure(state='normal' if self.model.enabled(event) and not self.closing else 'disabled')
        ready = self.model.connection == 'connected' and not self.closing
        self.refresh_button.configure(state='normal' if ready else 'disabled')
        self.export_button.configure(state='normal' if ready and not self._export_requested else 'disabled')
        self.player_box.configure(values=self.model.available_players)
        if self.player.get() not in self.model.available_players: self.player.set('')
        self.message.set(self.model.message)
        if self._rendered != s:
            self.bids.delete(*self.bids.get_children())
            self.teams.delete(*self.teams.get_children())
            for cid,name,bid,budget,count,rule in self.model.bid_rows:
                self.bids.insert('','end',iid=cid,values=(name,bid,budget,count,rule))
                self.teams.insert('','end',values=(name,'、'.join(s.get('teams',{}).get(cid,[])),budget,count))
            self._rendered = s

    def close(self):
        self.closing = True
        self.disconnect()


def main(argv=None):
    import argparse
    import os
    parser = argparse.ArgumentParser(description='Auction GUI login prefill')
    parser.add_argument('--server', default='http://127.0.0.1:3001')
    parser.add_argument('--admin-token')
    args = parser.parse_args(argv)
    root = tk.Tk()
    app = AdminApp(root)
    app.url.set(args.server)
    app.token.set(args.admin_token if args.admin_token is not None else
                  os.environ.get('FINAL_PROJECT_ADMIN_TOKEN', ''))
    root.mainloop()


if __name__ == '__main__':
    main()
