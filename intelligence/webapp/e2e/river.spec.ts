import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { TRACKS } from "../src/river/types";

const dates = ["2026-01-06", "2026-09-23", "2026-09-24"];
const latest = dates[2];
const archiveOnlyDate = "2026-08-04";
const entity = { id: "S1", name: "测试板块", pct_chg: 1, amount: 500 };

// Synthetic reader fixtures only. The real App, navigation, request lifecycle,
// browser storage and responsive layout run through the existing test server.
async function marketFixtures(page: Page) {
  await page.route("**/api/limitup/calendar?*", async route => {
    const end = new URL(route.request().url()).searchParams.get("end") ?? latest;
    const days = dates.filter(day => day <= end).map(trade_date => ({
      trade_date, ladder: { "2": 1, "5": 1 }, promotion_rate: {}, promotion_estimated: [],
      total: 2, high_boards: 1, max_boards: 5, market: null, top_themes: [],
      leader: { name: "测试甲股", height: 5, ts_code: "000001.SZ" },
      details: [
        { name: "测试甲股", ts_code: "000001.SZ", boards: 5, theme: "测试板块", pct: 10, first_limit_date: "2026-01-02" },
        { name: "测试乙股", ts_code: "000002.SZ", boards: 2, theme: null, pct: 10, first_limit_date: "2026-01-05" },
      ],
    }));
    await route.fulfill({ json: { start: days[0].trade_date, end: days.at(-1)!.trade_date, days,
      stats: { trading_days: days.length, avg_total: 2, avg_max_boards: 5, max_boards: 5, max_boards_date: end } } });
  });
  await page.route("**/api/river/**", async route => {
    const url = new URL(route.request().url());
    const end = url.searchParams.get("end") ?? latest;
    const day = url.searchParams.get("as_of") ?? latest;
    const visible = dates.filter(date => date <= end);
    const replies: Record<string, unknown> = {
      meta: { latest, trading_days: dates, default_entity: entity, hot_entities: [entity], tracks: [],
        coverage: Object.fromEntries(TRACKS.map(track => [track, { table: "fixture", min: dates[0], max: latest, rows: 3, exists: true }])),
        cohort_options: { market_stage: [], volume_state: [], concentration_state: [] } },
      "daily-overview": { start: visible[0], end: visible.at(-1), days: visible.map(date => ({ date })), calendar: dates, sectors: [], latest_market_date: latest },
      "daily-review": { schema_version: 1, trade_date: day, available_dates: [latest, archiveOnlyDate],
        status: [latest, archiveOnlyDate].includes(day) ? "available" : "missing", message: "所选日无归档；未替换为其他日期。",
        report: [latest, archiveOnlyDate].includes(day) ? { facts: { market_stage: "合成测试阶段", volume_ratio: 87.5, total_amount: 15000 },
          industries: [], matrices: { double_red: [], stock_highs: [], limit_up: [] }, engines: [], sections: [], diagnostics: [], warnings: [], core_board: [] } : null,
        provenance: { source_path: "fixture/daily-review.json", sha256: "fixture-sha", generated_at: "2026-09-24T20:00:00+08:00", note: "合成测试归档" } },
      kline: { start: visible[0], end: visible.at(-1), days: [], source: "fixture", strength_source: "fixture" },
      "opinion-attention": { collection_status: "not_connected", events: [], gaps: [], visible_observations: 0, event_count: 0 },
      timeline: { entity: { ...entity, codes_seen: [entity.id], alias_applied: false }, start: visible[0], end: visible.at(-1), trading_days: visible.length,
        judgment_source: { path: "fixture", exists: false }, days: visible.map(date => ({ date, market: null, theme: null, opinion: null, capital: null, stock: null, judgment: null })) },
      scan: { as_of: day, mode: "all", count: 0, rows: [] },
      entities: { as_of: day, items: [entity] },
    };
    const key = url.pathname.split("/").at(-1)!;
    expect(Object.hasOwn(replies, key), `unhandled fixture endpoint: ${key}`).toBeTruthy();
    await route.fulfill({ json: replies[key] });
  });
}

async function navigate(page: Page, testInfo: TestInfo, name: string) {
  if (testInfo.project.name === "mobile") await page.getByRole("button", { name: "打开会话列表" }).click();
  await page.getByRole("navigation", { name: "工作台一级导航" }).getByRole("button", { name, exact: true }).click();
}

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test.beforeEach(async ({ page }) => {
  await marketFixtures(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "数据缺失" })).toBeVisible();
});

