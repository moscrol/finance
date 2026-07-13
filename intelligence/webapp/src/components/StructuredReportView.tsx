import { AlertTriangle, Database, Sparkles } from "lucide-react";
import { userFacingIssue } from "../displayText";
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

const FALLBACK_LABELS: Record<string, string> = {
  provider_timeout: "模型响应超时（provider_timeout）",
  provider_unavailable: "模型服务暂不可用（provider_unavailable）",
  quality_gate_rejected: "模型输出未通过质量门禁（quality_gate_rejected）",
  budget_exhausted: "本轮时间预算不足（budget_exhausted）",
};

const SAFE_LLM_PROVIDERS = new Set([
  "zhipu",
  "glm",
  "openai",
  "deepseek",
  "moonshot",
  "kimi",
  "dashscope",
  "qwen",
  "tongyi",
  "fixture",
]);
const SAFE_MODEL_LABEL = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
const CREDENTIAL_FAMILY_CASE_INSENSITIVE =
  /^(?:gh[a-z]_|github_pat_|xox[a-z]-|(?:sk|rk)[-_]|hf_|glpat-|xapp-|bearer)/i;
const CREDENTIAL_FAMILY_CASE_SENSITIVE = /^(?:AKIA|ASIA|AIza|ya29\.)/;
const SUPPORTED_MODEL_FAMILY =
  /^(?:(?:glm|gpt|chatgpt|deepseek|kimi|moonshot|qwen|qwq|tongyi|claude)-[A-Za-z0-9][A-Za-z0-9._-]*|o[134](?:$|[-.][A-Za-z0-9][A-Za-z0-9._-]*)|fixture[A-Za-z0-9._-]*)$/i;
const JWT_SHAPE =
  /^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$/;
const UNSAFE_MODEL_LABEL =
  /(?:\.\.|error|exception|prompt|authorization|api[_-]?key|secret|header|traceback|credential)/i;
const PRIVATE_PATH_COMPONENT =
  /(?:^|\/)(?:users|home|private|var|tmp|etc)(?:\/|$)/i;

function safeProviderLabel(value: string | null): string | null {
  if (!value) return null;
  const normalized = value.toLowerCase();
  return SAFE_LLM_PROVIDERS.has(normalized) ? normalized : null;
}

function looksLikeHighEntropyToken(value: string): boolean {
  const compact = value.replace(/[-_]/g, "");
  if (compact.length < 48 || !/^[A-Za-z0-9]+$/.test(compact)) return false;
  const characterClasses = [/[a-z]/, /[A-Z]/, /[0-9]/].filter((pattern) =>
    pattern.test(compact),
  ).length;
  return characterClasses === 3 && new Set(compact).size >= 16;
}

function safeModelLabel(value: string | null): string | null {
  if (
    !value ||
    !SAFE_MODEL_LABEL.test(value) ||
    CREDENTIAL_FAMILY_CASE_INSENSITIVE.test(value) ||
    CREDENTIAL_FAMILY_CASE_SENSITIVE.test(value) ||
    JWT_SHAPE.test(value) ||
    looksLikeHighEntropyToken(value) ||
    UNSAFE_MODEL_LABEL.test(value) ||
    PRIVATE_PATH_COMPONENT.test(value) ||
    /^[A-Za-z]:\//.test(value) ||
    value.includes("://")
  ) {
    return null;
  }
  return SUPPORTED_MODEL_FAMILY.test(value) ? value : null;
}

function llmStatusLabel(report: StructuredReport): string {
  const { llm } = report;
  if (llm.used) {
    const provider = safeProviderLabel(llm.provider);
    const model = safeModelLabel(llm.model);
    if (provider && model) return `已使用 ${provider} · ${model}`;
    if (provider) return `已使用 ${provider} · 模型信息已隐藏`;
    return "已使用模型 · 服务信息已隐藏";
  }
  if (!llm.configured) return "模型服务未配置 · 已使用确定性回退";
  if (!llm.attempted) return "模型服务可用 · 本轮未调用";
  const fallback = llm.fallback_reason
    ? FALLBACK_LABELS[llm.fallback_reason]
    : null;
  return `模型服务已尝试 · 已回退：${fallback || "模型输出未采用"}`;
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
              {userFacingIssue(warning)}
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
  const llmLabel = llmStatusLabel(report);
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
                <li key={warning}>{userFacingIssue(warning)}</li>
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
