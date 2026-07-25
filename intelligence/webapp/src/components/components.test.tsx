import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import {
  applyChatStreamEvent,
  createLiveMessageState,
  StreamEventDeduper,
} from "../streamEvents";
import {
  userFacingIssue,
  userFacingStage,
  userFacingText,
} from "../displayText";
import { upsertStructuredReportModule } from "../structuredReport";
import { upsertTraceStep } from "../trace";
import type {
  ArtifactDescriptor,
  Bootstrap,
  ChatMessage,
  Conversation,
  LLMConfig,
  PerspectiveDescription,
  ProductSkillDescription,
  Run,
  RunBundle,
  StreamEnvelope,
  WorkbenchOverview,
} from "../types";
import { ArtifactLibrary } from "./ArtifactLibrary";
import { ArtifactViewer } from "./ArtifactViewer";
import { Composer } from "./Composer";
import { ConversationList } from "./ConversationList";
import { MessageBubble } from "./MessageBubble";
import { MessageThread } from "./MessageThread";
import { PerspectivePicker } from "./PerspectivePicker";
import { ResearchHome } from "./ResearchHome";
import { ResearchInspector } from "./ResearchInspector";
import { RunView } from "./RunView";
import { SkillInvocation } from "./SkillInvocation";
import { SkillPicker } from "./SkillPicker";
import { StructuredReportView } from "./StructuredReportView";

