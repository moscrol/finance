import {
  ArrowRight,
  BookOpenText,
  CalendarClock,
  FileSearch,
  LayoutDashboard,
} from "lucide-react";
import type { Bootstrap, Workflow } from "../types";
import { Composer } from "./Composer";
import { StatusBadge } from "./StatusBadge";

interface ResearchHomeProps {
  bootstrap: Bootstrap | null;
  draft: string;
  taskType: string;
  submitting: boolean;
  onDraftChange: (value: string) => void;
  onSubmit: (question: string) => void;
  onWorkflow: (workflow: Workflow) => void;
  onOpenRun: (runId: string) => void;
}

const workflowIcons = {
  daily: LayoutDashboard,
  theme: FileSearch,
  stock_research: BookOpenText,
};

export function ResearchHome({
  bootstrap,
  draft,
  taskType,
  submitting,
  onDraftChange,
  onSubmit,
  onWorkflow,
  onOpenRun,
}: ResearchHomeProps) {
  const pendingRuns = bootstrap?.recent_runs.filter((run) =>
    ["queued", "running", "failed"].includes(run.status),
  );

  return (
    <div className="home-surface">
      <header className="home-header">
        <span className="eyebrow">统一研究入口</span>
        <h1>开始一项可追溯的研究</h1>
        <p>自由提问，或从固定工作流开始。每次运行都会保留证据、降级、产物和回检线索。</p>
      </header>

      <Composer
        value={draft}
        taskType={taskType}
        disabled={submitting}
        onChange={onDraftChange}
        onSubmit={onSubmit}
      />

      <section className="workflow-grid" aria-labelledby="home-workflow-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">快捷入口</span>
            <h2 id="home-workflow-heading">常用研究工作流</h2>
          </div>
          <span className="section-meta">共用 Run / Trace / Artifact 协议</span>
        </div>
        <div className="workflow-list">
          {bootstrap?.workflows.map((workflow) => {
            const Icon = workflowIcons[workflow.id];
            return (
              <button
                className="workflow-row"
                type="button"
                key={workflow.id}
                onClick={() => onWorkflow(workflow)}
              >
                <span className="workflow-icon">
                  <Icon aria-hidden="true" size={20} />
                </span>
                <span className="workflow-copy">
                  <strong>{workflow.title}</strong>
                  <small>{workflow.description}</small>
                </span>
                <ArrowRight aria-hidden="true" size={17} />
              </button>
            );
          })}
        </div>
      </section>

      <section className="continue-section" aria-labelledby="continue-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">需要继续</span>
            <h2 id="continue-heading">运行与回检</h2>
          </div>
          {!!bootstrap?.pending_review_count && (
            <span className="pending-review">
              <CalendarClock aria-hidden="true" size={15} />
              {bootstrap.pending_review_count} 个待回检
            </span>
          )}
        </div>
        <div className="continue-list">
          {pendingRuns?.slice(0, 5).map((run) => (
            <button
              className="continue-row"
              type="button"
              key={run.run_id}
              onClick={() => onOpenRun(run.run_id)}
            >
              <span>
                <strong>{run.question}</strong>
                <small>
                  {run.task_type} · {new Date(run.created_at).toLocaleString("zh-CN")}
                </small>
              </span>
              <StatusBadge status={run.status} />
            </button>
          ))}
          {pendingRuns?.length === 0 && (
            <div className="quiet-empty">
              <span>没有等待处理的任务</span>
              <small>新研究会在这里显示运行、失败或待继续状态。</small>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
