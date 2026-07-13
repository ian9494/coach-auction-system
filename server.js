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

const bidRateByCoach = new Map();
const bidRateByIp = new Map();



const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, "public")));


function canSubmitBid(coachId, ip) {
  const now = Date.now();

  const lastCoachBid = bidRateByCoach.get(coachId) || 0;
  if (now - lastCoachBid < 300) {
    return false;
  }

  const recentIpBids = (bidRateByIp.get(ip) || []).filter((t) => now - t < 2000);

  if (recentIpBids.length >= 3) {
    return false; // 同一 IP 2 秒內超過 3 次出價
  }

  recentIpBids.push(now);
  bidRateByIp.set(ip, recentIpBids);
  bidRateByCoach.set(coachId, now);

  return true;
}

// 持久化狀態函式
function saveState() {
  const dataToSave = {
    status: state.status,
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    savedAt: Date.now(),
    bids: state.bids,
    budgets: coachBudgets,
    history: auctionHistory,
    winner: state.winner,
    winningAmount: state.winningAmount,
    minimumBid: state.minimumBid
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
    if (!fs.existsSync(STATE_FILE)) return null;
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch (err) {
    console.error("Error loading state:", err);
  }
  return null;
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
const COACH_FILE = path.join(__dirname, "data", "coach.csv");

function loadCoaches() {
  const rows = fs.readFileSync(COACH_FILE, "utf8")
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));

  const coaches = rows.map((line, index) => {
    const [rawId, ...nameParts] = line.split(",");
    const id = rawId.trim();
    const name = nameParts.join(",").trim() || id;

    if (!/^[a-zA-Z0-9_-]+$/.test(id)) {
      throw new Error(`Invalid coach id "${id}" on coach.csv line ${index + 1}`);
    }

    return { id, name };
  });

  const ids = coaches.map((coach) => coach.id);
  if (new Set(ids).size !== ids.length) {
    throw new Error("Duplicate coach id found in data/coach.csv");
  }

  return coaches;
}

const COACH_CONFIG = loadCoaches();
const COACHES = COACH_CONFIG.map((coach) => coach.id);

app.get("/api/coaches", (req, res) => {
  res.json(COACH_CONFIG);
});

const INITIAL_BUDGET = 1000; // 每位教練的初始預算
function loadMemberNames() {
  const filePath = path.join(__dirname, "data", "member.csv");
  return fs
    .readFileSync(filePath, "utf8")
    .replace(/^\uFEFF/, "")
    .split(/[\n\r,]+/)
    .map((name) => name.trim())
    .filter((name) => name !== "");
}

const TEAM_SIZE = 5;
const RESERVED_BID_PER_REMAINING_SLOT = 100;
const MIN_SPEND_AFTER_SECOND_PLAYER = 300;
const MAX_BID_AMOUNT = 500;
const PLAYER_ZONE_CONFIG = [
  { id: 1, size: 8, coachLimit: 1 },
  { id: 2, size: 8, coachLimit: 1 },
  { id: 3, size: 24, coachLimit: 3 },
];
const MEMBER_NAMES = loadMemberNames();
// 儲存每位教練的預算狀態，格式為 { coachId: remainingBudget }
const coachBudgets = {};

// 重置所有教練的預算狀態
function resetBudgets() {
  for (const coach of COACHES) {
    coachBudgets[coach] = INITIAL_BUDGET;
    }
}

let auctionHistory = []; // 儲存已得標的選手資訊

const restoredState = loadState();

let auctionTimer = null; // 競標計時器

// 競標狀態
const state = {
  status: "idle", // 競標狀態：idle | running | paused | ended
  currentPlayer: null, // 當前競標的球員名稱
  timeLeft: 0, // 剩餘時間（秒）
  duration: 90, // 競標總時間（秒）
  bids: {}, // 教練出價狀態，格式為 { coachId: bidAmount }
  winner: null, // 贏家教練ID
  winningAmount: null, // 贏家出價金額
};

// 重置所有教練的出價狀態
state.minimumBid = 0;

let lastAwardUndo = null;

