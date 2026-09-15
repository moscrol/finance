import {
  BarChart3,
  Radar,
  SearchCheck,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef } from "react";
import type {
  ChatMessage,
  FollowupContinuation,
  LiveMessageState,
  ProductSkillDescription,
  RunBundle,
} from "../types";
import { MessageBubble } from "./MessageBubble";

interface MessageThreadProps {
  messages: ChatMessage[];
  skills: ProductSkillDescription[];
  liveMessages: Record<string, LiveMessageState>;
  runBundles: Record<string, RunBundle>;
  onRegenerate: (message: ChatMessage) => void;
  onOpenArtifact: (artifactId: string) => void;
  onFollowup: (question: string, continuation?: FollowupContinuation) => void;
  onStarter: (prompt: string) => void;
}

export function MessageThread({
  messages,
  skills,
  liveMessages,
  runBundles,
  onRegenerate,
  onOpenArtifact,
  onFollowup,
  onStarter,
}: MessageThreadProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, liveMessages]);

  if (messages.length === 0) {
    const starters = [
      {
        title: "今日复盘",
        description: "复盘市场结构、主线和风险",
        prompt: "请复盘最新交易日的市场结构、主线、赚钱效应和主要风险。",
        icon: BarChart3,
      },
      {
        title: "研究雷达",
        description: "发现值得继续追踪的信号",
        prompt: "请生成最新 Daily Agent 研究雷达，并列出值得继续追踪的信号。",
        icon: Radar,
      },
      {
        title: "探索机会",
        description: "从当前证据寻找研究方向",
        prompt: "请列出当前最值得深入研究的三个方向，并说明证据边界。",
        icon: SearchCheck,
      },
    ];

    return (
      <div className="chat-empty chat-onboarding">
        <div className="onboarding-mark" aria-hidden="true">
          <Sparkles size={22} />
        </div>
        <span className="onboarding-eyebrow">FORESIGHT · LOCAL RESEARCH</span>
        <h1>交给 Foresight 一项研究任务</h1>
        <p>
          描述判断、标的和时间范围。系统会重新检索本轮证据，并持续展示来源与研究进度。
          快捷入口只会填入问题，你可以补充后再发送。
        </p>
        <div className="starter-grid" aria-label="快捷研究入口">
          {starters.map((starter) => {
            const Icon = starter.icon;
            return (
              <button
                type="button"
                key={starter.title}
                onClick={() => onStarter(starter.prompt)}
              >
                <span className="starter-icon">
                  <Icon aria-hidden="true" size={17} />
                </span>
                <span>
                  <strong>{starter.title}</strong>
                  <small>{starter.description}</small>
                </span>
              </button>
            );
          })}
        </div>
        <div className="onboarding-assurance">
          <ShieldCheck aria-hidden="true" size={14} />
          每轮新检索 · 证据可追溯 · 本地私有
        </div>
      </div>
    );
  }

  const lastAssistantId = [...messages]
    .reverse()
    .find((message) => message.role === "assistant")?.message_id;

  return (
    <section className="message-thread" aria-label="消息记录">
      {messages.map((message) => (
        <MessageBubble
          message={message}
          skills={skills}
          live={liveMessages[message.message_id] ?? null}
          bundle={
            message.run_id ? (runBundles[message.run_id] ?? null) : null
          }
          canRegenerate={message.message_id === lastAssistantId}
          onRegenerate={onRegenerate}
          onOpenArtifact={onOpenArtifact}
          onFollowup={onFollowup}
          key={message.message_id}
        />
      ))}
      <div ref={endRef} />
    </section>
  );
}
