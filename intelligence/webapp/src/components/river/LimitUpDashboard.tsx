import { ArrowLeft, ArrowRight, Flame, RefreshCw, Trophy } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getKline, getLimitUpCalendar } from "../../river/api";
import { ShKline } from "./ShKline";
import { TimelineViewport } from "./TimelineViewport";
import { fmtAmount, fmtDateShort, fmtNum, fmtPct, monoColor, shortStage, signClass, stageTone } from "../../river/format";
import type { Kline, LimitUpCalendar, LimitUpDay } from "../../river/types";

const WINDOWS = [20, 40, 60, 120] as const;

function boardsRange(days: LimitUpDay[]): number[] {
  const max = Math.max(2, ...days.map((d) => d.max_boards));
  const out: number[] = [];
  for (let b = max; b >= 2; b -= 1) out.push(b);
  return out;
}

function HeightSparkline({ days, selected, onSelect }: { days: LimitUpDay[]; selected: string | null; onSelect: (d: string) => void }) {
  const width = 900;
  const height = 96;
  const pad = { l: 26, r: 8, t: 14, b: 18 };
  const max = Math.max(3, ...days.map((d) => d.max_boards));
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const xs = days.map((_, i) => pad.l + (days.length === 1 ? innerW / 2 : (i / (days.length - 1)) * innerW));
  const y = (v: number) => pad.t + innerH - (v / max) * innerH;
  const path = days.map((d, i) => `${i === 0 ? "M" : "L"}${xs[i].toFixed(1)},${y(d.max_boards).toFixed(1)}`).join(" ");
  const totalMax = Math.max(1, ...days.map((d) => d.total));
  return (
    <svg className="ladder-spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="最高连板高度与连板总数走势">
      {days.map((d, i) => {
        const w = innerW / days.length;
        const h = (d.total / totalMax) * innerH;
        return (
          <rect key={`t-${d.trade_date}`} x={xs[i] - w / 2 + 1} width={Math.max(1, w - 2)} y={pad.t + innerH - h} height={h} className="spark-total" />
        );
      })}
      <path d={path} className="spark-line" />
      {days.map((d, i) => (
        <g key={d.trade_date}>
          <circle cx={xs[i]} cy={y(d.max_boards)} r={selected === d.trade_date ? 4.5 : 2.5} className={`spark-dot ${selected === d.trade_date ? "selected" : ""}`} />
          <rect x={xs[i] - innerW / days.length / 2} width={innerW / days.length} y={0} height={height} className="hit" role="button" tabIndex={0} aria-label={`连板高度 ${d.trade_date} ${d.max_boards}板`} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(d.trade_date); } }} onClick={() => onSelect(d.trade_date)}>
            <title>
              {d.trade_date} 最高 {d.max_boards} 板{d.leader?.name ? `（${d.leader.name}）` : ""} · 连板 {d.total} 家
            </title>
          </rect>
        </g>
      ))}
      <text x={pad.l - 4} y={y(max) + 4} className="tick" textAnchor="end">{max}板</text>
      <text x={pad.l - 4} y={y(0) + 4} className="tick" textAnchor="end">0</text>
      <text x={pad.l} y={height - 4} className="tick">{days[0] ? fmtDateShort(days[0].trade_date) : ""}</text>
      <text x={width - pad.r} y={height - 4} className="tick" textAnchor="end">{days.length ? fmtDateShort(days[days.length - 1].trade_date) : ""}</text>
    </svg>
  );
}

/** 连板日历：梯队热力 × 晋级率 × 龙头高度 × 市场环境，点一天看明细。 */
interface LimitUpDashboardProps {
  /** 与长河共享的当前交易日；只在用户主动选日时回写。 */
  focusDate?: string | null;
  onFocusDate?: (date: string) => void;
  onOpenRiver?: (date: string) => void;
}

