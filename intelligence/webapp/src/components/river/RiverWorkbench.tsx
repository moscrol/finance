import { TimelineViewport } from "./TimelineViewport";
import { CalendarRange, Database, RefreshCw, Waves } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getKline, getRiverMeta, getTimeline } from "../../river/api";
import { fmtNum } from "../../river/format";
import type { EntityHit, Kline, RiverMeta, Timeline } from "../../river/types";
import { CohortPanel } from "./CohortPanel";
import { EntityPicker } from "./EntityPicker";
import { RangePanel } from "./RangePanel";
import { RiverTimeline } from "./RiverTimeline";
import { ScanPanel } from "./ScanPanel";
import { ShKline } from "./ShKline";
import { SliceDrawer } from "./SliceDrawer";

type Tab = "scan" | "cohort" | "range";
const WINDOWS = [20, 40, 60, 120] as const;

/**
 * 记忆长河工作台。
 *
 * 主视图是「一个实体 × 一段交易日 × 六轨」的时间轴；点某一天在右侧抽屉里展开单点切片。
 * 下方三个 Tab 对应 river_query 的三种查询形状：横扫 / 纵扫 / 区间。
 * 所有数据现算、无 LLM；缺口如实画成缺口。
 */
interface RiverWorkbenchProps {
  onEntityChange?: (entity: EntityHit) => void;
  onPublicAttention?: (entity: EntityHit | null, date: string) => void;
  /** 与涨停梯队共享的当前交易日；只在用户主动选日时回写。 */
  initialEntity?: EntityHit | null;
  focusDate?: string | null;
  onFocusDate?: (date: string) => void;
}

