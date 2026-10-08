import { expect, test } from "@playwright/test";

test("calendar reads real API data, preserves gaps, refreshes and links the selected day", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  if (info.project.name === "mobile") await page.getByRole("button", { name: "打开会话列表" }).click();
  await page.getByRole("button", { name: "连板日历", exact: true }).click();
  await page.getByLabel("选择月份").fill("2026-09");
  const first = page.getByRole("article", { name: "2026-09-01" });
  await expect(first.getByText("断 6板 合成高标甲")).toBeVisible();
  await expect(first.getByText("断 6板 合成高标甲 · 未核")).toHaveCount(0);
  // 离开名单但当日无行情 = 停牌/无成交，只能待核，不能算断板。
  await expect(first.getByRole("region", { name: "断板待核" }).getByText("5板 合成停牌戊 · 停牌/无成交")).toBeVisible();
  await expect(first.getByText(/断 5板 合成停牌戊/)).toHaveCount(0);
  await expect(first.getByText("6-000002 合成高标乙")).toHaveClass(/--x5/);
  await first.getByRole("button", { name: /展开其余/ }).click();
  await expect(first.getByText("3-600009 合成样本9")).toBeVisible();
  await first.getByRole("button", { name: "收起" }).click();
  await expect(first.getByText("3-600009 合成样本9")).toHaveCount(0);
  const gap = page.getByRole("article", { name: "2026-09-24" });
  await expect(gap.getByText("断板未判定：当日或前一交易日名单缺失")).toBeAttached();
  await expect(gap.getByText(/断 5板 合成缺口丙/)).toHaveCount(0);
  await page.getByRole("button", { name: "≥2板", exact: true }).click();
  await expect(gap.getByText("2-000004 合成低板丁")).toBeAttached();
  const refreshed = page.waitForResponse(r => r.url().includes("board-calendar?") && r.status() === 200);
  await page.getByRole("button", { name: "刷新日历" }).click();
  await refreshed;
  await expect(first).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const scroll = page.getByRole("region", { name: "可横向滚动的连板日历" });
  expect(await scroll.evaluate(el => {
    const grid = el.firstElementChild as HTMLElement;
    return grid.scrollWidth <= grid.clientWidth + 2;
  })).toBe(true); // No inner clipping: overflow belongs to the outer scroller.
  await page.screenshot({ path: info.outputPath("calendar.png"), fullPage: true });
  await first.getByRole("button", { name: "查看 2026-09-01 连板梯队" }).click();
  await expect(page.getByText("合成高标乙", { exact: true }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("network failure is explicit and retry restores the same month", async ({ page }, info) => {
  await page.goto("/");
  if (info.project.name === "mobile") await page.getByRole("button", { name: "打开会话列表" }).click();
  await page.getByRole("button", { name: "连板日历", exact: true }).click();
  await page.getByLabel("选择月份").fill("2026-09");
  await expect(page.getByRole("article", { name: "2026-09-01" })).toBeVisible();
  await page.route("**/api/workbench/board-calendar?*", route => route.abort());
  await page.getByRole("button", { name: "刷新日历" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.unroute("**/api/workbench/board-calendar?*");
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByText("断 6板 合成高标甲")).toBeVisible();
  await expect(page.getByLabel("选择月份")).toHaveValue("2026-09");
});
