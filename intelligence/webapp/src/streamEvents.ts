import { upsertStructuredReportModule } from "./structuredReport";
import type {
  ChatMessage,
  LiveMessageState,
  LiveSkillInvocation,
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
    report: null,
    skillInvocations: {},
    currentStage: null,
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
  if (
    event.event_type === "stage.progress" &&
    typeof payload.stage === "string"
  ) {
    return { ...state, currentStage: payload.stage, status: "streaming" };
  }
  if (event.event_type === "text.delta") {
    const delta = typeof payload.delta === "string" ? payload.delta : "";
    return {
      ...state,
      narrative: `${state.narrative}${delta}`,
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
      narrative: payload.message.content || state.narrative,
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
