import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, CalendarDays, ChevronLeft, ChevronRight, CircleHelp, Layers3, Radio, RefreshCw, Search, TrendingUp, Waves } from "lucide-react";
import type { AttentionSnapshot, DailyMarket, DailyOverview, SectorSeries } from "../../river/dailyTypes";
import type { EntityHit } from "../../river/types";
import "../../riverDaily.css";
import { contiguousReturn, heatColor } from "../../river/dailyMath";
import { DailyReviewWorkspace } from "./DailyReviewWorkspace";

type Props = { focusDate?: string | null; onFocusDate?: (date: string) => void; onResearch?: (entity: EntityHit, date: string) => void };
type Tab = "rotation" | "ranking" | "attention";
const fmt = (n: number | null | undefined, digits = 0) => n == null || !Number.isFinite(n) ? "—" : n.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const pct = (n: number | null | undefined) => n == null ? "—" : `${n > 0 ? "+" : ""}${fmt(n, 2)}%`;
const sign = (n: number | null | undefined) => n == null ? "muted" : n > 0 ? "up" : n < 0 ? "down" : "flat";
const short = (d: string) => d.slice(5).replace("-", "/");
async function get<T>(url: string, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail || `读取失败（${res.status}），请确认新版后端已启动。`);
  }
  return res.json() as Promise<T>;
}

function IndexChart({ days, selected, onSelect }: { days: DailyMarket[]; selected: string; onSelect: (date: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  const display = days.find(d => d.date === (hover ?? selected)) ?? days[days.length - 1];
  const vals = days.flatMap(d => [d.sh_index_low, d.sh_index_high, d.sh_index_close, d.ma5, d.ma20]).filter((v): v is number => v != null && Number.isFinite(v));
  if (!vals.length) return <div className="dr-empty">此窗口没有可用指数价格，不绘制虚构 K 线。</div>;
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const width = 1040, right = 62, left = 12, inner = width - left - right, step = inner / days.length;
  const y = (v: number) => 34 + (max + span * .10 - v) / (span * 1.2) * 150;
  const x = (i: number) => left + step * (i + .5);
  const volumeMax = Math.max(1, ...days.map(d => d.total_amount ?? 0));
  const path = (field: "ma5" | "ma20") => {
    let active = false;
    return days.map((d, i) => {
      if (d[field] == null) { active = false; return ""; }
      const part = `${active ? "L" : "M"}${x(i)},${y(d[field]!)}`;
      active = true; return part;
    }).join(" ");
  };
  return <div className="dr-chart" onMouseLeave={() => setHover(null)}>
    <div className="dr-ohlc"><b>{display.date}</b><span>开 <em>{fmt(display.sh_index_open, 2)}</em></span><span>高 <em>{fmt(display.sh_index_high, 2)}</em></span><span>低 <em>{fmt(display.sh_index_low, 2)}</em></span><span>收 <em className={sign(display.sh_index_pct_chg)}>{fmt(display.sh_index_close, 2)}</em></span><span className="dr-ma5">MA5 {fmt(display.ma5, 2)}</span><span className="dr-ma20">MA20 {fmt(display.ma20, 2)}</span></div>
    <svg viewBox={`0 0 ${width} 275`} role="img" aria-label="上证指数日 K 线、5日和20日均线，以及全市场成交额">
      {[0, .33, .66, 1].map(v => <g key={v}><line x1={left} x2={width - right} y1={y(min + v * span)} y2={y(min + v * span)} className="dr-grid-line"/><text x={width - right + 10} y={y(min + v * span) + 4} className="dr-axis">{fmt(min + v * span)}</text></g>)}
      {days.map((d, i) => {
        const o = d.sh_index_open, c = d.sh_index_close, h = d.sh_index_high, l = d.sh_index_low;
        const color = o != null && c != null ? (c >= o ? "#ce6353" : "#389277") : "#aab0aa";
        return <g key={d.date}>
          {d.date === selected && <rect x={left + i * step} y="18" width={step} height="239" fill="#d8d3c7" opacity=".3"/>}
          {o != null && c != null && h != null && l != null ? <><line x1={x(i)} x2={x(i)} y1={y(h)} y2={y(l)} stroke={color}/><rect x={x(i) - Math.min(8, step * .27)} y={Math.min(y(o), y(c))} width={Math.min(16, step * .54)} height={Math.max(1.5, Math.abs(y(o) - y(c)))} fill={color} rx="1"/></> : c != null ? <circle cx={x(i)} cy={y(c)} r="2" fill={color}/> : null}
          {d.total_amount != null && <rect x={x(i) - step * .29} y={250 - d.total_amount / volumeMax * 37} width={step * .58} height={d.total_amount / volumeMax * 37} fill={color} opacity=".5" rx="1"/>}
          {(i === 0 || i === days.length - 1 || i % Math.max(1, Math.floor(days.length / 7)) === 0) && <text x={x(i)} y="270" className="dr-axis" textAnchor="middle">{short(d.date)}</text>}
        </g>;
      })}
      <path d={path("ma5")} stroke="#c5a14d" strokeWidth="1.5" fill="none"/><path d={path("ma20")} stroke="#7984b6" strokeWidth="1.5" fill="none"/>
      <text x={width - right + 10} y="226" className="dr-axis">成交额</text><text x={width - right + 10} y="242" className="dr-axis">亿元</text>
      {days.map((d, i) => <rect key={`hit-${d.date}`} x={left + i * step} y="15" width={step} height="243" fill="transparent" role="button" tabIndex={0} aria-label={`查看 ${d.date} 市场`} onFocus={() => setHover(d.date)} onBlur={() => setHover(null)} onMouseEnter={() => setHover(d.date)} onClick={() => onSelect(d.date)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(d.date); } }}><title>{d.date} 上证 {fmt(d.sh_index_close, 2)} / {pct(d.sh_index_pct_chg)}</title></rect>)}
    </svg>
  </div>;
}

