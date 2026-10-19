# Coach 註冊與帳號登入

Coach GUI 現在提供真正的註冊、登入與離線介面。Server 維持八個預先建立的教練席位；使用者註冊自己的帳號密碼並認領其中一席，不新增隊伍、不提供 Admin 自行註冊，也不改動競標核心。

## 操作

1. 依 Demo 文件建立新的隔離 demo root，啟動 Server／Coach GUI。
2. 填 Server URL、Coach ID（例如 coach01）、該席位邀請碼。邀請碼為 demo_tokens.json 的 coach_tokens.coach01；每席應私下分配給對應使用者。
3. 填帳號（4–32 個 ASCII 英數或底線）、密碼（10–128 字元）及確認密碼，按「註冊教練席位」。
4. 成功後按「登入」。此後只需 URL、帳號密碼，Server 自行決定 Coach ID；GUI 的 Coach ID 不會指定登入權限。
5. 離線後重新填密碼登入；網路短暫中斷則背景 worker 以本次登入資料重新驗證並恢復完整 snapshot，不自動重送競標命令。

帳號不分大小寫、密碼區分大小寫。同一帳號或席位不可重複認領；無效邀請碼、非法格式與多餘欄位會拒絕。註冊 ACK 遺失時先嘗試登入，不自動重送或推測失敗。

認領成功後原 Coach token／邀請碼不能再登入或出價；該席位原有 token 連線會被中斷，避免繼續收到私人出價資訊。尚未認領席位仍允許原 token 登入以相容既有 demo／測試；這條路徑不是註冊展示流程。Admin token 登入不變。

## 協定

匿名 Socket.IO 連線發送：

```text
register_coach {coachId, invite, username, password}
ACK {ok, error_code, message, version, round_id, request_id:null,
     payload:{coachId, username}}  // payload 僅在成功時含身份
```

註冊不自動加入角色 room，不產生 snapshot／競標 version 變動。錯誤包括 INVALID_PAYLOAD、INVALID_INVITE、INVALID_ACCOUNT、ACCOUNT_OR_SEAT_TAKEN、FORBIDDEN；連線失敗 GUI 顯示 REGISTRATION_UNCONFIRMED。

登入：`join_coach {username, password}`。成功後仍發 coach_state 與 payload.snapshot；身份由 DB 決定。帳號不存在、密碼不符回 UNAUTHORIZED，不區分原因。原 join_coach {coachId, token} 僅對未認領席位有效。

## 儲存與安全範圍

專題同一 SQLite 新增 coach_accounts 表，獨立於 auction snapshot，舊 schema_version 與 snapshot 格式不變；既有 DB 啟動時非破壞性建立表。username、唯一 coach_id、16-byte 隨機 salt、scrypt hash 存於專題 DB。scrypt 參數 N=16384、r=8、p=1；不儲存明文密碼或邀請碼。DB 的 UNIQUE 約束防止同時註冊重複帳號／席位。

hash 透過 asyncio.to_thread，並行上限四個，避免阻塞競標 event loop；DB 操作仍由 event loop thread 執行。帳號資料不進入 auction snapshot、ACK history、Viewer 或公開 API；密碼、token 不進 repr／應用日誌。

GUI 註冊使用獨立背景 worker、Queue 回傳結果，不從網路 thread 更新 Tk。登入密碼僅於連線 worker 記憶體保存以供重連，離線後不寫本機憑證檔。

範圍是課堂／受控網路 demo。沒有密碼重設、帳號刪除、郵件驗證、持久化登入 session、完整反暴力登入或 TLS 部署。外網使用前需另行設計；本輪不連正式站。重新展示請建全新 demo root，不直接改 DB 或刪除已運作帳號。

## 驗證

測試涵蓋邀請碼、格式、密碼雜湊、大小寫帳號、帳號／席位競態、權限、舊 token 連線撤銷、斷線／重連、Server 重啟、私人資訊、背景 transport，以及實際 Tkinter 註冊→登入→離線。舊競標／Edge smoke 繼續回歸。

2026-10-19 驗證：完整 pytest 連續兩次各 298 passed，包含 Edge browser 與實際 Tkinter callback／網路流程，沒有 skip。30 個模組 import、wheel build／安裝、repository 外 cwd 的 installed registration/login smoke 與 git diff --check 均成功。修正兩個既有測試問題：ACK 等待器保留先到 snapshot；HTTP privacy 依欄位契約檢查，避免隨機 UUID 含出價數字造成誤判。競標 domain／AuctionService、legacy 程式及正式 data/ 未修改。
