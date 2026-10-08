# Final Project Rules Baseline

日期：2026-10-08。基準為 Node `server.js`，commit `4cf6d802c211e71eb1ca4b532dcf1ece8d81fbbb`。
此文件記錄實際程式行為，不把註解、UI 提示或未實作的功能當成規則。
Phase 0 工作分支是 `codex/final-project-phase1`，只建立 skeleton / fixtures；沒有 domain、server 或 GUI 實作。
`FINAL_PROJECT_MIGRATION.md` 的 detached HEAD 描述是前一輪歷史快照，現在已建立工作分支。

## A. 必須保持一致的 domain rule

### 金額與名額（server.js 155–419）

- 初始預算每教練 1000，隊伍最多 5 位。預算可以由 Admin 增加，不能永遠由 `1000 - history` 推算。
- 金額是非負整數。`getBidError` 本身不做型別轉換；目前 `submit_bid` handler 先 `Number(amount)` 再驗證，這個輸入邊界的 coercion 不是 domain 規則。
- 單次出價最多 500，且不得超過剩餘預算。
- 若本輪得標：`remainingSlotsAfterWin = max(5 - playerCount - 1, 0)`；`reserveForRemaining = remainingSlotsAfterWin * 100`。
- `maxBid = min(500, max(0, budget - reserveForRemaining))`；分區已滿時 `maxBid = 0`，但不能因此認為 0 元出價有效：分區已滿仍拒絕。
- 當且僅當現有隊員數為 1：`secondPlayerMinimum = 301 - 已得標累計花費`。第二位得標後總花費必須 **> 300**，不是 >= 300。
- `minBid = max(minimumBid, secondPlayerMinimum, 0)`；非第二位時 secondPlayerMinimum 為 0。
- 即使顯示 maxBid=0，滿 5 人仍拒絕；Client UI 提示不取代 server 驗證。
- 有效 0 元與沒有出價不同：數字 `0` 可參與得標，`null` / 缺值不參與。JSON fixture 用 null，不使用 undefined / NaN。

### 分區（server.js 170–174、298–324）

| member.csv 的一基位置 | zone | 每教練上限 |
|---|---|---|
| 1–8 | 1 | 1 位 |
| 9–16 | 2 | 1 位 |
| 17–40 | 3 | 3 位 |

按啟動時 MEMBER_NAMES 的順序查 index，不是按圖片、姓名、出價或得標順序。Unknown / 第 41 位起沒有 zone；這是目前邊界行為，未決定是否允許專題自由輸入前不能默默更改。不要猜測正式名單。
現有 `loadMemberNames` 去 BOM、以逗號 / 換行切開、trim / 過濾空白，沒有檢查重複；`indexOf` 使用第一次出現的位置。

### 出價與底價（server.js 277–286、396–419、740–755、769–825）

- 只有 running 接受出價，paused / idle / ended 都拒絕。
- 成功出價覆寫同一教練的本輪金額，允許往上或往下改；最後有效價生效。無效改價不抹掉上一個有效 bid。
- 開始競標先 resetBids（所有教練 null），再對每位合資格者填 `rules.minBid`，只有通過 getBidError 且 <= maxBid 才填。
- 因此預設底價 0、全員空隊伍時，開始會自動產生 8 個 0 元 bid；沒有手動出價仍可能 0 元得標。
- 第二位教練自動填的 minBid 也受累計花費規則影響；不合法或名額已滿者保持 null。
- Admin 改 minimumBid：更新底價，再 pruneInvalidBids。所有數字舊 bid 若在新條件下無效就設 null；合法 bid 留下。
- 調低底價也不把 null 自動補為最低價；自動填價只在 startAuction 發生。
- getBidError 的順序是金額型別 / 負數、底價、預算、zone、隊伍人數、第二位最低價、maxBid。fixture error_category 是測試 adapter 正規化標籤，Node 本身回中文訊息。

### 得標、平手與預算（server.js 421–460、519–555）

- 結算重新檢查所有 bids，跳過 null、缺值、非 number 或不合法金額。
- 最高合法價獲勝，平手候選者按 Object.entries 的插入順序列出；`floor(Math.random() * candidates.length)` 選一位，均勻 RNG 時等機率。
- 沒有合資格候選者：winner / winningAmount 都 null；0 元合法價不屬於流標。
- 結算設 ended、timeLeft=0。若有 winner，扣 winningAmount、追加 `{playerName,winner,amount,time}` history、記錄 lastAwardUndo，匯出 CSV，再存 state / 廣播。
- getWinner 只選結果，不扣款；endAuction 才改預算與 history。Phase 1 harness 必須分清兩種操作。
- 記錄隨機選中結果；重啟不得重抽已完成的同一輪。未來冪等 service 是可靠性補強，不改平手規則。

