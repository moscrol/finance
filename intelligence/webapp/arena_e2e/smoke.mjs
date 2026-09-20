import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// Read-only local smoke: allocates demo assignments but casts no votes.
const baseURL = process.env.ARENA_SMOKE_URL ?? 'http://127.0.0.1:8816';
const output = new URL('../test-results/local-smoke/', import.meta.url);
await mkdir(fileURLToPath(output), { recursive: true });
const browser = await chromium.launch();
let failed = false;
try {
  for (const width of [1920, 1440, 1024, 768, 390, 360, 320]) {
    const page = await browser.newPage({ viewport: { width, height: 960 }, isMobile: width < 700, hasTouch: width < 700 });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(baseURL);
    await page.locator('.answer-grid').waitFor();
    await page.locator('.source-button img').evaluate(img => img.decode());
    const check = await page.evaluate(() => {
      const oversized = [...document.querySelectorAll('button,h1,h2,h3,.question-meta')].filter(node => {
        const r = node.getBoundingClientRect();
        return r.width > 0 && r.right > 0 && node.scrollWidth > node.clientWidth + 2;
      }).map(node => node.textContent);
      return {
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
        oversized,
        missingMedia: [...document.images].filter(img => !img.complete || !img.naturalWidth).length,
        textLength: document.querySelector('main').innerText.length,
        answerPanels: [...document.querySelectorAll('.answer-panel')].filter(node => node.getBoundingClientRect().height > 0).length,
      };
    });
    await page.screenshot({ path: fileURLToPath(new URL(`arena-${width}.png`, output)), fullPage: true });
    console.log(JSON.stringify({ width, ...check, errors }));
    failed ||= check.horizontalOverflow || check.oversized.length > 0 || check.missingMedia > 0 || check.textLength < 300 || errors.length > 0;
    await page.close();
  }
} finally { await browser.close(); }
if (failed) process.exitCode = 1;
