import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, BookOpen, ChevronDown, CircleHelp, Layers3, Radio } from "lucide-react";
import type { EntityHit } from "../../river/types";
import type { SectorSeries } from "../../river/dailyTypes";
import type { MatrixMode, ReviewBlock, ReviewCell, ReviewSnapshot } from "../../river/reviewTypes";
import "../../riverReview.css";

const modes: { key: MatrixMode; label: string; subtitle: string }[] = [
  { key: "double_red", label: "双红矩阵", subtitle: "涨幅 / 边际量 / 成交额亿" },
  { key: "stock_highs", label: "120日新高", subtitle: "当日120日新高去重个股数 · 原日报题材映射" },
  { key: "limit_up", label: "涨停矩阵", subtitle: "子板块成分股当日涨停去重个股数" },
];
const cell = (v: ReviewCell | undefined) => v == null || v === "-" || v === "" ? "—" : String(v);
const clean = (text?: string) => (text ?? "").replace(/\*\*/g, "");
const number = (facts: Record<string, unknown>, key: string) => typeof facts[key] === "number" && Number.isFinite(facts[key]) ? facts[key] as number : null;
const nf = (n: number | null, digits = 1) => n == null ? "—" : n.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

function ArchiveBlock({ block }: { block: ReviewBlock }) {
  if (block.kind === "table") return <div className="rv-archive-table">{block.title && <h5>{block.title}</h5>}<div className="rv-scroll"><table><thead><tr>{block.columns?.map((c, i) => <th key={i}>{c}</th>)}</tr></thead><tbody>{block.rows?.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{cell(v)}</td>)}</tr>)}</tbody></table></div></div>;
  if (block.kind === "heading") return <h4>{clean(block.text)}</h4>;
  if (block.kind === "chart") return <p className="rv-muted">原日报的图片未嵌入此视图；涨家数 MA5 与波段数据见本节表格。</p>;
  return <p className={block.kind === "conclusion" ? "rv-archive-conclusion" : ""}>{clean(block.text)}</p>;
}

type Props = {
  date: string; revision?: number; sectors: SectorSeries[]; marketDates: string[];
  onDate: (date: string) => void; onResearch?: (entity: EntityHit, date: string) => void;
  onSelectSector?: (sector: SectorSeries) => void;
  onAttention?: (sector: SectorSeries | null, date: string) => void;
};

