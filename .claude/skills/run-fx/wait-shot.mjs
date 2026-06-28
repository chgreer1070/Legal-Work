import { chromium } from 'playwright';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push('JS error: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('Console error: ' + m.text()); });
await page.goto(process.argv[2], { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
await page.screenshot({ path: process.argv[3], fullPage: true });
const chartReady = await page.evaluate(() => ({
  rateInstance: typeof rateChartInstance !== 'undefined' && rateChartInstance !== null,
  exposureInstance: typeof exposureChartInstance !== 'undefined' && exposureChartInstance !== null,
}));
console.log(JSON.stringify({ chartReady, errors }, null, 2));
await browser.close();
