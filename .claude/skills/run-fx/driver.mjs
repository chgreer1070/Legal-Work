#!/usr/bin/env node
// FX Recovery System driver.
//
// Subcommands:
//   shot <url> [out]        Screenshot a single page.
//   smoke [outdir]          Dashboard + Contracts screenshots, prints summary.
//   click <url> <selector>  Open url, click selector, screenshot result.
//
// All paths are relative to the repo root. Assumes:
//   - the FX app is already running on http://localhost:5000
//   - playwright is installed in this dir (npm install was run here once)

import { chromium } from "playwright";

const CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const BASE = process.env.FX_BASE_URL || "http://localhost:5000";

async function withPage(fn) {
  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  try { return await fn(page); } finally { await browser.close(); }
}

async function shot(url, out = "/tmp/fx-shot.png") {
  return withPage(async (page) => {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.screenshot({ path: out, fullPage: true });
    const title = await page.title();
    return { title, url: page.url(), screenshot: out };
  });
}

async function smoke(outdir = "/tmp") {
  const summary = await fetch(`${BASE}/fx/api/dashboard/summary`).then((r) => r.json());
  const dash = await shot(`${BASE}/fx/`, `${outdir}/fx-dashboard.png`);
  const contracts = await withPage(async (page) => {
    await page.goto(`${BASE}/fx/`, { waitUntil: "networkidle" });
    await page.click('a:has-text("Contracts")');
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${outdir}/fx-contracts.png`, fullPage: true });
    return { url: page.url(), rows: await page.locator("table tbody tr").count() };
  });
  return { summary, dash, contracts };
}

async function click(url, selector, out = "/tmp/fx-click.png") {
  return withPage(async (page) => {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.click(selector);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: out, fullPage: true });
    return { url: page.url(), screenshot: out };
  });
}

const [cmd, ...args] = process.argv.slice(2);
const fns = { shot, smoke, click };
if (!fns[cmd]) {
  console.error("usage: driver.mjs <shot|smoke|click> ...");
  process.exit(2);
}
console.log(JSON.stringify(await fns[cmd](...args), null, 2));
