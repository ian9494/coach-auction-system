# Phase 2B Transport Protocol

已實作 FastAPI + python-socketio AsyncServer + ASGIApp，Uvicorn 單 worker。
AuctionService 是唯一 authority；transport 不直接修改 state 或計算 winner / 預算 / zone。
沒有 GUI、Viewer migration、static public mount、TCP adapter 或 production deployment。

## 啟動與設定

`create_app(ProjectConfig(...), AuthConfig(...))` 可注入測試設定；import / factory 本身不建立 DB 或 listener。
ASGI lifespan 啟動時讀專題 examples roster、檢查 auth、開 SQLite、恢復 service；shutdown 停 broadcaster / display task / deadline timer、Socket.IO tasks 與 repository。
預設只有 `127.0.0.1:3001`，runtime 為 `runtime/final_project/`。不要共用正式 data、port 3000 或多個 workers。

本輪已驗證相容範圍：FastAPI 0.143.x、Uvicorn 0.54.x、python-socketio 5.17.x / Engine.IO 4.14.x、websockets 16.x、aiohttp 3.14.x；HTTP in-process 測試使用 httpx 0.28.x。
版本範圍已寫入 pyproject.toml。環境可用 pip 時，以 `python -m pip install -e '.[dev]'` 安裝。

AuthConfig 使用環境變數：

- `FINAL_PROJECT_ADMIN_TOKEN`
- `FINAL_PROJECT_COACH_TOKEN_COACH01` 到 `...COACH08`（一般規則為 ID.upper()）

所有 token 必須各自不同、16–1024 字元；缺少 / placeholder 會阻止 startup，不退回 dev-token。
`.env.example` 僅供設定參考，**不自動載入 .env**；本地自行 export 環境變數後：

```powershell
python -m final_project.server.app
```

本輪測試沒有啟動這個固定 port 指令。測試只用 in-process 或 localhost ephemeral port + temp DB。

## Roles / join

connect 僅建立未加入角色的 session；不能直接出價或管理。
成功 join 固定 role / coach_id，session 只存 role、coach_id、authenticated、joined，不存 token。
角色互斥；同一 socket 不能改 coach 或升權。相同角色重 join 仍要重新驗證 token。

| Event | Payload | 身分 |
|---|---|---|
| join_viewer | `{}` 或無 payload | 匿名 read-only |
| join_admin | `{"token":"<local-token>"}` | Admin token |
| join_coach | `{"coachId":"coach01","token":"<coach-token>"}` | 該 coach 獨立 token |

Token 用 constant-time 比對；錯誤不回 token、traceback 或 filesystem path。
成功 join ACK 的 payload 是 `{role, snapshot}`，snapshot 帶目前 version / round_id。
身份建立與命令執行都有每 socket lock，防止同時 join 造成角色 race。

## Mutation / ACK

```json
{"request_id":"bid-001","round_id":"<uuid>","amount":100}
```

| Event | Role | 額外欄位 |
|---|---|---|
| start_auction | Admin | playerName、duration（預設90） |
| pause_auction / resume_auction / end_auction | Admin | 無 |
| set_minimum_bid | Admin | amount |
| undo_last_award | Admin | 無 |
| submit_bid | Coach | amount |
| add_all_budgets / reset_auction | Admin | 尚未實作，NOT_IMPLEMENTED |

所有 mutation 必須 request_id；除了 start 都要 round_id。start 的 round_id 必須省略或 null。
request_id 只允許 1–128 個 ASCII 英數 / `_` / `-`；round_id 為非空字串，最長128。
amount 僅真正非負 int，最多 JSON safe integer；拒絕 bool、float、numeric string、NaN、缺值或未知欄位。
duration 僅真正 int，1–86400。start playerName 非空、最長200。
**submit_bid 若含 coachId / coach_id，直接 INVALID_PAYLOAD**；真正 coach_id 由 session 注入 service command。

所有 ACK（包含 join、未知事件與錯誤）結構相同：

```json
{
  "ok": true,
  "error_code": null,
  "message": "OK",
  "version": 2,
  "round_id": "<uuid>",
  "request_id": "bid-001",
  "payload": {"changed": true}
}
```

join request_id 為 null，payload 是 role / snapshot。格式錯誤 request_id 無法驗證時回 null。
service result 直接映射 ACK，保留 STALE_ROUND、INVALID_STATE、INVALID_BID、UNKNOWN_COACH、PERSISTENCE_ERROR 等。
transport 另外提供 UNAUTHORIZED、FORBIDDEN、INVALID_PAYLOAD、UNKNOWN_EVENT、SERVICE_NOT_READY、INTERNAL_ERROR、NOT_IMPLEMENTED。

request_id 先加入 **角色 + coach ID** 的 hash namespace，不依 sid / token，確保不同 coach 可用相同 ID，且重連 / restart 可取得原 ACK。
同身分相同 ID 與內容回舊 ACK，可能帶較舊 version；相同 ID 不同內容 REQUEST_ID_CONFLICT。
timeout 是 server-only command，沒有 event；不能從 Client 送內部 timer / service metadata。

