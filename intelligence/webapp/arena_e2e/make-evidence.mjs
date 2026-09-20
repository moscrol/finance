import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// A local bitmap of the fictional evidence cover, not an external market image.
const output = new URL('../arena-public/arena-evidence.png', import.meta.url);
await mkdir(fileURLToPath(new URL('../arena-public/', import.meta.url)), { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 320, height: 420 }, deviceScaleFactor: 1 });
  await page.setContent(`<html lang="zh-CN"><body style="margin:0;background:white;color:#456151;font-family:Arial,'PingFang SC',sans-serif;padding:30px;box-sizing:border-box;height:420px;border:1px solid #e1e8e2">
  <div style="border-top:5px solid #468266;padding-top:24px;font-size:12px">FINARENA / RESEARCH MATERIAL</div>
  <h1 style="font-size:27px;margin:18px 0 7px">共同参考材料</h1><div style="font-size:12px;color:#9ba9a0">虚构教学案例 · 非真实财务数据</div>
  <div style="height:1px;background:#dfe8e2;margin:27px 0"></div>
  <table style="width:100%;border-collapse:collapse;font-size:12px;line-height:3;text-align:left"><tr style="color:#7e9888"><th>财务指标</th><th>2024</th><th>2025</th></tr><tr><td>营业收入</td><td>80</td><td>100</td></tr><tr><td>归母净利润</td><td>5</td><td>7</td></tr><tr><td>经营现金流</td><td>10</td><td>6.5</td></tr></table>
  <div style="margin-top:21px;color:#a5b2a9;font-size:10px">金额单位：亿元 / 人工编写样例</div></body></html>`);
  await page.screenshot({ path: fileURLToPath(output) });
} finally { await browser.close(); }
