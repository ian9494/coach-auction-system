# Client / Server 訊息循序

join ACK 的 `payload.snapshot` 與角色 state event 都提供完整 snapshot；所有 mutation ACK 包含 ok、error_code、version、round_id、request_id、payload。broadcast worker 與 ACK 發送順序不保證，Client 同時處理兩者，不依賴 ACK 先到。

## Coach 登入

```mermaid
sequenceDiagram
  participant C as Coach GUI
  participant T as Socket.IO Server
  C->>T: Engine.IO / Socket.IO connect
  C->>T: join_coach {username, password}
  T->>T: 驗證帳號 hash / DB 決定 Coach 身份 / enter coach room
  T-->>C: coach_state (完整自己的 projection)
  T-->>C: ACK {ok, payload.snapshot}
```

## 開始競標

```mermaid
sequenceDiagram
  participant A as Admin
  participant T as Server
  participant S as AuctionService
  participant DB as SQLite
  participant C as Admin / Coach / Viewer
  A->>T: start_auction {request_id, playerName, duration}
  T->>S: authenticated START command
  S->>S: roster / sold 驗證、transition、new round / deadline
  S->>DB: atomic snapshot + processed ACK commit
  S-->>T: command result / publish snapshot
  par independent delivery
    T-->>A: ACK
  and role broadcast
    T-->>C: admin_state / coach_state / viewer_state
  end
```

## 出價／修改出價

```mermaid
sequenceDiagram
  participant C as Coach
  participant T as Server
  participant S as AuctionService
  participant DB as SQLite
  C->>T: submit_bid {request_id, round_id, amount}
  T->>S: coach identity from session (not client-supplied)
  S->>S: dedup / current round / running / budget / zone / minimum
  alt 合法
    S->>DB: snapshot + ACK commit
    S-->>T: result / snapshot
    T-->>C: ACK and coach_state (myBid)
    T-->>T: broadcast Admin allBids / Viewer public fields
  else 不合法
    S-->>T: error ACK (不改競標 state)
    T-->>C: {ok:false, error_code}
  end
```

## 結算

```mermaid
sequenceDiagram
  participant A as Timer / Admin
  participant S as AuctionService
  participant DB as SQLite
  participant T as Server
  participant C as Clients
  A->>S: timeout or authenticated end_auction command
  S->>S: serialized end / validate bids / tie RNG / award
  S->>DB: atomic history + budget + team + ACK
  S-->>T: publish ended snapshot
  T-->>C: role state with public result
```

Admin 路徑先經 Transport 驗證 `request_id`／`round_id`，收到 ACK；timer 是 Server 內部命令。Viewer 倒數達 0 不自行推測 winner。

## 斷線／重連

```mermaid
sequenceDiagram
  participant C as Coach
  participant T as Server
  C-xT: disconnect / network loss
  T->>T: transport close or heartbeat timeout; clear SID session
  C->>C: GUI offline; retain last snapshot; discard uncertain queued actions
  C->>T: reconnect (new SID)
  C->>T: join_coach {username, password}
  T-->>C: latest coach_state and join ACK snapshot
  C->>C: version guard; restore myBid / remaining / team / budget
```

Viewer 以 `join_viewer {}` 重連；Admin 用 `join_admin {token}`。正常登出不一定自動重連；非預期中斷 worker 自動重試。Server 不暫停競標等待掉線者。

## Coach 席位註冊

```mermaid
sequenceDiagram
  participant C as Coach GUI background worker
  participant T as Socket.IO Server
  participant A as AccountStore
  participant DB as Project SQLite
  C->>T: connect (anonymous)
  C->>T: register_coach {coachId, invite, username, password}
  T->>T: validate invite / input / anonymous session
  T->>A: register account and claim configured seat
  A->>A: random salt / scrypt in worker thread
  A->>DB: INSERT username + UNIQUE coach_id + salt + hash
  DB-->>A: atomic commit or uniqueness conflict
  A-->>T: registered or error
  T->>T: disconnect previous token sessions for this seat
  T-->>C: ACK (no password, no automatic role join)
  C->>T: disconnect registration connection
  C->>T: new connect + join_coach {username,password}
  T-->>C: authenticated coach_state + ACK snapshot
```

未認領席位可相容舊 token 登入；認領後失效。錯誤或 ACK 遺失的處理見 [註冊文件](FINAL_PROJECT_REGISTRATION.md)。
