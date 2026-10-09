# Phase 2C 整合驗證

本階段保留 Node 與 Python domain 規則，僅加固 Socket.IO room 故障隔離，新增整合測試。尚未實作 GUI、Viewer migration、OBS、raw TCP 或部署。

## 執行與隔離

使用開發環境執行 `python -m pytest -q`。原有 161 個測試保留，新增 15 個案例，合計 176 個。完整 suite 必須連續執行兩次。

`tests/live_support.py` 啟動真正的 Uvicorn / Socket.IO ASGI server、WebSocket clients 與 HTTP client。只 bind `127.0.0.1:0`，使用 pytest temporary root 下的 demo roster、隨機測試 token 與 SQLite。測試不使用 3000 / 3001、不讀寫正式 data、不建立專案 runtime DB。finally 關閉所有 client、server、socket 與 timer，並檢查 lifespan 完整退出。Windows 沙箱可能阻擋 asyncio 內部 socketpair，需在允許該本機操作的執行環境跑測試。

## 完整流程與壓力

1 Admin、8 Coach、1 Viewer 真實連線與驗證，啟動同一輪；8 Coach 各連續送出 12 次不同 request ID 的修改，共 96 次。每個 Coach 依序送出，各 Coach 並行。驗證最後接受的 bid、角色投影、單調 version、SQLite 與 authority 一致。

接續執行三種角色斷線 / 重新 join、pause / 拒絕 bid / resume、修改 bid、end、budget / history / winner、HTTP 結果、undo 與下一輪。Viewer 結算前無 winner / winning amount，也無 bids / allBids / leader / highest amount；Coach 只收到自己的 myBid；Admin 可看到全部 bids。下一輪自動最低價由 domain 規則重新計算，不保留前一輪人工出價。

## Reconnect 與 ACK

斷線不暫停 authority 倒數，也不刪除已接受 bid。每次新連線重新驗證與 join，取得完整角色 snapshot；不依賴 client 本地 state，也不回放 private event backlog。HTTP 與 Socket 使用相同 service，ended 時完整 Viewer snapshot 相等，results 與 history 相等。

測試透過不附 callback 的 Socket.IO emit 模擬「提交成功但 ACK 未收到」，再以相同 ID / payload 重送 bid、end、undo。回傳原 ACK，不再次增加 version、扣款或 undo。相同 ID 不同 payload 回傳 REQUEST_ID_CONFLICT。bid、end、undo 的去重紀錄跨全新 app lifespan / 同一 temp DB 仍有效。

注意：重送已處理的 ID 會回傳原 ACK，即使目前已進入新一輪；原 ACK 的 version / round_id 可以早於目前狀態。GUI 必須以較新的完整 snapshot 更新畫面，不能把舊 ACK 當成目前 state。未處理過的舊 round request 則在新一輪後回傳 STALE_ROUND。

## Restart 與截止競爭

running 尚未截止：從持久化 UTC deadline 換算剩餘時間並重新排程。running 已截止：啟動時結算一次。paused 保持 paused / 原剩餘時間，不排程。ended 保留結果。平手 fixture 使用兩個同價 Coach；再次 restart 改變 RNG 仍不重抽、不重複扣款。

競爭測試使用現有 FakeClock / FakeTimer 與註冊的 transport handlers，持有 service lock 讓兩個操作依指定順序進 queue，分別驗證 timeout 在 bid / end / pause 前後的六種排序。截止前 0.001 秒 bid 接受，截止後拒絕；兩種排序皆僅結算一次。再驗證舊 round request 與新 start 的兩種排序：start 前已 ended 的 bid 回 INVALID_STATE；start 後回 STALE_ROUND。此處不是依賴作業系統網路封包恰好抵達的順序，也不使用長 sleep。

## 故障行為

真實 transport 注入 repository commit failure：回 PERSISTENCE_ERROR，memory 不變、無新成功版本廣播；移除故障後同 ID 可重試。注入 Viewer room emit failure：持久化 authority 不 rollback，Admin / Coach room 照常更新，Viewer 可重新 join 取得最新 snapshot。room exception 僅記錄 event / version，不輸出 auth payload 或 token；不提供可靠 event delivery 保證。

malformed payload 僅拒絕該 request，其他合法 command 可繼續。直接關閉底層 WebSocket 模擬 abrupt disconnect，倒數與 bid 保留，可重新驗證並完成結算。

## 尚存限制

- 單程序 authority；SQLite commit 為同步操作，request 去重紀錄及 snapshot 廣播 queue 尚無容量 / 保留期限限制。課堂規模測試通過不代表大型效能或長時間慢客戶端壓測通過。
- room 傳送失敗沒有持久化 outbox / 自動事件重送；client 以重連取得完整 snapshot 恢復。ended / paused 沒有週期倒數廣播，因此不能只等待 tick 恢復。
- polling disconnect 可能等待 heartbeat；本輪主要使用 WebSocket，保留 Phase 2B polling 測試。
- auth rate limit、token rotation、TLS 與跨機部署仍未實作，不是此階段 blocker。
- 課程若要求 raw TCP，仍須在後續加入 TCP adapter；本階段未推定課程規格。

已具備進入 Phase 3 Coach GUI 的整合基礎。GUI 需明確處理重新驗證、request ID 保留、舊 ACK 與 snapshot version、斷線狀態與 timeout；本輪止於 Phase 2C。