test("original ladder, daily archive and six tracks keep the same historical date", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await navigate(page, testInfo, "连板");
  await expect(page.getByLabel("连板当前交易日")).toHaveValue(latest);
  await page.getByRole("gridcell", { name: `${latest} 5板 1家` }).click();
  await page.getByRole("button", { name: "查看测试甲股连板详情" }).click();
  await expect(page.getByRole("region", { name: "连板个股详情" })).toContainText("000001.SZ");
  await page.getByLabel("连板历史截止日").fill(dates[0]);
  await expect(page.getByLabel("连板当前交易日")).toHaveValue(dates[0]);
  await page.getByRole("button", { name: "同日复盘 ↗" }).click();
  await expect(page.getByLabel("复盘当前交易日")).toHaveValue(dates[0]);
  await expect(page.getByRole("heading", { name: "这一天尚无结构化日报归档" })).toBeVisible();
  await page.getByRole("button", { name: "板块六轨", exact: true }).click();
  await expect(page.getByLabel("横扫交易日")).toHaveValue(dates[0]);
  await page.getByRole("button", { name: "查看该板块同日公开消息 ↗" }).click();
  await expect(page.getByLabel("公开消息交易日")).toHaveValue(dates[0]);
  await expect(page.getByRole("heading", { name: "数据接口已就绪，等待真实信源。" })).toBeVisible();
  await page.getByRole("button", { name: "每日复盘", exact: true }).click();
  await page.getByRole("button", { name: "最新", exact: true }).click();
  await expect(page.getByLabel("复盘当前交易日")).toHaveValue(latest);
  await expect(page.getByText(`${latest} 日报`, { exact: true })).toBeVisible();
  await noOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("daily.png") });
  await page.getByRole("button", { name: "同日连板 ↗" }).click();
  await expect(page.getByLabel("连板当前交易日")).toHaveValue(latest);
  expect(errors).toEqual([]);
});

test("observations persist frozen conditions and append a review without a model request", async ({ page }, testInfo) => {
  const modelWrites: string[] = [];
  page.on("request", request => { if (request.method() === "POST" && /\/messages|\/runs|\/ask/.test(request.url())) modelWrites.push(request.url()); });
  await navigate(page, testInfo, "长河");
  await page.getByRole("button", { name: "观察验证", exact: true }).click();
  await expect(page.getByLabel("观察数据日")).toHaveValue(latest);
  await expect(page.getByText("87.5%", { exact: true })).toBeVisible();
  await page.getByLabel("待验证假设").fill("测试假设：回流是否扩散");
  await page.getByLabel("确认条件", { exact: true }).fill("后续续量并扩散");
  await page.getByLabel("推翻条件", { exact: true }).fill("续量失败即降级");
  await page.getByLabel("拟复查日期").fill("2026-09-28");
  for (const select of await page.getByRole("combobox", { name: /人工判定/ }).all()) await select.selectOption("missing");
  await page.getByRole("button", { name: "冻结这次观察" }).click();
  await expect(page.getByText(/原始条件已冻结到本浏览器/)).toBeVisible();
  await page.reload();
  await navigate(page, testInfo, "长河");
  await page.getByRole("button", { name: "观察验证", exact: true }).click();
  const record = page.locator(".obs-record");
  await expect(record).toContainText("续量失败即降级");
  await record.getByRole("textbox", { name: /复查证据/ }).fill("09-28 缺少后续量能证据，仍待核验");
  await record.getByRole("button", { name: "追加：信息不足" }).click();
  await expect(record).toContainText("人工复查：信息不足");
  await record.getByRole("button", { name: "生成Agent核验问题" }).click();
  await expect(page.getByLabel("Agent核验问题")).toHaveValue(/请主动找反证/);
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("foresight.observation-workbench.v1")!));
  expect(stored.records[0].strict_point_in_time).toBe(false);
  expect(stored.records[0].evidence.archive_sha256).toBe("fixture-sha");
  expect(stored.records[0].reviews).toHaveLength(1);
  const downloadEvent = page.waitForEvent("download");
  await record.getByRole("button", { name: "导出记录" }).click();
  const download = await downloadEvent;
  const exported = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(exported).toEqual(stored.records[0]);
  expect(modelWrites).toEqual([]);
  await noOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("observation.png") });
});

test("an explicitly selected archive remains readable when its market day is missing", async ({ page }, testInfo) => {
  await navigate(page, testInfo, "长河");
  await page.getByLabel("复盘当前交易日").selectOption(dates[0]);
  await expect(page.getByRole("heading", { name: "这一天尚无结构化日报归档" })).toBeVisible();
  await page.getByRole("button", { name: archiveOnlyDate, exact: true }).click();
  await expect(page.getByLabel("复盘当前交易日")).toHaveValue(archiveOnlyDate);
  await expect(page.getByText(`${archiveOnlyDate} 日报`, { exact: true })).toBeVisible();
  await expect(page.getByText(/所选日报日期暂无行情/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "这一天尚无结构化日报归档" })).toHaveCount(0);
  await noOverflow(page);
});

test("an explicit archive loads when the independent market API fails", async ({ page }, testInfo) => {
  await navigate(page, testInfo, "连板");
  await expect(page.getByLabel("连板当前交易日")).toHaveValue(latest);
  await page.route("**/api/river/daily-overview?*", route => route.fulfill({ status: 503, json: { detail: "synthetic market unavailable" } }));
  await page.getByRole("button", { name: "同日复盘 ↗" }).click();
  await expect(page.getByRole("alert")).toContainText("503");
  await expect(page.getByLabel("复盘当前交易日")).toHaveValue(latest);
  await expect(page.getByRole("button", { name: "展开完整日报 · 0 章节" })).toBeVisible();
});

