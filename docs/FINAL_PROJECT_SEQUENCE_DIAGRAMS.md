# Client / Server 訊息循序

join ACK 的 `payload.snapshot` 與角色 state event 都提供完整 snapshot；所有 mutation ACK 包含 ok、error_code、version、round_id、request_id、payload。broadcast worker 與 ACK 發送順序不保證，Client 同時處理兩者，不依賴 ACK 先到。

## Coach 登入

```mermaid
sequenceDiagram
  participant C as Coach GUI
  participant T as Socket.IO Server
  C->>T: Engine.IO / Socket.IO connect
  C->>T: join_coach {coachId, token}
  T->>T: 驗證 token / 固定 SID 身份 / enter coach room
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
  C->>T: join_coach {coachId, token}
  T-->>C: latest coach_state and join ACK snapshot
  C->>C: version guard; restore myBid / remaining / team / budget
```

Viewer 以 `join_viewer {}` 重連；Admin 用 `join_admin {token}`。正常登出不一定自動重連；非預期中斷 worker 自動重試。Server 不暫停競標等待掉線者。
