import {
  Archive,
  Boxes,
  ChevronRight,
  FolderArchive,
  MessageSquarePlus,
  PanelLeftClose,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { Conversation } from "../types";

interface ConversationListProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  mobileOpen: boolean;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
  onArchive: (conversationId: string) => void;
  onClose: () => void;
  onLibrary: () => void;
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
                <strong>{conversation.title}</strong>
                <small>
                  {new Date(conversation.updated_at).toLocaleDateString("zh-CN")}
                </small>
              </button>
              <button
                className="conversation-archive"
                type="button"
                aria-label={`归档${conversation.title}`}
                title={`归档${conversation.title}`}
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
        <div className="private-workspace-status">
          <span className="data-dot" aria-hidden="true" />
          本地执行 · 私有数据
        </div>
      </aside>
    </>
  );
}
