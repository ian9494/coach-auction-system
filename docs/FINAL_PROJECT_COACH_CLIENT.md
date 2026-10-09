# Phase 3 Coach Desktop Client

使用 Python 3.11+、Tkinter / ttk 與專題現有 Socket.IO stack。Windows Python 安裝需包含 Tcl/Tk；Linux 可能需要系統的 python3-tk 套件。沒有新增 GUI pip dependency。

## 啟動

依 README 建立 `.venv`、安裝專案、設定本機 demo token 並啟動 Python server。另一個終端執行：

```powershell
.\scripts\start_final_coach.ps1
# 或
.\.venv\Scripts\python.exe -m final_project.client.coach_app
```

登入區填 Server URL（預設 `http://127.0.0.1:3001`，可修改）、Coach ID（例如 `coach01`）與 server 對應 Token。Token 遮罩顯示、成功開始連線後清空 Entry，不寫入檔案或日誌。認證錯誤會停止該 worker，重新填寫後可再連線。連線失敗則持續嘗試，按「離線」可停止。

主畫面約 1000×720：上方連線與教練身份；中間當前選手、狀態、倒數、Minimum Bid、出價框，以及自己的 budget / 合法範圍 / 預留預算；下方自己隊伍與全部教練公開預算、人數。Coach projection 未提供自己的歷史成交價，所以隊伍只列選手名稱，不自行推算價格，也不顯示其他教練 bid。

## 操作

競標中且 Server eligible、連線成功、倒數大於 0 時可出價。每次送出 / 修改使用新 UUID request_id，payload 包含目前 round_id 與整數 amount。0 是合法輸入；空字串、負數、小數及超出 JSON 安全整数範圍會在本機拒絕。預算、zone 與最低價限制仍由 Server 最終判定。

paused / ended / idle / 斷線時停用按鈕。結算後顯示 winner / winning amount。倒數以 snapshot deadline 與本機時間計算，沒有 deadline 時以 time_left 校正；Client 不觸發結算。電腦時鐘偏差可能影響顯示與按鈕，Server deadline 仍具最終權威。

## Threading / Queue

`ClientTransport` 在專屬背景 thread 執行 asyncio / Socket.IO AsyncClient。該 worker owns HTTP session，處理 connect、join、command / ACK、自動 reconnect 與 cleanup。UI 呼叫 send_command 只寫 outbound Queue，不等待網路。

四種 inbound message：ConnectionChanged、SnapshotReceived、CommandAckReceived、TransportError。背景 callback 只寫 thread-safe Queue。Tkinter main thread 每 50ms 透過 root.after 消費最多 100 個事件並更新 widget；不在 callback 操作 Tk。不在 main thread 等待 ACK 或等待 worker 結束；關窗取消 worker，UI 輪詢 thread 結束後退出。

Transport 可接受 coach / admin / viewer credentials，供後續 GUI 重用；本階段只建立 Coach UI。外部 exceptions 統一轉為穩定 code，GUI 顯示友善訊息，不顯示 raw traceback / token。

## Reconnect 與版本

斷線保留最後 snapshot / myBid，停用出價。worker 重連重新驗證 / join，取得完整角色 snapshot 再恢復操作。未確認或排隊出價不自動重送；訊息提醒使用者查看 snapshot 後再決定。

`CoachViewModel.latest_version` 只由 snapshot 更新。version 小於目前值忽略；等於或更大則完整替換。ACK 只影響 command result 訊息，不改 authority snapshot，也不推進 latest_version。明確測試 snapshot v12 → ACK v11，狀態仍為 v12；較新 ACK 也等待 snapshot。新的手動登入建立新 model，避免切換 server / 身份時沿用舊版本。

## 驗證與限制

原 176 tests 保留，新增 33 個，完整 suite 連續兩次皆為 209 passed。新增 headless view-model 與真實 localhost ephemeral Socket.IO transport tests，涵蓋登入、auth failure、snapshot、bid / ACK、reconnect、新輪、stale snapshot / ACK、queue 多 producer、server unavailable、ACK timeout 不自動重送及 shutdown。資料庫與 roster 都在 temp root，不使用 3001 或正式 data。

另外執行隱藏 Tk 視窗的 widget 建構 / 初始出價停用 / shutdown smoke，以及真實 localhost ephemeral server 的 GUI 登入、選手顯示、Button.invoke 出價、snapshot 更新、pause / resume / end。測試使用 temp DB、隨機 token 與 injectable clock。這不是人工點擊驗證，未宣稱已完成視覺 QA 或 manual localhost 全流程 demo；pytest 本身完全不需要視窗。

仍未處理大量長時間 inbound queue 的容量、跨 server 狀態版本重設（必須手動離線 / 新登入）、TLS / token rotation / auth rate limit。Token 只存在記憶體，但 Python 無法保證立即抹除。Transport 使用 WebSocket；只支援 polling 的網路環境尚未驗證。尚無 Admin GUI、Viewer migration 或 raw TCP adapter。
