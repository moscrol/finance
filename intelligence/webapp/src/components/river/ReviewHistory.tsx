import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Download, RefreshCw } from "lucide-react";
import type { HistoryPoint, ReviewHistory as History } from "../../river/historyTypes";
import "../../riverHistory.css";
import { ReviewReadingGuide } from "./ReviewReadingGuide";

const format = (v: unknown) => v == null || v === "-" || v === "" ? "—" : typeof v === "number" ? v.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : String(v);
const modes = [{ key: "double_red", label: "双红原值", note: "涨幅 / 边际量 / 成交额，保留归档原文" }, { key: "limit_up", label: "涨停数量", note: "原日报题材映射；不同子板块不能相加当全市场" }, { key: "stock_highs", label: "120日新高", note: "原日报新高映射；没有列值不是零" }];

function Sparkline({ values, selected }: { values: (number | null)[]; selected: number }) {
  const valid = values.filter((v): v is number => v !== null);
  if (!valid.length) return <div className="rh-chart-empty">窗口内无可用读数</div>;
  const min = Math.min(...valid), max = Math.max(...valid);
  const x = (i: number) => 5 + i * 210 / Math.max(1, values.length - 1);
  const y = (v: number) => 43 - (max === min ? .5 : (v - min) / (max - min)) * 34;
  const range = `${valid.length < values.length ? `${values.length - valid.length} 日缺读数 · ` : ""}纵轴按本窗 ${min.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} – ${max.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 缩放，不同指标、不同窗口不可直接比高低`;
  return <figure className="rh-spark" title={range}><svg viewBox="0 0 220 50" aria-hidden="true">
    {values.map((v, i) => v !== null && i > 0 && values[i - 1] !== null ? <line key={`l${i}`} x1={x(i - 1)} y1={y(values[i - 1]!)} x2={x(i)} y2={y(v)} stroke="currentColor" strokeWidth="1.8" /> : null)}
    {values.map((v, i) => v === null ? <path key={i} d={`M${x(i) - 1} 46h2`} stroke="#baada0" /> : <circle key={i} cx={x(i)} cy={y(v)} r={i === selected ? 3.8 : 1.6} fill="currentColor" />)}
  </svg><figcaption className="rh-spark-range">本窗 {min.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} – {max.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}</figcaption></figure>;
}
// Distinct markers so "not in scope", "listed but empty", "no column" and
// "no archive" never collapse into the same dash a human would read as zero.
const MATRIX_MARK: Record<string, string> = { not_in_scope: "未覆盖", empty: "无行", not_reported: "未报" };
const ENGINE_NOTE: Record<string, string> = {
  empty: "列入前三但归档写明暂无可排序个股，不是未列入。",
  not_in_scope: "该行业当日不在成交前三，日报按设计不生成发动机表；不是零，也不是退出。",
  not_reported: "行业在前三但归档没有可投影的发动机表，未用其他行业补位。",
  unknown: "成交前三榜单缺失，无法判断是否应有发动机表。",
};
function matrixCell(point: HistoryPoint, mode: string, name: string) {
  if (point.status === "missing") return "缺档";
  if (point.status !== "available") return "不可读";
  const matrix = point.matrices[mode];
  if (!matrix || matrix.status !== "available") return MATRIX_MARK[matrix?.status ?? "not_reported"] ?? "未报";
  const rows = matrix.rows.filter(r => String(r.name) === name);
  if (rows.length > 1) return "重复名称，查原表";
  if (!rows.length) return matrix.truncated ? "截断外" : "未列";
  return format(rows[0].value);
}
function engineNames(point: HistoryPoint) {
  if (point.status !== "available") return "—";
  if (point.engines_status === "empty") return "列入但暂无";
  if (point.engines_status === "not_in_scope") return "未覆盖";
  if (!point.engines?.rows.length) return "未列名单";
  const index = point.engines.columns.indexOf("股票");
  return index < 0 ? "有明细，见原列" : point.engines.rows.slice(0, 3).map(row => format(row[index])).join("、");
}

