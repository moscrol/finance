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
        <span>Foresight · {runStatusLabels[model.runStatus]}</span>
        <small>研究收据</small>
      </div>
      <ul className="research-receipt-metrics">
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
        <li title={issueSummary}>
          <AlertTriangle aria-hidden="true" size={13} />
          <span>{model.issueCount} 项限制/缺口</span>
        </li>
      </ul>
    </section>
  );
}
