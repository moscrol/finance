import type { ReviewCell, ReviewEngine, ReviewSnapshot } from "./reviewTypes";

export type MatrixDayStatus = "available" | "empty" | "not_in_scope" | "not_reported";
export type EnginesStatus = "available" | "empty" | "not_in_scope" | "not_reported" | "unknown";

export interface HistoryPoint {
  date: string;
  status: "available" | "missing" | "unavailable";
  reason: string | null;
  provenance: ReviewSnapshot["provenance"] | null;
  metrics: Record<string, number | null>;
  deltas: Record<string, number | null>;
  comparison_date: string | null;
  top_industries: string[];
  industry_rank: number | null;
  industry_status: "ranked" | "not_in_list" | "unknown";
  matrices: Record<string, { status: MatrixDayStatus | string; rows: { name: ReviewCell; value: ReviewCell }[]; truncated: boolean; total_rows?: number }>;
  engines: (Omit<ReviewEngine, "industry"> & { truncated: boolean; total_rows: number }) | null;
  /** Why ``engines`` may be null: listed-but-empty is not the same as out of scope. */
  engines_status?: EnginesStatus;
  warnings: string[];
  detail_url: string;
}
export interface EvidenceContract {
  version: string; scope: string;
  groups: { id: string; label: string; question: string; fields: string[]; boundary: string; selection?: string }[];
  join_keys: string[]; citation_rule: string;
  selection_bias?: string;
  missing_semantics: Record<string, string>;
  provenance_policy: Record<string, string | boolean | null>;
  agent_rules: string[];
  related_reader?: { endpoint: string; purpose: string; boundary: string };
}
export interface ReviewHistory {
  evidence_contract?: EvidenceContract;
  schema_version: 1;
  knowledge_mode: "archived_report_not_as_known";
  start: string; end: string; requested_end: string; requested_days: number;
  calendar_complete: boolean;
  industry: string; industries: string[];
  points: HistoryPoint[];
  metrics: { key: string; label: string; unit: string; source_field: string }[];
  coverage: { available: number; total: number };
  notes: string[];
  limits: Record<string, number>;
}
