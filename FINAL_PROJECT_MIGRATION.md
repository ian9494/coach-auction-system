# 網路程式設計期末專題遷移規劃

分析日期：2026-10-07。此輪只新增本文件，不修改競標程式、不執行 reset 工具、不連線正式站。

## 1. 結論與分析範圍

建議採用 **Python asyncio + python-socketio AsyncServer + FastAPI / Uvicorn、Tkinter Coach 與 Admin GUI、沿用瀏覽器 Viewer / OBS**。以既有事件與 JSON 欄位為相容邊界，將 JavaScript 競標規則逐項移植、以行為測試比對；不是重新設計競標遊戲。Python 不能直接執行既有 JS domain code，因此重用的是規則、資料格式、協定與展示素材。

掃描了版本控制檔案清單、server.js、各角色 JS、HTML script 引用、設定、CSV 與開發工具。圖片僅盤點檔案用途，未逐張視覺檢查。以下是靜態程式分析；未啟動 Node server、未做瀏覽器或多人實測。checkout 缺少必要 member.csv，不能宣稱目前完整可啟動。

實際 Git 狀態為 detached HEAD，HEAD 與 final-project 都是 `4cf6d802c211e71eb1ca4b532dcf1ece8d81fbbb`；final-project 已在另一 checkout 使用。此輪沒有切換分支、提交或修改 main。後续實作前應先確認本 worktree 要使用的工作分支，避免以為提交會自動落在 final-project。

## 2. 現況：目錄與責任

