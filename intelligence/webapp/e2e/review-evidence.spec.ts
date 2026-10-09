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
  const guide = page.locator("details").filter({ has: page.locator("summary", { hasText: /^数据读法与 Agent 交接$/ }) });
  await expect(guide).not.toHaveAttribute("open");
  const metrics = page.getByRole("region", { name: "当前日市场读数", exact: true });
  await expect(metrics).toBeVisible();
  expect(await metrics.evaluate(node => !!(node.compareDocumentPosition(document.querySelector(".rh-reading")!) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true);
  await guide.locator(":scope > summary").click();
});

test("market readings have a complete first card in the initial viewport", async ({ page }, info) => {
  await page.getByText("数据读法与 Agent 交接", { exact: true }).click();
  await page.evaluate(() => {
    document.querySelectorAll("*").forEach(node => {
      if (node instanceof HTMLElement && node.scrollTop) node.scrollTop = 0;
    });
    window.scrollTo(0, 0);
  });
  const first = page.getByRole("region", { name: "当前日市场读数", exact: true }).locator("article").first();
  const box = await first.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("initial-market-readings.png") });
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
  await page.getByText("数据读法与 Agent 交接", { exact: true }).click();
  await page.getByText("告诉 Agent：这些数据应该怎样联立解读", { exact: true }).click();
  await expect(page.getByLabel("先看什么，再结合什么")).toHaveValue("保留方法草稿，不写入日报。");
  await page.getByRole("button", { name: "清空解读说明" }).click();
  await expect(page.getByLabel("先看什么，再结合什么")).toHaveValue("");
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("river-review-reading-instructions-v1")!))).toEqual({ question: "", method: "", cautions: "" });
});

test("hand-off opens chat with coordinates only and the server refuses when the Agent cannot receive it", async ({ page, request }) => {
  const evidence = await (await request.get(`/api/river/review-history?end=${end}&days=5&industry=${encodeURIComponent("电子")}`)).json();
  expect(evidence.window_fingerprint).toMatch(/^[0-9a-f]{64}$/);
  await page.getByText("告诉 Agent：这些数据应该怎样联立解读", { exact: true }).click();
  await page.getByLabel("先看什么，再结合什么").fill("先看市场，再核对同日子板块。");
  await page.getByRole("button", { name: "带着证据去问答" }).click();
  const composer = page.getByLabel("输入研究问题");
  await expect(composer).toHaveValue(/^请复盘 2026-09-18 至 2026-09-24 的电子，以每日复盘归档为准/);
  await expect(composer).toHaveValue(/我的解读方法（研究指导，不是市场事实）：先看市场，再核对同日子板块。/);
  await expect(page.getByRole("status", { name: "附带复盘证据" })).toBeVisible();
  const posted = page.waitForRequest(req => req.method() === "POST" && /\/messages(\?|$)/.test(req.url()));
  await page.getByRole("button", { name: "发送研究问题" }).click();
  const body = (await posted).postDataJSON();
  expect(body.review_evidence).toEqual({ schema: "review-evidence-ref/v1", end, days: 5, industry: "电子", fingerprint: evidence.window_fingerprint, selected_date: end });
  expect(JSON.stringify(body)).not.toContain("合成股票");
  // The fixture server has no model / continuous engine: refuse loudly, keep the attachment.
  await expect(page.getByRole("alert")).toContainText(/复盘证据无法送达给 Agent/);
  await expect(page.getByRole("status", { name: "附带复盘证据" })).toBeVisible();
});
