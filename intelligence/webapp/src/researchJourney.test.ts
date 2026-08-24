import { describe, expect, it } from "vitest";

import {
  RESEARCH_PHASES,
  buildResearchJourney,
  buildResearchReceipt,
} from "./researchJourney";
import type { AnswerPhase, RunBundle, TraceStep } from "./types";

const step = (
  name: string,
  status: TraceStep["status"],
  overrides: Partial<TraceStep> = {},
): TraceStep => ({
  step_id: `${name}-${status}`,
  name,
  status,
  started_at: "2026-08-24T10:00:00Z",
  finished_at: status === "running" ? null : "2026-08-24T10:01:00Z",
  input_summary: "输入摘要",
  output_summary: "输出摘要",
  warnings: [],
  ...overrides,
});

const bundle = (overrides: Partial<RunBundle> = {}): RunBundle => ({
  run: {
    run_id: "run-1", user: "default", question: "问题", task_type: "ask",
    status: "completed", schema_version: 1, session_id: null, parent_run_id: null,
    created_at: "2026-08-24T10:00:00Z", finished_at: null,
    source_date: null, duckdb_cutoff: null, kb_commit: null,
    kb_index_built_at: null, kb_index_freshness: null, manifest_ref: null,
    degrades: [], error: null, artifacts: [],
  },
  trace: [], followups: [], answer: null, structuredReport: null, registeredArtifacts: [],
  context: {
    evidence: [], memory: [], review: [], gaps: [], warnings: [],
    metadata: { source_date: null, duckdb_cutoff: null, kb_commit: null, kb_index_built_at: null, kb_index_freshness: null, manifest_ref: null },
  },
  ...overrides,
});

describe("buildResearchJourney", () => {
  it("defines four stable phase ids", () => {
    expect(RESEARCH_PHASES.map((phase) => phase.id)).toEqual([
      "understand", "research", "verify", "conclude",
    ]);
  });

  it.each<[string, number]>([
    ["understanding", 0], ["planning", 0], ["route_skills", 0],
    ["research", 1], ["ask_current_turn", 1], ["ask_retrieve_compose", 1],
    ["repair", 2], ["verification", 2],
    ["finalizing", 3], ["render_artifacts", 3], ["foresight_followups", 3],
  ])("maps known stage %s to its only active phase", (name, expectedIndex) => {
    const result = buildResearchJourney({
      progress: [step(name, "running")], answerPhase: null, terminalStatus: "streaming",
    });
    expect(result.phases.map((phase) => phase.status)).toEqual(
      RESEARCH_PHASES.map((_, index) => index === expectedIndex ? "running" : "waiting"),
    );
    expect(result.currentPhaseIndex).toBe(expectedIndex);
  });

  it("replays updates by step_id before deriving phase status", () => {
    const running = step("research", "running", { step_id: "same", output_summary: "旧进度" });
    const completed = step("research", "completed", { step_id: "same", output_summary: "新进度" });
    const result = buildResearchJourney({ progress: [running, completed], answerPhase: null, terminalStatus: "streaming" });
    expect(result.phases[1].status).toBe("completed");
    expect(result.currentAction).toBe("新进度");
  });

  it("closes stale production milestones with different step ids", () => {
    const research = buildResearchJourney({
      progress: [
        step("research", "running", { step_id: "continuous:episode:10:tool_request", output_summary: "正在查资料" }),
        step("research", "completed", { step_id: "continuous:episode:11:tool_result", output_summary: "已取得资料", finished_at: "2026-08-24T10:02:00Z" }),
      ], answerPhase: null, terminalStatus: "streaming",
    });
    const conclude = buildResearchJourney({
      progress: [
        step("finalizing", "running", { step_id: "continuous:episode:20:finalization", output_summary: "正在组织回答" }),
        step("finalizing", "completed", { step_id: "continuous:episode:21:finish", output_summary: "最终核验完成", finished_at: "2026-08-24T10:02:00Z" }),
      ], answerPhase: "validated_synthesis", terminalStatus: "streaming",
    });
    expect(research.phases[1].status).toBe("completed");
    expect(research.currentAction).toBe("已取得资料");
    expect(conclude.phases[3].status).toBe("completed");
    expect(conclude.currentAction).toBe("自然语言精修完成");
  });

  it("does not mark an earlier phase complete merely because a later phase began", () => {
    const result = buildResearchJourney({ progress: [step("research", "running")], answerPhase: null, terminalStatus: "streaming" });
    expect(result.phases.map((phase) => phase.status)).toEqual(["waiting", "running", "waiting", "waiting"]);
  });

  it("selects a failed action before a newer running action", () => {
    const result = buildResearchJourney({
      progress: [step("research", "running", { started_at: "2026-08-24T12:00:00Z", output_summary: "仍在查找" }), step("planning", "failed", { finished_at: "2026-08-24T11:00:00Z", output_summary: "计划失败" })],
      answerPhase: null, terminalStatus: "streaming",
    });
    expect(result.currentAction).toBe("计划失败");
    expect(result.currentPhaseIndex).toBe(0);
  });

  it("uses later input order when action timestamps cannot be parsed", () => {
    const result = buildResearchJourney({
      progress: [step("planning", "running", { started_at: "nope", output_summary: "先出现" }), step("research", "running", { started_at: "also-nope", output_summary: "后出现" })],
      answerPhase: null, terminalStatus: "streaming",
    });
    expect(result.currentAction).toBe("后出现");
  });

  it("marks unseen phases skipped at a terminal state", () => {
    const result = buildResearchJourney({ progress: [step("understanding", "completed")], answerPhase: null, terminalStatus: "completed" });
    expect(result.phases.map((phase) => phase.status)).toEqual(["completed", "skipped", "skipped", "skipped"]);
  });

  it("keeps unknown trace actions visible without assigning them to a phase", () => {
    const result = buildResearchJourney({ progress: [step("new_backend_stage", "running", { output_summary: "后台正在处理" })], answerPhase: null, terminalStatus: "streaming" });
    expect(result.currentAction).toBe("后台正在处理");
    expect(result.currentPhaseIndex).toBeNull();
    expect(result.phases.every((phase) => phase.status === "waiting")).toBe(true);
  });

  it("uses a safe action label for an unknown stage with no summary", () => {
    const result = buildResearchJourney({ progress: [step("future_stage", "running", { input_summary: "", output_summary: "" })], answerPhase: null, terminalStatus: "streaming" });
    expect(result.currentAction).toBe("执行研究步骤");
  });

  it("does not attach an unknown failure to an otherwise known running phase", () => {
    const result = buildResearchJourney({ progress: [step("research", "running"), step("future_stage", "failed", { output_summary: "未知失败" })], answerPhase: null, terminalStatus: "failed" });
    expect(result.currentAction).toBe("未知失败");
    expect(result.currentPhaseIndex).toBeNull();
    expect(result.phases[1].status).toBe("attention");
  });

  it.each<[AnswerPhase, string, "running" | "completed"]>([
    ["verified_draft", "可核验草稿已形成，正在精修", "running"],
    ["validated_synthesis", "自然语言精修完成", "completed"],
    ["verified_fallback", "已保留可核验版本", "completed"],
    ["decision_brief_fallback", "已保留决策摘要", "completed"],
    ["evidence_gap_fallback", "证据不足，已如实说明", "completed"],
  ])("applies answer phase %s", (answerPhase, action, status) => {
    const result = buildResearchJourney({ progress: [], answerPhase, terminalStatus: "streaming" });
    expect(result.phases[3].status).toBe(status);
    expect(result.currentAction).toBe(action);
    expect(result.currentPhaseIndex).toBe(3);
  });

  it("lets explicit conclusion running or failure override answer-phase completion", () => {
    const running = buildResearchJourney({ progress: [step("finalizing", "running", { output_summary: "正在发布" })], answerPhase: "validated_synthesis", terminalStatus: "streaming" });
    const failed = buildResearchJourney({ progress: [step("finalizing", "failed", { output_summary: "发布失败" })], answerPhase: "validated_synthesis", terminalStatus: "failed" });
    expect(running.phases[3].status).toBe("running");
    expect(running.currentAction).toBe("正在发布");
    expect(failed.phases[3].status).toBe("attention");
    expect(failed.currentAction).toBe("发布失败");
  });

  it("keeps completed work and flags the interrupted phase on cancellation", () => {
    const result = buildResearchJourney({ progress: [step("understanding", "completed"), step("research", "running")], answerPhase: null, terminalStatus: "cancelled" });
    expect(result.phases.map((phase) => phase.status)).toEqual(["completed", "attention", "skipped", "skipped"]);
    expect(result.runLabel).toBe("已停止");
  });
});

