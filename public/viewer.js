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
const currentPlayerAvatar = document.getElementById("currentPlayerAvatar");
const timeLeftText = document.getElementById("timeLeftText");
const runningSection = document.getElementById("runningSection");
const resultSection = document.getElementById("resultSection");
const rosterOverlay = document.getElementById("rosterOverlay");
const rosterCoachName = document.getElementById("rosterCoachName");
const rosterMemberList = document.getElementById("rosterMemberList");
const teamGridContainer = document.getElementById("teamGridContainer");
const imageFallback =
  "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";

let lastStatus = "idle";

socket.emit("join_viewer");

socket.on("viewer_state", (state) => {
  console.log("State updated:", state.status, "Winner:", state.winner);

  if (state.status === "ended" && state.winner && lastStatus !== "ended") {
    console.log("Triggering animation for:", state.winner);
    showRosterAnimation(state.winner, state.history || [], state.currentPlayer);
  }

  lastStatus = state.status;
  renderState(state);
});

function showRosterAnimation(winnerId, history, newPlayer) {
  const coachName = COACH_NAMES[winnerId] ?? winnerId;
  rosterCoachName.textContent = coachName;
  rosterMemberList.innerHTML = "";

  const teamMembers = history
    .filter((record) => record.winner === winnerId)
    .map((record) => record.playerName);

  teamMembers.forEach((name) => {
    const div = document.createElement("div");
    div.className = "member-item";
    div.textContent = name;

    if (name === newPlayer) {
      div.classList.add("new-member");
    }

    rosterMemberList.appendChild(div);
  });

  setTimeout(() => {
    rosterOverlay.classList.remove("visible");
    rosterOverlay.classList.add("hidden");
  }, 5000);
}

function renderState(state) {
  currentPlayerText.textContent = state.currentPlayer ?? "-";

  if (state.currentPlayer) {
    currentPlayerAvatar.src = `./assets/players/${state.currentPlayer}.jpg`;
    currentPlayerAvatar.style.display = "block";
  } else {
    currentPlayerAvatar.src = imageFallback;
  }

  currentPlayerAvatar.onerror = function () {
    this.src = imageFallback;
  };

  const displayTime = typeof state.timeLeft === "number" ? Math.max(0, state.timeLeft) : "-";
  timeLeftText.textContent = displayTime;

  if (state.status === "ended") {
    runningSection.classList.add("hidden");
    resultSection.classList.remove("hidden");
    renderTeamGrid(state.history || [], state);
    return;
  }

  resultSection.classList.add("hidden");
  runningSection.classList.remove("hidden");

  renderCoachCards(state.bids || {}, state.budgets || {}, state.history || []);
}

function renderTeamGrid(history, state) {
  if (!teamGridContainer) return;

  teamGridContainer.innerHTML = "";

  if (!state || !state.winner) {
    const noBidInfo = document.createElement("div");
    noBidInfo.className = "result-info-center";
    noBidInfo.innerHTML = `
      <p class="label">競標結果</p>
      <h1>無人出價</h1>
      <h2>-</h2>
    `;
    teamGridContainer.appendChild(noBidInfo);
    return;
  }

  const winnerId = state.winner;
  const teamMembers = history.filter((record) => record.winner === winnerId);
  const displayMembers = teamMembers.slice(-4).reverse();

  const createMemberElement = (member) => {
    const container = document.createElement("div");
    container.className = "member-mini-container";

    const img = document.createElement("img");
    img.className = "team-player-mini";
    img.src = `./assets/players/${member.playerName}.jpg`;
    img.onerror = function () {
      this.src = imageFallback;
    };

    const nameTag = document.createElement("span");
    nameTag.className = "member-mini-name";
    nameTag.textContent = member.playerName;

    container.appendChild(img);
    container.appendChild(nameTag);
    return container;
  };

  const leftGroup = document.createElement("div");
  leftGroup.className = "team-column";
  displayMembers.slice(0, 2).forEach((member) => leftGroup.appendChild(createMemberElement(member)));
  teamGridContainer.appendChild(leftGroup);

  const centerInfo = document.createElement("div");
  centerInfo.className = "result-info-center";
  centerInfo.innerHTML = `
    <p class="label">得標教練</p>
    <h1>${COACH_NAMES[winnerId] ?? winnerId}</h1>
    <h2>${state.winningAmount !== null && state.winningAmount !== undefined ? `$${state.winningAmount}` : "-"}</h2>
  `;
  teamGridContainer.appendChild(centerInfo);

  const rightGroup = document.createElement("div");
  rightGroup.className = "team-column";
  displayMembers.slice(2, 4).forEach((member) => rightGroup.appendChild(createMemberElement(member)));
  teamGridContainer.appendChild(rightGroup);
}

function renderCoachCards(bids, budgets, history = []) {
  runningSection.innerHTML = "";

  for (const coachId of COACHES) {
    const amount = bids[coachId];
    const budget = budgets[coachId];
    const teamMembers = history.filter((record) => record.winner === coachId);
    const hasBid = amount !== null && amount !== undefined;
    const coachName = COACH_NAMES[coachId] ?? coachId;

    const card = document.createElement("article");
    card.className = `coach-card${hasBid ? " has-bid" : ""}`;

    const memberDots = teamMembers.map(() => '<div class="member-dot"></div>').join("");

    card.innerHTML = `
      <img class="coach-avatar" src="./assets/coaches/${coachId}.png" alt="${coachName}" />
      <div>
        <p class="coach-name">${coachName}</p>
        <p class="bid-value${hasBid ? "" : " no-bid"}">${hasBid ? `$${amount}` : "尚未出價"}</p>
        <div class="team-icons">${memberDots}</div>
        <p class="budget-value">剩餘預算 ${budget === null || budget === undefined ? "-" : `$${budget}`}</p>
      </div>
    `;

    const coachAvatar = card.querySelector(".coach-avatar");
    coachAvatar.onerror = function () {
      const fallback = document.createElement("div");
      fallback.className = "coach-avatar-fallback";
      fallback.setAttribute("aria-hidden", "true");
      fallback.textContent = coachName.replace("Coach ", "C");
      this.replaceWith(fallback);
    };

    runningSection.appendChild(card);
  }
}
