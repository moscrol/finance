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
  kb_index_built_at: string | null;
  kb_index_freshness: string | null;
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
    citations?: Array<Record<string, string>>;
    trade_date?: string | null;
    matched_theme?: string | null;
  };
}

export interface Followup {
  type: string;
  question: string;
  rationale?: string;
  source?: string;
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
    kb_index_built_at: string | null;
    kb_index_freshness: string | null;
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
  source_label?: string | null;
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

export interface StreamEnvelope<TPayload extends Record<string, unknown> = Record<string, unknown>> {
  schema_version: number;
  event_id: string;
  event_type: string;
  run_id: string;
  conversation_id: string | null;
  message_id: string | null;
  seq: number;
  created_at: string;
  payload: TPayload;
}

export type StructuredReportEvent = StreamEnvelope<{
    report?: StructuredReport;
    module?: StructuredReportModule;
  }> & {
    event_type:
      | "report.start"
      | "report.module"
      | "report.complete"
      | "report.error"
      | "report_start"
      | "report_module"
      | "report_complete"
      | "report_error";
  };

export interface Workflow {
  id: "daily" | "theme" | "stock_research";
  title: string;
  description: string;
  task_type: string;
  artifact_id: string | null;
  prompt: string;
}

export interface SelfUseMaturity {
  distinct_trade_dates: number;
  success_rate: number;
  useful_rate: number;
  manual_rescue_rate: number;
  covered_workflows: string[];
  blockers: string[];
  eligible_for_user_decision: boolean;
  passed: boolean;
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
  self_use_maturity: SelfUseMaturity;
}

export type WorkbenchSection =
  | "today"
  | "themes"
  | "signals"
  | "validation"
  | "ask";

export interface DataFreshnessStatus {
  key: string;
  label: string;
  date: string | null;
  status: "complete" | "stale" | "missing" | "partial" | "failed" | "running";
  row_count: number;
  message: string;
  coverage?: {
    covered: number;
    total: number;
    missing: number;
  };
}

export interface MarketOverview {
  trade_date: string | null;
  stage: string;
  stage_source?: string;
  advancers?: number | null;
  advancers_ma5?: number | null;
  breadth_trend?: string;
  limit_up?: number | null;
  limit_down?: number | null;
  total_amount?: number | null;
  amount_vs_yesterday_pct?: number | null;
  amount_vs_ma20_pct?: number | null;
  mainlines: string[];
  risks: string[];
  concentration_pct?: number | null;
  concentration_state?: string;
  strength_marginal_pct?: number | null;
  strength_status?: string;
  validation_points: string[];
}

export interface ThemeState {
  theme_code: string;
  name: string;
  knowledge_stage: string;
  knowledge_stage_index: number;
  knowledge_date: string | null;
  market_stage: string;
  market_stage_index: number;
  market_date: string | null;
  source_count: number;
  sector_count: number;
  stock_count: number;
  sectors: string[];
  direction: string;
  evidence_type: string;
  detail_status: "current" | "stale";
}

export interface SignalCard {
  bucket: "new" | "strengthened" | "weakened" | "pending";
  bucket_label: string;
  title: string;
  change: string;
  summary: string;
  source_type: string;
  source_date: string | null;
  impact: string;
  market_confirmation: string;
  next_validation: string;
}

export interface WinrateRow {
  source_id: string;
  name: string;
  sample_count: number;
  t5_win_rate: number | null;
  t10_win_rate: number | null;
  average_excess: number;
  median_excess: number;
  average_drawdown: number | null;
  best_window: string;
}

export interface SellsideFlowItem {
  theme: string;
  source: string;
  report_date: string | null;
  mention_count: number;
  reason: string;
}

export interface MoneyflowLeader {
  stock_code: string;
  stock_name: string;
  scan_type: string;
  main_buy_net_wan: number | null;
  total_buy_net_wan: number | null;
  score: number | null;
  rank: number | null;
  pct_change: number | null;
}

export interface QuantOrder {
  stock_code: string;
  stock_name: string;
  quant_amount_wan: number | null;
  quant_pct_of_big_buy: number | null;
  cluster_count: number | null;
  biggest_cluster: string | null;
  rank: number | null;
}

export interface MoneyflowTrend {
  stock_code: string;
  stock_name: string;
  trade_date: string;
  history_days: number;
  consecutive_inflow_days: number;
  rank_change: number | null;
  is_new: boolean;
  divergence: string | null;
}

export interface WorkbenchOverview {
  as_of_date: string | null;
  market: MarketOverview;
  themes: ThemeState[];
  theme_axes: {
    knowledge: string[];
    market: string[];
  };
  signals: {
    new: SignalCard[];
    strengthened: SignalCard[];
    weakened: SignalCard[];
    pending: SignalCard[];
  };
  signal_date: string | null;
  winrate: WinrateRow[];
  sellside_flow: {
    priority: SellsideFlowItem[];
    confirmation: SellsideFlowItem[];
    caution: SellsideFlowItem[];
  };
  sellside_date: string | null;
  moneyflow: {
    status: string;
    target_date: string | null;
    trade_date: string | null;
    coverage: Record<string, number>;
    leaders: MoneyflowLeader[];
    quant_orders: QuantOrder[];
    warnings: string[];
    source: string;
  };
  moneyflow_trends: MoneyflowTrend[];
  validation: {
    logic_effectiveness: Record<string, unknown>;
    hypothesis_status: string;
  };
  data_status: DataFreshnessStatus[];
  agent_artifact: string | null;
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

export interface Conversation {
  conversation_id: string;
  user_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  summary: string;
  last_run_id: string | null;
}

export interface ChatMessage {
  message_id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
  status: string;
  run_id: string | null;
  skill_mode?: SkillMode;
  selected_skill_ids: string[];
  perspective_mode: PerspectiveMode;
  selected_perspective_ids: string[];
  invoked_skill_ids: string[];
  citations: Array<Record<string, unknown>>;
  degrades: string[];
  followups?: Followup[];
}

export type SkillMode = "manual" | "auto" | "hybrid";
export type PerspectiveMode = "neutral" | "single" | "compare";

export interface PerspectiveDescription {
  perspective_id: string;
  display_name: string;
  type: string;
  article_count: number;
  profile_confidence: string;
}

export interface ProductSkillDescription {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  triggers: string[];
  input_schema: Record<string, unknown>;
  permissions: string[];
  timeout_seconds: number;
}

export interface CreateMessageRequest {
  content: string;
  skill_mode: SkillMode;
  selected_skill_ids?: string[];
  perspective_mode?: PerspectiveMode;
  selected_perspective_ids?: string[];
  user?: string;
}

export interface CreateMessageResponse {
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string;
  run_id: string;
}

export type LLMProviderId =
  | "zhipu"
  | "openai"
  | "deepseek"
  | "moonshot"
  | "dashscope";

export interface LLMConfig {
  mode: "built_in" | "byok";
  display_name: string;
  ready: boolean;
  session_only: boolean;
  built_in_ready: boolean;
  provider: LLMProviderId | null;
  model: string | null;
}

export interface ConfigureLLMRequest {
  provider: LLMProviderId;
  api_key: string;
  model?: string;
  user?: string;
}

export type SkillInvocationStatus =
  | "pending"
  | "running"
  | "completed"
  | "degraded"
  | "failed";

export interface LiveSkillInvocation {
  skill_id: string;
  selection_source: "manual" | "rule" | "llm" | "unknown";
  reason: string;
  status: SkillInvocationStatus;
  warnings: string[];
}

export interface LiveWorkflow {
  owner: string;
  label: string;
  executionMode: "inline" | "subtask";
  preset: string;
  requiredSkillIds: string[];
  retrievalStages: string[];
  outputSchema: string;
  presentationKind: string;
  maxWallTimeSeconds: number;
  status: "loaded";
}

export type AnswerPhase =
  | "verified_draft"
  | "validated_synthesis"
  | "verified_fallback";

export interface LiveMessageState {
  conversationId: string;
  messageId: string;
  runId: string;
  narrative: string;
  answerRevision: number;
  answerPhase: AnswerPhase | null;
  answerFinal: boolean;
  report: StructuredReport | null;
  workflow: LiveWorkflow | null;
  skillInvocations: Record<string, LiveSkillInvocation>;
  status: "pending" | "streaming" | "completed" | "failed" | "cancelled";
  connection: "connected" | "reconnecting";
  cancelRequested: boolean;
}

export type Surface =
  | { kind: "home" }
  | { kind: WorkbenchSection }
  | { kind: "run"; runId: string }
  | { kind: "library" }
  | { kind: "artifact"; artifactId: string };
