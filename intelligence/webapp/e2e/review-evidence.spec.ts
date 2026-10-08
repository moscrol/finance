import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const end = "2026-09-24";

test.beforeEach(async ({ page }, info) => {
  // Only unrelated market navigation is stubbed. Both archive readers run through the real API.
  await page.route("**/api/river/meta?*", route => route.fulfill({ json: {
    latest: end, trading_days: ["2026-09-21", "2026-09-22", "2026-09-23", end],
    default_entity: null, hot_entities: [], tracks: [], coverage: {},
  } }));
  await page.route("**/api/river/daily-overview?*", route => route.fulfill({ json: {
    start: "2026-09-21", end, latest_market_date: end,
    days: ["2026-09-21", "2026-09-22", "2026-09-23", end].map(date => ({ date })),
    calendar: ["2026-09-21", "2026-09-22", "2026-09-23", end], sectors: [],
  } }));
  await page.route("**/api/river/kline?*", route => route.fulfill({ json: { start: end, end, days: [] } }));
  await page.goto("/");
  if (info.project.name === "mobile") await page.getByRole("button", { name: "打开会话列表" }).click();
  await page.getByRole("navigation", { name: "工作台一级导航" }).getByRole("button", { name: "长河", exact: true }).click();
  await page.getByRole("button", { name: "连续复盘 · 时间线" }).click();
  await page.getByLabel("连续复盘截止日").fill(end);
  await page.getByLabel("连续复盘窗口").selectOption("5");
  await expect(page.getByText("归档可读 3 / 5 日")).toBeVisible();
});

test("readable layout and lossless agent packet after matrix switching and collapse", async ({ page, request }, info) => {
  const errors: string[] = [], writes: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", req => { if (req.method() !== "GET") writes.push(req.url()); });
  const response = await request.get(`/api/river/review-history?end=${end}&days=5&industry=${encodeURIComponent("电子")}`);
  expect(response.ok()).toBe(true);
  const evidence = await response.json();
  const available = evidence.points.at(-1);
  expect(available.engines.rows).toHaveLength(80);
  expect(available.engines.total_rows).toBe(81);
  expect(available.engines.truncated).toBe(true);
  for (const label of ["市场环境", "行业位置", "子板块表现", "个股发动机"]) {
    await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible();
  }
  const matrixControls = page.getByRole("group", { name: "连续矩阵类型" });
  await matrixControls.getByRole("button", { name: "涨停数量" }).click();
  await page.getByRole("button", { name: "展开 14 行" }).click();
  await page.getByRole("button", { name: "收起子板块" }).click();
  await matrixControls.getByRole("button", { name: "120日新高" }).click();
  await page.getByText("告诉 Agent：这些数据应该怎样联立解读", { exact: true }).click();
  await page.getByLabel("这次想判断什么").fill("合成问题：行业强化是否有支持与反例？");
  await page.getByLabel("先看什么，再结合什么").fill("先看市场，再核对同日子板块和发动机原表。");
  await page.getByLabel("哪些情况不能直接下结论").fill("缺档不能判断退潮，截断不能判断退出。");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Agent 联立证据包" }).click();
  const download = await downloadPromise;
  const downloaded = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(downloaded.evidence).toEqual(evidence);
  expect(downloaded.user_instructions.question).toContain("合成问题");
  expect(downloaded.context.industry).toBe("电子");
  expect(downloaded.evidence.points.at(-1).matrices.double_red.rows[0].value).toBe("🔥1.0%/15.0/800");
  expect(downloaded.evidence.points.at(-1).engines.rows[3][1]).toBe("合成股票04");
  await expect(page.getByText("归档可读 3 / 5 日")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("heading", { name: "你看图表，Agent 读同种数据。" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("reading-map.png") });
  await page.getByLabel("这次想判断什么").scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("reading-instructions.png") });
  expect(errors).toEqual([]);
  expect(writes).toEqual([]);
});

test("missing day stays pinned; same-day return, session draft recovery and clearing", async ({ page }) => {
  await page.getByRole("button", { name: "连续复盘选日 2026-09-23" }).click();
  await expect(page.getByText(/当日缺少结构化归档/)).toBeVisible();
  await expect(page.getByLabel("连续复盘截止日")).toHaveValue(end);
  await page.getByText("告诉 Agent：这些数据应该怎样联立解读", { exact: true }).click();
  await page.getByLabel("先看什么，再结合什么").fill("保留方法草稿，不写入日报。");
  await page.getByRole("button", { name: "打开当日完整复盘" }).click();
  await expect(page.getByLabel("复盘当前交易日")).toHaveValue("2026-09-23");
  await expect(page.getByRole("heading", { name: "这一天尚无结构化日报归档" })).toBeVisible();
  await page.getByRole("button", { name: "连续复盘 · 时间线" }).click();
  await page.getByText("告诉 Agent：这些数据应该怎样联立解读", { exact: true }).click();
  await expect(page.getByLabel("先看什么，再结合什么")).toHaveValue("保留方法草稿，不写入日报。");
  await page.getByRole("button", { name: "清空解读说明" }).click();
  await expect(page.getByLabel("先看什么，再结合什么")).toHaveValue("");
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("river-review-reading-instructions-v1")!))).toEqual({ question: "", method: "", cautions: "" });
});
