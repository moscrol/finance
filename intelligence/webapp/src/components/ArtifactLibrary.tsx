import {
  Archive,
  FileCode2,
  FileJson2,
  FileText,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { ArtifactDescriptor } from "../types";
import { StatusBadge } from "./StatusBadge";

interface ArtifactLibraryProps {
  artifacts: ArtifactDescriptor[];
  loading: boolean;
  onOpen: (artifactId: string) => void;
}

const categoryLabels: Record<string, string> = {
  run: "研究运行",
  daily_agent: "每日 Agent",
  daily_review: "每日复盘",
  theme_candidates: "题材候选",
  cockpit: "驾驶舱",
  forecast_ledger: "预测回检",
  strategy_matrix: "策略矩阵",
  briefing: "研究简报",
  dual_blind: "双盲对照",
};

function ArtifactIcon({ format }: { format: string }) {
  if (format === "json") return <FileJson2 aria-hidden="true" size={18} />;
  if (format === "html") return <FileCode2 aria-hidden="true" size={18} />;
  return <FileText aria-hidden="true" size={18} />;
}

export function ArtifactLibrary({ artifacts, loading, onOpen }: ArtifactLibraryProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState("");
  const categories = useMemo(
    () => [...new Set(artifacts.map((artifact) => artifact.category))].sort(),
    [artifacts],
  );
  const dates = useMemo(
    () =>
      [
        ...new Set(
          artifacts
            .map((artifact) => artifact.date)
            .filter((artifactDate): artifactDate is string => artifactDate !== null),
        ),
      ].sort((left, right) => right.localeCompare(left)),
    [artifacts],
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return artifacts.filter((artifact) => {
      if (category && artifact.category !== category) return false;
      if (date && artifact.date !== date) return false;
      if (status && artifact.status !== status) return false;
      if (!needle) return true;
      return [artifact.title, artifact.source_path, artifact.category]
        .join(" ")
        .toLocaleLowerCase()
        .includes(needle);
    });
  }, [artifacts, category, date, query, status]);

  return (
    <div className="library-surface">
      <header className="surface-header">
        <span className="eyebrow">Human-readable Coverage</span>
        <h1>产物库</h1>
        <p>只展示 Registry 已注册内容。每项产物都能回到 canonical 来源，或明确标记来源缺失。</p>
      </header>

      <div className="library-toolbar" role="search">
        <label className="search-field">
          <Search aria-hidden="true" size={17} />
          <span className="sr-only">搜索产物</span>
          <input
            value={query}
            placeholder="搜索标题、分类或来源…"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="select-field">
          <SlidersHorizontal aria-hidden="true" size={16} />
          <span className="sr-only">按分类筛选</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">全部分类</option>
            {categories.map((item) => (
              <option value={item} key={item}>
                {categoryLabels[item] ?? item}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">按状态筛选</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">全部状态</option>
            <option value="ok">可用</option>
            <option value="warn">需核对</option>
            <option value="missing">文件缺失</option>
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">按日期筛选</span>
          <select value={date} onChange={(event) => setDate(event.target.value)}>
            <option value="">全部日期</option>
            {dates.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="library-summary">
        <span>{filtered.length} 项产物</span>
        <span>{artifacts.filter((artifact) => artifact.status !== "ok").length} 项需处理</span>
      </div>

      <div className="library-list">
        {loading && <div className="quiet-empty">正在读取 Artifact Registry…</div>}
        {!loading &&
          filtered.map((artifact) => (
            <button
              className="library-row"
              type="button"
              key={artifact.artifact_id}
              onClick={() => onOpen(artifact.artifact_id)}
            >
              <span className="library-icon">
                <ArtifactIcon format={artifact.format} />
              </span>
              <span className="library-copy">
                <strong>{artifact.title}</strong>
                <small>
                  {categoryLabels[artifact.category] ?? artifact.category}
                  {artifact.date ? ` · ${artifact.date}` : ""}
                  {` · ${artifact.format.toUpperCase()}`}
                </small>
                <code>{artifact.source_path}</code>
              </span>
              <StatusBadge status={artifact.status} />
            </button>
          ))}
        {!loading && filtered.length === 0 && (
          <div className="library-empty">
            <Archive aria-hidden="true" size={28} />
            <strong>没有符合条件的产物</strong>
            <span>调整搜索或筛选条件。</span>
          </div>
        )}
      </div>
    </div>
  );
}
