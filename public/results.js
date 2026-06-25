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
  if (list.scrollHeight <= list.clientHeight + 1) return null;

  const speed = 18;
  const pauseDuration = 1800;
  let direction = 1;
  let lastTime = performance.now();
  let pausedUntil = lastTime + pauseDuration;
  let animationFrame = 0;
  let stopped = false;

  function animate(now) {
    if (stopped) return;

    const elapsed = Math.min(now - lastTime, 100);
    lastTime = now;

    if (now >= pausedUntil) {
      list.scrollTop += direction * speed * (elapsed / 1000);

      const maxScroll = list.scrollHeight - list.clientHeight;
      if (list.scrollTop >= maxScroll - 1) {
        list.scrollTop = maxScroll;
        direction = -1;
        pausedUntil = now + pauseDuration;
      } else if (list.scrollTop <= 1) {
        list.scrollTop = 0;
        direction = 1;
        pausedUntil = now + pauseDuration;
      }
    }

    animationFrame = requestAnimationFrame(animate);
  }

  animationFrame = requestAnimationFrame(animate);

  return () => {
    stopped = true;
    cancelAnimationFrame(animationFrame);
  };
}

document.addEventListener("DOMContentLoaded", () => {
  fetchResults();
  setInterval(fetchResults, 10000);
});
