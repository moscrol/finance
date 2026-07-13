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
  const hasBoundEvidence =
    bundle?.context.evidence.some(
      (item) => item.classification === "bound_evidence",
    ) ?? true;
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
        {message.degrades.includes("llm_unavailable_template_answer") && (
          <span className="template-answer-label">
            自然语言综合暂时不可用
          </span>
        )}
        {!hasBoundEvidence && !content.includes(noEvidenceNotice) && (
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
