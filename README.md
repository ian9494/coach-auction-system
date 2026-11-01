# 選手競標系統｜第一次使用指南

這份教學帶你在 **Windows 的同一台電腦**上開啟 Python 專題版，扮演管理員和兩位教練，完成一次選手競標。

第一次使用請從第 1 步開始；已經安裝過的人，直接看「第 3 步：啟動」。

> **Demo 結束後，帳號、密碼的註冊資料與競標紀錄都會刪除。**
> 需要留下展示結果，請在關閉前匯出 CSV。這裡使用示範名單，不會操作正式賽事資料。

## 1. 打開正確的專案資料夾

請確認電腦已安裝 **Python 3.11 以上版本，並包含 Tkinter**。

本次新增的一鍵啟動版位於：

```text
C:\Users\USER\Documents\ChatGPT\特戰英豪比賽 選手競標系統
```

打開「命令提示字元」（CMD），貼上下面這一行並按 Enter：

```cmd
cd /d "C:\Users\USER\Documents\ChatGPT\特戰英豪比賽 選手競標系統"
```

如果你把專案移到其他位置，請把引號內的路徑改成新位置。
正確的資料夾裡應該看得到 `README.md`、`pyproject.toml` 和 `final_project` 資料夾。

> 這份教學的指令使用 CMD。每個指令區塊都可以逐行複製執行，不需要輸入畫面上的 `C:\...>` 提示文字。
> 另一個 `D:\Code\coach-auction-system` 資料夾可能仍是舊版；若看到「必須提供 --root」，先確認目前所在位置。

## 2. 第一次使用：安裝所需套件

在剛才的 CMD 視窗，依序執行：

