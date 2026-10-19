# 課程需求對照

已核對使用者提供的兩頁課程 PDF，依 Server 1–8、Client 1–5 要求整理；多組語意仍依本專題情境說明。檔案路徑均相對 repository。

| 要求 | 判定 | 程式／實際行為 | 展示方式 |
|---|---|---|---|
| Server 1 管理註冊、登入、離開 | 已符合 | `server/events.py`、`storage/accounts.py`：邀請碼認領 Coach 席位、註冊帳密、scrypt hash／SQLite、登入與 disconnect 清理 | GUI 註冊→登入→離線；錯誤密碼／重複認領拒絕 |
| Server 2 若需人數，告知缺多少 | 不適用 | 條件式要求：Admin 決定開局，1–8 Coach 可參與，不強制全員在線；沒有 presence count | 僅兩位 Coach 登入仍能競標 |
| Server 3 初始化 | 已符合 | `server/app.py`、`storage/repository.py`：載入 roster／auth，建立或恢復 SQLite snapshot／deadline | 新 session 為 idle、每隊 1000；重啟恢復 |
| Server 4 仲裁者 | 已符合 | `server/service.py`、`domain/transitions.py`：序列化命令、驗證、結算、平手抽選 | 出價／結算後 winner、預算、隊員更新 |
| Server 5 控制成員動作 | 已符合 | `server/events.py`、`server/schemas.py`、domain：角色、round、預算與區域規則驗證 | Coach 無管理權；暫停／非法出價被拒 |
| Server 6 轉送動作 | 已符合 | `server/projections.py`、`server/events.py`：依角色 room 傳 snapshot；密封價格只給本人及 Admin | Admin 見所有 bid，Coach 只見自己，Viewer 不見競標中價格 |
| Server 7 維護各組資訊 | 已符合 | `domain/models.py`、service、SQLite：8 隊 team／budget 與共同一場競標 | 多隊出價；結算／undo 後資訊同步。沒有多個獨立賽事房間 |
| Server 8 偵測異常離線 | 已符合 | Socket.IO／Engine.IO heartbeat 與 `events.py` disconnect 清理 | 中斷 Coach 網路／程序，重連必須重新 join；偵測須等 heartbeat，沒有在線名單 UI |
| Client 1 GUI | 已符合 | `client/coach_app.py`、`client/admin_app.py`：Tkinter | 開啟兩種 GUI |
| Client 2 註冊、登入、離開介面 | 已符合 | `client/coach_app.py`、`client/registration.py`、`client/transport.py`：註冊／帳密登入／離線與重連 | 填 Coach ID／邀請碼／帳密，註冊後登入；Admin 保留預設身份 |
| Client 3 接收其他動作 | 已符合 | `client/transport.py`、view model、Web Viewer：接收角色 snapshot | 開局／暫停／隊員／預算同步；不展示別人的密封 bid |
| Client 4 使用者動作與檢查 | 已符合 | GUI、view model：基本格式檢查後送命令；Server 最終裁決 | 改價、非法金額、Admin 管理命令 |
| Client 5 偵測 Server 中斷 | 已符合 | `client/transport.py`：狀態提示、重連、重新認證、完整 snapshot | 停止再啟動 demo server；確認恢復且不自動重送不確定命令 |

## 判定邊界

註冊現在由 Client 自行建立帳號密碼並認領預設 Coach 席位，詳見 [註冊文件](FINAL_PROJECT_REGISTRATION.md)。不開放自行註冊 Admin 或新增隊伍。PDF 要求 Python 與 Client GUI，沒有指定 raw TCP 或必須直接使用 socket；目前 python-socketio 符合通訊方式的文字要求。Server 7 的八隊由同一場競標管理，不宣稱支援多個獨立賽事房間。

未新增 presence tracking：加入在線身份、重複登入、重連競態與 UI 會增加交付風險，且 Server 2 是條件式要求。未加入 reset command 或線上 CSV import；使用全新的隔離 session，見 [Demo](FINAL_PROJECT_DEMO.md)。
