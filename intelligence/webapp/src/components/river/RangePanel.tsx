import { ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getRange } from "../../river/api";
import { fmtAmount, fmtDateShort, fmtPct, signClass } from "../../river/format";
import type { RangeResult } from "../../river/types";

interface RangePanelProps {
  entity: string | null;
  start: string;
  end: string;
  onPickDate: (date: string) => void;
}

const VALUE_LABELS: Record<string, string> = {
  cumulative_return_pct: "区间涨幅",
  max_drawdown_pct: "最大回撤",
  peak_return_pct: "最高点涨幅",
  amount_sum: "成交额合计",
  amount_avg: "日均成交额",
  turnover_avg: "日均换手",
};

function CurveChart({ result, onPickDate }: { result: RangeResult; onPickDate: (date: string) => void }) {
  const points = result.curve.filter((p) => p.cum_pct !== null);
  const width = 720;
  const height = 180;
  const pad = { l: 44, r: 12, t: 12, b: 26 };
  const { path, area, xs, yOf, zeroY, minV, maxV } = useMemo(() => {
    const values = points.map((p) => p.cum_pct as number);
    const minV = Math.min(0, ...values);
    const maxV = Math.max(0, ...values);
    const span = maxV - minV || 1;
    const innerW = width - pad.l - pad.r;
    const innerH = height - pad.t - pad.b;
    const xs = points.map((_, i) => pad.l + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW));
    const yOf = (v: number) => pad.t + innerH - ((v - minV) / span) * innerH;
    const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${xs[i].toFixed(1)},${yOf(p.cum_pct as number).toFixed(1)}`).join(" ");
    const zeroY = yOf(0);
    const area = points.length ? `${path} L${xs[xs.length - 1].toFixed(1)},${zeroY.toFixed(1)} L${xs[0].toFixed(1)},${zeroY.toFixed(1)} Z` : "";
    return { path, area, xs, yOf, zeroY, minV, maxV };
  }, [points, pad.l, pad.r, pad.t, pad.b]);

  if (points.length === 0) return <div className="empty-output">区间内没有可画的每日读数</div>;
  const last = points[points.length - 1].cum_pct as number;
  const peakIndex = result.peak_date ? points.findIndex((p) => p.date === result.peak_date) : -1;
  const ticks = [0, Math.floor(points.length / 2), points.length - 1].filter((v, i, a) => a.indexOf(v) === i);

  return (
    <svg className="range-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${result.entity_name} 区间累计涨幅曲线`}>
      <line x1={pad.l} x2={width - pad.r} y1={zeroY} y2={zeroY} className="axis" />
      <text x={pad.l - 6} y={yOf(maxV) + 4} className="tick" textAnchor="end">{fmtPct(maxV, 1)}</text>
      <text x={pad.l - 6} y={yOf(minV) + 4} className="tick" textAnchor="end">{fmtPct(minV, 1)}</text>
      <text x={pad.l - 6} y={zeroY + 4} className="tick" textAnchor="end">0</text>
      <path d={area} className={`area ${last >= 0 ? "up" : "down"}`} />
      <path d={path} className={`line ${last >= 0 ? "up" : "down"}`} />
      {peakIndex >= 0 && (
        <g>
          <circle cx={xs[peakIndex]} cy={yOf(points[peakIndex].cum_pct as number)} r={4} className="peak" />
          <text x={xs[peakIndex]} y={yOf(points[peakIndex].cum_pct as number) - 8} className="tick" textAnchor="middle">
            峰 {fmtDateShort(points[peakIndex].date)}
          </text>
        </g>
      )}
      {ticks.map((i) => (
        <text key={i} x={xs[i]} y={height - 8} className="tick" textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}>
          {fmtDateShort(points[i].date)}
        </text>
      ))}
      {points.map((p, i) => (
        <rect
          key={p.date}
          x={i === 0 ? pad.l : (xs[i - 1] + xs[i]) / 2}
          width={i === 0 ? (xs[1] ?? xs[0] + 8) - xs[0] : i === points.length - 1 ? width - pad.r - (xs[i - 1] + xs[i]) / 2 : (xs[i + 1] - xs[i - 1]) / 2}
          y={pad.t}
          height={height - pad.t - pad.b}
          className="hit"
          onClick={() => onPickDate(p.date)}
        >
          <title>
            {p.date} 累计 {fmtPct(p.cum_pct)} · 当日 {fmtPct(p.pct_chg)} · 成交 {fmtAmount(p.amount)}
          </title>
        </rect>
      ))}
    </svg>
  );
}