const apiMocks = vi.hoisted(() => ({
  approveForecastReflection: vi.fn(),
  archiveConversation: vi.fn(),
  cancelRun: vi.fn(),
  configureLLM: vi.fn(),
  forgetSavedLLM: vi.fn(),
  createConversation: vi.fn(),
  createConversationMessage: vi.fn(),
  createRun: vi.fn(),
  getArtifact: vi.fn(),
  getArtifactProjection: vi.fn(),
  getArtifactText: vi.fn(),
  getBootstrap: vi.fn(),
  getConversationMessages: vi.fn(),
  getFollowups: vi.fn(),
  getLLMConfig: vi.fn(),
  getPerspectives: vi.fn(),
  getRun: vi.fn(),
  getRunArtifactText: vi.fn(),
  getRunContext: vi.fn(),
  getRunReport: vi.fn(),
  getTrace: vi.fn(),
  getWorkbenchOverview: vi.fn(),
  getSkills: vi.fn(),
  listArtifacts: vi.fn(),
  listConversations: vi.fn(),
  renameConversation: vi.fn(),
  rejectForecastReflection: vi.fn(),
  selectBuiltInLLM: vi.fn(),
  setForecastRuleStatus: vi.fn(),
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
  self_use_maturity: {
    distinct_trade_dates: 1,
    success_rate: 1,
    useful_rate: 1,
    manual_rescue_rate: 0,
    covered_workflows: ["daily_market"],
    blockers: ["minimum_trade_dates", "missing_workflows"],
    eligible_for_user_decision: false,
    passed: false,
  },
};

const workbenchOverview: WorkbenchOverview = {
  as_of_date: "2026-07-10",
  market: {
    trade_date: "2026-07-10",
    stage: "轮动",
    mainlines: ["半导体"],
    risks: ["板块明细未更新"],
    validation_points: ["验证成交额"],
  },
  themes: [],
  theme_axes: {
    knowledge: ["暗流", "观察", "萌芽", "第一轮", "催化共振", "一致认同"],
    market: ["未确认", "首次响应", "扩散", "主升", "分歧 / 兑现"],
  },
  signals: {
    new: [
      {
        bucket: "new",
        bucket_label: "新出现",
        title: "半导体",
        change: "首次进入观察",
        summary: "研究叙事等待验证",
        source_type: "晨汇 / 研究队列",
        source_date: "2026-07-01",
        impact: "半导体",
        market_confirmation: "等待同日盘面核对",
        next_validation: "补公司基础资料与官方披露",
      },
    ],
    strengthened: [],
    weakened: [],
    pending: [],
  },
  signal_date: "2026-07-01",
  winrate: [],
  forecast_performance: {
    sample_goal: 25,
    total_judged: 6,
    decision_eligible: false,
    rows: [
      {
        key: "codex/duckdb",
        agent: "codex",
        source: "duckdb",
        sample_count: 6,
        hits: 2,
        misses: 3,
        partial: 1,
        unverifiable: 0,
        hit_rate: 0.3333,
        weighted_rate: 0.4167,
        sample_goal: 25,
        decision_eligible: false,
      },
    ],
  },
  learning_feedback: {
    pending_reflections: [
      {
        reflection_file: "2026-07-01.reflection.codex.duckdb.json",
        date: "2026-07-01",
        agent: "codex",
        source: "duckdb",
        hypothesis_id: "direction:semi",
        category: "direction",
        failure_mode: "A5 场景错位",
        lesson: "轮动期先看方向相对强度。",
        rule: "方向排序前先横比。",
        status: "pending_review",
        approvable: true,
      },
    ],
    pending_rules: [
      {
        id: "rule-1",
        date: "2026-07-01",
        issue: "忽略横向比较",
        correction: "先横比",
        rule: "方向排序至少比较三个候选。",
        status: "pending",
      },
    ],
    approved_lesson_count: 2,
    approved_rule_count: 1,
  },
  sellside_flow: { priority: [], confirmation: [], caution: [] },
  sellside_date: null,
  moneyflow: {
    status: "missing",
    target_date: "2026-07-10",
    trade_date: null,
    coverage: {},
    leaders: [],
    quant_orders: [],
    warnings: ["暂无 L2 数据"],
    source: "local features",
  },
  moneyflow_trends: [],
  validation: { logic_effectiveness: {}, hypothesis_status: "等待同日知识事件" },
  data_status: [
    {
      key: "market",
      label: "市场总览",
      date: "2026-07-10",
      status: "complete",
      row_count: 1,
      message: "已更新",
    },
  ],
  agent_artifact: null,
};

const llmConfig: LLMConfig = {
  mode: "built_in",
  display_name: "Foresight 默认模型",
  ready: true,
  session_only: false,
  built_in_ready: true,
  provider: "zhipu",
  model: "glm-5.2",
  credential_persisted: false,
  saved_credential_available: false,
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
      label: "查看最强反证",
      full_prompt: "请列出哪些证据最容易证伪，并给出核验来源？",
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

const conversations: Conversation[] = [
  {
    conversation_id: "conv_recent",
    user_id: "default",
    title: "液冷跟踪",
    status: "active",
    created_at: "2026-07-10T10:00:00+08:00",
    updated_at: "2026-07-11T09:00:00+08:00",
    summary: "跟踪液冷证据",
    last_run_id: "run_demo",
  },
  {
    conversation_id: "conv_old",
    user_id: "default",
    title: "机器人",
    status: "active",
    created_at: "2026-07-09T10:00:00+08:00",
    updated_at: "2026-07-10T09:00:00+08:00",
    summary: "",
    last_run_id: null,
  },
];

const productSkills: ProductSkillDescription[] = [
  {
    skill_id: "daily-review",
    name: "每日复盘",
    description: "市场复盘",
    version: "1.0.0",
    triggers: ["复盘"],
    input_schema: { type: "object" },
    permissions: ["local_read"],
    timeout_seconds: 30,
  },
  {
    skill_id: "daily-agent",
    name: "Daily Agent",
    description: "研究雷达",
    version: "1.0.0",
    triggers: ["研究雷达"],
    input_schema: { type: "object" },
    permissions: ["local_read"],
    timeout_seconds: 30,
  },
];

const perspectives: PerspectiveDescription[] = [
  {
    perspective_id: "fengyuan94",
    display_name: "风远94",
    type: "blogger",
    article_count: 35,
    profile_confidence: "medium",
  },
  {
    perspective_id: "blogger_x",
    display_name: "其他博主",
    type: "blogger",
    article_count: 5,
    profile_confidence: "medium",
  },
];

const assistantMessage: ChatMessage = {
  message_id: "msg_assistant",
  conversation_id: "conv_recent",
  role: "assistant",
  content: "这是模板回答。",
  created_at: "2026-07-11T09:00:02+08:00",
  status: "completed",
  run_id: "run_demo",
  selected_skill_ids: ["daily-review"],
  perspective_mode: "neutral",
  selected_perspective_ids: [],
  invoked_skill_ids: ["daily-review", "daily-agent"],
  citations: [],
  degrades: ["llm_unavailable_template_answer"],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

interface MockEventSourceInstance {
  emit: (eventType: string, data: unknown) => void;
  fail: () => void;
  close: ReturnType<typeof vi.fn>;
}

let mockEventSources: MockEventSourceInstance[] = [];

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

    await user.click(screen.getByText("运行详情"));
    expect(screen.getByText(/本轮存在限制/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "查看最强反证" }));
    expect(onFollowup).toHaveBeenCalledWith(
      "请列出哪些证据最容易证伪，并给出核验来源？",
    );
  });

  it("translates internal failures and stages into user-facing language", () => {
    expect(userFacingIssue("llm_unavailable_template_answer")).toContain(
      "已保留可核验数据",
    );
    expect(
      userFacingIssue(
        'Traceback (most recent call last): File "ask.py", line 99',
      ),
    ).toBe(
      "研究过程中出现内部错误；相关结论可能不完整，已保留其他可用证据。",
    );
    expect(userFacingIssue("找不到 /Users/a77/scripts/rag_index.py")).toBe(
      "某项本地研究数据暂不可用；相关证据未纳入本轮结论。",
    );
    expect(
      userFacingIssue(
        "未找到 canonical Daily Review Markdown；日报基础模块缺失。",
      ),
    ).toBe(
      "最新日报基础文件暂不可用；本轮仅使用可用盘面数据和补充快照。",
    );
    expect(
      userFacingIssue(
        "未连接本地 DuckDB；本轮回退到 snapshot/export。",
      ),
    ).toBe("未连接本地市场数据；本轮回退到历史盘面快照。");
    expect(
      userFacingText(
        "[S1] 2026-07-01-theme-candidates.json · market_context",
      ),
    ).toBe("2026-07-01 题材候选快照 · 市场环境");
    expect(userFacingText("MarketAdapter.get_new_high_directions")).toBe(
      "本地盘面数据",
    );
    expect(userFacingStage("ask_current_turn")).toBe("检索本轮证据");
  });

  it("counts only evidence records bound to verifiable citations", () => {
    render(
      <ResearchInspector
        bootstrap={bootstrap}
        bundle={{
          ...bundle,
          context: {
            ...bundle.context,
            evidence: [
              ...bundle.context.evidence,
              {
                id: "citation-record:S1",
                label: "[S1] 盘面快照",
                kind: "citation_record",
                classification: "bound_evidence",
                detail: "hash=abc123",
                status: "hit",
              },
              {
                id: "citation:S",
                label: "盘面证据",
                kind: "citation",
                classification: "fact_or_context",
                detail: "1 条引用",
                status: "hit",
              },
            ],
          },
        }}
        artifact={null}
        open
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("当前任务摘要")).toHaveTextContent("证据1");
  });

  it("keeps structured modules behind the explicit run inspector", () => {
    const structuredBundle: RunBundle = {
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
    };
    render(
      <MessageBubble
        message={assistantMessage}
        skills={productSkills}
        live={null}
        bundle={structuredBundle}
        canRegenerate={false}
        onRegenerate={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(screen.getByText("这是模板回答。")).toBeVisible();
    expect(screen.getByText("运行详情")).toBeVisible();
    expect(screen.queryByText("glm · glm-5.2")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "LLM 综合判断" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "L2 大单资金流" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("深信服")).not.toBeInTheDocument();
    expect(
      screen.queryByText("L2 最新扫描日早于报告日。"),
    ).not.toBeInTheDocument();
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

  it("shows a readable artifact date and source before technical metadata", async () => {
    const user = userEvent.setup();
    render(
      <ArtifactViewer
        artifact={{
          ...artifact,
          date: "2026-07-10",
          source_label: "研究任务：复盘最新交易日",
          source_of_truth: "run:run_demo",
          related_run_id: "run_demo",
        }}
        content="# 研究结论"
        loading={false}
        contentUrl="/api/artifacts/demo/content"
        onBack={vi.fn()}
        onOpenRun={vi.fn()}
      />,
    );

    expect(screen.getByText("2026-07-10")).toBeVisible();
    expect(screen.getByText("研究任务：复盘最新交易日")).toBeVisible();
    expect(screen.getByText("run:run_demo")).not.toBeVisible();
    await user.click(screen.getByText("高级详情"));
    expect(screen.getByText("run:run_demo")).toBeVisible();
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

  it("keeps internal tool names out of the user-facing trace", async () => {
    const user = userEvent.setup();
    render(
      <ResearchInspector
        bootstrap={bootstrap}
        bundle={bundle}
        artifact={null}
        open
        onClose={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "运行" }));
    await user.click(screen.getByText("命中盘面与图谱"));
    expect(screen.queryByText("ask_retrieve_compose")).toBeNull();
    expect(screen.getAllByText("已完成")).not.toHaveLength(0);
  });

  it("shows the structured report inside the explicit run inspector", async () => {
    const user = userEvent.setup();
    render(
      <ResearchInspector
        bootstrap={bootstrap}
        bundle={{
          ...bundle,
          structuredReport: {
            schema_version: 1,
            report_id: "run_inspector_report",
            title: "运行报告",
            task_type: "ask",
            status: "completed",
            as_of: "2026-07-10",
            llm: { used: true, provider: "glm", model: "glm-5.2" },
            warnings: [],
            modules: [
              {
                module_id: "summary",
                title: "综合判断",
                kind: "narrative",
                status: "complete",
                summary: "证据边界内的结论。",
                content: null,
                metrics: [],
                items: [],
                table: null,
                warnings: [],
                provenance: { source: "retrieved_evidence" },
              },
            ],
          },
        }}
        artifact={null}
        open
        onClose={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("tab", { name: "运行" }));
    expect(screen.getByText("已使用 glm · glm-5.2")).toBeVisible();
    expect(screen.getByRole("heading", { name: "综合判断" })).toBeVisible();
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
        <ResearchInspector
          bootstrap={bootstrap}
          bundle={bundle}
          artifact={null}
          open
          onClose={vi.fn()}
        />
      </>,
    );

    expect(screen.getByText("本报告包含降级或质量警告")).toBeVisible();
    expect(
      screen.getByText("知识库索引已过期；相关证据仅供参考。"),
    ).toBeVisible();
    expect(screen.getByText("知识库索引快照")).toBeVisible();
    expect(screen.getByText(/版本=abc123/)).toBeVisible();
    expect(screen.getByText(/时效=当前/)).toBeVisible();
  });

  it("shows only allowlisted provider and model metadata", () => {
    render(
      <StructuredReportView
        report={{
          schema_version: 1,
          report_id: "run_safe_model",
          title: "模型元数据",
          task_type: "ask",
          status: "completed",
          as_of: "2026-07-10",
          llm: { used: true, provider: "GLM", model: "glm-5.2" },
          warnings: [],
          modules: [],
        }}
      />,
    );

    expect(screen.getByText("已使用 glm · glm-5.2")).toBeVisible();
  });

  it("hides credential-shaped provider and model metadata", () => {
    render(
      <StructuredReportView
        report={{
          schema_version: 1,
          report_id: "run_unsafe_model",
          title: "模型元数据",
          task_type: "ask",
          status: "completed",
          as_of: "2026-07-10",
          llm: {
            used: true,
            provider: "github_pat_private",
            model: "ghp_abcdefghijklmnopqrstuvwxyz",
          },
          warnings: [],
          modules: [],
        }}
      />,
    );

    expect(screen.getByText("已使用模型 · 服务信息已隐藏")).toBeVisible();
    expect(screen.queryByText(/github_pat_private/)).toBeNull();
    expect(screen.queryByText(/ghp_abcdefghijklmnopqrstuvwxyz/)).toBeNull();
  });

  it("shows aggregate self-use maturity without private event details", () => {
    render(
      <ResearchInspector
        bootstrap={bootstrap}
        bundle={null}
        artifact={null}
        open
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("自用成熟度预览（Demo 非计分）")).toBeVisible();
    fireEvent.click(screen.getByText("自用成熟度预览（Demo 非计分）"));
    expect(screen.getByText("Day 1 尚未开始，以下指标仅供产品打磨参考。")).toBeVisible();
    expect(screen.getByText("交易日 1/10 · 核心工作流 1/5")).toBeVisible();
    expect(screen.getByText("成功 100% · 有用 100% · 人工救场 0%")).toBeVisible();
    expect(screen.getByText("阻塞项 2")).toBeVisible();
    expect(screen.queryByText("可由用户最终裁决")).toBeNull();
    expect(screen.queryByText("private note")).toBeNull();
    expect(screen.queryByText("private-run-id")).toBeNull();
  });
  it("does not start final self-use judgement during the demo stage", () => {
    render(
      <ResearchInspector
        bootstrap={{
          ...bootstrap,
          self_use_maturity: {
            ...bootstrap.self_use_maturity,
            eligible_for_user_decision: true,
          },
        }}
        bundle={null}
        artifact={null}
        open
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText("可由用户最终裁决")).toBeNull();
    expect(screen.getByText("自用成熟度预览（Demo 非计分）")).toBeVisible();
  });

});

describe("Chat-first conversation components", () => {
  it("restores, switches and archives conversations in the mobile drawer", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onArchive = vi.fn();
    const onClose = vi.fn();
    render(
      <ConversationList
        conversations={conversations}
        activeConversationId="conv_recent"
        mobileOpen
        onSelect={onSelect}
        onNew={vi.fn()}
        onArchive={onArchive}
        onClose={onClose}
        onLibrary={vi.fn()}
        activeSection="ask"
        onSection={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("会话列表")).toHaveClass("open");
    await user.click(screen.getByRole("button", { name: /^机器人/ }));
    expect(onSelect).toHaveBeenCalledWith("conv_old");
    await user.click(screen.getByRole("button", { name: "归档机器人" }));
    expect(onArchive).toHaveBeenCalledWith("conv_old");
    await user.click(screen.getByRole("button", { name: "关闭会话列表" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("filters conversation history without changing the active conversation", async () => {
    const user = userEvent.setup();
    render(
      <ConversationList
        conversations={conversations}
        activeConversationId="conv_recent"
        mobileOpen={false}
        onSelect={vi.fn()}
        onNew={vi.fn()}
        onArchive={vi.fn()}
        onClose={vi.fn()}
        onLibrary={vi.fn()}
        activeSection="ask"
        onSection={vi.fn()}
      />,
    );

    await user.type(screen.getByRole("searchbox", { name: "搜索会话" }), "机器人");
    expect(screen.getByRole("button", { name: /^机器人/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: /^液冷跟踪/ })).toBeNull();
  });

  it("starts a guided research workflow from the empty conversation", async () => {
    const user = userEvent.setup();
    const onFollowup = vi.fn();
    const onStarter = vi.fn();
    render(
      <MessageThread
        messages={[]}
        skills={productSkills}
        liveMessages={{}}
        runBundles={{}}
        onRegenerate={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={onFollowup}
        onStarter={onStarter}
      />,
    );

    await user.click(screen.getByRole("button", { name: /今日复盘/ }));
    expect(onStarter).toHaveBeenCalledWith(
      "请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。",
    );
    expect(onFollowup).not.toHaveBeenCalled();
    expect(screen.getByText(/每轮新检索/)).toBeVisible();
  });

  it("selects and removes product skills while keeping hybrid as default", async () => {
    const user = userEvent.setup();
    const onSelectionChange = vi.fn();
    render(
      <SkillPicker
        skills={productSkills}
        mode="hybrid"
        selectedSkillIds={["daily-review"]}
        onModeChange={vi.fn()}
        onSelectionChange={onSelectionChange}
      />,
    );

    expect(screen.getByRole("button", { name: "选择研究工具" })).toBeVisible();
    expect(screen.getByText("每日复盘")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "选择研究工具" }));
    await user.click(screen.getByRole("checkbox", { name: /Daily Agent/ }));
    expect(onSelectionChange).toHaveBeenCalledWith([
      "daily-review",
      "daily-agent",
    ]);
    await user.click(screen.getByRole("button", { name: "移除 每日复盘" }));
    expect(onSelectionChange).toHaveBeenLastCalledWith([]);
  });

  it("switches from data neutral to a selected KOL perspective", async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();
    const onSelectionChange = vi.fn();
    render(
      <PerspectivePicker
        perspectives={perspectives}
        mode="neutral"
        selectedPerspectiveIds={[]}
        onModeChange={onModeChange}
        onSelectionChange={onSelectionChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "选择分析视角" }));
    await user.click(screen.getByRole("radio", { name: /指定 KOL/ }));
    expect(onModeChange).toHaveBeenCalledWith("single");
    expect(onSelectionChange).toHaveBeenCalledWith(["fengyuan94"]);
  });

  it("distinguishes manual skills from automatically invoked skills", () => {
    render(
      <SkillInvocation
        skills={productSkills}
        selectedSkillIds={["daily-review"]}
        invokedSkillIds={["daily-review", "daily-agent"]}
        statuses={{ "daily-review": "completed", "daily-agent": "running" }}
      />,
    );

    expect(screen.getByText("已指定工具 · 每日复盘")).toHaveAttribute(
      "title",
      "每日复盘 · 已完成",
    );
    expect(screen.getByText("已自动选择 · Daily Agent")).toHaveAttribute(
      "title",
      "Daily Agent · 研究中",
    );
    expect(screen.queryByText("daily_projection_modules")).toBeNull();
  });

  it("offers stop while a message is running", async () => {
    const user = userEvent.setup();
    const onStop = vi.fn();
    render(
      <Composer
        value="继续追问"
        taskType="ask"
        running
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        onStop={onStop}
      />,
    );

    await user.click(screen.getByRole("button", { name: "停止生成" }));
    expect(onStop).toHaveBeenCalled();
  });

  it("marks template answers and regenerates without hiding the old answer", async () => {
    const user = userEvent.setup();
    const onRegenerate = vi.fn();
    render(
      <MessageBubble
        message={assistantMessage}
        skills={productSkills}
        live={null}
        bundle={bundle}
        canRegenerate
        onRegenerate={onRegenerate}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(screen.getByText("这是模板回答。")).toBeVisible();
    expect(screen.getByText("自然语言综合暂时不可用")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "重新生成回答" }));
    expect(onRegenerate).toHaveBeenCalledWith(assistantMessage);
    expect(screen.getByText("这是模板回答。")).toBeVisible();
  });

  it.each(["ask", "research", "workflow"])(
    "warns when a completed %s answer has no verifiable evidence",
    (taskType) => {
      render(
        <MessageBubble
          message={{
            ...assistantMessage,
            content: "这是一个仍需核验的判断。",
            degrades: [],
          }}
          skills={productSkills}
          live={null}
          bundle={{
            ...bundle,
            context: {
              ...bundle.context,
              evidence: [],
            },
            structuredReport: {
              schema_version: 1,
              report_id: `run_${taskType}`,
              title: "公司研究",
              task_type: taskType,
              status: "completed",
              as_of: null,
              llm: { used: false, provider: null, model: null },
              modules: [],
              warnings: [],
            },
          }}
          canRegenerate={false}
          onRegenerate={vi.fn()}
          onOpenArtifact={vi.fn()}
          onFollowup={vi.fn()}
        />,
      );

      expect(
        screen.getByText(
          "本轮未形成可验证的公司级来源；公司判断均按待验证展示。",
        ),
      ).toBeVisible();
    },
  );

  it("does not show the company evidence warning for an index technical answer", () => {
    render(
      <MessageBubble
        message={{
          ...assistantMessage,
          content: "科创50支撑区为1662.65–1669.99。",
          degrades: [],
        }}
        skills={productSkills}
        live={null}
        bundle={{
          ...bundle,
          context: {
            ...bundle.context,
            evidence: [],
          },
          structuredReport: {
            schema_version: 1,
            report_id: "run_market_technical",
            title: "科创50技术位",
            task_type: "research",
            status: "completed",
            as_of: "2026-07-24",
            llm: { used: false, provider: null, model: null },
            modules: [],
            warnings: [],
            task_frame: {
              question_type: "market_technical",
              subject_kind: "index",
              evidence_policy: "structured_market_technical",
            },
          },
        }}
        canRegenerate={false}
        onRegenerate={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(
      screen.queryByText(
        "本轮未形成可验证的公司级来源；公司判断均按待验证展示。",
      ),
    ).toBeNull();
  });

  it.each([
    ["chat", "chat"],
    ["meta", "meta"],
    ["clarify", "clarify"],
    ["static knowledge", "knowledge"],
    ["fresh knowledge", "knowledge"],
  ])(
    "does not show the company evidence warning for %s answers",
    (_label, taskType) => {
      render(
        <MessageBubble
          message={{
            ...assistantMessage,
            content: "这是不需要公司级证据提示的回答。",
            degrades: [],
          }}
          skills={productSkills}
          live={null}
          bundle={{
            ...bundle,
            context: {
              ...bundle.context,
              evidence: [],
            },
            structuredReport: {
              schema_version: 1,
              report_id: `run_${taskType}`,
              title: "普通对话",
              task_type: taskType,
              status: "completed",
              as_of: null,
              llm: { used: false, provider: null, model: null },
              modules: [],
              warnings: [],
            },
          }}
          canRegenerate={false}
          onRegenerate={vi.fn()}
          onOpenArtifact={vi.fn()}
          onFollowup={vi.fn()}
        />,
      );

      expect(
        screen.queryByText(
          "本轮未形成可验证的公司级来源；公司判断均按待验证展示。",
        ),
      ).toBeNull();
    },
  );

  it("replaces loading with a persistent cancelled message", () => {
    render(
      <MessageBubble
        message={{
          ...assistantMessage,
          content: "",
          status: "cancelled",
          degrades: [],
        }}
        skills={productSkills}
        live={null}
        bundle={null}
        canRegenerate
        onRegenerate={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(
      screen.getByText("已停止生成，已保留已生成内容。"),
    ).toBeVisible();
    expect(screen.queryByText("正在检索本轮证据")).toBeNull();
  });

  it("applies identity-checked deltas, module upserts and replay deduplication", () => {
    const deduper = new StreamEventDeduper();
    const initial = createLiveMessageState({
      conversationId: "conv_recent",
      messageId: "msg_assistant",
      runId: "run_demo",
    });
    const envelope = (
      eventId: string,
      eventType: string,
      payload: Record<string, unknown>,
      conversationId = "conv_recent",
    ): StreamEnvelope => ({
      schema_version: 1,
      event_id: eventId,
      event_type: eventType,
      run_id: "run_demo",
      conversation_id: conversationId,
      message_id: "msg_assistant",
      seq: Number(eventId.replace(/\D/g, "")) || 1,
      created_at: "2026-07-11T09:00:00+08:00",
      payload,
    });
    const firstDelta = envelope("evt-1", "text.delta", { delta: "真实" });
    const withText = applyChatStreamEvent(initial, firstDelta, deduper);
    const duplicate = applyChatStreamEvent(withText, firstDelta, deduper);
    const staleConversation = applyChatStreamEvent(
      duplicate,
      envelope("evt-2", "text.delta", { delta: "旧会话" }, "conv_old"),
      deduper,
    );
    const module = {
      module_id: "daily_overview",
      title: "今日核心",
      kind: "summary",
      status: "complete",
      summary: "第一版",
      content: null,
      metrics: [],
      items: [],
      table: null,
      warnings: [],
      provenance: { source: "canonical" },
    };
    const withModule = applyChatStreamEvent(
      staleConversation,
      envelope("evt-3", "report.module", { module }),
      deduper,
    );
    const replayedModule = applyChatStreamEvent(
      withModule,
      envelope("evt-4", "report.module", {
        module: { ...module, summary: "重连更新" },
      }),
      deduper,
    );

    expect(withText.narrative).toBe("真实");
    expect(duplicate).toBe(withText);
    expect(staleConversation).toBe(withText);
    expect(replayedModule.report?.modules).toHaveLength(1);
    expect(replayedModule.report?.modules[0].summary).toBe("重连更新");
  });

  it("applies answer snapshots with monotonic overwrite semantics", () => {
    const initial = createLiveMessageState({
      conversationId: "conv_recent",
      messageId: "msg_assistant",
      runId: "run_demo",
    });
    const envelope = (
      eventId: string,
      eventType: string,
      payload: Record<string, unknown>,
    ): StreamEnvelope => ({
      schema_version: 1,
      event_id: eventId,
      event_type: eventType,
      run_id: "run_demo",
      conversation_id: "conv_recent",
      message_id: "msg_assistant",
      seq: Number(eventId.replace(/\D/g, "")) || 1,
      created_at: "2026-07-11T09:00:00+08:00",
      payload,
    });
    const draft = applyChatStreamEvent(
      initial,
      envelope("snapshot-1", "answer.snapshot", {
        revision: 1,
        phase: "verified_draft",
        text: "可核验草稿",
        final: false,
      }),
    );
    const ignoredDelta = applyChatStreamEvent(
      draft,
      envelope("delta-2", "text.delta", { delta: "旧增量" }),
    );
    const terminal = applyChatStreamEvent(
      ignoredDelta,
      envelope("snapshot-3", "answer.snapshot", {
        revision: 2,
        phase: "validated_synthesis",
        text: "自然语言精修版",
        final: true,
      }),
    );
    const replay = applyChatStreamEvent(
      terminal,
      envelope("snapshot-4", "answer.snapshot", {
        revision: 2,
        phase: "validated_synthesis",
        text: "自然语言精修版",
        final: true,
      }),
    );
    const conflict = applyChatStreamEvent(
      replay,
      envelope("snapshot-5", "answer.snapshot", {
        revision: 2,
        phase: "verified_fallback",
        text: "冲突版本",
        final: true,
      }),
    );
    const stale = applyChatStreamEvent(
      conflict,
      envelope("snapshot-6", "answer.snapshot", {
        revision: 1,
        phase: "verified_draft",
        text: "旧草稿",
        final: false,
      }),
    );
    const completed = applyChatStreamEvent(
      stale,
      envelope("complete-7", "message.complete", {
        message: { ...assistantMessage, content: "过期完成正文" },
      }),
    );
    const invalid = applyChatStreamEvent(
      completed,
      envelope("snapshot-8", "answer.snapshot", {
        revision: 3,
        phase: "unknown",
        text: "非法终态",
        final: true,
      }),
    );

    expect(draft).toMatchObject({
      narrative: "可核验草稿",
      answerRevision: 1,
      answerPhase: "verified_draft",
      answerFinal: false,
    });
    expect(ignoredDelta).toBe(draft);
    expect(terminal).toMatchObject({
      narrative: "自然语言精修版",
      answerRevision: 2,
      answerPhase: "validated_synthesis",
      answerFinal: true,
    });
    expect(replay).toBe(terminal);
    expect(conflict).toBe(terminal);
    expect(stale).toBe(terminal);
    expect(completed.narrative).toBe("自然语言精修版");
    expect(invalid).toBe(completed);
  });

  it.each([
    ["verified_draft", false, "可核验草稿 · 模型精修中"],
    ["validated_synthesis", true, "自然语言精修完成"],
    ["verified_fallback", true, "已保留可核验版本"],
    ["decision_brief_fallback", true, "已保留决策摘要"],
    ["evidence_gap_fallback", true, "证据不足，已如实说明"],
  ] as const)("shows the %s answer phase", (phase, final, label) => {
    render(
      <MessageBubble
        message={{ ...assistantMessage, degrades: [] }}
        skills={productSkills}
        live={{
          ...createLiveMessageState({
            conversationId: "conv_recent",
            messageId: "msg_assistant",
            runId: "run_demo",
          }),
          narrative: "阶段回答",
          answerRevision: phase === "verified_draft" ? 1 : 2,
          answerPhase: phase,
          answerFinal: final,
          status: final ? "completed" : "streaming",
        }}
        bundle={bundle}
        canRegenerate={false}
        onRegenerate={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(screen.getByText(label)).toBeVisible();
  });

  it("loads and displays the selected owner workflow", () => {
    const initial = createLiveMessageState({
      conversationId: "conv_recent",
      messageId: "msg_assistant",
      runId: "run_demo",
    });
    const loaded = applyChatStreamEvent(initial, {
      schema_version: 1,
      event_id: "workflow-loaded",
      event_type: "workflow.loaded",
      run_id: "run_demo",
      conversation_id: "conv_recent",
      message_id: "msg_assistant",
      seq: 1,
      created_at: "2026-07-15T09:00:00+08:00",
      payload: {
        owner: "theme-research",
        label: "题材研究",
        execution_mode: "inline",
        preset: "theme-research",
        required_skill_ids: ["theme-research"],
        retrieval_stages: [
          "definition",
          "chain_stages",
          "company_mapping",
          "market_lifecycle",
          "counterevidence",
        ],
        output_schema: "theme_research.v1",
        presentation_kind: "research_answer",
        max_wall_time_seconds: 90,
        status: "loaded",
      },
    });

    render(
      <MessageBubble
        message={assistantMessage}
        skills={productSkills}
        live={loaded}
        bundle={null}
        canRegenerate={false}
        onRegenerate={vi.fn()}
        onOpenArtifact={vi.fn()}
        onFollowup={vi.fn()}
      />,
    );

    expect(loaded.workflow).toMatchObject({
      owner: "theme-research",
      label: "题材研究",
      retrievalStages: [
        "definition",
        "chain_stages",
        "company_mapping",
        "market_lifecycle",
        "counterevidence",
      ],
    });
    expect(
      screen.getByText("工作流已加载 · 题材研究 · 5 个阶段"),
    ).toBeVisible();
  });

  it("tracks skill results and ends loading on complete or cancel", () => {
    const initial = createLiveMessageState({
      conversationId: "conv_recent",
      messageId: "msg_assistant",
      runId: "run_demo",
    });
    const makeEnvelope = (
      eventId: string,
      eventType: string,
      payload: Record<string, unknown>,
    ): StreamEnvelope => ({
      schema_version: 1,
      event_id: eventId,
      event_type: eventType,
      run_id: "run_demo",
      conversation_id: "conv_recent",
      message_id: "msg_assistant",
      seq: 1,
      created_at: "2026-07-11T09:00:00+08:00",
      payload,
    });
    const started = applyChatStreamEvent(
      initial,
      makeEnvelope("skill-start", "skill.start", {
        skill_id: "daily_review",
        selection_source: "rule",
        reason: "命中复盘规则",
      }),
    );
    const completed = applyChatStreamEvent(
      started,
      makeEnvelope("skill-result", "skill.result", {
        skill_id: "daily_review",
        status: "degraded",
        warnings: ["缺少最新日期"],
      }),
    );
    const messageComplete = applyChatStreamEvent(
      completed,
      makeEnvelope("message-complete", "message.complete", {
        message: { ...assistantMessage, content: "最终回答" },
      }),
    );
    const cancelled = applyChatStreamEvent(
      started,
      makeEnvelope("message-cancel", "message.error", {
        message: {
          ...assistantMessage,
          status: "cancelled",
          content: "已保留片段",
        },
      }),
    );

    expect(completed.skillInvocations.daily_review).toMatchObject({
      selection_source: "rule",
      status: "degraded",
      warnings: ["缺少最新日期"],
    });
    expect(messageComplete).toMatchObject({
      narrative: "最终回答",
      status: "completed",
    });
    expect(cancelled).toMatchObject({
      narrative: "已保留片段",
      status: "cancelled",
    });
  });
});

describe("Workbench navigation reliability", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockEventSources = [];
    class MockEventSource {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      private readonly listeners = new Map<string, EventListener>();

      constructor() {
        mockEventSources.push(this);
      }

      addEventListener = vi.fn(
        (eventType: string, listener: EventListenerOrEventListenerObject) => {
          if (typeof listener === "function") {
            this.listeners.set(eventType, listener);
          }
        },
      );
      close = vi.fn();

      emit = (eventType: string, data: unknown) => {
        this.listeners.get(eventType)?.(
          new MessageEvent(eventType, { data: JSON.stringify(data) }),
        );
      };
      fail = () => {
        this.onerror?.();
      };
    }
    vi.stubGlobal("EventSource", MockEventSource);
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
    apiMocks.getBootstrap.mockResolvedValue(bootstrap);
    apiMocks.getWorkbenchOverview.mockResolvedValue(workbenchOverview);
    apiMocks.approveForecastReflection.mockResolvedValue({
      ...workbenchOverview.learning_feedback,
      pending_reflections: [],
      approved_lesson_count: 3,
    });
    apiMocks.setForecastRuleStatus.mockResolvedValue({
      ...workbenchOverview.learning_feedback,
      pending_rules: [],
      approved_rule_count: 2,
    });
    apiMocks.rejectForecastReflection.mockResolvedValue({
      ...workbenchOverview.learning_feedback,
      pending_reflections: [],
    });
    apiMocks.listConversations.mockResolvedValue([]);
    apiMocks.getConversationMessages.mockResolvedValue([]);
    apiMocks.getSkills.mockResolvedValue(productSkills);
    apiMocks.getPerspectives.mockResolvedValue(perspectives);
    apiMocks.getFollowups.mockResolvedValue([]);
    apiMocks.getLLMConfig.mockResolvedValue(llmConfig);
    apiMocks.getRunContext.mockResolvedValue(bundle.context);
    apiMocks.getRunReport.mockResolvedValue(null);
    apiMocks.getTrace.mockResolvedValue([]);
    apiMocks.getRunArtifactText.mockResolvedValue(null);
    apiMocks.createConversationMessage.mockResolvedValue({
      conversation_id: "conv_recent",
      user_message_id: "msg_user_new",
      assistant_message_id: "msg_assistant_new",
      run_id: "run_created",
    });
    apiMocks.renameConversation.mockResolvedValue({
      ...conversations[0],
      title: "新的研究问题",
    });
    apiMocks.configureLLM.mockResolvedValue({
      ...llmConfig,
      mode: "byok",
      display_name: "自带密钥",
      session_only: true,
      provider: "deepseek",
      model: "deepseek-chat",
    });
    apiMocks.selectBuiltInLLM.mockResolvedValue(llmConfig);
    apiMocks.forgetSavedLLM.mockResolvedValue(llmConfig);
  });

  it("opens on today and navigates across the five product surfaces", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "轮动" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "主题" }));
    expect(
      await screen.findByRole("heading", { name: "知识共识 × 盘面确认" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "信号" }));
    expect(
      await screen.findByRole("heading", { name: "只推变化，不重复旧观点" }),
    ).toBeVisible();
    expect(screen.getByText("晨汇 / 研究队列")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "验证" }));
    expect(
      await screen.findByRole("heading", {
        name: "机构胜率、资金流与假设回检",
      }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Agent 方向命中率" })).toBeVisible();
    expect(screen.getByText("6/25")).toBeVisible();
    expect(screen.getByText("样本积累中")).toBeVisible();
    expect(screen.getByRole("heading", { name: "待确认的 Lesson 与硬规则" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "批准 Lesson" }));
    expect(apiMocks.approveForecastReflection).toHaveBeenCalledWith(
      "2026-07-01.reflection.codex.duckdb.json",
      ["direction:semi"],
    );
    await user.click(screen.getByRole("button", { name: "问答" }));
    expect(screen.getByLabelText("输入研究问题")).toBeVisible();
  });

  it("restores the latest conversation and submits in hybrid mode", async () => {
    apiMocks.listConversations.mockResolvedValue(conversations);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    expect(await screen.findByText("每轮重新检索当前证据")).toBeVisible();
    expect(screen.getByText("Demo · 非计分 · Day 1 未开始")).toBeVisible();
    await user.type(screen.getByLabelText("输入研究问题"), "新的研究问题");
    await user.click(screen.getByRole("button", { name: "发送研究问题" }));

    expect(apiMocks.createConversationMessage).toHaveBeenCalledWith(
      "conv_recent",
      {
        content: "新的研究问题",
        skill_mode: "hybrid",
        selected_skill_ids: [],
        perspective_mode: "neutral",
        selected_perspective_ids: [],
        user: "default",
      },
    );
  });

  it("submits an explicit KOL perspective without mixing other profiles", async () => {
    apiMocks.listConversations.mockResolvedValue(conversations);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await screen.findByText("每轮重新检索当前证据");
    await user.click(screen.getByRole("button", { name: "选择分析视角" }));
    await user.click(screen.getByRole("radio", { name: /指定 KOL/ }));
    await user.type(screen.getByLabelText("输入研究问题"), "按风远视角复盘");
    await user.click(screen.getByRole("button", { name: "发送研究问题" }));

    expect(apiMocks.createConversationMessage).toHaveBeenCalledWith(
      "conv_recent",
      expect.objectContaining({
        content: "按风远视角复盘",
        perspective_mode: "single",
        selected_perspective_ids: ["fengyuan94"],
      }),
    );
  });

  it("restores the perspective picker from the latest user message", async () => {
    apiMocks.listConversations.mockResolvedValue(conversations);
    apiMocks.getConversationMessages.mockResolvedValue([
      {
        ...assistantMessage,
        message_id: "msg_user",
        role: "user",
        content: "按风远视角复盘",
        perspective_mode: "single",
        selected_perspective_ids: ["fengyuan94"],
      },
      assistantMessage,
    ]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await screen.findByText("按风远视角复盘");
    expect(
      screen.getByRole("button", { name: "选择分析视角" }),
    ).toHaveTextContent("风远94");
  });

  it("regenerates with the original user message perspective", async () => {
    apiMocks.listConversations.mockResolvedValue(conversations);
    const originalUserMessage: ChatMessage = {
      ...assistantMessage,
      message_id: "msg_user",
      role: "user",
      content: "按风远视角复盘",
      perspective_mode: "single",
      selected_perspective_ids: ["fengyuan94"],
    };
    apiMocks.getConversationMessages.mockResolvedValue([
      originalUserMessage,
      assistantMessage,
    ]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await screen.findByText("这是模板回答。");
    await user.click(screen.getByRole("button", { name: "重新生成回答" }));

    expect(apiMocks.createConversationMessage).toHaveBeenCalledWith(
      "conv_recent",
      expect.objectContaining({
        content: "按风远视角复盘",
        perspective_mode: "single",
        selected_perspective_ids: ["fengyuan94"],
      }),
    );
  });

  it("recovers a persisted terminal run after the stream disconnects", async () => {
    const finalMessage: ChatMessage = {
      ...assistantMessage,
      message_id: "msg_assistant_new",
      content: "数据截至 2026-07-10。最终可读回答。",
      status: "completed",
      run_id: "run_created",
    };
    apiMocks.listConversations.mockResolvedValue(conversations);
    apiMocks.getConversationMessages
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          ...assistantMessage,
          message_id: "msg_user_new",
          role: "user",
          content: "请复盘最新交易日",
          status: "completed",
          run_id: "run_created",
        },
        finalMessage,
      ]);
    let runStatus: Run["status"] = "running";
    apiMocks.getRun.mockImplementation(async () => ({
      ...bundle.run,
      run_id: "run_created",
      status: runStatus,
      artifacts: [],
    }));
    apiMocks.listArtifacts.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await user.click(await screen.findByRole("button", { name: /今日复盘/ }));
    expect(apiMocks.createConversationMessage).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "发送研究问题" }));
    const events = mockEventSources.at(-1);
    expect(events).toBeDefined();

    await act(async () => {
      events?.emit("text.delta", {
        schema_version: 1,
        event_id: "text:1",
        event_type: "text.delta",
        run_id: "run_created",
        conversation_id: "conv_recent",
        message_id: "msg_assistant_new",
        seq: 1,
        created_at: "2026-07-11T09:00:00+08:00",
        payload: { delta: "cycle_status raw stream" },
      });
    });
    expect(screen.getByText("cycle_status raw stream")).toBeVisible();
    expect(
      screen.getByText("正在研究", { selector: ".agent-status" }),
    ).toBeVisible();

    await waitFor(() => expect(apiMocks.getRun).toHaveBeenCalled());
    runStatus = "completed";
    await act(async () => events?.fail());

    expect(
      await screen.findByText("数据截至 2026-07-10。最终可读回答。"),
    ).toBeVisible();
    expect(screen.queryByText("cycle_status raw stream")).toBeNull();
    expect(screen.getByText("空闲", { selector: ".agent-status" })).toBeVisible();
    expect(
      screen.getByText("已完成", {
        selector: ".assistant-message-header span",
      }),
    ).toBeVisible();
  });

  it("keeps cancel pending until polling confirms the cancelled state", async () => {
    const cancelledMessage: ChatMessage = {
      ...assistantMessage,
      message_id: "msg_assistant_new",
      content: "",
      status: "cancelled",
      run_id: "run_created",
    };
    apiMocks.listConversations.mockResolvedValue(conversations);
    apiMocks.getConversationMessages
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          ...assistantMessage,
          message_id: "msg_user_new",
          role: "user",
          content: "请复盘最新交易日",
          status: "completed",
          run_id: "run_created",
        },
        cancelledMessage,
      ]);
    let runStatus: Run["status"] = "running";
    apiMocks.getRun.mockImplementation(async () => ({
      ...bundle.run,
      run_id: "run_created",
      status: runStatus,
      artifacts: [],
    }));
    apiMocks.cancelRun.mockResolvedValue({
      ...bundle.run,
      run_id: "run_created",
      status: "running",
      artifacts: [],
    });
    apiMocks.listArtifacts.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await user.click(await screen.findByRole("button", { name: /今日复盘/ }));
    await user.click(screen.getByRole("button", { name: "发送研究问题" }));
    const events = mockEventSources.at(-1);
    expect(events).toBeDefined();

    await user.click(screen.getByRole("button", { name: "停止生成" }));
    expect(
      await screen.findByRole("button", { name: "停止请求已提交" }),
    ).toBeDisabled();

    await waitFor(() => expect(apiMocks.getRun).toHaveBeenCalled());
    runStatus = "cancelled";
    await act(async () => events?.fail());

    expect(
      await screen.findByText("已停止生成，已保留已生成内容。"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "停止请求已提交" })).toBeNull();
  });

  it("closes the event stream and polling timer when unmounted", async () => {
    apiMocks.listConversations.mockResolvedValue(conversations);
    apiMocks.getRun.mockResolvedValue({
      ...bundle.run,
      run_id: "run_created",
      status: "running",
      artifacts: [],
    });
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    const user = userEvent.setup();
    const view = render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await user.click(await screen.findByRole("button", { name: /今日复盘/ }));
    await user.click(screen.getByRole("button", { name: "发送研究问题" }));
    const events = mockEventSources.at(-1);
    expect(events).toBeDefined();

    view.unmount();

    expect(events?.close).toHaveBeenCalled();
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });

  it("configures session-only BYOK without exposing the key", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "配置模型" }));
    expect(screen.getByRole("dialog", { name: "模型连接" })).toBeVisible();
    await user.selectOptions(screen.getByLabelText("选择模型服务商"), "deepseek");
    expect(screen.getByLabelText("模型 Base URL")).toHaveValue(
      "https://api.deepseek.com/v1",
    );
    await user.type(screen.getByLabelText("模型 API Key"), "sk-private-test");
    await user.click(screen.getByRole("button", { name: "使用自带密钥" }));

    await waitFor(() => {
      expect(apiMocks.configureLLM).toHaveBeenCalledWith({
        provider: "deepseek",
        api_key: "sk-private-test",
        base_url: "https://api.deepseek.com/v1",
        model: "deepseek-chat",
        remember: false,
        user: "default",
      });
    });
    expect(screen.getByRole("button", { name: "配置模型" })).toHaveTextContent(
      "自带密钥",
    );
    expect(screen.queryByText("sk-private-test")).not.toBeInTheDocument();
  });

  it("persists BYOK only after opt-in and can explicitly forget it", async () => {
    apiMocks.getLLMConfig.mockResolvedValueOnce({
      ...llmConfig,
      mode: "byok",
      display_name: "已保存模型",
      session_only: false,
      provider: "openai",
      model: "gpt-5.6-sol",
      credential_persisted: true,
      saved_credential_available: true,
    });
    apiMocks.configureLLM.mockResolvedValueOnce({
      ...llmConfig,
      mode: "byok",
      display_name: "已保存模型",
      session_only: false,
      provider: "openai",
      model: "gpt-5.6-sol",
      credential_persisted: true,
      saved_credential_available: true,
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "配置模型" }));
    expect(screen.getByText("此 Mac 已保存一个模型连接。")).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: /在此 Mac 安全记住/ }));
    await user.type(screen.getByLabelText("模型 API Key"), "sk-private-test");
    await user.click(screen.getByRole("button", { name: "使用自带密钥" }));

    await waitFor(() => {
      expect(apiMocks.configureLLM).toHaveBeenCalledWith(
        expect.objectContaining({
          api_key: "sk-private-test",
          remember: true,
          user: "default",
        }),
      );
    });
    await user.click(screen.getByRole("button", { name: "删除已保存密钥" }));
    await waitFor(() => {
      expect(apiMocks.forgetSavedLLM).toHaveBeenCalledWith("default");
    });
    expect(screen.queryByText("sk-private-test")).not.toBeInTheDocument();
  });

  it("regenerates as a new message without replacing the old answer", async () => {
    apiMocks.listConversations.mockResolvedValue(conversations);
    apiMocks.getConversationMessages.mockResolvedValue([
      {
        ...assistantMessage,
        message_id: "msg_question",
        role: "user",
        content: "原问题",
        run_id: null,
      },
      {
        ...assistantMessage,
        message_id: "msg_old_answer",
        content: "原回答仍保留",
        run_id: null,
      },
    ]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "问答" }));
    await user.click(
      await screen.findByRole("button", { name: "重新生成回答" }),
    );

    expect(screen.getByText("原回答仍保留")).toBeVisible();
    expect(apiMocks.createConversationMessage).toHaveBeenCalledWith(
      "conv_recent",
      expect.objectContaining({
        content: "原问题",
        skill_mode: "hybrid",
      }),
    );
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

  it("does not let a late conversation response replace the current thread", async () => {
    const first = deferred<ChatMessage[]>();
    const second = deferred<ChatMessage[]>();
    apiMocks.listConversations.mockResolvedValue(conversations);
    apiMocks.getConversationMessages.mockImplementation(
      (conversationId: string) =>
        conversationId === "conv_recent" ? first.promise : second.promise,
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: /^机器人/ }),
    );
    await act(async () =>
      second.resolve([
        {
          ...assistantMessage,
          message_id: "current_message",
          conversation_id: "conv_old",
          role: "user",
          content: "当前会话内容",
          run_id: null,
        },
      ]),
    );
    expect(await screen.findByText("当前会话内容")).toBeVisible();

    await act(async () =>
      first.resolve([
        {
          ...assistantMessage,
          message_id: "stale_message",
          role: "user",
          content: "旧会话迟到内容",
          run_id: null,
        },
      ]),
    );
    await waitFor(() => {
      expect(screen.queryByText("旧会话迟到内容")).toBeNull();
      expect(screen.getByText("当前会话内容")).toBeVisible();
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
        bootstrap={bootstrap}
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