### 開始、pause / resume、undo（server.js 208–241、608–649）

- start 清上次 lastAwardUndo，設選手、duration / timeLeft、running、winner / amount=null；底價沿用目前值。預設 90 秒，現行允許任意正整數 duration。
- handler 在 running / paused 時拒絕開始另一輪。pause 只從 running 成功，清 timer、保留 timeLeft、改 paused、存檔 / 廣播。
- resume 只從 paused 成功，改 running 並重建 timer，接續 timeLeft，不 reset bids / 預算。
- undo 僅能撤销當前 lastAwardUndo，且最新 history 的 playerName / winner / amount 必須吻合；沒有 snapshot 或不吻合就失敗。
- 成功 undo 清 timer、pop 最後 history、退回金額；設 ended、原選手、timeLeft=0、winner / amount=null、還原該輪 bids；lastAwardUndo=null、更新 CSV / state / 廣播。
- undo 不自動重開、不重新抽選、不恢復舊 minimumBid。下一輪 start 或 reset 會清 undo 機會；undo 不保存於舊 JSON，restart 後不能撤销。

## B. Legacy behavior / 預計在期末版修正

下列是現況紀錄，**不是 Phase 1 domain parity requirement**。應寫獨立修正測試，不要求 Python 複製缺陷。

| 項目 | Legacy behavior | 期末版方向 |
|---|---|---|
| Viewer 洩漏 bids / 目前最高價 | getViewerState 在 status != ended 傳原 bids；viewer.js 顯示金額，viewer-redesign.js 算最高價 / 領先者 / ticker | 公開 projection 不含 bid amounts、最高價或領先者；Coach 只看本人，Admin 可看全部 |
| 0 秒後多一 tick | startAuctionTimer 每秒 -1，只有 <0 才結算；0 時仍 running / 可接受 bid，90 秒約 91 ticks 才結束 | server deadline 到點只結算一次；GUI 倒數僅顯示 |
| restart deadline 已過卻不結算 | running + savedAt 時扣 floor(elapsedSeconds)，若 timeLeft=0 只設 ended，不呼叫 endAuction | 過期 running 依持久化 bids 完成一次結算，扣款 / history / 結果同一交易 |
| reset 不完整取消 timer | resetAuctionHandler 不清 auctionTimer，timer 還會 -1 / 結算；resetBudgetHandler 保留本輪 bids / status / winner | reset 經同一 service，取消 scheduler，明確重置契約與 CSV |
| 身分驗證不足 | join_admin 無 token 就設 isAdmin；start/end 不檢查角色；join_coach 只驗合法 ID；submit_bid 不綁 session ID；可加入多個角色 rooms | 所有命令驗證 session 角色與 coach 身分；不可由 payload 假冒；HTTP 同樣驗證 |
| NAT 不友善 | 每 coach 300ms，IP 2 秒最多 3 次；同教室多人共用 IP 互相擋；Maps 未完整清理 | 以認證 coach 限流為主，IP 輔助且清理過期紀錄 |

### reset 精確現況（server.js 834–881）

HTTP reset 使用 x-admin-token，ADMIN_TOKEN 未設定時退回 dev-token；snake / kebab aliases 指向相同 handler。
reset_budget：清 lastAwardUndo、全體預算回 1000、history=[]、saveState / broadcast；不清 bids、當輪狀態、winner、minimumBid 或 timer，不更新結果 CSV。
reset_auction：清 undo，idle、currentPlayer=null、timeLeft=0、winner / winningAmount=null、minimumBid=0、history=[]、預算回 1000、bids 全 null；saveState / broadcast；不清 timer、不重置 duration、不更新結果 CSV。
舊 reset bat 可能操作正式站，此專題禁止執行。

### timer / restart / storage 精確現況（server.js 46–79、243–275、559–606、651–653）

- timer 使用 setInterval，依 tick 減 1，不是 absolute deadline；每 5 秒 save，每 tick 广播。
- saveState：同步写 state.json.tmp 再 rename；包含 status、currentPlayer、timeLeft、savedAt、bids、budgets、history、winner、winningAmount、minimumBid。
- 不包含 duration、lastAwardUndo、rate-limit Maps 或 timer。JSON 解析錯誤只 log 並回 null，之後初始化預算；這種靜默回初始狀態有資料風險。
- running 恢復有 savedAt 才扣停機秒數；若剩餘 >0 重建 timer；paused 不扣時間。winner 僅保留現有教練 ID；缺少教練 bid / budget 分別補 null / 1000。
- auctionHistory 直接用 restored history 或 []，沒有完整 schema / 參照一致性驗證。
- CSV 含 BOM，每欄一個 coach、每列選手名；沒有金額，不能完整恢復。JSON 才是恢復來源。
- CSV async write 與 JSON sync save 非同一 transaction；儲存失敗只 log，仍可能廣播成功。Python persistence 要隔離路徑並先 commit 再 ACK。