/** 区间聚合：一个实体 × 一段日子；覆盖与换源写在数字旁边，不藏在日志里。 */
export function RangePanel({ entity, start, end, onPickDate }: RangePanelProps) {
  const [requireComplete, setRequireComplete] = useState(false);
  const [result, setResult] = useState<RangeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!entity || !start || !end) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRange(entity, start, end, { requireComplete })
      .then((res) => {
        if (!cancelled) setResult(res);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setResult(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entity, start, end, requireComplete]);

  return (
    <div className="river-panel">
      <div className="river-toolbar">
        <span className="river-toolbar-note">
          {entity ?? "—"} · {start} → {end}
        </span>
        <label className="river-check">
          <input type="checkbox" checked={requireComplete} onChange={(e) => setRequireComplete(e.target.checked)} />
          覆盖不完整或跨换源时不给数（回放 / 校准口径）
        </label>
        {loading && <span className="river-toolbar-note">计算中…</span>}
      </div>

      {error && <div className="slice-error" role="alert">{error}</div>}

      {result && (
        <>
          <div className="range-head">
            <span className={`slice-badge ${result.trustworthy ? "ok" : "warn"}`}>
              {result.trustworthy ? <ShieldCheck size={12} aria-hidden="true" /> : <TriangleAlert size={12} aria-hidden="true" />}
              {result.trustworthy ? "覆盖干净 · 未跨换源" : "读数有保留"}
            </span>
            <span className="slice-badge">
              覆盖 {result.coverage.actual_days}/{result.coverage.expected_days} 天
            </span>
            <span className="slice-badge">{result.method === "compounded_daily" ? "每日涨幅连乘" : "收盘对收盘"}</span>
            {result.codes_seen.length > 1 && <span className="slice-badge danger">跨换源 {result.codes_seen.join(" → ")}</span>}
            <span className="slice-badge">{result.kind === "sector" ? "板块" : "个股"} · {result.entity_id}</span>
          </div>

          <div className="range-metrics">
            {Object.entries(result.values).map(([key, value]) => {
              const isPct = key.endsWith("_pct");
              return (
                <div className="range-metric" key={key}>
                  <span>{VALUE_LABELS[key] ?? key}</span>
                  <strong className={isPct ? `river-sign ${signClass(value)}` : ""}>
                    {isPct ? fmtPct(value) : fmtAmount(value)}
                  </strong>
                  {key === "peak_return_pct" && result.peak_date && <small>峰值日 {result.peak_date}</small>}
                </div>
              );
            })}
            {result.gaps.map((g) => (
              <div className="range-metric is-gap" key={g.metric} title={g.reason}>
                <span>{VALUE_LABELS[g.metric] ?? g.metric}</span>
                <strong>算不出</strong>
                <small>{g.reason}</small>
              </div>
            ))}
          </div>

          <CurveChart result={result} onPickDate={onPickDate} />

          {(result.caveats.length > 0 || result.coverage.missing_dates.length > 0 || result.coverage.duplicate_dates.length > 0) && (
            <ul className="river-notes">
              {result.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
              {result.coverage.missing_dates.length > 0 && (
                <li>缺天：{result.coverage.missing_dates.slice(0, 12).join("、")}{result.coverage.missing_dates.length > 12 ? ` 等 ${result.coverage.missing_dates.length} 天` : ""}</li>
              )}
              {result.coverage.duplicate_dates.length > 0 && <li>重复日期：{result.coverage.duplicate_dates.join("、")}（连乘会多乘）</li>}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
