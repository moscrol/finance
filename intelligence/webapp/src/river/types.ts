// 记忆长河 / 连板日历的接口类型。与 intelligence/api/river_routes.py 一一对应。

export type Track = "market" | "theme" | "opinion" | "capital" | "stock" | "judgment";

export const TRACKS: Track[] = ["market", "theme", "opinion", "capital", "stock", "judgment"];

export const TRACK_LABELS: Record<Track, string> = {
  market: "盘面",
  theme: "题材",
  opinion: "舆论",
  capital: "资金",
  stock: "个股",
  judgment: "判断",
};

export interface EntityHit {
  id: string;
  name: string;
  amount: number | null;
  pct_chg: number | null;
}

export interface TrackCoverage {
  table: string;
  min: string | null;
  max: string | null;
  rows: number;
  exists?: boolean;
}

export interface RiverMeta {
  latest: string | null;
  trading_days: string[];
  default_entity: EntityHit | null;
  hot_entities: EntityHit[];
  tracks: { key: Track; label: string }[];
  coverage: Record<Track, TrackCoverage>;
  cohort_options: Record<"market_stage" | "volume_state" | "concentration_state", string[]>;
}

export interface TimelineMarket {
  stage: string | null;
  stage_day: number | null;
  sh_pct: number | null;
  total_amount: number | null;
  amount_chg_pct: number | null;
  limit_up: number | null;
  limit_down: number | null;
  sector_pct: number | null;
  sector_amount: number | null;
  sector_diff_ratio: number | null;
  sector_code: string | null;
}

export interface TimelineTheme {
  limit_up_count: number | null;
  total_count: number | null;
  limit_up_ratio: number | null;
  rank: number | null;
  top_stocks: { ts_code: string; name: string; limit_times: number }[];
}

export interface TimelineOpinion {
  reports: number;
  titles: string[];
}

export interface TimelineCapital {
  fund_flow_1d: number | null;
  fund_caliber: string;
  n_with_fund: number;
  n_stocks: number;
}

export interface TimelineStock {
  n_stocks: number;
  n_with_pct: number;
  n_up: number | null;
  n_down: number | null;
  n_limit_like: number | null;
  top_name: string | null;
  top_pct: number | null;
  amount_leader: string | null;
}

export interface TimelineJudgment {
  count: number;
  items: { id: string | null; claim: string | null; category: string | null; due: string | null }[];
}

export interface TimelineDay {
  date: string;
  market: TimelineMarket | null;
  theme: TimelineTheme | null;
  opinion: TimelineOpinion | null;
  capital: TimelineCapital | null;
  stock: TimelineStock | null;
  judgment: TimelineJudgment | null;
}

export interface Timeline {
  entity: { id: string; name: string; codes_seen: string[]; alias_applied: boolean };
  start: string;
  end: string;
  trading_days: number;
  judgment_source: { path: string; exists: boolean };
  days: TimelineDay[];
}

export interface RiverObject {
  track: Track;
  entity_id: string;
  object_type: string;
  ref: string;
  source_hash: string;
  valid_from: string;
  recorded_at: string | null;
  payload: Record<string, unknown>;
}

export interface RiverGap {
  track: Track;
  gap: true;
  reason: string;
  detail: string;
}

export type TrackResult = RiverObject[] | RiverGap;

export interface RiverSlice {
  as_of: string;
  entity_id: string;
  entity_name: string;
  knowledge_cutoff: string;
  pit_grade: "strict" | "trade_date_only";
  hindsight: boolean;
  alias_applied: boolean;
  tracks: Record<Track, TrackResult>;
}

export interface CrossSectionRow {
  entity_id: string;
  entity_name: string;
  pct_chg: number | null;
  diff_ratio: number | null;
  amount: number | null;
  strict_double_red: boolean | null;
  limit_up_count: number | null;
  coverage_90d: number;
  coverage_cumulative: number;
  days_since_last_report: number | null;
  fund_flow_1d: number | null;
  fund_caliber: string | null;
  market_pctile: number | null;
  opinion_pctile: number | null;
  dislocation: number | null;
}

