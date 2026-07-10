import {
  AlertCircle,
  ArrowLeft,
  Download,
  ExternalLink,
  FileQuestion,
} from "lucide-react";
import { supportsDailyProjection } from "../dailyReports";
import type {
  ArtifactDescriptor,
  DailyReportProjection,
} from "../types";
import { DailyReportView } from "./DailyReportView";
import { MarkdownView } from "./MarkdownView";
import { StatusBadge } from "./StatusBadge";

interface ArtifactViewerProps {
  artifact: ArtifactDescriptor;
  content: string | null;
  loading: boolean;
  contentUrl: string;
  projection?: DailyReportProjection | null;
  projectionError?: string | null;
  originalReportUrl?: string;
  onBack: () => void;
  onOpenRun: (runId: string) => void;
}

function JsonContent({ source }: { source: string }) {
  let rendered = source;
  try {
    rendered = JSON.stringify(JSON.parse(source), null, 2);
  } catch {
    rendered = source;
  }
  return <pre className="json-view">{rendered}</pre>;
}

export function ArtifactViewer({
  artifact,
  content,
  loading,
  contentUrl,
  projection = null,
  projectionError = null,
  originalReportUrl,
  onBack,
  onOpenRun,
}: ArtifactViewerProps) {
  const isDailyReport = supportsDailyProjection(artifact);

  return (
    <div className="artifact-viewer">
      <header className="artifact-header">
        <button className="text-button" type="button" onClick={onBack}>
          <ArrowLeft aria-hidden="true" size={16} />
          返回产物库
        </button>
        <div className="artifact-title-row">
          <div>
            <span className="eyebrow">{artifact.category}</span>
            <h1>{artifact.title}</h1>
          </div>
          <StatusBadge status={artifact.status} />
        </div>
        <dl className="artifact-meta">
          <div>
            <dt>日期</dt>
            <dd>{artifact.date ?? "未标记"}</dd>
          </div>
          <div>
            <dt>格式</dt>
            <dd>{artifact.format.toUpperCase()}</dd>
          </div>
          <div>
            <dt>来源</dt>
            <dd>{artifact.source_of_truth ?? "仅有渲染物"}</dd>
          </div>
        </dl>
        <div className="artifact-actions">
          {artifact.related_run_id && (
            <button
              className="secondary-button"
              type="button"
              onClick={() => onOpenRun(artifact.related_run_id!)}
            >
              查看生成任务
            </button>
          )}
          {artifact.status !== "missing" && !isDailyReport && (
            <>
              <a className="secondary-button" href={contentUrl} target="_blank" rel="noreferrer">
                <ExternalLink aria-hidden="true" size={15} />
                新窗口打开
              </a>
              <a className="secondary-button" href={contentUrl} download>
                <Download aria-hidden="true" size={15} />
                下载
              </a>
            </>
          )}
        </div>
      </header>

      {!artifact.canonical_exists && (
        <div className="alert alert-warning" role="status">
          <AlertCircle aria-hidden="true" size={18} />
          <div>
            <strong>Canonical 来源缺失</strong>
            <p>当前只能读取已注册的渲染物，不能把它视为新的事实源。</p>
          </div>
        </div>
      )}

      {artifact.status === "missing" ? (
        <div className="viewer-empty">
          <FileQuestion aria-hidden="true" size={34} />
          <h2>产物文件不存在</h2>
          <p>Registry 保留了来源记录。请重新运行对应生成流程后再打开。</p>
          <code>{artifact.source_path}</code>
        </div>
      ) : isDailyReport && loading ? (
        <div className="quiet-empty">正在生成原生报告…</div>
      ) : isDailyReport && projection ? (
        <DailyReportView
          projection={projection}
          originalReportUrl={originalReportUrl}
        />
      ) : isDailyReport && projectionError ? (
        <div className="native-report-error" role="alert">
          <FileQuestion aria-hidden="true" size={30} />
          <h2>暂时无法生成原生报告</h2>
          <p>{projectionError}</p>
          <p>请检查 canonical 来源后重试。原始报告可用时仍可在下方核对。</p>
          {originalReportUrl && (
            <details className="daily-disclosure original-report">
              <summary>原始报告</summary>
              <div className="iframe-shell">
                <iframe
                  title={`原始报告：${artifact.title}`}
                  src={originalReportUrl}
                  sandbox="allow-scripts"
                  referrerPolicy="no-referrer"
                />
              </div>
            </details>
          )}
        </div>
      ) : artifact.viewer === "legacy_html" ? (
        <div className="iframe-shell">
          <iframe
            title={artifact.title}
            src={contentUrl}
            sandbox="allow-scripts"
            referrerPolicy="no-referrer"
          />
        </div>
      ) : loading ? (
        <div className="quiet-empty">正在加载产物内容…</div>
      ) : artifact.viewer === "native_markdown" && content !== null ? (
        <MarkdownView source={content} className="artifact-native-view" />
      ) : artifact.viewer === "native_json" && content !== null ? (
        <JsonContent source={content} />
      ) : (
        <div className="viewer-empty">
          <FileQuestion aria-hidden="true" size={34} />
          <h2>暂不支持内嵌预览</h2>
          <p>可使用上方按钮在新窗口打开或下载。</p>
        </div>
      )}
    </div>
  );
}
