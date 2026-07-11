import { expect, test, type Page } from "@playwright/test";

const dailyAgentArtifact = {
  artifact_id: "daily_agent:2026-07-09:html:demo",
  title: "每日 Agent 简报 - 2026-07-09",
  category: "daily_agent",
  format: "html",
  date: "2026-07-09",
  viewer: "legacy_html",
  source_of_truth: "market_feature_store/exports/2026-07-09-daily-agent.json",
  source_path: "复盘/daily/2026-07-09/2026-07-09-daily-agent.html",
  related_run_id: null,
  status: "ok",
  schema_version: 1,
  updated_at: "2026-07-09T15:00:00+08:00",
  canonical_exists: true,
};

const dailyReviewArtifact = {
  ...dailyAgentArtifact,
  artifact_id: "daily_review:2026-07-09:html:demo",
  title: "每日复盘 - 2026-07-09",
  category: "daily_review",
  source_of_truth: "复盘/daily/2026-07-09/2026-07-09-daily-review.md",
  source_path: "复盘/daily/2026-07-09/2026-07-09-daily-review.html",
};

const runArtifact = {
  ...dailyAgentArtifact,
  artifact_id: "run:2026-07-10:md:answer",
  title: "研究回答",
  category: "run",
  format: "markdown",
  viewer: "native_markdown",
  source_of_truth: "run:run_demo",
  source_path: "user:default/runs/run_demo/answer.md",
  related_run_id: "run_demo",
};

const reportItem = {
  title: "氢能源",
  summary: "多信号共振，但仍需官方事实确认。",
  badges: ["旧逻辑唤醒", "旧逻辑待验证"],
  meta: [{ label: "代表股票", value: "金宏气体、昊华科技" }],
  next_action: "查公告、调研纪要和订单。",
  details: ["缺失：L3 官方验证"],
};

const dailyAgentProjection = {
  report_type: "daily_agent",
  title: "日常研究雷达",
  date: "2026-07-09",
  source_mode: "canonical_json",
  plain_summary: [
    "1 个旧逻辑重新活跃，0 个新方向进入候选。",
    "今日研究队列共 2 项。",
    "优先关注氢能源，结论仍需结合证据层级验证。",
  ],
  metrics: [
    { label: "旧逻辑重新活跃", value: "1", tone: "attention" },
    { label: "新逻辑候选", value: "0" },
    { label: "需要补官方证据", value: "1" },
    { label: "等待市场验证", value: "1" },
    { label: "降级或观察", value: "0" },
  ],
  sections: [
    { title: "值得关注", items: [reportItem, { ...reportItem, title: "风电" }] },
    {
      title: "今天要做什么",
      items: [
        { ...reportItem, title: "补齐题材研究" },
        { ...reportItem, title: "核对官方证据" },
      ],
    },
    { title: "证据边界", items: [{ ...reportItem, title: "仍缺 L3 官方验证" }] },
  ],
  glossary: [
    { term: "IMA", definition: "快速建立题材边界、产业链位置与核心公司的研究卡。" },
    { term: "L3", definition: "公告、订单或调研等官方事实。" },
  ],
  provenance: {
    canonical_path: dailyAgentArtifact.source_of_truth,
    rendered_path: dailyAgentArtifact.source_path,
    warnings: [],
    original_report_available: true,
    original_artifact_id: dailyAgentArtifact.artifact_id,
    generated_at: "2026-07-09T20:00:00+08:00",
  },
};

const dailyReviewProjection = {
  report_type: "daily_review",
  title: "每日复盘",
  date: "2026-07-09",
  source_mode: "canonical_markdown",
  plain_summary: [
    "市场性质：震荡修复。",
    "主导方向：AI 算力与电力设备。",
    "市场回暖，但量能仍需下一交易日确认。",
  ],
  metrics: [
    { label: "指数表现", value: "上证 +0.8%" },
    { label: "成交额", value: "1.35 万亿" },
    { label: "涨跌广度", value: "3,812 / 1,102" },
    { label: "涨停 / 跌停", value: "74 / 8" },
    { label: "市场强度", value: "中强" },
  ],
  sections: [
    { title: "主要方向", items: [{ ...reportItem, title: "AI 算力" }] },
    { title: "风险与验证", items: [{ ...reportItem, title: "量能尚未确认" }] },
    { title: "专业数据", items: [{ ...reportItem, title: "核心看板" }] },
  ],
  glossary: [],
  provenance: {
    canonical_path: dailyReviewArtifact.source_of_truth,
    rendered_path: dailyReviewArtifact.source_path,
    warnings: [],
    original_report_available: true,
    original_artifact_id: dailyReviewArtifact.artifact_id,
  },
};

