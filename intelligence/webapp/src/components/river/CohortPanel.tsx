import { useState } from "react";
import { postCohort } from "../../river/api";
import type { CohortFeature, CohortResult, CohortSelector, RiverMeta } from "../../river/types";

interface CohortPanelProps {
  meta: RiverMeta;
  onPickDate: (date: string) => void;
}

const SELECTORS: { key: CohortSelector; label: string; kind: "category" | "number"; hint: string }[] = [
  { key: "market_stage", label: "大盘阶段 =", kind: "category", hint: "「下跌阶段」与「下跌」已归一" },
  { key: "volume_state", label: "量能状态 =", kind: "category", hint: "" },
  { key: "concentration_state", label: "集中度状态 =", kind: "category", hint: "" },
  { key: "limit_up_gte", label: "涨停家数 ≥", kind: "number", hint: "" },
  { key: "limit_down_gte", label: "跌停家数 ≥", kind: "number", hint: "" },
  { key: "amount_change_lte", label: "成交额环比 ≤ (%)", kind: "number", hint: "缩量日" },
  { key: "amount_change_gte", label: "成交额环比 ≥ (%)", kind: "number", hint: "放量日" },
  { key: "sh_pct_lte", label: "上证涨跌 ≤ (%)", kind: "number", hint: "" },
  { key: "sh_pct_gte", label: "上证涨跌 ≥ (%)", kind: "number", hint: "" },
];

const FEATURES: { key: CohortFeature; label: string }[] = [
  { key: "market_stage", label: "大盘阶段" },
  { key: "volume_state", label: "量能状态" },
  { key: "concentration_state", label: "集中度状态" },
];

const VERDICT: Record<string, { label: string; tone: string; hint: string }> = {
  supported: { label: "支持", tone: "ok", hint: "Wilson 下界高过基准且前后半段同向" },
  refuted: { label: "反证", tone: "danger", hint: "Wilson 上界低于基准" },
  not_distinguishable: { label: "不可区分", tone: "muted", hint: "置信区间含基准，倍数再好看也不算规律" },
  insufficient_n: { label: "样本不足", tone: "warn", hint: "格子里样本太少，不下结论" },
};

