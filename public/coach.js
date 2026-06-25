const socket = io();

const params = new URLSearchParams(window.location.search);
const coachId = params.get("coach");

const coachTitle = document.getElementById("coachTitle");
const playerText = document.getElementById("playerText");
const timeText = document.getElementById("timeText");
const budgetText = document.getElementById("budgetText");
const statusText = document.getElementById("statusText");
const myTeamCount = document.getElementById("myTeamCount");
const myTeamList = document.getElementById("myTeamList");

const myBidText = document.getElementById("myBidText");
const bidInput = document.getElementById("bidInput");
const submitBtn = document.getElementById("submitBtn");
const messageText = document.getElementById("messageText");
const quickButtons = document.querySelectorAll("[data-add]");

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
    const current = Number(bidInput.value || 0);
    bidInput.value = current + addValue;
  });
});

submitBtn.addEventListener("click", () => {
  const amount = Number(bidInput.value);

  if (!Number.isInteger(amount) || amount < 0) {
    setMessage("請輸入正確金額");
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
