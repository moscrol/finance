import { upsertStructuredReportModule } from "./structuredReport";
import type {
  AnswerPhase,
  ChatMessage,
  LiveMessageState,
  LiveSkillInvocation,
  LiveWorkflow,
  StreamEnvelope,
  StructuredReport,
  StructuredReportModule,
} from "./types";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function parseStreamEnvelope<TPayload extends Record<string, unknown> = Record<string, unknown>>(
  value: unknown,
  payloadValidator?: (payload: Record<string, unknown>) => payload is TPayload,
): StreamEnvelope<TPayload> | null {
  if (!isRecord(value) || !isRecord(value.payload)) return null;
  if (
    value.schema_version !== 1 ||
    typeof value.event_id !== "string" || value.event_id.length === 0 ||
    typeof value.event_type !== "string" || value.event_type.length === 0 ||
    typeof value.run_id !== "string" || value.run_id.length === 0 ||
    !(typeof value.conversation_id === "string" || value.conversation_id === null) ||
    !(typeof value.message_id === "string" || value.message_id === null) ||
    typeof value.seq !== "number" || !Number.isSafeInteger(value.seq) || value.seq < 1 ||
    typeof value.created_at !== "string" || value.created_at.length === 0 ||
    (payloadValidator !== undefined && !payloadValidator(value.payload))
  ) return null;
  return value as unknown as StreamEnvelope<TPayload>;
}

export function parseStreamEnvelopeJson(text: string): StreamEnvelope | null {
  try {
    return parseStreamEnvelope(JSON.parse(text) as unknown);
  } catch {
    return null;
  }
}

export class StreamEventDeduper {
  private readonly seen = new Set<string>();

  accept(event: Pick<StreamEnvelope, "event_id">): boolean {
    if (this.seen.has(event.event_id)) return false;
    this.seen.add(event.event_id);
    return true;
  }

  clear(): void {
    this.seen.clear();
  }
}

export function createLiveMessageState(identity: {
  conversationId: string;
  messageId: string;
  runId: string;
}): LiveMessageState {
  return {
    ...identity,
    narrative: "",
    answerRevision: 0,
    answerPhase: null,
    answerFinal: false,
    report: null,
    workflow: null,
    skillInvocations: {},
    status: "pending",
    connection: "connected",
    cancelRequested: false,
  };
}

const isStructuredReport = (value: unknown): value is StructuredReport =>
  isRecord(value) &&
  typeof value.report_id === "string" &&
  Array.isArray(value.modules);

const isStructuredReportModule = (
  value: unknown,
): value is StructuredReportModule =>
  isRecord(value) &&
  typeof value.module_id === "string" &&
  typeof value.title === "string" &&
  Array.isArray(value.metrics) &&
  Array.isArray(value.items) &&
  Array.isArray(value.warnings);

const isChatMessage = (value: unknown): value is ChatMessage =>
  isRecord(value) &&
  typeof value.message_id === "string" &&
  typeof value.content === "string";

const answerPhases = new Set<AnswerPhase>([
  "verified_draft",
  "validated_synthesis",
  "verified_fallback",
]);

const isAnswerPhase = (value: unknown): value is AnswerPhase =>
  typeof value === "string" && answerPhases.has(value as AnswerPhase);

function emptyReport(runId: string): StructuredReport {
  return {
    schema_version: 1,
    report_id: runId,
    title: "研究回答",
    task_type: "ask",
    status: "streaming",
    as_of: null,
    llm: { used: false, provider: null, model: null },
    modules: [],
    warnings: [],
  };
}

function selectionSource(
  value: unknown,
): LiveSkillInvocation["selection_source"] {
  return value === "manual" || value === "rule" || value === "llm"
    ? value
    : "unknown";
}

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) &&
  value.every((item): item is string => typeof item === "string");

function liveWorkflow(
  payload: Record<string, unknown>,
): LiveWorkflow | null {
  const executionMode = payload.execution_mode;
  if (
    typeof payload.owner !== "string" ||
    typeof payload.label !== "string" ||
    (executionMode !== "inline" && executionMode !== "subtask") ||
    typeof payload.preset !== "string" ||
    !isStringArray(payload.required_skill_ids) ||
    !isStringArray(payload.retrieval_stages) ||
    typeof payload.output_schema !== "string" ||
    typeof payload.presentation_kind !== "string" ||
    typeof payload.max_wall_time_seconds !== "number" ||
    !Number.isSafeInteger(payload.max_wall_time_seconds) ||
    payload.max_wall_time_seconds < 1 ||
    payload.status !== "loaded"
  ) {
    return null;
  }
  return {
    owner: payload.owner,
    label: payload.label,
    executionMode,
    preset: payload.preset,
    requiredSkillIds: payload.required_skill_ids,
    retrievalStages: payload.retrieval_stages,
    outputSchema: payload.output_schema,
    presentationKind: payload.presentation_kind,
    maxWallTimeSeconds: payload.max_wall_time_seconds,
    status: "loaded",
  };
}

