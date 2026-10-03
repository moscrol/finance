import { useMemo, type ReactNode } from "react";
import {
  fmtAmount,
  fmtDateShort,
  fmtNum,
  fmtPct,
  heatColor,
  monoColor,
  shortStage,
  stageTone,
} from "../../river/format";
import { TRACKS, TRACK_LABELS, type Timeline, type TimelineDay, type Track } from "../../river/types";

interface RiverTimelineProps {
  timeline: Timeline;
  selected: string | null;
  onSelect: (date: string) => void;
  /** 底座（上证 K 线），渲染在大盘阶段行之上，与泳道共用列坐标。 */
  base?: ReactNode;
  compact?: boolean;
}

interface CellView {
  color: string;
  text: string;
  title: string;
  missing: boolean;
  bar?: number; // 0~1，个股轨上涨占比
}

function cellFor(track: Track, day: TimelineDay, scales: Scales): CellView {
  const missing = (t: string, why: string): CellView => ({
    color: "transparent",
    text: "",
    title: `${day.date} ${t}：${why}`,
    missing: true,
  });
  switch (track) {
    case "market": {
      const m = day.market;
      if (!m || m.sector_pct === null) return missing("盘面", "这一天没有该板块行情行");
      return {
        color: heatColor(m.sector_pct, scales.sectorPct),
        text: fmtPct(m.sector_pct, 1),
        title: `${day.date} 板块 ${fmtPct(m.sector_pct)} · 成交 ${fmtAmount(m.sector_amount)} · 大盘 ${shortStage(m.stage)}${m.stage_day ? ` 第${m.stage_day}天` : ""} · 上证 ${fmtPct(m.sh_pct)} · 涨停 ${m.limit_up ?? "—"}/跌停 ${m.limit_down ?? "—"}`,
        missing: false,
      };
    }
    case "theme": {
      const t = day.theme;
      if (!t || t.limit_up_count === null) return missing("题材", "涨停热度表没有该板块");
      const tops = t.top_stocks.map((s) => `${s.name}(${s.limit_times}板)`).join(" ");
      return {
        color: monoColor(t.limit_up_count, scales.limitUp),
        text: String(t.limit_up_count),
        title: `${day.date} 板块涨停 ${t.limit_up_count} 家 / ${t.total_count ?? "—"} 只 · 热度排名 ${t.rank ?? "—"}${tops ? ` · ${tops}` : ""}`,
        missing: false,
      };
    }
    case "opinion": {
      const o = day.opinion;
      if (!o) return missing("研报覆盖", "当日没有命中该板块的研报（研报目录只覆盖到入库最后一天）");
      return {
        color: monoColor(o.reports, scales.reports, "73, 111, 145"),
        text: String(o.reports),
        title: `${day.date} 研报 ${o.reports} 份：${o.titles.join("；")}`,
        missing: false,
      };
    }
    case "capital": {
      const c = day.capital;
      if (c?.fund_caliber.startsWith("mixed:")) return missing("资金", `混合口径 ${c.fund_caliber}，不可相加（${c.n_with_fund}/${c.n_stocks} 只有数）`);
      if (!c || c.fund_flow_1d === null) return missing("资金", "成分股当日没有资金流字段（不是净流入为 0）");
      return {
        color: heatColor(c.fund_flow_1d, scales.fund),
        text: `${c.fund_flow_1d > 0 ? "+" : ""}${c.fund_flow_1d.toFixed(0)}`,
        title: `${day.date} 成分股资金流合计 ${c.fund_flow_1d.toFixed(2)} 亿 · 口径 ${c.fund_caliber}（${c.n_with_fund}/${c.n_stocks} 只有数）`,
        missing: false,
      };
    }
    case "stock": {
      const s = day.stock;
      if (!s || s.n_stocks === 0) return missing("个股", "当日没有成分股行");
      if (!s.n_with_pct || s.n_up === null || s.n_down === null) return missing("个股", `涨跌幅缺失（0/${s.n_stocks} 只有数）`);
      const denom = s.n_up + s.n_down;
      const ratio = denom ? s.n_up / denom : 0.5;
      return {
        color: "transparent",
        text: s.n_limit_like ? `${s.n_limit_like}` : "",
        title: `${day.date} 成分股 ${s.n_stocks} 只（涨跌幅覆盖 ${s.n_with_pct}/${s.n_stocks}）：涨 ${s.n_up} / 跌 ${s.n_down} · 涨停级 ${s.n_limit_like ?? "—"} · 领涨 ${s.top_name ?? "—"} ${fmtPct(s.top_pct)} · 成交最大 ${s.amount_leader ?? "—"}`,
        missing: false,
        bar: ratio,
      };
    }
    case "judgment": {
      const j = day.judgment;
      if (!j) return missing("判断", "当日没有挂在该板块上的可证伪点");
      return {
        color: "rgba(198, 95, 62, 0.85)",
        text: `◆${j.count > 1 ? j.count : ""}`,
        title: `${day.date} ${j.count} 条判断：${j.items.map((x) => x.claim ?? "").join("；")}`,
        missing: false,
      };
    }
    default:
      return missing("未知", "未知轨");
  }
}

interface Scales {
  sectorPct: number;
  limitUp: number;
  reports: number;
  fund: number;
}