function undoLastAward() {
  if (!lastAwardUndo) return false;

  const latestRecord = auctionHistory[auctionHistory.length - 1];
  if (
    !latestRecord ||
    latestRecord.playerName !== lastAwardUndo.playerName ||
    latestRecord.winner !== lastAwardUndo.winner ||
    latestRecord.amount !== lastAwardUndo.amount
  ) {
    lastAwardUndo = null;
    return false;
  }

  if (auctionTimer) {
    clearInterval(auctionTimer);
    auctionTimer = null;
  }

  auctionHistory.pop();
  coachBudgets[lastAwardUndo.winner] += lastAwardUndo.amount;

  state.status = "ended";
  state.currentPlayer = lastAwardUndo.playerName;
  state.timeLeft = 0;
  state.bids = { ...lastAwardUndo.bids };
  state.winner = null;
  state.winningAmount = null;

  lastAwardUndo = null;
  saveHistoryToCSV();
  saveState();
  broadcastState();
  return true;
}

if (restoredState) {
  state.status = restoredState.status;
  state.currentPlayer = restoredState.currentPlayer;
  state.timeLeft = restoredState.timeLeft;
  if (state.status === "running" && restoredState.savedAt) {
    const elapsedSeconds = Math.floor((Date.now() - restoredState.savedAt) / 1000);
    state.timeLeft = Math.max(0, state.timeLeft - elapsedSeconds);
    if (state.timeLeft === 0) {
      state.status = "ended";
    }
  }
  state.winner = COACHES.includes(restoredState.winner) ? restoredState.winner : null;
  state.winningAmount = state.winner ? restoredState.winningAmount : null;
  state.minimumBid =
    Number.isInteger(restoredState.minimumBid) && restoredState.minimumBid >= 0
      ? restoredState.minimumBid
      : 0;
  const restoredBids = restoredState.bids || {};

  for (const coachId of COACHES) {
    state.bids[coachId] =
      restoredBids[coachId] !== undefined ? restoredBids[coachId] : null;
    coachBudgets[coachId] =
      restoredState.budgets && restoredState.budgets[coachId] !== undefined
        ? restoredState.budgets[coachId]
        : INITIAL_BUDGET;
  }

  auctionHistory = restoredState.history || [];
} else {
  resetBudgets();
}

function resetBids() {
  state.bids = {};
  for (const coach of COACHES) {
    state.bids[coach] = null;
  }
}

if (!restoredState) {
  resetBids();
}

function getCoachPlayerCount(coachId) {
  return auctionHistory.filter((h) => h.winner === coachId).length;
}

function getCoachSpent(coachId) {
  return auctionHistory
    .filter((h) => h.winner === coachId && typeof h.amount === "number")
    .reduce((total, h) => total + h.amount, 0);
}

function getPlayerZone(playerName) {
  if (!playerName) return null;

  const memberIndex = MEMBER_NAMES.indexOf(playerName);
  if (memberIndex < 0) return null;

  let zoneStart = 0;
  for (const zone of PLAYER_ZONE_CONFIG) {
    const zoneEnd = zoneStart + zone.size;
    if (memberIndex >= zoneStart && memberIndex < zoneEnd) {
      return zone;
    }
    zoneStart = zoneEnd;
  }

  return null;
}

function getCoachZonePlayerCount(coachId, zoneId) {
  if (!zoneId) return 0;

  return auctionHistory.filter((record) => {
    if (record.winner !== coachId) return false;
    const recordZone = getPlayerZone(record.playerName);
    return recordZone && recordZone.id === zoneId;
  }).length;
}

function getBidRules(coachId) {
  const budget =
    typeof coachBudgets[coachId] === "number" ? coachBudgets[coachId] : 0;
  const playerCount = getCoachPlayerCount(coachId);
  const playerZone = getPlayerZone(state.currentPlayer);
  const zonePlayerCount = playerZone
    ? getCoachZonePlayerCount(coachId, playerZone.id)
    : 0;
  const zoneLimitReached =
    playerZone !== null && zonePlayerCount >= playerZone.coachLimit;
  const remainingSlotsAfterWin = Math.max(TEAM_SIZE - playerCount - 1, 0);
  const reserveForRemaining =
    remainingSlotsAfterWin * RESERVED_BID_PER_REMAINING_SLOT;
  const maxBid = Math.min(
    MAX_BID_AMOUNT,
    Math.max(0, budget - reserveForRemaining)
  );
  const spentAfterWinFloor = getCoachSpent(coachId);
  const secondPlayerMinimum =
    playerCount === 1
      ? MIN_SPEND_AFTER_SECOND_PLAYER + 1 - spentAfterWinFloor
      : 0;

  return {
    playerCount,
    minBid: Math.max(state.minimumBid, secondPlayerMinimum, 0),
    maxBid: zoneLimitReached ? 0 : maxBid,
    playerZone,
    zonePlayerCount,
    zoneLimit: playerZone ? playerZone.coachLimit : null,
    zoneLimitReached,
    remainingSlotsAfterWin,
    reserveForRemaining,
  };
}

