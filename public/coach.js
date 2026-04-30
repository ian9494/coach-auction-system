const socket = io();

// 🔥 用網址帶 coachId
// ex: /coach.html?coach=coach1
const params = new URLSearchParams(window.location.search);
const coachId = params.get("coach");

if (!coachId) {
  alert("請用 ?coach=coach1 這種方式進入");
}

socket.emit("join_coach", { coachId });

// DOM
const playerText = document.getElementById("playerText");
const timeText = document.getElementById("timeText");
const statusText = document.getElementById("statusText");

const myBidText = document.getElementById("myBidText");
const budgetText = document.getElementById("budgetText");
const bidInput = document.getElementById("bidInput");
const submitBtn = document.getElementById("submitBtn");

const messageText = document.getElementById("messageText");

// 加價按鈕
function add(val) {
  const current = parseInt(bidInput.value || 0);
  bidInput.value = current + val;
}

// 送出出價
submitBtn.addEventListener("click", () => {
  const amount = Number(bidInput.value);

  if (!Number.isInteger(amount) || amount < 0) {
    setMessage("請輸入正確金額");
    return;
  }

  socket.emit("submit_bid", {
    coachId,
    amount
  });

  setMessage("已送出出價");
});

// 接收狀態
socket.on("coach_state", (state) => {
  render(state);
});

// 錯誤訊息
socket.on("error_message", (msg) => {
  setMessage(msg);
});

// UI 更新
function render(state) {
  playerText.textContent = state.currentPlayer ?? "-";
  timeText.textContent =
    typeof state.timeLeft === "number" ? state.timeLeft + " 秒" : "-";

  statusText.textContent = translateStatus(state.status);

  budgetText.textContent = typeof state.budget === "number" ? state.budget : "-";

  if (state.myBid !== null && state.myBid !== undefined) {
    myBidText.textContent = state.myBid;
  } else {
    myBidText.textContent = "尚未出價";
  }

  // 結束時顯示結果
  if (state.status === "ended") {
    if (state.winner === coachId) {
      setMessage(`🎉 你得標了！金額：${state.winningAmount}`);
    } else {
      setMessage(`得標者：${state.winner}（${state.winningAmount}）`);
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