export function AttentionPanel({ date, sector, onClear }: { date: string; sector: Pick<SectorSeries, "id" | "name"> | null; onClear: () => void }) {
  const [data, setData] = useState<AttentionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(null);
    const q = new URLSearchParams({ as_of: date });
    if (sector) q.set("entity_id", sector.id);
    get<AttentionSnapshot>(`/api/river/opinion-attention?${q}`, controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [date, sector]);
  return <div className="dr-attention">
    <div className="dr-section-head"><div><h3><Radio size={17}/> 公开消息传播 <small>{sector?.name ?? "全部已映射方向"}</small></h3><p>近 48 小时传播 · 截至所选日当时已入库的证据；不混入事后补采。</p></div>{sector && <button type="button" onClick={onClear}>查看全部方向</button>}</div>
    <div className="dr-attention-principles"><span>01 原文可追溯</span><span>02 同源不重复计数</span><span>03 热度 ≠ 事实硬度</span><span>04 研报覆盖独立保留</span></div>
    {error && <div className="dr-error" role="alert">{error}</div>}
    {!data && !error && <div className="dr-empty">读取当时可见的舆论记录…</div>}
    {data && (data.collection_status === "not_connected" ? <div className="dr-attention-empty"><div className="dr-radio-mark"><Radio size={28}/></div><h3>数据接口已就绪，等待真实信源。</h3><p>尚未导入 AIHOT 原始条目，因此这里不显示模拟热度。<br/>现有研报覆盖与卖方观点库保持原样，不被新闻热度替代。</p><span className="dr-chip">付费采集未开启</span><span className="dr-chip">不调用模型</span><p>真实信源接入后才会展示传播记录；当前研报覆盖可在板块六轨中查看。</p></div> : <>
      <div className="dr-attention-status"><b>{data.visible_observations} 条当时可见记录</b><span>{data.event_count} 个近48小时事件／待归组条目</span><span>导入快照，非全网覆盖</span></div>
      {!data.events.length && <div className="dr-empty">当前日期与板块下没有当时可见的近48小时记录。不是“市场没有讨论”。</div>}
      {data.events.map(event => <article className="dr-event" key={event.id}><div className="dr-event-top"><span className="dr-chip">{event.grouping === "reviewed" ? "已复核归组" : "待事件归组"}</span><span>事实待核验</span><strong>{event.heat == null ? "热度待核" : `观察热度 ${fmt(event.heat, 2)}`}</strong></div><h4>{event.title}</h4><p>{event.report_count} 篇记录 · {event.participant_count} 个已归一来源 · {event.lineage_complete ? "转载血缘已映射" : "转载血缘待核"} · 不判升降温</p><ul>{event.sources.map((source, i) => <li key={`${source.url}-${i}`}><a href={source.url} target="_blank" rel="noreferrer">{source.source_name || "未知来源"} ↗</a><span>发布 {source.published_at.slice(0, 10)} / 入库 {source.recorded_at.slice(0, 10)}</span></li>)}</ul></article>)}
      {data.truncated && <p className="dr-note">仅展示前100项；不是完整事件全集。</p>}
    </>)}
    {data && <p className="dr-note"><CircleHelp size={13}/>{data.gaps.join(" ")}</p>}
  </div>;
}

