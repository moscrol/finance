export interface SectorRank { id: string; name: string; pct_chg: number | null; amount: number | null; diff_ratio: number | null }
export interface DailyMarket {
  date: string; sh_index_open: number | null; sh_index_high: number | null; sh_index_low: number | null;
  sh_index_close: number | null; sh_index_pct_chg: number | null; ma5: number | null; ma20: number | null;
  total_amount: number | null; amount_vs_yesterday_pct: number | null; amount_ma20: number | null;
  advancers: number | null; limit_up: number | null; limit_down: number | null; market_stage: string | null;
  stage_day: number | null; volume_state: string | null; strength_avg_pct: number | null;
  sh_index_source: string | null; sector_count: number; sector_valid_count: number;
  sector_up_count: number; sector_down_count: number; sector_flat_count: number;
  sector_gainers: SectorRank[]; sector_losers: SectorRank[]; sector_amount_leaders: SectorRank[];
  limitup: null | { count: number; max_boards: number; stocks: { stock_ts_code: string; stock_name: string; boards: number; theme: string | null; pct_chg: number | null }[] };
}
export type SectorPoint = [number | null, number | null, number | null] | null;
export interface SectorSeries { id: string; name: string; key: string; points: SectorPoint[] }
export interface DailyOverview {
  schema_version?: number; days: DailyMarket[]; calendar: string[]; start?: string; end?: string;
  latest_market_date: string | null; latest_sector_date: string | null; sectors: SectorSeries[]; gaps: string[];
  amount_unit?: string; knowledge_mode?: string;
}
export interface AttentionEvent {
  id: string; title: string; entities: { id: string; name: string }[];
  heat: number | null; participant_count: number; report_count: number; unknown_sources: number;
  lineage_complete: boolean; grouping: string; evidence_status: string; trend_pct: number | null; trend_status: string;
  first_published_at: string; latest_published_at: string;
  sources: { source_name: string; source_kind: string; url: string; title: string; published_at: string; recorded_at: string }[];
}
export interface AttentionSnapshot {
  collection_status: string; last_import_at: string | null; events: AttentionEvent[]; event_count: number;
  visible_observations: number; missing_publication_times: number; cutoff: string;
  knowledge_mode: string; gaps: string[]; truncated: boolean;
}
