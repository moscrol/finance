import type { ResearchReceiptModel } from "../researchJourney";
import { researchRunLabel } from "../researchJourney";
import "./researchJourney.css";

interface ResearchReceiptProps {
  model: ResearchReceiptModel;
}

function receiptCutoff(cutoff: string | null): string {
  return cutoff ? `数据截至 ${cutoff}` : "数据日期未记录";
}

export function ResearchReceipt({ model }: ResearchReceiptProps) {
  return (
    <section
      className={`research-receipt is-${model.runStatus}`}
      aria-label="研究收据"
    >
      <h3 className="research-receipt-heading">
        {researchRunLabel(model.runStatus)}
      </h3>
      <div className="research-receipt-summary">
        <span>{model.evidenceCount} 条可验证引用</span>
        <span aria-hidden="true"> · </span>
        <span>{receiptCutoff(model.cutoff)}</span>
        <span aria-hidden="true"> · </span>
        <span>{model.artifactCount} 个产物</span>
        <span aria-hidden="true"> · </span>
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
      </div>
    </section>
  );
}
