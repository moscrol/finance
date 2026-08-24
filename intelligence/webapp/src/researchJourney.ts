import { userFacingIssue, userFacingStage, userFacingText } from "./displayText";
import { deduplicateTrace } from "./trace";
import type {
  AnswerPhase,
  LiveMessageState,
  RunBundle,
  TraceStep,
} from "./types";

export type ResearchPhaseId = "understand" | "research" | "verify" | "conclude";
export type ResearchPhaseStatus =
  | "waiting"
  | "running"
  | "completed"
  | "skipped"
  | "attention";

export interface ResearchJourneyPhase {
  id: ResearchPhaseId;
  label: string;
  status: ResearchPhaseStatus;
}

export interface ResearchJourneyModel {
  phases: ResearchJourneyPhase[];
  currentPhaseIndex: number | null;
  currentAction: string;
  runLabel: string;
  hasObservedTrace: boolean;
}

export interface ResearchReceiptModel {
  evidenceCount: number;
  cutoff: string | null;
  artifactCount: number;
  gapCount: number;
  degradeCount: number;
  degradeLabels: string[];
  runStatus: RunBundle["run"]["status"];
}

export const RESEARCH_PHASES: ReadonlyArray<Omit<ResearchJourneyPhase, "status">> = [
  { id: "understand", label: "理解与计划" },
  { id: "research", label: "查找证据" },
  { id: "verify", label: "交叉核验" },
  { id: "conclude", label: "形成结论" },
];

const phaseByStage: Record<string, ResearchPhaseId> = {
  understanding: "understand",
  planning: "understand",
  route_skills: "understand",
  research: "research",
  ask_current_turn: "research",
  ask_retrieve_compose: "research",
  repair: "verify",
  verification: "verify",
  finalizing: "conclude",
  render_artifacts: "conclude",
  foresight_followups: "conclude",
};

const phaseIndex = (id: ResearchPhaseId): number =>
  RESEARCH_PHASES.findIndex((phase) => phase.id === id);

const terminal = (status: LiveMessageState["status"]): boolean =>
  status === "completed" || status === "failed" || status === "cancelled";

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
  return terminal(terminalStatus) ? "skipped" : "waiting";
}

function actionRank(status: TraceStep["status"]): number {
  if (status === "failed") return 3;
  if (status === "running") return 2;
  return 1;
}

function actionTime(step: TraceStep): string | null {
  if (step.status === "running") return step.started_at;
  return step.finished_at ?? step.started_at;
}

