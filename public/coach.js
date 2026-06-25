const socket = io();

const params = new URLSearchParams(window.location.search);
const coachId = params.get("coach");

const coachTitle = document.getElementById("coachTitle");
const playerText = document.getElementById("playerText");
const timeText = document.getElementById("timeText");
const budgetText = document.getElementById("budgetText");
const minimumBidText = document.getElementById("minimumBidText");
const statusText = document.getElementById("statusText");
const myTeamCount = document.getElementById("myTeamCount");
const myTeamList = document.getElementById("myTeamList");
const coachBudgetList = document.getElementById("coachBudgetList");

const myBidText = document.getElementById("myBidText");
const bidInput = document.getElementById("bidInput");
const submitBtn = document.getElementById("submitBtn");
const messageText = document.getElementById("messageText");
const quickButtons = document.querySelectorAll("[data-add]");
let currentBudget = null;
let currentMinimumBid = 0;

coachTitle.textContent = coachId || "未指定教練";

if (!coachId) {
  setMessage("網址缺少 ?coach=coach1");
  submitBtn.disabled = true;
  bidInput.disabled = true;
}

socket.emit("join_coach", { coachId });

quickButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const addValue = Number(button.dataset.add);
    const current = Number(bidInput.value || currentMinimumBid);
    const nextValue = Math.max(0, current + addValue);
    bidInput.value =
      typeof currentBudget === "number"
        ? Math.min(nextValue, currentBudget)
        : nextValue;
  });
});

submitBtn.addEventListener("click", () => {
  const amount = Number(bidInput.value);

  if (!Number.isInteger(amount) || amount < 0) {
    setMessage("請輸入正確金額");
    return;
  }

  if (amount < currentMinimumBid) {
    setMessage(`出價不得低於底價 ${currentMinimumBid}`);
    return;
  }

  socket.emit("submit_bid", {
    coachId,
    amount,
  });

  setMessage("已送出出價");
  navigator.vibrate?.(80);
});

socket.on("coach_state", (state) => {
  if (state.coach) {
    coachTitle.textContent = state.coach.name;
  }
  render(state);
});

socket.on("error_message", (msg) => {
  setMessage(msg);
});

function render(state) {
  playerText.textContent = state.currentPlayer ?? "-";
  timeText.textContent =
    typeof state.timeLeft === "number" ? `${state.timeLeft} 秒` : "-";

  budgetText.textContent =
    typeof state.budget === "number" ? state.budget : "-";
  currentBudget = typeof state.budget === "number" ? state.budget : null;
  currentMinimumBid =
    Number.isInteger(state.minimumBid) && state.minimumBid >= 0
      ? state.minimumBid
      : 0;
  minimumBidText.textContent = currentMinimumBid;
  bidInput.min = currentMinimumBid;
  renderCoachBudgets(state.coaches || [], state.budgets || {});

  statusText.textContent = translateStatus(state.status);

  // 更新已選名單
  if (state.history) {
    const myHistory = state.history.filter(h => h.winner === coachId);
    myTeamCount.textContent = myHistory.length;
    myTeamList.innerHTML = "";
    myHistory.forEach(h => {
      const div = document.createElement("div");
      div.className = "my-team-item";
      div.innerHTML = `${h.playerName} <span>$${h.amount}</span>`;
      myTeamList.appendChild(div);
    });
  }

  if (state.myBid !== null && state.myBid !== undefined) {
    myBidText.textContent = state.myBid;
  } else {
    myBidText.textContent = "尚未出價";
  }

  const canBid = state.status === "running" && !!coachId;

  submitBtn.disabled = !canBid;
  bidInput.disabled = !canBid;
  quickButtons.forEach((button) => {
    button.disabled = !canBid;
  });

  if (state.status === "ended") {
    if (state.winner === coachId) {
      setMessage(`🎉 你得標了！金額：${state.winningAmount}`);
    } else if (state.winner) {
      setMessage(`得標者：${state.winner}（${state.winningAmount}）`);
    } else {
      setMessage("本輪無人出價");
    }
  }
}

function renderCoachBudgets(coaches, budgets) {
  coachBudgetList.innerHTML = "";

  coaches.forEach((coach) => {
    const item = document.createElement("div");
    item.className = `coach-budget-item${coach.id === coachId ? " is-me" : ""}`;

    const name = document.createElement("span");
    name.className = "coach-budget-name";
    name.textContent = coach.name;

    const budget = document.createElement("span");
    budget.className = "coach-budget-value";
    budget.textContent =
      typeof budgets[coach.id] === "number" ? `$${budgets[coach.id]}` : "-";

    item.append(name, budget);
    coachBudgetList.appendChild(item);
  });
}

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

function setMessage(msg) {
  messageText.textContent = msg;
}
