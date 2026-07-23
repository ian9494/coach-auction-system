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

  const result = await page.evaluate(() => {
    const d = window._img.data;
    const w = 1720, h = 356;

    // Detect any non-black pixels in hero right area
    const isNonBlack = (i) => {
      const r = d[i], g = d[i+1], b = d[i+2];
      return r > 20 || g > 20 || b > 20;
    };

    // Detect medium green tones (frame edges, various)
    const isGreenish = (i) => {
      const r = d[i], g = d[i+1], b = d[i+2];
      return g > 40 && g > r * 1.3;
    };

    // Detect bright green
    const isBright = (i) => d[i] < 100 && d[i+1] > 130 && d[i+2] < 100;

    const scanBox = (predicate, xStart, xEnd, yStart, yEnd) => {
      const bright = [];
      for (let y = yStart; y <= yEnd; y++) {
        for (let x = xStart; x <= xEnd; x++) {
          if (predicate((y*w+x)*4)) bright.push([x,y]);
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

    // Hero right side - detect frame edges (greenish)
    const heroRightBright = scanBox(isBright, 1500, 1720, 14, 116);
    const heroRightGreen = scanBox(isGreenish, 1500, 1720, 14, 116);
    // Sample specific columns to find rectangular box edges
    const sampleColHero = (x) => {
      const ys = [];
      for (let y = 14; y <= 116; y++) {
        const i = (y*w+x)*4;
        if (isBright(i) || isGreenish(i)) ys.push(y);
      }
      return { x, ys };
    };
    const heroCols = [1550, 1580, 1620, 1660, 1700].map(sampleColHero);

    return { heroRightBright, heroRightGreen, heroCols: heroCols.map(c => ({x:c.x, yCount:c.ys.length, first:c.ys[0], last:c.ys[c.ys.length-1]})) };
  });

  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})();
