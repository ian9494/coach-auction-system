# coach-auction-system
A coach draft auction system for community tournament

## Final Project Development

原本 Node 版本仍保留。Python 專題程式位於 `final_project/`，已完成 domain、service／SQLite／deadline 與 Phase 2B ASGI／Socket.IO／HTTP；尚無 GUI 或 Viewer 整合。
DEMO / TEST ONLY 名單在 `examples/final_project/`；正式 `data/` 不供專題測試使用。
專題預設 port 為 3001，runtime 位於 `runtime/final_project/`；設定範例為 `config/final_project.example.json`。
規則與已知缺陷見 `docs/FINAL_PROJECT_RULES_BASELINE.md`，規劃見 `FINAL_PROJECT_MIGRATION.md`。
Service、持久化與測試方式見 `docs/FINAL_PROJECT_SERVICE.md`。
Token 設定、啟動與通訊協定見 `docs/FINAL_PROJECT_PROTOCOL.md`；未設定憑證時拒絕啟動。
