import { useMemo, useState, type ReactNode } from "react";
import { fmtAmount, fmtDateShort, fmtNum, fmtPct, signClass } from "../../river/format";
import type { Kline, KlineDay } from "../../river/types";

interface ShKlineProps {
  days: KlineDay[];
  selected: string | null;
  onSelect: (date: string) => void;
  /** 左侧标签列宽度，需与下方泳道的标签列一致才能逐列对齐。 */
  labelWidth?: number;
  height?: number;
  source?: string | null;
  strengthSource?: string | null;
  entity?: Kline["entity"];
}

type Overlay = "ma5" | "ma10" | "ma20" | "ma60" | "week_ma";
type Pane = "strength" | "breadth" | "highs";

const OVERLAYS: { key: Overlay; label: string; color: string; hint: string }[] = [
  { key: "ma5", label: "MA5", color: "#c65f3e", hint: "5 日收盘均线（现算）" },
  { key: "ma10", label: "MA10", color: "#d09a3f", hint: "10 日收盘均线（现算）" },
  { key: "ma20", label: "MA20", color: "#496f91", hint: "20 日收盘均线（现算）" },
  { key: "ma60", label: "MA60", color: "#7a5ea6", hint: "60 日收盘均线（现算）" },
  { key: "week_ma", label: "周均", color: "#2e7d54", hint: "库里的 sh_week_ma（乖离率以它为基准）" },
];
const ENTITY_COLOR = "#8a4fb5";
const STRENGTH = { avg: "#9b9791", ma5: "#c65f3e", ma20: "#496f91" };
const HIGH_SERIES: { key: "high_20d" | "high_60d" | "high_120d" | "high_1y"; label: string; color: string }[] = [
  { key: "high_1y", label: "1 年", color: "#7a5ea6" },
  { key: "high_120d", label: "120 日", color: "#496f91" },
  { key: "high_60d", label: "60 日", color: "#d09a3f" },
  { key: "high_20d", label: "20 日", color: "#c65f3e" },
];

const W = 1000;
const PAD_T = 6;
const VOL_H = 36;
const GAP = 6;
const PANE_H: Record<Pane, number> = { strength: 84, breadth: 72, highs: 72 };

