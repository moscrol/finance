import {
  Archive,
  BadgeCheck,
  Boxes,
  CalendarDays,
  ChevronRight,
  FolderArchive,
  Layers3,
  MessageCircle,
  MessageSquarePlus,
  PanelLeftClose,
  RadioTower,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { Conversation, CreditsSummary, WorkbenchSection } from "../types";

const outputNavigation = [
  { section: "today", label: "今日", Icon: CalendarDays },
  { section: "themes", label: "主题", Icon: Layers3 },
  { section: "signals", label: "信号", Icon: RadioTower },
  { section: "validation", label: "验证", Icon: BadgeCheck },
  { section: "ask", label: "问答", Icon: MessageCircle },
] satisfies Array<{
  section: WorkbenchSection;
  label: string;
  Icon: typeof CalendarDays;
}>;

interface ConversationListProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  mobileOpen: boolean;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
  onArchive: (conversationId: string) => void;
  onClose: () => void;
  onLibrary: () => void;
  activeSection: WorkbenchSection;
  onSection: (section: WorkbenchSection) => void;
  credits?: CreditsSummary | null;
}

function displayConversationTitle(title: string): string {
  return title === "新对话" ? "未命名研究" : title;
}

function expiryLabel(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}

/** 钱包关着或 owner 豁免时不占位；额度为 0 用警示色，用户不用等到 429 才知道。 */
function CreditsLine({ credits }: { credits: CreditsSummary | null | undefined }) {
  if (!credits || !credits.enabled || credits.exempt || credits.remaining === null) {
    return null;
  }
  const empty = credits.remaining <= 0;
  const expiry = credits.next_expiry ? expiryLabel(credits.next_expiry) : "";
  return (
    <div
      className={empty ? "credits-line empty" : "credits-line"}
      role="status"
      aria-label={empty ? "研究额度已用完" : `剩余研究额度 ${credits.remaining} 次`}
    >
      <span className="credits-dot" aria-hidden="true" />
      <span>
        {empty ? "额度已用完，请联系管理员充值" : `剩余额度 ${credits.remaining} 次`}
        {!empty && expiry ? ` · ${expiry} 到期` : ""}
      </span>
    </div>
  );
}

export function ConversationList({
  conversations,
  activeConversationId,
  mobileOpen,
  onSelect,
  onNew,
  onArchive,
  onClose,
  onLibrary,
  activeSection,
  onSection,
  credits,
}: ConversationListProps) {
  const [query, setQuery] = useState("");
  const filteredConversations = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return conversations;
    return conversations.filter((conversation) =>
      `${conversation.title} ${conversation.summary}`
        .toLocaleLowerCase()
        .includes(normalizedQuery),
    );
  }, [conversations, query]);

  return (
    <>
      {mobileOpen && (
        <button
          className="conversation-backdrop"
          type="button"
          aria-label="关闭会话列表遮罩"
          onClick={onClose}
        />
      )}
      <aside
        className={`conversation-list ${mobileOpen ? "open" : ""}`}
        aria-label="会话列表"
      >
        <header className="conversation-list-header">
          <div className="brand">
            <span className="brand-mark">F</span>
            <span className="brand-copy">
              <strong>Foresight</strong>
              <span>Research Agent</span>
            </span>
          </div>
          <button
            className="icon-button conversation-close"
            type="button"
            aria-label="关闭会话列表"
            title="关闭会话列表"
            onClick={onClose}
          >
            <PanelLeftClose aria-hidden="true" size={18} />
          </button>
        </header>

        <div className="workspace-module" aria-label="当前研究工作区">
          <span className="workspace-module-icon" aria-hidden="true">
            <Boxes size={16} />
          </span>
          <span className="workspace-module-copy">
            <small>工作区</small>
            <strong>市场研究</strong>
          </span>
          <ChevronRight aria-hidden="true" size={14} />
        </div>

        <nav className="output-navigation" aria-label="工作台一级导航">
          {outputNavigation.map(({ section, label, Icon }) => (
            <button
              className={activeSection === section ? "active" : ""}
              type="button"
              aria-current={activeSection === section ? "page" : undefined}
              key={section}
              onClick={() => onSection(section)}
            >
              <Icon aria-hidden="true" size={16} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <button
          className="new-conversation-button"
          type="button"
          onClick={onNew}
        >
          <MessageSquarePlus aria-hidden="true" size={17} />
          新对话
        </button>

        <label className="conversation-search">
          <Search aria-hidden="true" size={15} />
          <span className="sr-only">搜索会话</span>
          <input
            type="search"
            value={query}
            placeholder="搜索会话"
            aria-label="搜索会话"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>

        <div className="conversation-scroll">
          <div className="conversation-section-heading">
            <h2>研究线程</h2>
            <span>{conversations.length}</span>
          </div>
          {filteredConversations.map((conversation) => (
            <div
              className={`conversation-row ${
                activeConversationId === conversation.conversation_id
                  ? "active"
                  : ""
              }`}
              key={conversation.conversation_id}
            >
              <button
                className="conversation-select"
                type="button"
                aria-current={
                  activeConversationId === conversation.conversation_id
                    ? "page"
                    : undefined
                }
                onClick={() => onSelect(conversation.conversation_id)}
              >
                <strong>{displayConversationTitle(conversation.title)}</strong>
                <small>
                  {new Date(conversation.updated_at).toLocaleDateString("zh-CN")}
                </small>
              </button>
              <button
                className="conversation-archive"
                type="button"
                aria-label={`归档${displayConversationTitle(conversation.title)}`}
                title={`归档${displayConversationTitle(conversation.title)}`}
                onClick={() => onArchive(conversation.conversation_id)}
              >
                <Archive aria-hidden="true" size={15} />
              </button>
            </div>
          ))}
          {conversations.length === 0 && (
            <p className="conversation-empty">
              还没有对话。发送第一条消息即可开始。
            </p>
          )}
          {conversations.length > 0 && filteredConversations.length === 0 && (
            <p className="conversation-empty">没有匹配的会话。</p>
          )}
        </div>

        <button
          className="conversation-library-link"
          type="button"
          aria-label="产物库"
          onClick={onLibrary}
        >
          <FolderArchive aria-hidden="true" size={17} />
          研究产物
        </button>
        <CreditsLine credits={credits} />
        <div className="private-workspace-status">
          <span className="data-dot" aria-hidden="true" />
          本地执行 · 私有数据
        </div>
      </aside>
    </>
  );
}
