import { expect, test, type Page, type TestInfo } from "@playwright/test";

async function expectNoHorizontalOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
}

async function expectComposerDoesNotOverlapThread(page: Page) {
  const boxes = await page.evaluate(() => {
    const thread = document.querySelector(".message-thread");
    const composer = document.querySelector(".chat-composer-dock");
    if (!thread || !composer) return null;
    const threadBox = thread.getBoundingClientRect();
    const composerBox = composer.getBoundingClientRect();
    return {
      threadBottom: threadBox.bottom,
      composerTop: composerBox.top,
    };
  });
  expect(boxes).not.toBeNull();
  expect(boxes!.threadBottom).toBeLessThanOrEqual(boxes!.composerTop + 1);
}

async function submitQuestion(
  page: Page,
  question: string,
  completedAnswerCount: number,
) {
  await page.getByLabel("输入研究问题").fill(question);
  await page.getByRole("button", { name: "发送研究问题" }).click();
  await expect(page.getByText("模板表达 · 未配置 LLM")).toHaveCount(
    completedAnswerCount,
    { timeout: 20_000 },
  );
}

async function selectManualDailyAgent(page: Page) {
  await page.getByLabel("Skill 调用模式").selectOption("manual");
  await page.getByRole("button", { name: "选择 Skill" }).click();
  await page.getByRole("checkbox", { name: /Daily Agent/ }).check();
  await expect(page.getByLabel("已选 Skill")).toContainText("Daily Agent");
}

async function activeConversationMessages(page: Page) {
  const conversationsResponse = await page.request.get(
    "/api/conversations?user=default",
  );
  expect(conversationsResponse.ok()).toBeTruthy();
  const conversations = (await conversationsResponse.json()) as Array<{
    conversation_id: string;
  }>;
  const conversationId = conversations[0].conversation_id;
  const messagesResponse = await page.request.get(
    `/api/conversations/${conversationId}/messages?user=default`,
  );
  expect(messagesResponse.ok()).toBeTruthy();
  return (await messagesResponse.json()) as Array<{
    role: "user" | "assistant";
    run_id: string | null;
    status: string;
  }>;
}

async function startNewConversation(page: Page, testInfo: TestInfo) {
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "打开会话列表" }).click();
  }
  await page.getByRole("button", { name: "新对话" }).click();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
});

test("model settings switch between managed model and session BYOK", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "single shared BYOK registry");

  await page.getByRole("button", { name: "配置模型" }).click();
  await expect(page.getByRole("dialog", { name: "模型连接" })).toBeVisible();
  await page.getByLabel("选择模型服务商").selectOption("zhipu");
  await page.getByLabel("模型 API Key").fill("glm-e2e-session-key");
  await page.getByRole("button", { name: "使用自带密钥" }).click();
  await expect(page.getByRole("button", { name: "配置模型" })).toContainText(
    "自带密钥",
  );

  const status = await page.request.get("/api/llm/config?user=default");
  expect(status.ok()).toBeTruthy();
  const statusPayload = await status.json();
  expect(statusPayload).toMatchObject({
    mode: "byok",
    ready: true,
    session_only: true,
    provider: "zhipu",
  });
  expect(JSON.stringify(statusPayload)).not.toContain("glm-e2e-session-key");

  await page.getByRole("button", { name: "Foresight 默认模型" }).click();
  await expect(page.getByRole("button", { name: "配置模型" })).toContainText(
    "默认模型",
  );
});

