import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Clock3,
  FileJson2,
  FileText,
  Link2,
  RefreshCw,
} from "lucide-react";
import type { RunBundle, TraceStep } from "../types";
import { MarkdownView } from "./MarkdownView";
import { StatusBadge } from "./StatusBadge";

const stageNames: Record<string, string> = {
  ask_retrieve_compose: "查询盘面与检索证据",
  render_artifacts: "生成回答与产物",
  foresight_followups: "生成后续研究问题",
};

function latestSteps(trace: TraceStep[]): TraceStep[] {
  const steps = new Map<string, TraceStep>();
  trace.forEach((step) => steps.set(step.step_id, step));
  return [...steps.values()];
}

interface RunViewProps {
  bundle: RunBundle;
  connection: "connected" | "reconnecting";
  onOpenRun: (runId: string) => void;
  onOpenArtifact: (artifactId: string) => void;
  onFollowup: (question: string) => void;
}

export function RunView({
  bundle,
  connection,
  onOpenRun,
  onOpenArtifact,
  onFollowup,
}: RunViewProps) {
  const { run, trace, followups, answer, registeredArtifacts } = bundle;
  const steps = latestSteps(trace);

  return (
    <article className="run-view">
      <header className="run-header">
        <div className="run-title-row">
          <div>
            <span className="eyebrow">
              {run.task_type} · {run.run_id}
            </span>
            <h1>{run.question}</h1>
          </div>
          <div className="run-badges">
            <StatusBadge status={run.status} />
            {run.degrades.length > 0 && <StatusBadge status="degraded" />}
            {connection === "reconnecting" && <StatusBadge status="reconnecting" />}
          </div>
        </div>
        <dl className="run-meta">
          <div>
            <dt>创建时间</dt>
            <dd>{new Date(run.created_at).toLocaleString("zh-CN")}</dd>
          </div>
          <div>
            <dt>数据截止</dt>
            <dd>{run.source_date ?? run.duckdb_cutoff ?? "未记录"}</dd>
          </div>
          <div>
            <dt>产物</dt>
            <dd>{run.artifacts.length} 个</dd>
          </div>
        </dl>
        {run.parent_run_id && (
          <button
            className="parent-link"
            type="button"
            onClick={() => onOpenRun(run.parent_run_id!)}
          >
            <ArrowLeft aria-hidden="true" size={15} />
            返回父任务
          </button>
        )}
      </header>

      {run.error && (
        <div className="alert alert-error" role="alert">
          <AlertCircle aria-hidden="true" size={18} />
          <div>
            <strong>运行失败</strong>
            <p>{run.error}</p>
          </div>
        </div>
      )}

      {run.degrades.length > 0 && (
        <div className="alert alert-warning" role="status">
          <RefreshCw aria-hidden="true" size={18} />
          <div>
            <strong>本次研究使用了降级路径</strong>
            <ul>
              {run.degrades.map((degrade) => (
                <li key={degrade}>{degrade}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <section className="run-section progress-section" aria-labelledby="progress-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">运行轨迹</span>
            <h2 id="progress-heading">研究阶段</h2>
          </div>
          {run.status === "running" && (
            <span className="live-label">
              <Clock3 aria-hidden="true" size={15} />
              实时更新
            </span>
          )}
        </div>
        <ol className="progress-list">
          {run.status === "queued" && (
            <li className="progress-row active">
              <span className="step-marker" />
              <span>
                <strong>理解问题</strong>
                <small>等待研究任务开始</small>
              </span>
              <StatusBadge status="queued" />
            </li>
          )}
          {steps.map((step) => (
            <li
              className={`progress-row ${step.status === "running" ? "active" : ""}`}
              key={step.step_id}
            >
              <span className="step-marker" />
              <span>
                <strong>{stageNames[step.name] ?? "处理研究步骤"}</strong>
                <small>{step.output_summary || step.input_summary || "处理中"}</small>
              </span>
              <StatusBadge
                status={
                  step.status === "completed"
                    ? "completed"
                    : step.status === "failed"
                      ? "failed"
                      : "running"
                }
              />
            </li>
          ))}
          {steps.length === 0 && run.status !== "queued" && (
            <li className="quiet-empty">尚未写入运行步骤</li>
          )}
        </ol>
      </section>

      <section className="run-section answer-section" aria-labelledby="answer-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">研究正文</span>
            <h2 id="answer-heading">回答</h2>
          </div>
        </div>
        {answer ? (
          <MarkdownView source={answer} />
        ) : run.status === "failed" ? (
          <div className="quiet-empty">
            <span>没有生成回答产物</span>
            <small>已保留运行轨迹和失败原因，可据此重试。</small>
          </div>
        ) : (
          <div className="answer-loading">
            <span className="loading-line" />
            <span className="loading-line short" />
            <span>回答将在研究完成后出现</span>
          </div>
        )}
      </section>

      <section className="run-section" aria-labelledby="artifacts-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">可追溯输出</span>
            <h2 id="artifacts-heading">产物</h2>
          </div>
        </div>
        <div className="artifact-rows">
          {run.artifacts.map((artifact) => {
            const registered = registeredArtifacts.find(
              (item) => item.related_run_id === run.run_id && item.source_path.endsWith(artifact.path),
            );
            const Icon = artifact.renderer === "json" ? FileJson2 : FileText;
            return (
              <button
                className="artifact-row"
                type="button"
                key={artifact.artifact_id}
                disabled={!registered}
                onClick={() => registered && onOpenArtifact(registered.artifact_id)}
              >
                <Icon aria-hidden="true" size={18} />
                <span>
                  <strong>{artifact.title}</strong>
                  <small>
                    {artifact.renderer} · {(artifact.bytes / 1024).toFixed(1)} KB
                  </small>
                </span>
                {registered ? <ArrowRight aria-hidden="true" size={16} /> : <Link2 aria-hidden="true" size={16} />}
              </button>
            );
          })}
          {run.artifacts.length === 0 && <div className="quiet-empty">暂无产物</div>}
        </div>
      </section>

      <section className="run-section followup-section" aria-labelledby="followups-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">继续研究</span>
            <h2 id="followups-heading">猜你想问</h2>
          </div>
        </div>
        <div className="followup-list">
          {followups.map((followup) => (
            <button
              className="followup-row"
              type="button"
              key={`${followup.type}:${followup.question}`}
              onClick={() => onFollowup(followup.question)}
            >
              <span>
                <strong>{followup.question}</strong>
                {followup.rationale && <small>{followup.rationale}</small>}
              </span>
              <ArrowRight aria-hidden="true" size={16} />
            </button>
          ))}
          {run.status === "completed" && followups.length === 0 && (
            <div className="quiet-empty">本次运行没有生成追问</div>
          )}
        </div>
      </section>
    </article>
  );
}
