const { chromium } = require("playwright");
const path = require("path");

const outPath = path.resolve(__dirname, "..", "shot.png");

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
  if (!consoleEl) throw new Error(".console not found");

  await consoleEl.screenshot({ path: outPath });
  console.log("Saved:", outPath);

  await browser.close();
})();
