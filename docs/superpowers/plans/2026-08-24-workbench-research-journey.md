# Workbench Research Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用现有 SSE Trace 与 RunBundle 真值，为 Workbench 增加四阶段研究旅程和终态研究收据，让用户在运行中看懂进度、完成后快速核对交付口径。

**Architecture:** 新建 `researchJourney.ts` 作为唯一语义归并点，把 Trace、answer phase 和 RunBundle 转成稳定视图模型；`ResearchJourney.tsx` 与 `ResearchReceipt.tsx` 只负责渲染。`MessageBubble.tsx` 负责在进行中旅程、终态收据和旧终态兜底之间选择，原始 Trace、warning、degrade、Artifact 与 followup 仍留在 `RunView`。

**Tech Stack:** React 19、TypeScript 5.8、Lucide React、原生 CSS、Vitest + Testing Library、Playwright。

---

## 文件结构与职责

| 文件 | 动作 | 单一职责 |
| --- | --- | --- |
| `intelligence/webapp/src/researchJourney.ts` | 新建 | Trace/answer phase/RunBundle 到旅程与收据视图模型的纯函数 |
| `intelligence/webapp/src/researchJourney.test.ts` | 新建 | 阶段映射、优先级、重放、未知步骤和收据口径 |
| `intelligence/webapp/src/components/ResearchJourney.tsx` | 新建 | 四阶段轨道、手机摘要、唯一 live region、重连提示 |
| `intelligence/webapp/src/components/ResearchReceipt.tsx` | 新建 | 引用数、截止日、产物、缺口与限制的终态索引 |
| `intelligence/webapp/src/components/researchJourney.css` | 新建 | 两个组件的局部样式、`<720px` 布局和 reduced-motion |
| `intelligence/webapp/src/App.tsx` | 修改 | 恢复/终态 bundle 安装确认、连接状态归属与顶栏非 live 状态 |
| `intelligence/webapp/src/components/MessageBubble.tsx` | 修改 | Journey / Receipt / 旧终态 Timeline 的安装与互斥规则 |
| `intelligence/webapp/src/components/MessageThread.tsx` | 修改 | 只把最新助手消息指定为 live-region owner |
| `intelligence/webapp/src/components/RunView.tsx` | 修改 | 保留终态审计 warning/degrade，并以非 live note 展示 |
| `intelligence/webapp/src/components/StructuredReportView.tsx` | 修改 | Inspector 内 warning/loading 保持可见但不参与 live 播报 |
| `intelligence/webapp/src/components/components.test.tsx` | 修改 | 用户可见状态、ARIA、安装顺序与旧详情保留 |
| `intelligence/webapp/e2e/workbench.spec.ts` | 修改 | 真 SSE 中的运行态、终态、三视口和原始详情对账 |

不修改 `types.ts`、`streamEvents.ts`、API、SSE schema、`package.json` 或后端文件。现有 `ProgressTimeline.tsx` 只保留为“已结束但 RunBundle 暂未加载”的审计兜底，不再承担运行中主视觉。

## Task 1：建立纯函数语义归并器

**Files:**

- Create: `intelligence/webapp/src/researchJourney.ts`
- Create: `intelligence/webapp/src/researchJourney.test.ts`

归并补充契约：去重后的唯一 step 按其最后一次 replay 输入位置排列；每个 completed/failed/skipped 仅关闭同一生命周期组内一个更早、未关闭的 running（已知步骤按阶段分组，未知步骤按原始 `name` 分组），但自身 replay 历史已有 running 的同 `step_id` 终态只闭合自身，绝不从摘要文本推断关联。收据的 `issueCount` / `issueLabels` 只从原始 `context.gaps` 经 `userFacingIssue`、trim、去空白和去重得出，UI 统一显示「N 项限制/缺口」。

- [ ] **Step 1：先写阶段与收据契约的失败测试**