function pathOf(days: KlineDay[], x: (i: number) => number, y: (v: number) => number, pick: (d: KlineDay) => number | null | undefined): string {
  let out = "";
  let pen = false;
  days.forEach((d, i) => {
    const v = pick(d);
    if (v === null || v === undefined || !Number.isFinite(v)) {
      pen = false;
      return;
    }
    out += `${pen ? " L" : " M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return out.trim();
}

function scale(values: (number | null | undefined)[], top: number, h: number, floor?: number) {
  const nums = values.filter((v): v is number => v !== null && v !== undefined && Number.isFinite(v));
  let max = nums.length ? Math.max(...nums) : 1;
  let min = nums.length ? Math.min(...nums) : 0;
  if (floor !== undefined) min = Math.min(min, floor);
  if (max === min) {
    max += 1;
    min -= 1;
  }
  return { max, min, y: (v: number) => top + h - ((v - min) / (max - min)) * h };
}

/**
 * 上证 K 线底座。默认只显示：K 线 + MA5/MA20/周均 + 两市成交额 + 强度层（强度加权涨幅 及 MA5/MA20）。
 * 选了板块时叠一条板块区间净值线（右轴）。广度、新高两层折叠，读数条一行，其余细节悬停看。
 * 所有层共用列坐标，与下方泳道逐列对齐；点任一列选中该交易日。
 */
export function ShKline({ days, selected, onSelect, labelWidth = 112, height = 210, source, strengthSource, entity }: ShKlineProps) {
  const [on, setOn] = useState<Record<Overlay, boolean>>({ ma5: true, ma10: false, ma20: true, ma60: false, week_ma: true });
  const [panes, setPanes] = useState<Record<Pane, boolean>>({ strength: true, breadth: false, highs: false });
  const [hover, setHover] = useState<string | null>(null);

  const n = days.length;
  const priceH = height - PAD_T - VOL_H - GAP - 2;
  const x = (i: number) => ((i + 0.5) / Math.max(1, n)) * W;
  const colW = W / Math.max(1, n);
  const hasEntity = !!entity && days.some((d) => d.entity_nav !== null && d.entity_nav !== undefined);

  const price = useMemo(() => {
    const maVals = days.flatMap((d) => OVERLAYS.filter((o) => on[o.key]).map((o) => d[o.key]));
    const s = scale([...days.map((d) => d.high ?? d.close), ...days.map((d) => d.low ?? d.close), ...maVals], PAD_T, priceH);
    const volMax = Math.max(1, ...days.map((d) => d.total_amount ?? 0), ...days.map((d) => d.amount_ma20 ?? 0));
    const volBase = PAD_T + priceH + GAP + VOL_H;
    return { ...s, volBase, vy: (v: number) => volBase - (v / volMax) * VOL_H, volMax };
  }, [days, on, priceH]);
  const nav = useMemo(() => scale(days.map((d) => d.entity_nav), PAD_T, priceH), [days, priceH]);
  const strength = useMemo(
    () => scale([...days.map((d) => d.strength_avg_pct), ...days.map((d) => d.strength_ma5_pct), ...days.map((d) => d.strength_ma20_pct)], PAD_T, PANE_H.strength - PAD_T - 6),
    [days],
  );
  const breadth = useMemo(() => scale(days.map((d) => d.advancers), PAD_T, PANE_H.breadth - PAD_T - 4, 0), [days]);
  const highs = useMemo(() => scale(HIGH_SERIES.flatMap((h) => days.map((d) => d[h.key])), PAD_T, PANE_H.highs - PAD_T - 4, 0), [days]);

  // 强度 MA5 与 MA20 的金叉 / 死叉位置
  const crosses = useMemo(() => {
    const out: { i: number; up: boolean }[] = [];
    for (let i = 1; i < days.length; i++) {
      const a = days[i - 1], b = days[i];
      if (a.strength_ma5_pct === null || a.strength_ma20_pct === null || b.strength_ma5_pct === null || b.strength_ma20_pct === null) continue;
      const before = a.strength_ma5_pct - a.strength_ma20_pct;
      const after = b.strength_ma5_pct - b.strength_ma20_pct;
      if (before <= 0 && after > 0) out.push({ i, up: true });
      else if (before >= 0 && after < 0) out.push({ i, up: false });
    }
    return out;
  }, [days]);

  if (n === 0) return null;

  const focus = hover ?? selected;
  const focusIdx = focus ? days.findIndex((d) => d.date === focus) : -1;
  const a = focusIdx >= 0 ? days[focusIdx] : days[n - 1];
  const hasStrength = days.some((d) => d.strength_ma5_pct !== null || d.strength_avg_pct !== null);
  const hasBreadth = days.some((d) => d.advancers !== null);
  const hasHighs = days.some((d) => d.high_60d !== null);
  const crowded = a.advancers !== null && a.limit_up !== null && a.limit_up >= 60 && a.advancers < 2000;

  const overlayFor = (h: number): ReactNode => (
    <>
      {focusIdx >= 0 && <rect x={x(focusIdx) - colW / 2} width={colW} y={0} height={h} className={hover ? "hover-col" : "selected-col"} />}
      {days.map((d, i) => (
        <rect key={d.date} x={x(i) - colW / 2} width={colW} y={0} height={h} className="hit" data-trade-date={d.date} onMouseEnter={() => setHover(d.date)} onClick={() => onSelect(d.date)} />
      ))}
    </>
  );
  const toggle = (key: Pane, label: string, ok: boolean) => (
    <button type="button" key={key} className={`pane-toggle ${panes[key] ? "active" : ""}`} disabled={!ok} title={ok ? (panes[key] ? "收起" : "展开") : "区间内无数据"} aria-pressed={panes[key]} onClick={() => setPanes((s) => ({ ...s, [key]: !s[key] }))}>
      {label}
    </button>
  );

  return (
    <div className="sh-kline" style={{ gridTemplateColumns: `${labelWidth}px minmax(0, 1fr)` }} onMouseLeave={() => setHover(null)}>
      {/* ---------- 主图 ---------- */}
      <div className="sh-kline-label">
        <strong>上证指数</strong>
        <small title={source ?? ""}>sh000001</small>
        <div className="sh-kline-toggles">
          {OVERLAYS.map((o) => (
            <button type="button" key={o.key} className={on[o.key] ? "active" : ""} style={{ ["--c" as string]: o.color }} title={o.hint} aria-pressed={on[o.key]} onClick={() => setOn((s) => ({ ...s, [o.key]: !s[o.key] }))}>
              {o.label}
            </button>
          ))}
        </div>
        {hasEntity && entity && (
          <small className="sh-entity-tag" style={{ color: ENTITY_COLOR }} title={entity.note}>
            ▬ {entity.name} 净值
          </small>
        )}
      </div>

      <div className="sh-kline-plot">
        <div className="sh-kline-readout" aria-live="polite">
          <b>{a.date}</b>
          <span className={`river-sign ${signClass(a.pct_chg)}`} title={`开 ${fmtNum(a.open, 2)} 高 ${fmtNum(a.high, 2)} 低 ${fmtNum(a.low, 2)}`}>
            收 {fmtNum(a.close, 2)} {fmtPct(a.pct_chg)}
          </span>
          {OVERLAYS.filter((o) => on[o.key]).map((o) => (
            <span key={o.key} style={{ color: o.color }}>
              {o.label} {fmtNum(a[o.key], 0)}
            </span>
          ))}
          {hasEntity && (
            <span style={{ color: ENTITY_COLOR }} title={entity?.note}>
              {entity?.name} {fmtPct(a.entity_pct ?? null)} · 净值 {fmtNum(a.entity_nav ?? null, 3)}
            </span>
          )}
          <span title="两市成交额 / 20 日均额">量 {fmtAmount(a.total_amount)}</span>
          <span className={crowded ? "warn" : ""} title={crowded ? "涨停多而涨家数弱 = 抱团非普涨" : "涨家数 · 涨停 / 跌停"}>
            涨 {a.advancers ?? "—"} · 停 {a.limit_up ?? "—"}/{a.limit_down ?? "—"}
          </span>
          {a.strength_status && <span className={`status-chip s-${a.strength_status}`}>{a.strength_status}</span>}
        </div>

        <svg style={{ height }} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" role="img" aria-label="上证指数 K 线与均线">
          {[price.max, (price.max + price.min) / 2, price.min].map((t, i) => (
            <line key={i} x1={0} x2={W} y1={price.y(t)} y2={price.y(t)} className="grid" />
          ))}
          {days.map((d, i) =>
            d.total_amount === null ? null : (
              <rect key={`v-${d.date}`} x={x(i) - colW * 0.32} width={colW * 0.64} y={price.vy(d.total_amount)} height={price.volBase - price.vy(d.total_amount)} className={`vol ${signClass(d.pct_chg)}`} />
            ),
          )}
          <path d={pathOf(days, x, price.vy, (d) => d.amount_ma20)} className="vol-ma" />
          {days.map((d, i) => {
            if (d.open === null || d.close === null) return null;
            const up = d.close >= d.open;
            const top = price.y(Math.max(d.open, d.close));
            const bottom = price.y(Math.min(d.open, d.close));
            return (
              <g key={d.date} className={`candle ${up ? "up" : "down"}`}>
                <line x1={x(i)} x2={x(i)} y1={price.y(d.high ?? Math.max(d.open, d.close))} y2={price.y(d.low ?? Math.min(d.open, d.close))} />
                <rect x={x(i) - colW * 0.32} width={colW * 0.64} y={top} height={Math.max(1.2, bottom - top)} />
              </g>
            );
          })}
          {OVERLAYS.filter((o) => on[o.key]).map((o) => (
            <path key={o.key} d={pathOf(days, x, price.y, (d) => d[o.key])} className="ma" style={{ stroke: o.color }} />
          ))}
          {hasEntity && <path d={pathOf(days, x, nav.y, (d) => d.entity_nav)} className="ma entity" style={{ stroke: ENTITY_COLOR }} />}
          {overlayFor(height)}
        </svg>
        <div className="sh-kline-axis" aria-hidden="true">
          <span style={{ top: PAD_T }}>{fmtNum(price.max, 0)}</span>
          <span style={{ top: PAD_T + priceH }}>{fmtNum(price.min, 0)}</span>
        </div>
        {hasEntity && (
          <div className="sh-kline-axis left" aria-hidden="true" style={{ color: ENTITY_COLOR }}>
            <span style={{ top: PAD_T }}>{fmtNum(nav.max, 2)}</span>
            <span style={{ top: PAD_T + priceH }}>{fmtNum(nav.min, 2)}</span>
          </div>
        )}
      </div>

      {/* ---------- 副图切换行 ---------- */}
      <div className="sh-pane-bar">
        {toggle("strength", "强度", hasStrength)}
        {toggle("breadth", "广度", hasBreadth)}
        {toggle("highs", "新高", hasHighs)}
      </div>
      <div className="sh-pane-bar-fill" />

      {/* ---------- 强度 ---------- */}
      {panes.strength && hasStrength && (
        <>
          <div className="sh-pane-label">
            <strong>强度</strong>
            <small title={strengthSource ?? "强势股（top5%）平均涨幅"}>
              <i style={{ background: STRENGTH.ma5 }} /> MA5 <i style={{ background: STRENGTH.ma20 }} /> MA20
              <br />
              <i style={{ background: STRENGTH.avg }} /> 当日 · ▲▼ 金叉/死叉
            </small>
          </div>
          <div className="sh-kline-plot sh-pane">
            <div className="sh-kline-readout">
              <span style={{ color: STRENGTH.ma5 }}>MA5 {fmtPct(a.strength_ma5_pct)}</span>
              <span style={{ color: STRENGTH.ma20 }}>MA20 {fmtPct(a.strength_ma20_pct)}</span>
              <span>当日 {fmtPct(a.strength_avg_pct)}</span>
              <span className={`river-sign ${signClass(a.strength_marginal_pct)}`} title="强度成交环比">
                环比 {fmtPct(a.strength_marginal_pct)}
              </span>
            </div>
            <svg style={{ height: PANE_H.strength }} viewBox={`0 0 ${W} ${PANE_H.strength}`} preserveAspectRatio="none" role="img" aria-label="强势股强度与均线">
              <line x1={0} x2={W} y1={strength.y(strength.min)} y2={strength.y(strength.min)} className="grid" />
              <path d={pathOf(days, x, strength.y, (d) => d.strength_avg_pct)} className="ma thin" style={{ stroke: STRENGTH.avg }} />
              <path d={pathOf(days, x, strength.y, (d) => d.strength_ma20_pct)} className="ma" style={{ stroke: STRENGTH.ma20 }} />
              <path d={pathOf(days, x, strength.y, (d) => d.strength_ma5_pct)} className="ma" style={{ stroke: STRENGTH.ma5 }} />
              {crosses.map((c) => {
                const yy = strength.y(days[c.i].strength_ma5_pct as number);
                return <circle key={c.i} cx={x(c.i)} cy={yy} r={3.2} className={`cross ${c.up ? "up" : "down"}`} />;
              })}
              {days.map((d, i) =>
                d.strength_status === "沸点" || d.strength_status === "冰点" ? (
                  <rect key={`st-${d.date}`} x={x(i) - colW * 0.3} width={colW * 0.6} y={PANE_H.strength - 4} height={3} className={`status ${d.strength_status === "沸点" ? "hot" : "cold"}`} />
                ) : null,
              )}
              {overlayFor(PANE_H.strength)}
            </svg>
            <div className="sh-kline-axis" aria-hidden="true">
              <span style={{ top: PAD_T }}>{fmtPct(strength.max)}</span>
              <span style={{ top: strength.y(strength.min) }}>{fmtPct(strength.min)}</span>
            </div>
          </div>
        </>
      )}

      {/* ---------- 广度 ---------- */}
      {panes.breadth && hasBreadth && (
        <>
          <div className="sh-pane-label">
            <strong>广度</strong>
            <small>
              涨家数柱 · 2500 中线
              <br />
              <i className="mk up" /> 涨停 <i className="mk down" /> 跌停
            </small>
          </div>
          <div className="sh-kline-plot sh-pane">
            <div className="sh-kline-readout">
              <span>
                涨家数 <b>{a.advancers ?? "—"}</b>
              </span>
              <span className="river-sign up">涨停 {a.limit_up ?? "—"}</span>
              <span className="river-sign down">跌停 {a.limit_down ?? "—"}</span>
              {crowded && <span className="warn">涨停多而涨家少 → 抱团非普涨</span>}
            </div>
            <svg style={{ height: PANE_H.breadth }} viewBox={`0 0 ${W} ${PANE_H.breadth}`} preserveAspectRatio="none" role="img" aria-label="涨家数与涨跌停">
              {breadth.max > 2500 && <line x1={0} x2={W} y1={breadth.y(2500)} y2={breadth.y(2500)} className="grid mid" />}
              <line x1={0} x2={W} y1={breadth.y(0)} y2={breadth.y(0)} className="grid" />
              {days.map((d, i) =>
                d.advancers === null ? (
                  <rect key={d.date} x={x(i) - colW * 0.3} width={colW * 0.6} y={PAD_T} height={PANE_H.breadth - PAD_T - 4} className="gap" />
                ) : (
                  <g key={d.date}>
                    <rect x={x(i) - colW * 0.32} width={colW * 0.64} y={breadth.y(d.advancers)} height={breadth.y(0) - breadth.y(d.advancers)} className={`bar ${d.advancers >= 2500 ? "up" : "down"}`} />
                    {d.limit_up !== null && <circle cx={x(i)} cy={breadth.y(d.advancers) - 3} r={Math.min(3.5, 1 + d.limit_up / 40)} className="mk up" />}
                    {d.limit_down !== null && d.limit_down > 0 && <circle cx={x(i)} cy={breadth.y(0) - 2} r={Math.min(3.5, 1 + d.limit_down / 15)} className="mk down" />}
                  </g>
                ),
              )}
              {overlayFor(PANE_H.breadth)}
            </svg>
            <div className="sh-kline-axis" aria-hidden="true">
              <span style={{ top: PAD_T }}>{breadth.max}</span>
            </div>
          </div>
        </>
      )}

      {/* ---------- 新高 ---------- */}
      {panes.highs && hasHighs && (
        <>
          <div className="sh-pane-label">
            <strong>新高</strong>
            <small>
              创新高家数
              <br />
              {HIGH_SERIES.map((h) => (
                <span key={h.key}>
                  <i style={{ background: h.color }} /> {h.label}{" "}
                </span>
              ))}
            </small>
          </div>
          <div className="sh-kline-plot sh-pane">
            <div className="sh-kline-readout">
              {HIGH_SERIES.map((h) => (
                <span key={h.key} style={{ color: h.color }}>
                  {h.label} {a[h.key] ?? "—"}
                </span>
              ))}
            </div>
            <svg style={{ height: PANE_H.highs }} viewBox={`0 0 ${W} ${PANE_H.highs}`} preserveAspectRatio="none" role="img" aria-label="创新高家数">
              <line x1={0} x2={W} y1={highs.y(0)} y2={highs.y(0)} className="grid" />
              {HIGH_SERIES.map((h) => (
                <path key={h.key} d={pathOf(days, x, highs.y, (d) => d[h.key])} className="ma" style={{ stroke: h.color }} />
              ))}
              {overlayFor(PANE_H.highs)}
            </svg>
            <div className="sh-kline-axis" aria-hidden="true">
              <span style={{ top: PAD_T }}>{highs.max}</span>
            </div>
          </div>
        </>
      )}

      <div />
      <div className="sh-kline-dates" aria-hidden="true">
        <span>{fmtDateShort(days[0].date)}</span>
        <span>{fmtDateShort(days[n - 1].date)}</span>
      </div>
    </div>
  );
}
