export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface RunArtifact {
  artifact_id: string;
  path: string;
  renderer: string;
  title: string;
  sha256: string;
  bytes: number;
  previewable: boolean;
  downloadable: boolean;
}

export interface Run {
  run_id: string;
  user: string;
  question: string;
  task_type: string;
  status: RunStatus;
  schema_version: number;
  session_id: string | null;
  parent_run_id: string | null;
  created_at: string;
  finished_at: string | null;
  source_date: string | null;
  duckdb_cutoff: string | null;
  kb_commit: string | null;
  manifest_ref: string | null;
  degrades: string[];
  error: string | null;
  artifacts: RunArtifact[];
}

export interface TraceStep {
  step_id: string;
  name: string;
  status: "running" | "completed" | "failed" | "skipped";
  started_at: string;
  finished_at: string | null;
  input_summary: string;
  output_summary: string;
  warnings: string[];
  retrieval?: {
    sources?: string[];
    citation_counts?: Record<string, number>;
    trade_date?: string | null;
    matched_theme?: string | null;
  };
}

export interface Followup {
  type: string;
  question: string;
  rationale?: string;
}

export interface EvidenceItem {
  id: string;
  label: string;
  kind: string;
  classification: string;
  detail: string;
  status: string;
}

export interface MemoryItem {
  label: string;
  detail: string;
  source: string;
}

export interface RunContext {
  evidence: EvidenceItem[];
  memory: MemoryItem[];
  review: MemoryItem[];
  gaps: string[];
  warnings: string[];
  metadata: {
    source_date: string | null;
    duckdb_cutoff: string | null;
    kb_commit: string | null;
    manifest_ref: string | null;
  };
}

export interface ArtifactDescriptor {
  artifact_id: string;
  title: string;
  category: string;
  format: string;
  date: string | null;
  viewer: "native_markdown" | "native_json" | "legacy_html" | "download";
  source_of_truth: string | null;
  source_path: string;
  related_run_id: string | null;
  status: "ok" | "warn" | "missing";
  schema_version: number;
  updated_at: string | null;
  canonical_exists: boolean;
}

export interface ReportMetric {
  label: string;
  value: string;
  tone?: string;
  context?: string;
}

export interface ReportMeta {
  label: string;
  value: string;
}

export interface ReportItem {
  title: string;
  summary: string;
  badges: string[];
  meta?: ReportMeta[];
  next_action?: string;
  details?: string[];
}

export interface ReportSection {
  title: string;
  items: ReportItem[];
}

export interface DailyReportProjection {
  report_type: "daily_agent" | "daily_review";
  title: string;
  date: string | null;
  source_mode: "canonical_json" | "canonical_markdown" | "legacy_html_projection";
  plain_summary: string[];
  metrics: ReportMetric[];
  sections: ReportSection[];
  glossary: Array<{ term: string; definition: string }>;
  provenance: {
    canonical_path: string | null;
    rendered_path: string | null;
    warnings: string[];
    original_report_available: boolean;
    original_artifact_id?: string | null;
    generated_at?: string | null;
  };
}

export interface StructuredReportMetric {
  label: string;
  value: string;
  context?: string | null;
  tone?: string;
}

export interface StructuredReportItem {
  title?: string;
  summary: string;
  badges?: string[];
  meta?: ReportMeta[];
  next_action?: string;
}

export interface StructuredReportTable {
  columns: Array<{ key: string; label: string }>;
  rows: Array<Record<string, string | number | null>>;
}

export interface StructuredReportModule {
  module_id: string;
  title: string;
  kind: string;
  status: "complete" | "degraded";
  summary: string | null;
  content: string | null;
  metrics: StructuredReportMetric[];
  items: StructuredReportItem[];
  table: StructuredReportTable | null;
  warnings: string[];
  provenance: {
    source: string | null;
    as_of?: string | null;
    generated_by?: string;
  };
}

export interface StructuredReport {
  schema_version: number;
  report_id: string;
  title: string;
  task_type: string;
  status: "streaming" | "completed" | "failed";
  as_of: string | null;
  llm: {
    used: boolean;
    provider: string | null;
    model: string | null;
  };
  modules: StructuredReportModule[];
  warnings: string[];
  completed_at?: string;
}

export interface StructuredReportEvent {
  event_id: string;
  event_type: "report_start" | "report_module" | "report_complete" | "report_error";
  created_at: string;
  payload: {
    report?: StructuredReport;
    module?: StructuredReportModule;
  };
}

export interface Workflow {
  id: "daily" | "theme" | "stock_research";
  title: string;
  description: string;
  task_type: string;
  artifact_id: string | null;
  prompt: string;
}

export interface Bootstrap {
  user: string;
  workflows: Workflow[];
  recent_runs: Run[];
  latest_artifacts: ArtifactDescriptor[];
  latest_daily_artifact: ArtifactDescriptor | null;
  pending_review_count: number;
  needs_human_action: number;
  data_cutoff: string | null;
}

export interface RunBundle {
  run: Run;
  trace: TraceStep[];
  followups: Followup[];
  context: RunContext;
  answer: string | null;
  structuredReport: StructuredReport | null;
  registeredArtifacts: ArtifactDescriptor[];
}

export type Surface =
  | { kind: "home" }
  | { kind: "run"; runId: string }
  | { kind: "library" }
  | { kind: "artifact"; artifactId: string };