function runPayload(runId = "run_demo", question = "半导体方向怎么看？") {
  const isDaily = runId === "run_daily";
  return {
    run_id: runId,
    user: "default",
    question,
    task_type: isDaily ? "daily" : "ask",
    status: "completed",
    schema_version: 1,
    session_id: "session_demo",
    parent_run_id: runId === "run_child" ? "run_demo" : null,
    created_at: "2026-07-10T10:00:00+08:00",
    finished_at: "2026-07-10T10:01:00+08:00",
    source_date: "2026-07-09",
    duckdb_cutoff: "2026-07-09",
    kb_commit: "abc123",
    manifest_ref: null,
    degrades: runId === "run_demo" ? ["llm_unavailable_template_answer"] : [],
    error: null,
    artifacts:
      runId === "run_demo"
        ? [
            {
              artifact_id: "artifact_answer",
              path: "answer.md",
              renderer: "markdown",
              title: "研究回答",
              sha256: "abc",
              bytes: 1024,
              previewable: true,
              downloadable: true,
            },
          ]
        : [],
  };
}

const structuredDailyReport = {
  schema_version: 1,
  report_id: "run_daily",
  title: "今日复盘",
  task_type: "daily",
  status: "completed",
  as_of: "2026-07-10",
  llm: { used: true, provider: "glm", model: "glm-5.2" },
  warnings: [],
  modules: [
    {
      module_id: "llm_synthesis",
      title: "LLM 综合判断",
      kind: "narrative",
      status: "complete",
      summary: "只在证据边界内组织表达。",
      content: "市场处于修复阶段，下一交易日验证成交额能否延续。",
      metrics: [],
      items: [],
      table: null,
      warnings: [],
      provenance: {
        source: "retrieved_evidence",
        as_of: "2026-07-10",
        generated_by: "llm:glm",
      },
    },
    {
      module_id: "l2_moneyflow",
      title: "L2 大单资金流",
      kind: "table",
      status: "degraded",
      summary: "自有逐笔成交口径。",
      content: null,
      metrics: [
        { label: "扫描日期", value: "2026-07-08" },
        { label: "覆盖股票", value: "112", context: "涨停股 + 成交额前100" },
      ],
      items: [],
      table: {
        columns: [
          { key: "stock", label: "股票" },
          { key: "main_buy_net_wan", label: "主买净额(万)" },
        ],
        rows: [{ stock: "深信服", main_buy_net_wan: 12000 }],
      },
      warnings: ["L2 最新扫描日早于报告日。"],
      provenance: {
        source: "feature_l2_capital_flow_daily",
        as_of: "2026-07-08",
        generated_by: "deterministic_duckdb_query",
      },
    },
  ],
};

function artifactId(url: string): string {
  const parts = new URL(url).pathname.split("/");
  return decodeURIComponent(parts.at(-1) ?? "");
}

