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
const resultPlayerAvatar = document.getElementById("resultPlayerAvatar");
const winnerText = document.getElementById("winnerText");
const winningAmountText = document.getElementById("winningAmountText");

const rosterOverlay = document.getElementById("rosterOverlay");
const rosterCoachName = document.getElementById("rosterCoachName");
const rosterMemberList = document.getElementById("rosterMemberList");

const teamGridContainer = document.getElementById("teamGridContainer");

let lastStatus = "idle";

socket.emit("join_viewer");

socket.on("viewer_state", (state) => {
  console.log("State updated:", state.status, "Winner:", state.winner);
  
  // 修改觸發邏輯：只要狀態變為 ended 且有贏家，就顯示動畫
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

  // 過濾出該教練的所有球員
  const teamMembers = history
    .filter(record => record.winner === winnerId)
    .map(record => record.playerName);

  teamMembers.forEach(name => {
    const div = document.createElement("div");
    div.className = "member-item";
    div.textContent = name;
    
    // 如果是剛標到的這一位，加個顏色動畫
    if (name === newPlayer) {
      div.classList.add("new-member");
    }
    
    rosterMemberList.appendChild(div);
  });

  // 顯示動畫遮罩
  rosterOverlay.classList.remove("hidden");
  rosterOverlay.classList.add("visible");

  // 5秒後自動消失
  setTimeout(() => {
    rosterOverlay.classList.remove("visible");
    rosterOverlay.classList.add("hidden");
  }, 5000);
}

function renderState(state) {
  currentPlayerText.textContent = state.currentPlayer ?? "-";
  
  // 修正倒數顯示邏輯
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
  renderTeamGrid(state.history || [], state);
}

function renderTeamGrid(history, state) {
  if (!teamGridContainer) return;

  // 清空並重新渲染
  teamGridContainer.innerHTML = "";

  // 分成前 4 隊與後 4 隊
  const firstHalf = COACHES.slice(0, 4);
  const secondHalf = COACHES.slice(4, 8);

  const createColumn = (coachId) => {
    const teamColumn = document.createElement("div");
    teamColumn.className = "team-column";
    const title = document.createElement("div");
    title.className = "team-column-name";
    title.textContent = COACH_NAMES[coachId] ?? coachId;
    teamColumn.appendChild(title);

    const teamMembers = history.filter(h => h.winner === coachId);
    teamMembers.forEach(member => {
      const img = document.createElement("img");
      img.className = "team-player-mini";
      img.src = `./assets/players/${member.playerName}.jpg`;
      img.onerror = function() { this.src = "./assets/players/default.jpg"; };
      teamColumn.appendChild(img);
    });
    return teamColumn;
  };

  // 1. 渲染前 4 隊
  firstHalf.forEach(id => teamGridContainer.appendChild(createColumn(id)));

  // 2. 插入中間的文字資訊 (只在 ended 狀態顯示詳細資訊)
  const centerInfo = document.createElement("div");
  centerInfo.className = "result-info-center";
  if (state && state.status === "ended") {
    centerInfo.innerHTML = `
      <p class="label">得標結果</p>
      <h1>${state.winner ? (COACH_NAMES[state.winner] ?? state.winner) : "無人出價"}</h1>
      <h2>${state.winningAmount !== null && state.winningAmount !== undefined ? `$${state.winningAmount}` : "-"}</h2>
    `;
  }
  teamGridContainer.appendChild(centerInfo);

  // 3. 渲染後 4 隊
  secondHalf.forEach(id => teamGridContainer.appendChild(createColumn(id)));
}

function renderCoachCards(bids, budgets, history = []) {
  runningSection.innerHTML = "";

  for (const coachId of COACHES) {
    const amount = bids[coachId];
    const budget = budgets[coachId];
    
    // 計算該教練已選人數
    const teamMembers = history.filter(h => h.winner === coachId);

    const card = document.createElement("article");
    card.className = "coach-card";

    let iconsHtml = "";
    teamMembers.forEach(() => {
      iconsHtml += `<div class="member-dot"></div>`;
    });

    card.innerHTML = `
      <img class="coach-avatar" src="./assets/coaches/${coachId}.png" alt="${coachId}" />
      <div>
        <p class="coach-name">${COACH_NAMES[coachId] ?? coachId}</p>
        <p class="bid-value">${amount === null || amount === undefined ? "未出價" : `$${amount}`}</p>
        <div class="team-icons">${iconsHtml}</div>
        <p class="budget-value">預算：${budget === null || budget === undefined ? "-" : `$${budget}`}</p>
      </div>
    `;

    runningSection.appendChild(card);
  }
}