function getBidError(coachId, bidAmount) {
  if (!Number.isInteger(bidAmount) || bidAmount < 0) {
    return "請輸入正確金額";
  }

  if (bidAmount < state.minimumBid) {
    return `出價不得低於底價 ${state.minimumBid}`;
  }

  if (bidAmount > coachBudgets[coachId]) {
    return "出價金額超過剩餘預算!";
  }

  const rules = getBidRules(coachId);

  if (rules.zoneLimitReached) {
    return `第 ${rules.playerZone.id} 區已選滿，每位教練此區最多 ${rules.zoneLimit} 位`;
  }

  if (rules.playerCount >= TEAM_SIZE) {
    return `你的隊伍已滿 ${TEAM_SIZE} 位，不能再出價`;
  }

  if (bidAmount < rules.minBid) {
    return `T2 選完總花費必須大於 ${MIN_SPEND_AFTER_SECOND_PLAYER}，本次至少要出 ${rules.minBid}`;
  }

  if (bidAmount > rules.maxBid) {
    return `出價過高，得標後剩餘 ${rules.remainingSlotsAfterWin} 位需各保留 ${RESERVED_BID_PER_REMAINING_SLOT}，最高可出 ${rules.maxBid}`;
  }

  return null;
}

function pruneInvalidBids() {
  for (const coachId of COACHES) {
    const bid = state.bids[coachId];
    if (typeof bid === "number" && getBidError(coachId, bid)) {
      state.bids[coachId] = null;
    }
  }
}

