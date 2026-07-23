const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto("http://localhost:3000/UI__2.png");
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

  // Detect "bright green" pixels — the frame color (r<80, g>150, b<80)
  const result = await page.evaluate(() => {
    const d = window._img.data;
    const w = 1720, h = 356;
    const isBright = (i) => d[i] < 100 && d[i+1] > 130 && d[i+2] < 100;

    // Find bright edges — sample each row/col
    const rowsWithBright = [];
    for (let y = 0; y < h; y++) {
      let cnt = 0;
      for (let x = 0; x < w; x++) {
        if (isBright((y*w+x)*4)) cnt++;
      }
      if (cnt > 5) rowsWithBright.push({ y, cnt });
    }

    // Find contiguous horizontal bright bands (progress bars)
    const bands = [];
    let bandStart = -1;
    for (let y = 0; y < h; y++) {
      const inBand = rowsWithBright.some(r => r.y === y && r.cnt > 200);
      if (inBand && bandStart < 0) bandStart = y;
      else if (!inBand && bandStart >= 0) {
        bands.push({ y0: bandStart, y1: y - 1, h: y - bandStart });
        bandStart = -1;
      }
    }
    if (bandStart >= 0) bands.push({ y0: bandStart, y1: h-1, h: h - bandStart });

    // Sample x-band for card frame edges at mid-y=180 (mid of first row of cards)
    const scanX = (yStart, yEnd) => {
      const brightCols = [];
      for (let x = 0; x < w; x++) {
        let cnt = 0;
        for (let y = yStart; y < yEnd; y++) {
          if (isBright((y*w+x)*4)) cnt++;
        }
        if (cnt > 5) brightCols.push(x);
      }
      return brightCols;
    };

    const row1BrightCols = scanX(120, 236);  // between hero and gap
    const row2BrightCols = scanX(240, 356);

    return {
      brightRows: rowsWithBright.slice(0, 40).map(r => `y=${r.y} cnt=${r.cnt}`),
      bands: bands,
      row1EdgesSample: row1BrightCols.slice(0, 40),
      row1EdgeCount: row1BrightCols.length,
    };
  });

  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})();
