// server.js
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, "public")));

app.get("/", (req, res) => {
  res.redirect("/admin.html");
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

resetBudgets(); // 初始化預算狀態

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
  let winner = null;
  let winningAmount = -1;

  for (const [coachId, amount] of Object.entries(state.bids)) {
    if (typeof amount === "number" && amount > winningAmount) {
      winner = coachId;
      winningAmount = amount;
    }
  }

  return {
    winner,
    winningAmount: winner ? winningAmount : null,
  };
}

// 獲取要傳給觀眾端的狀態，包含競標狀態、當前球員、剩餘時間、出價狀態等資訊
function getViewerState() {
  if (state.status === "ended") {
    return {
      status: state.status,
      currentPlayer: state.currentPlayer,
      timeLeft: state.timeLeft,
      winner: state.winner,
      winningAmount: state.winningAmount,
      budgets: coachBudgets,
    };
  }

  return {
    status: state.status,
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    bids: state.bids,
    budgets: coachBudgets,
  };
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
  }

  broadcastState();
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

  broadcastState();

  auctionTimer = setInterval(() => { // 每秒更新剩餘時間 並檢查是否結束競標 及時廣播狀態給所有客戶端
    state.timeLeft -= 1;

    if (state.timeLeft <= 0) {
      endAuction();
      return;
    }

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

    // 更新出價狀態，將教練的出價金額存儲在 state.bids 中，格式為 { coachId: bidAmount }
    state.bids[coachId] = bidAmount;

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
  broadcastState();

  res.json({ 
    ok: true,
    message: "Budgets have been reset",
    budgets: coachBudgets,});
});

// 啟動伺服器，監聽指定的端口，並在控制台輸出伺服器運行的URL
server.listen(PORT, () => {
  console.log(`Coach Auction System running on http://localhost:${PORT}`);
});