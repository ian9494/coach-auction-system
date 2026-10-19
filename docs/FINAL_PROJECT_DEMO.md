# Final Project 展示與交付

## 準備（PowerShell／Python 3.11+ 含 Tkinter）

DEMO / TEST ONLY：8 位 Coach01–08、40 位 Player01–40、每隊初始 1000。選手順序決定 zone：1–8／9–16／17–40；正式 data/ 不供測試。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$demoRoot = Join-Path $PWD ('runtime/final_project/demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m final_project.demo --root $demoRoot
$demoRoot  # 記下完整路徑給 Server 終端
$credentials = Get-Content -Raw (Join-Path $demoRoot 'runtime/final_project/demo_tokens.json') | ConvertFrom-Json
```

工具只接受不存在的新目錄，不覆寫舊 session。隨機 token 只寫本機隔離檔、不印出內容；Windows 權限繼承目錄 ACL。不要分享或 commit 憑證。重新展示建立新的 demoRoot，舊 DB／history／request ACK 不會混入；沒有在線 reset command。

## 啟動

Terminal 1 使用上一步的實際 demoRoot：

```powershell
.\scripts\start_final_server.ps1 -DemoRoot $demoRoot -Config (Join-Path $demoRoot 'config.json')
```

預設 127.0.0.1:3001；可先設定 FINAL_PROJECT_HOST／FINAL_PROJECT_PORT，禁止 3000。LAN 用 0.0.0.0，Client 改為電腦 LAN IP，防火牆須允許；沒有 TLS，僅受控 demo 網路。不連正式站。

Terminal 2：`.\scripts\start_final_admin.ps1`，GUI 輸入 URL 和 Admin token。準備終端可 `Set-Clipboard $credentials.admin_token` 後貼入遮罩欄。

Terminal 3+：`.\scripts\start_final_coach.ps1`，開 2–8 個 GUI，以 coach01–coach08 及各自 token 登入，例如 `Set-Clipboard $credentials.coach_tokens.coach01`。不用改 source。

Viewer：`http://127.0.0.1:3001/final-project/viewer.html`；結果 `/final-project/results.html`。換 port 時各 URL 一起更新。Ctrl+C 停止 Server；運行中不得刪 DB。Server 不要求八人全員在線、沒有在線人數 UI。

## 展示流程

1. Admin／Coach 登入，開 Viewer，說明預算、5 slot 與 zone。
2. Admin 選 Player17，duration 90，Start；quick demo 填 10。
3. Coach01 出價 200、Coach02 250、Coach01 改為 300。Admin 見全部出價，Coach 只見自己，Viewer 不見競標中價格。
4. Pause，嘗試出價應拒絕；resume。Force end 有確認，或等倒數結算。
5. 顯示 winner、team、budget；undo 後退回隊員／預算，沒有重新開局。
6. 全體加預算如 100，確認更新。下一輪選 Player18，出價並結算。
7. Admin export results：來自 Server 已結算結果；被 undo 的第一筆不留在 CSV。
8. Coach 斷線再登入，恢復 myBid／倒數／預算。Viewer 重新整理或網路恢復後取得 snapshot。
9. 故障展示：停止 Server，再用同一 demoRoot 啟動。GUI 顯示離線後重新認證；running deadline 已過期即結算一次，paused 保留。Client 不自動重送不確定命令，先檢查 snapshot。

Player01／Player09 可展示 zone1／2。規則詳見 [baseline](FINAL_PROJECT_RULES_BASELINE.md)。Coach 席位帳密註冊已實作（見下方補充）；在線 roster import、安全 reset、presence 未實作；新名單只能在新 session 啟動前準備，不更改已運作 roster 順序。

## OBS

Browser Source：`http://127.0.0.1:3001/final-project/viewer-transparent.html`，1920×1080；有底色版 viewer-colored.html。本地 vendor 不需 CDN。Edge 驗證透明 PNG alpha、排版、重連與密封資料；移除 AbortSignal.timeout／:has 必要依賴。OBS CEF 尚需實機 smoke，沒有宣稱已測 OBS；GUI 多視窗亦建議課前預演。

## 驗證與獨立 wheel

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q
python -m pip wheel . --no-deps --wheel-dir .pytest_cache/delivery-wheels
python -m venv .pytest_cache/delivery-venv
.\.pytest_cache\delivery-venv\Scripts\python.exe -m pip install .pytest_cache/delivery-wheels/coach_auction_final_project-0.0.1-py3-none-any.whl
.\.pytest_cache\delivery-venv\Scripts\python.exe scripts/smoke_installed_final_project.py
```

Browser pytest 需 FINAL_PROJECT_PLAYWRIGHT_MODULE 指向 Node Playwright、FINAL_PROJECT_BROWSER_EXECUTABLE 指向 Edge，否則 browser case skip；交付驗證明確配置。詳見 [Viewer](FINAL_PROJECT_VIEWER.md)。

wheel 含 Viewer、fallback、vendor/license、圖片、demo roster/config，約 77 MB，圖片造成大體積。installed smoke 強制檢查非 editable import 與 prefix 下的資產，啟動 ephemeral localhost Server 驗證 auth／密封 bid／結算／HTTP results／隔離 SQLite；不發布 PyPI。

一般 installed CLI：`python -m final_project.demo --root <新絕對目錄>`，再 `python -m final_project.server.app --demo-root <該目錄> --config <該目錄/config.json>`；GUI 用 `python -m final_project.client.admin_app`／coach_app。資產只讀，runtime 在可寫 demoRoot。

Acceptance 重用 tests/test_integration_lifecycle.py：1 Admin、8 Coach、1 Viewer、兩輪結算（第一輪 undo），改價、pause/resume、重連、lost ACK replay、舊 round 拒絕、HTTP／CSV export、Viewer privacy。tests/test_delivery.py 驗證 demo isolation／env port。

## Phase 6 交付驗證（2026-10-11）

最終完整 pytest 連續兩次各 285 passed（含 Edge browser，無 skip）；28 個 Python modules import 成功、PowerShell Server script syntax 成功。wheel 101 entries，無 credentials／SQLite runtime；全新 venv 安裝及 repository 外 cwd 的 installed-package smoke 通過。wheel 約 77 MB，保留既有圖片。git diff --check 成功，legacy server／GUI／Viewer 與 data/ 無改動。課程註冊語意／raw TCP 須確認；OBS CEF、實機多 GUI／跨機網路仍須課前預演。

## 註冊展示補充

原 coach_tokens 的值現在也作為一次性席位邀請碼。Coach GUI 填 Coach ID／邀請碼／帳號／密碼／確認密碼，按註冊，再按登入。認領後原 token 失效，重連／重啟以帳密登入。請用全新 demo root 展示，完整流程見 [註冊](FINAL_PROJECT_REGISTRATION.md)。上方 Phase 6 的 285 tests 為新增註冊前的歷史驗證紀錄。
