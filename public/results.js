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
    const response = await fetch('/api/results');
    const data = await response.json();
    renderResults(data);
    const loadingEl = document.getElementById('loading');
    if (loadingEl) loadingEl.style.display = 'none';
  } catch (err) {
    console.error('Failed to fetch results:', err);
    const loadingEl = document.getElementById('loading');
    if (loadingEl) loadingEl.textContent = '資料載入失敗，請檢查伺服器狀態。';
  }
}

function renderResults(results) {
  const grid = document.getElementById('grid');
  if (!grid) return;
  grid.innerHTML = '';

  // 取得最新的一筆成交紀錄
  const lastRecord = results.length > 0 ? results[results.length - 1] : null;

  // 整理資料：按教練分類
  const teams = {};
  Object.keys(COACH_NAMES).forEach(id => teams[id] = []);
  
  results.forEach(record => {
    if (teams[record.coachId]) {
      teams[record.coachId].push(record);
    }
  });

  // 渲染每個教練的卡片
  Object.keys(COACH_NAMES).forEach(coachId => {
    const members = teams[coachId];
    const card = document.createElement('div');
    card.className = 'coach-card';
    
    // 如果這隊包含了最新成員，且該教練就是該成員的教練，則加強卡片外框
    const isNewTeam = lastRecord && lastRecord.coachId === coachId;
    if (isNewTeam) {
      card.style.border = '2px solid rgba(255, 209, 102, 0.6)';
      card.style.boxShadow = '0 0 15px rgba(255, 209, 102, 0.2)';
    }

    card.innerHTML = `
      <div class="coach-name">
        <span style="${isNewTeam ? 'color: #ffd166; text-shadow: 0 0 8px rgba(255,209,102,0.5);' : ''}">${COACH_NAMES[coachId]}</span>
        <span style="font-size: 1rem; color: #64748b;">(已選 ${members.length})</span>
      </div>
      <ul class="member-list">
        ${members.length > 0 ? members.map(m => {
          const isLatest = lastRecord && m.playerName === lastRecord.playerName && m.coachId === lastRecord.coachId && m.amount === lastRecord.amount;
          return `
            <li class="member-item ${isLatest ? 'new-member' : ''}">
              <span>${m.playerName}</span>
              <span class="member-price">$${m.amount}</span>
            </li>
          `;
        }).join('') : '<li class="member-item" style="color: #475569;">尚無成員</li>'}
      </ul>
    `;
    grid.appendChild(card);
  });
}

// 初次讀取
document.addEventListener('DOMContentLoaded', () => {
  fetchResults();
  // 設定每 10 秒更新一次
  setInterval(fetchResults, 10000);
});
