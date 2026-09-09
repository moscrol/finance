import { RefreshCw, Sparkles } from "lucide-react";
import { continuationFor } from "../followups";
import type {
  ChatMessage,
  FollowupContinuation,
  LiveMessageState,
  ProductSkillDescription,
  RunBundle,
  SkillInvocationStatus,
} from "../types";
import { DigestSnapshotView } from "./DigestSnapshotView";
import { MarkdownView } from "./MarkdownView";
import { ProgressTimeline } from "./ProgressTimeline";
import { RunView } from "./RunView";
import { SkillInvocation } from "./SkillInvocation";

interface MessageBubbleProps {
  message: ChatMessage;
  skills: ProductSkillDescription[];
  live: LiveMessageState | null;
  bundle: RunBundle | null;
  canRegenerate: boolean;
  onRegenerate: (message: ChatMessage) => void;
  onOpenArtifact: (artifactId: string) => void;
  onFollowup: (question: string, continuation?: FollowupContinuation) => void;
}

export function MessageBubble({
  message,
  skills,
  live,
  bundle,
  canRegenerate,
  onRegenerate,
  onOpenArtifact,
  onFollowup,
}: MessageBubbleProps) {
  const content = live?.narrative || message.content;
  // 收尾后 live 只在 answerPhase 为 null 时被 App.finalizeRun 删掉，所以带
  // answer.snapshot 的 research/workflow 轮次（本页大多数）过程条会留着；
  // 其余轮次退回 RunView 里的「运行轨迹」，与改动前一致。
  const progressSteps = live?.progress ?? [];
  const invokedSkillIds = [
    ...new Set([
      ...message.invoked_skill_ids,
      ...Object.keys(live?.skillInvocations ?? {}),
    ]),
  ];
  const statuses = Object.fromEntries(
    Object.entries(live?.skillInvocations ?? {}).map(([skillId, invocation]) => [
      skillId,
      invocation.status,
    ]),
  ) as Record<string, SkillInvocationStatus>;
  const terminalStatus = live?.status ?? message.status;
  const runInFlight =
    terminalStatus === "pending" || terminalStatus === "streaming";
  const terminalNotice =
    terminalStatus === "cancelled"
      ? "已停止生成，已保留已生成内容。"
      : terminalStatus === "failed"
        ? "本轮生成失败，请重试。"
        : null;
  const answerStatus =
    live?.answerPhase === "verified_draft"
      ? "可核验草稿 · 模型精修中"
      : live?.answerPhase === "validated_synthesis"
        ? "自然语言精修完成"
        : live?.answerPhase === "verified_fallback"
          ? "已保留可核验版本"
          : live?.answerPhase === "decision_brief_fallback"
            ? "已保留决策摘要"
            : live?.answerPhase === "evidence_gap_fallback"
              ? "证据不足，已如实说明"
          : null;
  const assistantStatus =
    answerStatus ??
    (terminalStatus === "pending" || terminalStatus === "streaming"
      ? "研究中"
      : terminalStatus === "cancelled"
        ? "已停止"
        : terminalStatus === "failed"
          ? "失败"
          : "已完成");
  const hasBoundEvidence =
    bundle?.context.evidence.some(
      (item) => item.classification === "bound_evidence",
    ) ?? true;
  const report = live?.report ?? bundle?.structuredReport;
  // P1b 证据页只认 payload 键，且形状必须是带 bags 数组的对象——
  // 旧键 watchlist_digest_snapshot 是脱敏路径字符串，认不出来就不渲染（fail closed）。
  const rawDigestSnapshot = report?.watchlist_digest_snapshot_payload;
  const digestSnapshot =
    rawDigestSnapshot &&
    typeof rawDigestSnapshot === "object" &&
    Array.isArray(rawDigestSnapshot.bags) &&
    Array.isArray(rawDigestSnapshot.rows)
      ? rawDigestSnapshot
      : null;
  const taskType = report?.task_type;
  const taskFrame = report?.task_frame;
  const requiresCompanyEvidence = taskFrame
    ? taskFrame.subject_kind === "company" ||
      taskFrame.evidence_policy.startsWith("company_")
    : taskType === "ask" ||
      taskType === "research" ||
      taskType === "workflow";
  const noEvidenceNotice =
    "本轮未形成可验证的公司级来源；公司判断均按待验证展示。";

  if (message.role === "user") {
    return (
      <article className="message-row message-user" aria-label="你的消息">
        <div className="message-bubble">
          <p>{message.content}</p>
        </div>
      </article>
    );
  }

  return (
    <article className="message-row message-assistant" aria-label="研究助手消息">
      <div className="assistant-mark" aria-hidden="true">
        <Sparkles size={16} />
      </div>
      <div className="assistant-message-content">
        <div className="assistant-message-header">
          <strong>Foresight</strong>
          <span>{assistantStatus}</span>
        </div>
        <SkillInvocation
          skills={skills}
          selectedSkillIds={message.selected_skill_ids}
          invokedSkillIds={invokedSkillIds}
          statuses={statuses}
        />
        {live?.workflow && (
          <div className="workflow-loaded-status" role="status">
            工作流已加载 · {live.workflow.label} ·{" "}
            {live.workflow.retrievalStages.length} 个阶段
          </div>
        )}
        {(live?.answerPhase ?? null) === null &&
          message.degrades.includes("llm_unavailable_template_answer") && (
          <span className="template-answer-label">
            自然语言综合暂时不可用
          </span>
        )}
        {requiresCompanyEvidence &&
          !hasBoundEvidence &&
          !content.includes(noEvidenceNotice) && (
          <div className="message-evidence-warning" role="status">
            {noEvidenceNotice}
          </div>
        )}
        {progressSteps.length > 0 || runInFlight ? (
          <ProgressTimeline steps={progressSteps} active={runInFlight} />
        ) : null}
        {content ? <MarkdownView source={content} /> : null}
        {terminalNotice && (
          <div className="message-terminal-notice" role="status">
            {terminalNotice}
          </div>
        )}
        {digestSnapshot && (
          <DigestSnapshotView snapshot={digestSnapshot} />
        )}
        {bundle && (
          <RunView
            bundle={bundle}
            connection={live?.connection ?? "connected"}
            onOpenArtifact={onOpenArtifact}
            onFollowup={onFollowup}
          />
        )}
        {!bundle && (message.followups?.length ?? 0) > 0 && (
          <section aria-label="继续研究">
            <h3>继续研究</h3>
            <div className="message-followups">
              {message.followups?.map((followup) => (
                <button
                  key={`${followup.type}:${followup.full_prompt || followup.question}`}
                  type="button"
                  data-kind={followup.kind}
                  title={followup.kind_label}
                  onClick={() =>
                    onFollowup(
                      followup.full_prompt || followup.question,
                      continuationFor(followup, message.run_id),
                    )
                  }
                >
                  {followup.kind_label && (
                    <span aria-hidden="true" className="followup-kind">
                      {followup.kind_label}
                    </span>
                  )}
                  {followup.label || followup.question}
                </button>
              ))}
            </div>
          </section>
        )}
        {canRegenerate && message.status !== "pending" && (
          <button
            className="message-action"
            type="button"
            aria-label="重新生成回答"
            title="重新生成回答"
            onClick={() => onRegenerate(message)}
          >
            <RefreshCw aria-hidden="true" size={14} />
            重新生成
          </button>
        )}
      </div>
    </article>
  );
}
