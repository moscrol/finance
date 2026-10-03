import { useEffect, useState } from "react";
import { ClipboardCheck, Download, FileSearch, LockKeyhole } from "lucide-react";
import { getLimitUpCalendar } from "../../river/api";
import type { LimitUpDay } from "../../river/types";
import type { ReviewSnapshot } from "../../river/reviewTypes";
import { blankObservation, observationPrompt, observationTemplates, observationValidation } from "../../river/observation";
import type { ObservationForm, ObservationLens, ObservationRecord, ObservationVerdict } from "../../river/observation";
import "../../riverObservation.css";

const STORE = "foresight.observation-workbench.v1";
interface Notebook { forms: Record<string, ObservationForm>; records: ObservationRecord[] }
function notebook(): Notebook {
  try { const value = JSON.parse(window.localStorage.getItem(STORE) ?? "{}"); return { forms: value.forms ?? {}, records: Array.isArray(value.records) ? value.records : [] }; }
  catch { return { forms: {}, records: [] }; }
}
const verdicts: [ObservationVerdict, string][] = [["pending", "未评估"], ["supports", "支持"], ["opposes", "反对"], ["missing", "缺数据"]];
function show(value: unknown, suffix = "") { return typeof value === "number" && Number.isFinite(value) ? `${value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}${suffix}` : typeof value === "string" && value ? value : "—"; }
function exportRecord(record: ObservationRecord) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = `观察记录-${record.observation_date}-${record.lens}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function ObservationWorkbench({ date, dates, subject = "全市场", onDate, onEvidence }: {
  date: string | null; dates: string[]; subject?: string; onDate: (date: string) => void;
  onEvidence: (view: "daily" | "research" | "ladder") => void;
}) {
  const [lens, setLens] = useState<ObservationLens>("spt");
  const [form, setForm] = useState<ObservationForm>(() => blankObservation(subject));
  const [records, setRecords] = useState<ObservationRecord[]>(() => notebook().records);
  const [review, setReview] = useState<ReviewSnapshot | null>(null);
  const [ladder, setLadder] = useState<LimitUpDay | null>(null);
  const [archiveError, setArchiveError] = useState(false);
  const [ladderError, setLadderError] = useState(false);
  const [notice, setNotice] = useState("");
  const [storageError, setStorageError] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [revision, setRevision] = useState(0);
  const key = `${date ?? "pending"}|${subject}|${lens}`;
  useEffect(() => { setForm(notebook().forms[key] ?? blankObservation(subject)); setNotice(""); setPrompt(""); }, [key, subject]);
  useEffect(() => {
    setReview(null); setLadder(null); setArchiveError(false); setLadderError(false);
    if (!date) return;
    const controller = new AbortController();
    fetch(`/api/river/daily-review?as_of=${encodeURIComponent(date)}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("archive");
      const data = await response.json() as ReviewSnapshot;
      if (data.trade_date !== date) throw new Error("mismatched-date");
      if (!controller.signal.aborted) setReview(data);
    }).catch(() => { if (!controller.signal.aborted) setArchiveError(true); });
    getLimitUpCalendar(20, date).then(data => {
      if (controller.signal.aborted) return;
      const day = data.days.find(d => d.trade_date === date) ?? null;
      setLadder(day); setLadderError(!day);
    }).catch(() => { if (!controller.signal.aborted) setLadderError(true); });
    return () => controller.abort();
  }, [date, revision]);
  const template = observationTemplates[lens];
  const facts = review?.report?.facts ?? {};
  const saveNotebook = (data: Notebook) => {
    try { window.localStorage.setItem(STORE, JSON.stringify(data)); setStorageError(false); return true; }
    catch { setStorageError(true); return false; }
  };
  const change = (next: ObservationForm) => {
    setForm(next); const stored = notebook(); stored.forms[key] = next; saveNotebook(stored);
  };
  const freeze = () => {
    if (!date) return;
    const problem = observationValidation(form, date, lens);
    if (problem) { setNotice(problem); return; }
    const created = new Date().toISOString();
    const record: ObservationRecord = {
      schema_version: 1, id: `${created}-${Math.random().toString(36).slice(2, 8)}`, created_at: created,
      observation_date: date, lens, kind: "human_observation_not_backtest", strict_point_in_time: false,
      framework_source: template.source, framework_version: "2026-09-29-observation-v1", criteria_snapshot: structuredClone(template.criteria), form: structuredClone(form),
      evidence: { archive_status: review?.status ?? (archiveError ? "error" : "pending"), archive_sha256: review?.provenance?.sha256 ?? null, archive_generated_at: review?.provenance?.generated_at ?? null, archive_path: review?.provenance?.source_path ?? null, ladder_date: ladder?.trade_date ?? null, viewed_facts: Object.fromEntries(["market_stage", "total_amount", "volume_ratio", "top3_industry_ratio", "advancers", "advancers_ma5"].map(k => [k, facts[k] ?? null])), ladder_summary: ladder ? { max_boards: ladder.max_boards, leader_name: ladder.leader?.name ?? null } : null }, reviews: [],
    };
    const next = [record, ...records]; setRecords(next);
    const stored = notebook(); stored.records = next; const saved = saveNotebook(stored);
    setNotice(saved ? "原始条件已冻结到本浏览器。后续只能追加复查；尚未写入服务器或Agent台账。" : "原始条件仅在本页内存冻结，未保存到浏览器；请立即导出。");
  };
  const appendReview = (record: ObservationRecord, outcome: "supports" | "opposes" | "insufficient") => {
    const note = reviewNotes[record.id]?.trim();
    if (!note) { setNotice("追加复查前，请写明复查数据日、证据与原因；只选涨跌不能代替验证。"); return; }
    const next = records.map(r => r.id === record.id ? { ...r, reviews: [...r.reviews, { recorded_at: new Date().toISOString(), outcome, note }] } : r);
    setRecords(next); const stored = notebook(); stored.records = next; const saved = saveNotebook(stored);
    setNotice(saved ? "已追加人工复查。原假设、条件和证据引用没有覆盖。" : "复查仅在本页内存追加，未持久保存；请立即导出。");
  };
  return <section className="output-workbench observation-workbench" aria-label="人工观察验证工作区">
    <header className="output-workbench-header"><div><ClipboardCheck size={15}/><strong>观察验证</strong><span>事实 → 假设 → 反证 → 复查</span></div><button type="button" onClick={() => setRevision(n => n + 1)}>重读证据</button></header>
    <div className="obs-content">
      <div className="obs-intro"><span className="obs-eyebrow">HUMAN RESEARCH / 你来作判断</span><h2>不让图表替你下结论。</h2><p>用同一份事实，分别检验不同解释。模板整理自现有判读基线与画像，不代表作者当日观点，也不是已回测策略。</p></div>
      <div className="obs-controls"><label>观察数据日<select aria-label="观察数据日" value={date ?? ""} onChange={e => onDate(e.target.value)}>{!date && <option value="">等待交易日…</option>}{date && !dates.includes(date) && <option>{date}</option>}{dates.slice().reverse().map(d => <option key={d}>{d}</option>)}</select></label><div role="group" aria-label="观察模板">{(["spt", "fengyuan"] as const).map(value => <button type="button" key={value} aria-pressed={lens === value} onClick={() => setLens(value)}>{observationTemplates[value].title}</button>)}</div></div>
      <section className="obs-evidence" aria-label="同日事实参照"><header><div><b>01 / 同日事实，不是条件判定</b><small>{date ?? "待确认"} · 原daily归档与连板台账，各自独立读取</small></div><div><button type="button" onClick={() => onEvidence("daily")}>日报与指数 ↗</button><button type="button" onClick={() => onEvidence("research")}>板块六轨 ↗</button><button type="button" onClick={() => onEvidence("ladder")}>连板与锚点 ↗</button></div></header>
        {archiveError && <p role="alert">日报读取失败，不以其他日期替代。仍可记录“缺数据”，不要当作零。</p>}
        {review?.status === "missing" && <p>这一天没有结构化日报。保留缺口，不回退到最新日报。</p>}
        {!review && !archiveError && <p role="status">正在读取所选日归档…</p>}
        <div className="obs-facts">{[["市场阶段", show(facts.market_stage)], ["成交额", show(facts.total_amount, " 亿")], ["相对20日均量", show(facts.volume_ratio, "%")], ["前三行业集中度", show(facts.top3_industry_ratio, "%")], ["涨家数 / MA5", `${show(facts.advancers)} / ${show(facts.advancers_ma5)}`], ["全市场高度参照", ladder ? `${ladder.max_boards ?? "—"} 板 · ${ladder.leader?.name ?? "名称缺失"}` : "—"]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
        {ladderError && <p>所选日连板参照暂不可读；不会用全市场其他日期的高标补位。</p>}
        <small>“有数据”不等于“条件成立”。支撑位、板块阶段与方向锚需你明确标注；全市场最高板不自动属于所研究板块。</small>
      </section>
      <section className="obs-hypothesis"><label>观察对象<input aria-label="观察对象" value={form.subject} maxLength={160} onChange={e => change({ ...form, subject: e.target.value })}/></label><label>待验证假设<textarea aria-label="待验证假设" placeholder="例如：这次回流只是缩量修复，还是主线重新扩散？先写可被推翻的解释。" value={form.hypothesis} maxLength={4000} onChange={e => change({ ...form, hypothesis: e.target.value })}/></label></section>
      <div className="obs-section-label">02 / 按条件逐项核对 <span>以下判定全部由你填写，不是系统评级</span></div>
      <div className="obs-criteria">{template.criteria.map(c => <article key={c.id}><h3>{c.title}</h3><p>{c.question}</p><div className="obs-boundary">{c.boundary}</div><label>人工判定<select aria-label={`${c.title} 人工判定`} value={form.assessments[c.id]?.verdict ?? "pending"} onChange={e => change({ ...form, assessments: { ...form.assessments, [c.id]: { note: form.assessments[c.id]?.note ?? "", verdict: e.target.value as ObservationVerdict } } })}>{verdicts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><textarea aria-label={`${c.title} 证据备注`} placeholder="写下数据日、实体、观察值或原文位置；也可以明确说明缺什么。" maxLength={4000} value={form.assessments[c.id]?.note ?? ""} onChange={e => change({ ...form, assessments: { ...form.assessments, [c.id]: { verdict: form.assessments[c.id]?.verdict ?? "pending", note: e.target.value } } })}/></article>)}</div>
      <section className="obs-conditions"><label>什么出现才升级为确认？<textarea aria-label="确认条件" placeholder="声明指标、口径、观察窗口和由你选择的阈值；不要只写“继续走强”。" maxLength={4000} value={form.confirmation} onChange={e => change({ ...form, confirmation: e.target.value })}/></label><label>什么出现会推翻或降级？<textarea aria-label="推翻条件" placeholder="写在结果出来之前；反证出现后不得事后移动门槛。" maxLength={4000} value={form.invalidation} onChange={e => change({ ...form, invalidation: e.target.value })}/></label><label>拟复查日期<input type="date" aria-label="拟复查日期" min={date ?? undefined} value={form.reviewDate} onChange={e => change({ ...form, reviewDate: e.target.value })}/><small>人工指定日期，不自动假设它是下一交易日；没有后续数据就保留待复查。</small></label></section>
      <div className="obs-freeze"><button type="button" disabled={!date} onClick={freeze}><LockKeyhole size={14}/>冻结这次观察</button><p>形成时间记录为现在。历史归档不等于当时可得信息，本页不计算预测胜率、不回填未来数据。</p></div>
      {notice && <p className="obs-notice" role="status">{notice}</p>}{storageError && <p role="alert">浏览器存储不可用，当前内容只在页面内存中；请导出记录后再离开。</p>}
      <details className="obs-method"><summary>方法来源与存储边界</summary><p>{template.source}</p><p>判读基线已有规则ID；模板只组织观察顺序，不注入未经标定的倍数、天数或自动买卖信号。浏览器草稿与人工复查不是服务器正式台账，也不会自动交给Agent。导出的JSON保留事实引用、人工判定与形成时间，研究问题可由你手动交给Agent继续核验。</p></details>
      <div className="obs-section-label">03 / 冻结记录与追加复查 <span>{records.length} 条 · 本浏览器，不跨设备同步</span></div>
      {!records.length && <div className="obs-empty">还没有冻结记录。先写假设与反证，再看后来的结果。</div>}
      {records.map(record => <article className="obs-record" key={record.id}><header><b>{record.form.subject} · {record.observation_date}</b><span>{observationTemplates[record.lens].title}</span></header><p><b>原假设：</b>{record.form.hypothesis}</p><p><b>确认：</b>{record.form.confirmation}</p><p><b>推翻：</b>{record.form.invalidation}</p><small>形成于 {record.created_at} · 拟复查 {record.form.reviewDate} · 归档 {record.evidence.archive_status} · 非严格历史回测</small><div className="obs-record-actions"><button type="button" onClick={() => exportRecord(record)}><Download size={13}/>导出记录</button><button type="button" onClick={() => setPrompt(observationPrompt(record))}><FileSearch size={13}/>生成Agent核验问题</button></div><label>追加复查证据<textarea aria-label={`复查证据 ${record.id}`} placeholder="明确复查数据日、结果及证据来源；信息不足也可以记下，原条件保持不变。" value={reviewNotes[record.id] ?? ""} maxLength={4000} onChange={e => setReviewNotes({ ...reviewNotes, [record.id]: e.target.value })}/></label><div className="obs-record-actions">{([["supports", "追加：支持"], ["opposes", "追加：反证"], ["insufficient", "追加：信息不足"]] as const).map(([value, label]) => <button type="button" key={value} onClick={() => appendReview(record, value)}>{label}</button>)}</div>{record.reviews.map((r, i) => <blockquote key={i}><b>{r.outcome === "supports" ? "人工复查：支持" : r.outcome === "opposes" ? "人工复查：反证" : "人工复查：信息不足"}</b><span>{r.recorded_at}</span><p>{r.note}</p></blockquote>)}</article>)}
      {prompt && <section className="obs-prompt"><h3>Agent核验问题 · 尚未发送</h3><textarea aria-label="Agent核验问题" readOnly value={prompt}/><p>复制到问答继续核验。此处不调用模型、不启动采集，也不将你的推断作为已证实事实。</p></section>}
    </div>
  </section>;
}
