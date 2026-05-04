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
  // rosterOverlay.classList.remove("hidden");
  // rosterOverlay.classList.add("visible");

  // 5秒後自動消失
  setTimeout(() => {
    // rosterOverlay.classList.remove("visible");
    // rosterOverlay.classList.add("hidden");
  }, 5000);
}

function renderState(state) {
  currentPlayerText.textContent = state.currentPlayer ?? "-";
  
  // 更新選手頭貼
  if (state.currentPlayer) {
    currentPlayerAvatar.src = `./assets/players/${state.currentPlayer}.jpg`;
    currentPlayerAvatar.style.display = "block";
  } else {
    currentPlayerAvatar.src = `./assets/players/default.jpg`;
  }
  currentPlayerAvatar.onerror = function() { this.src = "./assets/players/default.jpg"; };
  
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

  // 1. 如果沒有贏家，顯示「無人出價」或其他提示
  if (!state || !state.winner) {
    const noBidInfo = document.createElement("div");
    noBidInfo.className = "result-info-center";
    noBidInfo.innerHTML = `
      <p class="label">得標結果</p>
      <h1>無人出價</h1>
      <h2>-</h2>
    `;
    teamGridContainer.appendChild(noBidInfo);
    return;
  }

  const winnerId = state.winner;
  const teamMembers = history.filter(h => h.winner === winnerId);
  // 只取最後加入的 4 個成員 (即前 4 位顯示的頭貼)
  const displayMembers = teamMembers.slice(-4).reverse();

  const createMemberElement = (member) => {
    const container = document.createElement("div");
    container.className = "member-mini-container";

    const img = document.createElement("img");
    img.className = "team-player-mini";
    img.src = `./assets/players/${member.playerName}.jpg`;
    img.onerror = function() { this.src = "./assets/players/default.jpg"; };
    
    const nameTag = document.createElement("span");
    nameTag.className = "member-mini-name";
    nameTag.textContent = member.playerName;

    container.appendChild(img);
    container.appendChild(nameTag);
    return container;
  };

  // 2. 渲染贏家的前 2 個成員 (左側)
  const leftGroup = document.createElement("div");
  leftGroup.className = "team-column";
  displayMembers.slice(0, 2).forEach(m => leftGroup.appendChild(createMemberElement(m)));
  teamGridContainer.appendChild(leftGroup);

  // 3. 插入中間的得標資訊
  const centerInfo = document.createElement("div");
  centerInfo.className = "result-info-center";
  centerInfo.innerHTML = `
    <p class="label">得標結果</p>
    <h1>${COACH_NAMES[winnerId] ?? winnerId}</h1>
    <h2>${state.winningAmount !== null && state.winningAmount !== undefined ? `$${state.winningAmount}` : "-"}</h2>
  `;
  teamGridContainer.appendChild(centerInfo);

  // 4. 渲染贏家的後 2 個成員 (右側)
  const rightGroup = document.createElement("div");
  rightGroup.className = "team-column";
  displayMembers.slice(2, 4).forEach(m => rightGroup.appendChild(createMemberElement(m)));
  teamGridContainer.appendChild(rightGroup);
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