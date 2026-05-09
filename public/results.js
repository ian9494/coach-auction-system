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

async function fetchResults() {
  try {
    const response = await fetch("/api/results");
    const data = await response.json();
    renderResults(data);

    const loadingEl = document.getElementById("loading");
    if (loadingEl) loadingEl.style.display = "none";
  } catch (err) {
    console.error("Failed to fetch results:", err);

    const loadingEl = document.getElementById("loading");
    if (loadingEl) loadingEl.textContent = "資料載入失敗，請確認伺服器狀態";
  }
}

function renderResults(results) {
  const grid = document.getElementById("grid");
  if (!grid) return;

  grid.innerHTML = "";

  const lastRecord = results.length > 0 ? results[results.length - 1] : null;
  const teams = {};
  Object.keys(COACH_NAMES).forEach((id) => {
    teams[id] = [];
  });

  results.forEach((record) => {
    if (teams[record.coachId]) {
      teams[record.coachId].push(record);
    }
  });

  Object.keys(COACH_NAMES).forEach((coachId) => {
    const members = teams[coachId];
    const card = document.createElement("div");
    const isNewTeam = lastRecord && lastRecord.coachId === coachId;
    card.className = `coach-card${isNewTeam ? " is-latest" : ""}`;

    card.innerHTML = `
      <div class="coach-name">
        <span class="coach-title">${COACH_NAMES[coachId]}</span>
        <span class="coach-count">${members.length} 人</span>
      </div>
      <ul class="member-list">
        ${
          members.length > 0
            ? members
                .map((member) => {
                  const isLatest =
                    lastRecord &&
                    member.playerName === lastRecord.playerName &&
                    member.coachId === lastRecord.coachId &&
                    member.amount === lastRecord.amount;

                  return `
                    <li class="member-item${isLatest ? " new-member" : ""}">
                      <span class="member-name">${member.playerName}</span>
                      <span class="member-price">$${member.amount}</span>
                    </li>
                  `;
                })
                .join("")
            : '<li class="member-item empty-member">尚無成員</li>'
        }
      </ul>
    `;

    grid.appendChild(card);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  fetchResults();
  setInterval(fetchResults, 10000);
});
