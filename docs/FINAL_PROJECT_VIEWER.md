# Phase 5 Viewer / OBS

## 啟動與 URL

依 README 設定 demo tokens 並啟動 Python server，再開以下 URL。Viewer 本身不需要 Admin / Coach Token。

| 用途 | 預設本機 URL |
|---|---|
| 瀏覽器 demo | http://127.0.0.1:3001/final-project/viewer.html |
| 有底色直播版 | http://127.0.0.1:3001/final-project/viewer-colored.html |
| OBS 透明版 | http://127.0.0.1:3001/final-project/viewer-transparent.html |
| 已結算結果 | http://127.0.0.1:3001/final-project/results.html |

更改 server port 時 URL 一起調整；JS 全部使用同 origin，不含正式 domain 或 token。需要由 Python server 開啟頁面，不能直接使用 file://。

## OBS Browser Source

新增 Browser Source，URL 填透明版，建議 width 1920 / height 1080。背景由頁面 CSS 提供透明，上方約 36vh 預留遊戲／攝影機畫面；下方競標區包含選手、倒數及 2 rows × 4 columns Coach 卡片。卡片使用半透明深色面板，卡片外的 body / root / feed-zone 為透明。

Normal 適合瀏覽器查看，Colored 提供漸層底色，Transparent 隱藏頁面導航並留較大的上方透明區。三個 HTML 只選擇模式，共用 viewer.js / viewer.css；沒有三套競標邏輯。未啟動真正 OBS 驗證，本輪以 headless Chromium / Edge 實際載入與 PNG alpha 驗證透明畫布。

## Static architecture / assets

FastAPI 只掛載以下目錄，外層 Socket.IO ASGI 保留 /socket.io transport route：

| URL prefix | Repository directory |
|---|---|
| /final-project | public/final-project |
| /vendor | public/vendor |
| /assets | public/assets |

不掛載整個 public、repository、data 或 legacy admin / coach / viewer。StaticFiles 不跟隨逃出目錄的 symlink，測試包含 encoded traversal；沒有 directory listing。静態檔與 runtime / temp config root 分離，正式 runtime DB 不會因頁面讀取而建立。

