/* Public projection only. UI countdown never settles an auction. */
(function (global) {
  'use strict';
  function publicSnapshot(data) {
    if (!data || !Number.isSafeInteger(data.version) || data.version < 0 ||
        !['idle', 'running', 'paused', 'ended'].includes(data.status)) return null;
    const coaches = Array.isArray(data.coaches) ? data.coaches.filter(c => c &&
      typeof c.id === 'string' && typeof c.name === 'string').map(c => ({id: c.id, name: c.name})) : [];
    const teams = Object.create(null), budgets = Object.create(null);
    for (const c of coaches) {
      const team = data.teams && data.teams[c.id];
      teams[c.id] = Array.isArray(team) ? team.filter(name => typeof name === 'string').slice() : [];
      const budget = data.budgets && data.budgets[c.id];
      budgets[c.id] = Number.isSafeInteger(budget) && budget >= 0 ? budget : 0;
    }
    const number = (value, fallback = 0) => typeof value === 'number' && Number.isFinite(value) ? value : fallback;
    return {version: data.version, round_id: typeof data.round_id === 'string' ? data.round_id : null,
      status: data.status, current_player: typeof data.current_player === 'string' ? data.current_player : null,
      duration: number(data.duration), time_left: number(data.time_left), remaining_seconds: number(data.remaining_seconds, number(data.time_left)),
      deadline_utc: typeof data.deadline_utc === 'number' && Number.isFinite(data.deadline_utc) ? data.deadline_utc : null,
      minimum_bid: number(data.minimum_bid), coaches, teams, budgets,
      winner: data.status === 'ended' && typeof data.winner === 'string' ? data.winner : null,
      winning_amount: data.status === 'ended' && Number.isSafeInteger(data.winning_amount) && data.winning_amount >= 0 ? data.winning_amount : null};
  }
  class ViewerModel {
    constructor(now = () => Date.now() / 1000) {
      this.now = now; this.latest_version = -1; this.state = null; this.receivedAt = 0;
    }
    apply(data) {
      const snapshot = publicSnapshot(data);
      if (!snapshot || snapshot.version < this.latest_version) return false;
      // At the same version only display time can change. Never move it backwards.
      if (snapshot.version === this.latest_version && snapshot.status === 'running' && this.state &&
          snapshot.remaining_seconds > this.state.remaining_seconds) return false;
      this.state = snapshot; this.latest_version = snapshot.version; this.receivedAt = this.now(); return true;
    }
    countdown() {
      if (!this.state) return 0;
      const s = this.state;
      const remaining = s.status !== 'running' ? s.remaining_seconds : s.deadline_utc !== null ?
        s.deadline_utc - this.now() : s.remaining_seconds - (this.now() - this.receivedAt);
      return Math.ceil(Math.max(0, remaining));
    }
  }
  function loadImage(image, folder, name) {
    const fallback = '/final-project/fallback-avatar.svg';
    if (!name) { image.onerror = null; image.src = fallback; return; }
    const paths = ['jpg', 'jpeg', 'png'].map(extension => `/assets/${folder}/${encodeURIComponent(name)}.${extension}`);
    let index = 0;
    image.onerror = () => {
      index += 1;
      if (index < paths.length) image.src = paths[index];
      else { image.onerror = null; image.src = fallback; }
    };
    image.src = paths[0];
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }
  function startViewer() {
    const model = new ViewerModel();
    const socket = global.io({transports: ['websocket', 'polling']});
    const connection = document.getElementById('connection');
    const player = document.getElementById('current-player');
    const avatar = document.getElementById('player-avatar');
    const grid = document.getElementById('coach-grid');
    const result = document.getElementById('result');
    let renderedVersion = -1, previousPlayer = null, joinRetry = null;
    const statuses = {idle: '等待競標', running: '密封競標進行中', paused: '競標暫停', ended: '競標已結束'};
    function render() {
      const s = model.state;
      if (!s) return;
      document.getElementById('countdown').textContent = String(model.countdown());
      document.getElementById('status').textContent = statuses[s.status];
      player.textContent = s.current_player || '等待選手';
      document.getElementById('minimum').textContent = String(s.minimum_bid);
      if (s.current_player !== previousPlayer) { loadImage(avatar, 'players', s.current_player); previousPlayer = s.current_player; }
      result.textContent = s.status === 'ended' ? (s.winner ?
        `${s.coaches.find(c => c.id === s.winner)?.name || s.winner} 得標 · 成交價 ${s.winning_amount}` : '本輪無得標者') : '出價保密，結算後公布得標結果';
      document.getElementById('viewer-root').dataset.status = s.status;
      if (renderedVersion === s.version) return;
      renderedVersion = s.version;
      const fragment = document.createDocumentFragment();
      for (const c of s.coaches) {
        const card = element('article', 'coach-card'); card.dataset.coachId = c.id;
        if (s.status === 'ended' && s.winner === c.id) card.classList.add('winner');
        const image = element('img', 'coach-avatar'); image.alt = c.name; loadImage(image, 'coaches', c.id);
        const details = element('div', 'coach-details');
        details.append(element('h2', '', c.name), element('p', 'budget', `剩餘預算 ${s.budgets[c.id]}`),
          element('p', 'team-count', `隊伍 ${s.teams[c.id].length} / 5`));
        const team = element('ul', 'team-list');
        for (const name of s.teams[c.id]) team.append(element('li', '', name));
        if (!s.teams[c.id].length) team.append(element('li', 'empty', '尚無隊員'));
        card.append(image, details, team); fragment.append(card);
      }
      grid.replaceChildren(fragment);
    }
    function accept(snapshot) { if (model.apply(snapshot)) render(); }
    function joinViewer() {
      connection.textContent = '取得最新狀態…';
      const sid = socket.id;
      socket.timeout(5000).emit('join_viewer', {}, (error, ack) => {
        if (!socket.connected || socket.id !== sid) return;
        if (error || !ack?.ok) {
          connection.textContent = '無法加入，稍後重試';
          joinRetry = global.setTimeout(() => { if (socket.connected) joinViewer(); }, 2000);
          return;
        }
        accept(ack.payload.snapshot); connection.textContent = '已連線';
      });
    }
    socket.on('connect', () => {
      global.clearTimeout(joinRetry);
      joinViewer();
    });
    socket.on('viewer_state', accept);
    socket.on('disconnect', reason => {
      global.clearTimeout(joinRetry);
      connection.textContent = '離線 · 保留最後畫面';
      if (reason === 'io server disconnect') socket.connect();
    });
    socket.on('connect_error', () => { connection.textContent = '連線失敗 · 重連中'; });
    const timer = global.setInterval(render, 250);
    global.addEventListener('pagehide', () => {
      global.clearInterval(timer); global.clearTimeout(joinRetry); socket.disconnect();
    }, {once: true});
    loadImage(avatar, 'players', null);
  }
  global.FinalProjectViewer = {ViewerModel, publicSnapshot, loadImage};
  if (typeof document !== 'undefined' && document.getElementById('viewer-root')) startViewer();
})(typeof window !== 'undefined' ? window : globalThis);
