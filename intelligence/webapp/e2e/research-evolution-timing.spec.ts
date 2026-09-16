import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

/** 真浏览器/真事件 API/隔离用户态，不调金融模型，不拿合成计时当真人效果。 */
test("I14：隐藏暂停应用内活跃，原始区间保留完整端到端时间", async ({ page, request }, testInfo) => {
  const created = await request.post("/api/conversations", { data: { title: "I14计时", user: "default" } });
  expect(created.ok()).toBe(true);
  await page.goto("/");
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "打开会话列表" }).click();
  }
  await page.getByRole("button", { name: "问答", exact: true }).click();
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
  const toggle = page.getByRole("button", { name: "打开研究检查器" });
  if (await toggle.isVisible()) await toggle.click();
  const start = page.getByRole("button", { name: "同意并开始本次计时" });
  await expect(start).toBeVisible();
  const requests: Array<{ url: string; body: { events: Array<Record<string, unknown>> }; response: unknown }> = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/research-evolution/events")) return;
    requests.push({ url: response.url(), body: response.request().postDataJSON(), response: await response.json() });
  });
  const consent = page.waitForResponse((r) => r.url().includes("/research-evolution/events"));
  await start.click();
  expect((await consent).ok()).toBe(true);
  const stop = page.getByRole("button", { name: "停止使用计时" });
  await expect(stop).toBeVisible();
  await page.waitForTimeout(150);
  // 自动化 Chromium 的后台窗口不保证触发 OS 可见性变化；显式投递浏览器
  // visibilitychange，测试真实 DOM 监听链，不冒称真人切后台实测。
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(300);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(150);
  await stop.click();
  await expect(start).toBeEnabled();
  await expect.poll(() => requests.flatMap((r) => r.body.events).filter((e) => e.event_type === "time_interval").length).toBe(3);
  const first = requests[0];
  const conversationId = new URL(first.url).pathname.split("/")[3];
  const ledger = resolve("test-results/workbench-users/default/research_evolution/product_value_events.jsonl");
  const stored = readFileSync(ledger, "utf8").trim().split("\n").map((line) => JSON.parse(line));
  const ids = requests.flatMap((r) => r.body.events).map((e) => e.event_id);
  const rows = stored.filter((r) => ids.includes(r.event_id));
  const consents = rows.filter((r) => r.event_type === "consent_changed");
  expect(consents.map((r) => r.payload.action)).toEqual(["grant", "withdraw"]);
  expect(rows.every((r) => r.pilot_id === `workbench:${conversationId}` && r.task_id === null)).toBe(true);
  await expect(page.getByRole("alert")).toHaveCount(0);
  const intervals = rows.filter((r) => r.event_type === "time_interval");
  expect(intervals).toHaveLength(3);
  expect(intervals.map((r) => r.payload.activity)).toEqual(["user_active", "pause", "user_active"]);
  expect(intervals[1].payload.pause_reason).toBe("tab_hidden");
  expect(intervals[1].payload.visibility).toBe("hidden");
  expect(intervals.every((r) => r.source_channel === "frontend" && r.owner_user_id === "default")).toBe(true);
  const duration = (r: typeof intervals[number]) => Date.parse(r.payload.end) - Date.parse(r.payload.start);
  const total = Date.parse(intervals[2].payload.end) - Date.parse(intervals[0].payload.start);
  const active = duration(intervals[0]) + duration(intervals[2]);
  expect(total).toBe(active + duration(intervals[1]));
  expect(total).toBeGreaterThan(active);
  expect(intervals[0].payload.end).toBe(intervals[1].payload.start);
  expect(intervals[1].payload.end).toBe(intervals[2].payload.start);
  expect(Date.parse(consents[1].payload.effective_at)).toBeGreaterThan(Date.parse(intervals[2].event_at));
  const countAfterStop = requests.length;
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await page.waitForTimeout(100);
  expect(requests).toHaveLength(countAfterStop);
  await expect(page.getByLabel("输入研究问题")).toBeEnabled();
  await testInfo.attach("I14-events", { body: JSON.stringify({ conversationId, rows, total, active, synthetic_visibility: true, paired_measurement: false }), contentType: "application/json" });
});
