const socket = io();

const INITIAL_BUDGET = 1000;
const RING_LENGTH = 245;
const imageFallback =
  "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
const imageExtensions = ["jpg", "jpeg", "png"];

let coaches = [];
let currentPlayer = null;
let displayedPlayer = null;
let roundDuration = 1;
let previousBids = {};
let previousStatus = "idle";

const $ = (id) => document.getElementById(id);
const formatAmount = (amount) => `$${Number(amount).toLocaleString("zh-TW")}`;

function getCoachName(coachId) {
  return coaches.find((coach) => coach.id === coachId)?.name ?? coachId;
}

function getAssetImages(folder, name) {
  const encodedName = encodeURIComponent(name);
  return imageExtensions.map((extension) => `./assets/${folder}/${encodedName}.${extension}`);
}

function getTeamSize(history, coachId) {
  return history.filter((record) => record.winner === coachId).length;
}

function getBidSummary(bids = {}) {
  const entries = Object.entries(bids).filter(
    ([, amount]) => Number.isFinite(amount) && amount > 0,
  );
  if (!entries.length) return { highest: null, leaders: [] };

  const highest = Math.max(...entries.map(([, amount]) => amount));
  return {
    highest,
    leaders: entries.filter(([, amount]) => amount === highest).map(([coachId]) => coachId),
  };
}

function setImage(container, sources, fallbackText) {
  container.replaceChildren();
  const img = document.createElement("img");
  img.alt = fallbackText;
  const candidates = Array.isArray(sources) ? sources : [sources];
  let candidateIndex = 0;
  img.onerror = () => {
    candidateIndex += 1;
    if (candidateIndex < candidates.length) {
      img.src = candidates[candidateIndex];
      return;
    }
    img.remove();
    container.textContent = fallbackText.slice(0, 1) || "-";
  };
  img.src = candidates[candidateIndex];
  container.appendChild(img);
}

function buildGrid() {
  $("grid").innerHTML = coaches
    .map(
      (coach, index) => `
        <article class="cap" data-coach-id="${coach.id}" data-state="idle">
          <div class="lead-badge">領先</div>
          <div class="top">
            <div class="c-ava" id="coachAvatar${index}"></div>
            <div class="c-info">
              <div class="c-heading">
                <div class="c-names">
                  <div class="c-zh">${coach.name}</div>
                </div>
              </div>
              <div class="c-bid">
                <span class="amt num" id="amount${index}">尚未出價</span>
                <span class="tag" id="tag${index}"></span>
                <span class="roster">隊員 <b class="num" id="roster${index}">0</b> 位</span>
              </div>
            </div>
          </div>
          <div class="budget">
            <div class="b-row"><span>剩餘預算</span><b class="num" id="budget${index}">$0</b></div>
            <div class="b-track"><div class="b-fill" id="budgetFill${index}" style="width:0"></div></div>
          </div>
        </article>`,
    )
    .join("");

  coaches.forEach((coach, index) => {
    setImage($("coachAvatar" + index), getAssetImages("coaches", coach.id), coach.name);
  });
}

function renderHero(state, bidSummary) {
  const playerName = state.currentPlayer || "等待下一位選手";
  $("pName").textContent = playerName;
  $("pEn").textContent = `底價 ${formatAmount(state.minimumBid || 0)}`;
  if (state.currentPlayer !== displayedPlayer) {
    displayedPlayer = state.currentPlayer;
    setImage(
      $("pAva"),
      state.currentPlayer ? getAssetImages("players", state.currentPlayer) : imageFallback,
      playerName,
    );
  }

  const amount = $("bidAmt");
  amount.dataset.result = state.status === "ended" ? (state.winner ? "winner" : "failed") : "";
  const nextAmount =
    state.status === "ended" && state.winner
      ? `得標：${getCoachName(state.winner)}`
      : state.status === "ended"
        ? "本輪流標"
        : bidSummary.highest === null
          ? "尚未出價"
          : formatAmount(bidSummary.highest);
  if (amount.textContent !== nextAmount) {
    amount.textContent = nextAmount;
    amount.classList.remove("pop");
    void amount.offsetWidth;
    amount.classList.add("pop");
  }

  const chip = $("leadChip");
  if (state.status === "ended" && state.winner) {
    chip.style.visibility = "visible";
    chip.textContent =
      state.winningAmount !== null && state.winningAmount !== undefined
        ? formatAmount(state.winningAmount)
        : "得標";
  } else if (bidSummary.leaders.length) {
    chip.style.visibility = "visible";
    chip.textContent =
      bidSummary.leaders.length > 2
        ? `${bidSummary.leaders.length} 位教練並列`
        : bidSummary.leaders.map(getCoachName).join(" / ");
  } else {
    chip.style.visibility = "hidden";
  }
}