export function LimitUpDashboard({ focusDate = null, onFocusDate, onOpenRiver }: LimitUpDashboardProps = {}) {
  const [days, setDays] = useState<number>(60);
  const [endDate, setEndDate] = useState<string | null>(focusDate);
  const requestId = useRef(0);
  const jumpToEnd = useRef(false);
  const handledFocus = useRef<string | null>(null);
  const selectedRef = useRef<string | null>(focusDate);
  const detailsRef = useRef<HTMLDivElement>(null);
  const [boardFilter, setBoardFilter] = useState<number | null>(null);
  const [stockCode, setStockCode] = useState<string | null>(null);
  const [data, setData] = useState<LimitUpCalendar | null>(null);
  const [kline, setKline] = useState<Kline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelectedDay] = useState<string | null>(focusDate);
  const setSelected = useCallback(
    (date: string) => {
      setSelectedDay(date);
      selectedRef.current = date;
      handledFocus.current = date;
      setBoardFilter(null); setStockCode(null);
      onFocusDate?.(date);
    },
    [onFocusDate],
  );

  const load = useCallback(() => {
    const request = ++requestId.current;
    setKline(null);
    setLoading(true);
    setError(null);
    getLimitUpCalendar(days, endDate)
      .then((res) => {
        if (request !== requestId.current) return;
        setData(res);
        const next = !jumpToEnd.current && res.days.some(d => d.trade_date === selectedRef.current) ? selectedRef.current : res.end;
        jumpToEnd.current = false;
        setSelectedDay(next);
        if (next && next !== selectedRef.current) onFocusDate?.(next);
        selectedRef.current = next;
        setBoardFilter(null); setStockCode(null);
        if (res.start && res.end) getKline(res.start, res.end).then(k => { if (request === requestId.current) setKline(k); }).catch(() => { if (request === requestId.current) setKline(null); });
      })
      .catch((err: Error) => { if (request === requestId.current) setError(err.message); })
      .finally(() => { if (request === requestId.current) setLoading(false); });
  }, [days, endDate, onFocusDate]);

  useEffect(() => {
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  useEffect(() => {
    if (!focusDate || !data || loading || handledFocus.current === focusDate) return;
    handledFocus.current = focusDate;
    selectedRef.current = focusDate;
    setBoardFilter(null); setStockCode(null);
    if (data.days.some((day) => day.trade_date === focusDate)) setSelectedDay(focusDate);
    else if (data.start && data.end && (focusDate < data.start || focusDate > data.end)) setEndDate(focusDate);
  }, [focusDate, data, loading]);

  const rows = useMemo(() => (data ? boardsRange(data.days) : []), [data]);
  const cellScale = useMemo(() => {
    if (!data) return 5;
    const counts = data.days.flatMap((d) => Object.values(d.ladder));
    const sorted = counts.filter((c) => c > 0).sort((a, b) => a - b);
    return sorted.length ? Math.max(3, sorted[Math.floor(sorted.length * 0.9)]) : 5;
  }, [data]);
  const day = data?.days.find((d) => d.trade_date === selected) ?? null;
  const grouped = useMemo(() => {
    if (!day) return [];
    const map = new Map<number, LimitUpDay["details"]>();
    for (const item of day.details) {
      if (!map.has(item.boards)) map.set(item.boards, []);
      map.get(item.boards)!.push(item);
    }
    return [...map.entries()].sort((a, b) => b[0] - a[0]);
  }, [day]);

  const selectedIndex = data?.days.findIndex(d => d.trade_date === selected) ?? -1;
  const stock = day?.details.find(s => s.ts_code === stockCode);
  const showDetails = () => detailsRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  const goLatest = () => {
    jumpToEnd.current = true;
    if (endDate === null) load(); else setEndDate(null);
  };
  const columns = data?.days.length ?? 0;
  const dense = columns > 70;
  const mid = columns > 40 && !dense;
  const overviewLabelEvery = columns > 80 ? 10 : columns > 30 ? 5 : 1;
  const gridStyle = { gridTemplateColumns: `72px repeat(${columns}, minmax(0, 1fr))` };

  return (
    <div className="output-workbench ladder-workbench river-original">
      <div className="output-workbench-header">
        <div>
          <Flame aria-hidden="true" size={15} />
          <strong>连板日历</strong>
          <span>fact_limit_advance_daily · 梯队 / 晋级率 / 龙头高度，与大盘阶段对照</span>
        </div>
        <div>
          <div className="river-segment" role="tablist" aria-label="窗口宽度">
            {WINDOWS.map((w) => (
              <button type="button" key={w} className={days === w ? "active" : ""} onClick={() => setDays(w)}>
                {w} 日
              </button>
            ))}
          </div>
          <button type="button" onClick={load}>
            <RefreshCw aria-hidden="true" size={12} /> 刷新
          </button>
        </div>
      </div>

      {error && <div className="global-error" role="alert"><span>{error}</span></div>}
      {loading && <div className="surface-loading" role="status">正在读取连板台账…</div>}

      {data && !loading && !error && (
        <div className="ladder-body">
          <div className="original-selection-bar">
            <div className="original-date-picker"><button type="button" aria-label="连板上一交易日" disabled={selectedIndex <= 0} onClick={() => setSelected(data.days[selectedIndex - 1].trade_date)}><ArrowLeft size={14}/></button><label>所选交易日<select aria-label="连板当前交易日" value={selected ?? ""} onChange={e => setSelected(e.target.value)}>{data.days.slice().reverse().map(d => <option key={d.trade_date}>{d.trade_date}</option>)}</select></label><button type="button" aria-label="连板下一交易日" disabled={selectedIndex < 0 || selectedIndex >= data.days.length - 1} onClick={() => setSelected(data.days[selectedIndex + 1].trade_date)}><ArrowRight size={14}/></button><button type="button" onClick={goLatest}>最新窗口</button></div>
            <div className="original-selection-actions"><label>历史截止日<input type="date" aria-label="连板历史截止日" value={endDate ?? data.end ?? ""} onChange={e => { if (/^\d{4}-\d{2}-\d{2}$/.test(e.target.value)) { jumpToEnd.current = true; setEndDate(e.target.value); } }}/></label><button type="button" disabled={!day} onClick={showDetails}>查看当日个股 ↓</button>{onOpenRiver && <button type="button" disabled={!day} onClick={() => day && onOpenRiver(day.trade_date)}>同日复盘 ↗</button>}</div>
          </div>
          {data.days.length === 0 && <div className="empty-output">这个截止日之前没有可用连板交易日。不是连板家数为零。</div>}
          <div className="ladder-stats">
            <div>
              <span>窗口</span>
              <strong>{data.stats.trading_days} 个交易日</strong>
              <small>{data.start} → {data.end}</small>
            </div>
            <div>
              <span>日均连板家数</span>
              <strong>{fmtNum(data.stats.avg_total, 1)}</strong>
              <small>2 板及以上</small>
            </div>
            <div>
              <span>日均最高板</span>
              <strong>{fmtNum(data.stats.avg_max_boards, 2)}</strong>
            </div>
            <div>
              <span>窗口最高</span>
              <strong>{data.stats.max_boards ?? "—"} 板</strong>
              <small>
                <button type="button" className="river-link" onClick={() => data.stats.max_boards_date && setSelected(data.stats.max_boards_date)}>
                  {data.stats.max_boards_date}
                </button>
              </small>
            </div>
            {day && (
              <div className="ladder-stat-today">
                <span>{day.trade_date}</span>
                <strong>
                  <Trophy aria-hidden="true" size={14} /> {day.leader?.name ?? "—"} {day.leader?.height ? `${day.leader.height} 板` : ""}
                </strong>
                <small>
                  连板 {day.total} 家 · 3 板以上 {day.high_boards} 家 · 涨停 {day.market?.limit_up ?? "—"} / 跌停 {day.market?.limit_down ?? "—"}
                </small>
              </div>
            )}
          </div>

          <HeightSparkline days={data.days} selected={selected} onSelect={setSelected} />

          <TimelineViewport dates={data.days.map(d => d.trade_date)} selected={selected} labelWidth={72} label="连板时间轴">{compact => {
            const labelEvery = compact ? overviewLabelEvery : 1;
            return <div className={`ladder-grid ${compact && dense ? "dense" : ""} ${compact && mid ? "mid" : ""}`} role="grid" aria-label="连板梯队热力日历">
            {kline && kline.days.length === data.days.length && (
              <ShKline days={kline.days} selected={selected} onSelect={setSelected} labelWidth={72} height={200} source={kline.source} strengthSource={kline.strength_source} />
            )}
            <div className="ladder-row ladder-row-head" style={gridStyle} role="row">
              <div className="ladder-label">日期</div>
              {data.days.map((d, i) => (
                <button
                  type="button"
                  role="columnheader"
                  key={d.trade_date}
                  className={`ladder-date ${selected === d.trade_date ? "selected" : ""} ${i === 0 || d.trade_date.slice(0, 7) !== data.days[i - 1].trade_date.slice(0, 7) ? "month-break" : ""}`}
                  onClick={() => setSelected(d.trade_date)}
                  title={d.trade_date}
                  data-trade-date={d.trade_date}
                  aria-label={`选择连板日期 ${d.trade_date}`}
                >
                  {(i % labelEvery === 0 || selected === d.trade_date || i === 0 || d.trade_date.slice(0, 7) !== data.days[i - 1].trade_date.slice(0, 7)) ? fmtDateShort(d.trade_date).replace("-", "/") : ""}
                </button>
              ))}
            </div>
            {rows.map((b) => (
              <div className="ladder-row" style={gridStyle} key={b} role="row">
                <div className="ladder-label">{b} 板</div>
                {data.days.map((d) => {
                  const n = d.ladder[String(b)] ?? 0;
                  const rate = d.promotion_rate[String(b)];
                  const est = d.promotion_estimated.includes(b);
                  return (
                    <button
                      type="button"
                      role="gridcell"
                      key={`${b}-${d.trade_date}`}
                      className={`ladder-cell ${selected === d.trade_date ? "selected" : ""} ${n === 0 ? "zero" : ""}`}
                      style={{ background: monoColor(n, cellScale, b >= 5 ? "169, 52, 47" : "204, 118, 42") }}
                      title={`${d.trade_date} ${b} 板 ${n} 家${rate !== null && rate !== undefined ? ` · 晋级率 ${rate}%${est ? "（首板数为估算）" : ""}` : ""}`}
                      aria-label={`${d.trade_date} ${b}板 ${n}家`}
                      onClick={() => { setSelected(d.trade_date); setBoardFilter(b); showDetails(); }}
                    >
                      {n > 0 ? n : ""}
                    </button>
                  );
                })}
              </div>
            ))}
            <div className="ladder-row ladder-row-meta" style={gridStyle} role="row">
              <div className="ladder-label">涨停</div>
              {data.days.map((d) => (
                <button type="button" role="gridcell" key={`lu-${d.trade_date}`} className={`ladder-meta ${selected === d.trade_date ? "selected" : ""}`} onClick={() => setSelected(d.trade_date)} title={`${d.trade_date} 涨停 ${d.market?.limit_up ?? "—"} / 跌停 ${d.market?.limit_down ?? "—"}`}>
                  {d.market?.limit_up ?? ""}
                </button>
              ))}
            </div>
            <div className="ladder-row ladder-row-meta" style={gridStyle} role="row">
              <div className="ladder-label">阶段</div>
              {data.days.map((d) => (
                <button type="button" role="gridcell" key={`st-${d.trade_date}`} className={`ladder-stage tone-${stageTone(d.market?.stage)} ${selected === d.trade_date ? "selected" : ""}`} onClick={() => setSelected(d.trade_date)} title={`${d.trade_date} ${shortStage(d.market?.stage) || "未知"}${d.market?.stage_day ? ` 第${d.market.stage_day}天` : ""} · 上证 ${fmtPct(d.market?.sh_pct)}`} />
              ))}
            </div>
          </div>;
          }}</TimelineViewport>
          <div className="river-legend">
            <span><i className="swatch count" /> 2–4 板家数</span>
            <span><i className="swatch up" /> 5 板及以上家数</span>
            <span><i className="swatch tone-bull" /> 主升</span>
            <span><i className="swatch tone-side" /> 横盘</span>
            <span><i className="swatch tone-bear" /> 下跌</span>
            <span><i className="swatch tone-top" /> 顶部</span>
            <span><i className="swatch tone-bottom" /> 底部</span>
          </div>

          {day && (
            <div className="ladder-detail" ref={detailsRef} aria-label="所选日连板明细">
              <div className="ladder-detail-side">
                <h3>
                  {day.trade_date} 梯队
                  <small>
                    {shortStage(day.market?.stage) || "阶段未知"}
                    {day.market?.stage_day ? ` 第${day.market.stage_day}天` : ""} · 上证 {fmtPct(day.market?.sh_pct)} · 两市 {fmtAmount(day.market?.amount)}（{fmtPct(day.market?.amount_chg_pct, 1)}）
                  </small>
                </h3>
                <ul className="ladder-bars">
                  {rows
                    .filter((b) => (day.ladder[String(b)] ?? 0) > 0 || b <= 3)
                    .map((b) => {
                      const n = day.ladder[String(b)] ?? 0;
                      const rate = day.promotion_rate[String(b)];
                      const est = day.promotion_estimated.includes(b);
                      const maxN = Math.max(1, ...Object.values(day.ladder));
                      return (
                        <li key={b}>
                          <span className="ladder-bar-label">{b} 板</span>
                          <span className="ladder-bar-track">
                            <i style={{ width: `${(n / maxN) * 100}%` }} className={b >= 5 ? "high" : ""} />
                          </span>
                          <b>{n}</b>
                          <small title={est ? "首板数 = 昨日涨停家数 − 昨日连板家数，是估算" : `今日 ${b} 板 / 昨日 ${b - 1} 板`}>
                            {rate === null || rate === undefined ? "晋级率 —" : `晋级率 ${rate}%${est ? "*" : ""}`}
                          </small>
                        </li>
                      );
                    })}
                </ul>
                {day.promotion_estimated.length > 0 && <p className="river-hint">* 2 板晋级率的分母（昨日首板数）由昨日涨停家数减去昨日连板家数估算。</p>}
                {day.top_themes.length > 0 && (
                  <p className="ladder-themes">
                    题材：
                    {day.top_themes.map((t) => (
                      <span key={t.theme} className="river-pill">
                        {t.theme} × {t.count}
                      </span>
                    ))}
                  </p>
                )}
              </div>
              <div className="ladder-detail-main">
                <div className="original-board-filter" role="group" aria-label="连板个股梯队筛选"><button type="button" aria-pressed={boardFilter === null} onClick={() => { setBoardFilter(null); setStockCode(null); }}>全部梯队 · {day.details.length}</button>{grouped.map(([b, items]) => <button type="button" key={b} aria-pressed={boardFilter === b} onClick={() => { setBoardFilter(b); setStockCode(null); }}>{b}板 · {items.length}家</button>)}</div>
                {boardFilter !== null && !grouped.some(([b]) => b === boardFilter) && <div className="empty-output">所选日的 {boardFilter} 板没有列出个股明细。可切回全部梯队查看。</div>}
                {stock && <section className="original-stock-inspector" aria-label="连板个股详情"><div><b>{stock.name}</b><code>{stock.ts_code}</code><span>{day.trade_date}</span><button type="button" onClick={() => setStockCode(null)} aria-label="关闭连板个股详情">×</button></div><dl><div><dt>当前梯队</dt><dd>{stock.boards}板</dd></div><div><dt>当日涨幅</dt><dd>{fmtPct(stock.pct)}</dd></div><div><dt>首板日期</dt><dd>{stock.first_limit_date ?? "—"}</dd></div><div><dt>原始题材标签</dt><dd>{stock.theme || "未提供"}</dd></div></dl><p>仅展示当日台账；题材标签不等于经验证的涨停原因。二板晋级率中的估算分母仍单独标注。</p></section>}
                {grouped.length === 0 && <div className="empty-output">这一天没有 2 板及以上的个股</div>}
                {grouped.filter(([b]) => boardFilter === null || b === boardFilter).map(([boards, items]) => (
                  <section className="ladder-group" key={boards}>
                    <h4>
                      {boards} 板 <small>{items.length} 家</small>
                    </h4>
                    <div className="ladder-chips">
                      {items.map((s) => (
                        <button type="button" aria-label={`查看${s.name}连板详情`} aria-pressed={stockCode === s.ts_code} onClick={() => setStockCode(s.ts_code)} className={`ladder-chip ${boards >= 5 ? "high" : ""}`} key={s.ts_code} title={`${s.name} ${s.ts_code} · 首板 ${s.first_limit_date ?? "—"} · ${s.theme ?? "无题材标签"}`}>
                          <strong>{s.name}</strong>
                          <span className={`river-sign ${signClass(s.pct)}`}>{fmtPct(s.pct, 1)}</span>
                          {s.theme && <small>{s.theme}</small>}
                        </button>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