export function DailyRiverDashboard({ focusDate = null, onFocusDate, onResearch }: Props) {
  const [windowDays, setWindowDays] = useState(20);
  const [anchor, setAnchor] = useState<string | null>(null);
  const [data, setData] = useState<DailyOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string | null>(focusDate);
  const [sectorKey, setSectorKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("amount");
  const [limit, setLimit] = useState(24);
  const [tab, setTab] = useState<Tab>("rotation");
  const [metric, setMetric] = useState<"pct" | "amount">("pct");
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null); setData(null);
    const q = new URLSearchParams({ days: String(windowDays) });
    if (anchor) q.set("end", anchor);
    get<DailyOverview>(`/api/river/daily-overview?${q}`, controller.signal)
      .then(res => { setData(res); setSelected(current => current ?? res.end ?? null); })
      .catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [windowDays, anchor, revision]);
  useEffect(() => {
    if (!focusDate) return;
    setSelected(focusDate);
    if (data && data.days.length && !data.days.some(d => d.date === focusDate) && data.calendar.includes(focusDate)) setAnchor(focusDate);
  }, [focusDate, data]);
  const selectDay = (date: string) => {
    setSelected(date); onFocusDate?.(date);
    if (data && !data.days.some(d => d.date === date)) setAnchor(date);
  };
  // No silent fallback to the first or latest day: an absent date stays absent and is disclosed.
  const foundIndex = data?.days.findIndex(d => d.date === selected) ?? -1;
  const index = Math.max(0, foundIndex);
  const day = foundIndex >= 0 ? data?.days[foundIndex] ?? null : null;
  const sector = data?.sectors.find(s => s.key === sectorKey) ?? null;
  const point = sector?.points[index] ?? null;
  const calendarIndex = data?.calendar.indexOf(day?.date ?? "") ?? -1;
  const filtered = useMemo(() => {
    if (!data) return [];
    const filteredRows = data.sectors.filter(s => (!query || s.name.includes(query) || s.id.includes(query)) && s.points[index] != null);
    return filteredRows.sort((a, b) => {
      const av = sort === "five" ? contiguousReturn(a.points, index) : a.points[index]?.[sort === "amount" ? 1 : 0] ?? null;
      const bv = sort === "five" ? contiguousReturn(b.points, index) : b.points[index]?.[sort === "amount" ? 1 : 0] ?? null;
      if (av == null) return bv == null ? a.name.localeCompare(b.name, "zh-CN") : 1;
      if (bv == null) return -1;
      return sort === "losers" ? av - bv : bv - av;
    });
  }, [data, index, query, sort]);
  const dateToday = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date());
  const research = (s: SectorSeries) => { if (day) onResearch?.({ id: s.id, name: s.name, amount: s.points[index]?.[1] ?? null, pct_chg: s.points[index]?.[0] ?? null }, day.date); };
  const rows = filtered.slice(0, limit);
  const pickRank = (id: string, name: string) => setSectorKey(data?.sectors.find(s => s.id === id && s.name === name)?.key ?? null);
  return <section className="dr" aria-label="每日市场记忆长河">
    <div className="dr-mast"><div><div className="dr-eyebrow"><span/> MARKET MEMORY · A-SHARE</div><h1>时间记忆长河<span>看见市场，如何走到今天。</span></h1></div><button className="dr-refresh" type="button" onClick={() => setRevision(v => v + 1)} disabled={loading}><RefreshCw size={14} className={loading ? "dr-spinning" : ""}/>{loading ? "读取中" : "刷新数据"}</button></div>
    <div className="dr-datebar"><div className="dr-datenav"><CalendarDays size={16}/><button type="button" aria-label="上一交易日" disabled={!data || calendarIndex <= 0} onClick={() => data && selectDay(data.calendar[calendarIndex - 1])}><ChevronLeft size={15}/></button><select aria-label="当前交易日" value={day?.date ?? ""} onChange={e => selectDay(e.target.value)}>{!data?.calendar.length && <option value="">读取日期…</option>}{data?.calendar.slice().reverse().map(d => <option key={d} value={d}>{d}</option>)}</select><button type="button" aria-label="下一交易日" disabled={!data || calendarIndex < 0 || calendarIndex >= data.calendar.length - 1} onClick={() => data && selectDay(data.calendar[calendarIndex + 1])}><ChevronRight size={15}/></button><span className="dr-chip">交易日联动</span></div><div className="dr-window">{[10, 20, 40, 60].map(n => <button type="button" aria-pressed={windowDays === n} className={windowDays === n ? "active" : ""} key={n} onClick={() => setWindowDays(n)}>{n} 日</button>)}<button type="button" onClick={() => { setAnchor(null); if (data?.latest_market_date) selectDay(data.latest_market_date); }}>最新</button></div></div>
    {data?.latest_market_date && data.latest_market_date < dateToday && <div className="dr-freshness"><span className="dr-status-dot"/>最新盘面：{data.latest_market_date} · 板块：{data.latest_sector_date ?? "无"}<span>历史收盘快照，不是实时行情</span></div>}
    {error && <div className="dr-error" role="alert">{error}<button type="button" onClick={() => setRevision(v => v + 1)}>重新读取</button></div>}
    {loading && <div className="dr-loading"><Waves size={24}/><b>正在对齐指数、板块与交易日…</b><p>只读本地事实库，不调用模型</p></div>}
    {data && data.days.length > 0 && selected && foundIndex < 0 && !loading && <div className="dr-empty" role="status">所选日 {selected} 不在当前窗口的数据中（可能缺档）；未替换为其他日期。</div>}
    {data && !data.days.length && <div className="dr-empty">当前范围没有交易日数据。{data.gaps.join(" ")}</div>}
    {day && data && <>
      <div className="dr-kpis">
        <div className="dr-kpi"><span>上证指数 <small>000001.SH</small></span><strong className={sign(day.sh_index_pct_chg)}>{fmt(day.sh_index_close, 2)}</strong><div className={sign(day.sh_index_pct_chg)}>{day.sh_index_pct_chg != null && (day.sh_index_pct_chg >= 0 ? <ArrowUpRight size={15}/> : <ArrowDownRight size={15}/>)}{pct(day.sh_index_pct_chg)}<small>当日涨跌</small></div></div>
        <div className="dr-kpi"><span>全市场成交额 <small>亿元</small></span><strong>{fmt(day.total_amount, 2)}</strong><div className={sign(day.amount_vs_yesterday_pct)}>较上一交易日 {pct(day.amount_vs_yesterday_pct)}</div></div>
        <div className="dr-kpi"><span>市场广度 <small>上涨家数</small></span><strong>{fmt(day.advancers)}<small>家</small></strong><div>涨停 <b className="up">{fmt(day.limit_up)}</b><i/>跌停 <b className="down">{fmt(day.limit_down)}</b></div></div>
        <div className="dr-kpi"><span>板块温度 <small>{day.sector_valid_count} 个有效读数</small></span><strong><b className="up">{day.sector_up_count}</b><small>涨 /</small><b className="down">{day.sector_down_count}</b><small>跌</small></strong><div className="dr-breadth"><i style={{ width: `${day.sector_up_count / Math.max(1, day.sector_valid_count) * 100}%` }}/><em style={{ width: `${day.sector_down_count / Math.max(1, day.sector_valid_count) * 100}%` }}/></div></div>
      </div>
      <div className="dr-top-grid"><div className="dr-card dr-index"><div className="dr-section-head"><div><h3><TrendingUp size={17}/> 指数与市场环境</h3><p>上证日 K 线 · 均线 · 成交额，共用同一个日期</p></div><span className="dr-phase">{day.market_stage?.replace("阶段", "") ?? "阶段缺失"}{day.stage_day != null ? ` · 第 ${day.stage_day} 天` : ""}</span></div><IndexChart days={data.days} selected={day.date} onSelect={selectDay}/><div className="dr-chart-foot"><span>来源：{day.sh_index_source || "fact_market_daily"}</span><span>点选 K 线，查看当天全景 ↗</span></div></div>
      <aside className="dr-card dr-daynote"><div className="dr-section-head"><h3>这一天的市场</h3><span>{short(day.date)}</span></div><div className="dr-daynote-title">{day.sh_index_pct_chg == null ? "指数读数缺失" : day.sh_index_pct_chg > 0 ? "指数收涨" : day.sh_index_pct_chg < 0 ? "指数收跌" : "指数收平"}<span>，{day.amount_vs_yesterday_pct == null ? "量能待核" : day.amount_vs_yesterday_pct > 0 ? "成交放量" : day.amount_vs_yesterday_pct < 0 ? "成交缩量" : "成交持平"}。</span></div><p>领涨方向</p><div className="dr-leading-tags">{day.sector_gainers.slice(0, 3).map(s => <button type="button" key={s.id} onClick={() => pickRank(s.id, s.name)}>{s.name}<b>{pct(s.pct_chg)}</b></button>)}{!day.sector_gainers.length && <span>无有效领涨板块记录</span>}</div><div className="dr-ladder-summary"><div><small>连板高度</small><b>{day.limitup?.max_boards ?? "—"}<em>板</em></b></div><div><small>连板个股</small><b>{day.limitup?.count ?? "—"}<em>家</em></b></div><div><small>强度加权涨幅</small><b className={sign(day.strength_avg_pct)}>{pct(day.strength_avg_pct)}</b></div></div><p className="dr-quiet">以上为数据描述，不推断行情因果。</p></aside></div>
      <DailyReviewWorkspace date={day.date} revision={revision} sectors={data.sectors} marketDates={data.days.map(d => d.date)} onDate={selectDay} onResearch={onResearch} onSelectSector={s => setSectorKey(s.key)} onAttention={(s, date) => { setSectorKey(s?.key ?? null); selectDay(date); setTab("attention"); requestAnimationFrame(() => document.getElementById("daily-market-scan")?.scrollIntoView({ behavior: "smooth", block: "start" })); }}/>
      <div className="dr-bottom-grid" id="daily-market-scan"><div className="dr-card dr-board"><div className="dr-board-tabs" role="tablist" aria-label="每日市场视图"><button type="button" role="tab" aria-selected={tab === "rotation"} onClick={() => setTab("rotation")}><Layers3 size={15}/>板块轮动</button><button type="button" role="tab" aria-selected={tab === "ranking"} onClick={() => setTab("ranking")}>当日榜单</button><button type="button" role="tab" aria-selected={tab === "attention"} onClick={() => setTab("attention")}><Radio size={15}/>舆论观察</button><span>{day.date}</span></div>
      {tab === "attention" ? <AttentionPanel date={day.date} sector={sector} onClear={() => setSectorKey(null)}/> : <>
        <div className="dr-board-tools"><label className="dr-search"><Search size={14}/><input aria-label="搜索板块" placeholder="搜索板块或代码" value={query} onChange={e => setQuery(e.target.value)}/></label><select aria-label="板块排序" value={sort} onChange={e => setSort(e.target.value)}><option value="amount">成交额优先</option><option value="gainers">当日领涨</option><option value="losers">当日领跌</option><option value="five">近5日涨幅</option></select><select aria-label="显示板块数量" value={limit} onChange={e => setLimit(Number(e.target.value))}><option value={24}>前24个</option><option value={60}>前60个</option><option value={1000}>全部板块</option></select>{tab === "rotation" && <div className="dr-metric"><button type="button" aria-pressed={metric === "pct"} onClick={() => setMetric("pct")}>涨跌幅</button><button type="button" aria-pressed={metric === "amount"} onClick={() => setMetric("amount")}>成交额</button></div>}</div>
        <div className="dr-table-wrap"><table className={`dr-heat-table ${tab === "ranking" ? "is-ranking" : ""}`}><thead><tr><th>板块 <small>{rows.length}/{filtered.length}</small></th>{tab === "rotation" ? data.days.map(d => <th key={d.date} className={d.date === day.date ? "is-selected" : ""}><button type="button" aria-label={`选择日期 ${d.date}`} onClick={() => selectDay(d.date)}>{short(d.date)}</button></th>) : <><th>涨跌幅</th><th>成交额 / 亿</th><th>板块边际量</th></>}<th>近5日</th></tr></thead><tbody>{rows.map(s => <tr key={s.key} className={s.key === sectorKey ? "is-sector" : ""}><th><button type="button" onClick={() => setSectorKey(s.key)} title={`${s.name} ${s.id}`}><span>{s.name}</span><small>{s.id}</small></button></th>{tab === "rotation" ? s.points.map((p, i) => {
          const val = p?.[metric === "pct" ? 0 : 1] ?? null;
          const max = Math.max(1, ...s.points.map(x => x?.[1] ?? 0));
          const color = metric === "pct" ? heatColor(val) : val == null ? "" : `rgba(91,124,154,${.08 + val / max * .62})`;
          return <td key={data.days[i].date} className={`${val == null ? "is-missing" : ""} ${i === index ? "is-selected" : ""}`}><button type="button" style={{ background: color }} aria-label={`${s.name} ${data.days[i].date} ${metric === "pct" ? pct(val) : fmt(val, 1) + "亿元"}`} onClick={() => { setSectorKey(s.key); selectDay(data.days[i].date); }} title={`${s.name} · ${data.days[i].date}\n涨跌 ${pct(p?.[0])}\n成交额 ${fmt(p?.[1], 2)}亿元`}>{val == null ? "—" : metric === "pct" ? `${val > 0 ? "+" : ""}${val.toFixed(1)}` : fmt(val)}</button></td>;
        }) : <><td className={sign(s.points[index]?.[0])}>{pct(s.points[index]?.[0])}</td><td>{fmt(s.points[index]?.[1], 2)}</td><td>{fmt(s.points[index]?.[2], 2)}</td></>}<td className={`dr-return ${sign(contiguousReturn(s.points, index))}`}>{pct(contiguousReturn(s.points, index))}</td></tr>)}</tbody></table>{!rows.length && <div className="dr-empty">当前日期与筛选下没有板块记录。</div>}</div>
        <div className="dr-heat-footer"><span>点击单元格：日期与板块同步联动</span><div><i className="dr-legend-down"/>跌 <i className="dr-legend-zero"/>平 <i className="dr-legend-up"/>涨 <i className="dr-legend-missing"/>缺失</div></div><p className="dr-note">近5日 = 截至所选日的5个连续交易日复合涨幅；任一天缺失则不计算。成交额色深在板块自身窗口内比较。</p>
      </>}</div>
      <aside className="dr-detail-column"><div className="dr-card dr-sector-detail"><div className="dr-section-head"><h3>板块放大镜</h3><Layers3 size={16}/></div>{sector ? <><div className="dr-sector-title">{sector.name}<small>{sector.id}</small></div><div className={`dr-sector-value ${sign(point?.[0])}`}>{pct(point?.[0])}<small>{short(day.date)} 当日涨跌</small></div><dl><div><dt>成交额</dt><dd>{fmt(point?.[1], 2)} 亿</dd></div><div><dt>近5日复合涨幅</dt><dd className={sign(contiguousReturn(sector.points, index))}>{pct(contiguousReturn(sector.points, index))}</dd></div><div><dt>板块边际量</dt><dd>{fmt(point?.[2], 2)}</dd></div></dl><button type="button" className="dr-primary" onClick={() => research(sector)}>展开板块六轨 <ArrowRight size={15}/></button><button type="button" className="dr-secondary" onClick={() => setTab("attention")}>查看该板块舆论 <Radio size={14}/></button></> : <div className="dr-sector-placeholder"><Layers3 size={28}/><h4>从一天，走进一个板块。</h4><p>点击热力图或领涨方向，<br/>查看同日表现和舆论来源。</p></div>}</div>
      <div className="dr-card dr-ladder-detail"><div className="dr-section-head"><h3>当日连板梯队</h3><small>{day.date}</small></div>{day.limitup ? <><div className="dr-stock-list">{day.limitup.stocks.slice(0, 10).map(s => <div key={s.stock_ts_code}><b className="dr-board-badge">{s.boards}板</b><span>{s.stock_name}<small>{s.theme || s.stock_ts_code}</small></span><strong className={sign(s.pct_chg)}>{pct(s.pct_chg)}</strong></div>)}</div>{day.limitup.count > 10 && <p className="dr-note">显示前10只，完整明细见连板日历。</p>}</> : <p className="dr-empty">当日无连板明细。不能据此判断连板数量为0。</p>}</div></aside></div>
      <details className="dr-data-notes"><summary><CircleHelp size={13}/> 数据口径与缺口</summary><ul>{data.gaps.map(g => <li key={g}>{g}</li>)}</ul><p>数据日期与查询日期分开显示。行情视图读取当前快照；舆论观察仅按本地实际入库时刻回放，两者不混称“严格历史回测”。</p></details>
    </>}
  </section>;
}