| 位置 | 用途與實際情況 |
|---|---|
| server.js（886 行） | 唯一正式後端：Express、HTTP server、Socket.IO、所有競標規則、狀態、計時、CSV 與 JSON 儲存混在同一檔 |
| public/admin.html / .css / .js | Web 管理：選人、開始、暫停、繼續、強制結束、底價、全體加預算、撤銷；可看全部出價 |
| public/coach.html / .css / .js | `?coach=<id>` 指定教練；出價與改價、個人 bidRules、隊伍與全體預算顯示；UI 驗證只是輔助 |
| public/viewer.html、viewer-colored.html、viewer-transparent.html / viewer.js / viewer.css | 共用 Viewer 邏輯與展示樣式，供 OBS Browser Source 使用 |
| public/auction-overlay-redesign.html / viewer-redesign.js | 另一套直播展示，含目前最高價、領先者與出價 ticker；HTML 原型 JS 位於 application/x-prototype-disabled script，不會執行，不能當成正式競標邏輯 |
| public/results*.html / results.js / results.css | 成果分隊展示；HTTP 每 10 秒輪詢，不是 Socket.IO 即時更新 |
| public/assets/players、coaches、frames；public/*.png；根目錄 UI__2_1920x1080.png | 頭像與版型素材；根目錄圖片不在 Express public 靜態根下 |
| data/coach.csv | 唯一 tracked 資料檔，8 位教練 id/name；讀取時檢查 ID 格式與重複 |
| data/member.csv | 必要選手名單，checkout 中不存在，且被 gitignore 排除；啟動同步讀取，缺檔會失敗 |
| data/state.json、state.json.tmp、auction_results.csv | 執行時資料，checkout 中不存在，被忽略 |
| devTools/ | Playwright 截圖與 DOM 尺寸工具、Pillow / numpy / scipy 圖片工具、curl reset bat；不是 Python 競標實作 |
| package.json / package-lock.json | Express 5、Socket.IO 4；沒有有效 test / start script，main 指向不存在的 index.js |
| README.md / nodemon.json / .gitignore | README 只有兩行；nodemon 避免儲存資料触發重啟；未宣告 devTools 的額外依賴 |

沒有找到 repository 內 AGENTS.md 或現成測試。不能由檔名、圖片數量或註解推導缺少的正式名單順序。

### 核心函式地圖（server.js）

- 規則：getPlayerZone、getCoachPlayerCount、getCoachSpent、getCoachZonePlayerCount、getBidRules、getBidError、pruneInvalidBids、applyAutoMinimumBids、getWinner（約 306–466 行）。
- 狀態投影：getViewerState、getCoachState、broadcastState（約 469–532 行）。
- 狀態轉移：startAuction、pauseAuction、resumeAuction、endAuction、undoLastAward、resetBids、resetBudgets。
- I/O：saveState / loadState（48–79）、saveHistoryToCSV（約 556–585）、startAuctionTimer（587–606）、Socket.IO handlers（656–831）、HTTP reset handlers（834–881）。
- 真正 source of truth：全域 state、coachBudgets、auctionHistory；lastAwardUndo、auctionTimer、rate-limit Maps 是另外的執行期狀態。Client 本地 state 只服務 UI。

## 3. 現況：HTTP / Socket.IO 協定

目前不是原生 WebSocket 協定，而是 Socket.IO；可能走 WebSocket 或 HTTP long-polling。三種瀏覽器角色都用同源 `io()`；HTML 從 Node 提供的 `/socket.io/socket.io.js` 載入客戶端。

### HTTP

| Method / path | 行為 |
|---|---|
| GET / | 程式有 redirect /admin.html；另有 public 靜態檔服務 |
| GET /api/coaches | 回傳 [{id,name}] |
| GET /api/members | 每次重新讀 member.csv，按 history 過濾已售選手 |
| GET /api/results | 從記憶體 history 回傳 [{playerName,coachId,amount}]，不是讀結果 CSV |
| POST /api/admin/reset_budget、/api/admin/reset-budgets | x-admin-token 驗證，預算回 1000、history 清空，但當輪状态/出價未清除 |
| POST /api/admin/reset_auction、/api/admin/reset-auctions | token 驗證，重置競標、預算、history、出價；沒有清除正在跑的 timer |

目前「CSV 匯入」是從伺服器磁碟讀 coach.csv / member.csv，沒有 upload API 或 GUI 匯入功能。「CSV 匯出」是自動寫 data/auction_results.csv，沒有 download API；不能把描述的功能當成已存在的介面。

### Socket.IO

| Client → Server | Payload | 責任 |
|---|---|---|
| join_viewer | 無 | 加 viewer room，立即取得 snapshot |
| join_admin | 無 | 加 admin room，設定 isAdmin，取得含 allBids / canUndo 的 snapshot |
| join_coach | {coachId} | ID 合法即加入 coach:<id>；不驗證身分 |
| start_auction | {playerName,duration} | 檢查未 running / paused；開始新輪，預設 90 秒 |
| end_auction | 無 | running / paused 時結算 |
| pause_auction、resume_auction | 無 | 暫停 / 繼續 |
| set_minimum_bid | {amount} | 設底價並清掉失效出價 |
| add_all_budgets | {amount}，預設 100 | 增加全體預算 |
| undo_last_award | 無 | 撤銷最近一次可撤銷得標 |
| submit_bid | {coachId,amount} | 覆寫該 coach 本輪出價；最後一筆有效值留存 |

Server → Client：viewer_state、admin_state、coach_state、error_message。每秒及成功操作後廣播完整 snapshot；沒有 request ID、round ID、version、成功 ACK。

Coach snapshot 包含本人 myBid、budget、bidRules、公開隊伍 / 預算；Admin 看全部。**Viewer 在未 ended 時也收到原始 bids，viewer.js 顯示金額，viewer-redesign.js 還推導最高價與領先者，與密封競標需求不一致。** 不能只在 GUI 隱藏金額；Python server 必須從公開 payload 移除金額。

## 4. 競標流程與必須保留的規則

1. 載入教練與按順序排列的選手；載入 snapshot 或初始化預算 1000。
2. Admin 開始新輪：status=running、選手、duration / timeLeft、清 winner 與 bids，再對所有符合資格者自動填最低合法出價。
3. Coach 可在 running 多次改價；整數、非負、底價、剩餘預算、名額、保留預算與其他規則全部由 server 驗證。
4. running 可 paused，paused 不收出價；resume 接續剩餘時間。
5. timer 或 Admin 強制結束：重新驗證出價，最高合法價得標，同價候選者隨機等機率選一位；扣預算、追加 history、存檔、广播。
6. 下一輪開始取消上一輪的撤銷機會；撤銷會退還款項、移除最後 history，回 ended / 無 winner，保留該輪 bids，但不會重新開放競標。

| 規則 | 現行精確行為 |
|---|---|
| 隊伍 | 每隊最多 5 人 |
| 上限 | 單次最高 500；還需得標後對每個剩餘 slot 保留 100 |
| 第二位 | 已有 1 位時，第二位得標後累計花費必須 **大於** 300；min = 301 - 已花費，再與底價及 0 取 max |
| 分區 | member.csv 第 1–8 位 zone 1（每隊 1 位）、9–16 位 zone 2（每隊 1 位）、17–40 位 zone 3（每隊 3 位）；未知姓名 / 超過 40 位没有 zone 限制 |
| 0 元與 null | 0 是有效出價，null 是沒有出價；不可用 truthiness 合併 |
| 自動底價 | 開始時對所有合資格 coach 填 minBid；預設底價 0 時可自動 0 元得標，不一定「無人手動出價就流標」 |
| 修改底價 | 清除不合法舊價；不再自動補出價 |
| rate limit | 每 coach 至少隔 300ms，同 IP 2 秒最多 3 次；同教室共用 NAT 會互相影響 |
| 倒數 | timeLeft 從 90 每秒 -1，到 0 先廣播，再到 -1 才 end；約第 91 次 tick 結算，0 秒仍 running |

以上 domain 規則先建立 parity cases。安全性、截止時間與恢復缺陷要另列「預期修正」，不能偷偷當成等價移植。推薦期末版使用真正 deadline，在 90 秒截止、不接受逾時出價；這是明確修正，需在測試及報告說明。

### 持久化現況

saveState 同步寫 tmp 再 rename，包含 status、currentPlayer、timeLeft、savedAt、bids、budgets、history、winner、winningAmount、minimumBid。出價與轉移時儲存，計時每 5 秒儲存。未保存 duration、lastAwardUndo、rate limits。重啟 running 時按 savedAt 扣停機秒數，若歸零直接設 ended，**沒有呼叫結算，因此可能沒有 winner / history / 扣款**。剩餘時間大於 0 才重建 timer；paused 保持剩餘時間。

結果 CSV 是 BOM UTF-8，每欄一隊、每列選手名，沒有成交價 / timestamp；不能用它完整恢復。JSON 才是恢復來源。CSV 非同步獨立寫，與 JSON 並非單一交易；reset 沒有重新匯出 CSV。

## 5. 三類拆分

| 類型 | 項目 | 處理方式 |
|---|---|---|
| 可以直接保留 | 圖片、頭像、frame、現有 CSS、colored / transparent 版型、coach.csv 格式 | 素材與視覺沿用；Python 靜態服務保持 URL 相容 |
| 可以直接保留 | server.js、原 Web Admin / Coach、Node package / lock、nodemon、devTools | 作為正式版原始參考 / 回退，不在第一階段改寫；reset bat 不能用於專題測試 |
| 可以重用但需改寫 | domain functions、狀態轉移、JSON snapshot / CSV 格式 | Python 語意移植，依同組 fixture 比對；JSON 增加 schema version |
| 可以重用但需改寫 | 事件名稱與角色 snapshot、HTTP responses | 建 Python adapter；加 auth、ACK / request_id / round_id / version，保留既有 response 欄位 |
| 可以重用但需改寫 | Viewer JS / 結果展示 | 保留排版，改密封資訊顯示、重連 join、Socket.IO client 引用；results 輪詢可先保留 |
| 應重新實作 | Python Coach GUI / Admin GUI、共用 transport | Web DOM 不能直接移到 Tkinter；以既有操作與狀態欄位作規格 |
| 應重新實作 | deadline scheduler、session auth、重連同步、命令去重、交易一致性、測試 | 現有實作不足以可靠處理新架構；不得各角色各寫一套核心規則 |

UI 與 domain 不是全部混在瀏覽器：主要 domain 已在 server，但 server 的 domain、transport、disk I/O 耦合很高；Coach 重複部分驗證，Viewer 還自己推導領先者。

## 6. Python Client / Server 設計

### 技術比較與選擇

| 方案 | 優點 | 代價 / 適用 |
|---|---|---|
| TCP socket + threads / asyncio streams | 能直接展示 TCP framing、收發、拆包，適合明訂 socket 作業 | 要定義長度前綴或 newline JSON、連線生命週期、驗證；瀏覽器不能直接連 TCP，要再建橋接 |
| asyncio | 多連線與計時的並行執行基礎 | 不是 wire protocol，必須搭配 TCP、WebSocket 或 Socket.IO |
| 原生 WebSocket + FastAPI | Python / browser 都能推送 JSON | Socket.IO client 不能直接連 raw WebSocket，既有事件與重連需重寫 |
| **python-socketio + asyncio / ASGI** | 沿用事件、rooms、瀏覽器協定；Python client 與 Web Viewer 同 server | 需確認 Python / JS 協定版本，明確處理靜態 client script 與應用層安全 |
| HTTP 輪詢 | 容易示範與除錯 | 倒數與多人出價的主通道不適合只依賴輪詢；保留作名單與結果 API |

預設選最後的 Socket.IO 方案，是實際跨 process / 跨主機網路通訊。若課程要求「一定使用 socket 模組並自行設計 TCP 協定」，改加 asyncio TCP adapter，讓 TCP 與 Viewer Socket.IO 共用同一 AuctionService；不建立兩份競標狀態。此要求目前未提供，不能宣稱教授必定接受 Socket.IO。

建議依賴：python-socketio、FastAPI、Uvicorn，GUI 使用 python-socketio client 所需 HTTP / WebSocket 依賴；實作時固定已驗證版本。server 單一 process / worker，避免各 worker 各有不同 auction state；這個 8 coach 規模不需要 Redis 或多 worker。

### GUI

優先 Tkinter / ttk：標準庫介面、部署負擔小、足夠顯示輸入、表格、倒數、隊伍與連線狀態。PySide6 適合更複雜視覺與 model/view，但增加安裝、打包與 event loop 整合工作；目前不以視覺重製為主，先不選。不要直接把 browser CSS 視覺逐項重做。

Tkinter main thread 只負責 UI；一個背景 transport thread 使用 socketio.Client，接收 callback 將訊息放 Queue，main thread 透過 after() 消費。送出也用 outbound queue / 序列化工作，避免主執行緒等待網路。背景 thread 不直接改 Tk widget；關窗時停止重連並關閉 transport。

### 資料路徑

```text
Python Admin GUI ─┐
Python Coach GUI ×8 ─ Socket.IO / JSON ─ Python ASGI server
Web Viewer / OBS ─┘                       │
Web results ─ HTTP API ────────────────────┤
                                          ├─ auth / transport adapters
                                          ├─ AuctionService（命令與計時順序）
                                          ├─ 純 domain rules + role projections
                                          └─ SQLite / CSV repository
```

- 每個連線驗證角色：Admin token、每 coach 獨立 token；coach 身分取自 server session，不接受 payload 任意指定他人。切角色需移除原 rooms；Viewer 不可升權。
- Admin 命令延續開始 / 暫停 / 繼續 / 結束 / 底價 / 加預算 / 撤銷 / reset；所有入口（HTTP 也一樣）走同一 service 與 auth。
- 狀態唯一權威在 server。用單一命令 queue 順序处理 bids、Admin 命令與 timer timeout，或等價全域鎖；推薦 queue，讓寫入及結算無競態。快照讀 immutable copy，不能在廣播 await 期間讓一半舊一半新狀態混入。
- 每輪 round_id、每次變更 version。commands 帶 request_id / round_id；ACK 帶 ok、error_code、message、version。去重結果一併持久化，ACK 在 commit 後回覆；過舊 round 或截止後拒絕。
- domain 用整數金額、可注入 RNG 與 clock；平手記錄候選者與選中者，重啟不能重抽同輪。
- 公開 snapshot：選手、status、timeLeft、duration、deadline、底價、隊伍、預算、已結算 winner / amount；可顯示 submitted flags，但不含金額 / 領先者 / ticker bid amounts。Coach 只加自己 myBid / rules；Admin 才有 allBids。
- 開始 / resume 建立 deadline；paused 保存剩餘時間。執行期用 monotonic clock 控制截止，存 UTC deadline 用於恢復；Client 倒數只是顯示，不決定是否受理。
- rate limit 改以認證 coach 為主；IP 較寬鬆輔助並清理過期條目，以免教室 NAT 阻擋所有人。

### Viewer / OBS 相容細節

同 Python server 提供 public / assets 及 /api/coaches、/api/results、/api/members。沿用 join_viewer / viewer_state，新增欄位不破壞歷史顯示；移除 bids 金額是有意的資訊契約修正，要同步改兩套 Viewer renderer。

Python Socket.IO server 不應假定會像 Node 自動提供 `/socket.io/socket.io.js`。新增本地固定版本 public/vendor/socket.io.min.js 並修改專題 Viewer HTML script 引用；本地檔較适合教室離線展示。原 Web Admin / Coach 保留作參考，不當作未修改就可相容的新系統入口。結果頁 HTTP 輪詢保持即可，若時間足夠再接即時通知。

### 斷線 / 重連 / restart

- 斷線保留 server 已接收出價，倒數不中止；GUI 禁用出價並顯示離線，未 ACK 不顯示成功。
- 每次 connect / reconnect 重新驗證、join 正確角色、取得完整 snapshot，替換本地 cache。現在 Web JS 的 join 在 top-level，沒有 connect handler 重加 room；transport 自動重連不等於應用狀態已恢復。
- 不自動重送過期 bid。ACK 丟失時以 request_id 查詢 / 去重重試，先同步確認 round_id；同 coach 多連線共用 room，service 收到順序決定最後有效價，所有該 coach GUI 都收到新 myBid。
- Python runtime 與正式 data 分離。推薦 SQLite（標準庫）單一 snapshot row / transaction，包含 undo、deadline、round_id、version、last settlement、去重紀錄；CSV 是可重新生成的匯出，不是第二套 authority。
- 舊 JSON 以唯讀 importer + 明確目標路徑導入新 DB，保留原檔；解析、schema、教練、數值與歷史關聯檢查失敗則報錯，不靜默重置預算。
- restart running 若 UTC deadline 已過：依保存 bids 只結算一次；未過則恢復 timer；paused 保持 paused。資料 commit 失敗不回成功 ACK，顯示 server 錯誤；CSV 匯出失敗可重試，不能重複扣款。

## 7. 依風險與依賴分階段

| 階段 | 工作 | 驗收 / 依賴 |
|---|---|---|
| Phase 0：基準與隔離 | 確認工作分支、課程是否限定 raw TCP；補專題選手 fixture（不可假造正式順序）、記錄協定與已知缺陷；固定 rules baseline | 可從乾淨 checkout 啟動測試資料；正式資料 / port / reset 工具隔離 |
| Phase 1：domain 抽離與移植 | 新增 Python model / rules / transitions；以 Node 可控測試 harness 捕捉原規則，不先重構正式 server.js | 同樣 fixture 比對合法價、分區、第二人、0/null、自動底價、改價、平手 RNG、撤銷；bug 修正測試單列 |
| Phase 2：Python server 與可靠狀態 | ASGI / events / HTTP / auth / queue / deadline / SQLite / ACK；先用 headless Python clients | 8 clients 同時連線；最後有效價、身份隔離、密封 payload、只結算一次、存檔失敗、paused / running restart；依賴 Phase 1 |
| Phase 3：Coach GUI | Tkinter UI、transport queue、本人出價與隊伍 / 預算、連線與 ACK 狀態 | 至少兩個独立 GUI process 實測改價、限制、斷線 / 重連；依賴 Phase 2 |
| Phase 4：Admin GUI | 名單、競標控制、底價 / 預算、撤銷、CSV 匯入驗證 / 匯出、reset | 管理命令驗證與角色保護；pause / resume、reset 清 timer、已售選手不可重售；依賴 Phase 2，共用 Phase 3 transport |
| Phase 5：Viewer / OBS | 靜態服務、固定 JS client、密封 renderer、重連；結果 API 相容 | Browser / OBS 看到同步倒數與已結算結果，網路 payload 不洩漏出價；依賴 Phase 2 |
| Phase 6：專題交付驗證 | 全流程、局域網第二台機器、錯誤處理、中文 README、架構與協定說明、demo 腳本 | Admin + 8 Coach + Viewer，90 秒結算、平手、斷線、server restart、CSV；依賴前階段 |

持久化與基本錯誤處理必須在 Phase 2 就有，不能等所有 GUI 完成才補。優先展示完整競標閉環，再做 GUI 外觀。每階段維持 Node 可回退，禁止 Node / Python 同時寫同一資料來源。

## 8. 預計檔案變更（後續建議，非本輪已實作）

### 新增

```text
FINAL_PROJECT_MIGRATION.md             # 本輪唯一新增
pyproject.toml                        # Python 依賴與執行設定
.env.example                          # 空白 / 範例設定，不放實際 token
final_project/__init__.py
final_project/config.py
final_project/domain/__init__.py
final_project/domain/models.py
final_project/domain/rules.py
final_project/domain/transitions.py
final_project/server/__init__.py
final_project/server/app.py            # ASGI bootstrap / 靜態與 API routing
final_project/server/service.py        # 單一命令 queue / state authority
final_project/server/events.py
final_project/server/projections.py
final_project/server/auth.py
final_project/server/timer.py
final_project/storage/__init__.py
final_project/storage/repository.py    # SQLite commit / load
final_project/storage/csv_io.py
final_project/storage/legacy_import.py
final_project/client/__init__.py
final_project/client/transport.py
final_project/client/coach_app.py
final_project/client/admin_app.py
config/final_project.example.json      # 規則、路徑等，不含憑證
examples/final_project/coach.csv
examples/final_project/member.csv      # 明確標示非正式示範名單與分區
public/vendor/socket.io.min.js         # 固定版本與 license notice
scripts/start_final_server.ps1
scripts/start_final_coach.ps1
scripts/start_final_admin.ps1
scripts/export_final_results.ps1
scripts/legacy_parity.cjs              # 可控 timer / RNG / disk 的 Node 基準 harness
tests/fixtures/auction_cases.json
tests/test_domain.py
tests/test_protocol.py
tests/test_persistence.py
tests/test_multi_client.py
docs/FINAL_PROJECT_PROTOCOL.md
docs/FINAL_PROJECT_DEMO.md
runtime/final_project/auction.sqlite3  # 執行產物，ignore
```

### 預計修改

- README.md：新增 Python 專題中文啟動與局域網連線方法，保留 Node 說明。
- .gitignore：加入 .venv、__pycache__、pytest cache、專題 runtime、SQLite 附屬檔；示範 CSV 放 examples，避開 /data/* 忽略規則。
- public/viewer.js、public/viewer-redesign.js：密封呈現、connect 時 join / 斷線提示、正確 duration。
- public/viewer.html、viewer-colored.html、viewer-transparent.html、auction-overlay-redesign.html：本地 Socket.IO script；redesign 移除公開最高價 / 金額 ticker 文案。
- public/results.js：僅在驗收需要時補 HTTP response 驗證 / 更新策略；初期無需改資料契約。
- 若希望專題 Viewer 修改也完全不影響原展示檔，可改新增 public/final-project/ 下的版型副本；以保留原檔為預設，不維護两套 domain。

### 暫時保留不動

server.js、package.json、package-lock.json、nodemon.json、public/admin.*、public/coach.*、public/results*.html、所有 CSS 與圖片、data/coach.csv、devTools/*、LICENSE、.gitattributes。原 data/state.json / member.csv / auction_results.csv 即使後續出現，也不原地轉換覆寫。main / 正式部署不在此次工作範圍。

## 9. 重構風險與優先度

| 優先 | 風險與證據 | 遷移措施 |
|---|---|---|
| P0 | getViewerState 未 ended 傳 bids；兩套 Viewer 直接展示；join_admin 不驗證、start/end 不查 Admin、submit_bid 未綁 socket.data.coachId | Python auth + role projection 先完成；不能保留漏洞作相容要求 |
| P0 | checkout 缺 member.csv；順序決定分區，但 /api/members 動態讀與 MEMBER_NAMES 啟動快照不同 | 單一 validated roster；執行期匯入透過 service，不能直接改檔悄悄改分區 |
| P0 | reset_auction 不清 timer，reset_budget 留本輪 bids / winner；兩者 CSV 留舊內容 | 重置作完整狀態轉移，取消 scheduler，commit 後重建匯出 |
| P0 | 到 0 不結算；restart 過期直接 ended 不得標 | deadline + 冪等結算；單列行為修正 |
| P1 | start 只驗字串 truthy，trim 後可能空；允許未知 / 已售選手、任意正 duration | 清楚驗證名單 / 重複售出 / 空字串；未知選手是否要保留自由輸入須列設計選項 |
| P1 | state、budgets、history、undo 分散；endAuction 本身無重入保護；undo 未持久化 | 單一 model、service queue、transaction、round settlement ID |
| P1 | write error 只 log，仍可能對 Client 廣播成功；JSON 與 async CSV 非交易，並行匯出可能覆蓋 | commit 後 ACK、CSV 從權威資料序列化重建 |
| P1 | 金額 Number(amount) 接受數字字串等轉換；Python bool 是 int 子類 | 明確定義 typed payload，拒絕 bool / 非有限值，legacy coercion 只在 importer / compatibility adapter |
| P1 | 沒有 success ACK、request / round / version，Client 送出就寫成功 | ACK 與 snapshot 確認；去重防止 add budget / undo 重試重做 |
| P1 | Web reconnect 沒重新 join；同 socket 可加入多個 coach / role rooms | reconnect 再認證同步；session 角色唯一 |
| P1 | 同 IP 限流太緊、Maps 不清理；同步 JSON I/O 阻塞 event loop | 身分限流 / 清理、持久化序列化工作，避免主 event loop 長阻塞 |
| P2 | dev-token fallback；reset_auction.bat 硬編正式 HTTPS URL，同時 reset localhost / 正式站 | 專題工具只使用明確環境配置，不執行舊 bat |
| P2 | port 預設 3000，devTools 固定 localhost:3000；字體用 Google Fonts | 專題預設隔離 port 3001 / 獨立資料路徑；提供離線字体 fallback |
| P2 | Viewer 固定預算 1000 / 隊伍 5、0 元顯示不一致；duration 缺 snapshot | 投影提供規則與 duration，UI 不推導 domain |
| P2 | 多處 innerHTML 插入姓名與資料 | 專題 renderer 使用 textContent / DOM 建構，匯入文字不作 HTML |
| P2 | CSV 用 split / join，無標準 quoting；toLocaleString timestamp 不具固定時區格式；history 可含舊 coach | Python csv + utf-8-sig，UTC ISO timestamp；legacy schema validation 與明確錯誤報告 |
| P2 | 無可用測試、README 不完整、devTools 依賴未宣告、main=index.js 不符 | 新專題 entrypoints / 測試 / 中文文件，原 Node metadata 先保留 |

## 10. 官方技術參考與待確認事項

- python-socketio 支援 asyncio AsyncServer、ASGIApp 與 FastAPI / Uvicorn 整合：[官方 Server 文件](https://python-socketio.readthedocs.io/en/stable/server.html)。
- Python event-driven Client 與 reconnect 能力：[官方 Client 文件](https://python-socketio.readthedocs.io/en/stable/client.html)。應用層仍要重新驗證、join、同步 snapshot。
- Tkinter event loop / threading 限制：[Python 官方文件](https://docs.python.org/3/library/tkinter.html)。採主執行緒 UI + Queue / after 模式。
- 瀏覽器 Socket.IO 客戶端安裝與 script 引用：[Socket.IO 官方文件](https://socket.io/docs/v4/client-installation/)。實作時鎖定 Python / JS 相容版本。

後續實作前需確認課程是否限定 raw TCP，以及正式 member.csv 的正確來源 / 順序。其餘已提供建議預設，可先做隔離 fixture 與 domain parity；不需要為了規劃去改正式賽事資料。