/** A window is pinned independently of the day cursor. The same response is exported for AI review. */
export function ReviewHistory({ initialEnd, selectedDate, onSelect, onOpenReport, refreshToken = 0 }: {
  initialEnd: string | null; selectedDate: string | null; refreshToken?: number;
  onSelect: (date: string) => void; onOpenReport: (date: string) => void;
}) {
  const pinnedIndustry = useRef("");
  const [end, setEnd] = useState(initialEnd ?? "");
  const [days, setDays] = useState(20);
  const [industry, setIndustry] = useState("");
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<History | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState("double_red");
  const [expanded, setExpanded] = useState(false);
  const [localSelected, setLocalSelected] = useState<string | null>(selectedDate);
  useEffect(() => { setLocalSelected(selectedDate); }, [selectedDate]);
  useEffect(() => {
    const effectiveIndustry = industry || pinnedIndustry.current;
    const controller = new AbortController();
    setData(null); setError(null);
    const params = new URLSearchParams({ days: String(days) });
    if (end) params.set("end", end);
    if (effectiveIndustry) params.set("industry", effectiveIndustry);
    fetch(`/api/river/review-history?${params}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `连续复盘暂不可读（${response.status}）`);
      }
      const body = await response.json() as History;
      if (body.schema_version !== 1 || body.knowledge_mode !== "archived_report_not_as_known" || !Array.isArray(body.points) || body.requested_days !== days || (end && body.requested_end !== end) || (effectiveIndustry && body.industry !== effectiveIndustry)) throw new Error("连续复盘响应日期、行业或版本不一致，未展示错位数据。");
      if (!controller.signal.aborted) { pinnedIndustry.current = body.industry; setData(body); }
    }).catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [end, days, industry, revision, refreshToken]);
  const chosen = localSelected ?? selectedDate ?? data?.end ?? null;
  const point = data?.points.find(p => p.date === chosen);
  const select = (day: string) => { setLocalSelected(day); onSelect(day); };
  const names = [...new Set(data?.points.flatMap(p => p.matrices[mode]?.rows.map(r => String(r.name)) ?? []) ?? [])];
  const download = () => {
    if (!data) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify({ ...data, selected_date: chosen }, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `连续复盘-${data.start}-${data.end}.json`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  // "按最近归档选择" must really un-pin: otherwise the ref keeps re-sending the old industry.
  const chooseIndustry = (value: string) => {
    if (!value) { pinnedIndustry.current = ""; setRevision(v => v + 1); }
    setIndustry(value); setExpanded(false);
  };
  const changeWindow = (value: string) => { setEnd(value); setLocalSelected(value || null); if (value) onSelect(value); };
  const currentMode = modes.find(m => m.key === mode)!;
  return <section className="rh-workspace" aria-label="连续复盘工作区">
    <header className="rh-mast"><div><span className="rh-eyebrow">DAILY REVIEW · THROUGH TIME</span><h2>把每天的复盘，连起来看。</h2><p>先看变化，再回到当日依据。只读归档，不改写过去。</p></div><button type="button" onClick={() => setRevision(v => v + 1)}><RefreshCw size={14}/>刷新连续复盘</button></header>
    <div className="rh-controls"><label>窗口截止日<input type="date" aria-label="连续复盘截止日" value={end} onChange={e => changeWindow(e.target.value)} /></label><label>交易日窗口<select aria-label="连续复盘窗口" value={days} onChange={e => setDays(Number(e.target.value))}>{[5, 20, 40, 60].map(n => <option key={n} value={n}>{n} 个交易日</option>)}</select></label><label>固定观察行业<select aria-label="连续复盘行业" value={industry || data?.industry || ""} onChange={e => chooseIndustry(e.target.value)}><option value="">按最近归档选择</option>{industry && !data?.industries.includes(industry) && <option value={industry}>{industry}</option>}{data?.industries.map(name => <option key={name}>{name}</option>)}</select></label><button type="button" disabled={!data} onClick={download}><Download size={14}/>导出本窗证据 JSON</button></div>
    <div className="rh-boundary">归档视角 · 不是当时可知回放，也不是最新修订行情。点日期只移动光标，不改变整个窗口。导出保留同一份读数、来源与限制；不会自动发送给 AI。</div>
    {error && <div className="rh-error" role="alert">{error}<button type="button" onClick={() => setRevision(v => v + 1)}>重试连续复盘</button></div>}
    {!data && !error && <p role="status">正在对齐日报归档与计划交易日…</p>}
    {data && <>
      <ReviewReadingGuide data={data} selectedDate={chosen}/>
      <div className="rh-window"><b>{data.start} → {data.end}</b><span>归档可读 {data.coverage.available} / {data.coverage.total} 日</span><span>当前光标 {chosen ?? "未选"}</span>{!data.calendar_complete && <strong>部分前序日历未知，窗口未补造</strong>}</div>
      {data.requested_end !== data.end && <p className="rh-boundary" role="note">所选截止日 {data.requested_end} 不是已收盘的计划交易日，窗口止于此前最近的交易日 {data.end}；没有用其他日期的归档顶替。</p>}
      {chosen && !data.points.some(p => p.date === chosen) && <p className="rh-boundary" role="note">当前光标 {chosen} 不在本窗口内，下方读数不显示该日；请在表头点选窗口内的交易日。</p>}
      {!data.coverage.available && <p className="rh-empty">这个窗口没有可读的结构化日报。HTML 仍可在原导航台查看；这里不抓取 HTML 猜测数值。</p>}
      <div className="rh-metrics">{data.metrics.map(metric => <article key={metric.key}><span>{metric.label} <small>{metric.unit}</small></span><strong>{format(point?.metrics[metric.key])}</strong><Sparkline values={data.points.map(p => p.metrics[metric.key] ?? null)} selected={data.points.findIndex(p => p.date === chosen)}/><small>{point?.comparison_date && point.deltas[metric.key] != null ? `较 ${point.comparison_date.slice(5)} 差 ${format(point.deltas[metric.key])}${metric.unit === "%" ? " 个百分点" : ` ${metric.unit}`}` : "无可比前日或字段缺失"}</small></article>)}</div>
      <div className="rh-section-head"><h3>01 / 日报里的连续读数</h3><span>图中断点不补零 · 未列入不等于零 · 未知不判断顺位</span></div>
      <div className="rh-scroll" tabIndex={0} role="region" aria-label="连续读数横向滚动"><table className="rh-table"><thead><tr><th>指标 / 日期</th>{data.points.map(p => <th key={p.date} className={p.date === chosen ? "selected" : ""}><button type="button" aria-pressed={p.date === chosen} aria-label={`连续复盘选日 ${p.date}`} onClick={() => select(p.date)}>{p.date.slice(5)}</button></th>)}</tr></thead><tbody>
        <tr><th>归档覆盖</th>{data.points.map(p => <td key={p.date} className={p.status === "available" ? "" : "gap"}>{p.status === "available" ? "可读" : p.status === "missing" ? "缺归档" : "不可读"}</td>)}</tr>
        {data.metrics.map(m => <tr key={m.key}><th>{m.label}<small>{m.unit}</small></th>{data.points.map(p => <td key={p.date}>{format(p.metrics[m.key])}</td>)}</tr>)}
        <tr><th>当日成交前三行业</th>{data.points.map(p => <td key={p.date}>{p.top_industries.join(" / ") || "—"}</td>)}</tr>
        <tr><th>{data.industry || "所选行业"} · 榜内顺位</th>{data.points.map(p => <td key={p.date}>{p.industry_status === "ranked" ? `第 ${p.industry_rank}` : p.industry_status === "not_in_list" ? "未列入" : "未知"}</td>)}</tr>
        <tr><th>发动机名单 · 前3项</th>{data.points.map(p => <td key={p.date}>{engineNames(p)}</td>)}</tr>
      </tbody></table></div>
      <div className="rh-section-head"><h3>02 / {data.industry || "行业"} · 子板块轨迹</h3><div className="rh-tabs" role="group" aria-label="连续矩阵类型">{modes.map(m => <button type="button" aria-pressed={mode === m.key} key={m.key} onClick={() => { setMode(m.key); setExpanded(false); }}>{m.label}</button>)}</div></div>
      <p className="rh-muted">{currentMode.note}。每列只用当天报告的当天列，不以后来报告补旧值；原名相同不证明实体身份跨期一致。</p>
      <p className="rh-muted">单元格标记：未覆盖 = 当日不是重点行业，日报不生成该矩阵；无行 = 已入选但矩阵为空；未报 = 缺当日列；未列 = 当日矩阵有表但无此名称；缺档 = 无当日归档。均不等于零。</p>
      {names.length ? <><div className="rh-scroll" tabIndex={0} role="region" aria-label="连续子板块矩阵"><table className="rh-table"><thead><tr><th>原日报名称</th>{data.points.map(p => <th key={p.date}>{p.date.slice(5)}</th>)}</tr></thead><tbody>{names.slice(0, expanded ? undefined : 12).map(name => <tr key={name}><th>{name}</th>{data.points.map(p => { const value = matrixCell(p, mode, name); return <td key={p.date} className={p.matrices[mode]?.status === "available" && p.status === "available" ? "" : "gap"}>{value}</td>; })}</tr>)}</tbody></table></div>{names.length > 12 && <button type="button" onClick={() => setExpanded(v => !v)}>{expanded ? "收起子板块" : `展开 ${names.length} 行`}</button>}</> : <p className="rh-empty">这些归档没有所选行业的当日矩阵值，不表示该行业为零。</p>}
      <section className="rh-evidence" aria-label="连续复盘同日证据"><header><div><span className="rh-eyebrow">03 / BACK TO THE SOURCE</span><h3>{chosen ?? "请选择日期"} · 同日依据</h3></div>{chosen && <button type="button" onClick={() => onOpenReport(chosen)}>打开当日完整复盘 <ArrowUpRight size={14}/></button>}</header>
        {!point ? <p>所选日不在当前窗口，日期未被替换。请调整窗口或打开该日归档。</p> : point.status !== "available" ? <p>{point.status === "missing" ? "当日缺少结构化归档" : `当日归档不可读：${point.reason}`}，未用别的日期补位。</p> : <>
          <dl><div><dt>归档来源</dt><dd>{point.provenance?.source_path ?? "未知"}</dd></div><div><dt>报告形成时间</dt><dd>{point.provenance?.generated_at ?? "未知，不按交易日推定"}</dd></div><div><dt>内容 SHA256</dt><dd>{point.provenance?.sha256 ?? "未知"}</dd></div></dl>
          <p className="rh-muted">哈希用于核对版本，不证明来源真实或当时已知。差值只是原字段的算术差；公式历史版本未完整记录。</p>
          {point.engines?.rows.length ? <div className="rh-scroll"><table className="rh-table"><caption>{data.industry} · 当日发动机原表</caption><thead><tr>{point.engines.columns.map((c, i) => <th key={i}>{c}</th>)}</tr></thead><tbody>{point.engines.rows.map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{format(v)}</td>)}</tr>)}</tbody></table></div> : <p>{ENGINE_NOTE[point.engines_status ?? "unknown"] ?? "归档未列出该行业发动机名单，不以其他行业补位。"}</p>}
          {(point.engines?.truncated || Object.values(point.matrices).some(m => m.truncated)) && <p>部分表格达到返回行数上限，请打开当日完整复盘核对全部行。</p>}
          {point.warnings.length > 0 && <details><summary>当日报告提示 · {point.warnings.length} 条</summary><ul>{point.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></details>}
        </>}
      </section>
      <details className="rh-method"><summary>数据口径、AI消费与限制</summary><ul>{data.notes.map(note => <li key={note}>{note}</li>)}</ul><p>指标来源：{data.metrics.map(m => m.source_field).join("、")}。接口 /api/river/review-history 与导出使用同一份结构化结果；本页不调用模型、不写观察台账。</p></details>
    </>}
  </section>;
}