// 計算競標結果，找出最高出價的教練 return:得標教練ID和出價金額
function getWinner() {
  let highestAmount = -1;
  let candidates = [];

  // 獲取目前各隊人數
  for (const [coachId, amount] of Object.entries(state.bids)) {
    // 嚴格判斷數值，處理 0 元出價比 null (無出價) 優先
    if (
      amount === null ||
      amount === undefined ||
      typeof amount !== "number" ||
      getBidError(coachId, amount)
    ) continue;
    
    // 檢查該隊是否已滿 5 人
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
    coaches: COACH_CONFIG,
    status: state.status,
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    winner: state.winner,
    winningAmount: state.winningAmount,
    minimumBid: state.minimumBid,
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
  const coach = COACH_CONFIG.find((item) => item.id === coachId);
  const bidRules = COACHES.includes(coachId) ? getBidRules(coachId) : null;

  return {
    coach,
    coaches: COACH_CONFIG,
    budgets: coachBudgets,
    status: state.status,
    currentPlayer: state.currentPlayer,
    timeLeft: state.timeLeft,
    minimumBid: state.minimumBid,
    bidRules,
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
    canUndo: lastAwardUndo !== null,
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
    lastAwardUndo = {
      playerName: state.currentPlayer,
      winner: state.winner,
      amount: state.winningAmount,
      bids: { ...state.bids },
    };

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

function startAuctionTimer() {
  if (auctionTimer) {
    clearInterval(auctionTimer);
    auctionTimer = null;
  }

  auctionTimer = setInterval(() => {
    state.timeLeft -= 1;

    if (state.timeLeft < 0) { // 修改這裡：從 <= 0 改為 < 0，這樣 0 秒時會廣播一次再結束
      state.timeLeft = 0;
      endAuction();
      return;
    }

    if (state.timeLeft % 5 === 0) saveState(); // 每5秒紀錄一次剩餘時間
    broadcastState();
  }, 1000);
}

function pauseAuction() {
  if (state.status !== "running") return false;

  if (auctionTimer) {
    clearInterval(auctionTimer);
    auctionTimer = null;
  }

  state.status = "paused";
  saveState();
  broadcastState();
  return true;
}

function resumeAuction() {
  if (state.status !== "paused") return false;

  state.status = "running";
  saveState();
  broadcastState();
  startAuctionTimer();
  return true;
}

// 開始競標，初始化狀態並啟動計時器，每秒更新剩餘時間並廣播狀態給所有客戶端
function startAuction(playerName, duration = 90) {
  lastAwardUndo = null;

  state.status = "running";
  state.currentPlayer = playerName;
  state.duration = duration;
  state.timeLeft = duration;
  state.winner = null;
  state.winningAmount = null;
  resetBids();

  saveState();
  broadcastState();

  startAuctionTimer();
}

if (state.status === "running") {
  startAuctionTimer();
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
    socket.data.isAdmin = true;
    socket.emit("admin_state", {
      ...getViewerState(),
      allBids: state.bids,
      canUndo: lastAwardUndo !== null,
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
    if (state.status === "running" || state.status === "paused") {
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
    if (state.status === "running" || state.status === "paused") {
      endAuction();
    }
  });

  socket.on("pause_auction", () => {
    if (!socket.data.isAdmin) return;
    pauseAuction();
  });

  socket.on("resume_auction", () => {
    if (!socket.data.isAdmin) return;
    resumeAuction();
  });

  socket.on("add_all_budgets", ({ amount = 100 } = {}) => {
    if (!socket.data.isAdmin) return;

    const safeAmount = Number(amount);
    if (!Number.isInteger(safeAmount) || safeAmount <= 0) {
      socket.emit("error_message", "預算增加額必須是正整數");
      return;
    }

    for (const coachId of COACHES) {
      coachBudgets[coachId] += safeAmount;
    }

    saveState();
    broadcastState();
  });

  socket.on("set_minimum_bid", ({ amount }) => {
    if (!socket.data.isAdmin) return;

    const minimumBid = Number(amount);
    if (!Number.isInteger(minimumBid) || minimumBid < 0) {
      socket.emit("error_message", "底價必須是大於或等於 0 的整數");
      return;
    }

    state.minimumBid = minimumBid;

    pruneInvalidBids();

    saveState();
    broadcastState();
  });

  socket.on("undo_last_award", () => {
    if (!socket.data.isAdmin) return;

    const undone = undoLastAward();
    if (!undone) {
      socket.emit("error_message", "沒有可以復原的操作");
      return;
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
    const ip = socket.data.ip || socket.handshake.address;

    const bidError = getBidError(coachId, bidAmount);
    if (bidError) {
      socket.emit("error_message", bidError);
      return;
    }

    if (!canSubmitBid(coachId, ip)) {
      socket.emit("error_message", "出價過於頻繁，請稍後再試");
      return;
    }

    // 驗證出價金額是否為非負整數，如果無效則返回錯誤訊息
    if (!Number.isInteger(bidAmount) || bidAmount < 0) {
      socket.emit("error_message", "無效的出價金額");
      return;
    }

    // 驗證出價金額是否超過教練剩餘預算，如果超過則返回錯誤訊息
    if (bidAmount < state.minimumBid) {
      socket.emit("error_message", `出價不得低於底價 ${state.minimumBid}`);
      return;
    }

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
function verifyAdminToken(req, res) {
  const token = req.headers["x-admin-token"];

  if (token !== ADMIN_TOKEN) {
    res.status(401).json({ ok: false, message: "Unauthorized" });
    return false;
  }

  return true;
}

function resetBudgetHandler(req, res) {
  if (!verifyAdminToken(req, res)) return;

  lastAwardUndo = null;
  resetBudgets();
  auctionHistory = [];
  saveState();
  broadcastState();

  res.json({ 
    ok: true,
    message: "Budgets have been reset",
    budgets: coachBudgets,});
}

function resetAuctionHandler(req, res) {
  if (!verifyAdminToken(req, res)) return;

  lastAwardUndo = null;
  state.status = "idle";
  state.currentPlayer = null;
  state.timeLeft = 0;
  state.winner = null;
  state.winningAmount = null;
  state.minimumBid = 0;
  auctionHistory = [];
  resetBudgets();
  resetBids();
  saveState();
  broadcastState();
  res.json({ ok: true, message: "Auction has been reset" });
}

app.post("/api/admin/reset_budget", resetBudgetHandler);
app.post("/api/admin/reset-budgets", resetBudgetHandler);
app.post("/api/admin/reset_auction", resetAuctionHandler);
app.post("/api/admin/reset-auctions", resetAuctionHandler);

// 啟動伺服器，監聽指定的端口，並在控制台輸出伺服器運行的URL
server.listen(PORT, () => {
  console.log(`Coach Auction System running on http://localhost:${PORT}`);
});
