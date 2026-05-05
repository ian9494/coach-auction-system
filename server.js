// server.js
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");
const fs = require("fs");

const STATE_FILE = path.join(__dirname, "data", "state.json");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, "public")));

// 持久化狀態函式
function saveState() {
  const dataToSave = {
    status: state.status === "running" ? "ended" : state.status, // 重放時如果不為 idle/ended 就強制結束
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    bids: state.bids,
    budgets: coachBudgets,
    history: auctionHistory,
    winner: state.winner,
    winningAmount: state.winningAmount
  };

  const tmpFile = STATE_FILE + ".tmp";
  try {
    fs.writeFileSync(tmpFile, JSON.stringify(dataToSave, null, 2));
    fs.renameSync(tmpFile, STATE_FILE);
  } catch (err) {
    console.error("Error saving state:", err);
  }
}

function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      const data = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
      
      state.status = data.status === "running" ? "ended" : data.status;
      state.currentPlayer = data.currentPlayer;
      state.timeLeft = data.timeLeft;
      state.winner = data.winner;
      state.winningAmount = data.winningAmount;
      state.bids = data.bids || {};
      
      for (const coachId of COACHES) {
        coachBudgets[coachId] = data.budgets && data.budgets[coachId] !== undefined 
          ? data.budgets[coachId] 
          : INITIAL_BUDGET;
      }
      
      auctionHistory = data.history || [];
      return true;
    }
  } catch (err) {
    console.error("Error loading state:", err);
  }
  return false;
}

app.get("/", (req, res) => {
  res.redirect("/admin.html");
});

// Twitch Bot 與前端獲取成交紀錄 API (從 auctionHistory 獲取完整資訊，而非單純從 CSV)
app.get("/api/results", (req, res) => {
  // 為了讓 Twitch bot 和展示頁面能拿到金額，我們優先從內存的 auctionHistory 讀取
  // 如果伺服器剛重啟，auctionHistory 會從 state.json 加載回來
  const results = auctionHistory.map(h => ({
    playerName: h.playerName,
    coachId: h.winner,
    amount: h.amount
  }));
  res.json(results);
});

app.get("/api/members", (req, res) => {
  const filePath = path.join(__dirname, "data", "member.csv");
  fs.readFile(filePath, "utf8", (err, data) => {
    if (err) {
      console.error("Error reading member.csv:", err);
      return res.status(500).json({ error: "Failed to read member list" });
    }
    // 解析 CSV 格式 (逗號與換行) 並過濾掉空字串
    const members = data
      .split(/[\n\r,]+/)
      .map((m) => m.trim())
      .filter((m) => m !== "");
    
    // 過濾掉已經標出去的選手
    const soldNames = auctionHistory.map(h => h.playerName);
    const availableMembers = members.filter(m => !soldNames.includes(m));
    
    res.json(availableMembers);
  });
});

const ADMIN_TOKEN = process.env.ADMIN_TOKEN || "dev-token"; // 管理員驗證令牌，實際使用時應該從環境變數或安全存儲中獲取

// 輸入教練列表，實際使用時可從資料庫或其他來源獲取
const COACHES = [
  "coach1",
  "coach2",
  "coach3",
  "coach4",
  "coach5",
  "coach6",
  "coach7",
  "coach8",
];

const INITIAL_BUDGET = 1000; // 每位教練的初始預算
// 儲存每位教練的預算狀態，格式為 { coachId: remainingBudget }
const coachBudgets = {};

// 重置所有教練的預算狀態
function resetBudgets() {
  for (const coach of COACHES) {
    coachBudgets[coach] = INITIAL_BUDGET;
    }
}

let auctionHistory = []; // 儲存已得標的選手資訊

if (!loadState()) {
  resetBudgets(); // 初始化預算狀態
}

let auctionTimer = null; // 競標計時器

// 競標狀態
const state = {
  status: "idle", // 競標狀態：idle | running | ended
  currentPlayer: null, // 當前競標的球員名稱
  timeLeft: 0, // 剩餘時間（秒）
  duration: 90, // 競標總時間（秒）
  bids: {}, // 教練出價狀態，格式為 { coachId: bidAmount }
  winner: null, // 贏家教練ID
  winningAmount: null, // 贏家出價金額
};

// 重置所有教練的出價狀態
function resetBids() {
  state.bids = {};
  for (const coach of COACHES) {
    state.bids[coach] = null;
  }
}

resetBids(); // 初始化出價狀態