function quantileScale(values: number[], fallback: number): number {
  const xs = values.filter((v) => Number.isFinite(v) && v !== 0).map(Math.abs).sort((a, b) => a - b);
  if (xs.length === 0) return fallback;
  const q = xs[Math.min(xs.length - 1, Math.floor(xs.length * 0.9))];
  return q > 0 ? q : fallback;
}

/** 六泳道时间轴：横轴交易日，纵轴六轨；缺格画斜纹，不用空白冒充「为零」。 */
export function RiverTimeline({ timeline, selected, onSelect, base, compact = true }: RiverTimelineProps) {
  const scales = useMemo<Scales>(
    () => ({
      sectorPct: quantileScale(timeline.days.map((d) => d.market?.sector_pct ?? 0), 3),
      limitUp: quantileScale(timeline.days.map((d) => d.theme?.limit_up_count ?? 0), 10),
      reports: quantileScale(timeline.days.map((d) => d.opinion?.reports ?? 0), 3),
      fund: quantileScale(timeline.days.map((d) => d.capital?.fund_flow_1d ?? 0), 20),
    }),
    [timeline],
  );

  const coverage = useMemo(() => {
    const total = timeline.days.length || 1;
    const out: Record<Track, number> = { market: 0, theme: 0, opinion: 0, capital: 0, stock: 0, judgment: 0 };
    for (const day of timeline.days) {
      for (const track of TRACKS) {
        if (!cellFor(track, day, scales).missing) out[track] += 1;
      }
    }
    for (const track of TRACKS) out[track] = Math.round((out[track] / total) * 100);
    return out;
  }, [timeline, scales]);

  const columns = timeline.days.length;
  const dense = compact && columns > 45;
  const labelEvery = !compact ? 1 : columns > 80 ? 10 : columns > 30 ? 5 : 1;
  const gridStyle = { gridTemplateColumns: `112px repeat(${columns}, minmax(0, 1fr))` };
  const monthBreaks = new Set<number>();
  timeline.days.forEach((day, index) => {
    if (index === 0 || day.date.slice(0, 7) !== timeline.days[index - 1].date.slice(0, 7)) monthBreaks.add(index);
  });

  return (
    <div className={`river-timeline ${dense ? "dense" : ""}`} role="grid" aria-label={`${timeline.entity.name} 六轨时间轴`}>
      {base}
      <div className="river-row river-row-stage" style={gridStyle} role="row">
        <div className="river-lane-label">
          <strong>大盘阶段</strong>
          <small>fact_market_daily</small>
        </div>
        {timeline.days.map((day, index) => (
          <button
            type="button"
            role="gridcell"
            key={day.date}
            data-trade-date={day.date}
            className={`river-stage-cell tone-${stageTone(day.market?.stage)} ${selected === day.date ? "selected" : ""} ${monthBreaks.has(index) ? "month-break" : ""}`}
            title={`${day.date} ${shortStage(day.market?.stage) || "阶段未知"}${day.market?.stage_day ? ` 第${day.market.stage_day}天` : ""} · 上证 ${fmtPct(day.market?.sh_pct)} · 两市 ${fmtAmount(day.market?.total_amount)}`}
            onClick={() => onSelect(day.date)}
          >
            {(monthBreaks.has(index) || index % labelEvery === 0 || selected === day.date) && (
              <span className="river-stage-date">{fmtDateShort(day.date)}</span>
            )}
          </button>
        ))}
      </div>

      {TRACKS.map((track) => (
        <div className={`river-row river-row-${track}`} style={gridStyle} key={track} role="row">
          <div className="river-lane-label">
            <strong>{track === "opinion" ? "研报覆盖" : TRACK_LABELS[track]}</strong>
            <small>{coverage[track]}% 有数</small>
          </div>
          {timeline.days.map((day, index) => {
            const cell = cellFor(track, day, scales);
            return (
              <button
                type="button"
                role="gridcell"
                key={`${track}-${day.date}`}
                className={`river-cell ${cell.missing ? "missing" : ""} ${selected === day.date ? "selected" : ""} ${monthBreaks.has(index) ? "month-break" : ""}`}
                style={{ background: cell.color }}
                title={cell.title}
                aria-label={cell.title}
                onClick={() => onSelect(day.date)}
              >
                {cell.bar !== undefined && (
                  <span className="river-cell-bar" aria-hidden="true">
                    <i style={{ height: `${Math.round(cell.bar * 100)}%` }} />
                  </span>
                )}
                {cell.text && <span className="river-cell-text">{cell.text}</span>}
              </button>
            );
          })}
        </div>
      ))}

      <div className="river-legend">
        <span><i className="swatch up" /> 涨 / 净流入</span>
        <span><i className="swatch down" /> 跌 / 净流出</span>
        <span><i className="swatch count" /> 计数（涨停家数 / 研报份数）</span>
        <span><i className="swatch missing" /> 缺口：这条轨这一天读不到，不是零</span>
        <span>研报份数不是公开消息热度；覆盖比例只针对当前实体与窗口。</span>
        <span className="river-legend-note">
          {fmtNum(timeline.trading_days)} 个交易日 · 强度按区间 90 分位归一
          {timeline.entity.codes_seen.length > 1 && (
            <em> · 跨换源：{timeline.entity.codes_seen.join(" → ")}，跨切换日数值不可直接比较</em>
          )}
        </span>
      </div>
    </div>
  );
}