describe("buildResearchReceipt", () => {
  it("counts bound evidence, selects the first nonblank cutoff, and humanizes unique degrades", () => {
    const result = buildResearchReceipt(bundle({
      run: { ...bundle().run, source_date: " ", duckdb_cutoff: "2026-08-23", artifacts: [{ artifact_id: "a", path: "a", renderer: "md", title: "A", sha256: "a", bytes: 1, previewable: true, downloadable: true }, { artifact_id: "b", path: "b", renderer: "md", title: "B", sha256: "b", bytes: 1, previewable: true, downloadable: true }], degrades: ["llm_unavailable_template_answer", "llm_unavailable_template_answer", "wiki-rag stale"] },
      context: { ...bundle().context, evidence: [
        { id: "1", label: "一", kind: "x", classification: "bound_evidence", detail: "", status: "ok" },
        { id: "2", label: "二", kind: "x", classification: "fact_source", detail: "", status: "ok" },
      ], gaps: ["gap-1", "gap-2"], metadata: { ...bundle().context.metadata, source_date: "2026-08-22" } },
    }));
    expect(result).toMatchObject({ evidenceCount: 1, cutoff: "2026-08-23", artifactCount: 2, gapCount: 2, degradeCount: 2, runStatus: "completed" });
    expect(result.degradeLabels).toEqual([
      "自然语言综合暂时不可用，已保留可核验数据与研究产物。",
      "知识库索引已过期；相关证据仅供参考。",
    ]);
  });

  it("counts only gaps independent from raw degrades and warnings", () => {
    const result = buildResearchReceipt(bundle({
      run: { ...bundle().run, degrades: ["llm_unavailable_template_answer"] },
      context: {
        ...bundle().context,
        warnings: ["  warning-1  "],
        gaps: ["llm_unavailable_template_answer", "warning-1", "independent-gap"],
      },
    }));
    expect(result.gapCount).toBe(1);
    expect(result.degradeCount).toBe(1);
  });

  it("falls back through metadata cutoff fields and then null", () => {
    const metadata = { ...bundle().context.metadata, source_date: " ", duckdb_cutoff: "2026-08-21" };
    expect(buildResearchReceipt(bundle({ context: { ...bundle().context, metadata } })).cutoff).toBe("2026-08-21");
    expect(buildResearchReceipt(bundle()).cutoff).toBeNull();
  });
});
