import { RefreshCw, Sparkles } from "lucide-react";
import type {
  ChatMessage,
  LiveMessageState,
  ProductSkillDescription,
  RunBundle,
  SkillInvocationStatus,
} from "../types";
import { MarkdownView } from "./MarkdownView";
import { RunView } from "./RunView";
import { SkillInvocation } from "./SkillInvocation";
import { userFacingStage } from "../displayText";

interface MessageBubbleProps {
  message: ChatMessage;
  skills: ProductSkillDescription[];
  live: LiveMessageState | null;
  bundle: RunBundle | null;
  canRegenerate: boolean;
  onRegenerate: (message: ChatMessage) => void;
  onOpenArtifact: (artifactId: string) => void;
  onFollowup: (question: string) => void;
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
  const persistedTerminalPhase =
    message.role === "assistant" &&
    message.status === "completed" &&
    message.answer_final === true &&
    typeof message.answer_revision === "number" &&
    Number.isSafeInteger(message.answer_revision) &&
    message.answer_revision > 0 &&
    (message.answer_phase === "validated_synthesis" ||
      message.answer_phase === "verified_fallback")
      ? message.answer_phase
      : null;
  const answerPhase = live ? live.answerPhase : persistedTerminalPhase;
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
  const terminalNotice =
    terminalStatus === "cancelled"
      ? "已停止生成，已保留已生成内容。"
      : terminalStatus === "failed"
        ? "本轮生成失败，请重试。"
        : null;
  const assistantStatus =
    terminalStatus === "pending" || terminalStatus === "streaming"
      ? "研究中"
      : terminalStatus === "cancelled"
        ? "已停止"
        : terminalStatus === "failed"
          ? "失败"
          : "已完成";
  const answerPhaseStatus =
    answerPhase === "verified_draft"
      ? "可核验草稿 · 模型精修中"
      : answerPhase === "validated_synthesis"
        ? "自然语言精修完成"
        : answerPhase === "verified_fallback"
          ? "已保留可核验版本"
          : null;
  const hasBoundEvidence =
    bundle?.context.evidence.some(
      (item) => item.classification === "bound_evidence",
    ) ?? true;
  const noEvidenceNotice =
    "本轮未形成可回查的硬证据；当前判断按待验证展示。";
  const targetCompanyEvidenceNotice =
    "本轮未形成可回查的目标公司级硬证据；当前公司判断按待验证展示。";
  const hasVisibleEvidenceNotice =
    content.includes(noEvidenceNotice) ||
    content.includes(targetCompanyEvidenceNotice);

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
        {answerPhaseStatus && (
          <span
            className={`answer-phase-label answer-phase-${answerPhase}`}
            role="status"
          >
            {answerPhaseStatus}
          </span>
        )}
        {message.degrades.includes("llm_unavailable_template_answer") &&
          answerPhase !== "validated_synthesis" && (
          <span className="template-answer-label">
            自然语言综合暂时不可用
          </span>
        )}
        {!hasBoundEvidence && !hasVisibleEvidenceNotice && (
          <div className="message-evidence-warning" role="status">
            {noEvidenceNotice}
          </div>
        )}
        {content ? (
          <MarkdownView source={content} />
        ) : terminalNotice ? null : (
          <div className="message-thinking" role="status">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
            {live?.currentStage
              ? userFacingStage(live.currentStage)
              : "正在检索本轮证据"}
          </div>
        )}
        {terminalNotice && (
          <div className="message-terminal-notice" role="status">
            {terminalNotice}
          </div>
        )}
        {bundle && (
          <RunView
            bundle={bundle}
            connection={live?.connection ?? "connected"}
            onOpenArtifact={onOpenArtifact}
            onFollowup={onFollowup}
          />
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
