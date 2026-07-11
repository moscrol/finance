import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { upsertStructuredReportModule } from "../structuredReport";
import { upsertTraceStep } from "../trace";
import type {
  ArtifactDescriptor,
  Bootstrap,
  Run,
  RunBundle,
} from "../types";
import { ArtifactLibrary } from "./ArtifactLibrary";
import { ArtifactViewer } from "./ArtifactViewer";
import { ResearchHome } from "./ResearchHome";
import { ResearchInspector } from "./ResearchInspector";
import { RunView } from "./RunView";
import { StructuredReportView } from "./StructuredReportView";

const apiMocks = vi.hoisted(() => ({
  createRun: vi.fn(),
  getArtifact: vi.fn(),
  getArtifactProjection: vi.fn(),
  getArtifactText: vi.fn(),
  getBootstrap: vi.fn(),
  getFollowups: vi.fn(),
  getRun: vi.fn(),
  getRunArtifactText: vi.fn(),
  getRunContext: vi.fn(),
  getRunReport: vi.fn(),
  getTrace: vi.fn(),
  listArtifacts: vi.fn(),
}));

vi.mock("../api", () => ({
  ...apiMocks,
  artifactContentUrl: (artifactId: string) => `/api/artifacts/${artifactId}/content`,
  runEventsUrl: (runId: string) => `/api/runs/${runId}/events`,
}));

const artifact: ArtifactDescriptor = {
  artifact_id: "daily:2026-07-09:md:1",
  title: "每日 Agent 简报 - 2026-07-09",
  category: "daily_agent",
  format: "markdown",
  date: "2026-07-09",
  viewer: "native_markdown",
  source_of_truth: "market_feature_store/exports/2026-07-09-daily-agent.md",
  source_path: "market_feature_store/exports/2026-07-09-daily-agent.md",
  related_run_id: null,
  status: "ok",
  schema_version: 1,
  updated_at: "2026-07-09T15:00:00+08:00",
  canonical_exists: true,
};

const bootstrap: Bootstrap = {
  user: "default",
  workflows: [
    {
      id: "daily",
      title: "今日复盘",
      description: "打开最新产物",
      task_type: "daily",
      artifact_id: artifact.artifact_id,
      prompt: "复盘",
    },
    {
      id: "theme",
      title: "题材深挖",
      description: "拆解题材",
      task_type: "theme",
      artifact_id: null,
      prompt: "深挖：",
    },
    {
      id: "stock_research",
      title: "个股研究",
      description: "研究公司",
      task_type: "stock_research",
      artifact_id: null,
      prompt: "研究：",
    },
  ],
  recent_runs: [],
  latest_artifacts: [artifact],
  latest_daily_artifact: artifact,
  pending_review_count: 0,
  needs_human_action: 0,
  data_cutoff: "2026-07-09",
};