async function mockWorkbench(page: Page) {
  const recentRun = { ...runPayload(), status: "running", finished_at: null };
  const bootstrap = {
    user: "default",
    workflows: [
      {
        id: "daily",
        title: "今日复盘",
        description: "打开最新日常产物，再继续追问",
        task_type: "daily",
        artifact_id: dailyAgentArtifact.artifact_id,
        prompt: "复盘",
      },
      {
        id: "theme",
        title: "题材深挖",
        description: "从产业链、证据与盘面阶段拆解题材",
        task_type: "theme",
        artifact_id: null,
        prompt: "请深挖这个题材：",
      },
      {
        id: "stock_research",
        title: "个股研究",
        description: "核对公司角色、兑现路径与风险",
        task_type: "stock_research",
        artifact_id: null,
        prompt: "请研究这只股票：",
      },
    ],
    recent_runs: [recentRun],
    latest_artifacts: [dailyAgentArtifact, dailyReviewArtifact],
    latest_daily_artifact: dailyAgentArtifact,
    pending_review_count: 1,
    needs_human_action: 0,
    data_cutoff: "2026-07-09",
  };

  await page.route("**/api/workbench/bootstrap**", (route) =>
    route.fulfill({ json: bootstrap }),
  );
  await page.route(/\/api\/artifacts(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: route.request().url().includes("category=run")
        ? [runArtifact]
        : [dailyAgentArtifact, dailyReviewArtifact],
    }),
  );
  await page.route(/\/api\/artifacts\/[^/?]+(?:\?.*)?$/, (route) => {
    const id = artifactId(route.request().url());
    const descriptor =
      id === dailyReviewArtifact.artifact_id
        ? dailyReviewArtifact
        : dailyAgentArtifact;
    return route.fulfill({ json: descriptor });
  });
  await page.route(/\/api\/artifacts\/[^/]+\/content/, (route) =>
    route.fulfill({
      contentType: "text/html",
      body: `<html><body><h1>旧版归档报告</h1><img alt="历史图表" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='40'%3E%3C/svg%3E"></body></html>`,
    }),
  );
  await page.route(/\/api\/artifacts\/[^/]+\/projection/, (route) => {
    const id = decodeURIComponent(
      new URL(route.request().url()).pathname.split("/").at(-2) ?? "",
    );
    return route.fulfill({
      json:
        id === dailyReviewArtifact.artifact_id
          ? dailyReviewProjection
          : dailyAgentProjection,
    });
  });
  await page.route(/\/api\/runs\/([^/?]+)(?:\?.*)?$/, (route) => {
    const runId = new URL(route.request().url()).pathname.split("/").pop() ?? "run_demo";
    return route.fulfill({
      json: runPayload(
        runId,
        runId === "run_child"
          ? "哪些证据最容易证伪？"
          : runId === "run_daily"
            ? "今日复盘"
            : "半导体方向怎么看？",
      ),
    });
  });
  await page.route(/\/api\/runs\/([^/]+)\/report/, (route) => {
    const runId = new URL(route.request().url()).pathname.split("/").at(-2);
    return route.fulfill({ json: runId === "run_daily" ? structuredDailyReport : null });
  });
  await page.route(/\/api\/runs\/([^/]+)\/trace/, (route) =>
    route.fulfill({
      json: [
        {
          step_id: "s01",
          name: "ask_retrieve_compose",
          status: "completed",
          started_at: "2026-07-10T10:00:00+08:00",
          finished_at: "2026-07-10T10:00:10+08:00",
          input_summary: "半导体方向怎么看？",
          output_summary: "命中盘面与图谱",
          warnings: [],
        },
      ],
    }),
  );
  await page.route(/\/api\/runs\/([^/]+)\/followups/, (route) =>
    route.fulfill({
      json: {
        followups: route.request().url().includes("run_child")
          ? []
          : [{ type: "evidence", question: "哪些证据最容易证伪？", rationale: "检查反证" }],
      },
    }),
  );
  await page.route(/\/api\/runs\/([^/]+)\/context/, (route) =>
    route.fulfill({
      json: {
        evidence: [
          {
            id: "source:market",
            label: "盘面快照",
            kind: "source",
            classification: "fact_source",
            detail: "本次检索已命中",
            status: "hit",
          },
        ],
        memory: [],
        review: [],
        gaps: ["llm_unavailable_template_answer"],
        warnings: [],
        metadata: {
          source_date: "2026-07-09",
          duckdb_cutoff: "2026-07-09",
          kb_commit: "abc123",
          manifest_ref: null,
        },
      },
    }),
  );
  await page.route(/\/api\/runs\/run_demo\/artifacts\/answer.md/, (route) =>
    route.fulfill({
      contentType: "text/markdown",
      body: "# 结论\n半导体仍需观察下一交易日承接。",
    }),
  );
  await page.route("**/api/runs", async (route) => {
    if (route.request().method() === "POST") {
      const requestBody = route.request().postDataJSON() as { task_type?: string };
      return route.fulfill({
        json: {
          run_id: requestBody.task_type === "daily" ? "run_daily" : "run_child",
          status: "queued",
        },
      });
    }
    return route.continue();
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
}

async function openArtifact(page: Page, title: RegExp) {
  await page.getByRole("button", { name: "产物库" }).click();
  await page.getByRole("button", { name: title }).click();
}

test.beforeEach(async ({ page }) => {
  await mockWorkbench(page);
  await page.goto("/");
});

test("homepage remains readable with explicitly named mobile controls", async ({
  page,
}) => {
  await expect(page.getByRole("heading", { name: "开始一项可追溯的研究" })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建研究" })).toHaveAttribute(
    "aria-label",
    "新建研究",
  );
  await expect(page.getByRole("button", { name: "研究首页" })).toHaveAttribute(
    "aria-label",
    "研究首页",
  );
  await expect(page.getByRole("button", { name: "产物库" })).toHaveAttribute(
    "aria-label",
    "产物库",
  );
  await expectNoHorizontalOverflow(page);
});

test("daily workflow opens an LLM and L2 structured report", async ({ page }) => {
  await page.locator(".workflow-row", { hasText: "今日复盘" }).click();

  await expect(page.getByText("glm · glm-5.2")).toBeVisible();
  await expect(page.getByRole("heading", { name: "LLM 综合判断" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "L2 大单资金流" })).toBeVisible();
  await expect(page.getByText("深信服")).toBeVisible();
  await expect(page.getByText("L2 最新扫描日早于报告日。")).toBeVisible();
  await expect(page.locator(".iframe-shell")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
});

test("native Daily Agent is the default and keeps the original report secondary", async ({
  page,
}) => {
  await openArtifact(page, /每日 Agent 简报/);
  await expect(page.getByRole("heading", { name: "日常研究雷达" })).toBeVisible();
  await expect(page.getByText("旧逻辑重新活跃", { exact: true })).toBeVisible();
  await expect(page.locator("iframe")).toBeHidden();
  await page.getByText("原始报告", { exact: true }).click();
  const frame = page.locator("iframe");
  await expect(frame).toBeVisible();
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  await expectNoHorizontalOverflow(page);
});

test("native Daily Review renders canonical sections without horizontal overflow", async ({
  page,
}) => {
  await openArtifact(page, /每日复盘/);
  await expect(page.getByRole("heading", { name: "每日复盘", exact: true })).toBeVisible();
  await expect(page.getByText("市场温度")).toBeVisible();
  await expect(page.getByRole("heading", { name: "风险与验证" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("surface changes reset document scroll", async ({ page }) => {
  await openArtifact(page, /每日 Agent 简报/);
  await page.evaluate(() => {
    document.body.style.minHeight = "2600px";
    window.scrollTo(0, 1400);
  });
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  await page.getByRole("button", { name: "研究首页" }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
});

test("late artifact responses cannot replace the current selection", async ({ page }) => {
  await page.route(/\/api\/artifacts\/[^/?]+(?:\?.*)?$/, async (route) => {
    const id = artifactId(route.request().url());
    if (id === dailyAgentArtifact.artifact_id) {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    return route.fulfill({
      json:
        id === dailyReviewArtifact.artifact_id
          ? dailyReviewArtifact
          : dailyAgentArtifact,
    });
  });

  await openArtifact(page, /每日 Agent 简报/);
  await page.getByRole("button", { name: "产物库" }).click();
  await page.getByRole("button", { name: /每日复盘/ }).click();
  await expect(page.getByRole("heading", { name: "每日复盘", exact: true })).toBeVisible();
  await page.waitForTimeout(350);
  await expect(
    page.getByRole("heading", { name: "每日 Agent 简报 - 2026-07-09" }),
  ).toHaveCount(0);
});

test("completed run keeps degrade, answer, artifacts and followup in one surface", async ({
  page,
}) => {
  await page.getByRole("button", { name: /半导体方向怎么看/ }).last().click();
  await expect(page.getByRole("heading", { name: "半导体方向怎么看？" })).toBeVisible();
  await expect(page.getByText("本次研究使用了降级路径")).toBeVisible();
  await expect(page.getByText("半导体仍需观察下一交易日承接。")).toBeVisible();
  await expect(page.getByRole("button", { name: /研究回答/ })).toBeVisible();
  await page.getByRole("button", { name: /哪些证据最容易证伪/ }).click();
  await expect(page.getByRole("heading", { name: "哪些证据最容易证伪？" })).toBeVisible();
});

test("running state remains visible while SSE reconnects", async ({ page }) => {
  await page.route(/\/api\/runs\/run_demo(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        ...runPayload(),
        status: "running",
        finished_at: null,
        degrades: [],
        artifacts: [],
      },
    }),
  );
  await page.route(/\/api\/runs\/run_demo\/events/, (route) => route.abort());

  await page.getByRole("button", { name: /半导体方向怎么看/ }).last().click();
  await expect(page.getByRole("article").getByText("运行中", { exact: true })).toBeVisible();
  await expect(page.getByText("实时更新")).toBeVisible();
  await expect(page.getByText("正在恢复连接")).toBeVisible();
});

test("failed run preserves the failure reason and completed trace", async ({ page }) => {
  await page.route(/\/api\/runs\/run_demo(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        ...runPayload(),
        status: "failed",
        finished_at: "2026-07-10T10:00:20+08:00",
        degrades: [],
        error: "mock data source failure",
        artifacts: [],
      },
    }),
  );

  await page.getByRole("button", { name: /半导体方向怎么看/ }).last().click();
  await expect(page.getByRole("alert")).toContainText("mock data source failure");
  await expect(page.getByText("没有生成回答产物")).toBeVisible();
  await expect(page.getByText("查询盘面与检索证据")).toBeVisible();
});
