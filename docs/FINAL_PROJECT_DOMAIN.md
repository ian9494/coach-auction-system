# Phase 1 Domain

`models.py` 定義 AuctionStatus、Coach、Player、Zone、Bid、Award、UndoAward、AuctionState。
金額使用真正 int；bid None / 0 分開。State 使用 instance-owned maps，沒有 global mutable state。
State 是可控 mutable dataclass，但 public transitions deepcopy 後回傳新 state；caller 不應自行修改 model 繞過命令驗證。

`rules.py` 是純函式：zone / 人數 / 花費、min / max bid、錯誤分類、prune / auto minimum、winner selection。
`transitions.py` 提供 start、pause、resume、submit、set minimum、end、undo。
命令拒絕時拋 DomainError(code)，原 state 不變；重複 end 對 ended state 不抽籤、不呼叫 clock、不扣款。
end 以 caller 提供的 `rng: () -> float [0,1)` 與 `clock: () -> str` 決定 winner / history time。
不實作即時倒數；同一舊 running snapshot 不能由多個 caller 各自提交，Phase 2 service 要序列化並持久化權威 state。

## 使用與驗證

```python
from final_project.domain.models import AuctionState, Coach, Player
from final_project.domain.transitions import start_auction, submit_bid, end_auction

state = AuctionState((Coach("coach01", "Coach01"),), (Player("Player01"),))
state = start_auction(state, "Player01")
state = submit_bid(state, "coach01", 200)
state = end_auction(state, rng=lambda: 0.0, clock=lambda: "TEST_CLOCK")
```

```powershell
python -m pytest -q
node scripts/legacy_parity.cjs
```

pytest 是唯一 dev dependency，沒有 Phase 2 網路 dependencies。本次驗證使用 `.venv/Scripts/python.exe -m pytest -q`。
Node harness 讀 server.js 與 demo fixture，按欄首 function / closing brace 擷取白名單函式；格式改變會報 extraction error。
VM 沒有 require / process / network / fs，timer / disk / broadcast 是 stub；不載入 server entrypoint。
這是本 repo 受控測試基準，不是執行不可信程式的安全 sandbox，也不是新系統 source of truth。
fixture adapter 屬測試層，負責 legacy camelCase JSON 與 Python typed model 映射；domain 本身不讀 CSV / JSON。

## Phase 2 責任

transport、角色 auth、room projections、ACK / request ID、命令順序、實際 deadline、restart、reset、SQLite / CSV 均留到 Phase 2。
Python domain 沒有 server listener、GUI、持久化 I/O 或 network side effects。
課程 raw TCP requirement 尚未確認；預設仍可使用 python-socketio，必要時 Phase 2 增加 TCP adapter。
