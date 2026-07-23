const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  await page.goto(
    "http://localhost:3000/auction-overlay-redesign.html?bg=ui2",
    { waitUntil: "networkidle" }
  );
  await page.waitForTimeout(1500);

  const consoleEl = await page.$(".console");
  await consoleEl.screenshot({ path: path.resolve(__dirname, "..", "shot_big.png") });

  await browser.close();
})();
