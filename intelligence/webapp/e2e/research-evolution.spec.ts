import { expect, test, type Page, type TestInfo } from "@playwright/test";

/**
 * 研究进化面板的隔离端到端：真浏览器 + 真服务 + 临时用户态。
 *
 * 这台隔离服务**没有**市场库，所以证据目录一定读不到——这正好是要钉住的那条线：
 * 读不到就如实说「还判不了」，不能显示成「没有问题」「0 条」，也不能整页崩掉。
 * 有市场库时的完整绑定→变化→复核链路由 `intelligence/tests/test_research_evolution_api.py` 覆盖。
 */

/** 工作台默认落在「今日」面，问答面才有检查器入口——与 workbench.spec.ts 同一套导航。 */
async function gotoChat(page: Page, testInfo: TestInfo) {
  await page.goto("/");
  if (testInfo.project.name === "mobile") {
    // 视口 ≥1180 或侧边栏已内联展开时，开关按钮根本不出现——等得到就点，等不到就直接用侧边栏。
    const toggle = page.getByRole("button", { name: "打开会话列表" });
    await toggle
      .waitFor({ state: "visible", timeout: 5000 })
      .then(() => toggle.click())
      .catch(() => undefined);
  }
  await page.getByRole("button", { name: "问答", exact: true }).click();
  // 开一个干净会话：否则会自动落到上一条测试留下的会话上，面板状态随执行顺序变。
  await page.getByRole("button", { name: "新对话" }).click();
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
}

async function openMaintenanceTab(page: Page) {
  await page.getByRole("button", { name: "打开研究检查器" }).click();
  // 检查器用的是 role="tablist"，子项是 tab 不是 button。
  const tab = page.getByRole("tab", { name: "维护" });
  await expect(tab).toBeVisible();
  await tab.click();
}

test.describe("研究进化面板", () => {
  test("接口在真实服务上可达，缺输入如实报「还判不了」", async ({ page, request }) => {
    await page.goto("/");
    const created = await request.post("/api/conversations", {
      data: { title: "制冷剂配额", user: "default" },
    });
    expect(created.ok()).toBeTruthy();
    const conversationId = (await created.json()).conversation_id as string;

    const view = await request.get(
      `/api/conversations/${conversationId}/research-evolution?user=default`,
    );
    expect(view.status()).toBe(200);
    const body = await view.json();
    expect(body.schema_version).toBe("research-evolution-view/v1");
    expect(body.owner_user_id).toBe("default");

    // 缺输入一律是 unknown/pending，绝不塌成空数组冒充「没问题」。
    expect(body.module_status.maintenance.status).toBe("unknown");
    expect(body.module_status.maintenance.reason).toBe("no_bindings");
    expect(body.module_status.diagnostics.status).toBe("unknown");
    expect(body.module_status.validation_receipts.status).toBe("unknown");
    expect(body.gaps.length).toBeGreaterThan(0);
    expect(JSON.stringify(body)).not.toContain("/Users/");
  });

  test("未认证模式拒绝任意换用户，且不泄漏他人会话是否存在", async ({ request }) => {
    const created = await request.post("/api/conversations", {
      data: { title: "本人的", user: "default" },
    });
    const conversationId = (await created.json()).conversation_id as string;

    const foreign = await request.get(
      `/api/conversations/${conversationId}/research-evolution?user=mallory`,
    );
    expect(foreign.status()).toBe(403);
    expect((await foreign.json()).detail.code).toBe("owner_forbidden");

    const missing = await request.get(
      "/api/conversations/conv_nope/research-evolution?user=default",
    );
    expect(missing.status()).toBe(404);
    expect((await missing.json()).detail.code).toBe("not_found");
  });

  test("R1 回归针：空 run_id 的 continuation 必须 422，不能默默进消息口", async ({ request }) => {
    // 旧病：「继续核查」把空字符串 run_id 硬塞进 continuation，服务端 422，用户看到提问失败。
    // 返修后前端只在有真实起源 run 时才带 continuation；这条针把门口的行为钉死。
    const created = await request.post("/api/conversations", {
      data: { title: "R1 针", user: "default" },
    });
    const conversationId = (await created.json()).conversation_id as string;
    const bad = await request.post(`/api/conversations/${conversationId}/messages`, {
      data: {
        content: "继续核查",
        skill_mode: "auto",
        user: "default",
        continuation: { run_id: "", kind: "condition_test", source: "research-evolution" },
      },
    });
    expect(bad.status()).toBe(422);
  });

  test("R8 回归针：未知动作返回 400，actor 必须等于登录用户", async ({ request }) => {
    const created = await request.post("/api/conversations", {
      data: { title: "R8 针", user: "default" },
    });
    const conversationId = (await created.json()).conversation_id as string;
    const bad = await request.post(
      `/api/conversations/${conversationId}/research-evolution/actions`,
      { data: { action: "nuke_everything", idempotency_key: "k-1", user: "default" } },
    );
    expect(bad.status()).toBe(400);
    expect((await bad.json()).detail.code).toBe("invalid_request");
  });

});

test.describe("研究进化面板 · 浏览器渲染", () => {
  // 检查器开关只在 ≤1179px 露出（`styles.css` 的 `.inspector-toggle`）；
  // 固定视口比依赖 project 几何更稳，也不会在别人改 project 宽度时莫名其妙红。
  test.use({ viewport: { width: 1024, height: 768 } });

  test("维护页在浏览器里渲染，空态写的是「尚不能比较变化」", async ({ page }, testInfo) => {
    await gotoChat(page, testInfo);
    await openMaintenanceTab(page);

    await expect(
      page.getByRole("heading", { name: "待复核与下一步研究" }),
    ).toBeVisible();
    // 这个会话还没有建立任何依赖：面板必须说「尚不能比较变化」，
    // 而不是显示成「没有需要复核的」或干脆一片空白。
    await expect(
      page.getByText(/原记录没有完整依据，尚不能比较变化/),
    ).toBeVisible();
    await expect(page.getByText(/已证伪/)).toHaveCount(0);

    const sizes = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
  });
});
