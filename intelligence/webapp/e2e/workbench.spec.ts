import { expect, test, type Page } from "@playwright/test";

const artifact = {
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

const runArtifact = {
  ...artifact,
  artifact_id: "run:2026-07-10:md:answer",
  title: "研究回答",
  category: "run",
  format: "markdown",
  viewer: "native_markdown",
  source_of_truth: "run:run_demo",
  source_path: "user:default/runs/run_demo/answer.md",
  related_run_id: "run_demo",
};

function runPayload(runId = "run_demo", question = "半导体方向怎么看？") {
  return {
    run_id: runId,
    user: "default",
    question,
    task_type: "ask",
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
        artifact_id: artifact.artifact_id,
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
    latest_artifacts: [artifact],
    latest_daily_artifact: artifact,
    pending_review_count: 1,
    needs_human_action: 0,
    data_cutoff: "2026-07-09",
  };

  await page.route("**/api/workbench/bootstrap**", (route) =>
    route.fulfill({ json: bootstrap }),
  );
  await page.route("**/api/artifacts?**", (route) =>
    route.fulfill({
      json: route.request().url().includes("category=run") ? [runArtifact] : [artifact],
    }),
  );
  await page.route(/\/api\/artifacts\/[^/]+\/content/, (route) => {
    if (route.request().url().includes("daily_agent")) {
      return route.fulfill({
        contentType: "text/html",
        body: "<html><body><h1>旧版每日简报</h1></body></html>",
      });
    }
    return route.fulfill({ contentType: "text/markdown", body: "# 研究回答" });
  });
  await page.route(/\/api\/artifacts\/[^/?]+(?:\?.*)?$/, (route) =>
    route.fulfill({ json: artifact }),
  );
  await page.route(/\/api\/runs\/([^/?]+)(?:\?.*)?$/, (route) => {
    const runId = new URL(route.request().url()).pathname.split("/").pop() ?? "run_demo";
    return route.fulfill({
      json: runPayload(
        runId,
        runId === "run_child" ? "哪些证据最容易证伪？" : "半导体方向怎么看？",
      ),
    });
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
      return route.fulfill({ json: { run_id: "run_child", status: "queued" } });
    }
    return route.continue();
  });
}

test.beforeEach(async ({ page }) => {
  await mockWorkbench(page);
  await page.goto("/");
});

test("homepage remains readable without horizontal overflow", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "开始一项可追溯的研究" })).toBeVisible();
  await expect(page.getByRole("button", { name: /题材深挖/ }).first()).toBeVisible();
  const sizes = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
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

test("registered legacy html opens in the constrained viewer", async ({ page }) => {
  await page.getByRole("button", { name: "产物库" }).click();
  await page.getByRole("button", { name: /每日 Agent 简报/ }).click();
  await expect(page.getByRole("heading", { name: "每日 Agent 简报 - 2026-07-09" })).toBeVisible();
  const frame = page.locator("iframe");
  await expect(frame).toBeVisible();
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  const source = await frame.getAttribute("src");
  expect(source).not.toBeNull();
  const content = await page.evaluate(
    async (url) => fetch(url).then((response) => response.text()),
    source ?? "",
  );
  expect(content).toContain("旧版每日简报");
});
