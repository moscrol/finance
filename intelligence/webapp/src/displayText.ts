const issueLabels: Record<string, string> = {
  llm_unavailable_template_answer:
    "自然语言综合暂时不可用，已保留可核验数据与研究产物。",
  trading_calendar_unavailable:
    "交易日历暂不可用，因此无法确认下一交易日。",
  non_trading_day: "记录日期不是有效交易日，相关日期结论不可采用。",
  future_trade_date: "记录日期晚于当前可验证范围，相关日期结论不可采用。",
};

const internalIssuePattern =
  /Traceback|File ".+", line \d+|^[A-Za-z_][\w.]+(?:Error|Exception):|^[a-z][a-z0-9_]+$/;
const localPathPattern = /\/(?:Users|home)\/|[A-Za-z]:\\/;

export function userFacingIssue(issue: string): string {
  const value = issue.trim();
  if (issueLabels[value]) return issueLabels[value];
  if (/^wiki-rag\b/i.test(value)) {
    return value.includes("stale")
      ? "知识库索引已过期；相关证据仅供参考。"
      : "知识库检索暂不可用；本轮未使用知识库语义证据。";
  }
  if (/^answer-orchestrator[:：]/i.test(value)) {
    return "问题类型未能高置信识别；本轮按通用研究问题处理，结论需显式说明假设。";
  }
  if (/^(?:模块\s+)?replay[:：]/i.test(value)) {
    return "当前题材缺少历史发酵信号，相关历史回放未执行。";
  }
  if (/未配置 LLM key/i.test(value)) {
    return "自然语言综合暂时不可用；已保留可核验数据与结构化产物。";
  }
  if (localPathPattern.test(value)) {
    return "某项本地研究数据暂不可用；相关证据未纳入本轮结论。";
  }
  if (internalIssuePattern.test(value)) {
    return "研究过程中出现内部错误；相关结论可能不完整，已保留其他可用证据。";
  }
  return value;
}

export const stageLabels: Record<string, string> = {
  route_skills: "选择研究工具",
  ask_current_turn: "检索本轮证据",
  ask_retrieve_compose: "核对数据时效并组织回答",
  render_artifacts: "生成研究产物",
  foresight_followups: "整理后续核验问题",
};

export function userFacingStage(stage: string): string {
  return stageLabels[stage] ?? "执行研究步骤";
}

export function evidenceClassificationLabel(classification: string): string {
  if (classification === "bound_evidence") return "可验证引用";
  if (classification === "fact_source") return "检索来源";
  if (classification === "fact_or_context") return "引用汇总";
  return "研究依据";
}

export function freshnessLabel(freshness: string | null): string {
  if (freshness === "fresh") return "当前";
  if (freshness === "stale") return "已过期";
  if (freshness === "unknown") return "待确认";
  return freshness ?? "未记录";
}

export function traceStatusLabel(status: string): string {
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已停止";
  if (status === "running") return "进行中";
  return "等待中";
}
