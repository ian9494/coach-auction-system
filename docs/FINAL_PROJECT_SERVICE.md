# Phase 2A：AuctionService / SQLite / Deadline

此階段只有 transport-independent service、stdlib asyncio timer 與 sqlite3 repository。
沒有 HTTP route、Socket.IO handlers、TCP adapter、GUI 或 Viewer。

## Authority 與命令

`AuctionService.open(repository, initial, clock=..., rng=..., timer=...)` 恢復或建立狀態。
只有一個 service / event loop / process 管理一個 DB；`asyncio.Lock` 是所有命令與 timeout 共用的序列化入口。
`snapshot()` 回 defensive copy，且 running 的 time_left / remaining 由 monotonic deadline 計算。
外部不能透過 snapshot 修改權威狀態；repository 只供 service 使用。

`Command` 包含 kind、request_id、round_id、payload。支援 start、pause、resume、submit_bid、set_minimum_bid、end、undo、timeout。
除了 start，其餘命令必須指定當輪 round_id；pause / resume 等錯誤狀態會拒絕。
timeout 的 deadline_utc 必須符合目前 schedule，過早事件不會結算，也不會記成完成 request。

`CommandResult` 包含 ok、error_code、message、version、round_id、payload（changed）。
錯誤碼包含 INVALID_REQUEST、INVALID_COMMAND、INVALID_STATE、INVALID_BID、UNKNOWN_COACH、STALE_ROUND、STALE_TIMER、TIMEOUT_NOT_DUE、DEADLINE_PASSED、REQUEST_ID_CONFLICT、PERSISTENCE_ERROR、SERVICE_CLOSED。
payload 不含全體 bids；角色資訊 projection 留待 Phase 2B。

每次有效 state / lifecycle metadata 變更 version +1；相同金額重送、已 ended 再 end、拒絕命令及顯示秒數刷新不增加 version。
每次 start 產生新 UUID round_id。結算記 settled_round_id，undo 保留已結算身分；下一轮 start 才清除。
Phase 1 domain 不增加 transport / session 欄位；這些 metadata 存在 service Snapshot。

## Transaction 與 request dedup

命令先產生獨立 candidate：

1. 執行純 domain transition / 更新 candidate metadata。
2. 將 candidate 與 request result 放入同一 SQLite transaction。
3. commit 成功後交換記憶體 authority，再更新 timer / 回成功。

DB 寫入失敗回 PERSISTENCE_ERROR，記憶體 / active timer 不採用 candidate；此失敗結果不會 cache，原 request 可重試。
被拒絕的有效格式命令也保存 failure ACK；若連 failure ACK 都存不了，回 PERSISTENCE_ERROR。
initial commit / load / expired recovery 失敗則 open 報 RepositoryError，不靜默重新初始化。

request_id 以 kind + round_id + canonical JSON payload 的 SHA-256 fingerprint 綁定。
相同 ID / 相同命令回原先完全相同的 ACK（包括原 version / round_id），即使目前已到下一輪或已 restart。
同 ID 不同內容回 REQUEST_ID_CONFLICT，不能重做副作用。內部 timeout 使用保留的 `timeout:` prefix。
Phase 2B 必須將 request_id 與已驗證的 caller 身分一起命名空間化，並禁止 transport 直接發出 timeout command。
目前未裁剪 processed 紀錄，以確保 restart 去重；後續若加 retention，需要明確界定重試期限。

## Deadline / recovery

- running 同時有持久化 UTC deadline 與執行期 monotonic deadline。實際受理時在 lock 內檢查 cutoff，不依 Client 倒數。
- 到 deadline 即結算；late bid 先走同一 timeout path 結算，再回 DEADLINE_PASSED。若結算存檔失敗，拒絕出價並回 PERSISTENCE_ERROR。
- pause 保存 fractional remaining，清 UTC deadline、取消 timer；time_left 只是 ceil(remaining) 顯示。
- resume 用 remaining 建新 UTC / monotonic deadline。旧 schedule 的 deadline 不符時拒絕，不結算新 schedule。
- Default DeadlineTimer 是一個 asyncio task；timeout commit 失敗每 0.1 秒重試。成功 / stale / closed 停止，不開任何網路 listener。
- idle restart 恢復 idle；paused restart 保留 remaining，停機不扣時。
- running restart 用 UTC deadline - UTC now 建新的 monotonic deadline；未到期重新 schedule，已到期使用已保存 bids 結算一次。
- 已結算後再 restart 不抽籤、不扣款、不新增 history；undo metadata 與 request 結果同樣恢復。

UTC 恢復仍依赖 OS wall clock 準確；執行期 wall clock 跳動不影響 monotonic 受理，但跨 restart 的嚴重時鐘偏差須由部署時間同步處理。
RNG 若結算 transaction 失敗，之後重試可能重新抽選；只有成功 commit 的結果為正式結果，此時尚未送 success ACK。

## SQLite schema / 路徑

repository 只能從 ProjectConfig 取得 DB 路徑；預設是 `runtime/final_project/auction.sqlite3`，禁止 data/ 與越界 / symlink 指向正式 data。
測試顯式以 `ProjectConfig(project_root=tmp_path)` 把相同 runtime 相對路徑放到 pytest temp root；JSON 設定不能指定 project_root。

使用 `PRAGMA user_version=1`；唯一表：

```sql
CREATE TABLE snapshot (
    id INTEGER PRIMARY KEY CHECK(id=1),
    schema_version INTEGER NOT NULL,
    document TEXT NOT NULL
);
```

document 是 UTF-8 JSON envelope：schema_version、state、metadata。
state 包含完整 Phase 1 dataclass（coaches / roster / budgets / bids / history / undo 等）；metadata 包含 version、round_id、remaining、deadline_utc、settled_round_id、processed request fingerprints / ACKs。
沒有 pickle；拒絕未知 schema、缺少 state 欄位、非法型別 / 金額、壞 JSON、非有限值、無效 coach 參照與缺少 deadline 的 running state。
整個 snapshot + metadata + requests 以單次 upsert transaction 寫入；CSV 不參與 authority。
遇到不相同的 configured roster 與 DB roster，startup 明確失敗，避免更換名單順序悄悄改 zone。

repository 的 sqlite 呼叫目前同步且持有 service lock。8-coach 專題規模優先簡單可靠；若 DB 變大 / write latency 增加，需在維持 commit-before-ACK 的前提改單一 I/O worker。
不支援多個 service / worker 同寫一個 DB，Phase 2B 部署必須保持單一 authority。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

目前 125 tests passed，含原有 81 tests 與 25 個 Node parity 共用案例。
pytest 的 basetemp 指向忽略的 `.pytest_cache/tmp`，只在暫存目錄建立 DB；不建立實際 runtime/final_project DB。
Windows sandbox 可能阻擋 asyncio 的 OS 內部 self-pipe：需允許這個 event-loop 機制才能跑 async tests；這不是應用 HTTP / Socket.IO listener。
測試有 deterministic fake clocks / timers，以及實際 asyncio task 的 cancel / retry / service callback 測試，不依賴網路。

Phase 2B 可接 transport，仍需實作 caller auth、role projections、ACK 映射與安全 request namespace；raw TCP requirement 尚未確認。
