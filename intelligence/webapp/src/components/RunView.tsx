import {
  AlertTriangle,
  ChevronDown,
  Clock3,
  FileJson2,
  FileText,
} from "lucide-react";
import type { RunBundle, TraceStep } from "../types";
import { StatusBadge } from "./StatusBadge";

const stageNames: Record<string, string> = {
  ask_retrieve_compose: "检索本轮证据并组织回答",
  render_artifacts: "生成回答与产物",
  foresight_followups: "生成后续研究问题",
  route_skills: "选择本轮 Skill",
  ask_current_turn: "执行本轮检索",
};

function latestSteps(trace: TraceStep[]): TraceStep[] {
  const steps = new Map<string, TraceStep>();
  trace.forEach((step) => steps.set(step.step_id, step));
  return [...steps.values()];
}

interface RunViewProps {
  bundle: RunBundle;
  connection: "connected" | "reconnecting";
  onOpenRun?: (runId: string) => void;
  onOpenArtifact: (artifactId: string) => void;
  onFollowup: (question: string) => void;
}

export function RunView({
  bundle,
  connection,
  onOpenArtifact,
  onFollowup,
}: RunViewProps) {
  const { run, trace, followups, registeredArtifacts } = bundle;

  return (
    <details className="message-run-details">
      <summary>
        <span>
          <ChevronDown aria-hidden="true" size={15} />
          运行详情
        </span>
        <span className="message-run-statuses">
          <StatusBadge status={run.status} />
          {run.degrades.length > 0 && <StatusBadge status="degraded" />}
          {connection === "reconnecting" && (
            <StatusBadge status="reconnecting" />
          )}
        </span>
      </summary>

      <div className="message-run-body">
        <dl className="message-run-meta">
          <div>
            <dt>Run</dt>
            <dd>{run.run_id}</dd>
          </div>
          <div>
            <dt>数据截止</dt>
            <dd>{run.source_date ?? run.duckdb_cutoff ?? "未记录"}</dd>
          </div>
        </dl>

        {run.error && (
          <div className="message-run-warning" role="alert">
            <AlertTriangle aria-hidden="true" size={15} />
            {run.error}
          </div>
        )}
        {run.degrades.length > 0 && (
          <div className="message-run-warning" role="status">
            <AlertTriangle aria-hidden="true" size={15} />
            <span>本轮使用降级路径：{run.degrades.join("；")}</span>
          </div>
        )}

        <section aria-labelledby={`trace-${run.run_id}`}>
          <h3 id={`trace-${run.run_id}`}>
            <Clock3 aria-hidden="true" size={15} />
            运行轨迹
          </h3>
          <ol className="message-trace-list">
            {latestSteps(trace).map((step) => (
              <li key={step.step_id}>
                <details>
                  <summary>
                    <span>{stageNames[step.name] ?? "研究步骤"}</span>
                    <StatusBadge
                      status={
                        step.status === "completed"
                          ? "completed"
                          : step.status === "failed"
                            ? "failed"
                            : "running"
                      }
                    />
                  </summary>
                  <dl>
                    <div>
                      <dt>内部工具</dt>
                      <dd>{step.name}</dd>
                    </div>
                    <div>
                      <dt>结果</dt>
                      <dd>
                        {step.output_summary ||
                          step.input_summary ||
                          "尚无摘要"}
                      </dd>
                    </div>
                  </dl>
                </details>
              </li>
            ))}
            {trace.length === 0 && <li>尚未写入运行步骤</li>}
          </ol>
        </section>

        {run.artifacts.length > 0 && (
          <section aria-labelledby={`artifacts-${run.run_id}`}>
            <h3 id={`artifacts-${run.run_id}`}>产物</h3>
            <div className="message-artifacts">
              {run.artifacts.map((artifact) => {
                const registered = registeredArtifacts.find(
                  (item) =>
                    item.related_run_id === run.run_id &&
                    item.source_path.endsWith(artifact.path),
                );
                const Icon =
                  artifact.renderer === "json" ? FileJson2 : FileText;
                return (
                  <button
                    type="button"
                    key={artifact.artifact_id}
                    disabled={!registered}
                    onClick={() =>
                      registered && onOpenArtifact(registered.artifact_id)
                    }
                  >
                    <Icon aria-hidden="true" size={15} />
                    {artifact.title}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {followups.length > 0 && (
          <section aria-labelledby={`followups-${run.run_id}`}>
            <h3 id={`followups-${run.run_id}`}>继续研究</h3>
            <div className="message-followups">
              {followups.map((followup) => (
                <button
                  type="button"
                  key={`${followup.type}:${followup.question}`}
                  onClick={() => onFollowup(followup.question)}
                >
                  {followup.question}
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </details>
  );
}
