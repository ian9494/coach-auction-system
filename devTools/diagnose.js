const { chromium } = require("playwright");
const path = require("path");

const outDir = path.resolve(__dirname, "..");

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // Screenshot WITHOUT PNG background
  await page.goto("http://localhost:3000/auction-overlay-redesign.html", {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  const noBgConsole = await page.$(".console");
  await noBgConsole.screenshot({ path: path.join(outDir, "shot_no_bg.png") });

  // Get measurements
  const measurements = await page.evaluate(() => {
    const consoleEl = document.querySelector(".console");
    const consoleRect = consoleEl.getBoundingClientRect();
    const rel = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        x: Math.round(r.left - consoleRect.left),
        y: Math.round(r.top - consoleRect.top),
        w: Math.round(r.width),
        h: Math.round(r.height),
      };
    };
    const cards = [...document.querySelectorAll(".cap")];
    return {
      console: { w: Math.round(consoleRect.width), h: Math.round(consoleRect.height) },
      hero: rel(document.querySelector(".hero")),
      pAva: rel(document.querySelector(".p-ava")),
      timer: rel(document.querySelector(".timer")),
      tRing: rel(document.querySelector(".t-ring")),
      bidBlock: rel(document.querySelector(".bid-block")),
      pPlate: rel(document.querySelector(".p-plate")),
      eyebrow: rel(document.querySelector(".eyebrow")),
      pName: rel(document.querySelector(".p-name")),
      cards: cards.map((c, i) => ({
        i,
        cap: rel(c),
        ava: rel(c.querySelector(".c-ava")),
        top: rel(c.querySelector(".top")),
        cinfo: rel(c.querySelector(".c-info")),
        cnames: rel(c.querySelector(".c-names")),
        czh: rel(c.querySelector(".c-zh")),
        roster: rel(c.querySelector(".roster")),
        cbid: rel(c.querySelector(".c-bid")),
        amt: rel(c.querySelector(".amt")),
        brow: rel(c.querySelector(".b-row")),
        btrack: rel(c.querySelector(".b-track")),
      })),
    };
  });
  console.log(JSON.stringify(measurements, null, 2));

  // Screenshot WITH PNG background
  await page.goto("http://localhost:3000/auction-overlay-redesign.html?bg=ui2", {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  const withBg = await page.$(".console");
  await withBg.screenshot({ path: path.join(outDir, "shot_bg.png") });

  await browser.close();
})();