```cmd
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

第一行會建立這個專案專用的 Python 環境，放在 `.venv` 資料夾。
第二行會下載並安裝專案需要的套件，第一次需要網路，請等它執行完。

安裝成功後會回到可以輸入指令的狀態。**如果出現紅色 ERROR，先處理錯誤，再繼續。**

後面的指令都使用 `.venv\Scripts\python.exe`，確保啟動時用得到剛安裝的套件；不需要另外執行環境啟用腳本。

## 3. 啟動：一個指令開好所有視窗

### Quick Demo：兩位教練

在專案資料夾的 CMD 執行：

```cmd
.venv\Scripts\python.exe -m final_project.demo
```

等幾秒，應該會看到：

| 畫面 | 用途 | 接下來做什麼 |
| --- | --- | --- |
| 原本的 CMD | 在背景運行 Server，讓其他視窗交換資料 | 保持開著 |
| Admin 視窗 | 管理員選人、開始競標、查看出價與結算 | 按「連線」 |
| Coach01 視窗 | 第一位教練登入、出價 | 依第 4 步操作 |
| Coach02 視窗 | 第二位教練登入、出價 | 依第 4 步操作 |
| 瀏覽器 Viewer | 給觀眾看競標畫面 | 保持開著即可 |

Server 會先確認可以正常服務，才開啟其他視窗。視窗可能重疊在一起，可以用工作列切換。

**不要重複執行啟動指令。** 已有一組 Demo 運行時，請先關閉它，再開新的一組。

### Full Demo：八位教練

```cmd
.venv\Scripts\python.exe -m final_project.demo --coaches 8
```

這會開啟 Admin、Coach01～Coach08 和 Viewer。兩位教練版比較適合第一次練習。

如果目前的 `python` 已經裝好專案套件，也可以使用以下簡寫：

```cmd
python -m final_project.demo
python -m final_project.demo --coaches 8
```

`scripts\start_demo.cmd` 使用的也是這個簡寫；若套件只裝在 `.venv`，請使用上面明確指定 `.venv\Scripts\python.exe` 的方式。

## 4. 教練怎麼註冊、登入？

### 建議第一次先練習「註冊 → 登入」

一鍵啟動會幫每個 Coach 視窗填好 **Server URL、Coach ID、邀請碼**，先不要修改這三個欄位。
邀請碼是系統產生的一長串文字，畫面會用星號遮住，不需要自己找或複製。

在 Coach01 視窗，先切到「首次註冊」分頁：

1. 帳號填自己想用的名稱，例如 `coach_demo01`。
2. 密碼填自己設定的展示用密碼，需 10～128 個字元。
3. 「確認密碼」再填一次同樣的密碼。
4. 按「註冊教練席位」，等畫面顯示註冊完成。
5. 註冊成功會自動切到「帳密登入」分頁，再按「登入」，確認畫面顯示「已連線」。

接著在 Coach02 視窗重複上述操作，**使用不同帳號**，例如 `coach_demo02`。

| 欄位 | 規則 |
| --- | --- |
| 帳號 | 4～32 個英文字母、數字或底線；不分大小寫 |
| 密碼 | 10～128 個字元；區分大小寫，請用展示專用密碼 |
| Coach ID | 已建立的教練席位，例如 `coach01`、`coach02` |
| 邀請碼 | 第一次註冊時用來認領對應席位；Launcher 已預填 |

**註冊就是把帳號綁定到一個教練席位。** 例如 `coach_demo01` 註冊到 `coach01`，之後這個帳號就是代表 Coach01 出價。
同一個帳號不能重複註冊，同一席位也只能被認領一次。

### 已經註冊過，要重新登入

在同一次 Demo 還沒結束的情況下，切到「帳密登入」分頁，只需填 **Server URL、帳號、密碼**，再按「登入」。
不需要重新註冊，也不需要填邀請碼或確認密碼；Coach ID 由 Server 依帳號判定，修改欄位不會變成另一位教練。
登入後密碼欄會清空，這是正常行為；按「離線」後再登入，需要重新輸入密碼。

註冊成功後，原本的邀請碼就不能再用來登入該席位，請改用帳密。

### 只想快速試出價，不展示註冊

切到「快速 Demo（未註冊席位）」分頁，在**還沒註冊的席位**，保留一鍵啟動預填的 Coach ID 與邀請碼，帳號密碼留空，直接按「登入」即可。
這是舊 Token 登入方式。若之後想展示註冊，最簡單的方式是結束 Demo，再重新啟動一輪，使用新預填資料操作。

> Admin 不用註冊帳號。Admin 視窗已填好專用 Token，直接按「連線」。
> 若 Admin 離線後 Token 欄已清空，初次練習可先匯出需要的結果，再結束整組 Demo、重新啟動，取得新的預填資料。

## 5. 跟著做：完成第一次競標

1. **Admin 按「連線」**，確認顯示「已連線」，並且出現教練及選手資料。
2. **Coach01、Coach02 登入**，確認兩個視窗都顯示「已連線」。
3. 回到 Admin，從左側下拉選單挑一位選手。
4. 將「競標秒數」改成 `30`，方便第一次操作。
5. 按「開始競標」。Coach 和 Viewer 應該會出現該選手及倒數時間。
6. 在 Coach01 的出價欄輸入 `100`，按「送出／修改出價」。
7. 在 Coach02 輸入 `120`，按「送出／修改出價」。
8. 確認畫面有收到出價結果；若被拒絕，依畫面提示修正金額。倒數結束前可以再次送出修改價格。
9. 等倒數結束，查看得標者、成交價及隊伍名單。若上述兩筆都是有效出價，且無其他更高出價，Coach02 會以 `120` 得標。
10. 回 Admin 挑下一位選手，再按「開始競標」，即可進行下一輪。

Demo 名單有 8 位教練、40 位選手，每隊初始預算為 1000。
開啟兩個 Coach 視窗也能展示，不需要等八個視窗全部登入。

出價是否有效由 Server 判斷，會考慮最低出價、剩餘預算、後續名額預留和隊伍限制；請看 Coach 視窗的「我的預算與規則」。
Admin 能監看全部教練出價；Coach 及觀眾不會看到其他教練尚未結算的密封出價。

GUI 採用米白底與少量綠色重點；登入成功會收起登入區，可按「展開登入設定」再次查看欄位與離線按鈕。斷線後會自動展開。視窗較小時，可用右側捲軸查看底部內容，外觀不需連網載入。

## 6. 管理員常用按鈕

| 按鈕／欄位 | 用途 |
| --- | --- |
| 重新整理選手 | 重新取得可以競標的選手清單 |
| 暫停／繼續 | 暫停倒數，準備好後繼續 |
| 強制結算 | 提早結束目前競標，尚有剩餘時間時會要求確認 |
| 套用 Minimum Bid | 設定最低出價；第一次練習可先保留預設值 |
| 全體增加預算 | 依輸入金額替全部教練增加預算，會要求確認 |
| 撤銷上一筆得標 | 撤銷上一筆得標並恢復相關預算與隊伍，會要求確認 |
| 匯出 Server 結果 CSV | 選擇存檔位置，把目前結果存成 CSV |

有些按鈕只在符合條件時才能按；例如尚未連線或沒有進行中的競標時，部分按鈕會是灰色。
目前沒有一鍵清空所有資料的 Reset 按鈕；想重新練習，請結束 Demo 後重新啟動。

## 7. 看觀眾畫面、匯出結果

Viewer 只用來觀看，不需要登入。瀏覽器沒自動開啟時，可以自己貼上：

[開啟 Viewer](http://127.0.0.1:3001/final-project/viewer.html)

[開啟結果頁](http://127.0.0.1:3001/final-project/results.html)

這些網址需要 Demo 仍在運行，而且要在啟動 Demo 的同一台電腦開啟。
要保存結果，請在 Admin 按「匯出 Server 結果 CSV」，選好檔名與存檔位置，再關閉 Demo。

展示選項（一次選需要的指令執行即可）：

```cmd
.venv\Scripts\python.exe -m final_project.demo --no-browser
.venv\Scripts\python.exe -m final_project.demo --viewer transparent
.venv\Scripts\python.exe -m final_project.demo --viewer colored
.venv\Scripts\python.exe -m final_project.demo --viewer normal
```

`--no-browser`：仍開啟 Server 和 GUI，只是不自動開瀏覽器。
`transparent`：透明背景觀眾頁，供 OBS Browser Source 使用；`colored`：有底色版本；`normal`：一般版本，也是預設值。
OBS 可使用 `http://127.0.0.1:3001/final-project/viewer-transparent.html`，尺寸設為 1920×1080；OBS 實際顯示仍需自行預演。

