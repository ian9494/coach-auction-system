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

    // Avatar box is grayer/lighter than card bg
    // Card bg is dark green (r~10-25, g~25-45, b~10-25)
    // Avatar box is dark gray (r,g,b all ~50-90, close to each other)
    const isGrayBox = (i) => {
      const r = d[i], g = d[i+1], b = d[i+2];
      // Gray-ish and not too dark
      return r > 40 && r < 100 &&
             g > 40 && g < 100 &&
             b > 40 && b < 100 &&
             Math.abs(r - g) < 20 && Math.abs(g - b) < 20;
    };

    // Also detect hero avatar box
    const scanBox = (xStart, xEnd, yStart, yEnd) => {
      const bright = [];
      for (let y = yStart; y <= yEnd; y++) {
        for (let x = xStart; x <= xEnd; x++) {
          if (isGrayBox((y*w+x)*4)) bright.push([x,y]);
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

    // Card 1 (x=0-420) — left area for avatar
    const c1Ava = scanBox(0, 200, 120, 234);
    const c2Ava = scanBox(434, 634, 120, 234);
    const c3Ava = scanBox(867, 1067, 120, 234);
    const c4Ava = scanBox(1300, 1500, 120, 234);
    // Row 2 avatars
    const c5Ava = scanBox(0, 200, 238, 356);
    const c6Ava = scanBox(434, 634, 238, 356);

    // Hero avatar
    const heroAva = scanBox(0, 200, 14, 116);
    // Hero "剩餘時間" area (right side)
    const heroTime = scanBox(1500, 1720, 14, 116);

    return { c1Ava, c2Ava, c3Ava, c4Ava, c5Ava, c6Ava, heroAva, heroTime };
  });

  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})();
