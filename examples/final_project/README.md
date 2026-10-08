# DEMO / TEST ONLY

此資料完全是專題測試用假名單，不是正式 VALORANT 賽事資料。
coach.csv 有 8 位 Coach01–Coach08（ID 為 coach01–coach08）。
member.csv 有 40 位 Player01–Player40，沒有 header 或註解列，避免被 Node 當成選手。

順序刻意固定：Player01–08 為 zone 1、Player09–16 為 zone 2、Player17–40 為 zone 3。
不可用圖片檔名猜測正式名單，不可將這些資料複製到 data/。
Phase 1 harness 應讀這個目錄並注入獨立測試環境；不得直接啟動 server.js 讀寫正式 data/。
