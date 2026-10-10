(function () {
  'use strict';
  const rows = document.getElementById('results-body');
  const status = document.getElementById('results-status');
  let loading = false;
  async function refresh() {
    if (loading) return;
    loading = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch('/api/results', {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw new Error('unavailable');
      const results = await response.json();
      if (!Array.isArray(results)) throw new Error('invalid');
      const fragment = document.createDocumentFragment();
      for (const result of results) {
        if (!result || typeof result.playerName !== 'string' || typeof result.coachId !== 'string' || !Number.isSafeInteger(result.amount)) continue;
        const row = document.createElement('tr');
        for (const value of [result.playerName, result.coachId, result.amount]) {
          const cell = document.createElement('td'); cell.textContent = String(value); row.append(cell);
        }
        fragment.append(row);
      }
      rows.replaceChildren(fragment); status.textContent = results.length ? `已結算 ${results.length} 筆` : '尚無得標結果';
    } catch (_) { status.textContent = '離線／無法更新 · 保留最後結果'; }
    finally { clearTimeout(timeout); loading = false; }
  }
  refresh();
  const timer = setInterval(refresh, 3000);
  window.addEventListener('pagehide', () => clearInterval(timer), {once: true});
})();
