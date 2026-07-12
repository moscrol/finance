import { AlertTriangle, ChevronDown } from "lucide-react";
import { userFacingIssue } from "../displayText";
import type {
  DailyReportProjection,
  ReportItem,
} from "../types";

interface DailyReportViewProps {
  projection: DailyReportProjection;
  originalReportUrl?: string;
}

const sourceLabels = {
  canonical_json: "结构化原始数据",
  canonical_markdown: "原始研究报告",
  legacy_html_projection: "历史 HTML 兼容投影",
};

function ReportRow({ item, ordered }: { item: ReportItem; ordered: boolean }) {
  return (
    <article className={ordered ? "daily-report-row action-row" : "daily-report-row"}>
      <div className="daily-report-row-main">
        <div className="daily-report-item-heading">
          <h4>{item.title}</h4>
          <div className="report-badges">
            {item.badges.map((badge) => (
              <span key={badge}>{badge}</span>
            ))}
          </div>
        </div>
        <p>{item.summary}</p>
        {!!item.meta?.length && (
          <dl className="daily-report-meta">
            {item.meta.map((entry) => (
              <div key={`${entry.label}:${entry.value}`}>
                <dt>{entry.label}</dt>
                <dd>{entry.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {item.next_action && (
          <p className="next-action">
            <strong>下一步</strong>
            <span>{item.next_action}</span>
          </p>
        )}
        {!!item.details?.length && (
          <details className="report-item-details">
            <summary>
              查看证据边界
              <ChevronDown aria-hidden="true" size={15} />
            </summary>
            <ul>
              {item.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}

export function DailyReportView({
  projection,
  originalReportUrl,
}: DailyReportViewProps) {
  const metricHeading =
    projection.report_type === "daily_agent" ? "研究工作量" : "市场温度";
  const isCompatibilityMode =
    projection.source_mode === "legacy_html_projection";

  return (
    <article className="daily-report">
      <header className="daily-report-intro">
        <div>
          <span className="eyebrow">{sourceLabels[projection.source_mode]}</span>
          <h2>{projection.title}</h2>
        </div>
        {projection.date && <time dateTime={projection.date}>{projection.date}</time>}
      </header>

      {isCompatibilityMode && (
        <div className="projection-warning" role="status">
          <AlertTriangle aria-hidden="true" size={18} />
          <div>
            <strong>兼容投影</strong>
            <p>当前只提取历史报告中的已知章节，请结合原始报告核验。</p>
          </div>
        </div>
      )}

      <section
        className="daily-summary"
        aria-labelledby="daily-summary-heading"
        data-testid="daily-summary"
      >
        <h3 id="daily-summary-heading">三件需要知道的事</h3>
        <ol>
          {projection.plain_summary.map((summary) => (
            <li key={summary}>{summary}</li>
          ))}
        </ol>
      </section>

      <section
        className="daily-metrics"
        aria-labelledby="daily-metrics-heading"
        data-testid="daily-metrics"
      >
        <h3 id="daily-metrics-heading">{metricHeading}</h3>
        <div className="daily-metric-grid">
          {projection.metrics.map((metric) => (
            <div
              className={`daily-metric ${metric.tone ? `metric-${metric.tone}` : ""}`}
              key={metric.label}
            >
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              {metric.context && <small>{metric.context}</small>}
            </div>
          ))}
        </div>
      </section>

      <div className="daily-report-sections" data-testid="daily-sections">
        {projection.sections
          .filter((section) => section.items.length > 0)
          .map((section) => (
            <section
              className="daily-report-section"
              aria-labelledby={`section-${section.title}`}
              key={section.title}
            >
              <h3 id={`section-${section.title}`}>{section.title}</h3>
              <div className="daily-report-rows">
                {section.items.map((item) => (
                  <ReportRow
                    item={item}
                    ordered={section.title === "今天要做什么"}
                    key={`${section.title}:${item.title}`}
                  />
                ))}
              </div>
            </section>
          ))}
      </div>

      <details className="daily-disclosure" data-testid="daily-glossary">
        <summary>
          <span>术语表</span>
          <ChevronDown aria-hidden="true" size={16} />
        </summary>
        <dl className="glossary-list">
          {projection.glossary.map((entry) => (
            <div key={entry.term}>
              <dt>{entry.term}</dt>
              <dd>{entry.definition}</dd>
            </div>
          ))}
        </dl>
      </details>

      <footer className="daily-provenance" data-testid="daily-provenance">
        <h3>来源与边界</h3>
        {projection.provenance.warnings.map((warning) => (
          <p className="provenance-warning" key={warning}>
            {userFacingIssue(warning)}
          </p>
        ))}
        <dl>
          <div>
            <dt>原始来源</dt>
            <dd>
              <code>
                {projection.provenance.canonical_path ?? "历史产物未关联原始来源"}
              </code>
            </dd>
          </div>
          {projection.provenance.generated_at && (
            <div>
              <dt>生成时间</dt>
              <dd>{projection.provenance.generated_at}</dd>
            </div>
          )}
        </dl>
      </footer>

      {projection.provenance.original_report_available && originalReportUrl && (
        <details className="daily-disclosure original-report">
          <summary>
            <span>原始报告</span>
            <ChevronDown aria-hidden="true" size={16} />
          </summary>
          <p>沙箱化展示历史渲染物，仅用于归档对照。</p>
          <div className="iframe-shell">
            <iframe
              title={`原始报告：${projection.title}`}
              src={originalReportUrl}
              sandbox="allow-scripts"
              referrerPolicy="no-referrer"
              loading="lazy"
            />
          </div>
        </details>
      )}
    </article>
  );
}
