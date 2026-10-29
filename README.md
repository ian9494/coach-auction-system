## Quick Demo

先安裝依賴：`python -m pip install -e ".[dev]"`（Python 3.11+，需 Tkinter）。

```sh
python -m final_project.demo
```

自動啟動 localhost:3001 Python Server、Admin、Coach01、Coach02 與預設瀏覽器 Viewer。
GUI 已預填 URL／席位／token，按連線或登入即可。Windows 也可執行 `scripts/start_demo.cmd`。

## Full Demo

```sh
python -m final_project.demo --coaches 8
```

`--coaches 1–8`（預設 2）；`--no-browser` 關閉自動開瀏覽器；
`--viewer normal|transparent|colored` 選擇 Viewer。
Server 通過 `/health` polling 後才啟動 GUI／Viewer，20 秒內未就緒便清理並退出。
3001 已被占用時啟動失敗，請先停止舊 Server。

每次使用獨立暫存資料目錄與九個不同的 DEMO ONLY token，透過 child environment 傳入，
不讀寫 `.env`，不將 token 放入命令列或寫入憑證檔。此模式的競標與註冊資料於結束後刪除。
Ctrl+C、Server 結束或全部 GUI 關閉會清理所有 child processes；單獨關閉 GUI 可繼續展示。
請保留 launcher 終端；強制終止 launcher（例如工作管理員結束程序）無法保證執行清理。
瀏覽器由系統管理，不會在清理時關閉。
原有 `python -m final_project.demo --root <新目錄>` 仍保留為離線準備模式。

# Coach Auction System

VALORANT 社群賽事密封競標系統；保留 Node 正式版，另有大學網路程式設計 Python 專題版。

## Final Project Version

Python ASGI／Socket.IO Server + Tkinter Admin／Coach GUI + Web Viewer／OBS。多人密封出價與改價、倒數、pause/resume、預算／zone 規則、隨機平手抽選、undo、結果 CSV export、SQLite 與重連恢復。Server 為唯一狀態來源。

Python 3.11+（含 Tkinter），PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$demoRoot = Join-Path $PWD ('runtime/final_project/demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m final_project.demo --root $demoRoot
.\scripts\start_final_server.ps1 -DemoRoot $demoRoot -Config (Join-Path $demoRoot 'config.json')
```

其他終端執行 `.\scripts\start_final_admin.ps1`／`.\scripts\start_final_coach.ps1`。Coach GUI 先用邀請碼註冊，再以帳號密碼登入；Admin 使用 token。本機邀請碼／token 在 demoRoot 的 runtime/final_project/demo_tokens.json，不提交 Git。

預設 127.0.0.1:3001；Server 可用 FINAL_PROJECT_HOST／FINAL_PROJECT_PORT 覆寫，禁止 3000。Viewer `/final-project/viewer.html`，OBS `/final-project/viewer-transparent.html`（1920×1080），結果 `/final-project/results.html`。

程式 final_project/；DEMO / TEST ONLY 名單 examples/final_project/ 有 8 教練／40 選手，每隊初始 1000。正式 data/ 不供專題測試。Admin 90 秒或 10 秒 quick demo。支援邀請碼認領 Coach 席位、帳號密碼註冊／登入；沒有在線 roster import、presence、reset command；新展示建立新 demoRoot。

測試 `.\.venv\Scripts\python.exe -m pytest -q`。Browser smoke 需配置 Node Playwright／Edge，否則 skip；交付驗證包含 browser。完整步驟及 wheel 安裝見 [Demo](docs/FINAL_PROJECT_DEMO.md)。

報告素材：[架構與方法](docs/FINAL_PROJECT_ARCHITECTURE.md)、[訊息循序圖](docs/FINAL_PROJECT_SEQUENCE_DIAGRAMS.md)、[課程需求對照](docs/FINAL_PROJECT_REQUIREMENTS_CHECKLIST.md)、[文件入口](docs/FINAL_PROJECT_MIGRATION.md)。已核對課程 PDF，未要求 raw TCP；[註冊操作](docs/FINAL_PROJECT_REGISTRATION.md) 已補齊。

## Legacy Node Version

原 server.js、public/admin.*／coach.* 與 legacy Viewer 保留，核心未因專題交付改寫。本輪不部署、不接正式站、不覆寫正式資料。原 Node 版使用既有 package.json 與正式環境設定，勿混用 Python demo token／runtime。