## C. Phase 0 fixture 共用契約與後續條件

`examples/final_project/coach.csv`：8 位假教練；`member.csv`：40 位 Player01–40。均為 **DEMO / TEST ONLY**，不是正式資料。CSV 不放 header / 註解，以免 Node 將它當成名字；標示放在同目錄 README。

`tests/fixtures/auction_cases.json` 是宣告資料，沒有 pytest 或 Node harness 實作：

- schema_version=1，roster 路徑以 repository root 為基準，只指向 examples。
- 每例含 id、classification、initial、steps、expected；initial 注入全部 logical state（包括執行期 lastAwardUndo）。
- operation 是測試語意，例如 validate_bid、select_winner、submit_bid、start_auction、set_minimum_bid、pause、resume、undo_last_award；不是既有 wire API 或已實作的 Python API。
- expected 採部分欄位 assertion；map 指定鍵逐一檢查；history 檢查長度 / 記錄的指定欄位。未指定時間字串，不受 locale 影響。
- error_category 由 adapter 根據 Node 實際 error 分類；不能假稱 Node 已提供 error code。
- rng_values 使用 [0,1) 的 Math.random 語意與相同候選順序。避免 Python random.choice 與 JS 相同 seed 卻不同結果。
- null_no_bid / zero_beats_null 直接注入 bids 以測 getWinner，不經 start；因 start 會自動填底價，不能將兩者混淆。
- Phase 1 harness 必須 stub timer、disk、network，注入假名單；不能直接執行正式 server entrypoint。所有 tests 禁止讀寫 data/ runtime。

課程是否要求 Python socket / raw TCP **尚未提供**。預設架構仍可用 python-socketio；若課程限定 raw TCP，Phase 2 加 TCP adapter，共用同一 service。Phase 0 不實作 adapter，也不安裝未確認的網路依賴。

Phase 1 準備條件：安全工作分支、隔離配置、示範 roster、規則 baseline、宣告案例已備齊。下一階段仍需建立 adapter / tests，案例資料不代表規則已驗證。正式 roster 缺少不阻擋 demo domain parity，但不能宣稱正式名單 / 資料恢復已驗證。

## D. Phase 1 驗證與 intentional differences

Phase 1 已加入 Python models / rules / transitions，以及直接擷取 server.js 白名單函式的隔離 Node harness。
共用 fixture 擴充為 25 例，包含結算與未出價流標；pytest 對 Python 與 Node 的完整可比較 JSON 作相等檢查，並檢查 fixture 的預期欄位。沒有執行正式 server。

再次對照 server.js 後補充一項容易誤讀的邊界：`max(0, budget - reserve)` 只限制最高價；即使 budget < reserve，底價 0、其他條件合法時 0 元仍可接受。baseline 原公式正確，但「必須保留」的文字不完全描述這個 clamp 邊界；目前保持 parity，沒有自行更改遊戲規則。

明確 differences（不作 bug parity）：

- Python amount / minimum / duration 僅接受真正 int，拒絕 bool、float、numeric string；不仿效事件 handler 的 Number() coercion。Node pure validation 對 `1.0` 與 `1` 無法區分，Python 可區分。
- start 拒絕 trim 後空選手，不將空白名當有效選手；未知非空姓名仍保持沒有 zone 的舊規則。
- end 僅從 running / paused 結算；重複 end 已 ended state 為 no-op。Node endAuction 函式本身無保護（其 event handler 有 status check），Python domain 提供此保護。
- 依本輪要求，end 先 prune invalid bids；Node getWinner 跳過 invalid bids，但 endAuction 留它們在 bids。合法結果 / 金額一致，但無效 bid 清除屬 intentional difference，測試另外驗證。
- undo history mismatch 時 Python 拋錯並保留 input state；Node 會清 lastAwardUndo 後回 false。Python 保持失敗命令不修改 input 的純轉移契約。
- Clock 由 caller 注入字串，不在 domain 呼叫 Date / locale；正式 UTC 格式留待 Phase 2。fixture 比較排除未指定的舊時間字串。

既有六項 legacy defects 仍不實作；沒有新增 auth、timer、reset 或 persistence。Parity 僅代表這批可控案例，不代表所有正式賽事資料或傳輸行為均已驗證。
