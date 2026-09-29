import { CircleAlert, Clock3, ShieldCheck, ShieldOff, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getSlice } from "../../river/api";
import { fmtTs } from "../../river/format";
import { TRACKS, TRACK_LABELS, type RiverGap, type RiverObject, type RiverSlice, type Track } from "../../river/types";

interface SliceDrawerProps {
  asOf: string | null;
  entity: string | null;
  open: boolean;
  onClose: () => void;
}

const GAP_REASONS: Record<string, string> = {
  no_data: "没有数据",
  no_source: "数据源不存在",
  entity_unresolved: "实体口径接不上",
  pit_filtered: "被知识截止过滤（记录时刻晚于截止）",
};

// 每类对象挑几个关键字段展示；其余折叠在「原始 payload」里，不做二次加工。
const KEY_FIELDS: Record<Track, string[]> = {
  market: ["market_stage", "stage_day", "pct_chg", "amount", "diff_ratio", "strict_double_red", "limit_up", "limit_down", "total_amount", "limit_up_count", "total_count", "limit_up_ratio", "rank", "market_share"],
  theme: ["stock_name", "limit_times", "pct_chg", "limit_status", "up_stat", "leader_plate"],
  opinion: ["title", "heat", "participant_count", "grouping", "evidence_status", "caveat", "report_date", "count_30d", "count_90d", "cumulative_count", "days_since_last", "last_coverage_date"],
  capital: ["fund_flow_1d_sum", "fund_flow_5d_sum", "fund_caliber", "n_with_fund", "n_stocks", "total_fund"],
  stock: ["stock_name", "pct_chg", "close", "amount", "limit_times", "high_status_label"],
  judgment: ["claim", "category", "due", "metric"],
};

function isGap(value: RiverObject[] | RiverGap): value is RiverGap {
  return !Array.isArray(value) && (value as RiverGap).gap === true;
}

function fmtValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.map(fmtValue).join("、");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ObjectCard({ object, track }: { object: RiverObject; track: Track }) {
  const [raw, setRaw] = useState(false);
  const keys = KEY_FIELDS[track].filter((k) => k in object.payload);
  return (
    <div className="slice-object">
      <div className="slice-object-head">
        <span className="slice-object-type">{object.object_type === "public_news_attention" ? "公开消息传播 · 未核实" : object.object_type}</span>
        <code title={object.ref}>{object.ref}</code>
      </div>
      <dl className="slice-fields">
        {keys.map((k) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{fmtValue(object.payload[k])}</dd>
          </div>
        ))}
      </dl>
      <div className="slice-object-foot">
        <span title="系统什么时候知道这条对象（recorded_at）">
          <Clock3 aria-hidden="true" size={12} /> 记录于 {fmtTs(object.recorded_at)}
        </span>
        <button type="button" onClick={() => setRaw((v) => !v)}>
          {raw ? "收起 payload" : "原始 payload"}
        </button>
      </div>
      {raw && <pre className="slice-raw">{JSON.stringify(object.payload, null, 2)}</pre>}
    </div>
  );
}

/** 单点切片抽屉：一天 × 一个实体 × 六轨；Gap 与 pit_grade 原样展示。 */
export function SliceDrawer({ asOf, entity, open, onClose }: SliceDrawerProps) {
  const [slice, setSlice] = useState<RiverSlice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [requireStrict, setRequireStrict] = useState(false);

  useEffect(() => {
    if (!open || !asOf || !entity) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getSlice(asOf, entity, { requireStrict })
      .then((res) => {
        if (!cancelled) setSlice(res);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setSlice(null);
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, asOf, entity, requireStrict]);

  if (!open) return null;

  return (
    <aside className="slice-drawer" aria-label="当日切片">
      <header className="slice-head">
        <div>
          <span className="output-eyebrow">单点切片 · 一天 × 一个实体 × 六轨</span>
          <strong>
            {slice?.entity_name ?? entity} · {asOf}
          </strong>
          {slice && (
            <div className="slice-badges">
              <span className={`slice-badge ${slice.pit_grade === "strict" ? "ok" : "warn"}`} title="strict = 六轨对象的记录时刻都不晚于知识截止；trade_date_only = 有对象只知道交易日、不知道何时入库">
                {slice.pit_grade === "strict" ? <ShieldCheck size={12} aria-hidden="true" /> : <ShieldOff size={12} aria-hidden="true" />}
                PIT {slice.pit_grade}
              </span>
              <span className="slice-badge" title="knowledge_cutoff：这一片允许看见的最晚时刻">
                截止 {slice.knowledge_cutoff}
              </span>
              {slice.hindsight && <span className="slice-badge danger">事后视角 · 不得进校准</span>}
              {slice.alias_applied && <span className="slice-badge warn">跨供应商别名归一</span>}
            </div>
          )}
        </div>
        <button type="button" className="icon-button" aria-label="关闭切片" onClick={onClose}>
          <X size={17} aria-hidden="true" />
        </button>
      </header>

      <label className="slice-strict">
        <input type="checkbox" checked={requireStrict} onChange={(e) => setRequireStrict(e.target.checked)} />
        严格 PIT（过滤记录时刻晚于截止 / 未知的对象，回放与校准口径）
      </label>

      {loading && <div className="surface-loading">正在读取六轨…</div>}
      {error && (
        <div className="slice-error" role="alert">
          <CircleAlert size={14} aria-hidden="true" /> {error}
        </div>
      )}

      {slice && !loading && (
        <div className="slice-tracks">
          {TRACKS.map((track) => {
            const result = slice.tracks[track];
            const gap = result && isGap(result) ? result : null;
            const objects = result && !isGap(result) ? result : [];
            return (
              <section className={`slice-track ${gap ? "is-gap" : ""}`} key={track}>
                <h3>
                  <span>{track === "opinion" ? "研报与公开消息（分开记录）" : TRACK_LABELS[track]}</span>
                  <small>{gap ? "缺口" : `${objects.length} 个对象`}</small>
                </h3>
                {gap ? (
                  <p className="slice-gap">
                    <strong>{GAP_REASONS[gap.reason] ?? gap.reason}</strong>
                    {gap.detail && <span>{gap.detail}</span>}
                  </p>
                ) : (
                  objects.map((object) => <ObjectCard key={object.ref} object={object} track={track} />)
                )}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}
