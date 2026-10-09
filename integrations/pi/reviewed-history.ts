/** Opt-in native Pi revision loop. Domain rules and receipt validation stay in Python. */
import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { isAbsolute } from "node:path";
import type { AssistantMessage, Usage } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { childEnvironment, createHistoryTool, validatePayload } from "./market-history.ts";

type RecordValue = Record<string, unknown>;
type Message = { role: "system" | "user"; content: string };
type Prepared = { request: RecordValue; messages: Message[]; batch_count?: number };
type Verdict = RecordValue & { status: "reviewed" | "revision_required" | "unavailable"; issues: string[] };
type ReviewUsage = { stage: string; provider: string; model: string; usage: Usage };

const hash = (text: string) => createHash("sha256").update(text).digest("hex");
const record = (value: unknown): value is RecordValue => value !== null && typeof value === "object" && !Array.isArray(value);
const textContent = (content: unknown): string => typeof content === "string" ? content : Array.isArray(content)
  ? content.filter((part): part is { type: "text"; text: string } => record(part) && part.type === "text" && typeof part.text === "string").map(part => part.text).join("\n") : "";

function preparation(value: unknown): Prepared {
  if (!record(value) || !record(value.request) || typeof value.request.request_id !== "string" || !Array.isArray(value.messages) ||
      value.messages.length !== 2 || !value.messages.every((m, i) => record(m) && m.role === (i === 0 ? "system" : "user") && typeof m.content === "string")) {
    throw new Error("History review request unavailable.");
  }
  return value as Prepared;
}

function verdict(value: unknown): Verdict {
  if (!record(value) || !["reviewed", "revision_required", "unavailable"].includes(String(value.status)) ||
      !Array.isArray(value.issues) || !value.issues.every(issue => typeof issue === "string")) {
    throw new Error("History review receipt unavailable.");
  }
  return value as Verdict;
}

export function runReviewCommand(action: "prepare" | "accept" | "audit" | "batch" | "accept_batches" | "complete", value: unknown, signal?: AbortSignal): Promise<unknown> {
  const root = process.env.FINANCE_HISTORY_CODE_ROOT;
  const python = process.env.FINANCE_HISTORY_PYTHON;
  if (!root || !python || !isAbsolute(root) || !isAbsolute(python) || signal?.aborted) {
    return Promise.reject(new Error("History review configuration unavailable or cancelled."));
  }
  const input = JSON.stringify(value);
  if (Buffer.byteLength(input) > 512 * 1024) return Promise.reject(new Error("History review input exceeds budget."));
  return new Promise((accept, reject) => {
    const fail = () => reject(new Error("History review bridge unavailable, cancelled or over budget."));
    try {
      const child = execFile(python, ["-m", "intelligence.history_answer_review_cli", action], {
        cwd: root, env: childEnvironment(root), encoding: "utf8", signal, timeout: 35_000, maxBuffer: 512 * 1024,
      }, (error, stdout) => {
        if (error) { fail(); return; }
        try { accept(JSON.parse(stdout)); } catch { fail(); }
      });
      child.stdin?.on("error", fail);
      child.stdin?.end(input);
    } catch { fail(); }
  });
}

function deliveredToolTexts(payload: unknown): Set<string> {
  const texts = new Set<string>();
  if (!record(payload)) return texts;
  if (Array.isArray(payload.messages)) for (const message of payload.messages) {
    if (!record(message)) continue;
    if (message.role === "tool") texts.add(textContent(message.content));
    if (message.role === "user" && Array.isArray(message.content)) for (const block of message.content) {
      if (record(block) && block.type === "tool_result") texts.add(textContent(block.content));
    }
  }
  if (Array.isArray(payload.input)) for (const item of payload.input) {
    if (record(item) && item.type === "function_call_output" && typeof item.output === "string") texts.add(item.output);
  }
  return texts;
}

// One settle continuation per Pi process. finance-mode.ts shares this key, so enabling both
// fails extension load at startup instead of stacking two follow-up turns.
const CONTINUATION_OWNER = Symbol.for("finance.pi.continuation-owner");

function claimContinuation(pi: ExtensionAPI, name: string): void {
  const registry = globalThis as unknown as Record<symbol, string | undefined>;
  const owner = registry[CONTINUATION_OWNER];
  if (owner !== undefined && owner !== name) {
    throw new Error(`Pi continuation already owned by ${owner}; ${name} would stack a second follow-up turn. Load only one of them.`);
  }
  registry[CONTINUATION_OWNER] = name;
  pi.on("session_shutdown", () => { if (registry[CONTINUATION_OWNER] === name) delete registry[CONTINUATION_OWNER]; });
}

