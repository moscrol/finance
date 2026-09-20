import { expect, test, type Page } from "@playwright/test";

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "打开导航", exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("navigation", { name: "主导航", exact: true }).getByRole("button", { name, exact: true }).click();
}

async function voteButton(page: Page, name: string) {
  return page.locator(".vote-buttons").getByRole("button", { name, exact: true });
}

test("anonymous vote, invitation, receipt, and honest leaderboard", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "研究盲评", exact: true })).toBeVisible();
  await expect(page.locator(".answer-grid")).toBeVisible();
  await expect(page.locator(".answer-grid")).not.toContainText("E2E Fixture");
  await expect(page.locator(".source-button img")).toHaveJSProperty("naturalWidth", 320);
  await page.screenshot({ path: testInfo.outputPath("anonymous.png"), fullPage: true });
  const code = await (await page.request.post("/__fixture__/invite")).json();
  await page.locator(".reviewer-button").click();
  await page.getByLabel("邀请码", { exact: true }).fill(code.code);
  await page.getByRole("button", { name: "确认加入", exact: true }).click();
  await expect(page.locator(".reviewer-button")).toContainText("R-");
  const before = await (await page.request.get("/api/arena/leaderboard")).json();
  await (await voteButton(page, "A 更好")).click();
  await expect(page.locator(".vote-receipt")).toContainText("已计入正式统计");
  await expect(page.locator(".answer-grid")).toContainText("E2E Fixture");
  const after = await (await page.request.get("/api/arena/leaderboard")).json();
  expect(after.formal_votes).toBe(before.formal_votes + 1);
  await page.screenshot({ path: testInfo.outputPath("receipt.png"), fullPage: true });
  await navigate(page, "胜率观察");
  await expect(page.locator(".leaderboard-table")).toContainText("E2E Fixture");
  await expect(page.locator(".leaderboard-table")).toContainText("样本积累中");
  await page.getByRole("button", { name: "两两对战", exact: true }).click();
  await expect(page.locator(".leaderboard-table")).toContainText("vs E2E Fixture");
  await navigate(page, "我的评测");
  await expect(page.locator(".history-list")).toContainText("计入正式统计");
  await page.locator(".history-list button").first().click();
  await expect(page.locator(".vote-receipt")).toContainText("已计入正式统计");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});

test("guest demo votes never enter formal metrics; mobile answer tabs work", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator(".answer-grid")).toBeVisible();
  await page.getByRole("button", { name: "体验场", exact: true }).click();
  await expect(page.locator(".provenance-band")).toContainText("人工编写");
  if (testInfo.project.name.includes("mobile")) {
    await page.getByRole("button", { name: "回答 B", exact: true }).click();
    await expect(page.getByRole("article", { name: "回答 B" })).toBeVisible();
    await expect(page.getByRole("article", { name: "回答 A" })).not.toBeVisible();
  }
  await page.locator(".source-button").click();
  await expect(page.getByRole("dialog")).toContainText("虚构");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const before = await (await page.request.get("/api/arena/leaderboard")).json();
  await (await voteButton(page, "同样好")).click();
  await expect(page.locator(".vote-receipt")).toContainText("体验投票已记录");
  const after = await (await page.request.get("/api/arena/leaderboard")).json();
  expect(after.formal_votes).toBe(before.formal_votes);
  await page.getByRole("button", { name: "下一场", exact: true }).click();
  await expect(page.locator(".vote-buttons")).toBeVisible();
  await page.getByRole("button", { name: "报告问题", exact: true }).click();
  await page.getByLabel("补充说明").fill("本测试仅确认问题报告可以真实保存。");
  await page.getByRole("button", { name: "提交复核", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("问题已提交");
  await page.screenshot({ path: testInfo.outputPath("demo.png"), fullPage: true });
});

test("question participation is persisted and explicitly queued", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator(".answer-grid")).toBeVisible();
  await page.getByRole("button", { name: "提交题目", exact: true }).click();
  await page.getByLabel("研究问题").fill("请比较两家企业的利润与现金流，哪些证据能够判断盈利质量？");
  await page.getByRole("checkbox", { name: "题目不含个人、账户或机构保密信息；同意审核后用于公开匿名评测。" }).check();
  await page.getByRole("dialog").getByRole("button", { name: "提交题目", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("运营审核队列");
  await navigate(page, "我的评测");
  await expect(page.locator(".question-list")).toContainText("盈利质量");
  await expect(page.locator(".question-list")).toContainText("待运营审核");
  await page.reload();
  await navigate(page, "我的评测");
  await expect(page.locator(".question-list")).toContainText("盈利质量");
  await page.screenshot({ path: testInfo.outputPath("history.png"), fullPage: true });
});

test("strategy page has no invented returns and no horizontal overflow", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator(".answer-grid")).toBeVisible();
  await navigate(page, "策略前向");
  await expect(page.getByRole("heading", { name: "尚无已登记的前向策略", exact: true })).toBeVisible();
  await expect(page.locator("main")).toContainText("成交核算与行情结算尚未接入");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("strategy.png"), fullPage: true });
});