export function RiverWorkbench({ focusDate = null, onFocusDate, initialEntity = null, onEntityChange, onPublicAttention }: RiverWorkbenchProps = {}) {
  const [meta, setMeta] = useState<RiverMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [entity, setEntity] = useState<EntityHit | null>(initialEntity);
  const [windowDays, setWindowDays] = useState<number>(60);
  const [customRange, setCustomRange] = useState<{ start: string; end: string } | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [kline, setKline] = useState<Kline | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedDay, setSelectedDay] = useState<string | null>(focusDate);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("scan");

  const loadMeta = useCallback(() => {
    setMetaError(null);
    getRiverMeta(400)
      .then((m) => {
        setMeta(m);
        setEntity((current) => current ?? m.default_entity);
      })
      .catch((err: Error) => setMetaError(err.message));
  }, []);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const range = useMemo(() => {
    if (customRange) return customRange;
    if (!meta || meta.trading_days.length === 0) return null;
    const days = meta.trading_days;
    const start = days[Math.max(0, days.length - windowDays)];
    return { start, end: days[days.length - 1] };
  }, [meta, windowDays, customRange]);

  useEffect(() => {
    if (!entity || !range) return;
    let cancelled = false;
    setLoading(true);
    setTimeline(null);
    setKline(null);
    setTimelineError(null);
    getKline(range.start, range.end, entity.id)
      .then((k) => {
        if (!cancelled) setKline(k);
      })
      .catch(() => {
        if (!cancelled) setKline(null);
      });
    getTimeline(entity.name, range.start, range.end)
      .then((t) => {
        if (cancelled) return;
        setTimeline(t);
        setSelectedDay((current) => (current && t.days.some((d) => d.date === current) ? current : t.end));
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setTimeline(null);
          setTimelineError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entity, range]);

  const pickDay = (date: string, open = true) => {
    setSelectedDay(date);
    onFocusDate?.(date);
    if (open) setDrawerOpen(true);
    if (range && (date < range.start || date > range.end)) {
      // 纵扫命中的日子可能在当前窗口之外：把窗口挪过去，保持 60 个交易日宽度。
      const days = meta?.trading_days ?? [];
      const idx = days.indexOf(date);
      if (idx >= 0) {
        const start = days[Math.max(0, idx - Math.floor(windowDays / 2))];
        const end = days[Math.min(days.length - 1, idx + Math.floor(windowDays / 2))];
        setCustomRange({ start, end });
      }
    }
  };

  useEffect(() => {
    if (initialEntity) setEntity(initialEntity);
  }, [initialEntity]);

  useEffect(() => {
    if (!focusDate) return;
    setSelectedDay(focusDate);
    const days = meta?.trading_days ?? [];
    const idx = days.indexOf(focusDate);
    if (idx >= 0 && range && (focusDate < range.start || focusDate > range.end)) {
      setCustomRange({ start: days[Math.max(0, idx - windowDays + 1)], end: focusDate });
    }
  }, [focusDate, meta, range, windowDays]);

  useEffect(() => { if (entity) onEntityChange?.(entity); }, [entity, onEntityChange]);
  const coverage = meta?.coverage;

  return (
    <div className={`output-workbench river-workbench ${drawerOpen ? "drawer-open" : ""}`}>
      <div className="output-workbench-header">
        <div>
          <Waves aria-hidden="true" size={15} />
          <strong>时间记忆长河</strong>
          <span>六类数据按交易日对齐 · 每条标明哪天的数据、何时知道、来源、缺了什么 · 读取路径无模型</span>
        </div>
        <button type="button" onClick={loadMeta}>
          <RefreshCw aria-hidden="true" size={12} /> 刷新
        </button>
      </div>

      <div className="river-controls">
        {meta && (
          <EntityPicker value={entity} asOf={meta.latest} hot={meta.hot_entities} onChange={(e) => {
            setEntity(e);
            setDrawerOpen(false);
          }} />
        )}
        <div className="river-segment" role="tablist" aria-label="窗口宽度">
          {WINDOWS.map((w) => (
            <button
              type="button"
              key={w}
              className={!customRange && windowDays === w ? "active" : ""}
              onClick={() => {
                setCustomRange(null);
                setWindowDays(w);
              }}
            >
              {w} 日
            </button>
          ))}
        </div>
        <label className="river-range-input">
          <CalendarRange aria-hidden="true" size={14} />
          <input
            type="date"
            value={range?.start ?? ""}
            max={range?.end}
            onChange={(e) => range && setCustomRange({ start: e.target.value, end: range.end })}
            aria-label="起始日"
          />
          <span>→</span>
          <input
            type="date"
            value={range?.end ?? ""}
            min={range?.start}
            max={meta?.latest ?? undefined}
            onChange={(e) => range && setCustomRange({ start: range.start, end: e.target.value })}
            aria-label="截止日"
          />
        </label>
        {coverage && (
          <div className="river-coverage" title="各轨主数据在库里覆盖的日期范围">
            <Database aria-hidden="true" size={13} />
            {(["market", "theme", "opinion", "capital", "judgment"] as const).map((k) => {
              const c = coverage[k];
              const label = { market: "盘面", theme: "题材", opinion: "研报", capital: "资金", judgment: "判断" }[k];
              const ok = k === "judgment" ? c.exists : Boolean(c.max);
              return (
                <span key={k} className={ok ? "" : "off"} title={`${c.table}${c.min ? ` ${c.min} ~ ${c.max}` : ""} · ${fmtNum(c.rows)} 行`}>
                  {label} {k === "judgment" ? (c.exists ? `${fmtNum(c.rows)} 条` : "无源") : c.max ? `~${c.max.slice(5)}` : "无"}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {metaError && <div className="global-error" role="alert"><span>{metaError}</span></div>}

      <div className="river-body">
        <div className="river-main">
          {timelineError && <div className="slice-error" role="alert">{timelineError}</div>}
          {loading && !timeline && <div className="surface-loading">正在对齐六轨…</div>}
          {timeline && (
            <>
              <div className="river-title">
                <strong>{timeline.entity.name}</strong>
                <code>{timeline.entity.id}</code>
                <span>
                  {timeline.start} → {timeline.end} · {timeline.trading_days} 个交易日
                  {selectedDay && (
                    <>
                      {" "}· 已选 <b>{selectedDay}</b>
                      {!drawerOpen && (
                        <button type="button" className="river-link" onClick={() => setDrawerOpen(true)}>
                          打开切片
                        </button>
                      )}
                    </>
                  )}
                </span>
                {loading && <small>更新中…</small>}
              </div>
              {onPublicAttention && selectedDay && <button type="button" className="original-public-jump" onClick={() => onPublicAttention(entity, selectedDay)}>查看该板块同日公开消息 ↗</button>}
              <TimelineViewport dates={timeline.days.map(d => d.date)} selected={selectedDay} label="六轨时间轴">{compact => <RiverTimeline
                compact={compact}
                timeline={timeline}
                selected={selectedDay}
                onSelect={pickDay}
                base={kline && kline.days.length === timeline.days.length ? <ShKline days={kline.days} selected={selectedDay} onSelect={pickDay} source={kline.source} strengthSource={kline.strength_source} entity={kline.entity} /> : null}
              />}</TimelineViewport>
            </>
          )}

          <div className="river-tabs" role="tablist" aria-label="查询形状">
            <button type="button" role="tab" aria-selected={tab === "scan"} className={tab === "scan" ? "active" : ""} onClick={() => setTab("scan")}>
              横扫 <small>一天 × 全部板块</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === "cohort"} className={tab === "cohort" ? "active" : ""} onClick={() => setTab("cohort")}>
              纵扫 <small>一批日子 × 一个特征</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === "range"} className={tab === "range" ? "active" : ""} onClick={() => setTab("range")}>
              区间 <small>一个实体 × 一段日子</small>
            </button>
          </div>

          {meta && tab === "scan" && (
            <ScanPanel
              asOf={selectedDay ?? meta.latest}
              onDateChange={date => pickDay(date, false)}
              tradingDays={meta.trading_days}
              onPickEntity={(e) => {
                setEntity(e);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          )}
          {meta && tab === "cohort" && <CohortPanel meta={meta} onPickDate={pickDay} />}
          {meta && tab === "range" && range && (
            <RangePanel entity={entity?.name ?? null} start={range.start} end={range.end} onPickDate={pickDay} />
          )}
        </div>

        <SliceDrawer asOf={selectedDay} entity={entity?.name ?? null} open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      </div>
    </div>
  );
}
