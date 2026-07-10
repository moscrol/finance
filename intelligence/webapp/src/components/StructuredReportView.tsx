import { AlertTriangle, Database, Sparkles } from "lucide-react";
import type {
  StructuredReport,
  StructuredReportModule,
} from "../types";
import { MarkdownView } from "./MarkdownView";

function displayValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  }
  return value;
}

function ReportModule({ module }: { module: StructuredReportModule }) {
  return (
    <section
      className={`stream-module ${module.status === "degraded" ? "stream-module-degraded" : ""}`}
      aria-labelledby={`module-${module.module_id}`}
    >
      <header className="stream-module-header">
        <div>
          <span className="eyebrow">{module.kind}</span>
          <h3 id={`module-${module.module_id}`}>{module.title}</h3>
        </div>
        <span className={`stream-module-status ${module.status}`}>{module.status}</span>
      </header>

      {module.summary && <p className="stream-module-summary">{module.summary}</p>}

      {module.metrics.length > 0 && (
        <dl className="stream-metrics">
          {module.metrics.map((metric) => (
            <div key={`${module.module_id}:${metric.label}`}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
              {metric.context && <small>{metric.context}</small>}
            </div>
          ))}
        </dl>
      )}

      {module.content && (
        <div className="stream-narrative">
          <MarkdownView source={module.content} />
        </div>
      )}

      {module.table && module.table.rows.length > 0 && (
        <div className="stream-table-shell">
          <table>
            <thead>
              <tr>
                {module.table.columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {module.table.rows.map((row, rowIndex) => (
                <tr key={`${module.module_id}:row:${rowIndex}`}>
                  {module.table!.columns.map((column) => (
                    <td key={column.key}>{displayValue(row[column.key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {module.items.length > 0 && (
        <div className="stream-items">
          {module.items.map((item, index) => (
            <article key={`${module.module_id}:item:${index}`}>
              <div>
                {item.title && <strong>{item.title}</strong>}
                <p>{item.summary}</p>
              </div>
              {!!item.badges?.length && (
                <div className="stream-item-badges">
                  {item.badges.map((badge) => (
                    <span key={badge}>{badge}</span>
                  ))}
                </div>
              )}
              {!!item.meta?.length && (
                <dl>
                  {item.meta.map((meta) => (
                    <div key={`${meta.label}:${meta.value}`}>
                      <dt>{meta.label}</dt>
                      <dd>{meta.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {item.next_action && <small>下一步：{item.next_action}</small>}
            </article>
          ))}
        </div>
      )}

      {module.warnings.length > 0 && (
        <ul className="stream-warnings">
          {module.warnings.map((warning) => (
            <li key={warning}>
              <AlertTriangle aria-hidden="true" size={14} />
              {warning}
            </li>
          ))}
        </ul>
      )}

      <footer className="stream-provenance">
        <Database aria-hidden="true" size={13} />
        <span>{module.provenance.source || "未记录来源"}</span>
        {module.provenance.as_of && <span>截至 {module.provenance.as_of}</span>}
        {module.provenance.generated_by && (
          <span>{module.provenance.generated_by}</span>
        )}
      </footer>
    </section>
  );
}

export function StructuredReportView({ report }: { report: StructuredReport }) {
  const llmLabel = report.llm.used
    ? `${report.llm.provider || "LLM"}${report.llm.model ? ` · ${report.llm.model}` : ""}`
    : "LLM 等待中或已降级";
  return (
    <div className="structured-report" aria-live="polite">
      <header className="structured-report-status">
        <span>
          <Sparkles aria-hidden="true" size={16} />
          {llmLabel}
        </span>
        <span>
          {report.status === "streaming"
            ? `流式生成中 · 已完成 ${report.modules.length} 个模块`
            : `结构化报告 · ${report.modules.length} 个模块${
                report.warnings.length > 0 ? " · 已降级" : ""
              }`}
        </span>
      </header>
      {report.warnings.length > 0 && (
        <div className="alert alert-warning stream-report-warning" role="status">
          <AlertTriangle aria-hidden="true" size={16} />
          <div>
            <strong>本报告包含降级或质量警告</strong>
            <ul>
              {report.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <div className="stream-module-list">
        {report.modules.map((module) => (
          <ReportModule module={module} key={module.module_id} />
        ))}
      </div>
      {report.status === "streaming" && (
        <div className="stream-module-loading" role="status">
          <span />
          正在生成下一个模块…
        </div>
      )}
    </div>
  );
}