创建 `intelligence/webapp/src/researchJourney.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import {
  buildResearchJourney,
  buildResearchReceipt,
  type ResearchPhaseId,
} from "./researchJourney";
import type {
  AnswerPhase,
  LiveMessageState,
  RunBundle,
  TraceStep,
} from "./types";

function traceStep(overrides: Partial<TraceStep> = {}): TraceStep {
  return {
    step_id: "step-1",
    name: "research",
    status: "running",
    started_at: "2026-08-24T10:00:00+08:00",
    finished_at: null,
    input_summary: "",
    output_summary: "正在核对研究资料。",
    warnings: [],
    ...overrides,
  };
}

function journey(
  progress: TraceStep[],
  answerPhase: AnswerPhase | null = null,
  terminalStatus: LiveMessageState["status"] = "streaming",
) {
  return buildResearchJourney({ progress, answerPhase, terminalStatus });
}

function runBundle(): RunBundle {
  return {
    run: {
      run_id: "run-receipt",
      user: "default",
      question: "液冷怎么看？",
      task_type: "research",
      status: "completed",
      schema_version: 1,
      session_id: null,
      parent_run_id: null,
      created_at: "2026-08-24T10:00:00+08:00",
      finished_at: "2026-08-24T10:01:00+08:00",
      source_date: "2026-08-21",
      duckdb_cutoff: "2026-08-20",
      kb_commit: null,
      kb_index_built_at: null,
      kb_index_freshness: null,
      manifest_ref: null,
      degrades: [
        "llm_unavailable_template_answer",
        "llm_unavailable_template_answer",
      ],
      error: null,
      artifacts: [
        {
          artifact_id: "answer",
          path: "answer.md",
          renderer: "markdown",
          title: "研究回答",
          sha256: "abc",
          bytes: 100,
          previewable: true,
          downloadable: true,
        },
      ],
    },
    trace: [],
    followups: [],
    context: {
      evidence: [
        {
          id: "bound-1",
          label: "公告一",
          kind: "source",
          classification: "bound_evidence",
          detail: "已绑定",
          status: "hit",
        },
        {
          id: "bound-2",
          label: "公告二",
          kind: "source",
          classification: "bound_evidence",
          detail: "已绑定",
          status: "hit",
        },
        {
          id: "candidate-1",
          label: "检索候选",
          kind: "source",
          classification: "fact_source",
          detail: "仅检索命中",
          status: "hit",
        },
      ],
      memory: [],
      review: [],
      gaps: ["缺少客户口径", "缺少下一交易日验证"],
      warnings: [],
      metadata: {
        source_date: "2026-08-19",
        duckdb_cutoff: "2026-08-18",
        kb_commit: null,
        kb_index_built_at: null,
        kb_index_freshness: null,
        manifest_ref: null,
      },
    },
    answer: "研究回答",
    structuredReport: null,
    registeredArtifacts: [],
  };
}

describe("buildResearchJourney", () => {
  it.each([
    ["understanding", "understand"],
    ["planning", "understand"],
    ["route_skills", "understand"],
    ["research", "research"],
    ["ask_current_turn", "research"],
    ["ask_retrieve_compose", "research"],
    ["repair", "verify"],
    ["verification", "verify"],
    ["finalizing", "conclude"],
    ["render_artifacts", "conclude"],
    ["foresight_followups", "conclude"],
  ] as const)("maps %s to %s", (name, phaseId) => {
    const model = journey([traceStep({ name })]);

    expect(
      model.phases.find((phase) => phase.id === phaseId)?.status,
    ).toBe("running");
    expect(model.currentPhaseIndex).toBe(
      model.phases.findIndex((phase) => phase.id === phaseId),
    );
  });

  it("upserts replayed step ids before reducing phase state", () => {
    const model = journey([
      traceStep({ step_id: "same", status: "running" }),
      traceStep({
        step_id: "same",
        status: "completed",
        finished_at: "2026-08-24T10:01:00+08:00",
        output_summary: "研究资料已核对。",
      }),
    ]);

    expect(model.phases[1].status).toBe("completed");
    expect(model.currentAction).toBe("研究资料已核对。");
  });

  it("does not backfill earlier phases when a later phase starts", () => {
    const model = journey([traceStep({ name: "verification" })]);

    expect(model.phases.map((phase) => phase.status)).toEqual([
      "waiting",
      "waiting",
      "running",
      "waiting",
    ]);
  });

  it("prioritizes a failed step over a newer running step", () => {
    const model = journey([
      traceStep({
        step_id: "failed",
        name: "planning",
        status: "failed",
        finished_at: "2026-08-24T10:00:30+08:00",
        output_summary: "研究计划未能完成。",
      }),
      traceStep({
        step_id: "running",
        name: "research",
        started_at: "2026-08-24T10:01:00+08:00",
        output_summary: "仍在检索。",
      }),
    ]);

    expect(model.phases[0].status).toBe("attention");
    expect(model.currentPhaseIndex).toBe(0);
    expect(model.currentAction).toBe("研究计划未能完成。");
  });

  it("uses input order when timestamps cannot be parsed", () => {
    const model = journey([
      traceStep({
        step_id: "failed-1",
        status: "failed",
        started_at: "invalid",
        finished_at: "invalid",
        output_summary: "第一次失败。",
      }),
      traceStep({
        step_id: "failed-2",
        status: "failed",
        started_at: "also-invalid",
        finished_at: "also-invalid",
        output_summary: "第二次失败。",
      }),
    ]);

    expect(model.currentAction).toBe("第二次失败。");
  });

  it("marks unobserved phases skipped only after a terminal event", () => {
    const model = journey(
      [
        traceStep({
          name: "planning",
          status: "completed",
          finished_at: "2026-08-24T10:00:10+08:00",
        }),
      ],
      null,
      "completed",
    );

    expect(model.phases.map((phase) => phase.status)).toEqual([
      "completed",
      "skipped",
      "skipped",
      "skipped",
    ]);
  });

  it("keeps an unknown running step out of the four phases", () => {
    const model = journey([
      traceStep({ name: "new_backend_stage", output_summary: "正在读取新来源。" }),
    ]);

    expect(model.phases.every((phase) => phase.status === "waiting")).toBe(
      true,
    );
    expect(model.currentPhaseIndex).toBeNull();
    expect(model.currentAction).toBe("正在读取新来源。");
  });

  it("uses a safe generic action for an unknown step without summaries", () => {
    const model = journey([
      traceStep({
        name: "new_backend_stage",
        input_summary: "",
        output_summary: "",
      }),
    ]);

    expect(model.currentAction).toBe("执行研究步骤");
  });

  it("does not attach an unknown failure to an unrelated known phase", () => {
    const model = journey([
      traceStep({
        step_id: "known-running",
        name: "research",
        status: "running",
        output_summary: "正在检索。",
      }),
      traceStep({
        step_id: "unknown-failed",
        name: "new_backend_stage",
        status: "failed",
        finished_at: "2026-08-24T10:01:00+08:00",
        output_summary: "新步骤执行失败。",
      }),
    ]);

    expect(model.phases[1].status).toBe("running");
    expect(model.currentPhaseIndex).toBeNull();
    expect(model.currentAction).toBe("新步骤执行失败。");
  });

  it.each([
    ["verified_draft", "running", "可核验草稿已形成，正在精修"],
    ["validated_synthesis", "completed", "自然语言精修完成"],
    ["verified_fallback", "completed", "已保留可核验版本"],
    ["decision_brief_fallback", "completed", "已保留决策摘要"],
    ["evidence_gap_fallback", "completed", "证据不足，已如实说明"],
  ] as const)(
    "maps answer phase %s to the conclusion phase",
    (answerPhase, expectedStatus, action) => {
      const model = journey([], answerPhase);

      expect(model.phases[3].status).toBe(expectedStatus);
      expect(model.currentPhaseIndex).toBe(3);
      expect(model.currentAction).toBe(action);
    },
  );

  it.each([
    ["running", "running"],
    ["failed", "attention"],
  ] as const)(
    "keeps explicit %s conclusion trace ahead of a final answer phase",
    (traceStatus, expectedStatus) => {
      const model = journey(
        [
          traceStep({
            name: "render_artifacts",
            status: traceStatus,
            output_summary: "正在收尾研究产物。",
          }),
        ],
        "validated_synthesis",
      );

      expect(model.phases[3].status).toBe(expectedStatus);
      expect(model.currentAction).toBe("正在收尾研究产物。");
    },
  );

  it("keeps completed work and marks the interrupted phase on cancellation", () => {
    const model = journey(
      [
        traceStep({
          step_id: "plan",
          name: "planning",
          status: "completed",
          finished_at: "2026-08-24T10:00:30+08:00",
        }),
        traceStep({
          step_id: "research",
          name: "research",
          status: "running",
          started_at: "2026-08-24T10:01:00+08:00",
        }),
      ],
      null,
      "cancelled",
    );

    expect(model.phases.map((phase) => phase.status)).toEqual([
      "completed",
      "attention",
      "skipped",
      "skipped",
    ]);
    expect(model.runLabel).toBe("已停止");
  });

  it("exposes stable phase ids", () => {
    expect(
      journey([]).phases.map((phase) => phase.id satisfies ResearchPhaseId),
    ).toEqual(["understand", "research", "verify", "conclude"]);
  });
});

describe("buildResearchReceipt", () => {
  it("counts only bound evidence and combines context issues", () => {
    const receipt = buildResearchReceipt(runBundle());

    expect(receipt).toMatchObject({
      evidenceCount: 2,
      cutoff: "2026-08-21",
      artifactCount: 1,
      issueCount: 2,
      runStatus: "completed",
    });
    expect(receipt.issueLabels).toEqual([
      "缺少客户口径",
      "缺少下一交易日验证",
    ]);
  });

  it("uses the documented cutoff fallback order", () => {
    const bundle = runBundle();
    bundle.run.source_date = null;
    bundle.run.duckdb_cutoff = null;

    expect(buildResearchReceipt(bundle).cutoff).toBe("2026-08-19");

    bundle.context.metadata.source_date = null;
    expect(buildResearchReceipt(bundle).cutoff).toBe("2026-08-18");

    bundle.context.metadata.duckdb_cutoff = null;
    expect(buildResearchReceipt(bundle).cutoff).toBeNull();
  });
});
```

- [ ] **Step 2：运行测试并确认因模块尚不存在而失败**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/researchJourney.test.ts
```

Expected: FAIL，错误包含 `Failed to resolve import "./researchJourney"`。

- [ ] **Step 3：实现最小且完整的语义归并器**

创建 `intelligence/webapp/src/researchJourney.ts`：

```ts
import { userFacingIssue, userFacingStage, userFacingText } from "./displayText";
import { deduplicateTrace } from "./trace";
import type {
  AnswerPhase,
  LiveMessageState,
  RunBundle,
  RunStatus,
  TraceStep,
} from "./types";

export type ResearchPhaseId =
  | "understand"
  | "research"
  | "verify"
  | "conclude";

