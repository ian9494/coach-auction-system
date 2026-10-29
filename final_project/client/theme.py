"""Quiet desktop theme with a restrained green accent, entirely offline."""
import tkinter as tk
from tkinter import ttk

PAPER = '#f2f6ec'
INK = '#0d140d'
ACID = '#287344'
LIME = '#e1eddd'
GOLD = '#c5ddc0'
MUTED = '#5a6b58'
FONT = 'Microsoft JhengHei UI'


class Card(ttk.LabelFrame):
    """Lightweight section: whitespace and a subtle divider, without shadows."""


class LoginPanel(ttk.Frame):
    """Collapse login fields after connecting; keep settings reachable."""
    def __init__(self, parent, text):
        super().__init__(parent)
        self.connected = False
        self.expanded = True
        self.toggle = ttk.Button(self, text='收起登入設定', command=self.toggle_fields)
        self.toggle.pack(anchor='e', pady=(0, 4))
        self.content = Card(self, text=text, padding=10)
        self.content.pack(fill='x', pady=(0, 8))

    def toggle_fields(self):
        self.expanded = not self.expanded
        if self.expanded:
            self.content.pack(fill='x', pady=(0, 8))
        else:
            self.content.pack_forget()
        self.toggle.configure(text='收起登入設定' if self.expanded else '展開登入設定')

    def set_connected(self, connected):
        if connected != self.connected:
            self.connected = connected
            if self.expanded == connected:
                self.toggle_fields()


def create_body(root, padding=16):
    """Keep controls reachable on laptop screens and at enlarged display scales."""
    shell = ttk.Frame(root)
    shell.pack(fill='both', expand=True)
    canvas = tk.Canvas(shell, background=PAPER, highlightthickness=0)
    scrollbar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    body = ttk.Frame(canvas, padding=padding)
    window = canvas.create_window(0, 0, window=body, anchor='nw')
    def resize(_event=None):
        canvas.itemconfigure(window, width=canvas.winfo_width(),
                             height=max(body.winfo_reqheight(), canvas.winfo_height()))
        canvas.configure(scrollregion=canvas.bbox('all'))
    canvas.bind('<Configure>', resize)
    body.bind('<Configure>', resize)
    def wheel(event):
        if not isinstance(event.widget, (ttk.Treeview, ttk.Combobox)):
            canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
    root.bind('<MouseWheel>', wheel, add='+')
    return body


def create_header(parent, title, subtitle):
    header = ttk.Frame(parent, padding=(0, 4, 0, 12))
    header.pack(fill='x')
    options = {'textvariable': title} if isinstance(title, tk.Variable) else {'text': title}
    ttk.Label(header, style='Title.TLabel', **options).pack(anchor='w')
    ttk.Label(header, text=subtitle, style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
    return header


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    root.configure(background=PAPER)
    style.configure('.', font=(FONT, 10), background=PAPER, foreground=INK)
    style.configure('TFrame', background=PAPER)
    style.configure('TLabelframe', background=PAPER, bordercolor=INK,
                    lightcolor=PAPER, darkcolor=PAPER, borderwidth=0, relief='flat')
    style.configure('TLabelframe.Label', font=(FONT, 11, 'bold'), foreground=INK)
    style.configure('TLabel', background=PAPER)
    style.configure('TEntry', fieldbackground='white', foreground=INK, bordercolor='#b8c4b4',
                    lightcolor='#b8c4b4', darkcolor='#b8c4b4', padding=5)
    style.map('TEntry', bordercolor=[('focus', ACID)],
              fieldbackground=[('disabled', '#e3e8dd')])
    style.configure('TCombobox', fieldbackground='white', foreground=INK, arrowcolor=INK,
                    bordercolor='#b8c4b4', padding=4)
    style.map('TCombobox', fieldbackground=[('readonly', 'white')],
              foreground=[('readonly', INK)], selectbackground=[('readonly', ACID)],
              selectforeground=[('readonly', INK)])
    style.configure('TButton', padding=(12, 7), background='white', foreground=INK,
                    bordercolor='#c8d2c3', lightcolor='#c8d2c3', darkcolor='#c8d2c3', borderwidth=1,
                    font=(FONT, 10, 'bold'), focusthickness=2, focuscolor=INK)
    style.map('TButton', background=[('disabled', '#e3e8dd'), ('pressed', GOLD), ('active', LIME)],
              foreground=[('disabled', '#737d6e')], bordercolor=[('focus', ACID)])
    style.configure('Primary.TButton', background=ACID, foreground='white')
    style.map('Primary.TButton', background=[('disabled', '#e3e8dd'), ('pressed', '#205c37'), ('active', '#348451')],
              foreground=[('disabled', '#737d6e'), ('!disabled', 'white')])
    style.configure('Danger.TButton', foreground='#9d2436', background='#fff0ed')
    style.map('Danger.TButton', background=[('disabled', '#e3e8dd'), ('active', '#ffd8d0')],
              foreground=[('disabled', '#737d6e')])
    style.configure('TNotebook', background=PAPER, borderwidth=0)
    style.configure('TNotebook.Tab', padding=(12, 7), background='#e3e8dd', bordercolor=INK)
    style.map('TNotebook.Tab', background=[('selected', LIME), ('active', '#eaf0e6')],
              foreground=[('selected', INK)])
    style.configure('Title.TLabel', font=(FONT, 20, 'bold'))
    style.configure('Hero.TLabel', font=(FONT, 16, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Online.TLabel', foreground='#24631c', font=(FONT, 11, 'bold'))
    style.configure('Offline.TLabel', foreground='#805222', font=(FONT, 11, 'bold'))
    style.configure('Treeview', rowheight=30, background='white', fieldbackground='white',
                    foreground=INK, bordercolor='#d8dfd3', lightcolor='#d8dfd3', darkcolor='#d8dfd3')
    style.configure('Treeview.Heading', font=(FONT, 10, 'bold'), padding=7,
                    background='#e7ece2', foreground=MUTED, bordercolor='#d8dfd3')
    style.map('Treeview', background=[('selected', LIME)], foreground=[('selected', INK)])
    return style
