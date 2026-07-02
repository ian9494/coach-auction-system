let lastRenderSignature = "";
let stopAutoScroll = [];

async function fetchResults() {
  try {
    const [resultsResponse, coachesResponse] = await Promise.all([
      fetch("/api/results"),
      fetch("/api/coaches"),
    ]);
    const [results, coaches] = await Promise.all([
      resultsResponse.json(),
      coachesResponse.json(),
    ]);
    const renderSignature = JSON.stringify({ results, coaches });
    if (renderSignature !== lastRenderSignature) {
      lastRenderSignature = renderSignature;
      renderResults(results, coaches);
    }

    const loadingEl = document.getElementById("loading");
    if (loadingEl) loadingEl.style.display = "none";
  } catch (err) {
    console.error("Failed to fetch results:", err);

    const loadingEl = document.getElementById("loading");
    if (loadingEl) loadingEl.textContent = "資料載入失敗，請確認伺服器狀態";
  }
}

function renderResults(results, coaches) {
  const grid = document.getElementById("grid");
  if (!grid) return;

  stopAutoScroll.forEach((stop) => stop());
  stopAutoScroll = [];
  grid.innerHTML = "";

  const lastRecord = results.length > 0 ? results[results.length - 1] : null;
  const teams = {};
  coaches.forEach((coach) => {
    teams[coach.id] = [];
  });

  results.forEach((record) => {
    if (teams[record.coachId]) {
      teams[record.coachId].push(record);
    }
  });

  coaches.forEach((coach) => {
    const coachId = coach.id;
    const members = teams[coachId];
    const card = document.createElement("div");
    const isNewTeam = lastRecord && lastRecord.coachId === coachId;
    card.className = `coach-card${isNewTeam ? " is-latest" : ""}`;

    card.innerHTML = `
      <div class="coach-name">
        <span class="coach-title">${coach.name}</span>
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

  requestAnimationFrame(() => {
    grid.querySelectorAll(".member-list").forEach((list) => {
      const stop = startAutoScroll(list);
      if (stop) stopAutoScroll.push(stop);
    });
  });
}

function startAutoScroll(list) {
  const maxScroll = () => Math.max(0, list.scrollHeight - list.clientHeight);
  if (maxScroll() <= 1) return null;

  list.classList.add("is-scrollable");

  const pauseDuration = 1800;
  const scrollStep = () => Math.max(28, Math.floor(list.clientHeight * 0.75));
  let direction = 1;
  let timer = 0;
  let stopped = false;

  function advance() {
    if (stopped) return;

    const limit = maxScroll();
    if (limit <= 1) return;

    let nextTop = list.scrollTop + direction * scrollStep();

    if (nextTop >= limit) {
      nextTop = limit;
      direction = -1;
    } else if (nextTop <= 0) {
      nextTop = 0;
      direction = 1;
    }

    list.scrollTo({ top: nextTop, behavior: "smooth" });
  }

  timer = setInterval(advance, pauseDuration);
  setTimeout(advance, 600);

  return () => {
    stopped = true;
    clearInterval(timer);
    list.classList.remove("is-scrollable");
  };
}

document.addEventListener("DOMContentLoaded", () => {
  fetchResults();
  setInterval(fetchResults, 10000);
});
