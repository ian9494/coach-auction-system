const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto("http://localhost:3000/");
  await page.setContent(`
    <canvas id="c" width="1720" height="356"></canvas>
    <img id="img" src="/UI__2.png" style="display:none">
  `, { waitUntil: "networkidle" });

  await page.evaluate(async () => {
    const img = document.getElementById("img");
    await new Promise((res) => (img.complete ? res() : (img.onload = res)));
    const c = document.getElementById("c");
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0, 1720, 356);
    window._img = ctx.getImageData(0, 0, 1720, 356);
  });

  // Look at roster pill area — around y=145-180 for row 1
  // The pill has bright green border on TOP and BOTTOM
  const result = await page.evaluate(() => {
    const d = window._img.data;
    const w = 1720, h = 356;
    const isBright = (i) => d[i] < 100 && d[i+1] > 130 && d[i+2] < 100;

    // Card 1 x range: 0 to 420
    // Card 2: 434 to 854
    // Card 3: 867 to 1287
    // Card 4: 1300 to 1720

    // Detect pill in card 1: find horizontal bright bands within y=140-180 in x=200-420
    const scanCard = (xStart, xEnd, yStart, yEnd) => {
      const bright = [];
      for (let y = yStart; y <= yEnd; y++) {
        for (let x = xStart; x <= xEnd; x++) {
          if (isBright((y*w+x)*4)) bright.push([x,y]);
        }
      }
      if (!bright.length) return null;
      const xs = bright.map(p=>p[0]), ys = bright.map(p=>p[1]);
      return {
        x0: Math.min(...xs), x1: Math.max(...xs),
        y0: Math.min(...ys), y1: Math.max(...ys),
        count: bright.length,
      };
    };

    // Card 1 pill area (right side of top area)
    const c1Pill = scanCard(200, 420, 140, 180);
    const c2Pill = scanCard(634, 854, 140, 180);
    const c3Pill = scanCard(1067, 1287, 140, 180);
    const c4Pill = scanCard(1500, 1720, 140, 180);
    // Row 2 pills
    const c5Pill = scanCard(200, 420, 260, 300);
    const c6Pill = scanCard(634, 854, 260, 300);

    // Card 1 avatar box area (left side of top area)
    // avatar likely spans y=125-190, x=0-100
    const c1Ava = scanCard(0, 200, 125, 195);

    // Card 1 frame edges — top edge
    const c1TopBand = scanCard(0, 420, 118, 130);

    return { c1Pill, c2Pill, c3Pill, c4Pill, c5Pill, c6Pill, c1Ava, c1TopBand };
  });

  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})();
