// Capture real product screenshots for the README.
const { chromium } = require("playwright");
const fs = require("fs");

const BASE = "http://127.0.0.1:8471";
const OUT = "/Users/efi/Hackathons/Agent Rush/airlock/docs/screenshots";

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: "/Users/efi/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });

  // 1. workbench
  await page.goto(BASE + "/");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: OUT + "/workbench.png", fullPage: true });
  console.log("workbench ✓");

  // 2. real task through the UI (fake-mode agent): upload + question
  await page.setInputFiles('input[name="file"]', "/tmp/demo.csv");
  await page.fill('textarea[name="question"]', "Which region generated the most revenue? Summarise the data.");
  await Promise.all([page.waitForURL("**/run/**"), page.click('button[type="submit"]')]);
  await page.waitForSelector("div.answer, div.verdict", { timeout: 30000 }); // result panel rendered
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT + "/run_complete.png", fullPage: true });
  console.log("run_complete ✓");

  // 3. attack page
  await page.goto(BASE + "/attack");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: OUT + "/attack_mode.png", fullPage: true });
  console.log("attack_mode ✓");

  // 4. attack absorbed (rm -rf)
  await Promise.all([page.waitForURL("**/run/**"), page.click('form[action="/attack/rm_rf"] button')]);
  await page.waitForSelector("div.verdict", { timeout: 30000 }); // ABSORBED verdict rendered
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT + "/attack_absorbed.png", fullPage: true });
  console.log("attack_absorbed ✓");

  // 5. receipts list + one receipt (latest by mtime)
  await page.goto(BASE + "/receipts");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: OUT + "/receipts.png", fullPage: true });
  const firstReceipt = await page.$eval('tbody tr td a[href^="/receipt/"]', a => a.getAttribute("href"));
  await page.goto(BASE + firstReceipt);
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: OUT + "/receipt.png", fullPage: true });
  console.log("receipts ✓");

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