// 計算競標結果，找出最高出價的教練 return:得標教練ID和出價金額
function getWinner() {
  let highestAmount = -1;
  let candidates = [];

  // 獲取目前各隊人數
  const teamCounts = {};
  COACHES.forEach(c => teamCounts[c] = auctionHistory.filter(h => h.winner === c).length);

  for (const [coachId, amount] of Object.entries(state.bids)) {
    // 嚴格判斷數值，處理 0 元出價比 null (無出價) 優先
    if (amount === null || amount === undefined || typeof amount !== "number") continue;
    
    // 檢查該隊是否已滿 5 人
    if (teamCounts[coachId] >= 5) continue;

    if (amount > highestAmount) {
      highestAmount = amount;
      candidates = [coachId];
    } else if (amount === highestAmount && amount !== -1) {
      candidates.push(coachId);
    }
  }

  if (candidates.length === 0) {
    return {
      winner: null,
      winningAmount: null,
    };
  }

  // 從符合資格（最高價且未滿員）的人中隨機選出一個
  const randomIndex = Math.floor(Math.random() * candidates.length);
  const winner = candidates[randomIndex];

  return {
    winner,
    winningAmount: highestAmount,
  };
}

// 獲取要傳給觀眾端的狀態，包含競標狀態、當前球員、剩餘時間、出價狀態等資訊
function getViewerState() {
  const baseState = {
    status: state.status,
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    winner: state.winner,
    winningAmount: state.winningAmount,
    budgets: coachBudgets,
    history: auctionHistory, // 確保 history 隨時都有傳出去
  };

  if (state.status !== "ended") {
    baseState.bids = state.bids;
  }

  return baseState;
}

// 獲取要傳給教練端的狀態，包含競標狀態、當前球員、剩餘時間、出價狀態等資訊
function getCoachState(coachId) {
  return {
    status: state.status,
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    myBid: state.bids[coachId] ?? null,
    budget: coachBudgets[coachId],
    winner: state.status === "ended" ? state.winner : null,
    winningAmount: state.status === "ended" ? state.winningAmount : null,
    history: auctionHistory, // 新增這行：讓教練端也收得到得標歷史
  };
}

// 廣播狀態更新給所有連接的客戶端，觀眾端、管理端和教練端根據需求接收不同的狀態資訊
function broadcastState() {
  io.to("viewer").emit("viewer_state", getViewerState());
  io.to("admin").emit("admin_state", {
    ...getViewerState(),
    allBids: state.bids,
  });

  for (const coachId of COACHES) {
    io.to(`coach:${coachId}`).emit("coach_state", getCoachState(coachId));
  }
}

// 結束競標，計算結果並更新狀態，然後廣播給所有客戶端
function endAuction() {
  if (auctionTimer) {
    clearInterval(auctionTimer);
    auctionTimer = null;
  }

  const result = getWinner();

  state.status = "ended";
  state.timeLeft = 0;
  state.winner = result.winner;
  state.winningAmount = result.winningAmount;

  if (state.winner && state.winningAmount !== null) {
    coachBudgets[state.winner] -= state.winningAmount;
    
    // 記錄得標結果
    auctionHistory.push({
      playerName: state.currentPlayer,
      winner: state.winner,
      amount: state.winningAmount,
      time: new Date().toLocaleString()
    });
    
    // 將結果存入 CSV
    saveHistoryToCSV();
  }

  saveState();
  broadcastState();
}

// 將競標紀錄存入 CSV (分隊列出)
function saveHistoryToCSV() {
  const historyFilePath = path.join(__dirname, "data", "auction_results.csv");
  
  // 建立各隊的成員列表
  const teams = {};
  COACHES.forEach(coach => teams[coach] = []);
  
  auctionHistory.forEach(record => {
    if (teams[record.winner]) {
      // 根據您的需求，我們只存選手名字在 CSV 中以維持原本格式
      teams[record.winner].push(record.playerName);
    }
  });

  // 計算最大成員數以便建立 CSV 列
  const maxMembers = Math.max(...Object.values(teams).map(t => t.length), 1);
  
  let csvContent = COACHES.join(",") + "\n";
  
  for (let i = 0; i < maxMembers; i++) {
    const row = COACHES.map(coach => teams[coach][i] || "");
    csvContent += row.join(",") + "\n";
  }

  fs.writeFile(historyFilePath, "\ufeff" + csvContent, "utf8", (err) => {
    if (err) console.error("Error saving auction_results.csv:", err);
  });
}

// 開始競標，初始化狀態並啟動計時器，每秒更新剩餘時間並廣播狀態給所有客戶端
function startAuction(playerName, duration = 90) {
  if (auctionTimer) {
    clearInterval(auctionTimer);
    auctionTimer = null;
  }

  state.status = "running";
  state.currentPlayer = playerName;
  state.duration = duration;
  state.timeLeft = duration;
  state.winner = null;
  state.winningAmount = null;
  resetBids();

  saveState();
  broadcastState();

  auctionTimer = setInterval(() => { 
    state.timeLeft -= 1;

    if (state.timeLeft < 0) { // 修改這裡：從 <= 0 改為 < 0，這樣 0 秒時會廣播一次再結束
      endAuction();
      return;
    }

    if (state.timeLeft % 5 === 0) saveState(); // 每5秒紀錄一次剩餘時間
    broadcastState();
  }, 1000);
}

