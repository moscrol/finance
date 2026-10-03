export type ObservationVerdict = "pending" | "supports" | "opposes" | "missing";
export type ObservationLens = "spt" | "fengyuan";
export interface ObservationCriterion { id: string; title: string; question: string; boundary: string }
export const observationTemplates: Record<ObservationLens, { title: string; source: string; criteria: ObservationCriterion[] }> = {
  spt: { title: "SPT · 量能与结构", source: "reading_baseline / CR-01、SPT-A01/A02/A03/A10；现有SPT画像的量能与筹码结构镜头", criteria: [
    { id: "market", title: "01 市场是否给出量能条件？", question: "先看指数位置、成交额相对均量和涨家数，再谈板块。一次放量与持续放量分开记录。", boundary: "相对均量是事实，不自动等于主升资格；具体阈值由你声明，未经标定不作为硬规则。" },
    { id: "sector", title: "02 主线是在扩散，还是缩容？", question: "对照行业成交占比的连续变化、子板块矩阵与前排个股。上涨是否伴随宽度和量能？", boundary: "前三行业集中度不是某一题材的占比；不要把主线名单或缺失强度当作确认。" },
    { id: "structure", title: "03 回流或新承接的结构齐了吗？", question: "明确你画的支撑／压力位；记录缩量回踩、后续续量、突破或失败的条件。", boundary: "本观察页没有30／60分钟结构读数。日线不能代替分钟底背离，缺这一条就标缺数据。" },
    { id: "counter", title: "04 哪个现象会推翻现在的解释？", question: "写出下一观察窗口的反向情景：例如续量失败、占比回落、前排失去联动。", boundary: "结构类比不是未来收益保证；不要事后移动支撑位或改写原条件。" },
  ] },
  fengyuan: { title: "风远 · 双锚与兑现", source: "reading_baseline / FY-A01/A04/A05/A06/A09/A10；现有风远画像的根／干／果结构", criteria: [
    { id: "root", title: "01 根：产业逻辑靠什么兑现？", question: "列出供给约束、订单、交期或价格证据，区分领先、确认与滞后指标。", boundary: "日报量价不能证明产业定价权；原文、发布日期、订单或产业数据缺失时保留缺口。" },
    { id: "capital", title: "02 干：资金结构有证据吗？", question: "区分行情结果与资金主体证据；检查不同类型标的的表现是否符合你的解释。", boundary: "L2净额不等于持有人身份，不能据此认定信仰资金、FOMO或ETF赎回。" },
    { id: "anchors", title: "03 果：方向锚与高度锚是否共振？", question: "由你明确写下两个锚是谁，再核对走势、连板高度与板块联动；单锚走弱不算双锚确认。", boundary: "全市场最高板不自动等于当前板块的高度锚；两个锚的选择是人工假设，应一并留存。" },
    { id: "counter", title: "04 有没有足以使框架失效的反证？", question: "区分基本面证伪与流动性挤压。新增催化、反向吞噬或后续不创新低，会如何改变判断？", boundary: "利多不涨须有具体利多及可见时间；没有消息证据，不能仅凭K线贴这个标签。" },
  ] },
};
export interface ObservationForm {
  subject: string; hypothesis: string; confirmation: string; invalidation: string; reviewDate: string;
  assessments: Record<string, { verdict: ObservationVerdict; note: string }>;
}
export interface ObservationRecord {
  schema_version: 1; id: string; created_at: string; observation_date: string; lens: ObservationLens;
  kind: "human_observation_not_backtest"; strict_point_in_time: false;
  framework_source: string; framework_version: string; criteria_snapshot: ObservationCriterion[]; form: ObservationForm;
  evidence: { archive_status: string; archive_sha256: string | null; archive_generated_at: string | null; archive_path: string | null; ladder_date: string | null; viewed_facts: Record<string, unknown>; ladder_summary: { max_boards: number | null; leader_name: string | null } | null };
  reviews: { recorded_at: string; outcome: "supports" | "opposes" | "insufficient"; note: string }[];
}
export function blankObservation(subject = "全市场"): ObservationForm {
  return { subject, hypothesis: "", confirmation: "", invalidation: "", reviewDate: "", assessments: {} };
}
export function observationValidation(form: ObservationForm, date: string, lens: ObservationLens): string | null {
  if (!form.subject.trim() || !form.hypothesis.trim()) return "请先写清观察对象与待验证假设。";
  if (!form.confirmation.trim() || !form.invalidation.trim()) return "请同时写出确认条件与推翻条件，不能只记录支持自己的理由。";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.reviewDate) || form.reviewDate <= date) return "请选择晚于观察数据日的复查日期；日期由你指定，不冒充T+1交易日。";
  if (observationTemplates[lens].criteria.some(c => !form.assessments[c.id] || form.assessments[c.id].verdict === "pending")) return "请逐项作出人工判定；缺少证据可明确选择“缺数据”，不必凑成确认。";
  return null;
}
export function observationPrompt(record: ObservationRecord): string {
  const f = record.form;
  return [
    "请核查下面的人类观察草稿，而不是替它背书。人工判断不是事实证据；请主动找反证并保留数据缺口。不要自动下单或调用采集。",
    `观察数据日：${record.observation_date}；记录形成时间：${record.created_at}。这不是严格历史时点回测，不可据此计算预测胜率。`,
    `观察模板：${observationTemplates[record.lens].title}（不是作者当日观点）；对象：${f.subject}`,
    `假设：${f.hypothesis}`, `确认条件：${f.confirmation}`, `推翻条件：${f.invalidation}`, `拟复查日期：${f.reviewDate}`,
    ...(record.criteria_snapshot ?? observationTemplates[record.lens].criteria).map(c => `${c.title}：人工判定=${f.assessments[c.id]?.verdict ?? "pending"}；备注=${f.assessments[c.id]?.note || "未补充"}`),
    `归档状态：${record.evidence.archive_status}；归档SHA256：${record.evidence.archive_sha256 ?? "缺失"}；来源：${record.evidence.archive_path ?? "缺失"}。`,
    "请先核验上述数据是否可取得、日期与口径是否匹配；不要把缺失当零，不要把日线当分钟线、资金净额当持有人身份、研报覆盖当公开消息热度。",
  ].join("\n");
}