## Projections / broadcasting

| Role / event | Snapshot |
|---|---|
| Viewer / viewer_state | status、current_player、duration、time_left、remaining_seconds、deadline_utc、minimum_bid、coaches、teams、budgets、結算後 winner / winning_amount、version / round_id |
| Coach / coach_state | Viewer 欄位 + coach identity、本人 myBid、本人 bidRules / eligible |
| Admin / admin_state | Viewer 欄位 + allBids、canUndo |

Viewer 沒有 bids、allBids、最高价 / 領先者、ticker bid、undo 或 processed requests；Coach 沒有他人 bid。
只有已結算結果的 winner / winning_amount 是公開金額；不回目前最高价。
共同欄位採 snake_case，myBid / bidRules / allBids / canUndo 沿用既有名稱；尚未宣稱舊 public JS 可直接相容。

Service post-commit queue 供 broadcaster 收到 Client mutation 與 internal timeout settlement。
Viewer / Admin / coach:<id> rooms 分別收到 role projection，不傳 full state 後靠 UI 隱藏。
每秒顯示 tick 僅讀 service snapshot，不寫 SQLite、不增加 version。
廣播有序列化 lock，丟棄舊 version 或同 version 倒數較舊的 snapshot，避免顯示倒退。
廣播失敗不回滾已 commit 命令；記錄不含 payload 的一般警告，Client 重連以完整 snapshot 恢復。

## Reconnect

每次 connect / reconnect 都需重新 join / auth；不恢復舊 sid 的 role，也不依賴漏掉的 incremental events。
join 返回最新完整 snapshot（Coach 含自己 myBid）。Client 應以 version 排序 state events，並辨識重送 ACK 的原 version。
同一教練多個已驗證 socket 會加入同一 room，仍由 service 決定最後有效出價。

## HTTP（全部 read-only）

| Method / path | 回應 |
|---|---|
| GET /health | status、ready |
| GET /api/coaches | legacy-compatible [{id,name}] |
| GET /api/members | 專題 roster 尚未售出的選手名字 |
| GET /api/results | service history 的 [{playerName,coachId,amount}] |
| GET /api/state/viewer | 只有 Viewer projection |

沒有公開 raw state / bids / Admin endpoint，也沒有 HTTP mutation；不讀正式 member.csv 或以 CSV results 作 authority。
尚未 ready 時 read API 回503；未知路由404。沒有掛載 public 或 data。

## Tests / limits

Phase 4 更新：Admin event `add_all_budgets` 已實作，payload 為 request_id、round_id（idle 無 round 時可 null）、strict positive int amount；當前 round 必須相符，走 service 的 atomic commit / dedup / version 路徑。Coach / Viewer 無權限。reset_auction 仍為 NOT_IMPLEMENTED。Start 現在由 service 驗證 roster 成員與未售出狀態。Admin client 控制與 CSV export 見 [Admin Client](FINAL_PROJECT_ADMIN_CLIENT.md)。以下測試數字描述 Phase 2B 當時結果。

測試分兩層：in-process FastAPI / 已註冊 Socket.IO handlers（fake session / emit capture），以及真實 Uvicorn ASGI + Admin / Viewer / 8 個 AsyncClient 的 localhost:0 測試。
後者驗證 WebSocket 與 HTTP polling handshake、ACK、rooms、重連、HTTP 與 shutdown；固定3001未啟動，正式站未連線。
涵蓋角色race、冒名bid、strict payload、敏感欄位缺席、token不出現在錯誤 / log / DB、PERSISTENCE_ERROR、principal namespace與跨app重啟ACK、timeout廣播及倒數不寫DB。
本輪完整 pytest：161 passed，包含前階段原有125 tests；syntax / import / dependency check 亦通過。

已知限制：目前只適合受控 demo，尚無 token輪換、auth嘗試限流、TLS deployment 或跨機實测；不可直接公開部署。
實測 Python AsyncClient 的 polling disconnect 可能等到 outstanding long-poll GET 的 heartbeat window 才結束；live test 採測試專用1秒 ping interval / timeout，應用預設值未更動。後續 Client 應明確處理 bounded disconnect，WebSocket 路徑本輪關閉正常。
保留單一 authority / synchronous SQLite 與 processed-request未裁剪的 Phase 2A 限制。完整 snapshot 廣播 queue 在高流量時也需要流量控制。
Phase 2C 範圍待確認；本輪不開始 GUI / Viewer / TCP。課程是否要求 raw TCP 仍未知。

整合方式依官方 [python-socketio ASGI 文件](https://python-socketio.readthedocs.io/en/stable/server.html)；Python測試client使用 [AsyncClient](https://python-socketio.readthedocs.io/en/stable/client.html)。
