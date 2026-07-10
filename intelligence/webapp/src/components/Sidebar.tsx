import {
  Archive,
  BookOpenText,
  ChevronRight,
  FileSearch,
  LayoutDashboard,
  PanelLeftClose,
  Plus,
  Search,
} from "lucide-react";
import type { Bootstrap, Run, Surface, Workflow } from "../types";
import { StatusBadge } from "./StatusBadge";

interface SidebarProps {
  bootstrap: Bootstrap | null;
  surface: Surface;
  onHome: () => void;
  onLibrary: () => void;
  onOpenRun: (runId: string) => void;
  onWorkflow: (workflow: Workflow) => void;
}

const workflowIcons = {
  daily: LayoutDashboard,
  theme: FileSearch,
  stock_research: BookOpenText,
};

function runLabel(run: Run): string {
  return run.question.length > 28 ? `${run.question.slice(0, 28)}…` : run.question;
}

export function Sidebar({
  bootstrap,
  surface,
  onHome,
  onLibrary,
  onOpenRun,
  onWorkflow,
}: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="工作台导航">
      <div className="brand">
        <div className="brand-mark">MI</div>
        <div className="brand-copy">
          <strong>Market Intelligence</strong>
          <span>Workbench</span>
        </div>
        <PanelLeftClose className="desktop-only" aria-hidden="true" size={17} />
      </div>

      <button className="new-research-button" type="button" onClick={onHome}>
        <Plus aria-hidden="true" size={17} />
        <span>新建研究</span>
      </button>

      <nav className="sidebar-nav" aria-label="主要入口">
        <button
          type="button"
          className={surface.kind === "home" ? "nav-row active" : "nav-row"}
          onClick={onHome}
          title="研究首页"
        >
          <Search aria-hidden="true" size={17} />
          <span>研究首页</span>
        </button>
        <button
          type="button"
          className={surface.kind === "library" ? "nav-row active" : "nav-row"}
          onClick={onLibrary}
          title="产物库"
        >
          <Archive aria-hidden="true" size={17} />
          <span>产物库</span>
          {!!bootstrap?.needs_human_action && (
            <span className="nav-count" aria-label={`${bootstrap.needs_human_action} 个需核对项`}>
              {bootstrap.needs_human_action}
            </span>
          )}
        </button>
      </nav>

      <section className="sidebar-section" aria-labelledby="workflow-heading">
        <h2 id="workflow-heading">工作流</h2>
        <div className="sidebar-list">
          {bootstrap?.workflows.map((workflow) => {
            const Icon = workflowIcons[workflow.id];
            return (
              <button
                className="sidebar-row"
                type="button"
                key={workflow.id}
                onClick={() => onWorkflow(workflow)}
                title={workflow.title}
              >
                <Icon aria-hidden="true" size={17} />
                <span>{workflow.title}</span>
                <ChevronRight className="row-chevron" aria-hidden="true" size={15} />
              </button>
            );
          })}
        </div>
      </section>

      <section className="sidebar-section recent-section" aria-labelledby="recent-heading">
        <h2 id="recent-heading">最近任务</h2>
        <div className="recent-runs">
          {bootstrap?.recent_runs.slice(0, 8).map((run) => (
            <button
              className={`recent-run ${surface.kind === "run" && surface.runId === run.run_id ? "active" : ""}`}
              type="button"
              key={run.run_id}
              onClick={() => onOpenRun(run.run_id)}
            >
              <span>{runLabel(run)}</span>
              <StatusBadge status={run.status} />
            </button>
          ))}
          {bootstrap && bootstrap.recent_runs.length === 0 && (
            <p className="sidebar-empty">暂无历史任务</p>
          )}
        </div>
      </section>

      <div className="sidebar-footer">
        <span className="data-dot" aria-hidden="true" />
        <span>数据截止 {bootstrap?.data_cutoff ?? "待生成"}</span>
      </div>
    </aside>
  );
}
