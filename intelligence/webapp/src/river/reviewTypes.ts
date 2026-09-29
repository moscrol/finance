export type ReviewCell = string | number | null;
export interface ReviewBlock { kind: "table" | "heading" | "note" | "text" | "conclusion" | "chart"; title?: string | null; text?: string; columns?: string[]; rows?: ReviewCell[][] }
export interface ReviewSection { id: string; index: number; title: string; blocks: ReviewBlock[] }
export interface ReviewMatrix { industry: string; dates: string[]; rows: ReviewCell[][]; status: "available" | "empty" }
export interface ReviewEngine { industry: string; columns: string[]; rows: ReviewCell[][] }
export type MatrixMode = "double_red" | "stock_highs" | "limit_up";
export interface ReviewReport {
  facts: Record<string, unknown>; industries: string[];
  matrices: Record<MatrixMode, ReviewMatrix[]>; engines: ReviewEngine[];
  sections: ReviewSection[]; diagnostics: string[]; warnings: string[];
  core_board: { dimension: string; conclusion: string }[];
}
export interface ReviewSnapshot {
  schema_version: number; trade_date: string; status: "available" | "missing";
  available_dates: string[]; report: ReviewReport | null; message?: string;
  provenance?: { source_path: string; generated_at: string | null; sha256: string; note: string };
}