export type ResearchPhaseStatus =
  | "waiting"
  | "running"
  | "completed"
  | "skipped"
  | "attention";

interface ResearchPhaseDefinition {
  id: ResearchPhaseId;
  label: string;
  names: readonly string[];
}

export interface ResearchJourneyPhase {
  id: ResearchPhaseId;
  label: string;
  status: ResearchPhaseStatus;
}

export interface ResearchJourneyModel {
  phases: ResearchJourneyPhase[];
  currentPhaseIndex: number | null;
  currentAction: string;
  runLabel: "正在研究" | "已完成" | "需要关注" | "已停止";
  hasObservedTrace: boolean;
}

export interface ResearchReceiptModel {
  evidenceCount: number;
  cutoff: string | null;
  artifactCount: number;
  issueCount: number;
  issueLabels: string[];
  runStatus: RunStatus;
}

interface BuildResearchJourneyInput {
  progress: TraceStep[];
  answerPhase: AnswerPhase | null;
  terminalStatus: LiveMessageState["status"];
}

export const RESEARCH_PHASES: readonly ResearchPhaseDefinition[] = [
  {
    id: "understand",
    label: "理解与计划",
    names: ["understanding", "planning", "route_skills"],
  },
  {
    id: "research",
    label: "查找证据",
    names: ["research", "ask_current_turn", "ask_retrieve_compose"],
  },
  {
    id: "verify",
    label: "交叉核验",
    names: ["repair", "verification"],
  },
  {
    id: "conclude",
    label: "形成结论",
    names: ["finalizing", "render_artifacts", "foresight_followups"],
  },
];

const answerPhaseActions: Record<AnswerPhase, string> = {
  verified_draft: "可核验草稿已形成，正在精修",
  validated_synthesis: "自然语言精修完成",
  verified_fallback: "已保留可核验版本",
  decision_brief_fallback: "已保留决策摘要",
  evidence_gap_fallback: "证据不足，已如实说明",
};

function phaseIndexFor(name: string): number | null {
  const index = RESEARCH_PHASES.findIndex((phase) => phase.names.includes(name));
  return index === -1 ? null : index;
}

function phaseStatus(
  steps: TraceStep[],
  terminalStatus: LiveMessageState["status"],
): ResearchPhaseStatus {
  if (steps.some((step) => step.status === "failed")) return "attention";
  if (steps.some((step) => step.status === "running")) {
    return terminalStatus === "failed" || terminalStatus === "cancelled"
      ? "attention"
      : "running";
  }
  if (steps.some((step) => step.status === "completed")) return "completed";
  if (steps.some((step) => step.status === "skipped")) return "skipped";
  return terminalStatus === "completed" ||
    terminalStatus === "failed" ||
    terminalStatus === "cancelled"
    ? "skipped"
    : "waiting";
}

function latestInputIndexes(progress: TraceStep[]): Map<string, number> {
  return progress.reduce((indexes, step, index) => {
    indexes.set(step.step_id, index);
    return indexes;
  }, new Map<string, number>());
}

function replayOrderedTrace(progress: TraceStep[]): TraceStep[] {
  const indexes = latestInputIndexes(progress);
  return [...deduplicateTrace(progress)].sort(
    (left, right) => (indexes.get(left.step_id) ?? -1) -
      (indexes.get(right.step_id) ?? -1),
  );
}

function terminalStepIdsWithPriorRunning(progress: TraceStep[]): Set<string> {
  const runningStepIds = new Set<string>();
  const replayClosedStepIds = new Set<string>();
  for (const step of progress) {
    if (step.status === "running") {
      runningStepIds.add(step.step_id);
    } else if (runningStepIds.has(step.step_id)) {
      replayClosedStepIds.add(step.step_id);
    }
  }
  return replayClosedStepIds;
}

function lifecycleGroup(step: TraceStep): string {
  const phaseIndex = phaseIndexFor(step.name);
  return phaseIndex === null ? `stage:${step.name}` : `phase:${phaseIndex}`;
}

function closeSupersededRunnings(
  trace: TraceStep[],
  replayClosedStepIds: Set<string>,
): TraceStep[] {
  const unmatchedRunnings = new Map<string, number[]>();
  const closedRunnings = new Set<number>();

  trace.forEach((step, index) => {
    const group = lifecycleGroup(step);
    if (step.status === "running") {
      unmatchedRunnings.set(group, [
        ...(unmatchedRunnings.get(group) ?? []),
        index,
      ]);
      return;
    }
    if (replayClosedStepIds.has(step.step_id)) return;
    const [runningIndex, ...remaining] = unmatchedRunnings.get(group) ?? [];
    if (runningIndex === undefined) return;
    closedRunnings.add(runningIndex);
    unmatchedRunnings.set(group, remaining);
  });

  return trace.filter((_, index) => !closedRunnings.has(index));
}

function parseTime(value: string | null): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function newestStep(
  steps: TraceStep[],
  timestamp: (step: TraceStep) => string | null,
): TraceStep | null {
  return steps.reduce<TraceStep | null>((selected, step) => {
    if (!selected) return step;
    const selectedTime = parseTime(timestamp(selected));
    const stepTime = parseTime(timestamp(step));
    if (selectedTime !== null && stepTime !== null) {
      return stepTime >= selectedTime ? step : selected;
    }
    return step;
  }, null);
}

function selectCurrentStep(steps: TraceStep[]): TraceStep | null {
  return (
    newestStep(
      steps.filter((step) => step.status === "failed"),
      (step) => step.finished_at ?? step.started_at,
    ) ??
    newestStep(
      steps.filter((step) => step.status === "running"),
      (step) => step.started_at,
    ) ??
    newestStep(
      steps.filter(
        (step) => step.status === "completed" || step.status === "skipped",
      ),
      (step) => step.finished_at ?? step.started_at,
    )
  );
}

function stepAction(step: TraceStep): string {
  const raw =
    step.output_summary || step.input_summary || userFacingStage(step.name);
  return userFacingText(raw) || "执行研究步骤";
}

function runLabel(
  status: LiveMessageState["status"],
): ResearchJourneyModel["runLabel"] {
  if (status === "completed") return "已完成";
  if (status === "failed") return "需要关注";
  if (status === "cancelled") return "已停止";
  return "正在研究";
}

export function buildResearchJourney({
  progress,
  answerPhase,
  terminalStatus,
}: BuildResearchJourneyInput): ResearchJourneyModel {
  const trace = replayOrderedTrace(progress);
  const steps = closeSupersededRunnings(
    trace,
    terminalStepIdsWithPriorRunning(progress),
  );
  const phaseSteps = RESEARCH_PHASES.map((_, index) =>
    steps.filter((step) => phaseIndexFor(step.name) === index),
  );
  const statuses = phaseSteps.map((items) => phaseStatus(items, terminalStatus));
  const explicitConclusionFailed = phaseSteps[3].some(
    (step) => step.status === "failed",
  );
  const explicitConclusionRunning = phaseSteps[3].some(
    (step) => step.status === "running",
  );

  if (
    answerPhase &&
    !explicitConclusionFailed &&
    !explicitConclusionRunning
  ) {
    statuses[3] = answerPhase === "verified_draft" ? "running" : "completed";
  }

  const selectedStep = selectCurrentStep(steps);
  const selectedPhaseIndex = selectedStep
    ? phaseIndexFor(selectedStep.name)
    : null;
  const explicitUrgentStep =
    selectedStep?.status === "failed" || selectedStep?.status === "running";
  let currentPhaseIndex =
    answerPhase && !explicitUrgentStep ? 3 : selectedPhaseIndex;
  if (currentPhaseIndex === null && !selectedStep) {
    const activeIndex = statuses.findIndex(
      (status) => status === "attention" || status === "running",
    );
    currentPhaseIndex = activeIndex === -1 ? null : activeIndex;
  }

  const currentAction =
    answerPhase && !explicitUrgentStep
      ? answerPhaseActions[answerPhase]
      : selectedStep
        ? stepAction(selectedStep)
        : terminalStatus === "failed"
          ? "研究未完成"
          : terminalStatus === "cancelled"
            ? "研究已停止"
            : terminalStatus === "completed"
              ? "研究已完成"
              : "正在启动研究";

  return {
    phases: RESEARCH_PHASES.map((phase, index) => ({
      id: phase.id,
      label: phase.label,
      status: statuses[index],
    })),
    currentPhaseIndex,
    currentAction,
    runLabel: runLabel(terminalStatus),
    hasObservedTrace: trace.length > 0,
  };
}

