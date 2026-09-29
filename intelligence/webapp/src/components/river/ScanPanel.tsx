import { ArrowDownWideNarrow, ArrowUpNarrowWide } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getScan } from "../../river/api";
import { fmtAmount, fmtNum, fmtPct, signClass } from "../../river/format";
import type { CrossSectionRow, EntityHit, ScanResult } from "../../river/types";

interface ScanPanelProps {
  asOf: string | null;
  tradingDays: string[];
  onPickEntity: (entity: EntityHit) => void;
}

type SortKey = keyof Pick<
  CrossSectionRow,
  "pct_chg" | "amount" | "limit_up_count" | "coverage_90d" | "fund_flow_1d" | "market_pctile" | "opinion_pctile" | "dislocation" | "diff_ratio"
>;

const COLUMNS: { key: SortKey; label: string; hint: string }[] = [
  { key: "pct_chg", label: "涨跌", hint: "板块当日涨跌幅" },
  { key: "diff_ratio", label: "涨跌家数差", hint: "diff_ratio：涨家数−跌家数占比" },
  { key: "amount", label: "成交额", hint: "亿" },
  { key: "limit_up_count", label: "涨停", hint: "板块内涨停家数（热度表）" },
  { key: "coverage_90d", label: "90日研报", hint: "近 90 日研报覆盖份数（主口径；累计数被回填批次污染，只作背景）" },
  { key: "fund_flow_1d", label: "资金", hint: "成分股主力净流入合计（亿），混源置空" },
  { key: "market_pctile", label: "盘面分位", hint: "当日横截面里的涨跌幅分位" },
  { key: "opinion_pctile", label: "舆论分位", hint: "当日横截面里 90 日覆盖的分位" },
  { key: "dislocation", label: "错位", hint: "舆论分位 − 盘面分位：正 = 喊得多、还没走" },
];

function pctile(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}`;
}

/** 横扫：一天 × 全部板块，跨维找错位。 */
export function ScanPanel({ asOf, tradingDays, onPickEntity }: ScanPanelProps) {
  const [day, setDay] = useState<string | null>(asOf);
  const [mode, setMode] = useState<"all" | "dislocation">("dislocation");
  const [minCoverage, setMinCoverage] = useState(3);
  const [maxPctile, setMaxPctile] = useState(0.4);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "dislocation", dir: -1 });
  const [filter, setFilter] = useState("");

  useEffect(() => setDay(asOf), [asOf]);

  useEffect(() => {
    if (!day) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getScan(day, mode, { minCoverage90d: minCoverage, maxMarketPctile: maxPctile })
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
  }, [day, mode, minCoverage, maxPctile]);

  const rows = useMemo(() => {
    if (!result) return [];
    const q = filter.trim();
    const filtered = q ? result.rows.filter((r) => r.entity_name.includes(q) || r.entity_id.includes(q)) : result.rows;
    return [...filtered].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (Number(av) - Number(bv)) * sort.dir;
    });
  }, [result, sort, filter]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: -1 }));

  return (
    <div className="river-panel">
      <div className="river-toolbar">
        <label>
          <span>日期</span>
          <select value={day ?? ""} onChange={(e) => setDay(e.target.value)}>
            {[...tradingDays].reverse().map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <div className="river-segment" role="tablist" aria-label="横扫模式">
          <button type="button" className={mode === "dislocation" ? "active" : ""} onClick={() => setMode("dislocation")}>
            错位（盘面弱 × 舆论热）
          </button>
          <button type="button" className={mode === "all" ? "active" : ""} onClick={() => setMode("all")}>
            全部板块
          </button>
        </div>
        {mode === "dislocation" && (
          <>
            <label>
              <span>90 日研报 ≥</span>
              <input type="number" min={0} value={minCoverage} onChange={(e) => setMinCoverage(Number(e.target.value))} />
            </label>
            <label>
              <span>盘面分位 ≤</span>
              <input type="number" min={0} max={1} step={0.05} value={maxPctile} onChange={(e) => setMaxPctile(Number(e.target.value))} />
            </label>
          </>
        )}
        <label className="grow">
          <span>筛选</span>
          <input type="search" placeholder="板块名 / 代码" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </label>
        <span className="river-toolbar-note">
          {loading ? "计算中…" : result ? `${rows.length} / ${result.count} 行` : ""}
        </span>
      </div>

      {error && <div className="slice-error" role="alert">{error}</div>}

      {result && result.rows.length === 0 && !loading && (
        <div className="empty-output">这一天在当前阈值下没有错位板块。放宽「90 日研报」或「盘面分位」再试；研报目录只覆盖到 {"入库最后一天"}，越晚的日子 90 日覆盖越可能为 0。</div>
      )}

      {rows.length > 0 && (
        <div className="output-table-scroll river-table-scroll">
          <table className="output-table river-table">
            <thead>
              <tr>
                <th>板块</th>
                {COLUMNS.map((c) => (
                  <th key={c.key} title={c.hint}>
                    <button type="button" className={`sort ${sort.key === c.key ? "active" : ""}`} onClick={() => toggleSort(c.key)}>
                      {c.label}
                      {sort.key === c.key &&
                        (sort.dir === -1 ? <ArrowDownWideNarrow size={12} aria-hidden="true" /> : <ArrowUpNarrowWide size={12} aria-hidden="true" />)}
                    </button>
                  </th>
                ))}
                <th>双红</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.entity_id}>
                  <td>
                    <button
                      type="button"
                      className="river-link"
                      onClick={() => onPickEntity({ id: r.entity_id, name: r.entity_name, amount: r.amount, pct_chg: r.pct_chg })}
                      title="在长河里打开这个板块"
                    >
                      {r.entity_name}
                    </button>
                    <code>{r.entity_id}</code>
                  </td>
                  <td className={`num river-sign ${signClass(r.pct_chg)}`}>{fmtPct(r.pct_chg)}</td>
                  <td className={`num river-sign ${signClass(r.diff_ratio)}`}>{fmtNum(r.diff_ratio, 1)}</td>
                  <td className="num">{fmtAmount(r.amount)}</td>
                  <td className="num">{r.limit_up_count ?? "—"}</td>
                  <td className="num">
                    {r.coverage_90d}
                    <small className="muted"> / 累计 {r.coverage_cumulative}</small>
                  </td>
                  <td className={`num river-sign ${signClass(r.fund_flow_1d)}`} title={r.fund_caliber ?? ""}>
                    {r.fund_flow_1d === null ? (r.fund_caliber?.startsWith("mixed") ? "混源" : "—") : fmtNum(r.fund_flow_1d, 1)}
                  </td>
                  <td className="num">{pctile(r.market_pctile)}</td>
                  <td className="num">{pctile(r.opinion_pctile)}</td>
                  <td className="num">
                    {r.dislocation === null ? (
                      "—"
                    ) : (
                      <span className="river-disloc">
                        <i style={{ width: `${Math.round(Math.abs(r.dislocation) * 100)}%` }} className={r.dislocation > 0 ? "hot" : "cold"} />
                        <b>{r.dislocation > 0 ? "+" : ""}{r.dislocation.toFixed(2)}</b>
                      </span>
                    )}
                  </td>
                  <td>{r.strict_double_red === null ? "—" : r.strict_double_red ? <span className="river-pill red">双红</span> : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