## 8. 正確關閉 Demo

1. 先匯出想留下的 CSV。
2. 切回啟動 Demo 的 CMD 視窗。
3. 按 **Ctrl+C**，等它回到可以輸入指令的狀態。
4. 瀏覽器分頁不會自動關閉，可以自行關掉。

Launcher 會嘗試停止 Server 和它開啟的所有 GUI，逾時仍未退出的子程序會被強制停止。
單獨關掉一個 GUI 不會讓整組 Demo 當掉；全部 GUI 都關閉後，Launcher 也會結束。
請保留 CMD 視窗，使用 Ctrl+C 結束；強制結束 Launcher 可能讓清理流程來不及執行。

**重新啟動就是全新的一場。** 上次註冊的帳號和競標紀錄不會保留，請重新註冊。

## 9. 出問題時，先看這裡

| 看到的情況 | 可以怎麼做 |
| --- | --- |
| `No module named fastapi` 或其他套件名稱 | 回到第 2 步安裝套件，再使用 `.venv\Scripts\python.exe` 啟動 |
| `No module named final_project` | 目前所在資料夾可能不對，重新執行第 1 步的 `cd /d` 指令 |
| `No module named final_project.emo` | 少打了一個 `d`，正確名稱是 `final_project.demo` |
| 提示必須提供 `--root` | 你執行到舊版程式；確認使用的是本 README 所在、包含一鍵 Launcher 的資料夾 |
| 找不到 `.venv\Scripts\python.exe` | 確認位置正確，並先執行第 2 步建立環境 |
| `python` 無法辨識 | 先安裝 Python，安裝時勾選加入 PATH，重新開 CMD 再試 |
| `No module named tkinter` | 透過 Python 安裝程式補裝 Tcl/Tk 與 IDLE，再重試 |
| `Demo launch failed...`，沒有開出視窗 | 看同一個 CMD 上方有沒有更具體的錯誤；先確認套件已安裝，以及另一組 Demo 是否還開著、占用 3001 |
| Viewer 打不開 | 確認 CMD 還在運行，使用第 7 步的完整網址；結束 Demo 後網址就不能使用 |
| 註冊提示帳號或席位已被使用 | 同一席位只能註冊一次；已有帳號就直接登入，另一席位請使用不同帳號 |
| 登入失敗 | 確認大小寫與密碼；已認領席位請用帳密；重新啟動 Demo 後需重新註冊 |
| 出價按鈕是灰色 | 確認已連線、Admin 已開始競標、沒有暫停、倒數未結束，且這位教練符合出價資格 |
| 出價被拒絕 | 看畫面上的規則與錯誤提示，確認金額、預算和最低出價 |

請不要為了排除問題修改 `.env` 或刪除正式 `data/`。一鍵 Demo 會自行產生展示用 Token，使用獨立的暫存資料。

## 其他文件與開發資訊

一般操作照上面的步驟即可；需要技術細節或保留資料的手動啟動方式，再看以下文件：

- [完整 Demo 與手動啟動說明](docs/FINAL_PROJECT_DEMO.md)：包含 `--root` 離線準備模式和獨立啟動流程。
- [註冊與登入說明](docs/FINAL_PROJECT_REGISTRATION.md)
- [架構與方法](docs/FINAL_PROJECT_ARCHITECTURE.md)
- [訊息循序圖](docs/FINAL_PROJECT_SEQUENCE_DIAGRAMS.md)
- [課程需求對照](docs/FINAL_PROJECT_REQUIREMENTS_CHECKLIST.md)
- [專題文件入口](docs/FINAL_PROJECT_MIGRATION.md)

程式位於 `final_project/`，示範名單位於 `examples/final_project/`。
執行自動測試：

```cmd
.venv\Scripts\python.exe -m pytest -q
```

部分瀏覽器測試需要額外配置，缺少條件時會跳過。測試通過不代表已在你的電腦完成多視窗或 OBS 預演。

原 Node 版的 `server.js`、既有 public 頁面與正式資料仍保留；本教學操作的是 Python 專題 Demo。Node 版依其既有環境設定運行，兩版的 Token 與資料請分開使用。