function firstRecordedDate(values: Array<string | null>): string | null {
  return values.find((value) => Boolean(value?.trim()))?.trim() ?? null;
}

export function buildResearchReceipt(
  bundle: RunBundle,
): ResearchReceiptModel {
  const issueLabels = [
    ...new Set(
      bundle.context.gaps
        .map((issue) => userFacingIssue(issue).trim())
        .filter((issue) => issue.length > 0),
    ),
  ];

  return {
    evidenceCount: bundle.context.evidence.filter(
      (item) => item.classification === "bound_evidence",
    ).length,
    cutoff: firstRecordedDate([
      bundle.run.source_date,
      bundle.run.duckdb_cutoff,
      bundle.context.metadata.source_date,
      bundle.context.metadata.duckdb_cutoff,
    ]),
    artifactCount: bundle.run.artifacts.length,
    issueCount: issueLabels.length,
    issueLabels,
    runStatus: bundle.run.status,
  };
}
```

- [ ] **Step 4：运行纯函数测试并确认通过**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/researchJourney.test.ts
```

Expected: PASS，`buildResearchJourney` 与 `buildResearchReceipt` 两组测试全绿。

- [ ] **Step 5：提交纯函数切片**

```bash
git add -- intelligence/webapp/src/researchJourney.ts intelligence/webapp/src/researchJourney.test.ts
git commit -m "feat: model workbench research journey" -- intelligence/webapp/src/researchJourney.ts intelligence/webapp/src/researchJourney.test.ts
```

## Task 2：实现可访问的 ResearchJourney 组件

**Files:**

- Create: `intelligence/webapp/src/components/ResearchJourney.tsx`
- Create: `intelligence/webapp/src/components/researchJourney.css`
- Modify: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1：写组件语义、唯一 live region 和重连的失败测试**

在 `components.test.tsx` 顶部导入 `within`、归并器和组件：

```ts
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { buildResearchJourney } from "../researchJourney";
import { ResearchJourney } from "./ResearchJourney";
```

在 `describe("Chat-first conversation components", ...)` 中加入：

```tsx
it("renders four truthful research phases with one polite live region", () => {
  const model = buildResearchJourney({
    progress: [
      {
        step_id: "research-running",
        name: "research",
        status: "running",
        started_at: "2026-08-24T10:00:00+08:00",
        finished_at: null,
        input_summary: "",
        output_summary: "正在核对公告、盘面与知识库。",
        warnings: [],
      },
    ],
    answerPhase: null,
    terminalStatus: "streaming",
  });

  render(<ResearchJourney model={model} connection="connected" />);

  const stageList = screen.getByRole("list", { name: "研究阶段" });
  expect(within(stageList).getAllByRole("listitem")).toHaveLength(4);
  expect(
    within(stageList).getByLabelText("查找证据，进行中"),
  ).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("阶段 2/4 · 查找证据")).toBeInTheDocument();

  const liveRegion = screen.getByRole("status");
  expect(liveRegion).toHaveAttribute("aria-live", "polite");
  expect(liveRegion).toHaveTextContent("正在核对公告、盘面与知识库。");
  expect(stageList).not.toHaveAttribute("aria-live");
});

it("preserves the current journey while the connection recovers", () => {
  const model = buildResearchJourney({
    progress: [],
    answerPhase: null,
    terminalStatus: "streaming",
  });

  render(<ResearchJourney model={model} connection="reconnecting" />);

  expect(screen.getByText("Foresight · 正在研究")).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent(
    "连接恢复中 · 正在启动研究",
  );
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
});

it("uses the compact journey treatment after draft text appears", () => {
  const model = buildResearchJourney({
    progress: [],
    answerPhase: "verified_draft",
    terminalStatus: "streaming",
  });

  render(
    <ResearchJourney model={model} connection="connected" compact />,
  );

  expect(screen.getByLabelText("研究进度")).toHaveClass("is-compact");
  expect(screen.getByText("阶段 4/4 · 形成结论")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "可核验草稿已形成，正在精修",
  );
});
```

- [ ] **Step 2：运行定向测试并确认组件尚不存在**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/components/components.test.tsx -t "research phases|connection recovers|compact journey"
```

Expected: FAIL，错误包含 `Failed to resolve import "./ResearchJourney"`。

- [ ] **Step 3：实现 ResearchJourney 组件**

创建 `intelligence/webapp/src/components/ResearchJourney.tsx`：

```tsx
import { AlertTriangle, Check, Circle, Minus } from "lucide-react";
import type {
  ResearchJourneyModel,
  ResearchPhaseStatus,
} from "../researchJourney";
import "./researchJourney.css";

interface ResearchJourneyProps {
  model: ResearchJourneyModel;
  connection: "connected" | "reconnecting";
  compact?: boolean;
}

const phaseStatusLabels: Record<ResearchPhaseStatus, string> = {
  waiting: "等待中",
  running: "进行中",
  completed: "已完成",
  skipped: "未执行",
  attention: "需要关注",
};

function PhaseIcon({ status }: { status: ResearchPhaseStatus }) {
  if (status === "completed") return <Check size={12} />;
  if (status === "attention") return <AlertTriangle size={12} />;
  if (status === "skipped") return <Minus size={12} />;
  return <Circle size={10} />;
}