test("real chat persists three fresh turns, skills, SSE, and regeneration", async ({
  page,
}, testInfo) => {
  test.slow();
  const marker = `E2E-${testInfo.project.name}-${Date.now()}`;
  const firstQuestion = `${marker} 请复盘今天市场怎么样`;
  const secondQuestion = `${marker} 第二轮请看今天研究什么`;
  const thirdQuestion = `${marker} 第三轮有哪些风险`;

  await submitQuestion(page, firstQuestion, 1);
  await expect(page.getByText("自动调用 · 每日复盘")).toBeVisible();
  const firstAnswer = page.getByLabel("研究助手消息").first();
  await expect(
    firstAnswer.getByText(/数据降级：当前未连接本地 DuckDB/),
  ).toBeVisible();
  await expect(firstAnswer.getByText(/命中主题=/)).toHaveCount(0);
  await expect(firstAnswer.locator(".stream-table-shell")).toHaveCount(0);
  await firstAnswer.getByText("运行详情", { exact: true }).click();
  await expect(
    firstAnswer.getByRole("heading", { name: "运行轨迹" }),
  ).toBeVisible();
  await expect(
    firstAnswer.getByRole("button", { name: "结构化对话报告" }),
  ).toBeVisible();

  await selectManualDailyAgent(page);
  await submitQuestion(page, secondQuestion, 2);
  await expect(page.getByText("手动指定 · Daily Agent")).toBeVisible();
  const secondAnswer = page.getByLabel("研究助手消息").nth(1);
  await expect(secondAnswer.locator(".stream-table-shell")).toHaveCount(0);
  await secondAnswer.getByText("运行详情", { exact: true }).click();
  await expect(
    secondAnswer.getByRole("button", { name: "结构化对话报告" }),
  ).toBeVisible();

  await submitQuestion(page, thirdQuestion, 3);
  await expect(page.getByLabel("你的消息")).toHaveCount(3);
  await expect(page.getByLabel("研究助手消息")).toHaveCount(3);

  const beforeRegeneration = await activeConversationMessages(page);
  const originalRunId = beforeRegeneration.at(-1)?.run_id;
  expect(originalRunId).toBeTruthy();
  await page.getByRole("button", { name: "重新生成回答" }).click();
  await expect(page.getByText("模板表达 · 未配置 LLM")).toHaveCount(4, {
    timeout: 20_000,
  });
  await expect(page.getByText(thirdQuestion, { exact: true })).toHaveCount(2);

  const afterRegeneration = await activeConversationMessages(page);
  const regeneratedRunId = afterRegeneration.at(-1)?.run_id;
  expect(regeneratedRunId).toBeTruthy();
  expect(regeneratedRunId).not.toBe(originalRunId);
  const regeneratedRunResponse = await page.request.get(
    `/api/runs/${regeneratedRunId}?user=default`,
  );
  expect(regeneratedRunResponse.ok()).toBeTruthy();
  const regeneratedRun = (await regeneratedRunResponse.json()) as {
    parent_run_id: string | null;
  };
  expect(regeneratedRun.parent_run_id).toBe(originalRunId);

  await page.reload();
  await expect(page.getByText(firstQuestion, { exact: true })).toBeVisible();
  await expect(page.getByText(secondQuestion, { exact: true })).toBeVisible();
  await expect(page.getByText("自动调用 · 每日复盘")).toBeVisible();
  await expect(page.getByText("手动指定 · Daily Agent")).toBeVisible();
  await expect(page.getByText("模板表达 · 未配置 LLM")).toHaveCount(4);

  await expectNoHorizontalOverflow(page);
  await expectComposerDoesNotOverlapThread(page);
});

test("stop preserves cancellation and responsive drawers remain closable", async ({
  page,
}, testInfo) => {
  await startNewConversation(page, testInfo);
  await selectManualDailyAgent(page);
  await page
    .getByLabel("输入研究问题")
    .fill(`E2E-cancel-${testInfo.project.name} 请完整分析今天研究什么`);
  await page.getByRole("button", { name: "发送研究问题" }).click();
  await page.getByRole("button", { name: "停止生成" }).click({
    timeout: 5_000,
  });
  await expect(page.getByText("已停止生成，已保留已生成内容。")).toBeVisible({
    timeout: 20_000,
  });

  await page.reload();
  await expect(page.getByText("已停止生成，已保留已生成内容。")).toBeVisible();
  const messages = await activeConversationMessages(page);
  expect(messages.at(-1)?.status).toBe("cancelled");

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "打开会话列表" }).click();
    await expect(
      page.getByRole("complementary", { name: "会话列表" }),
    ).toHaveClass(/open/);
    await page
      .getByRole("button", { name: "关闭会话列表", exact: true })
      .click();
    await expect(
      page.getByRole("complementary", { name: "会话列表" }),
    ).not.toHaveClass(/open/);
  }
  if (testInfo.project.name !== "desktop") {
    await page.getByRole("button", { name: "打开研究检查器" }).click();
    await expect(
      page.getByRole("complementary", { name: "研究检查器" }),
    ).toHaveClass(/open/);
    await page.getByRole("button", { name: "关闭检查器" }).click();
    await expect(
      page.getByRole("complementary", { name: "研究检查器" }),
    ).not.toHaveClass(/open/);
  }

  await expectNoHorizontalOverflow(page);
  await expectComposerDoesNotOverlapThread(page);
});