const bundle: RunBundle = {
  run: {
    run_id: "run_demo",
    user: "default",
    question: "半导体方向怎么看？",
    task_type: "ask",
    status: "completed",
    schema_version: 1,
    session_id: "session_demo",
    parent_run_id: null,
    created_at: "2026-07-10T10:00:00+08:00",
    finished_at: "2026-07-10T10:01:00+08:00",
    source_date: "2026-07-09",
    duckdb_cutoff: "2026-07-09",
    kb_commit: "abc123",
    kb_index_built_at: "2026-07-09T16:00:00+08:00",
    kb_index_freshness: "fresh",
    manifest_ref: null,
    degrades: ["llm_unavailable_template_answer"],
    error: null,
    artifacts: [
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
    ],
  },
  trace: [
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
  followups: [
    {
      type: "evidence",
      question: "哪些证据最容易证伪？",
      rationale: "检查反证",
    },
  ],
  context: {
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
      kb_index_built_at: "2026-07-09T16:00:00+08:00",
      kb_index_freshness: "fresh",
      manifest_ref: null,
    },
  },
  answer: "# 结论\n证据仍需下一交易日确认。",
  structuredReport: null,
  registeredArtifacts: [{ ...artifact, related_run_id: "run_demo", source_path: "user:default/runs/run_demo/answer.md" }],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

describe("Workbench components", () => {
  it("starts a workflow preset and submits from the unified composer", async () => {
    const user = userEvent.setup();
    const onWorkflow = vi.fn();
    const onSubmit = vi.fn();
    const { rerender } = render(
      <ResearchHome
        bootstrap={bootstrap}
        draft=""
        taskType="ask"
        submitting={false}
        onDraftChange={vi.fn()}
        onSubmit={onSubmit}
        onWorkflow={onWorkflow}
        onOpenRun={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /题材深挖/ }));
    expect(onWorkflow).toHaveBeenCalledWith(bootstrap.workflows[1]);

    rerender(
      <ResearchHome
        bootstrap={bootstrap}
        draft="请研究液冷"
        taskType="theme"
        submitting={false}
        onDraftChange={vi.fn()}
        onSubmit={onSubmit}
        onWorkflow={onWorkflow}
        onOpenRun={vi.fn()}
      />,
    );
    fireEvent.keyDown(screen.getByLabelText("输入研究问题"), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("请研究液冷");
  });

  it("keeps degraded state, evidence and followups visible", async () => {
    const onFollowup = vi.fn();
    const user = userEvent.setup();
    render(
      <RunView
        bundle={bundle}
        connection="connected"
        onOpenRun={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={onFollowup}
      />,
    );

    expect(screen.getByText("本次研究使用了降级路径")).toBeInTheDocument();
    expect(screen.getByText("证据仍需下一交易日确认。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /哪些证据最容易证伪/ }));
    expect(onFollowup).toHaveBeenCalledWith("哪些证据最容易证伪？");
  });

  it("renders LLM and L2 modules without an HTML artifact", () => {
    render(
      <RunView
        bundle={{
          ...bundle,
          structuredReport: {
            schema_version: 1,
            report_id: "run_demo",
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
                content: "量能修复，仍需验证。",
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
                metrics: [{ label: "扫描日期", value: "2026-07-08" }],
                items: [],
                table: {
                  columns: [{ key: "stock", label: "股票" }],
                  rows: [{ stock: "深信服" }],
                },
                warnings: ["L2 最新扫描日早于报告日。"],
                provenance: {
                  source: "feature_l2_capital_flow_daily",
                  as_of: "2026-07-08",
                  generated_by: "deterministic_duckdb_query",
                },
              },
            ],
          },
        }}
        connection="connected"
        onOpenRun={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(screen.getByText("glm · glm-5.2")).toBeVisible();
    expect(screen.getByRole("heading", { name: "LLM 综合判断" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "L2 大单资金流" })).toBeVisible();
    expect(screen.getByText("深信服")).toBeVisible();
    expect(screen.getByText("L2 最新扫描日早于报告日。")).toBeVisible();
  });

  it("sanitizes markdown before rendering an artifact", () => {
    const { container } = render(
      <ArtifactViewer
        artifact={artifact}
        content={'# 安全正文\n<script>alert("x")</script><strong>保留内容</strong>'}
        loading={false}
        contentUrl="/api/artifacts/demo/content"
        onBack={vi.fn()}
        onOpenRun={vi.fn()}
      />,
    );
    expect(screen.getByText("安全正文")).toBeInTheDocument();
    expect(screen.getByText("保留内容")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
  });

  it("keeps workflow summaries in their native JSON viewer", () => {
    render(
      <ArtifactViewer
        artifact={{
          ...artifact,
          artifact_id: "daily_review:2026-07-09:json:summary",
          category: "daily_review",
          format: "json",
          viewer: "native_json",
          source_path:
            "market_feature_store/exports/2026-07-09-daily-workflow-summary.json",
          source_of_truth:
            "market_feature_store/exports/2026-07-09-daily-workflow-summary.json",
        }}
        content='{"status":"completed"}'
        loading={false}
        contentUrl="/api/artifacts/summary/content"
        onBack={vi.fn()}
        onOpenRun={vi.fn()}
      />,
    );

    expect(screen.getByText(/"status": "completed"/)).toBeVisible();
    expect(screen.queryByText("正在生成原生报告…")).toBeNull();
  });

  it("filters the artifact registry by date", async () => {
    const user = userEvent.setup();
    const olderArtifact = {
      ...artifact,
      artifact_id: "daily:2026-07-08:markdown:1",
      title: "每日 Agent 简报 - 2026-07-08",
      date: "2026-07-08",
      source_path: "market_feature_store/exports/2026-07-08-daily-agent.md",
    };
    render(
      <ArtifactLibrary
        artifacts={[artifact, olderArtifact]}
        loading={false}
        onOpen={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByLabelText("按日期筛选"), "2026-07-09");
    expect(screen.getByText("每日 Agent 简报 - 2026-07-09")).toBeVisible();
    expect(screen.queryByText("每日 Agent 简报 - 2026-07-08")).toBeNull();
  });

  it("exposes internal tool names only inside run details", async () => {
    const user = userEvent.setup();
    render(
      <ResearchInspector bundle={bundle} artifact={null} open onClose={vi.fn()} />,
    );
    await user.click(screen.getByRole("tab", { name: "运行" }));
    expect(screen.getByText("ask_retrieve_compose")).not.toBeVisible();
    await user.click(screen.getByText("命中盘面与图谱"));
    expect(screen.getByText("ask_retrieve_compose")).toBeVisible();
  });

  it("shows report degradation warnings and the bound KB snapshot", () => {
    render(
      <>
        <StructuredReportView
          report={{
            schema_version: 1,
            report_id: "run_demo",
            title: "今日复盘",
            task_type: "daily",
            status: "completed",
            as_of: "2026-07-10",
            llm: { used: true, provider: "glm", model: "glm-5.2" },
            warnings: ["wiki-rag 索引新鲜度=stale"],
            modules: [],
          }}
        />
        <ResearchInspector bundle={bundle} artifact={null} open onClose={vi.fn()} />
      </>,
    );

    expect(screen.getByText("本报告包含降级或质量警告")).toBeVisible();
    expect(screen.getByText("wiki-rag 索引新鲜度=stale")).toBeVisible();
    expect(screen.getByText("知识库索引快照")).toBeVisible();
    expect(screen.getByText(/revision=abc123/)).toBeVisible();
    expect(screen.getByText(/freshness=fresh/)).toBeVisible();
  });
});

describe("Workbench navigation reliability", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
    apiMocks.getFollowups.mockResolvedValue([]);
    apiMocks.getRunContext.mockResolvedValue(bundle.context);
    apiMocks.getRunReport.mockResolvedValue(null);
    apiMocks.getTrace.mockResolvedValue([]);
    apiMocks.getRunArtifactText.mockResolvedValue(null);
    apiMocks.createRun.mockResolvedValue({ run_id: "run_created", status: "queued" });
  });

  it("starts a new streaming run for the daily workflow", async () => {
    apiMocks.getBootstrap.mockResolvedValue(bootstrap);
    apiMocks.listArtifacts.mockResolvedValue([]);
    apiMocks.getRun.mockResolvedValue({
      ...bundle.run,
      run_id: "run_created",
      task_type: "daily",
      status: "completed",
      artifacts: [],
    });
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /今日复盘/ }).length).toBeGreaterThan(0);
    });
    await user.click(screen.getAllByRole("button", { name: /今日复盘/ })[0]);

    expect(apiMocks.createRun).toHaveBeenCalledWith("复盘", "daily", "default", null);
  });

  it("upserts replayed report modules by module_id", () => {
    const report = {
      schema_version: 1,
      report_id: "run_demo",
      title: "今日复盘",
      task_type: "daily",
      status: "streaming" as const,
      as_of: "2026-07-10",
      llm: { used: false, provider: null, model: null },
      warnings: [],
      modules: [],
    };
    const module = {
      module_id: "l2_moneyflow",
      title: "L2 大单资金流",
      kind: "table",
      status: "complete" as const,
      summary: null,
      content: null,
      metrics: [],
      items: [],
      table: null,
      warnings: [],
      provenance: { source: "duckdb" },
    };

    const replayed = upsertStructuredReportModule(
      upsertStructuredReportModule(report, module),
      { ...module, summary: "重放后更新" },
    );

    expect(replayed.modules).toHaveLength(1);
    expect(replayed.modules[0].summary).toBe("重放后更新");
  });

  it("does not let a late run response replace the current selection", async () => {
    const first = deferred<Run>();
    const second = deferred<Run>();
    const runA = {
      ...bundle.run,
      run_id: "run_a",
      question: "先打开的研究",
      artifacts: [],
    };
    const runB = {
      ...bundle.run,
      run_id: "run_b",
      question: "当前研究",
      artifacts: [],
    };
    apiMocks.getBootstrap.mockResolvedValue({
      ...bootstrap,
      recent_runs: [runA, runB],
    });
    apiMocks.getRun.mockImplementation((runId: string) =>
      runId === "run_a" ? first.promise : second.promise,
    );
    apiMocks.listArtifacts.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("button", { name: "新建研究" })).toHaveAttribute(
      "aria-label",
      "新建研究",
    );
    expect(screen.getByRole("button", { name: "研究首页" })).toHaveAttribute(
      "aria-label",
      "研究首页",
    );
    expect(screen.getByRole("button", { name: "产物库" })).toHaveAttribute(
      "aria-label",
      "产物库",
    );
    await user.click(await screen.findByRole("button", { name: /先打开的研究/ }));
    await user.click(screen.getByRole("button", { name: /当前研究/ }));
    await act(async () => second.resolve(runB));
    expect(await screen.findByRole("heading", { name: "当前研究" })).toBeVisible();
    expect(window.scrollTo).toHaveBeenLastCalledWith({
      top: 0,
      behavior: "auto",
    });

    await act(async () => first.resolve(runA));
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "先打开的研究" })).toBeNull();
      expect(screen.getByRole("heading", { name: "当前研究" })).toBeVisible();
    });
  });

  it("does not let a late artifact response replace the current selection", async () => {
    const first = deferred<ArtifactDescriptor>();
    const second = deferred<ArtifactDescriptor>();
    const artifactA: ArtifactDescriptor = {
      ...artifact,
      artifact_id: "briefing:a",
      title: "先打开的报告",
      category: "briefing",
      source_path: "reports/a.md",
      source_of_truth: "reports/a.md",
    };
    const artifactB: ArtifactDescriptor = {
      ...artifactA,
      artifact_id: "briefing:b",
      title: "当前报告",
      source_path: "reports/b.md",
      source_of_truth: "reports/b.md",
    };
    apiMocks.getBootstrap.mockResolvedValue(bootstrap);
    apiMocks.listArtifacts.mockResolvedValue([artifactA, artifactB]);
    apiMocks.getArtifact.mockImplementation((artifactId: string) =>
      artifactId === "briefing:a" ? first.promise : second.promise,
    );
    apiMocks.getArtifactText.mockImplementation((artifactId: string) =>
      Promise.resolve(artifactId === "briefing:a" ? "# 旧正文" : "# 当前正文"),
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "产物库" }));
    await user.click(await screen.findByRole("button", { name: /先打开的报告/ }));
    await user.click(screen.getByRole("button", { name: "产物库" }));
    await user.click(screen.getByRole("button", { name: /当前报告/ }));
    await act(async () => second.resolve(artifactB));
    expect(await screen.findByRole("heading", { name: "当前报告" })).toBeVisible();

    await act(async () => first.resolve(artifactA));
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "先打开的报告" })).toBeNull();
      expect(screen.getByRole("heading", { name: "当前报告" })).toBeVisible();
    });
  });

  it("upserts replayed trace steps by step_id", async () => {
    const replayed = {
      ...bundle.trace[0],
      output_summary: "重放后更新",
    };
    const trace = upsertTraceStep(
      upsertTraceStep([], bundle.trace[0]),
      replayed,
    );
    const user = userEvent.setup();
    render(
      <ResearchInspector
        bundle={{ ...bundle, trace }}
        artifact={null}
        open
        onClose={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("tab", { name: "运行" }));
    expect(screen.getAllByText("重放后更新")).toHaveLength(1);
  });
});