// 處理客戶端連接，根據不同的事件處理加入觀眾、管理員和教練房間，以及開始競標、結束競標和提交出價等操作
io.on("connection", (socket) => {
  console.log("client connected:", socket.id);

  // 添加觀眾房間，並發送當前狀態給觀眾端
  socket.on("join_viewer", () => {
    socket.join("viewer");
    socket.emit("viewer_state", getViewerState());
  });

  // 添加管理員房間，並發送當前狀態和所有出價資訊給管理員端
  socket.on("join_admin", () => {
    socket.join("admin");
    socket.emit("admin_state", {
      ...getViewerState(),
      allBids: state.bids,
    });
  });

  // 添加教練房間，並發送當前狀態給教練端
  socket.on("join_coach", ({ coachId }) => {
    if (!COACHES.includes(coachId)) {
      socket.emit("error_message", "無效的教練ID");
      return;
    }

    socket.join(`coach:${coachId}`);
    socket.data.coachId = coachId;
    socket.emit("coach_state", getCoachState(coachId));
  });

  // 處理開始競標事件，驗證輸入並啟動競標
  socket.on("start_auction", ({ playerName, duration }) => {
    if (state.status === "running") {
      socket.emit("error_message", "已有競標正在進行中，請先結束本輪競標");
      return;
    }

    if (!playerName || typeof playerName !== "string") {
      socket.emit("error_message", "playerName is required");
      return;
    }

    const safeDuration =
      Number.isInteger(duration) && duration > 0 ? duration : 90;

    startAuction(playerName.trim(), safeDuration);
  });

  // 處理結束競標事件，驗證狀態並結束競標
  socket.on("end_auction", () => {
    if (state.status === "running") {
      endAuction();
    }
  });

  // 處理提交出價事件，驗證輸入並更新出價狀態，然後廣播更新給所有客戶端
  socket.on("submit_bid", ({ coachId, amount }) => {
    // 如果競標未在進行中，則返回錯誤訊息
    if (state.status !== "running") {
      socket.emit("error_message", "目前沒有正在進行的競標");
      return;
    }

    // 驗證教練ID是否有效，如果無效則返回錯誤訊息
    if (!COACHES.includes(coachId)) {
      socket.emit("error_message", "錯誤的教練ID");
      return;
    }

    const bidAmount = Number(amount);

    // 驗證出價金額是否為非負整數，如果無效則返回錯誤訊息
    if (!Number.isInteger(bidAmount) || bidAmount < 0) {
      socket.emit("error_message", "無效的出價金額");
      return;
    }

    // 驗證出價金額是否超過教練剩餘預算，如果超過則返回錯誤訊息
    if (bidAmount > coachBudgets[coachId]) {
      socket.emit("error_message", "出價金額超過剩餘預算!");
      return;
    }

    // 檢查該隊伍是否已滿 5 人
    const currentCount = auctionHistory.filter(h => h.winner === coachId).length;
    if (currentCount >= 5) {
      socket.emit("error_message", "你的隊伍已滿 5 人，無法再出價！");
      return;
    }

    // 更新出價狀態，將教練的出價金額存儲在 state.bids 中，格式為 { coachId: bidAmount }
    state.bids[coachId] = bidAmount;

    saveState();
    broadcastState();
  });

  // 處理客戶端斷開連接事件，記錄斷開連接的客戶端ID
  socket.on("disconnect", () => {
    console.log("client disconnected:", socket.id);
  });
});

// 管理端重置預算的API，重置所有教練的預算狀態，然後廣播更新給所有客戶端
app.post("/api/admin/reset_budget", (req, res) => {
  const token = req.headers["x-admin-token"];

  if (token !== ADMIN_TOKEN) {
    return res.status(401).json({ ok: false, message: "Unauthorized" });
  }

  resetBudgets();
  auctionHistory = [];
  saveState();
  broadcastState();

  res.json({ 
    ok: true,
    message: "Budgets have been reset",
    budgets: coachBudgets,});
});

app.post("/api/admin/reset_auction", (req, res) => {
  const token = req.headers["x-admin-token"];
  
  if (token !== ADMIN_TOKEN) {
    return res.status(401).json({ ok: false, message: "Unauthorized" });
  }

  state.status = "idle";
  state.currentPlayer = null;
  state.timeLeft = 0;
  state.winner = null;
  state.winningAmount = null;
  auctionHistory = [];
  resetBudgets();
  resetBids();
  saveState();
  broadcastState();
  res.json({ ok: true, message: "Auction has been reset" });
});

// 啟動伺服器，監聽指定的端口，並在控制台輸出伺服器運行的URL
server.listen(PORT, () => {
  console.log(`Coach Auction System running on http://localhost:${PORT}`);
});