function renderTimer(state) {
  const timeLeft = Number.isFinite(state.timeLeft) ? Math.max(0, state.timeLeft) : 0;
  if (state.currentPlayer !== currentPlayer) {
    currentPlayer = state.currentPlayer;
    roundDuration = Math.max(1, timeLeft);
  } else if (timeLeft > roundDuration) {
    roundDuration = timeLeft;
  }

  $("tNum").textContent = timeLeft;
  $("tBar").style.strokeDashoffset =
    RING_LENGTH * (1 - Math.min(1, timeLeft / roundDuration));

  const timer = $("timerBox");
  timer.classList.toggle("warn", timeLeft <= 30 && timeLeft > 10);
  timer.classList.toggle("crit", timeLeft <= 10 && state.status === "running");
  timer.querySelector(".t-label").textContent = state.status === "paused" ? "已暫停" : "剩餘時間";
}

function renderCards(state, bidSummary) {
  coaches.forEach((coach, index) => {
    const card = document.querySelector(`[data-coach-id="${coach.id}"]`);
    const bid = state.bids?.[coach.id];
    const hasBid = Number.isFinite(bid) && bid > 0;
    const isLeader = hasBid && bid === bidSummary.highest;
    const budget = Number.isFinite(state.budgets?.[coach.id]) ? state.budgets[coach.id] : 0;

    card.dataset.state = isLeader ? "lead" : hasBid ? "out" : "idle";
    $("amount" + index).textContent = hasBid ? formatAmount(bid) : "尚未出價";
    $("tag" + index).textContent = isLeader ? "目前最高價" : hasBid ? "已出價" : "";
    $("budget" + index).textContent = formatAmount(budget);
    $("budgetFill" + index).style.width = `${Math.max(0, Math.min(100, (budget / INITIAL_BUDGET) * 100))}%`;
    $("roster" + index).textContent = getTeamSize(state.history || [], coach.id);
  });
}

function updateTicker(state) {
  for (const [coachId, amount] of Object.entries(state.bids || {})) {
    if (!Number.isFinite(amount) || amount <= 0) continue;
    if (previousBids[coachId] === amount) continue;
    const entry = document.createElement("span");
    entry.className = "entry";
    entry.innerHTML = `<b>${getCoachName(coachId)}</b> 出價 <b class="num">${formatAmount(amount)}</b>`;
    const separator = document.createElement("span");
    separator.className = "sep";
    separator.textContent = "/";
    $("tickerBody").prepend(entry, separator);
  }

  while ($("tickerBody").children.length > 10) {
    $("tickerBody").lastElementChild.remove();
  }
  previousBids = { ...(state.bids || {}) };
}

function renderResult(state) {
  const stamp = $("stamp");
  const word = $("stampWord");
  const isNewResult = state.status === "ended" && previousStatus !== "ended";

  if (state.status !== "ended") {
    stamp.classList.remove("show");
    return;
  }

  word.classList.toggle("fail", !state.winner);
  word.textContent = state.winner ? "得標" : "流標";
  $("stampSub").textContent = state.winner
    ? `${getCoachName(state.winner)} ${state.winningAmount !== null && state.winningAmount !== undefined ? formatAmount(state.winningAmount) : ""}`
    : "本輪無人出價";
  stamp.classList.add("show");

  if (isNewResult && state.winner) {
    const winningCard = document.querySelector(`[data-coach-id="${state.winner}"]`);
    winningCard?.classList.add("won");
    setTimeout(() => winningCard?.classList.remove("won"), 1300);
  }
}

function renderState(state) {
  if (state.coaches && JSON.stringify(state.coaches) !== JSON.stringify(coaches)) {
    coaches = state.coaches;
    buildGrid();
  }

  const bidSummary = getBidSummary(state.bids || {});
  renderHero(state, bidSummary);
  renderTimer(state);
  renderCards(state, bidSummary);
  updateTicker(state);
  renderResult(state);
  previousStatus = state.status;
}

socket.emit("join_viewer");
socket.on("viewer_state", renderState);