export function installHistoryReview(pi: ExtensionAPI, options: { maxRepairs?: number; timeoutMs?: number } = {}) {
  const maxRepairs = options.maxRepairs ?? 1;
  const timeoutMs = options.timeoutMs ?? 300_000;
  if (!Number.isInteger(maxRepairs) || maxRepairs < 0 || maxRepairs > 2 || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error("Invalid history review policy.");
  }
  if (maxRepairs > 0) claimContinuation(pi, "reviewed-history");
  let epoch = 0;
  let question = "";
  let repairs = 0;
  let pending: { draft: string; issues: string[]; statements: RecordValue[]; readouts: unknown[] } | undefined;
  let sources = new Map<string, RecordValue>();
  let delivered: RecordValue[] = [];
  let reviews = new Map<string, Verdict>();

  const reset = (prompt: string) => {
    epoch++; question = prompt; repairs = 0; pending = undefined;
    sources = new Map(); delivered = []; reviews = new Map();
  };
  pi.on("before_agent_start", event => { reset(event.prompt); });
  pi.on("before_provider_request", event => {
    const texts = deliveredToolTexts(event.payload);
    delivered = [...sources.entries()].filter(([text]) => texts.has(text)).map(([, source]) => source);
  });

  async function reviewCall(prepared: Prepared, stage: string, ctx: ExtensionContext, usage: ReviewUsage[], attempts: RecordValue[]): Promise<string> {
    if (!ctx.model) throw new Error("History reviewer model unavailable.");
    const model = ctx.model;
    const attempt: RecordValue = { stage, provider: model.provider, model: model.id, payload_seen: false, response_received: false };
    attempts.push(attempt);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const signal = ctx.signal ? AbortSignal.any([ctx.signal, controller.signal]) : controller.signal;
    try {
      const response = await ctx.modelRegistry.streamSimple(model, {
        messages: prepared.messages.map(message => message.role === "system"
          ? { role: "system" as const, content: message.content, timestamp: Date.now() }
          : { role: "user" as const, content: message.content, timestamp: Date.now() }),
      }, {
        signal, timeoutMs, maxRetries: 0, maxTokens: 16384, temperature: 0, reasoning: "high",
        onPayload: (payload, actualModel) => {
          attempt.payload_seen = true;
          pi.events.emit("finance_history_review", { phase: "provider_request", stage,
            request_id: prepared.request.request_id, provider: actualModel.provider, model: actualModel.id, payload });
          return undefined;
        },
        onResponse: response => {
          attempt.response_received = true; attempt.http_status = response.status;
          pi.events.emit("finance_history_review", { phase: "provider_response", stage,
            request_id: prepared.request.request_id, status: response.status });
        },
      }).result();
      attempt.stop_reason = response.stopReason;
      usage.push({ stage, provider: response.provider, model: response.model, usage: response.usage });
      pi.events.emit("finance_history_review", { phase: "reviewer_end", stage,
        request_id: prepared.request.request_id, response });
      if (signal.aborted || response.stopReason !== "stop" || response.provider !== model.provider || response.model !== model.id ||
          response.content.some(block => block.type === "toolCall")) throw new Error("History reviewer did not complete.");
      return textContent(response.content);
    } finally { attempt.cancelled = signal.aborted; clearTimeout(timer); }
  }

  pi.on("message_end", async (event, ctx) => {
    // Queued steering/follow-up user messages bypass before_agent_start.
    // Controller feedback is a custom message and must not reset its repair count.
    if (event.message.role === "user") { reset(textContent(event.message.content)); return; }
    if (event.message.role === "toolResult" && event.message.toolName === "finance_market_history" && !event.message.isError) {
      const details = event.message.details;
      const text = textContent(event.message.content);
      if (record(details) && record(details.review_source) && details.review_source.public_text === text && typeof details.as_of === "string") {
        try {
          validatePayload(text, details.as_of);
          sources.set(text, details.review_source);
        } catch { /* A malformed result grants no review evidence. */ }
      }
      return;
    }
    if (event.message.role !== "assistant" || event.message.stopReason !== "stop" || event.message.content.some(block => block.type === "toolCall")) return;
    const message: AssistantMessage = event.message;
    const draft = textContent(message.content);
    const turnEpoch = epoch;
    const turnQuestion = question;
    let admittedSources: RecordValue[] = [];
    let reused = false;
    let preparedId: string | undefined;
    const usage: ReviewUsage[] = [];
    const attempts: RecordValue[] = [];
    let decision: Verdict = { status: "unavailable", issues: ["历史材料复核未完成，原稿未经确认。"] };
    pending = undefined;
    try {
      pi.events.emit("finance_history_review", { phase: "draft", draft, draft_sha256: hash(draft), repairs });
      admittedSources = structuredClone(delivered);
      const prepared = preparation(await runReviewCommand("prepare", { question: turnQuestion, draft, sources: admittedSources }, ctx.signal));
      const requestId = String(prepared.request.request_id);
      preparedId = requestId;
      const cached = reviews.get(requestId);
      if (cached) {
        decision = structuredClone(cached);
        reused = true;
      } else {
        if (!Number.isInteger(prepared.batch_count) || !prepared.batch_count || prepared.batch_count > 16) {
          throw new Error("History review batch plan unavailable.");
        }
        const responses: string[] = [];
        for (let index = 0; index < prepared.batch_count; index++) {
          const batch = preparation(await runReviewCommand("batch", { request: prepared.request, index }, ctx.signal));
          responses.push(await reviewCall(batch, `claims:${index + 1}`, ctx, usage, attempts));
        }
        let accepted = await runReviewCommand("accept_batches", { request: prepared.request, responses }, ctx.signal);
        if (!record(accepted)) throw new Error("History review response unavailable.");
        if (accepted.completion) {
          const completion = preparation(accepted.completion);
          const response = await reviewCall(completion, "completeness", ctx, usage, attempts);
          accepted = await runReviewCommand("complete", { request: prepared.request, first: accepted.verdict, response }, ctx.signal);
          if (!record(accepted)) throw new Error("History completeness review unavailable.");
        }
        decision = verdict(accepted.verdict);
        if (accepted.audit) {
          const audit = preparation(accepted.audit);
          const response = await reviewCall(audit, "nonfactual", ctx, usage, attempts);
          const combined = await runReviewCommand("audit", { first: decision, audit_request: audit.request, response }, ctx.signal);
          if (!record(combined)) throw new Error("History review audit unavailable.");
          decision = verdict(combined.verdict);
        }
      }
      if (turnEpoch !== epoch || ctx.signal?.aborted) {
        decision = { status: "unavailable", issues: ["本次复核已取消或会话已切换，原稿未经确认。"] };
      }
    } catch {
      decision = { status: "unavailable", issues: ["历史材料复核不可用或回执无效，原稿保留但未经确认。"] };
    }
    if (preparedId && turnEpoch === epoch && !ctx.signal?.aborted) reviews.set(preparedId, structuredClone(decision));
    const receipt = { schema_version: "pi-history-review/v1", ...decision, draft, draft_sha256: hash(draft),
      repairs, question: turnQuestion, reused_review: reused,
      source_hashes: admittedSources.map(source => hash(String(source.public_text))),
      reviewer_attempts: attempts, reviewer_usage: usage, usage_accounting: "separate_nested_requests_not_author_usage",
      not_independent_financial_approval: true };
    try {
      pi.appendEntry("finance_history_review", receipt);
      pi.events.emit("finance_history_review", { phase: "verdict", receipt });
      if (ctx.hasUI) ctx.ui.setStatus("history-review", `历史复核 ${decision.status} · ${attempts.length} 次复核尝试`);
    } catch {
      decision = { status: "unavailable", issues: ["历史复核记录未能保存，原稿保留但未经确认。"] };
    }
    if (decision.status === "reviewed") return;
    if (decision.status === "revision_required" && repairs < maxRepairs && turnEpoch === epoch && !ctx.signal?.aborted) {
      const rejected = new Set(Array.isArray(decision.rejected_sentence_indexes) ? decision.rejected_sentence_indexes : []);
      const statements = Array.isArray(decision.claim_checks) ? decision.claim_checks.filter(row => record(row) &&
        (row.supported === false || rejected.has(row.sentence_index))).map(row => ({
          sentence_index: row.sentence_index, text: row.text, reason: row.reason, readouts: row.material_anchors,
        })) : [];
      const references = new Set(statements.flatMap(row => Array.isArray(row.readouts)
        ? row.readouts.filter(record).map(anchor => anchor.anchor_index) : []));
      const readouts = Array.isArray(decision.readouts) ? decision.readouts.filter(row => record(row) && references.has(row.anchor_index)) : [];
      pending = { draft, issues: decision.issues, statements, readouts };
    }
    // Preserve the work, not an empty fallback. The receipt and visible status
    // never present a rejected/unavailable review as a financial certificate.
    const note = pending ? "历史材料复核未通过。以下保留本次原稿。"
      : "历史材料复核未通过或不可用。以下为未确认的原稿，不是已核验结论。";
    const issues = decision.issues.map(issue => `- ${issue}`).join("\n");
    return { message: { ...message, content: [{ type: "text", text: `> ${note}\n\n${draft}\n\n### 复核记录\n${issues}` }] } };
  });

  pi.on("turn_end", event => {
    if (!pending || event.outcome !== "completed") { pending = undefined; return; }
    // Pi evaluates canContinue after committing the proposed feedback entry;
    // the pre-entry context ends in an assistant message and cannot continue yet.
    const rejected = pending;
    pending = undefined;
    repairs++;
    return { continue: true, entries: [{ type: "custom_message", customType: "finance_history_revision", display: false,
      content: "根据本次历史材料复核，修订完整回答。保留已支持内容，修改无支持或矛盾的命题及遗漏的必要限定；"
        + "复核意见是待核指引，不是新市场事实；引用读数来自原材料，须核对其窗口、类型和单位。"
        + "不能改原数据、补零、把差值当水平或把描述统计升级。仍不足就明确说明。\n"
        + JSON.stringify({ original_draft: rejected.draft, review_issues: rejected.issues, rejected_statements: rejected.statements, readouts: rejected.readouts }),
      details: { revision_attempt: repairs, maximum_revision_attempts: maxRepairs } }] };
  });
}

export default function (pi: ExtensionAPI) {
  pi.registerTool(createHistoryTool(true));
  installHistoryReview(pi);
}
