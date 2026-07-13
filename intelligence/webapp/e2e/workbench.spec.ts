import { expect, test, type Page, type TestInfo } from "@playwright/test";

const answerTimeout = 45_000;

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
  await expect
    .poll(
      async () =>
        (await activeConversationMessages(page)).filter(
          (message) =>
            message.role === "assistant" && message.status === "completed",
        ).length,
      { timeout: answerTimeout },
    )
    .toBe(completedAnswerCount);
  await expect(page.getByLabel("研究助手消息")).toHaveCount(
    completedAnswerCount,
  );
}

async function selectManualDailyAgent(page: Page) {
  await selectManualSkill(page, /Daily Agent/);
}

async function selectManualSkill(page: Page, name: RegExp) {
  await page.getByLabel("研究工具选择方式").selectOption("manual");
  await page.getByRole("button", { name: "选择研究工具" }).click();
  await page.getByRole("checkbox", { name }).check();
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

async function selectWorkbenchSection(
  page: Page,
  testInfo: TestInfo,
  section: "今日" | "主题" | "信号" | "验证" | "问答",
) {
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "打开会话列表" }).click();
  }
  await page.getByRole("button", { name: section, exact: true }).click();
}

test.beforeEach(async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "数据缺失" })).toBeVisible();
  await selectWorkbenchSection(page, testInfo, "问答");
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
});

test("structured workbench keeps five surfaces available", async ({
  page,
}, testInfo) => {
  await selectWorkbenchSection(page, testInfo, "今日");
  await expect(page.getByRole("heading", { name: "数据缺失" })).toBeVisible();
  await selectWorkbenchSection(page, testInfo, "主题");
  await expect(
    page.getByRole("heading", { name: "知识共识 × 盘面确认" }),
  ).toBeVisible();
  await selectWorkbenchSection(page, testInfo, "信号");
  await expect(
    page.getByRole("heading", { name: "只推变化，不重复旧观点" }),
  ).toBeVisible();
  await selectWorkbenchSection(page, testInfo, "验证");
  await expect(
    page.getByRole("heading", { name: "机构胜率、资金流与假设回检" }),
  ).toBeVisible();
  await selectWorkbenchSection(page, testInfo, "问答");
  await expect(page.getByLabel("输入研究问题")).toBeVisible();
});

test("model settings switch between managed model and session BYOK", async ({
  page,
}) => {
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
  await startNewConversation(page, testInfo);
  const marker = `E2E-${testInfo.project.name}-${Date.now()}`;
  const firstQuestion = `${marker} 请复盘今天市场怎么样`;
  const secondQuestion = `${marker} 第二轮请看今天研究什么`;
  const thirdQuestion = `${marker} 第三轮有哪些风险`;

  await submitQuestion(page, firstQuestion, 1);
  await expect(page.getByText("已自动选择 · 每日复盘")).toBeVisible();
  const firstAnswer = page.getByLabel("研究助手消息").first();
  await expect(firstAnswer.getByText(/直接定性/)).toBeVisible();
  await expect(firstAnswer.getByText(/下一步验证/)).toBeVisible();
  await expect(firstAnswer.getByText(/图谱命中|状态机|检索骨架/)).toHaveCount(
    0,
  );
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
  await expect(page.getByText("已指定工具 · Daily Agent")).toBeVisible();
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
  await expect(page.getByText(thirdQuestion, { exact: true })).toHaveCount(2);
  await expect
    .poll(
      async () => {
        const messages = await activeConversationMessages(page);
        const latest = messages.at(-1);
        return (
          latest?.status === "completed" &&
          latest.run_id !== originalRunId
        );
      },
      { timeout: answerTimeout },
    )
    .toBe(true);

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
  await selectWorkbenchSection(page, testInfo, "问答");
  await expect(page.getByText(firstQuestion, { exact: true })).toBeVisible();
  await expect(page.getByText(secondQuestion, { exact: true })).toBeVisible();
  await expect(page.getByText("已自动选择 · 每日复盘")).toBeVisible();
  await expect(page.getByText("已指定工具 · Daily Agent")).toHaveCount(3);
  await expect(page.getByLabel("研究助手消息")).toHaveCount(4);

  await expectNoHorizontalOverflow(page);
  await expectComposerDoesNotOverlapThread(page);
});

test("stock deep-dive owns and continues a traceable Workbench answer", async ({
  page,
}, testInfo) => {
  test.slow();
  await startNewConversation(page, testInfo);
  await expect(page.getByLabel("研究工具选择方式")).toBeEnabled();
  await expect(page.getByLabel("已选研究工具")).toHaveCount(0);
  await selectManualSkill(page, /个股深挖/);
  await expect(page.getByLabel("已选研究工具")).toContainText("个股深挖");

  await submitQuestion(page, "请个股深挖英维克的液冷业务", 1);

  await expect(page.getByText("已指定工具 · 个股深挖")).toBeVisible();
  const answer = page.getByLabel("研究助手消息").first();
  await expect(
    answer.getByRole("heading", { name: "个股深挖" }),
  ).toBeVisible();
  await expect(answer.getByRole("heading", { name: "核心判断" })).toBeVisible();
  await expect(answer.getByRole("heading", { name: "公司证据" })).toBeVisible();
  await expect(
    answer.getByRole("heading", { name: "下一步如何验证" }),
  ).toBeVisible();
  await expect(
    answer.getByText(
      "本轮未形成可回查的硬证据；当前判断按待验证展示。",
    ),
  ).toHaveCount(0);
  await expect(answer.getByText(/液冷/).first()).toBeVisible();
  await expect(
    answer.getByText(
      /数据要素|entity_exposures|evidence_index|evidence_count|concept_graph|RAG|DuckDB|registry|internal|baseline|multi-source|人工 review|sanity check|Provider|\brelated\b/,
    ),
  ).toHaveCount(0);

  await expect(page.getByLabel("已选研究工具")).toContainText("个股深挖");
  await submitQuestion(page, "那它的主要风险和下一步验证是什么？", 2);

  const followUp = page.getByLabel("研究助手消息").nth(1);
  await expect(
    followUp.getByRole("heading", { name: "个股深挖" }),
  ).toBeVisible();
  await expect(followUp.getByText(/英维克/).first()).toBeVisible();
  await expect(
    followUp.getByRole("heading", { name: "反证与缺口" }),
  ).toBeVisible();
  await expect(
    followUp.getByRole("heading", { name: "下一步如何验证" }),
  ).toBeVisible();
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
  await selectWorkbenchSection(page, testInfo, "问答");
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
  const inspector = page.getByRole("complementary", {
    name: "研究检查器",
    includeHidden: true,
  });
  if (testInfo.project.name === "desktop") {
    await expect(inspector).toHaveClass(/open/);
  } else {
    await page.getByRole("button", { name: "打开研究检查器" }).click();
    await expect(inspector).toHaveClass(/open/);
  }
  await page.getByRole("button", { name: "关闭检查器" }).click();
  await expect(inspector).not.toHaveClass(/open/);
  if (testInfo.project.name === "desktop") {
    await page.getByRole("button", { name: "打开研究检查器" }).click();
    await expect(inspector).toHaveClass(/open/);
  }

  await expectNoHorizontalOverflow(page);
  await expectComposerDoesNotOverlapThread(page);
});