export interface ScanResult {
  as_of: string;
  mode: "all" | "dislocation";
  count: number;
  rows: CrossSectionRow[];
}

export type CohortSelector =
  | "market_stage"
  | "volume_state"
  | "concentration_state"
  | "limit_up_gte"
  | "limit_down_gte"
  | "amount_change_lte"
  | "amount_change_gte"
  | "sh_pct_lte"
  | "sh_pct_gte"
  | "explicit";

export type CohortFeature = "market_stage" | "volume_state" | "concentration_state";

export interface CohortRequest {
  selector: CohortSelector;
  value?: string | number | null;
  dates?: string[];
  feature: CohortFeature;
  start?: string | null;
  end?: string | null;
}

export interface CohortCell {
  value: string;
  k: number;
  n: number;
  rate: number;
  baseline: number;
  wilson_lo: number;
  wilson_hi: number;
  p_value: number;
  p_adjusted: number;
  rate_first_half: number | null;
  rate_second_half: number | null;
  verdict: "insufficient_n" | "not_distinguishable" | "supported" | "refuted" | string;
}

export interface CohortResult {
  selector_label: string;
  dates: string[];
  note?: string;
  report: {
    feature: string;
    cohort_size: number;
    baseline_size: number;
    cells: CohortCell[];
    notes: string[];
  } | null;
}

export interface RangeResult {
  kind: "stock" | "sector";
  entity_id: string;
  entity_name: string;
  start: string;
  end: string;
  method: string;
  trustworthy: boolean;
  coverage: {
    expected_days: number;
    actual_days: number;
    complete: boolean;
    clean: boolean;
    missing_dates: string[];
    missing_return_dates?: string[];
    duplicate_dates: string[];
  };
  codes_seen: string[];
  values: Record<string, number | null>;
  peak_date: string | null;
  gaps: { metric: string; reason: string }[];
  caveats: string[];
  curve: { date: string; pct_chg: number | null; cum_pct: number | null; amount: number | null }[];
}

export interface KlineDay {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  amount: number | null;
  pct_chg: number | null;
  week_ma: number | null;
  deviation_pct: number | null;
  total_amount: number | null;
  amount_ma20: number | null;
  stage: string | null;
  stage_day: number | null;
  limit_up: number | null;
  limit_down: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  advancers: number | null;
  strength_avg_pct: number | null;
  strength_ma5_pct: number | null;
  strength_ma20_pct: number | null;
  strength_marginal_pct: number | null;
  strength_status: string | null;
  high_20d: number | null;
  high_60d: number | null;
  high_120d: number | null;
  high_1y: number | null;
  entity_pct?: number | null;
  entity_nav?: number | null;
}

export interface Kline {
  index: string;
  code: string;
  source: string | null;
  strength_source: string | null;
  entity: { id: string; name: string; coverage: number; note: string } | null;
  start: string;
  end: string;
  ma_windows: number[];
  days: KlineDay[];
}

// ---- 连板 ----
export interface LimitUpDetail {
  name: string;
  ts_code: string;
  boards: number;
  theme: string | null;
  pct: number | null;
  first_limit_date: string | null;
}

export interface LimitUpDay {
  trade_date: string;
  ladder: Record<string, number>;
  promotion_rate: Record<string, number | null>;
  promotion_estimated: number[];
  data_status?: "available" | "missing";
  total: number | null;
  high_boards: number | null;
  max_boards: number | null;
  details: LimitUpDetail[];
  top_themes: { theme: string; count: number }[];
  market: {
    limit_up: number | null;
    limit_down: number | null;
    advancers: number | null;
    amount: number | null;
    amount_chg_pct: number | null;
    stage: string | null;
    stage_day: number | null;
    sh_pct: number | null;
    volume_state: string | null;
  } | null;
  leader: { height: number; name: string | null; ts_code: string | null } | null;
}

export interface LimitUpCalendar {
  start: string | null;
  end: string | null;
  days: LimitUpDay[];
  stats: {
    trading_days: number;
    avg_total: number | null;
    avg_max_boards: number | null;
    max_boards: number | null;
    max_boards_date: string | null;
  };
}
