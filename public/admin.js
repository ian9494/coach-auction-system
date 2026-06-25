const socket = io();

const playerNameInput = document.getElementById("playerNameInput");
const memberButtonContainer = document.getElementById("memberButtonContainer");
const durationInput = document.getElementById("durationInput");
const startButton = document.getElementById("startButton");
const endButton = document.getElementById("endButton");
const minimumBidText = document.getElementById("minimumBidText");
const minimumBidInput = document.getElementById("minimumBidInput");
const setMinimumBidButton = document.getElementById("setMinimumBidButton");
const minimumBidPresetButtons = document.querySelectorAll("[data-minimum-bid]");
const addAllBudgetsButton = document.getElementById("addAllBudgetsButton");
const undoButton = document.getElementById("undoButton");

const statusText = document.getElementById("statusText");
const currentPlayerText = document.getElementById("currentPlayerText");
const timeLeftText = document.getElementById("timeLeftText");
const winnerText = document.getElementById("winnerText");
const winningAmountText = document.getElementById("winningAmountText");
const bidList = document.getElementById("bidList");
const messageText = document.getElementById("messageText");
let coachNames = {};

socket.emit("join_admin");

// 獲取成員名單並生成按鈕
async function fetchMemberList() {
  try {
    const response = await fetch("/api/members");
    if (!response.ok) throw new Error("Failed to fetch");
    const members = await response.json();
    
    memberButtonContainer.innerHTML = "";
    members.forEach(name => {
      const btn = document.createElement("button");
      btn.textContent = name;
      btn.type = "button";
      btn.style.padding = "5px 10px";
      btn.style.cursor = "pointer";
      
      btn.addEventListener("click", () => {
        playerNameInput.value = name;
      });
      
      memberButtonContainer.appendChild(btn);
    });
  } catch (error) {
    console.error("Error loading member list:", error);
  }
}

fetchMemberList();

startButton.addEventListener("click", () => {
  const playerName = playerNameInput.value.trim();
  const duration = Number(durationInput.value);

  if (!playerName) {
    setMessage("請輸入選手名稱");
    return;
  }

  socket.emit("start_auction", {
    playerName,
    duration: Number.isInteger(duration) && duration > 0 ? duration : 90,
  });

  setMessage("已送出開始競標");
});

endButton.addEventListener("click", () => {
  socket.emit("end_auction");
  setMessage("已送出強制結束");
});

minimumBidPresetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const amount = Number(button.dataset.minimumBid);
    minimumBidInput.value = amount;
    socket.emit("set_minimum_bid", { amount });
  });
});

setMinimumBidButton.addEventListener("click", () => {
  const amount = Number(minimumBidInput.value);
  if (!Number.isInteger(amount) || amount < 0) {
    setMessage("底價必須是大於或等於 0 的整數");
    return;
  }

  socket.emit("set_minimum_bid", { amount });
});

addAllBudgetsButton.addEventListener("click", () => {
  socket.emit("add_all_budgets", { amount: 100 });
});

undoButton.addEventListener("click", () => {
  socket.emit("undo_last_award");
});

socket.on("admin_state", (state) => {
  coachNames = Object.fromEntries(
    (state.coaches || []).map((coach) => [coach.id, coach.name])
  );
  renderState(state);
  // 如果競標結束，自動刷新成員名單按鈕並清空輸入框
  if (state.status === "ended") {
    playerNameInput.value = "";
    fetchMemberList();
  }
});

socket.on("error_message", (message) => {
  setMessage(message);
});

function renderState(state) {
  statusText.textContent = state.status ?? "-";
  currentPlayerText.textContent = state.currentPlayer ?? "-";
  timeLeftText.textContent =
    typeof state.timeLeft === "number" ? `${state.timeLeft} 秒` : "-";
  winnerText.textContent = state.winner ?? "-";
  winningAmountText.textContent =
    state.winningAmount !== null && state.winningAmount !== undefined
      ? state.winningAmount
      : "-";

  const minimumBid =
    Number.isInteger(state.minimumBid) && state.minimumBid >= 0
      ? state.minimumBid
      : 0;
  minimumBidText.textContent = minimumBid;
  if (document.activeElement !== minimumBidInput) {
    minimumBidInput.value = minimumBid;
  }
  undoButton.disabled = !state.canUndo;

  renderBids(state.allBids || state.bids || {}, state.budgets || {});
}

function renderBids(bids, budgets = {}) {
  bidList.innerHTML = "";

  for (const [coachId, amount] of Object.entries(bids)) {
    const budget = budgets[coachId];

    const li = document.createElement("li");

    li.textContent =
      `${coachNames[coachId] || coachId}: ` +
      `${amount === null ? "尚未出價" : amount}` +
      `（剩餘預算：${budget === undefined ? "-" : budget}）`;

    bidList.appendChild(li);
  }
}

function setMessage(message) {
  messageText.textContent = message;
  messageText.style.display = "block";
  
  // 3秒後自動消失
  setTimeout(() => {
    messageText.style.display = "none";
  }, 3000);
}