export function ResearchJourney({
  model,
  connection,
  compact = false,
}: ResearchJourneyProps) {
  const currentPhase =
    model.currentPhaseIndex === null
      ? null
      : model.phases[model.currentPhaseIndex];
  const mobileSummary = currentPhase
    ? `阶段 ${model.currentPhaseIndex! + 1}/${model.phases.length} · ${currentPhase.label}`
    : "研究阶段更新中";
  const action =
    connection === "reconnecting"
      ? `连接恢复中 · ${model.currentAction}`
      : model.currentAction;

  return (
    <section
      className={`research-journey${compact ? " is-compact" : ""}`}
      aria-label="研究进度"
    >
      <div className="research-journey-heading">
        <span>Foresight · {model.runLabel}</span>
        <small>研究旅程</small>
      </div>

      <div className="research-journey-mobile-summary">{mobileSummary}</div>

      <ol className="research-journey-track" aria-label="研究阶段" role="list">
        {model.phases.map((phase, index) => {
          const current = index === model.currentPhaseIndex;
          const statusLabel = phaseStatusLabels[phase.status];
          return (
            <li
              key={phase.id}
              className={[
                "research-journey-phase",
                `is-${phase.status}`,
                current ? "is-current" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-current={current ? "step" : undefined}
              aria-label={`${phase.label}，${statusLabel}`}
            >
              <span className="research-journey-marker" aria-hidden="true">
                <PhaseIcon status={phase.status} />
              </span>
              <span className="research-journey-phase-copy">
                <strong>{phase.label}</strong>
                <small>{statusLabel}</small>
              </span>
            </li>
          );
        })}
      </ol>

      <div
        className={[
          "research-journey-action",
          connection === "reconnecting" ? "is-reconnecting" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {action}
      </div>
    </section>
  );
}
```

- [ ] **Step 4：实现桌面轨道、手机四段条和 reduced-motion 样式**

创建 `intelligence/webapp/src/components/researchJourney.css`：

```css
.research-journey,
.research-receipt {
  width: 100%;
  margin: 0 0 14px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.72);
}

.research-journey {
  display: grid;
  gap: 12px;
  padding: 13px 14px 12px;
}

.research-journey-heading,
.research-receipt-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.research-journey-heading > span,
.research-receipt-heading > span {
  color: var(--ink);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.015em;
}

.research-journey-heading small,
.research-receipt-heading small {
  color: var(--faint);
  font-size: 8px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.research-journey-mobile-summary {
  display: none;
}

.research-journey-track {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.research-journey-phase {
  position: relative;
  display: grid;
  min-width: 0;
  grid-template-columns: 20px minmax(0, 1fr);
  align-items: start;
  gap: 6px;
  color: var(--faint);
  transition:
    color 160ms ease,
    opacity 160ms ease;
}

.research-journey-phase:not(:last-child)::after {
  position: absolute;
  z-index: 0;
  top: 9px;
  right: 0;
  left: 20px;
  height: 1px;
  background: var(--line);
  content: "";
  transition: background-color 160ms ease;
}

.research-journey-marker {
  position: relative;
  z-index: 1;
  display: grid;
  width: 19px;
  height: 19px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--faint);
  background: var(--surface);
  transition:
    color 160ms ease,
    border-color 160ms ease,
    background-color 160ms ease;
}

.research-journey-phase-copy {
  position: relative;
  z-index: 1;
  display: grid;
  min-width: 0;
  gap: 2px;
  padding-right: 7px;
  background: linear-gradient(90deg, var(--surface) 72%, transparent);
}

.research-journey-phase-copy strong {
  overflow: hidden;
  font-size: 9px;
  font-weight: 560;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.research-journey-phase-copy small {
  font-size: 8px;
  font-weight: 450;
}

.research-journey-phase.is-completed {
  color: var(--muted);
}

.research-journey-phase.is-completed .research-journey-marker {
  border-color: #c8d5cd;
  color: #587563;
  background: #f3f7f4;
}

.research-journey-phase.is-completed:not(:last-child)::after {
  background: #c8d5cd;
}

.research-journey-phase.is-running,
.research-journey-phase.is-current {
  color: var(--ink);
}

.research-journey-phase.is-running .research-journey-marker {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.research-journey-phase.is-current.is-running
  .research-journey-marker::before {
  position: absolute;
  inset: -4px;
  border: 1px solid rgba(198, 95, 62, 0.32);
  border-radius: 50%;
  content: "";
  animation: research-journey-pulse 1.8s ease-out infinite;
}

.research-journey-phase.is-attention {
  color: var(--red);
}

.research-journey-phase.is-attention .research-journey-marker {
  border-color: #d9aaa5;
  color: var(--red);
  background: var(--red-soft);
}

.research-journey-phase.is-skipped {
  opacity: 0.62;
}

.research-journey-action {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.55;
}

.research-journey-action.is-reconnecting {
  color: var(--amber);
}

.research-journey.is-compact {
  grid-template-columns: minmax(250px, 0.95fr) minmax(180px, 1.05fr);
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
}

.research-journey.is-compact .research-journey-heading,
.research-journey.is-compact .research-journey-mobile-summary {
  display: none;
}

.research-journey.is-compact .research-journey-phase-copy small {
  display: none;
}

.research-journey.is-compact .research-journey-action {
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes research-journey-pulse {
  0% {
    opacity: 0.72;
    transform: scale(0.86);
  }
  70%,
  100% {
    opacity: 0;
    transform: scale(1.22);
  }
}

@media (max-width: 719px) {
  .research-journey {
    gap: 9px;
    padding: 12px;
  }

  .research-journey-mobile-summary {
    display: block;
    color: var(--ink);
    font-size: 10px;
    font-weight: 600;
  }

  .research-journey-track {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 4px;
  }

  .research-journey-phase {
    display: block;
    min-height: 4px;
    border-radius: 999px;
    background: var(--line);
  }

  .research-journey-phase.is-completed {
    background: #8ea397;
  }

  .research-journey-phase.is-running,
  .research-journey-phase.is-current {
    background: var(--accent);
  }

  .research-journey-phase.is-attention {
    background: var(--red);
  }

  .research-journey-phase.is-skipped {
    background: #d8d5cf;
  }

  .research-journey-marker,
  .research-journey-phase-copy,
  .research-journey-phase::after {
    display: none;
  }

  .research-journey.is-compact {
    grid-template-columns: 1fr;
    gap: 7px;
  }

  .research-journey.is-compact .research-journey-mobile-summary {
    display: block;
  }

  .research-journey.is-compact .research-journey-action {
    overflow: visible;
    text-align: left;
    white-space: normal;
  }
}

@media (prefers-reduced-motion: reduce) {
  .research-journey-phase.is-current.is-running
    .research-journey-marker::before {
    animation: none;
  }
}
```

- [ ] **Step 5：运行组件定向测试并确认通过**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/components/components.test.tsx -t "research phases|connection recovers|compact journey"
```

Expected: PASS，两条 ResearchJourney 测试全绿。

- [ ] **Step 6：提交 ResearchJourney 组件切片**

```bash
git add -- intelligence/webapp/src/components/ResearchJourney.tsx intelligence/webapp/src/components/researchJourney.css intelligence/webapp/src/components/components.test.tsx
git commit -m "feat: render workbench research journey" -- intelligence/webapp/src/components/ResearchJourney.tsx intelligence/webapp/src/components/researchJourney.css intelligence/webapp/src/components/components.test.tsx
```

## Task 3：实现 ResearchReceipt 组件

**Files:**

- Create: `intelligence/webapp/src/components/ResearchReceipt.tsx`
- Modify: `intelligence/webapp/src/components/researchJourney.css`
- Modify: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1：写收据口径与人话标签的失败测试**

在 `components.test.tsx` 导入组件和收据归并器：

```ts
import {
  buildResearchJourney,
  buildResearchReceipt,
} from "../researchJourney";
import { ResearchReceipt } from "./ResearchReceipt";
```

在 `describe("Chat-first conversation components", ...)` 中加入：

```tsx
it("renders a terminal research receipt from context issues", () => {
  const receiptBundle: RunBundle = {
    ...bundle,
    run: {
      ...bundle.run,
      source_date: null,
      duckdb_cutoff: null,
      degrades: ["llm_unavailable_template_answer"],
      artifacts: [...bundle.run.artifacts, { ...bundle.run.artifacts[0], artifact_id: "second" }],
    },
    context: {
      ...bundle.context,
      evidence: [
        ...bundle.context.evidence,
        {
          id: "bound",
          label: "公司公告",
          kind: "source",
          classification: "bound_evidence",
          detail: "已绑定到正文",
          status: "hit",
        },
      ],
      gaps: ["缺少客户口径"],
      metadata: {
        ...bundle.context.metadata,
        source_date: null,
        duckdb_cutoff: null,
      },
    },
  };

  render(<ResearchReceipt model={buildResearchReceipt(receiptBundle)} />);

  const receipt = screen.getByLabelText("研究收据");
  expect(receipt).toHaveTextContent("Foresight · 已完成");
  expect(receipt).toHaveTextContent("1 条可验证引用");
  expect(receipt).toHaveTextContent("数据日期未记录");
  expect(receipt).toHaveTextContent("2 个产物");
  expect(receipt).toHaveTextContent("1 项限制/缺口");
  expect(receipt).toHaveAttribute(
    "data-issue-summary",
    "缺少客户口径",
  );
});
```

- [ ] **Step 2：运行定向测试并确认组件尚不存在**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/components/components.test.tsx -t "terminal research receipt"
```

Expected: FAIL，错误包含 `Failed to resolve import "./ResearchReceipt"`。

- [ ] **Step 3：实现 ResearchReceipt 组件**

创建 `intelligence/webapp/src/components/ResearchReceipt.tsx`：

```tsx
import {
  AlertTriangle,
  CalendarDays,
  FileStack,
  Link2,
} from "lucide-react";
import type { ResearchReceiptModel } from "../researchJourney";
import type { RunStatus } from "../types";
import "./researchJourney.css";

interface ResearchReceiptProps {
  model: ResearchReceiptModel;
}

const runStatusLabels: Record<RunStatus, string> = {
  queued: "等待中",
  running: "正在研究",
  completed: "已完成",
  failed: "需要关注",
  cancelled: "已停止",
};

export function ResearchReceipt({ model }: ResearchReceiptProps) {
  return (
    <section
      className={`research-receipt is-${model.runStatus}`}
      aria-label="研究收据"
      data-issue-summary={model.issueLabels.join("；") || undefined}
    >
      <div className="research-receipt-heading">
        <span>Foresight · {runStatusLabels[model.runStatus]}</span>
        <small>研究收据</small>
      </div>
      <ul className="research-receipt-metrics">
        <li>
          <Link2 aria-hidden="true" size={13} />
          <span>{model.evidenceCount} 条可验证引用</span>
        </li>
        <li>
          <CalendarDays aria-hidden="true" size={13} />
          <span>
            {model.cutoff ? `数据截至 ${model.cutoff}` : "数据日期未记录"}
          </span>
        </li>
        <li>
          <FileStack aria-hidden="true" size={13} />
          <span>{model.artifactCount} 个产物</span>
        </li>
        <li title={model.issueLabels.join("；") || undefined}>
          <AlertTriangle aria-hidden="true" size={13} />
          <span>{model.issueCount} 项限制/缺口</span>
        </li>
      </ul>
    </section>
  );
}
```

- [ ] **Step 4：把收据样式追加到组件样式文件**

在 `researchJourney.css` 的第一个 reduced-motion 媒体查询之前加入：

```css
.research-receipt {
  display: grid;
  gap: 10px;
  padding: 12px 14px;
}

.research-receipt.is-failed,
.research-receipt.is-cancelled {
  border-color: #e2c6bd;
}

.research-receipt-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 15px;
  margin: 0;
  padding: 0;
  color: var(--muted);
  font-size: 9px;
  line-height: 1.45;
  list-style: none;
}

.research-receipt-metrics li {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
}

.research-receipt-metrics svg {
  flex: 0 0 auto;
  color: var(--faint);
}

.research-receipt-metrics span {
  overflow-wrap: anywhere;
}

@media (max-width: 719px) {
  .research-receipt {
    padding: 12px;
  }

  .research-receipt-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px 12px;
  }

  .research-receipt-metrics li:nth-child(2) {
    grid-column: 1 / -1;
    grid-row: 1;
  }
}

@media (max-width: 420px) {
  .research-receipt-metrics {
    grid-template-columns: 1fr;
  }

  .research-receipt-metrics li:nth-child(2) {
    grid-column: auto;
  }
}
```

- [ ] **Step 5：运行收据定向测试并确认通过**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/components/components.test.tsx -t "terminal research receipt"
```

Expected: PASS，收据五个口径与限制人话属性均匹配。

- [ ] **Step 6：提交 ResearchReceipt 组件切片**

```bash
git add -- intelligence/webapp/src/components/ResearchReceipt.tsx intelligence/webapp/src/components/researchJourney.css intelligence/webapp/src/components/components.test.tsx
git commit -m "feat: render workbench research receipt" -- intelligence/webapp/src/components/ResearchReceipt.tsx intelligence/webapp/src/components/researchJourney.css intelligence/webapp/src/components/components.test.tsx
```

## Task 4：在 MessageBubble 安装 Journey / Receipt / 旧兜底

**Files:**

- Modify: `intelligence/webapp/src/App.tsx`
- Modify: `intelligence/webapp/src/components/MessageBubble.tsx`
- Modify: `intelligence/webapp/src/components/MessageThread.tsx`
- Modify: `intelligence/webapp/src/components/ResearchJourney.tsx`
- Modify: `intelligence/webapp/src/components/RunView.tsx`
- Modify: `intelligence/webapp/src/components/StructuredReportView.tsx`
- Modify: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1：写安装互斥、完成收据和失败保真的失败测试**

在 `describe("Chat-first conversation components", ...)` 中加入：

```tsx
it("shows a static journey before the first trace arrives", () => {
  render(
    <MessageBubble
      message={{
        ...assistantMessage,
        content: "",
        status: "pending",
        degrades: [],
      }}
      skills={productSkills}
      live={createLiveMessageState({
        conversationId: "conv_recent",
        messageId: "msg_assistant",
        runId: "run_demo",
      })}
      bundle={null}
      canRegenerate={false}
      onRegenerate={vi.fn()}
      onOpenArtifact={vi.fn()}
      onFollowup={vi.fn()}
    />,
  );

  expect(screen.getByLabelText("研究进度")).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("正在启动研究");
  expect(screen.queryByText("正在检索本轮证据")).toBeNull();
});

it("replaces the live journey with a receipt when the terminal bundle is loaded", () => {
  render(
    <MessageBubble
      message={{
        ...assistantMessage,
        content: "最终回答",
        status: "completed",
        degrades: [],
      }}
      skills={productSkills}
      live={null}
      bundle={{
        ...bundle,
        context: {
          ...bundle.context,
          evidence: [
            ...bundle.context.evidence,
            {
              id: "bound",
              label: "公司公告",
              kind: "source",
              classification: "bound_evidence",
              detail: "已绑定",
              status: "hit",
            },
          ],
        },
      }}
      canRegenerate={false}
      onRegenerate={vi.fn()}
      onOpenArtifact={vi.fn()}
      onFollowup={vi.fn()}
    />,
  );

  expect(screen.queryByLabelText("研究进度")).toBeNull();
  expect(screen.getByLabelText("研究收据")).toBeVisible();
  expect(screen.getByText("最终回答")).toBeVisible();
  expect(screen.getByText("运行详情", { exact: true })).toBeVisible();
});

it("keeps failed live progress visible without pretending completion", () => {
  render(
    <MessageBubble
      message={{
        ...assistantMessage,
        content: "部分回答",
        status: "failed",
        degrades: [],
      }}
      skills={productSkills}
      live={{
        ...createLiveMessageState({
          conversationId: "conv_recent",
          messageId: "msg_assistant",
          runId: "run_demo",
        }),
        status: "failed",
        progress: [
          {
            step_id: "verification-failed",
            name: "verification",
            status: "failed",
            started_at: "2026-08-24T10:00:00+08:00",
            finished_at: "2026-08-24T10:00:10+08:00",
            input_summary: "",
            output_summary: "引用核验未完成。",
            warnings: [],
          },
        ],
      }}
      bundle={null}
      canRegenerate={false}
      onRegenerate={vi.fn()}
      onOpenArtifact={vi.fn()}
      onFollowup={vi.fn()}
    />,
  );

  expect(screen.getByLabelText("研究进度")).toBeVisible();
  expect(screen.getByLabelText("交叉核验，需要关注")).toHaveAttribute(
    "aria-current",
    "step",
  );
  expect(screen.getByLabelText("研究进度")).toHaveClass("is-compact");
  expect(screen.getByRole("status")).toHaveTextContent("引用核验未完成。");
  expect(screen.getByText("本轮生成失败，请重试。")).toBeVisible();
});
```

把既有 `shows every episode milestone, not only the newest one` 测试改名为 `condenses episode milestones into four truthful phases`，并把断言替换为：

```tsx
expect(screen.getByLabelText("研究进度")).toBeVisible();
expect(screen.getByLabelText("理解与计划，已完成")).toBeVisible();
expect(screen.getByLabelText("查找证据，进行中")).toHaveAttribute(
  "aria-current",
  "step",
);
expect(screen.getByRole("status")).toHaveTextContent("正在查主线结构。");
expect(screen.queryByText("已形成研究计划。")).toBeNull();
expect(screen.queryByText("正在查盘面快照。")).toBeNull();
```

保留既有 `keeps the timeline available after the answer lands` 测试：它锁定终态 bundle 尚未成功加载时 `ProgressTimeline` 的终态审计兜底。另加 App 恢复与竞态回归：pending assistant 即使已预取到 running bundle，或轮询已提前看到终态 Run，仍必须显示 Journey、保持 EventSource/轮询，不得显示错误、Receipt 或 RunView；只有下一次 reconciliation 同时读到终态持久化 assistant message 与终态 bundle 才完成互换。再锁定 reload 终态 bundle 失败可见、终态正文覆盖旧 live 草稿、failed/cancelled fallback 不显示假重连，且全局加载错误不抢占 Journey 的 live region。

- [ ] **Step 2：运行 Chat-first 测试并确认新安装规则失败**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/components/components.test.tsx -t "static journey|loaded|failed live progress|condenses episode"
```

Expected: FAIL，当前 `MessageBubble` 仍渲染旧 `ProgressTimeline`，且没有研究收据。

- [ ] **Step 3：实现 MessageBubble 的互斥安装规则**

在 `MessageBubble.tsx` 增加导入：

```tsx
import {
  buildResearchJourney,
  buildResearchReceipt,
} from "../researchJourney";
import { ResearchJourney } from "./ResearchJourney";
import { ResearchReceipt } from "./ResearchReceipt";
```

把 `terminalStatus` 和 `runInFlight` 的计算替换为收窄后的公开状态。先确认持久化 assistant message 已终态，再把 bundle 按 `completed | failed | cancelled` 收窄为 `terminalBundle`；`queued | running` bundle 或“Run 已终态但 message 仍 pending”都只是预取快照，不能触发终态 UI。所有 `useMemo` 必须在用户消息提前返回之前无条件调用：

```tsx
const persistedMessageTerminal = isTerminalMessageStatus(message.status);
const content = persistedMessageTerminal
  ? message.content
  : live?.narrative || message.content;
const terminalBundle = useMemo(
  () => persistedMessageTerminal && bundle && isTerminalBundle(bundle)
    ? bundle
    : null,
  [bundle, persistedMessageTerminal],
);
const researchStatus: LiveMessageState["status"] =
  terminalBundle?.run.status ??
  (persistedMessageTerminal
    ? publicMessageStatus(message.status)
    : live?.status ?? publicMessageStatus(message.status));
const terminalStatus = researchStatus;
const runInFlight =
  researchStatus === "pending" || researchStatus === "streaming";
```

在无条件 hook 区域建立视图模型：

```tsx
const showJourney =
  message.role !== "user" &&
  !terminalBundle &&
  (runInFlight ||
    ((researchStatus === "failed" || researchStatus === "cancelled") &&
      progressSteps.length > 0));
const showLegacyTerminalProgress =
  message.role !== "user" &&
  !terminalBundle &&
  researchStatus === "completed" &&
  progressSteps.length > 0;
const journeyModel = useMemo(
  () => showJourney
    ? buildResearchJourney({
        progress: progressSteps,
        answerPhase: live?.answerPhase ?? null,
        terminalStatus: researchStatus,
      })
    : null,
  [live?.answerPhase, progressSteps, researchStatus, showJourney],
);
const receiptModel = useMemo(
  () => terminalBundle ? buildResearchReceipt(terminalBundle) : null,
  [terminalBundle],
);
```

把旧的 `ProgressTimeline` 条件块：

```tsx
{progressSteps.length > 0 || runInFlight ? (
  <ProgressTimeline steps={progressSteps} active={runInFlight} />
) : null}
```

替换为：

```tsx
{journeyModel && (
  <ResearchJourney
    model={journeyModel}
    connection={runInFlight ? (live?.connection ?? "connected") : "connected"}
    compact={Boolean(content)}
  />
)}
{receiptModel && <ResearchReceipt model={receiptModel} />}
{showLegacyTerminalProgress && (
  <ProgressTimeline steps={progressSteps} active={false} />
)}
```

保持该块位于 `MarkdownView` 之前；保持 `terminalNotice`、`RunView`、followups 和 regenerate 的相对顺序不变。

`ResearchReceipt`、`RunView` 和公司证据 warning 只消费由“持久化 assistant message 已终态 + bundle 已终态”共同收窄出的 `terminalBundle`。失败/取消是主状态，必须覆盖 `answerPhase` 的交付版本标签。`MessageThread` 只把最新助手消息标为播报 owner：该消息的 Journey 才使用 `role=status`；历史 Journey 与 terminal notice 保持可见但使用 `role=note`。顶栏状态只做视觉文本，workflow / evidence warning、RunView 的终态 error/degrade，以及 Inspector 内 StructuredReport 的 warning/loading 都使用 `role=note`；StructuredReport wrapper 不设置 `aria-live`。retained failed/cancelled Journey 存在时，全局 bundle 错误也使用 `role=note`；无 Journey 时继续使用 `role=alert`。只有播报 owner 没有 Journey 时，它的终态 notice 才使用 `role=status`。

`loadConversationData()` 必须返回 `{ messages, appliedToCurrentConversation, appliedBundles, failedRunIds }`；后三者只对通过 conversation generation 检查并安装到当前会话的结果有效。`finalizeRun()` 收到轮询/SSE 的终态 Run 后，先重载会话并按 `message_id + run_id` 确认目标持久化 assistant message 也已终态；若仍 pending/streaming 或读取失败，保持 EventSource、轮询和 live 原状，由后续 reconciliation 重试，不显示错误。确认消息终态后才关闭 transport、写 live 终态；目标终态 bundle 出现于 `appliedBundles` 时清理 live，否则保留 progress/workflow，显示简短错误，让 Timeline / Journey 继续作为审计兜底。安装成功后无条件清理 stale live state，不再由 `answerPhase` 延长其生命周期。会话 restore 若 `failedRunIds` 命中持久化终态 assistant message，则显示可重试的最终结果加载错误；只命中 running/pending message 时保持安静。

`connection` 只表达 EventSource 链路：仅 `onerror` 写 `reconnecting`，`onopen` 写 `connected`。cancel 接口成功只写 `cancelRequested=true`；轮询失败、finalize 和 cancel 都不得伪造连接状态。Journey 只有在 `pending|streaming` 时消费 reconnecting；终态 retained fallback 固定按 connected 渲染，避免把已结束误报成「连接恢复中」。

- [ ] **Step 4：运行完整组件测试并修正任何旧断言冲突**

Run:

```bash
cd intelligence/webapp
pnpm exec vitest run src/components/components.test.tsx
```

Expected: PASS，`Chat-first conversation components`、导航可靠性和既有 Workbench 组件测试全部通过；终态无 terminal bundle 的 `研究过程（3 步）` 仍存在，running bundle 恢复仍显示 Journey。

- [ ] **Step 5：提交安装切片**

```bash
git add -- intelligence/webapp/src/App.tsx intelligence/webapp/src/components/MessageBubble.tsx intelligence/webapp/src/components/MessageThread.tsx intelligence/webapp/src/components/ResearchJourney.tsx intelligence/webapp/src/components/RunView.tsx intelligence/webapp/src/components/StructuredReportView.tsx intelligence/webapp/src/components/components.test.tsx
git commit -m "feat: install research journey in chat" -- intelligence/webapp/src/App.tsx intelligence/webapp/src/components/MessageBubble.tsx intelligence/webapp/src/components/MessageThread.tsx intelligence/webapp/src/components/ResearchJourney.tsx intelligence/webapp/src/components/RunView.tsx intelligence/webapp/src/components/StructuredReportView.tsx intelligence/webapp/src/components/components.test.tsx
```

## Task 5：用真消息流锁定三视口行为

**Files:**

- Modify: `intelligence/webapp/e2e/workbench.spec.ts`

- [ ] **Step 1：让真聊天 helper 同时核对运行态和终态**

在 `submitQuestion` 中，发送按钮点击之后、completed poll 之前加入：

```ts
await expect(page.getByLabel("研究进度").last()).toBeVisible({
  timeout: 5_000,
});
if ((page.viewportSize()?.width ?? 1_000) < 720) {
  await expect(
    page.locator(".research-journey-mobile-summary").last(),
  ).toBeVisible();
  await expect(
    page.locator(".research-journey-phase-copy:visible"),
  ).toHaveCount(0);
}
```

在 completed answer 数量与助手消息数量断言之后加入（此处必须同时确认终态 Run、终态持久化 assistant message 与终态 bundle，不得把 running bundle 或提前终态的 Run 当成收据）：

```ts
await expect(page.getByLabel("研究收据").last()).toBeVisible({
  timeout: 10_000,
});
await expect(page.getByLabel("研究进度")).toHaveCount(0);
```

在 `real chat persists three fresh turns...` 用例 reload 后的四条助手消息断言之后加入：

```ts
await expect(page.getByLabel("研究收据")).toHaveCount(4);
```

既有 `运行详情` 展开、`运行轨迹` heading、无横向溢出和 Composer 不遮挡断言全部保留。

- [ ] **Step 2：运行 desktop 项目并确认三类 UI 断言通过**

Run:

```bash
cd intelligence/webapp
WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python pnpm exec playwright test e2e/workbench.spec.ts --project=desktop
```

Expected: PASS；运行中出现 `研究进度`，完成后切换为 `研究收据`，`运行详情` 仍可展开。

- [ ] **Step 3：运行 tablet 与 mobile 项目**

Run:

```bash
cd intelligence/webapp
WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python pnpm exec playwright test e2e/workbench.spec.ts --project=tablet --project=mobile
```

Expected: PASS；1024px 与 390px 均无横向溢出，390px 只显示手机阶段摘要和四段条，不显示四个完整阶段标签。

- [ ] **Step 4：提交端到端契约**

```bash
git add -- intelligence/webapp/e2e/workbench.spec.ts
git commit -m "test: cover research journey across viewports" -- intelligence/webapp/e2e/workbench.spec.ts
```

## Task 6：全量门禁、浏览器人检与交付核对

**Files:**

- Verify only; no production file is added in this task.

- [ ] **Step 1：运行前端全量门禁**

Run:

```bash
cd intelligence/webapp
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Expected: 四条命令 exit code 都为 0；build 产物正常生成；`package.json` 无变更。

- [ ] **Step 2：运行仓库 Python 叶子门禁，排除共享契约回归**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
```

Expected: ruff 与 pytest exit code 都为 0。若出现与本分支无关的基线失败，保存完整命令、首个失败测试和当前 revision，不把红灯写成通过。

- [ ] **Step 3：在本地浏览器逐态检查**

使用本分支 Workbench，在 1440×900、1024×768、390×844 三个视口逐项核对：

1. pending 无 Trace：显示“正在启动研究”，不伪造已完成阶段。
2. running：只有当前阶段呼吸，最新动作可读，四阶段不横向溢出。
3. reconnecting：阶段不清空，只在动作行显示“连接恢复中”。
4. completed：收据位于回答正文之前，RunView 位于正文之后且可展开。
5. failed/cancelled：已完成阶段保留，当前阶段显示“需要关注”，终态通知仍在。
6. 开启系统减少动画：当前阶段不再循环呼吸，内容与布局不变。

Expected: 六项行为与设计规格一致；不切换或覆盖 8792 的现有运行时。

- [ ] **Step 4：核对 diff 边界与红线文件**

Run:

```bash
git diff --check gitea/main...HEAD
git diff --name-only gitea/main...HEAD
git diff --exit-code gitea/main...HEAD -- intelligence/webapp/package.json
git diff --name-only gitea/main...HEAD | rg -v '^(docs/superpowers/(specs|plans)/|intelligence/webapp/)'
git status --short
```

Expected:

- `git diff --check` exit code 为 0。
- `package.json` diff 为空。
- 边界过滤命令无输出。
- 工作树干净。
- 变更只包含规格、计划、前端模块、前端测试与 E2E。

- [ ] **Step 5：形成交付摘要，不合并 main、不切换生产运行时**

摘要必须列出：新增组件、数据口径、测试命令与结果、浏览器三视口结果、分支名、提交序列、仍存在的真实限制。随后 push 当前 `codex/feat-workbench-research-journey` 分支并创建 PR；PR 只请求用户复核，不自行合并。

## 需求到任务的对照

| 设计要求 | 实施位置 |
| --- | --- |
| 四阶段真实映射、未知步骤、重放、优先级 | Task 1 |
| answer phase 合成证据但显式 Trace 优先 | Task 1 |
| 终态 skipped、失败/取消保真 | Task 1、Task 4 |
| 唯一动态焦点、ARIA live、重连 | Task 2 |
| 部分草稿出现后收紧为紧凑旅程 | Task 2、Task 4 |
| `<720px` 阶段 n/4 + 四段条 | Task 2、Task 5 |
| bound evidence、截止日、产物、限制/缺口合并口径 | Task 1、Task 3 |
| Journey / Receipt / 旧终态 fallback 互斥 | Task 4 |
| 原始 Run Trace、warning、artifact、followup 保留 | Task 4、Task 5 |
| 无依赖、无 API/schema 改动 | Task 6 |
| 三视口、reduced-motion、无溢出 | Task 2、Task 5、Task 6 |
