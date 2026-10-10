# coach-auction-system
A coach draft auction system for community tournament

## Final Project Development

原本 Node 版本仍保留。Python 專題程式位於 `final_project/`，已完成 domain、service／SQLite／deadline、ASGI／Socket.IO／HTTP、整合驗證、Tkinter Coach／Admin GUI 與專題 Viewer／OBS overlay。
DEMO / TEST ONLY 名單在 `examples/final_project/`；正式 `data/` 不供專題測試使用。
專題預設 port 為 3001，runtime 位於 `runtime/final_project/`；設定範例為 `config/final_project.example.json`。
規則與已知缺陷見 `docs/FINAL_PROJECT_RULES_BASELINE.md`，規劃見 `FINAL_PROJECT_MIGRATION.md`。
Service、持久化與測試方式見 `docs/FINAL_PROJECT_SERVICE.md`。
Token 設定、啟動與通訊協定見 `docs/FINAL_PROJECT_PROTOCOL.md`；未設定憑證時拒絕啟動。

本機 Coach demo（PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:FINAL_PROJECT_ADMIN_TOKEN = [guid]::NewGuid().ToString('N')
1..8 | ForEach-Object {
    $key = 'FINAL_PROJECT_COACH_TOKEN_COACH{0:00}' -f $_
    [Environment]::SetEnvironmentVariable($key, [guid]::NewGuid().ToString('N'), 'Process')
}
# 複製本機 Coach01 demo token，到 GUI 的遮罩 Token 欄貼上。
Set-Clipboard $env:FINAL_PROJECT_COACH_TOKEN_COACH01
.\.venv\Scripts\python.exe -m final_project.server.app
```

另一個終端執行 `.\scripts\start_final_coach.ps1`，以 `coach01` 登入本機 server。
demo server 使用 examples 名單與隔離的 `runtime/final_project/`，不使用正式 data。
Coach 啟動、threading、重連與版本排序見 [Coach Client 說明](docs/FINAL_PROJECT_COACH_CLIENT.md)。

Admin 執行 `.\scripts\start_final_admin.ps1`，使用 server 對應的 Admin Token 登入；可控制競標、全體加預算、undo 與匯出結果 CSV。
控制、二次確認與目前支援範圍見 [Admin Client 說明](docs/FINAL_PROJECT_ADMIN_CLIENT.md)。Roster import 與安全 reset 留後續階段。

啟動 Python server 後，瀏覽器開 `http://127.0.0.1:3001/final-project/viewer.html`。
OBS Browser Source 使用 `http://127.0.0.1:3001/final-project/viewer-transparent.html`（1920×1080）；有底色版本為 `viewer-colored.html`，結果頁為 `results.html`。
Viewer 使用本地 vendor JS，可離線 demo；running 不傳送 private bid。URL、靜態檔、透明模式與 browser smoke 見 [Viewer／OBS 說明](docs/FINAL_PROJECT_VIEWER.md)。
