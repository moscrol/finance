import { continuationFor, triggerStatusLabel } from "../followups";
import type { FollowupContinuation, ResearchProject } from "../types";
import "./researchProject.css";

interface ResearchProjectPanelProps {
  project: ResearchProject | null;
  onFollowup?: (question: string, continuation?: FollowupContinuation) => void;
}

const ROUND_STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  running: "进行中",
  queued: "排队中",
  failed: "失败",
  cancelled: "已停止",
  pending: "进行中",
};

/**
 * 研究项目状态：`GET /api/conversations/{id}/research-project` 的只读展示。
 * 全部字段来自 run / 消息 / 判断轨的投影，这里不解析正文、不猜结论。
 */
export function ResearchProjectPanel({ project, onFollowup }: ResearchProjectPanelProps) {
  if (!project) {
    return <div className="inspector-empty">选择一个会话后显示研究项目状态。</div>;
  }
  const done = project.rounds.filter((round) => round.status === "completed");
  if (done.length === 0) {
    return (
      <div className="inspector-empty">
        本会话还没有完成的研究轮次；第一轮完成后这里会出现已解决什么、还缺什么。
      </div>
    );
  }
  const last = done[done.length - 1];

  return (
    <section className="research-project" aria-label="研究项目状态">
      <header className="research-project-header">
        <span className="eyebrow">研究项目</span>
        <strong>{project.subject || project.title}</strong>
        <small>
          已研究 {done.length} 轮 · 上轮数据截止 {project.as_of ?? "未记录"}
          {project.origin_conversation_id ? " · 接续早先会话" : ""}
        </small>
      </header>

      <dl className="research-project-facts">
        <div>
          <dt>当前判断</dt>
          <dd>{project.current_judgment || "上轮没有可提取的结论标题"}</dd>
        </div>
        <div>
          <dt>已读资料</dt>
          <dd>{project.materials_read} 条引用</dd>
        </div>
        <div>
          <dt>计算产物</dt>
          <dd>{project.artifacts.length > 0 ? project.artifacts.join("、") : "—"}</dd>
        </div>
      </dl>

      <h3>未解问题</h3>
      {project.open_questions.length > 0 ? (
        <ul className="research-project-list" aria-label="未解问题">
          {project.open_questions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="research-project-muted">上轮没有留下未完成核验的缺口。</p>
      )}

      <h3>后续触发点</h3>
      {project.triggers.length > 0 ? (
        <ul className="research-project-list" aria-label="后续触发点">
          {project.triggers.map((trigger) => (
            <li key={trigger.id}>
              <span className={`research-project-status status-${trigger.status}`}>
                {triggerStatusLabel(trigger.status)}
              </span>
              <span>{trigger.claim}</span>
              <small>到期 {trigger.due || "—"}</small>
            </li>
          ))}
        </ul>
      ) : (
        <p className="research-project-muted">没有登记到本会话或本对象的可证伪点。</p>
      )}
      {project.prior_note && (
        <p className="research-project-prior" data-prior-status={project.prior_status ?? ""}>
          {project.prior_note}
        </p>
      )}

      {project.next_questions.length > 0 && (
        <>
          <h3>下一问</h3>
          <div className="message-followups research-project-next" aria-label="下一问">
            {project.next_questions.map((card) => (
              <button
                type="button"
                key={`${card.type}:${card.full_prompt || card.question}`}
                data-kind={card.kind}
                title={card.kind_label}
                onClick={() =>
                  onFollowup?.(
                    card.full_prompt || card.question,
                    continuationFor(card, last.run_id),
                  )
                }
              >
                {card.kind_label && (
                  <span aria-hidden="true" className="followup-kind">
                    {card.kind_label}
                  </span>
                )}
                {card.label || card.question}
              </button>
            ))}
          </div>
        </>
      )}

      <h3>轮次</h3>
      <ol className="research-project-rounds" aria-label="研究轮次">
        {project.rounds.map((round) => (
          <li key={round.run_id}>
            <strong>#{round.index}</strong>
            <span>{round.question}</span>
            <small>
              {ROUND_STATUS_LABEL[round.status] ?? round.status} · 数据截止{" "}
              {round.as_of ?? "—"} · 引用 {round.citations}
              {round.continuation
                ? ` · 延续自「${round.continuation.label ?? round.continuation.kind ?? "上一轮"}」`
                : ""}
            </small>
          </li>
        ))}
      </ol>
    </section>
  );
}