Socket.IO JS client 固定 **4.8.1**，從官方 npm archive 取得，與 Python Socket.IO 5 / Engine.IO 4 相容，依官方 [compatibility table](https://python-socketio.readthedocs.io/en/stable/intro.html#version-compatibility)。JS、MIT license、來源及 SHA-256 放在 public/vendor。gitattributes 保留原有 normalization，另指定 vendor bytes 不轉換換行，確保 Windows checkout 後 hash 一致。runtime 沒有 CDN、Google Fonts 或 Node /socket.io/socket.io.js 依賴，可離線 demo。

沿用 assets/coaches、assets/players、assets/frames：Coach 圖片用 coach.id，Player 圖片用 player name，URI encode 後依序嘗試 jpg / jpeg / png。不存在時落到本地 fallback-avatar.svg，有限次重試，不反覆錯誤迴圈。Demo Coach01 / Player01 沒有正式賽事頭像，使用 fallback。沒有修改或重建原圖片。

## State contract / 密封資訊

viewer_state 與 join snapshot 是唯一競標 authority。renderer 保存明確 allowlist：status、current_player、duration、time_left、remaining_seconds、deadline_utc、minimum_bid、coach id / name、teams、budgets、結算後 winner / winning_amount、version / round_id。未知額外欄位不保存、不 dump 到 DOM。

running / paused 只顯示選手、狀態、倒數、Minimum Bid、各 Coach 名稱／頭像／預算／隊伍／人數，不顯示出價、領先者、最高金額或 submitted flag。Server 沒有提供 submitted flag，本輪也沒有推導。

ended 才公布 winner / winning amount，並 highlight 得標 Coach。下一輪清除 highlight，歷史選手保留在 teams。沒有得標者顯示「本輪無得標者」。結果頁每 3 秒只讀 /api/results，不读 CSV，也不增加 HTTP mutation。

名稱一律用 textContent / createElement；圖片位置與名稱亦分離。HTML 注入測試確認帶有 img / script / b 字串的名稱只作文字顯示。

## Reconnect / versions / countdown

每次 Socket.IO connect 都重新 join_viewer，join ACK 提供完整 snapshot 重新建立畫面。join timeout / failure 可在同連線重試；舊 sid 的延遲 join ACK 不更新連線狀態。disconnect 保留最後畫面並顯示離線，正常 transport 中斷會自動重連，server disconnect 也會重新 connect。

latest_version 只由公開 snapshot 推進。舊 version 忽略；相同 version 且較舊倒數的 snapshot 也忽略。新 round 清除目前 winner highlight。若 server 改用全新空 DB、version 從頭開始，請重新載入頁面；Client 不會為 reconnect 任意重設版本排序。

有 deadline 時用 deadline − browser time 做 display；否則從最新 remaining / time_left locally tick。paused 倒數不變，到 0 仍等待 server ended snapshot，Viewer 不触發結算。本機時間偏差可能影響視覺倒數，不影響 Server 判定。

## 測試

核心 pytest 不需要 OBS 或瀏覽器：靜態檔路由、legacy / private paths 不公開、vendor hash / license、DOM source、public projection / JS model 的版本與倒數都有測試。Node 不可用時只略過 JS executable contract；HTTP / Python tests 仍可執行。

額外 browser smoke 使用 Playwright（可使用現有工具環境），配置：

```powershell
$env:FINAL_PROJECT_PLAYWRIGHT_MODULE = '<installed playwright package directory>'
# 可選：改用本機 Edge / Chromium；未設定則使用 Playwright 已安裝的 Chromium。
$env:FINAL_PROJECT_BROWSER_EXECUTABLE = '<browser executable path>'
.\.venv\Scripts\python.exe -m pytest tests/test_viewer_browser.py -q
```

測試自行建立 localhost ephemeral server、temp DB / tokens，把測試憑證經 stdin 傳給 scripts/smoke_final_viewer.cjs；不將 token 放在 command line、頁面 URL 或 log。測試 Browser 與 Admin / Coach 驅動頁分開，Viewer 的 WebSocket frame 捕捉包含實際 viewer_state；逐層確認無 bids / allBids / myBid / private rules / leader / highest amount。running 的 winner / amount 為 null。

Browser smoke 驗證 Player01 → 兩 Coach 出價 → pause / resume → end → winner / amount / results → 下一輪 → 重連。並驗證透明頁面沒有 pageerror、三個背景 computed transparent、1920×1080 的 2×4 layout、圖片 fallback 可完成、畫布第一個空白 pixel alpha=0、外部 runtime request=0、惡意名稱不執行與未知欄位不顯示。測試時注入與 FakeClock 一致的 browser display time。

最終原有 246 tests 加 30 個 Viewer cases，共 276；連續兩次完整 pytest 都通過，包含實際 Edge browser smoke，未跳過瀏覽器測試。未處理的背景 thread exception 亦設為測試錯誤。

## 限制與 Phase 6

僅驗證目前本機 Edge / Chromium；未做真正 OBS、其他瀏覽器或跨機部署驗證。Phase 6 將 AbortSignal.timeout 換成 AbortController + setTimeout，透明頁以 html class 取代 :has；OBS CEF 仍需實機 smoke。results 最多約 3 秒更新延遲。缺少圖片會有有限次 404 後 fallback，屬預期。

Phase 6 wheel 已封裝 static／vendor／assets，installed runtime 由 final_project/resources.py 找到 prefix 下的只讀資產；驗證與步驟見 [Demo](FINAL_PROJECT_DEMO.md)。沒有新增 raw TCP、TLS、Cloudflare、production deployment、roster import 或 reset。legacy Viewer / results 全部保留不動，Python domain 與 Coach / Admin GUI 亦未修改。