/** 纵扫：条件筛出一批日子，与全样本基准比，统计门给四态判词。 */
export function CohortPanel({ meta, onPickDate }: CohortPanelProps) {
  const [selector, setSelector] = useState<CohortSelector>("limit_up_gte");
  const [value, setValue] = useState<string>("80");
  const [feature, setFeature] = useState<CohortFeature>("market_stage");
  const [start, setStart] = useState<string>("");
  const [end, setEnd] = useState<string>("");
  const [result, setResult] = useState<CohortResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const selectorSpec = SELECTORS.find((s) => s.key === selector)!;
  const categoryOptions =
    selectorSpec.kind === "category" ? meta.cohort_options[selector as keyof RiverMeta["cohort_options"]] ?? [] : [];

  const run = () => {
    setLoading(true);
    setError(null);
    postCohort({
      selector,
      value: selectorSpec.kind === "number" ? Number(value) : value,
      feature,
      start: start || null,
      end: end || null,
    })
      .then(setResult)
      .catch((err: Error) => {
        setResult(null);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  };

  return (
    <div className="river-panel">
      <div className="river-toolbar">
        <label>
          <span>选日条件</span>
          <select
            value={selector}
            onChange={(e) => {
              const next = e.target.value as CohortSelector;
              setSelector(next);
              const spec = SELECTORS.find((s) => s.key === next)!;
              if (spec.kind === "category") {
                const opts = meta.cohort_options[next as keyof RiverMeta["cohort_options"]] ?? [];
                setValue(opts[0] ?? "");
              } else {
                setValue(next.startsWith("limit") ? "80" : next.startsWith("amount") ? "-10" : "-1");
              }
            }}
          >
            {SELECTORS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>值</span>
          {selectorSpec.kind === "category" ? (
            <select value={value} onChange={(e) => setValue(e.target.value)}>
              {categoryOptions.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          ) : (
            <input type="number" value={value} step="any" onChange={(e) => setValue(e.target.value)} />
          )}
        </label>
        <label>
          <span>比较特征</span>
          <select value={feature} onChange={(e) => setFeature(e.target.value as CohortFeature)}>
            {FEATURES.map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>起</span>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          <span>止</span>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button type="button" className="river-primary" onClick={run} disabled={loading}>
          {loading ? "计算中…" : "纵扫"}
        </button>
      </div>
      <p className="river-hint">
        判词来自 methodology_backtest.stats（Wilson 区间 + BH 校正 + 前后半段同向）。默认输出是「不可区分」，不是规律。
      </p>

      {error && <div className="slice-error" role="alert">{error}</div>}

      {result && (
        <div className="cohort-result">
          <div className="cohort-summary">
            <div>
              <span className="output-eyebrow">条件</span>
              <strong>{result.selector_label}</strong>
            </div>
            <div>
              <span className="output-eyebrow">命中日子</span>
              <strong>{result.dates.length}</strong>
            </div>
            {result.report && (
              <div>
                <span className="output-eyebrow">基准样本</span>
                <strong>{result.report.baseline_size} 个交易日</strong>
              </div>
            )}
          </div>

          {result.note && <div className="empty-output">{result.note}</div>}

          {result.report && (
            <div className="output-table-scroll">
              <table className="output-table river-table cohort-table">
                <thead>
                  <tr>
                    <th>{FEATURES.find((f) => f.key === feature)?.label}</th>
                    <th>命中 k/n</th>
                    <th>命中率 vs 基准</th>
                    <th title="Wilson 95% 区间">Wilson 区间</th>
                    <th title="BH 校正后的 p">p (校正)</th>
                    <th title="前半段 / 后半段命中率，检验是否同向">前 / 后半段</th>
                    <th>判词</th>
                  </tr>
                </thead>
                <tbody>
                  {result.report.cells.map((cell) => {
                    const v = VERDICT[cell.verdict] ?? { label: cell.verdict, tone: "muted", hint: "" };
                    const max = Math.max(cell.rate, cell.baseline, cell.wilson_hi, 0.01);
                    return (
                      <tr key={cell.value}>
                        <td>{cell.value}</td>
                        <td className="num">
                          {cell.k}/{cell.n}
                        </td>
                        <td>
                          <div className="cohort-bars" aria-label={`命中率 ${(cell.rate * 100).toFixed(1)}%，基准 ${(cell.baseline * 100).toFixed(1)}%`}>
                            <span className="cohort-bar rate" style={{ width: `${(cell.rate / max) * 100}%` }} />
                            <span className="cohort-bar base" style={{ width: `${(cell.baseline / max) * 100}%` }} />
                            <b>
                              {(cell.rate * 100).toFixed(1)}% <small>vs {(cell.baseline * 100).toFixed(1)}%</small>
                            </b>
                          </div>
                        </td>
                        <td className="num">
                          {(cell.wilson_lo * 100).toFixed(0)}–{(cell.wilson_hi * 100).toFixed(0)}%
                        </td>
                        <td className="num">{cell.p_adjusted.toFixed(3)}</td>
                        <td className="num">
                          {cell.rate_first_half === null ? "—" : `${(cell.rate_first_half * 100).toFixed(0)}%`} /{" "}
                          {cell.rate_second_half === null ? "—" : `${(cell.rate_second_half * 100).toFixed(0)}%`}
                        </td>
                        <td>
                          <span className={`river-pill ${v.tone}`} title={v.hint}>
                            {v.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {result.report && result.report.notes.length > 0 && (
            <ul className="river-notes">
              {result.report.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}

          {result.dates.length > 0 && (
            <details className="cohort-dates">
              <summary>命中的 {result.dates.length} 个交易日（点一天在长河里定位）</summary>
              <div className="cohort-date-chips">
                {result.dates.map((d) => (
                  <button type="button" key={d} onClick={() => onPickDate(d)}>
                    {d}
                  </button>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
