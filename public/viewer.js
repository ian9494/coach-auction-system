const socket = io();

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

const COACH_NAMES = {
  coach1: "Coach 1",
  coach2: "Coach 2",
  coach3: "Coach 3",
  coach4: "Coach 4",
  coach5: "Coach 5",
  coach6: "Coach 6",
  coach7: "Coach 7",
  coach8: "Coach 8",
};

const currentPlayerText = document.getElementById("currentPlayerText");
const timeLeftText = document.getElementById("timeLeftText");
const runningSection = document.getElementById("runningSection");
const resultSection = document.getElementById("resultSection");
const winnerText = document.getElementById("winnerText");
const winningAmountText = document.getElementById("winningAmountText");

socket.emit("join_viewer");

socket.on("viewer_state", (state) => {
  renderState(state);
});

function renderState(state) {
  currentPlayerText.textContent = state.currentPlayer ?? "-";
  timeLeftText.textContent =
    typeof state.timeLeft === "number" ? `${state.timeLeft}` : "-";

  if (state.status === "ended") {
    runningSection.classList.add("hidden");
    resultSection.classList.remove("hidden");

    winnerText.textContent = state.winner
      ? COACH_NAMES[state.winner] ?? state.winner
      : "無人出價";

    winningAmountText.textContent =
      state.winningAmount !== null && state.winningAmount !== undefined
        ? `$${state.winningAmount}`
        : "-";

    return;
  }

  resultSection.classList.add("hidden");
  runningSection.classList.remove("hidden");

  renderCoachCards(state.bids || {}, state.budgets || {});
}

function renderCoachCards(bids, budgets) {
  runningSection.innerHTML = "";

  for (const coachId of COACHES) {
    const amount = bids[coachId];
    const budget = budgets[coachId];

    const card = document.createElement("article");
    card.className = "coach-card";

    card.innerHTML = `
      <img class="coach-avatar" src="./assets/coaches/${coachId}.png" alt="${coachId}" />
      <div>
        <p class="coach-name">${COACH_NAMES[coachId] ?? coachId}</p>
        <p class="bid-value">${amount === null || amount === undefined ? "未出價" : `$${amount}`}</p>
        <p class="budget-value">剩餘預算：${budget === null || budget === undefined ? "-" : `$${budget}`}</p>
      </div>
    `;

    runningSection.appendChild(card);
  }
}