/** A navigable projection of the canonical report, not a second metric engine. */
export function DailyReviewWorkspace({ date, revision = 0, sectors, marketDates, onDate, onResearch, onSelectSector, onAttention }: Props) {
  const [snapshot, setSnapshot] = useState<ReviewSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [industry, setIndustry] = useState<string | null>(null);
  const [mode, setMode] = useState<MatrixMode>("double_red");
  const [selectedRow, setSelectedRow] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [allStocks, setAllStocks] = useState(false);
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const [fullReport, setFullReport] = useState(false);
  const matrixScroll = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    setSnapshot(null); setError(null); setSelectedStock(null);
    fetch(`/api/river/daily-review?as_of=${encodeURIComponent(date)}`, { signal: controller.signal })
      .then(async response => {
        const body = await response.json() as ReviewSnapshot & { detail?: string };
        if (!response.ok) throw new Error(body.detail || `日报读取失败（${response.status}）`);
        if (body.schema_version !== 1 || body.trade_date !== date || !["available", "missing"].includes(body.status) || (body.status === "available" && !body.report)) throw new Error("日报响应与所选日期不一致或版本不兼容；没有显示其他日期的数据。");
        if (!controller.signal.aborted) setSnapshot(body);
      })
      .catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [date, revision, retry]);
  const data = snapshot?.trade_date === date ? snapshot : null;
  const report = data?.report;
  const activeIndustry = report?.industries.includes(industry ?? "") ? industry! : report?.industries[0] ?? "";
  const activeMode = modes.find(m => m.key === mode)!;
  const matrix = report?.matrices[mode].find(m => m.industry === activeIndustry);
  useEffect(() => {
    const scroller = matrixScroll.current;
    const column = scroller?.querySelector<HTMLTableCellElement>("thead .selected-date");
    if (scroller && column) scroller.scrollLeft = Math.max(0, column.offsetLeft - scroller.clientWidth + column.offsetWidth + 8);
  }, [date, activeIndustry, mode, data]);
  const currentColumn = (matrix?.dates.indexOf(date) ?? -1) + 1;
  const chosenRow = matrix?.rows.find(r => String(r[0]) === selectedRow);
  const dateIndex = marketDates.indexOf(date);
  const resolve = (name: string): SectorSeries | null => {
    const matches = sectors.filter(s => s.name === name && dateIndex >= 0 && s.points[dateIndex] != null);
    return matches.length === 1 ? matches[0] : null;
  };
  const chosenSector = chosenRow ? resolve(String(chosenRow[0])) : null;
  const pick = (name: string) => { setSelectedRow(name); const match = resolve(name); if (match) onSelectSector?.(match); };
  const research = (sector: SectorSeries) => onResearch?.({ id: sector.id, name: sector.name, amount: sector.points[dateIndex]?.[1] ?? null, pct_chg: sector.points[dateIndex]?.[0] ?? null }, date);
  const facts = report?.facts ?? {};
  const concentration = report?.sections.find(s => s.id === "concentration")?.blocks.find(b => b.kind === "table");
  const today = concentration?.rows?.find(r => r[0] === "今日");
  const yesterday = concentration?.rows?.find(r => r[0] === "昨日");
  const priorShare = (name: string) => {
    for (let i = 1; i <= 3; i++) {
      const nameIndex = concentration?.columns?.indexOf(`行业${i}`) ?? -1;
      const shareIndex = concentration?.columns?.indexOf(`占比${i}`) ?? -1;
      if (yesterday && nameIndex >= 0 && shareIndex >= 0 && yesterday[nameIndex] === name) return cell(yesterday[shareIndex]);
    }
    return "未列入昨日前三";
  };
  const leaders = [1, 2, 3].flatMap(i => {
    const ni = concentration?.columns?.indexOf(`行业${i}`) ?? -1;
    const pi = concentration?.columns?.indexOf(`占比${i}`) ?? -1;
    return today && ni >= 0 && pi >= 0 && today[ni] ? [{ name: String(today[ni]), share: cell(today[pi]) }] : [];
  });
  const totalShare = number(facts, "top3_industry_ratio");
  const delta = number(facts, "top3_industry_ratio_delta_pp");
  const engine = report?.engines.find(e => e.industry === activeIndustry);
  const stock = engine?.rows.find(r => String(r[2]) === selectedStock);
  const changeIndustry = (name: string) => { setIndustry(name); setSelectedRow(null); setSelectedStock(null); setExpanded(false); setAllStocks(false); };

  return <section className="rv-workspace" aria-label="原日报复盘工作区">
    <header className="rv-header"><div><div className="rv-eyebrow">DAILY REVIEW / 原有复盘口径</div><h2>资金去向与持续性<span>从行业，到子板块，再到个股。</span></h2></div><span className="rv-source-pill"><BookOpen size={13}/> {date} 日报</span></header>
    {error && <div className="rv-state rv-error" role="alert"><b>日报暂不可读</b><p>{error}</p><button type="button" onClick={() => setRetry(n => n + 1)}>重试日报</button></div>}
    {!data && !error && <div className="rv-state" role="status">正在读取 {date} 的原始复盘归档…</div>}
    {data?.status === "missing" && <div className="rv-state"><h3>这一天尚无结构化日报归档</h3><p>{data.message}</p><p>下方行情扫描仍可使用。已有日报：</p><div className="rv-date-links">{data.available_dates.map(d => <button type="button" key={d} onClick={() => onDate(d)}>{d}</button>)}{!data.available_dates.length && <span>尚未发现归档。请通过原 daily-full 流程生成，网页不会触发生产写入。</span>}</div></div>}
    {report && <>
      <div className="rv-summary">
        <article className="rv-concentration"><div className="rv-label">成交集中度 <small>前三行业合计</small></div><strong>{nf(totalShare)}<em>%</em></strong><p>较昨日 <b>{delta == null ? "—" : `${delta > 0 ? "+" : ""}${nf(delta, 2)}`} 个百分点</b><span>{String(facts.concentration_state ?? "状态缺失")}</span></p><div className="rv-share-track" aria-label={`前三行业成交占比 ${nf(totalShare)}%`}>{totalShare != null && <i style={{ width: `${Math.max(0, Math.min(100, totalShare))}%` }}/>}</div></article>
        <div className="rv-leaders">{leaders.map((item, i) => <button type="button" key={item.name} className={activeIndustry === item.name ? "active" : ""} aria-label={`聚焦${item.name}行业`} aria-pressed={activeIndustry === item.name} onClick={() => changeIndustry(item.name)}><span className="rv-rank">0{i + 1}</span><span><b>{item.name}</b><small>昨日 {priorShare(item.name)}</small></span><strong>{item.share}</strong><ArrowUpRight size={15}/></button>)}{!leaders.length && <p className="rv-muted">本日报未提供成交前三行业明细。</p>}</div>
        <div className="rv-context"><div><span>周均线偏离度</span><b>{nf(number(facts, "sh_deviation_pct"), 2)}%</b></div><div><span>相对20日均量</span><b>{nf(number(facts, "volume_ratio"))}%</b></div><div><span>涨家数 MA5</span><b>{nf(number(facts, "advancers_ma5"))}</b></div><p>{String(facts.ma5_position ?? "位置缺失")} · {String(facts.ma5_trend ?? "趋势缺失")}<small>MA5 为5日均值，不是当日涨家数。</small></p></div>
      </div>
      <div className="rv-matrix-card">
        <div className="rv-matrix-head"><div><span className="rv-eyebrow">01 / 行业内的连续观察</span><h3>近15日复盘矩阵</h3></div><div className="rv-counts"><span>今日双红 <b>{nf(number(facts, "double_red_count"), 0)}</b></span><span>单红 <b>{nf(number(facts, "single_red_count"), 0)}</b></span><span>120日新高 <b>{nf(number(facts, "stock_high_120d_count"), 0)}</b></span></div></div>
        <div className="rv-controls"><nav className="rv-mode-tabs" aria-label="复盘矩阵类型">{modes.map(m => <button type="button" key={m.key} aria-pressed={mode === m.key} onClick={() => { setMode(m.key); setExpanded(false); setSelectedRow(null); }}>{m.label}</button>)}</nav><div className="rv-industries" aria-label="复盘行业分组">{report.industries.map(name => <button type="button" key={name} aria-pressed={activeIndustry === name} onClick={() => changeIndustry(name)}>{name}</button>)}</div></div>
        <div className="rv-matrix-caption"><b>{activeIndustry || "行业缺失"}</b><span>{activeMode.subtitle}</span><small>{matrix?.rows.length ?? 0} 行 · 按原日报顺序</small></div>
        {matrix?.rows.length ? <><div className="rv-scroll rv-matrix-scroll" ref={matrixScroll}><table className="rv-matrix" aria-label={`${activeIndustry} ${activeMode.label}`}><thead><tr><th>子板块 / 参照</th>{matrix.dates.map(d => <th key={d} className={d === date ? "selected-date" : ""}><button type="button" aria-label={`复盘切换至 ${d}`} onClick={() => onDate(d)}>{d.slice(5)}{d === date && <span>当前</span>}</button></th>)}</tr></thead><tbody>{matrix.rows.slice(0, expanded ? undefined : 10).map((row, i) => {
          const reference = mode === "double_red" && (String(row[0]).startsWith("申万一级：") || String(row[0]).startsWith("上证指数"));
          return <tr key={`${row[0]}-${i}`} className={`${reference ? "rv-reference" : ""} ${chosenRow === row ? "selected-row" : ""}`}><th title={cell(row[0])}>{reference ? cell(row[0]) : <button type="button" onClick={() => pick(String(row[0]))} aria-pressed={chosenRow === row}>{cell(row[0])}</button>}</th>{matrix.dates.map((d, j) => {
            const value = row[j + 1], hot = typeof value === "string" && value.includes("🔥");
            return <td key={d} className={`${d === date ? "selected-date" : ""} ${value == null || value === "-" ? "rv-missing" : ""} ${hot ? "rv-hot" : ""}`}><button type="button" aria-label={`${cell(row[0])} ${d} ${cell(value)}`} style={typeof value === "number" && value > 0 ? { backgroundColor: `rgba(76,128,109,${Math.min(.44, .05 + value * .015)})` } : undefined} onClick={() => { if (!reference) { setSelectedRow(String(row[0])); if (d === date) pick(String(row[0])); } onDate(d); }}>{cell(value)}</button></td>;
          })}</tr>;
        })}</tbody></table></div>{matrix.rows.length > 10 && <button type="button" className="rv-expand" onClick={() => setExpanded(v => !v)}>{expanded ? "收起矩阵" : `展开全部 ${matrix.rows.length} 行`}<ChevronDown size={13}/></button>}</> : <div className="rv-matrix-empty"><Layers3 size={24}/><h4>本归档未提供该行业的可用矩阵行</h4><p>{mode === "stock_highs" ? `当日全市场120日新高为 ${nf(number(facts, "stock_high_120d_count"), 0)} 只；行业／题材映射缺失，不表示该行业为零。可在完整日报的“120日新高”一节查看分布。` : "可能是窗口内未列出符合口径的子板块，也可能存在覆盖缺口。请结合完整日报的数据覆盖检查，不补造数值。"}</p></div>}
        <div className="rv-matrix-legend">{mode === "double_red" ? <><span>🔥 涨幅 &gt; 0、边际量 &gt; 10、成交额 &gt; 500亿</span><span>母行业：成交占比 / 涨幅</span><span>上证：120日均量比 / 涨幅</span></> : <span>行口径沿用日报；不同子板块可能包含同一只股票，不能把各行相加当作全市场总数。</span>}<span>— 原报告未列值，不补 0</span><span>左右滑动看历史 · 点击日期联动</span></div>
        {chosenRow && <div className="rv-row-detail"><div><span className="rv-eyebrow">所选子板块 · {date}</span><h4>{cell(chosenRow[0])}<code>{currentColumn > 0 ? cell(chosenRow[currentColumn]) : "所选日不在矩阵内"}</code></h4><p>{chosenSector ? `同日唯一板块映射：${chosenSector.id}` : "未找到同日唯一板块代码；保留原名，不猜测映射。"}</p></div><div className="rv-row-actions"><button type="button" disabled={!chosenSector || !onResearch} onClick={() => chosenSector && research(chosenSector)}>板块六轨 <ArrowUpRight size={14}/></button><button type="button" disabled={!chosenSector || !onAttention} onClick={() => chosenSector && onAttention?.(chosenSector, date)}><Radio size={14}/> 同日公开消息</button></div></div>}
      </div>
      <div className="rv-engine-card"><div className="rv-matrix-head"><div><span className="rv-eyebrow">02 / 谁在推动这个行业</span><h3>{activeIndustry} · 个股发动机</h3></div><span className="rv-formula">√ 成交额亿 × 当日涨幅</span></div><p className="rv-engine-note">成交占比前三行业的当日开根加权 Top20 · 与新高、双红交叉观察；不是近五日加权榜，也不代表个股因果归因。</p>
        {engine?.rows.length ? <><div className="rv-scroll"><table className="rv-engine" aria-label={`${activeIndustry} 个股发动机`}><thead><tr>{engine.columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{engine.rows.slice(0, allStocks ? undefined : 8).map((row, i) => <tr key={`${row[2]}-${i}`} className={stock === row ? "selected-row" : ""}>{row.map((value, j) => <td key={j} className={j === 3 ? String(value).startsWith("-") ? "rv-negative" : "rv-positive" : ""}>{j === 1 ? <button type="button" aria-label={`查看${cell(value)}发动机明细`} onClick={() => setSelectedStock(String(row[2]))}>{cell(value)}</button> : j === 6 && value !== "否" && value !== "-" ? <span className="rv-high-badge">{cell(value)}</span> : cell(value)}</td>)}</tr>)}</tbody></table></div>{engine.rows.length > 8 && <button type="button" className="rv-expand" onClick={() => setAllStocks(v => !v)}>{allStocks ? "收起个股" : `查看全部 ${engine.rows.length} 只发动机`}<ChevronDown size={13}/></button>}</> : <div className="rv-state">本归档没有该行业的个股发动机名单；不拿其他行业补位。</div>}
        {stock && <div className="rv-stock-detail" role="region" aria-label="个股发动机明细"><div><span className="rv-eyebrow">{date} · {activeIndustry}</span><h4>{cell(stock[1])} <code>{cell(stock[2])}</code></h4></div><dl><div><dt>当日涨幅</dt><dd>{cell(stock[3])}</dd></div><div><dt>成交额</dt><dd>{cell(stock[4])}</dd></div><div><dt>开根加权</dt><dd>{cell(stock[5])}</dd></div><div><dt>新高状态</dt><dd>{cell(stock[6])}</dd></div><div><dt>命中双红</dt><dd>{cell(stock[7])}</dd></div></dl><p>双红题材：{cell(stock[8])}。以上是归档事实层对比，不把加权排名当作买入信号。</p></div>}
      </div>
      <details className="rv-quality"><summary><CircleHelp size={14}/> 数据口径与归档提示 <span>{report.diagnostics.length + report.warnings.length} 条</span></summary><ul>{[...report.diagnostics, ...report.warnings].map((note, i) => <li key={i}>{note}</li>)}<li>“缩量普涨”等赚钱效应描述是滚动窗口派生结论，不等于所选日普涨；完整日报保留其窗口说明。</li><li>成交集中度使用日报摘要；矩阵中的母行业占比保留各自原始缺失值，不做混源补齐。</li></ul></details>
      <div className="rv-archive-footer"><div><b><BookOpen size={14}/> 同一份 daily，换一种阅读方式</b><p>数据日 {date} · 生成于 {data?.provenance?.generated_at ?? "时间缺失"}</p><small>{data?.provenance?.note}</small></div><button type="button" aria-expanded={fullReport} onClick={() => setFullReport(v => !v)}>{fullReport ? "收起完整日报" : `展开完整日报 · ${report.sections.length} 章节`}<ChevronDown size={14}/></button></div>
      {fullReport && <div className="rv-full-report" aria-label="完整日报归档"><p className="rv-source-path">来源：{data?.provenance?.source_path} · 原始表格与结论，非重新生成。图片另见原 HTML；请结合上方口径提示核对结论。</p>{report.sections.map(section => <details key={section.id}><summary>{String(section.index).padStart(2, "0")} / {section.title}</summary><div className="rv-archive-section">{section.blocks.map((block, i) => <ArchiveBlock key={i} block={block}/>)}</div></details>)}</div>}
    </>}
  </section>;
}
