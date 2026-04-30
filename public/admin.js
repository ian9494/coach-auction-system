const socket = io();

const playerNameInput = document.getElementById("playerNameInput");
const durationInput = document.getElementById("durationInput");
const startButton = document.getElementById("startButton");
const endButton = document.getElementById("endButton");

const statusText = document.getElementById("statusText");
const currentPlayerText = document.getElementById("currentPlayerText");
const timeLeftText = document.getElementById("timeLeftText");
const winnerText = document.getElementById("winnerText");
const winningAmountText = document.getElementById("winningAmountText");
const bidList = document.getElementById("bidList");
const messageText = document.getElementById("messageText");

socket.emit("join_admin");

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

socket.on("admin_state", (state) => {
  renderState(state);
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

  renderBids(state.allBids || state.bids || {}, state.budgets || {});
}

function renderBids(bids, budgets = {}) {
  bidList.innerHTML = "";

  for (const [coachId, amount] of Object.entries(bids)) {
    const budget = budgets[coachId];

    const li = document.createElement("li");

    li.textContent =
      `${coachId}: ` +
      `${amount === null ? "尚未出價" : amount}` +
      `（剩餘預算：${budget === undefined ? "-" : budget}）`;

    bidList.appendChild(li);
  }
}

function setMessage(message) {
  messageText.textContent = message;
}