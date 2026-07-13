const socket = io();

const params = new URLSearchParams(window.location.search);
const coachId = params.get("coach");

const coachTitle = document.getElementById("coachTitle");
const playerText = document.getElementById("playerText");
const timeText = document.getElementById("timeText");
const budgetText = document.getElementById("budgetText");
const minimumBidText = document.getElementById("minimumBidText");
const statusText = document.getElementById("statusText");
const allTeamList = document.getElementById("allTeamList");
const coachBudgetList = document.getElementById("coachBudgetList");

const myBidText = document.getElementById("myBidText");
const bidInput = document.getElementById("bidInput");
const submitBtn = document.getElementById("submitBtn");
const messageText = document.getElementById("messageText");
const quickButtons = document.querySelectorAll("[data-add]");
let currentBudget = null;
let currentMinimumBid = 0;
let currentMaxBid = null;
let currentZoneLimitReached = false;
let coachRoster = [];
let latestBudgets = {};
let latestHistory = [];

coachTitle.textContent = coachId || "未指定教練";

if (!coachId) {
  setMessage("網址缺少 ?coach=coach1");
  submitBtn.disabled = true;
  bidInput.disabled = true;
}

socket.emit("join_coach", { coachId });

fetch("/api/coaches")
  .then((response) => {
    if (!response.ok) throw new Error("Failed to load coaches");
    return response.json();
  })
  .then((coaches) => {
    if (!Array.isArray(coaches)) return;
    coachRoster = coaches;
    renderCoachBudgets(coachRoster, latestBudgets);
    renderAllCoachTeams(coachRoster, latestHistory);
  })
  .catch(() => {
    renderCoachBudgets(coachRoster, latestBudgets);
    renderAllCoachTeams(coachRoster, latestHistory);
  });

quickButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const addValue = Number(button.dataset.add);
    const current = Number(bidInput.value || currentMinimumBid);
    const nextValue = Math.max(0, current + addValue);
    bidInput.value =
      typeof currentMaxBid === "number"
        ? Math.min(nextValue, currentMaxBid)
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

  if (typeof currentMaxBid === "number" && amount > currentMaxBid) {
    setMessage(`出價過高，最高可出 ${currentMaxBid}`);
    return;
  }

  if (currentZoneLimitReached) {
    setMessage("此區已達可選人數上限");
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
    state.bidRules &&
    Number.isInteger(state.bidRules.minBid) &&
    state.bidRules.minBid >= 0
      ? state.bidRules.minBid
      : Number.isInteger(state.minimumBid) && state.minimumBid >= 0
        ? state.minimumBid
        : 0;
  currentMaxBid =
    state.bidRules &&
    Number.isInteger(state.bidRules.maxBid) &&
    state.bidRules.maxBid >= 0
      ? state.bidRules.maxBid
      : null;
  currentZoneLimitReached = !!(
    state.bidRules && state.bidRules.zoneLimitReached
  );
  minimumBidText.textContent = currentMinimumBid;
  bidInput.min = currentMinimumBid;
  if (typeof currentMaxBid === "number") {
    bidInput.max = currentMaxBid;
  } else {
    bidInput.removeAttribute("max");
  }
  if (Array.isArray(state.coaches) && state.coaches.length > 0) {
    coachRoster = state.coaches;
  }
  if (state.budgets && typeof state.budgets === "object") {
    latestBudgets = state.budgets;
  } else if (typeof state.budget === "number" && coachId) {
    latestBudgets = { ...latestBudgets, [coachId]: state.budget };
  }
  renderCoachBudgets(coachRoster, latestBudgets);

  statusText.textContent = translateStatus(state.status);

  if (Array.isArray(state.history)) {
    latestHistory = state.history;
  }
  renderAllCoachTeams(coachRoster, latestHistory);

  if (state.myBid !== null && state.myBid !== undefined) {
    myBidText.textContent = state.myBid;
  } else {
    myBidText.textContent = "尚未出價";
  }

  const canBid =
    state.status === "running" &&
    !!coachId &&
    !currentZoneLimitReached &&
    (typeof currentMaxBid !== "number" || currentMaxBid >= currentMinimumBid);

  if (canBid) {
    const inputAmount = Number(bidInput.value);
    const shouldFillMinimum =
      bidInput.value === "" ||
      !Number.isInteger(inputAmount) ||
      inputAmount < currentMinimumBid;

    if (shouldFillMinimum) {
      bidInput.value =
        typeof currentMaxBid === "number"
          ? Math.min(currentMinimumBid, currentMaxBid)
          : currentMinimumBid;
    }
  }

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

  const roster =
    Array.isArray(coaches) && coaches.length > 0
      ? coaches
      : coachId
        ? [{ id: coachId, name: coachTitle.textContent || coachId }]
        : [];

  if (roster.length === 0) {
    coachBudgetList.textContent = "尚未載入教練資料";
    return;
  }

  roster.forEach((coach) => {
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

function renderAllCoachTeams(coaches, history) {
  allTeamList.innerHTML = "";

  const roster =
    Array.isArray(coaches) && coaches.length > 0
      ? coaches
      : coachId
        ? [{ id: coachId, name: coachTitle.textContent || coachId }]
        : [];

  if (roster.length === 0) {
    allTeamList.textContent = "尚未載入教練資料";
    return;
  }

  const safeHistory = Array.isArray(history) ? history : [];

  roster.forEach((coach) => {
    const coachHistory = safeHistory.filter((record) => record.winner === coach.id);
    const group = document.createElement("div");
    group.className = `team-group${coach.id === coachId ? " is-me" : ""}`;

    const header = document.createElement("div");
    header.className = "team-group-header";

    const name = document.createElement("span");
    name.className = "team-group-name";
    name.textContent = coach.name;

    const count = document.createElement("span");
    count.className = "team-group-count";
    count.textContent = `${coachHistory.length}/5`;

    header.append(name, count);
    group.appendChild(header);

    const list = document.createElement("div");
    list.className = "team-member-list";

    if (coachHistory.length === 0) {
      const empty = document.createElement("div");
      empty.className = "team-member-empty";
      empty.textContent = "尚未選人";
      list.appendChild(empty);
    } else {
      coachHistory.forEach((record) => {
        const item = document.createElement("div");
        item.className = "team-member-item";

        const player = document.createElement("span");
        player.className = "team-member-name";
        player.textContent = record.playerName || "-";

        const amount = document.createElement("span");
        amount.className = "team-member-amount";
        amount.textContent =
          typeof record.amount === "number" ? `$${record.amount}` : "-";

        item.append(player, amount);
        list.appendChild(item);
      });
    }

    group.appendChild(list);
    allTeamList.appendChild(group);
  });
}

function translateStatus(status) {
  switch (status) {
    case "idle":
      return "等待開始";
    case "running":
      return "競標中";
    case "paused":
      return "已暫停";
    case "ended":
      return "競標結束";
    default:
      return "-";
  }
}

function setMessage(msg) {
  messageText.textContent = msg;
}
