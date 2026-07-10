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
  registeredArtifacts: ArtifactDescriptor[];
}

export type Surface =
  | { kind: "home" }
  | { kind: "run"; runId: string }
  | { kind: "library" }
  | { kind: "artifact"; artifactId: string };
