import {
  AlertTriangle,
  BrainCircuit,
  Database,
  History,
  ListTree,
  PanelRightClose,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState } from "react";
import type { ArtifactDescriptor, RunBundle, TraceStep } from "../types";

type InspectorTab = "evidence" | "trace" | "memory" | "review";

interface ResearchInspectorProps {
  bundle: RunBundle | null;
  artifact: ArtifactDescriptor | null;
  open: boolean;
  onClose: () => void;
}

const tabs: Array<{ id: InspectorTab; label: string; icon: typeof Database }> = [
  { id: "evidence", label: "证据", icon: Database },
  { id: "trace", label: "运行", icon: ListTree },
  { id: "memory", label: "记忆", icon: BrainCircuit },
  { id: "review", label: "回检", icon: History },
];

function TraceItem({ step }: { step: TraceStep }) {
  return (
    <details className="inspector-trace-row">
      <summary>
        <span className={`trace-dot trace-${step.status}`} />
        <span>
          <strong>{step.output_summary || "研究步骤"}</strong>
          <small>{step.status}</small>
        </span>
      </summary>
      <dl>
        <div>
          <dt>内部工具</dt>
          <dd>{step.name}</dd>
        </div>
        <div>
          <dt>开始</dt>
          <dd>{step.started_at}</dd>
        </div>
        {step.finished_at && (
          <div>
            <dt>完成</dt>
            <dd>{step.finished_at}</dd>
          </div>
        )}
      </dl>
      {step.warnings.length > 0 && (
        <ul>
          {step.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </details>
  );
}

export function ResearchInspector({
  bundle,
  artifact,
  open,
  onClose,
}: ResearchInspectorProps) {
  const [tab, setTab] = useState<InspectorTab>("evidence");
  const context = bundle?.context;

  return (
    <>
      {open && <button className="inspector-backdrop" aria-label="关闭研究检查器" onClick={onClose} />}
      <aside className={`research-inspector ${open ? "open" : ""}`} aria-label="研究检查器">
        <header className="inspector-header">
          <div>
            <span className="eyebrow">Research Inspector</span>
            <strong>研究检查器</strong>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭检查器">
            <X className="drawer-close" aria-hidden="true" size={18} />
            <PanelRightClose className="desktop-close" aria-hidden="true" size={18} />
          </button>
        </header>

        <div className="inspector-tabs" role="tablist" aria-label="检查器视图">
          {tabs.map((item) => {
            const Icon = item.icon;
            return (
              <button
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={tab === item.id ? "active" : ""}
                key={item.id}
                onClick={() => setTab(item.id)}
              >
                <Icon aria-hidden="true" size={15} />
                {item.label}
              </button>
            );
          })}
        </div>

        <div className="inspector-body">
          {tab === "evidence" && (
            <section aria-labelledby="inspector-evidence-heading">
              <h2 id="inspector-evidence-heading">证据与边界</h2>
              {artifact && (
                <div className="inspector-source-card">
                  <ShieldCheck aria-hidden="true" size={18} />
                  <div>
                    <strong>{artifact.canonical_exists ? "Canonical 来源可用" : "Canonical 来源缺失"}</strong>
                    <code>{artifact.source_of_truth ?? artifact.source_path}</code>
                  </div>
                </div>
              )}
              {context &&
                (context.metadata.kb_commit ||
                  context.metadata.kb_index_built_at ||
                  context.metadata.kb_index_freshness) && (
                  <div className="inspector-source-card">
                    <Database aria-hidden="true" size={18} />
                    <div>
                      <strong>知识库索引快照</strong>
                      <code>
                        {[
                          context.metadata.kb_commit
                            ? `revision=${context.metadata.kb_commit.slice(0, 12)}`
                            : "",
                          context.metadata.kb_index_built_at
                            ? `built_at=${context.metadata.kb_index_built_at}`
                            : "",
                          context.metadata.kb_index_freshness
                            ? `freshness=${context.metadata.kb_index_freshness}`
                            : "",
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </code>
                    </div>
                  </div>
                )}
              {context?.evidence.map((item) => (
                <div className="inspector-item" key={item.id}>
                  <span className="evidence-mark" aria-hidden="true" />
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.detail}</p>
                    <small>{item.classification}</small>
                  </div>
                </div>
              ))}
              {context?.gaps.map((gap) => (
                <div className="inspector-item inspector-warning" key={gap}>
                  <AlertTriangle aria-hidden="true" size={16} />
                  <div>
                    <strong>数据缺口或降级</strong>
                    <p>{gap}</p>
                  </div>
                </div>
              ))}
              {!artifact && (!context || (context.evidence.length === 0 && context.gaps.length === 0)) && (
                <div className="inspector-empty">当前页面没有可展示的证据记录。</div>
              )}
            </section>
          )}

          {tab === "trace" && (
            <section aria-labelledby="inspector-trace-heading">
              <h2 id="inspector-trace-heading">运行详情</h2>
              {bundle?.trace.map((step, index) => (
                <TraceItem step={step} key={`${step.step_id}:${index}`} />
              ))}
              {!bundle?.trace.length && <div className="inspector-empty">未选择研究运行。</div>}
            </section>
          )}

          {tab === "memory" && (
            <section aria-labelledby="inspector-memory-heading">
              <h2 id="inspector-memory-heading">本次命中的记忆</h2>
              {context?.memory.map((item) => (
                <div className="inspector-item" key={`${item.label}:${item.detail}`}>
                  <BrainCircuit aria-hidden="true" size={16} />
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.detail}</p>
                    <small>{item.source}</small>
                  </div>
                </div>
              ))}
              {!context?.memory.length && (
                <div className="inspector-empty">
                  当前 Run 未记录记忆命中。不会把用户全部记忆误标为“本次已使用”。
                </div>
              )}
            </section>
          )}

          {tab === "review" && (
            <section aria-labelledby="inspector-review-heading">
              <h2 id="inspector-review-heading">关联回检</h2>
              {context?.review.map((item) => (
                <div className="inspector-item" key={`${item.label}:${item.detail}`}>
                  <History aria-hidden="true" size={16} />
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.detail}</p>
                    <small>{item.source}</small>
                  </div>
                </div>
              ))}
              {!context?.review.length && (
                <div className="inspector-empty">当前 Run 没有关联 checkpoint 或历史 verdict。</div>
              )}
            </section>
          )}
        </div>
      </aside>
    </>
  );
}
