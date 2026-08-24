import {
  AlertTriangle,
  CalendarDays,
  FileStack,
  Link2,
} from "lucide-react";
import type { ResearchReceiptModel } from "../researchJourney";
import type { RunStatus } from "../types";
import "./researchJourney.css";

interface ResearchReceiptProps {
  model: ResearchReceiptModel;
}

const runStatusLabels: Record<RunStatus, string> = {
  queued: "等待中",
  running: "正在研究",
  completed: "已完成",
  failed: "需要关注",
  cancelled: "已停止",
};

export function ResearchReceipt({ model }: ResearchReceiptProps) {
  const issueSummary = model.issueLabels.join("；") || undefined;

  return (
    <section
      className={`research-receipt is-${model.runStatus}`}
      aria-label="研究收据"
      data-issue-summary={issueSummary}
    >
      <div className="research-receipt-heading">
        <h3>Foresight · {runStatusLabels[model.runStatus]}</h3>
        <small>研究收据</small>
      </div>
      <ul
        className="research-receipt-metrics"
        role="list"
        aria-label="研究收据指标"
      >
        <li>
          <Link2 aria-hidden="true" size={13} />
          <span>{model.evidenceCount} 条可验证引用</span>
        </li>
        <li>
          <CalendarDays aria-hidden="true" size={13} />
          <span>
            {model.cutoff ? `数据截至 ${model.cutoff}` : "数据日期未记录"}
          </span>
        </li>
        <li>
          <FileStack aria-hidden="true" size={13} />
          <span>{model.artifactCount} 个产物</span>
        </li>
        <li className="research-receipt-issues">
          <AlertTriangle aria-hidden="true" size={13} />
          {model.issueCount > 0 ? (
            <details className="research-receipt-issue-disclosure">
              <summary tabIndex={0}>{model.issueCount} 项限制/缺口</summary>
              <ul
                className="research-receipt-issue-labels"
                role="list"
                aria-label="限制与缺口详情"
              >
                {model.issueLabels.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </details>
          ) : (
            <span>0 项限制/缺口</span>
          )}
        </li>
      </ul>
    </section>
  );
}
