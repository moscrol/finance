import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, RefreshCw } from "lucide-react";
import { getKline } from "../../river/api";
import type { DailyOverview, SectorSeries } from "../../river/dailyTypes";
import type { EntityHit, Kline } from "../../river/types";
import { ShKline } from "./ShKline";
import { DailyReviewWorkspace } from "./DailyReviewWorkspace";
import { TimelineViewport } from "./TimelineViewport";

/** Original Workbench chrome, canonical daily-review content. No second dashboard entry. */
export function OriginalDailyReview({ focusDate, onFocusDate, onResearch, onAttention }: {
  focusDate: string | null; onFocusDate: (day: string) => void;
  onResearch: (entity: EntityHit, date: string) => void;
  onAttention: (entity: Pick<SectorSeries, "id" | "name"> | null, date: string) => void;
}) {
  const [days, setDays] = useState(40);
  const [anchor, setAnchor] = useState<string | null>(focusDate);
  const [revision, setRevision] = useState(0);
  const [overview, setOverview] = useState<DailyOverview | null>(null);
  const [kline, setKline] = useState<Kline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chartError, setChartError] = useState(false);
  const desired = useRef(focusDate);
  const notify = useRef(onFocusDate);
  useEffect(() => { desired.current = focusDate; notify.current = onFocusDate; }, [focusDate, onFocusDate]);
  useEffect(() => {
    const controller = new AbortController();
    setOverview(null); setKline(null); setError(null); setChartError(false);
    const query = new URLSearchParams({ days: String(days) });
    if (anchor) query.set("end", anchor);
    fetch(`/api/river/daily-overview?${query}`, { signal: controller.signal }).then(async res => {
      if (!res.ok) throw new Error(`复盘行情接口暂不可用（${res.status}）。请确认配套后端已发布，不会改用其他交易日。`);
      const data = await res.json() as DailyOverview;
      if (controller.signal.aborted) return;
      if (desired.current && desired.current !== anchor && !data.days.some(d => d.date === desired.current)) {
        setAnchor(desired.current);
        return;
      }
      setOverview(data);
      if (!desired.current && data.end) { desired.current = data.end; notify.current(data.end); }
      if (data.start && data.end) getKline(data.start, data.end).then(k => { if (!controller.signal.aborted) setKline(k); }).catch(() => { if (!controller.signal.aborted) setChartError(true); });
    }).catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [days, anchor, revision]);
  useEffect(() => {
    if (focusDate && overview && focusDate !== anchor && !overview.days.some(d => d.date === focusDate)) setAnchor(focusDate);
  }, [focusDate, overview, anchor]);
  const selected = focusDate ?? overview?.end ?? null;
  const index = overview?.calendar.indexOf(selected ?? "") ?? -1;
  const pick = (date: string) => {
    desired.current = date; onFocusDate(date);
    if (overview && !overview.days.some(d => d.date === date)) setAnchor(date);
  };
  return <div className="output-workbench original-review">
    <div className="output-workbench-header"><div><BookOpen size={15}/><strong>每日复盘</strong><span>原 daily 指标 · 行业 → 子板块 → 个股</span></div><button type="button" onClick={() => setRevision(n => n + 1)}><RefreshCw size={12}/> 刷新复盘</button></div>
    <div className="original-selection-bar"><div className="original-date-picker"><button type="button" aria-label="复盘上一交易日" disabled={!overview || index <= 0} onClick={() => overview && pick(overview.calendar[index - 1])}><ArrowLeft size={14}/></button><label>交易日<select aria-label="复盘当前交易日" value={selected ?? ""} onChange={e => pick(e.target.value)}>{!overview && <option value="">读取日期…</option>}{selected && overview && !overview.calendar.includes(selected) && <option value={selected}>{selected}</option>}{overview?.calendar.slice().reverse().map(d => <option key={d}>{d}</option>)}</select></label><button type="button" aria-label="复盘下一交易日" disabled={!overview || index < 0 || index >= overview.calendar.length - 1} onClick={() => overview && pick(overview.calendar[index + 1])}><ArrowRight size={14}/></button><button type="button" disabled={!overview?.latest_market_date} onClick={() => { desired.current = null; setOverview(null); setAnchor(null); setRevision(n => n + 1); }}>最新</button></div><div className="river-segment" role="group" aria-label="复盘指数窗口">{[20, 40, 60, 120].map(w => <button type="button" key={w} className={days === w ? "active" : ""} aria-pressed={days === w} onClick={() => setDays(w)}>{w} 日</button>)}</div></div>
    {error && <div className="global-error" role="alert">{error}</div>}
    {!overview && !error && <div className="surface-loading" role="status">正在对齐交易日与原始复盘…</div>}
    {overview && <div className="original-review-body">
      {selected && !overview.days.some(d => d.date === selected) && <p className="river-hint">所选日报日期暂无行情；归档仍按 {selected} 读取。</p>}
      {!overview.days.length && <div className="empty-output">所选窗口没有交易日记录。</div>}
      {kline && <details className="original-index-fold" open><summary>指数与市场环境 <span>{kline.start} → {kline.end} · 当前行情快照，非严格历史回测</span></summary><TimelineViewport dates={kline.days.map(d => d.date)} selected={selected} label="复盘指数时间轴">{() => <ShKline days={kline.days} selected={selected} onSelect={pick} source={kline.source} strengthSource={kline.strength_source}/>}</TimelineViewport></details>}
      {chartError && <p className="river-hint">指数图暂不可读；下方日报归档独立展示，不用虚构K线补齐。</p>}
      {selected && <DailyReviewWorkspace date={selected} revision={revision} sectors={overview.sectors} marketDates={overview.days.map(d => d.date)} onDate={pick} onResearch={onResearch} onAttention={onAttention}/>}
    </div>}
  </div>;
}
