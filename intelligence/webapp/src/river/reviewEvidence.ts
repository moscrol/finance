import type { ReviewHistory } from "./historyTypes";
import type { ReviewEvidenceRef } from "../types";

export interface ReadingInstructions { question: string; method: string; cautions: string }

/** Lossless evidence handoff: no dashboard scraping, filtering, summarization or metric recomputation. */
export function buildReviewEvidencePacket(evidence: ReviewHistory, selectedDate: string | null, instructions: ReadingInstructions) {
  if (evidence.evidence_contract?.version !== "review-evidence/v1") throw new Error("缺少兼容的数据种类合同，不能生成 Agent 交接包。");
  return {
    schema: "review-agent-handoff/v1",
    purpose: "同一份证据，两种读法；用户方法不是市场事实",
    context: {
      start: evidence.start, end: evidence.end, requested_end: evidence.requested_end,
      industry: evidence.industry, selected_date: selectedDate,
      selected_date_in_window: evidence.points.some(p => p.date === selectedDate),
      knowledge_mode: evidence.knowledge_mode,
    },
    user_instructions: { ...instructions, role: "user_authored_research_guidance_not_market_facts", scope: "本包窗口与行业" },
    evidence,
    response_contract: {
      sections: ["覆盖与口径限制", "按用户方法联立证据", "支持与不支持的证据", "仍不能判断的问题"],
      citations: "引用 evidence 内交易日、行业、JSON Pointer（如 /evidence/points/0/metrics/total_amount）和当日 provenance.sha256",
      pointer_base: "本包根对象。evidence_contract.citation_rule 中的 /points/... 相对 evidence 本身，在本包内一律加前缀 /evidence（即 /evidence/points/...）。",
      distinguish: ["归档原值", "相邻日算术差", "用户假设", "Agent推断"],
    },
  };
}

export const REVIEW_HANDOFF_EVENT = "workbench:review-evidence-handoff";
export interface ReviewEvidenceHandoff { ref: ReviewEvidenceRef; label: string; message: string }

/**
 * "带着证据去问答": coordinates + the fingerprint of what the page showed, never the numbers.
 * The server re-reads the same archive and refuses if it changed; the visible message carries
 * only the user's reading method, explicitly labelled as guidance rather than fact.
 */
export function buildReviewEvidenceHandoff(evidence: ReviewHistory, selectedDate: string | null, instructions: ReadingInstructions): ReviewEvidenceHandoff {
  if (!evidence.window_fingerprint || !evidence.industry) throw new Error("该窗口缺少指纹或固定行业，不能交给 Agent。");
  const selected = evidence.points.some(p => p.date === selectedDate) ? selectedDate : null;
  const label = `${evidence.start} → ${evidence.end} · ${evidence.industry}${selected ? ` · 查看日 ${selected}` : ""}`;
  // One paragraph on purpose: the chat's message splitter treats earlier lines and quoted spans as
  // attached material, and the time contract reads the market window from the question itself.
  const flat = (text: string) => text.replace(/\s+/g, " ").trim();
  const question = flat(instructions.question) || `${evidence.industry}在这段窗口里的变化，是否得到市场环境、行业位置、子板块和发动机名单的共同支持？`;
  const parts = [
    `请复盘 ${evidence.start} 至 ${evidence.end} 的${evidence.industry}，以每日复盘归档为准（${evidence.requested_days} 个计划交易日，其中 ${evidence.coverage.available} 日有可读归档）。`,
    `这次想判断：${question}`,
    flat(instructions.method) && `我的解读方法（研究指导，不是市场事实）：${flat(instructions.method)}`,
    flat(instructions.cautions) && `不能直接下结论的情况：${flat(instructions.cautions)}`,
    "回答依次写：覆盖与口径限制、按我的方法联立证据、支持与不支持的证据、仍不能判断的问题；引用交易日与证据编号。",
  ].filter(Boolean);
  return {
    ref: { schema: "review-evidence-ref/v1", end: evidence.end, days: evidence.requested_days, industry: evidence.industry, fingerprint: evidence.window_fingerprint, selected_date: selected },
    label,
    message: parts.join(" "),
  };
}

export function sendReviewEvidenceToChat(handoff: ReviewEvidenceHandoff) {
  window.dispatchEvent(new CustomEvent<ReviewEvidenceHandoff>(REVIEW_HANDOFF_EVENT, { detail: handoff }));
}
