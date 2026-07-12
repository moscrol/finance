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

const publicTextReplacements: Array<[RegExp, string]> = [
  [/\bDuckDB\b/gi, "本地市场数据"],
  [/snapshot\/export/gi, "历史盘面快照"],
  [/\bcapacity_industry\b/g, "成交容量居前"],
  [/\bmarket_context\b/g, "市场环境"],
  [/\bknowledge_evidence\b/g, "知识库候选资料"],
  [/\bMarketAdapter\.get_[A-Za-z0-9_]+\b/g, "本地盘面数据"],
  [/\bgraph_only\b/g, "仅有概念关联，未发现公司级证据"],
  [/\bL1_L3_candidate\b/g, "候选资料，需公告或年报确认"],
  [/\bTrue\b/g, "是"],
  [/\bFalse\b/g, "否"],
  [/\brun trace\b/gi, "本次研究记录"],
];

export function userFacingText(text: string): string {
  let value = text.trim();
  if (!value) return value;
  if (/chunk=|hash=|index=/.test(value)) {
    return "该来源已绑定到本轮回答，可在运行记录中回查。";
  }
  if (localPathPattern.test(value)) return "本地研究文件";
  value = value.replace(/^\[[A-Z]\d+\]\s*/, "");
  value = value.replace(
    /\b(20\d{2}-\d{2}-\d{2})-theme-candidates\.json\b/g,
    "$1 题材候选快照",
  );
  for (const [pattern, replacement] of publicTextReplacements) {
    value = value.replace(pattern, replacement);
  }
  return value
    .replace("本地 本地市场数据", "本地市场数据")
    .replace(/到\s+历史盘面快照/g, "到历史盘面快照")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function userFacingIssue(issue: string): string {
  const value = issue.trim();
  if (issueLabels[value]) return issueLabels[value];
  if (/canonical Daily Review Markdown/i.test(value)) {
    return "最新日报基础文件暂不可用；本轮仅使用可用盘面数据和补充快照。";
  }
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
  const humanized = userFacingText(value);
  if (humanized !== value) return humanized;
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
