import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type {
  ArtifactDescriptor,
  Bootstrap,
  RunBundle,
} from "../types";
import { ArtifactLibrary } from "./ArtifactLibrary";
import { ArtifactViewer } from "./ArtifactViewer";
import { ResearchHome } from "./ResearchHome";
import { ResearchInspector } from "./ResearchInspector";
import { RunView } from "./RunView";

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
      manifest_ref: null,
    },
  },
  answer: "# 结论\n证据仍需下一交易日确认。",
  registeredArtifacts: [{ ...artifact, related_run_id: "run_demo", source_path: "user:default/runs/run_demo/answer.md" }],
};

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
});