test("two tabs serialize simultaneous freezes and reviews without replacing frozen conditions", async ({ page, context }, testInfo) => {
  const other = await context.newPage();
  await marketFixtures(other);
  await other.goto("/");
  for (const [index, tab] of [page, other].entries()) {
    await navigate(tab, testInfo, "长河");
    await tab.getByRole("button", { name: "观察验证", exact: true }).click();
    await expect(tab.getByText("87.5%", { exact: true })).toBeVisible();
    await tab.getByLabel("待验证假设").fill(`标签页 ${index + 1} 的原始假设`);
    await tab.getByLabel("确认条件", { exact: true }).fill(`标签页 ${index + 1} 的确认条件`);
    await tab.getByLabel("推翻条件", { exact: true }).fill(`标签页 ${index + 1} 的推翻条件`);
    await tab.getByLabel("拟复查日期").fill("2026-09-28");
    for (const select of await tab.getByRole("combobox", { name: /人工判定/ }).all()) await select.selectOption("missing");
  }
  const holdLock = () => page.evaluate(() => new Promise<void>(held => {
    void navigator.locks.request("foresight.observation-workbench.v1", () => new Promise<void>(release => {
      (window as Window & { releaseObservationLock?: () => void }).releaseObservationLock = release;
      held();
    }));
  }));
  const releaseLock = () => page.evaluate(() => (window as Window & { releaseObservationLock?: () => void }).releaseObservationLock?.());
  const stored = () => page.evaluate(() => JSON.parse(localStorage.getItem("foresight.observation-workbench.v1")!));
  await holdLock();
  try {
    await Promise.all([page, other].map(tab => tab.getByRole("button", { name: "冻结这次观察" }).click()));
    expect((await stored()).records).toHaveLength(0);
    await expect.poll(() => page.evaluate(async () => (await navigator.locks.query()).pending?.filter(lock => lock.name === "foresight.observation-workbench.v1").length)).toBe(2);
  } finally { await releaseLock(); }
  for (const tab of [page, other]) await expect(tab.getByText(/原始条件已冻结到本浏览器/)).toBeVisible();
  await expect.poll(async () => (await stored()).records.length).toBe(2);
  const frozen = (await stored()).records;
  expect(frozen.map((record: { form: { hypothesis: string } }) => record.form.hypothesis).sort()).toEqual(["标签页 1 的原始假设", "标签页 2 的原始假设"]);
  for (const [index, tab] of [page, other].entries()) {
    await expect(tab.locator(".obs-record")).toHaveCount(2);
    await tab.getByLabel(`复查证据 ${frozen[0].id}`).fill(`标签页 ${index + 1} 的追加证据`);
  }
  await holdLock();
  try {
    await Promise.all([page, other].map(tab => tab.locator(".obs-record").filter({ has: tab.getByLabel(`复查证据 ${frozen[0].id}`) }).getByRole("button", { name: "追加：信息不足" }).click()));
    expect((await stored()).records[0].reviews).toHaveLength(0);
    await expect.poll(() => page.evaluate(async () => (await navigator.locks.query()).pending?.filter(lock => lock.name === "foresight.observation-workbench.v1").length)).toBe(2);
  } finally { await releaseLock(); }
  await expect.poll(async () => (await stored()).records[0].reviews.length).toBe(2);
  const final = (await stored()).records;
  expect(final[0].reviews.map((review: { note: string }) => review.note).sort()).toEqual(["标签页 1 的追加证据", "标签页 2 的追加证据"]);
  expect(final.map((record: { reviews: unknown[] }) => ({ ...record, reviews: [] }))).toEqual(frozen);
  await other.close();
});

test("theme remains an optional persistent choice and the conversation entry stays usable", async ({ page }, testInfo) => {
  await expect(page.locator("html")).toHaveAttribute("data-theme", "paper");
  await page.getByRole("button", { name: "切换为科技主题" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "tech");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "tech");
  await navigate(page, testInfo, "连板");
  await expect(page.getByLabel("连板当前交易日")).toHaveValue(latest);
  await expect(page.locator(".chat-title strong")).toContainText("连板梯队与晋级");
  const title = await page.locator(".chat-title strong").boundingBox();
  expect(title!.height).toBeLessThan(32);
  expect(title!.width).toBeGreaterThan(70);
  const selectedWindow = page.getByRole("tablist", { name: "窗口宽度" }).getByRole("button", { name: "60 日" });
  await expect(selectedWindow).toHaveCSS("background-color", "rgb(43, 38, 32)");
  await expect(selectedWindow).toHaveCSS("color", "rgb(255, 255, 255)");
  await noOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("theme.png") });
  await page.getByRole("button", { name: "切换为暖纸主题" }).click();
  await navigate(page, testInfo, "问答");
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
});