export function applyChatStreamEvent(
  state: LiveMessageState,
  event: StreamEnvelope,
  deduper?: StreamEventDeduper,
): LiveMessageState {
  if (
    event.conversation_id !== state.conversationId ||
    event.message_id !== state.messageId ||
    event.run_id !== state.runId
  ) {
    return state;
  }
  if (deduper && !deduper.accept(event)) return state;

  const payload = event.payload;
  if (event.event_type === "text.delta") {
    if (state.answerRevision > 0) return state;
    const delta = typeof payload.delta === "string" ? payload.delta : "";
    return {
      ...state,
      narrative: `${state.narrative}${delta}`,
      status: "streaming",
    };
  }
  if (event.event_type === "answer.snapshot") {
    const revision = payload.revision;
    const phase = payload.phase;
    const text = payload.text;
    const final = payload.final;
    if (
      typeof revision !== "number" ||
      !Number.isSafeInteger(revision) ||
      revision < 1 ||
      !isAnswerPhase(phase) ||
      typeof text !== "string" ||
      text.trim().length === 0 ||
      typeof final !== "boolean" ||
      (phase === "verified_draft" && final) ||
      (phase !== "verified_draft" && !final)
    ) {
      return state;
    }
    if (revision < state.answerRevision) return state;
    if (revision === state.answerRevision) return state;
    return {
      ...state,
      narrative: text,
      answerRevision: revision,
      answerPhase: phase,
      answerFinal: final,
      status: "streaming",
    };
  }
  if (event.event_type === "report.start" && isStructuredReport(payload.report)) {
    return { ...state, report: payload.report, status: "streaming" };
  }
  if (
    event.event_type === "report.module" &&
    isStructuredReportModule(payload.module)
  ) {
    return {
      ...state,
      report: upsertStructuredReportModule(
        state.report ?? emptyReport(state.runId),
        payload.module,
      ),
      status: "streaming",
    };
  }
  if (
    (event.event_type === "report.complete" ||
      event.event_type === "report.error") &&
    isStructuredReport(payload.report)
  ) {
    return { ...state, report: payload.report };
  }
  if (event.event_type === "workflow.loaded") {
    const workflow = liveWorkflow(payload);
    return workflow
      ? {
          ...state,
          workflow,
          status: "streaming",
        }
      : state;
  }
  if (
    (event.event_type === "skill.start" ||
      event.event_type === "skill.result") &&
    typeof payload.skill_id === "string"
  ) {
    const previous = state.skillInvocations[payload.skill_id];
    const status =
      payload.status === "completed" ||
      payload.status === "degraded" ||
      payload.status === "failed"
        ? payload.status
        : "running";
    const invocation: LiveSkillInvocation = {
      skill_id: payload.skill_id,
      selection_source: selectionSource(
        payload.selection_source ?? previous?.selection_source,
      ),
      reason:
        typeof payload.reason === "string"
          ? payload.reason
          : (previous?.reason ?? ""),
      status,
      warnings: Array.isArray(payload.warnings)
        ? payload.warnings.filter(
            (warning): warning is string => typeof warning === "string",
          )
        : (previous?.warnings ?? []),
    };
    return {
      ...state,
      skillInvocations: {
        ...state.skillInvocations,
        [invocation.skill_id]: invocation,
      },
      status: "streaming",
    };
  }
  if (
    (event.event_type === "message.complete" ||
      event.event_type === "message.error") &&
    isChatMessage(payload.message)
  ) {
    return {
      ...state,
      narrative:
        state.answerRevision > 0
          ? state.narrative
          : (payload.message.content || state.narrative),
      status:
        payload.message.status === "cancelled"
          ? "cancelled"
          : payload.message.status === "completed"
            ? "completed"
            : "failed",
    };
  }
  if (event.event_type === "message.start") {
    return { ...state, status: "streaming" };
  }
  return state;
}
