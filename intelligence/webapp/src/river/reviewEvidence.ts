import type { ReviewHistory } from "./historyTypes";

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
