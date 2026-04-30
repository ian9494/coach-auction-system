const socket = io();

// DOM
const statusText = document.getElementById("statusText");
const currentPlayerText = document.getElementById("currentPlayerText");
const timeLeftText = document.getElementById("timeLeftText");

const runningSection = document.getElementById("runningSection");
const resultSection = document.getElementById("resultSection");

const bidTableBody = document.getElementById("bidsTableBody");
const winnerText = document.getElementById("winnerText");
const winningAmountText = document.getElementById("winningAmountText");
const messageText = document.getElementById("messageText");

socket.emit("join_viewer");

socket.on("viewer_state", (state) => {
  renderState(state);
});

socket.on("error_message", (message) => {
  setMessage(message);
});

function renderState(state) {
  statusText.textContent = translateStatus(state.status);
  currentPlayerText.textContent = state.currentPlayer ?? "-";
  timeLeftText.textContent =
    typeof state.timeLeft === "number" ? `${state.timeLeft} 秒` : "-";

  if (state.status === "ended") {
    runningSection.style.display = "none";
    resultSection.style.display = "block";

    winnerText.textContent = state.winner ?? "無人出價";
    winningAmountText.textContent =
      state.winningAmount !== null && state.winningAmount !== undefined
        ? state.winningAmount
        : "-";

    renderBids(state.bids || {}, state.budgets || {});
    return;
  }

  resultSection.style.display = "none";
  runningSection.style.display = "block";

  renderBids(state.bids || {}, state.budgets || {});
}

// 渲染出價列表，顯示每位教練的出價金額，如果尚未出價則顯示 "尚未出價"
function renderBids(bids, budgets) {
  bidTableBody.innerHTML = "";

  const entries = Object.entries(bids);

  if (entries.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.textContent = "尚無出價資料";
    cell.colSpan = 3;
    row.appendChild(cell);
    bidTableBody.appendChild(row);
    return;
  }

  for (const [coachId, amount] of entries) {
    const row = document.createElement("tr");
    const coachCell = document.createElement("td");
    coachCell.textContent = coachId;
    row.appendChild(coachCell);

    const amountCell = document.createElement("td");
    amountCell.textContent = amount === null ? "尚未出價" : amount;
    row.appendChild(amountCell);

    const budgetCell = document.createElement("td");
    budgetCell.textContent = typeof budgets[coachId] === "number" ? budgets[coachId] : "-";
    row.appendChild(budgetCell);

    bidTableBody.appendChild(row);
  }
}

// 翻譯競標狀態為中文顯示
function translateStatus(status) {
  switch (status) {
    case "idle":
      return "等待開始";
    case "running":
      return "競標中";
    case "ended":
      return "競標結束";
    default:
      return "-";
  }
}

function setMessage(message) {
  messageText.textContent = message;
}