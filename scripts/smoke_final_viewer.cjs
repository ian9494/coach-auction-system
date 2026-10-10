/* Optional Playwright smoke; stdin contains only temporary test credentials. */
const fs = require('node:fs');
const zlib = require('node:zlib');
const { chromium } = require(process.env.FINAL_PROJECT_PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const url = new URL(config.url);
  if (url.hostname !== '127.0.0.1' || ['3000', '3001'].includes(url.port)) throw new Error('Test URL must use loopback ephemeral port');
  const browser = await chromium.launch({headless: true, ...(process.env.FINAL_PROJECT_BROWSER_EXECUTABLE ?
    {executablePath: process.env.FINAL_PROJECT_BROWSER_EXECUTABLE} : {})});
  const errors = [], frames = [], outside = [];
  try {
    const context = await browser.newContext({viewport: {width: 1920, height: 1080}});
    await context.addInitScript(wall => { Date.now = () => wall * 1000; }, config.clock || 1000);
    context.on('request', request => { if (new URL(request.url()).origin !== url.origin) outside.push(request.url()); });
    const page = await context.newPage();
    await page.addInitScript(() => {
      let factory;
      Object.defineProperty(window, 'io', {configurable:true, get:() => factory, set:fn => {
        factory = (...args) => { const socket = fn(...args); window.__testViewerSocket = socket; return socket; };
      }});
    });
    page.on('pageerror', error => errors.push(error.name));
    page.on('websocket', ws => ws.on('framereceived', event => {
      const payload = String(event.payload);
      if (payload.startsWith('42')) {
        try { const message = JSON.parse(payload.slice(2)); if (message[0] === 'viewer_state') frames.push(message[1]); } catch (_) {}
      }
    }));
    await page.goto(config.url + '/final-project/viewer.html');
    await page.waitForFunction(() => document.getElementById('connection').textContent === '已連線');
    const control = await context.newPage();
    await control.goto(config.url + '/final-project/results.html');
    await control.addScriptTag({url: config.url + '/vendor/socket.io.min.js'});
    await control.evaluate(async auth => {
      async function joined(event, payload) {
        const socket = io({transports: ['websocket']});
        await new Promise((resolve, reject) => { socket.once('connect', resolve); socket.once('connect_error', reject); });
        const ack = await socket.timeout(5000).emitWithAck(event, payload);
        if (!ack.ok) throw new Error('Auth failed');
        return socket;
      }
      window.testAdmin = await joined('join_admin', {token: auth.admin});
      window.testCoaches = [await joined('join_coach', {coachId:'coach01', token:auth.coach01}),
        await joined('join_coach', {coachId:'coach02', token:auth.coach02})];
      window.testRound = null;
    }, config.auth);
    async function command(event, fields = {}, coachIndex = null) {
      return control.evaluate(async ({event, fields, coachIndex}) => {
        const data = {request_id: crypto.randomUUID().replaceAll('-', ''), ...fields};
        if (event !== 'start_auction') data.round_id = window.testRound;
        const socket = coachIndex === null ? window.testAdmin : window.testCoaches[coachIndex];
        const ack = await socket.timeout(5000).emitWithAck(event, data);
        if (!ack.ok) throw new Error('Command rejected');
        window.testRound = ack.round_id; return ack;
      }, {event, fields, coachIndex});
    }
    await command('start_auction', {playerName: 'Player01', duration: 90});
    await page.waitForFunction(() => document.getElementById('current-player').textContent === 'Player01');
    await command('submit_bid', {amount: 213}, 0);
    const lastBid = await command('submit_bid', {amount: 317}, 1);
    // Wait for actual Viewer websocket payloads, not Admin acknowledgements.
    const deadline = Date.now() + 5000;
    while (!frames.some(frame => frame.version === lastBid.version)) {
      if (Date.now() > deadline) throw new Error('Viewer frame timeout');
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    const body = await page.locator('body').innerText();
    if (body.includes('213') || body.includes('317') || (await page.locator('.winner').count())) throw new Error('Running display leak');
    await command('pause_auction');
    await page.waitForFunction(() => document.getElementById('status').textContent === '競標暫停');
    await command('resume_auction');
    await page.waitForFunction(() => document.getElementById('status').textContent === '密封競標進行中');
    await command('end_auction');
    await page.waitForFunction(() => document.getElementById('result').textContent.includes('Coach02 得標 · 成交價 317'));
    if (await page.locator('.winner').count() !== 1) throw new Error('Winner highlight missing');
    await control.waitForFunction(() => document.getElementById('results-body').textContent.includes('Player01coach02317'));
    await command('start_auction', {playerName: 'Player02', duration: 90});
    await page.waitForFunction(() => document.getElementById('current-player').textContent === 'Player02');
    if (await page.locator('.winner').count()) throw new Error('Old highlight retained');
    // Drop the actual socket and let the JS client rejoin automatically.
    await page.evaluate(() => window.__testViewerSocket.io.engine.close());
    await page.waitForFunction(() => document.getElementById('connection').textContent.includes('離線'));
    if (await page.locator('#current-player').textContent() !== 'Player02') throw new Error('Disconnect cleared state');
    await command('pause_auction');
    await page.waitForFunction(() => document.getElementById('connection').textContent === '已連線', null, {timeout:15000});
    if (await page.locator('#current-player').textContent() !== 'Player02') throw new Error('Reconnect state mismatch');
    await page.waitForFunction(() => document.getElementById('status').textContent === '競標暫停');
    await command('resume_auction');
    await page.waitForFunction(() => document.getElementById('status').textContent === '密封競標進行中');
    const transparent = await context.newPage();
    transparent.on('pageerror', error => errors.push(error.name));
    await transparent.goto(config.url + '/final-project/viewer-transparent.html');
    await transparent.waitForFunction(() => document.querySelectorAll('.coach-card').length === 8);
    const backgrounds = await transparent.evaluate(() => ['body', '#viewer-root', '.feed-zone'].map(
      selector => getComputedStyle(document.querySelector(selector)).backgroundColor));
    if (backgrounds.some(color => color !== 'rgba(0, 0, 0, 0)')) throw new Error('Overlay not transparent');
    const layout = await transparent.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.coach-card'));
      return {rows:new Set(cards.map(card => Math.round(card.getBoundingClientRect().top))).size,
        columns:getComputedStyle(document.getElementById('coach-grid')).gridTemplateColumns.split(' ').length,
        bottom:document.getElementById('coach-grid').getBoundingClientRect().bottom};
    });
    if (layout.rows !== 2 || layout.columns !== 4 || layout.bottom > 1080) throw new Error('2x4 overlay layout invalid');
    await transparent.waitForFunction(() => Array.from(document.querySelectorAll('img')).every(image => image.complete && image.naturalWidth > 0));
    const forbidden = new Set(['bids','allBids','myBid','bidRules','eligible','leader','highestBid','highestBidder','highest_amount','processed','last_award_undo']);
    function check(value) {
      if (value && typeof value === 'object') for (const [key, child] of Object.entries(value)) {
        if (forbidden.has(key)) throw new Error('Network projection leak'); check(child);
      }
    }
    for (const frame of frames) {
      check(frame);
      if (frame.status === 'running' && (frame.winner !== null || frame.winning_amount !== null)) throw new Error('Early result leak');
    }
    if (!frames.some(frame => frame.status === 'running') || !frames.some(frame => frame.status === 'ended')) throw new Error('Missing network evidence');
    // DOM injection is literal text, and stale versions cannot undo the latest round.
    await page.evaluate(() => {
      const m = new FinalProjectViewer.ViewerModel(() => 1000);
      m.apply({version:12,status:'running',current_player:'<img src=x onerror=alert(1)>',coaches:[],teams:{},budgets:{},time_left:90});
      m.apply({version:11,status:'ended',coaches:[]});
      if (m.latest_version !== 12) throw new Error('Stale version accepted');
      window.__testViewerSocket.emitEvent(['viewer_state', {version:99999,status:'running',
        current_player:'<img src=x onerror=alert(1)>',coaches:[{id:'test',name:'<script>alert(1)</script>'}],
        teams:{test:['<b>literal player</b>']},budgets:{test:1000},time_left:90,
        allBids:{test:987},myBid:654,leader:'PRIVATE'}]);
    });
    if (await page.locator('#current-player').textContent() !== '<img src=x onerror=alert(1)>') throw new Error('Name rendering mismatch');
    if (await page.locator('[onerror], #coach-grid script, #coach-grid b').count()) throw new Error('HTML injection');
    const injectedText = await page.locator('body').innerText();
    if (injectedText.includes('987') || injectedText.includes('654') || injectedText.includes('PRIVATE')) throw new Error('Unknown fields rendered');
    if (errors.length || outside.length) throw new Error('Page error or external runtime dependency');
    const screenshot = await transparent.screenshot({...(config.screenshot ? {path:config.screenshot} : {}), omitBackground:true});
    const chunks = []; let offset = 8;
    while (offset < screenshot.length) {
      const length = screenshot.readUInt32BE(offset), type = screenshot.toString('ascii', offset + 4, offset + 8);
      if (type === 'IDAT') chunks.push(screenshot.subarray(offset + 8, offset + 8 + length));
      offset += length + 12;
    }
    // RGBA PNG first pixel has no left/above predictor for any PNG filter.
    if (screenshot[25] !== 6 || zlib.inflateSync(Buffer.concat(chunks))[4] !== 0) throw new Error('Overlay canvas alpha is not transparent');
    console.log(JSON.stringify({ok:true, viewer_frames:frames.length, running_payload_private_fields:0,
      page_errors:errors.length, external_requests:outside.length, transparent_backgrounds:backgrounds,
      layout, transparent_pixel_alpha:0, reconnect:true, results:true}));
    await context.close();
  } finally { await browser.close(); }
}
main().catch(error => { console.error('Viewer smoke failed: ' + error.message); process.exitCode = 1; });
