import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

/**
 * 放行条件 #1 的真链路：真浏览器表单 → 真 bindings API → 真刷新投影。
 *
 * 打的是 playwright.config 里第二台隔离服务（8794）：带一份 bootstrap 现造的真实市场库
 * （schema.sql 全表 + published 板块快照 + 两天行情）和一个预置会话 + 一条属于它的判断。
 * 与 research-evolution.spec.ts 那台「无库服务」互补：那台钉「读不到要如实说」，这台钉
 * 「读得到时，绑定链路真的走通」。
 */

const conversationId = readFileSync(
  new URL("../test-results/re06-users/re06-conversation-id.txt", import.meta.url),
  "utf-8",
).trim();

// 打第二台隔离服务（带真实市场库那台），不是全局的 8791。
test.use({ baseURL: process.env.RE06_E2E_URL ?? "http://127.0.0.1:8794" });

async function gotoSeededConversation(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "问答", exact: true }).click();
  // 用户态里只有预置会话 → 自动落在它上面（列表按 updated_at 排序）。
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
}

test.describe("研究进化 · 绑定真链路（带真实市场库的隔离服务）", () => {
  test("表单建绑定 → 服务端落账 → 投影刷新为已绑定", async ({ page, request }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "绑定链路只在 desktop 项目跑一份");
    test.setTimeout(90000);
    await gotoSeededConversation(page);

    // 面板打开前，服务端视角：这条判断是可跟踪对象、还没有绑定。
    const before = await request.get(
      `/api/conversations/${conversationId}/research-evolution?user=default`,
    );
    expect(before.status()).toBe(200);
    const beforeBody = await before.json();
    expect(beforeBody.inputs.bindings).toBe(0);
    expect(beforeBody.inputs.trackable_objects.length).toBeGreaterThan(0);

    const inspectorToggle = page.getByRole("button", { name: "打开研究检查器" });
    if (await inspectorToggle.isVisible().catch(() => false)) {
      await inspectorToggle.click();
    }
    await page.getByRole("tab", { name: "维护" }).click();

    // 未绑定记录 → 「从现在开始跟踪」→ 受控目录勾选 → 提交。
    await page.getByRole("button", { name: "从现在开始跟踪" }).first().click();
    await page.getByPlaceholder("例：制冷剂").fill("制冷剂");
    await page.locator(".re-bind-form input[type=date]").fill("2026-09-12");
    await page.getByRole("button", { name: "拉取可用证据" }).click();
    const versionCheckbox = page.getByRole("checkbox", {
      name: /fact_sector_daily:2026-09-12:BK0001/,
    });
    await expect(versionCheckbox).toBeVisible({ timeout: 15000 });
    await versionCheckbox.check();
    await page.getByRole("button", { name: "开始跟踪" }).click();

    // 真刷新后的投影：绑定数 +1，未绑定清单清空（这条判断已进入跟踪）。
    await expect(page.getByText("还没有依据的旧记录")).toBeHidden({ timeout: 15000 });
    const after = await request.get(
      `/api/conversations/${conversationId}/research-evolution?user=default`,
    );
    const afterBody = await after.json();
    expect(afterBody.inputs.bindings).toBe(1);
    const trackable = afterBody.inputs.trackable_objects as Array<Record<string, unknown>>;
    expect(trackable.every((item) => item.bound === true)).toBeTruthy();
  });
});
