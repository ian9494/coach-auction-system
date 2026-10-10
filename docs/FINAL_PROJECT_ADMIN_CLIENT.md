# Phase 4 Admin Desktop Client

## 啟動與登入

依 README 建立環境、設定本機 demo tokens 並啟動 Python server，再執行：

```powershell
.\scripts\start_final_admin.ps1
# 或
.\.venv\Scripts\python.exe -m final_project.client.admin_app
```

填入可修改的 Server URL（預設 localhost:3001）與對應的 Admin Token。Token 遮罩顯示，開始連線後清空 Entry，不儲存於檔案或日誌。使用與 Coach 相同的 ClientTransport；network thread 處理 Socket.IO / HTTP，Queue 傳入 snapshot、ACK、connection、HTTP data 與安全的 error code，root.after 僅在 main thread 更新 Tk widget。

Demo 可先在設定 tokens 的同一 PowerShell 用 `Set-Clipboard $env:FINAL_PROJECT_ADMIN_TOKEN`，貼入已開啟的 Admin 登入欄，再啟動 server；不同終端不會自動共用 process environment。請勿把 token 寫進文件或 commit。

## 畫面與操作

視窗約 1150×800。頂部是登入、連線状态、version / round；左側選手、秒數、競標控制、最低價與加預算；中間是目前選手、狀態、倒數、Minimum Bid、winner / winning amount；右側是全部 Coach bid、budget、人數；下方隊伍摘要與 CSV 匯出、操作結果訊息。投影未提供每位 Coach 的詳細 eligible / error，表格明確顯示「依 Server 判定」，不在 Admin Client 重建 domain rules。

選手來自 GET /api/members，不讀 server filesystem。登入、重連及 teams 變更後重新取得名單，也可手動重新整理；即使舊 HTTP 回應含售出者，最新 snapshot 的 teams 仍會將其排除。Server start 在 service 再次驗證選手屬於 roster 且尚未售出；未知 / 已售出者回 INVALID_COMMAND。Undo 後可重新競標該選手。

| 狀態 | 控制 |
|---|---|
| idle / ended | 開始下一輪 |
| running | 暫停、強制結算 |
| paused | 繼續、強制結算 |
| offline / reconnecting | 所有 mutation 停用，保留最後畫面 |
| pending | mutation 暫時停用，避免重複點擊 |

Start 使用選手與正整數 duration（1～86400，預設 90）。Minimum Bid 接受非負整數；idle 尚無 round 時停用，已有 round 時可套用。舊 bid 失效會由最新 allBids snapshot 顯示「—」。None 顯示「—」，合法 0 顯示「0」。Undo 僅在 canUndo 時啟用。

Force End 在倒數尚有時間時、Add All Budgets、Undo 均有二次確認；取消不送任何 command。Client 倒數只供顯示，不觸發結算；force end 即使本機顯示 0 仍可操作。

## 全體加預算

正式增加 domain transition 與 AuctionService command `add_all_budgets`，限 Admin、strict positive int，每次使用新的 UUID request_id。既有 round 必須提供目前 round_id；idle 尚無 round 可為 null。單次 amount 與各結果 budget 不超過 JSON 安全整數 2^53−1。

由 service lock 序列化、copy-on-write、SQLite commit 後更新 authority / snapshot / version；持久化失敗不改 memory。相同 ID / payload replay 不再次增加預算，跨 restart 保留 dedup。沒有直接修改 GUI / transport budget，也不補回舊 bid、不改 history、timer 或既有出價上限規則。截止已過時仍沿用 service 的先結算再處理命令順序。

## CSV 與 reset 範圍

本輪只支援 Export Results。背景 HTTP 取得 /api/results 的 authority history，再由存檔視窗選擇位置，使用 Python csv、utf-8-sig、欄位 playerName / coachId / amount。輸出不依賴 Client 重建結果，也不讀正式 auction_results.csv；名稱以公式起始字元開頭时加文字前綴，避免試算表當公式執行。匯出是該次 HTTP 讀取時的結果，之後發生 undo / 新得標需重新匯出。

Roster import 留 Phase 6。安全 reset / clear results 也留後續階段；本輪沒有 reset 按鈕或任何清空資料的 Client 捷徑，reset_auction 仍回 NOT_IMPLEMENTED。後續必須另外定義 budgets / history 的清空範圍並完整驗證 timer 與持久化。

## Authority、pending 與重連

只有 snapshot 更新 latest_version / state；舊 snapshot 忽略，ACK 只顯示 command outcome。ACK v11 不覆蓋 snapshot v12；較新 ACK 也不自行重建狀態。pending 在 ACK 與對應或更高版本 snapshot 都抵達後解除，兩種抵達順序皆有測試。rejected ACK 解除 pending；未確認操作不自動重送。

斷線保留最後畫面並停用 controls，auction 在 server 持續。自動重連重新 join_admin，完整 snapshot 替換 local state。若 committed ACK 已成功但廣播一直未到，pending 可能保持停用：使用者可按離線再登入，取得完整 snapshot 恢復。此階段未導入可靠事件重送 / outbox。

## 驗證與已知限制

headless presenter / service / transport 測試涵蓋 controls、輸入、None / 0、snapshot / ACK 排序、重連、認證、server unavailable、player validation、加預算 atomic failure / restart dedup、CSV encoding。原有「add_all_budgets 未實作」測試更新成新的 strict payload 驗證；reset 仍保持未實作。

最終共 246 tests（原有 209 加 37），連續兩次通過，並將未處理背景 thread exception 視為錯誤。認證失敗與 UI disconnect 的 cleanup 競爭另有 deterministic regression，避免再次取消正在關閉的 socket / HTTP session。

`test_admin_gui_smoke.py` 在 Tk 可用時建立 hidden window，真實 localhost ephemeral server 配至少 2 Coach。透過 GUI 啟動 Player01 / 5 秒、兩 Coach 出價、表格、pause / resume、取消與確認 force end、winner、export、取消與確認 undo、取消與確認加預算、下一輪 start；fake clock 避免依賴實際等待 5 秒。沒有 display 時只 skip 這個 smoke，所有核心測試仍可 headless 執行。

另修正既有多人 E2E 的等待競爭：比較各角色 frame 前須等所有角色抵達相同 authority version，不只等待 Admin。

未做人工視覺驗收、跨機 / TLS 部署、名單匯入、reset、Viewer / OBS migration、raw TCP。沿用單程序 authority、同步 SQLite、Queue / dedup 未限制容量與本機時計影響倒數的已知限制。公開 read-only HTTP APIs 仍無新增 auth；不要把目前受控 demo 當作 production 安全部署。