function parsedTime(value: string | null): number | null {
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function latestInputIndexes(progress: TraceStep[]): Map<string, number> {
  return progress.reduce((indexes, step, index) => {
    indexes.set(step.step_id, index);
    return indexes;
  }, new Map<string, number>());
}

function replayOrderedTrace(progress: TraceStep[]): {
  trace: TraceStep[];
  indexes: Map<string, number>;
} {
  const indexes = latestInputIndexes(progress);
  return {
    trace: [...deduplicateTrace(progress)].sort(
      (left, right) => (indexes.get(left.step_id) ?? -1) -
        (indexes.get(right.step_id) ?? -1),
    ),
    indexes,
  };
}

function isLater(
  candidate: TraceStep,
  candidateIndex: number,
  previous: TraceStep,
  previousIndex: number,
): boolean {
  const candidateTime = parsedTime(actionTime(candidate));
  const previousTime = parsedTime(actionTime(previous));
  if (candidateTime === null || previousTime === null) {
    return candidateIndex > previousIndex;
  }
  return candidateTime > previousTime ||
    (candidateTime === previousTime && candidateIndex > previousIndex);
}

function closeSupersededKnownRunnings(
  trace: TraceStep[],
  indexes: Map<string, number>,
): TraceStep[] {
  return trace.filter((step) => {
    const phase = phaseByStage[step.name];
    if (!phase || step.status !== "running") return true;
    const stepIndex = indexes.get(step.step_id) ?? -1;
    return !trace.some((candidate) =>
      phaseByStage[candidate.name] === phase &&
      candidate.status !== "running" &&
      isLater(
        candidate,
        indexes.get(candidate.step_id) ?? -1,
        step,
        stepIndex,
      ),
    );
  });
}

function newestAction(steps: TraceStep[]): TraceStep | null {
  return steps.reduce<TraceStep | null>((current, candidate) => {
    if (current === null) return candidate;
    const rankDifference = actionRank(candidate.status) - actionRank(current.status);
    if (rankDifference !== 0) return rankDifference > 0 ? candidate : current;

    const currentTime = parsedTime(actionTime(current));
    const candidateTime = parsedTime(actionTime(candidate));
    if (currentTime === null || candidateTime === null) return candidate;
    return candidateTime >= currentTime ? candidate : current;
  }, null);
}

function actionText(step: TraceStep): string {
  const summary = step.output_summary.trim() || step.input_summary.trim();
  return summary ? userFacingText(summary) : userFacingStage(step.name);
}

const answerPhaseAction: Record<AnswerPhase, { status: ResearchPhaseStatus; action: string }> = {
  verified_draft: { status: "running", action: "可核验草稿已形成，正在精修" },
  validated_synthesis: { status: "completed", action: "自然语言精修完成" },
  verified_fallback: { status: "completed", action: "已保留可核验版本" },
  decision_brief_fallback: { status: "completed", action: "已保留决策摘要" },
  evidence_gap_fallback: { status: "completed", action: "证据不足，已如实说明" },
};

function emptyAction(status: LiveMessageState["status"]): string {
  if (status === "streaming" || status === "pending") return "正在启动研究";
  if (status === "failed") return "研究未完成";
  if (status === "cancelled") return "研究已停止";
  return "研究已完成";
}

function runLabel(status: LiveMessageState["status"]): string {
  if (status === "pending" || status === "streaming") return "正在研究";
  if (status === "completed") return "已完成";
  if (status === "failed") return "需要关注";
  return "已停止";
}

export function buildResearchJourney({
  progress,
  answerPhase,
  terminalStatus,
}: {
  progress: TraceStep[];
  answerPhase: AnswerPhase | null;
  terminalStatus: LiveMessageState["status"];
}): ResearchJourneyModel {
  const { trace, indexes } = replayOrderedTrace(progress);
  const normalizedTrace = closeSupersededKnownRunnings(trace, indexes);
  const byPhase = new Map<ResearchPhaseId, TraceStep[]>();
  for (const step of normalizedTrace) {
    const phase = phaseByStage[step.name];
    if (!phase) continue;
    byPhase.set(phase, [...(byPhase.get(phase) ?? []), step]);
  }

  const phases = RESEARCH_PHASES.map((phase) => ({
    ...phase,
    status: phaseStatus(byPhase.get(phase.id) ?? [], terminalStatus),
  }));
  const conclusionSteps = byPhase.get("conclude") ?? [];
  const conclusionHasExplicitActiveState = conclusionSteps.some(
    (step) => step.status === "failed" || step.status === "running",
  );
  const answerUpdate = answerPhase && !conclusionHasExplicitActiveState
    ? answerPhaseAction[answerPhase]
    : null;
  if (answerUpdate) phases[3] = { ...phases[3], status: answerUpdate.status };

  const selected = newestAction(normalizedTrace);
  const selectedPhase = selected ? phaseByStage[selected.name] : undefined;
  const answerCanDescribeAction = answerUpdate !== null &&
    (selected === null || actionRank(selected.status) === 1);

  return {
    phases,
    currentPhaseIndex: answerCanDescribeAction
      ? phaseIndex("conclude")
      : selectedPhase
        ? phaseIndex(selectedPhase)
        : null,
    currentAction: answerCanDescribeAction
      ? answerUpdate.action
      : selected
        ? actionText(selected)
        : emptyAction(terminalStatus),
    runLabel: runLabel(terminalStatus),
    hasObservedTrace: trace.length > 0,
  };
}

function nonBlank(value: string | null): string | null {
  const trimmed = value?.trim();
  return trimmed || null;
}

export function buildResearchReceipt(bundle: RunBundle): ResearchReceiptModel {
  const cutoff = [
    bundle.run.source_date,
    bundle.run.duckdb_cutoff,
    bundle.context.metadata.source_date,
    bundle.context.metadata.duckdb_cutoff,
  ].map(nonBlank).find((value): value is string => value !== null) ?? null;
  const degradeLabels = [...new Set(bundle.run.degrades.map(userFacingIssue))];
  const nonGapIssues = new Set(
    [...bundle.run.degrades, ...bundle.context.warnings].map((item) => item.trim()),
  );

  return {
    evidenceCount: bundle.context.evidence.filter(
      (item) => item.classification === "bound_evidence",
    ).length,
    cutoff,
    artifactCount: bundle.run.artifacts.length,
    gapCount: bundle.context.gaps.filter(
      (gap) => !nonGapIssues.has(gap.trim()),
    ).length,
    degradeCount: degradeLabels.length,
    degradeLabels,
    runStatus: bundle.run.status,
  };
}
