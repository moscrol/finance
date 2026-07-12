import {
  BrainCircuit,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  PanelLeftOpen,
  PanelRightOpen,
  RefreshCw,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  archiveConversation,
  artifactContentUrl,
  cancelRun,
  configureLLM,
  createConversation,
  createConversationMessage,
  getArtifact,
  getArtifactProjection,
  getArtifactText,
  getBootstrap,
  getConversationMessages,
  getFollowups,
  getLLMConfig,
  getRun,
  getRunArtifactText,
  getRunContext,
  getRunReport,
  getSkills,
  getTrace,
  listArtifacts,
  listConversations,
  renameConversation,
  runEventsUrl,
  selectBuiltInLLM,
} from "./api";
import { ArtifactLibrary } from "./components/ArtifactLibrary";
import { ArtifactViewer } from "./components/ArtifactViewer";
import { Composer } from "./components/Composer";
import { ConversationList } from "./components/ConversationList";
import { MessageThread } from "./components/MessageThread";
import { ModelSettings } from "./components/ModelSettings";
import { ResearchInspector } from "./components/ResearchInspector";
import { supportsDailyProjection } from "./dailyReports";
import { userFacingIssue } from "./displayText";
import {
  applyChatStreamEvent,
  createLiveMessageState,
  parseStreamEnvelopeJson,
  StreamEventDeduper,
} from "./streamEvents";
import { deduplicateTrace } from "./trace";
import type {
  ArtifactDescriptor,
  Bootstrap,
  ChatMessage,
  Conversation,
  DailyReportProjection,
  LiveMessageState,
  LLMConfig,
  LLMProviderId,
  ProductSkillDescription,
  Run,
  RunBundle,
  SkillMode,
  Surface,
} from "./types";

const chatEventTypes = [
  "message.start",
  "trace.step",
  "skill.start",
  "skill.result",
  "report.start",
  "report.module",
  "citation.ready",
  "text.delta",
  "report.complete",
  "report.error",
  "message.complete",
  "message.error",
];

interface StreamIdentity {
  conversationId: string;
  messageId: string;
  runId: string;
}

export default function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [surface, setSurface] = useState<Surface>({ kind: "home" });
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [skills, setSkills] = useState<ProductSkillDescription[]>([]);
  const [runBundles, setRunBundles] = useState<Record<string, RunBundle>>({});
  const [liveMessages, setLiveMessages] = useState<
    Record<string, LiveMessageState>
  >({});
  const [draft, setDraft] = useState("");
  const [skillMode, setSkillMode] = useState<SkillMode>("hybrid");
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
  const [llmConfig, setLLMConfig] = useState<LLMConfig | null>(null);
  const [modelSettingsOpen, setModelSettingsOpen] = useState(false);
  const [modelSettingsSaving, setModelSettingsSaving] = useState(false);
  const [modelSettingsError, setModelSettingsError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [conversationDrawerOpen, setConversationDrawerOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [artifacts, setArtifacts] = useState<ArtifactDescriptor[]>([]);
  const [artifact, setArtifact] = useState<ArtifactDescriptor | null>(null);
  const [artifactContent, setArtifactContent] = useState<string | null>(null);
  const [artifactProjection, setArtifactProjection] =
    useState<DailyReportProjection | null>(null);
  const [artifactProjectionError, setArtifactProjectionError] =
    useState<string | null>(null);
  const [originalReportArtifactId, setOriginalReportArtifactId] =
    useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeConversationRef = useRef<string | null>(null);
  const conversationGeneration = useRef(0);
  const artifactGeneration = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const runPollTimerRef = useRef<number | null>(null);
  const runPollInFlightRef = useRef(false);
  const finalizingRunRef = useRef<string | null>(null);

  const user = bootstrap?.user ?? "default";

  const fetchRunBundle = useCallback(
    async (runId: string): Promise<RunBundle> => {
      const run = await getRun(runId, user);
      const answerArtifact = run.artifacts.find(
        (item) => item.path === "answer.md",
      );
      const [
        trace,
        followups,
        context,
        registeredArtifacts,
        answer,
        structuredReport,
      ] = await Promise.all([
        getTrace(runId, user),
        getFollowups(runId, user),
        getRunContext(runId, user),
        listArtifacts({ category: "run" }, user),
        answerArtifact
          ? getRunArtifactText(runId, answerArtifact.path, user).catch(
              () => null,
            )
          : Promise.resolve(null),
        getRunReport(runId, user).catch(() => null),
      ]);
      return {
        run,
        trace: deduplicateTrace(trace),
        followups,
        context,
        answer,
        structuredReport,
        registeredArtifacts: registeredArtifacts.filter(
          (item) => item.related_run_id === runId,
        ),
      };
    },
    [user],
  );

  const loadConversationData = useCallback(
    async (conversationId: string): Promise<ChatMessage[]> => {
      const generation = ++conversationGeneration.current;
      const nextMessages = await getConversationMessages(conversationId, user);
      const runIds = [
        ...new Set(
          nextMessages
            .map((message) => message.run_id)
            .filter((runId): runId is string => Boolean(runId)),
        ),
      ];
      const bundles = await Promise.all(
        runIds.map((runId) =>
          fetchRunBundle(runId)
            .then((bundle) => [runId, bundle] as const)
            .catch(() => null),
        ),
      );
      if (
        activeConversationRef.current === conversationId &&
        conversationGeneration.current === generation
      ) {
        setMessages(nextMessages);
        setRunBundles(
          Object.fromEntries(
            bundles.filter(
              (item): item is readonly [string, RunBundle] => item !== null,
            ),
          ),
        );
      }
      return nextMessages;
    },
    [fetchRunBundle, user],
  );

  const clearRunPolling = useCallback(() => {
    if (runPollTimerRef.current !== null) {
      window.clearInterval(runPollTimerRef.current);
      runPollTimerRef.current = null;
    }
    runPollInFlightRef.current = false;
  }, []);

  const finalizeRun = useCallback(
    async (
      identity: StreamIdentity,
      status: "completed" | "failed" | "cancelled",
      events: EventSource,
    ) => {
      if (eventSourceRef.current !== events) return;
      if (finalizingRunRef.current === identity.runId) return;
      finalizingRunRef.current = identity.runId;
      setLiveMessages((current) => {
        const state = current[identity.messageId];
        return state?.runId === identity.runId
          ? {
              ...current,
              [identity.messageId]: {
                ...state,
                status,
                connection: "connected",
              },
            }
          : current;
      });
      clearRunPolling();
      events.close();
      eventSourceRef.current = null;
      try {
        await Promise.all([
          loadConversationData(identity.conversationId),
          listConversations(user).then(setConversations),
        ]);
        setLiveMessages((current) => {
          const state = current[identity.messageId];
          if (!state || state.runId !== identity.runId) return current;
          const next = { ...current };
          delete next[identity.messageId];
          return next;
        });
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : "运行已结束，但最新结果暂时无法加载",
        );
      } finally {
        if (finalizingRunRef.current === identity.runId) {
          finalizingRunRef.current = null;
        }
      }
    },
    [clearRunPolling, loadConversationData, user],
  );

  const connectStream = useCallback(
    (identity: StreamIdentity) => {
      eventSourceRef.current?.close();
      clearRunPolling();
      const deduper = new StreamEventDeduper();
      const events = new EventSource(runEventsUrl(identity.runId, user));
      eventSourceRef.current = events;

      setLiveMessages((current) => ({
        ...current,
        [identity.messageId]:
          current[identity.messageId] ??
          createLiveMessageState(identity),
      }));

      const applyEvent = (rawEvent: Event) => {
        if (eventSourceRef.current !== events) return;
        const envelope = parseStreamEnvelopeJson(
          (rawEvent as MessageEvent<string>).data,
        );
        if (!envelope) return;
        setLiveMessages((current) => {
          const state = current[identity.messageId];
          if (!state) return current;
          const next = applyChatStreamEvent(state, envelope, deduper);
          return next === state
            ? current
            : { ...current, [identity.messageId]: next };
        });
      };
      chatEventTypes.forEach((eventType) =>
        events.addEventListener(eventType, applyEvent),
      );
      events.onopen = () => {
        if (eventSourceRef.current !== events) return;
        setLiveMessages((current) => {
          const state = current[identity.messageId];
          return state
            ? {
                ...current,
                [identity.messageId]: {
                  ...state,
                  connection: "connected",
                },
              }
            : current;
        });
      };
      const reconcileStatus = async () => {
        if (eventSourceRef.current !== events) return;
        if (runPollInFlightRef.current) return;
        runPollInFlightRef.current = true;
        try {
          const run = await getRun(identity.runId, user);
          if (eventSourceRef.current !== events) return;
          if (["completed", "failed", "cancelled"].includes(run.status)) {
            await finalizeRun(
              identity,
              run.status as "completed" | "failed" | "cancelled",
              events,
            );
          }
        } catch {
          if (eventSourceRef.current !== events) return;
          setLiveMessages((current) => {
            const state = current[identity.messageId];
            return state
              ? {
                  ...current,
                  [identity.messageId]: {
                    ...state,
                    connection: "reconnecting",
                  },
                }
              : current;
          });
        } finally {
          runPollInFlightRef.current = false;
        }
      };
      events.onerror = () => {
        if (eventSourceRef.current !== events) return;
        setLiveMessages((current) => {
          const state = current[identity.messageId];
          return state
            ? {
                ...current,
                [identity.messageId]: {
                  ...state,
                  connection: "reconnecting",
                },
              }
            : current;
        });
        void reconcileStatus();
      };
      void reconcileStatus();
      runPollTimerRef.current = window.setInterval(() => {
        void reconcileStatus();
      }, 2000);
      events.addEventListener("run", (rawEvent) => {
        try {
          const nextRun = JSON.parse(
            (rawEvent as MessageEvent<string>).data,
          ) as Run;
          if (nextRun.run_id !== identity.runId) return;
          if (["completed", "failed", "cancelled"].includes(nextRun.status)) {
            void finalizeRun(
              identity,
              nextRun.status as "completed" | "failed" | "cancelled",
              events,
            );
          }
        } catch {
          setError("运行结束事件格式无效");
        }
      });
    },
    [clearRunPolling, finalizeRun, user],
  );

  const selectConversation = useCallback(
    async (conversationId: string) => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      clearRunPolling();
      activeConversationRef.current = conversationId;
      setActiveConversationId(conversationId);
      setSurface({ kind: "home" });
      setMessages([]);
      setRunBundles({});
      setLiveMessages({});
      setConversationDrawerOpen(false);
      setLoading(true);
      try {
        const nextMessages = await loadConversationData(conversationId);
        const pending = [...nextMessages]
          .reverse()
          .find(
            (message) =>
              message.role === "assistant" &&
              message.status === "pending" &&
              message.run_id,
          );
        if (
          pending?.run_id &&
          activeConversationRef.current === conversationId
        ) {
          connectStream({
            conversationId,
            messageId: pending.message_id,
            runId: pending.run_id,
          });
        }
        setError(null);
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "无法恢复会话",
        );
      } finally {
        if (activeConversationRef.current === conversationId) {
          setLoading(false);
        }
      }
    },
    [clearRunPolling, connectStream, loadConversationData],
  );

  useEffect(() => {
    let disposed = false;
    void getBootstrap()
      .then(async (nextBootstrap) => {
        if (disposed) return;
        setBootstrap(nextBootstrap);
        const [nextConversations, nextSkills, nextLLMConfig] = await Promise.all([
          listConversations(nextBootstrap.user),
          getSkills(nextBootstrap.user),
          getLLMConfig(nextBootstrap.user).catch(() => null),
        ]);
        if (disposed) return;
        setConversations(nextConversations);
        setSkills(nextSkills);
        setLLMConfig(nextLLMConfig);
        if (nextConversations[0]) {
          await selectConversation(nextConversations[0].conversation_id);
        } else {
          setLoading(false);
        }
      })
      .catch((caught) => {
        if (!disposed) {
          setError(
            caught instanceof Error ? caught.message : "Workbench 初始化失败",
          );
          setLoading(false);
        }
      });
    return () => {
      disposed = true;
      eventSourceRef.current?.close();
      clearRunPolling();
    };
  }, [clearRunPolling, selectConversation]);

  const saveBYOK = useCallback(
    async (provider: LLMProviderId, apiKey: string, model: string) => {
      setModelSettingsSaving(true);
      setModelSettingsError(null);
      try {
        const configured = await configureLLM({
          provider,
          api_key: apiKey,
          model,
          user,
        });
        setLLMConfig(configured);
      } catch (caught) {
        setModelSettingsError(
          caught instanceof Error ? caught.message : "模型连接失败",
        );
      } finally {
        setModelSettingsSaving(false);
      }
    },
    [user],
  );

  const restoreBuiltInLLM = useCallback(async () => {
    setModelSettingsSaving(true);
    setModelSettingsError(null);
    try {
      setLLMConfig(await selectBuiltInLLM(user));
    } catch (caught) {
      setModelSettingsError(
        caught instanceof Error ? caught.message : "无法切换默认模型",
      );
    } finally {
      setModelSettingsSaving(false);
    }
  }, [user]);

  const newConversation = useCallback(async (): Promise<Conversation> => {
    const created = await createConversation("新对话", user);
    setConversations((current) => [created, ...current]);
    await selectConversation(created.conversation_id);
    return created;
  }, [selectConversation, user]);

  const submitResearch = useCallback(
    async (question: string) => {
      if (submitting) return;
      setSubmitting(true);
      try {
        let conversationId = activeConversationRef.current;
        let conversation = conversations.find(
          (item) => item.conversation_id === conversationId,
        );
        if (!conversationId) {
          conversation = await newConversation();
          conversationId = conversation.conversation_id;
        }
        const created = await createConversationMessage(conversationId, {
          content: question,
          skill_mode: skillMode,
          selected_skill_ids: selectedSkillIds,
          user,
        });
        const now = new Date().toISOString();
        const userMessage: ChatMessage = {
          message_id: created.user_message_id,
          conversation_id: conversationId,
          role: "user",
          content: question,
          created_at: now,
          status: "completed",
          run_id: created.run_id,
          selected_skill_ids: selectedSkillIds,
          invoked_skill_ids: [],
          citations: [],
          degrades: [],
        };
        const assistantMessage: ChatMessage = {
          message_id: created.assistant_message_id,
          conversation_id: conversationId,
          role: "assistant",
          content: "",
          created_at: now,
          status: "pending",
          run_id: created.run_id,
          selected_skill_ids: selectedSkillIds,
          invoked_skill_ids: [],
          citations: [],
          degrades: [],
        };
        setMessages((current) => [
          ...current,
          userMessage,
          assistantMessage,
        ]);
        setLiveMessages((current) => ({
          ...current,
          [created.assistant_message_id]: createLiveMessageState({
            conversationId,
            messageId: created.assistant_message_id,
            runId: created.run_id,
          }),
        }));
        setDraft("");
        setSelectedSkillIds([]);
        connectStream({
          conversationId,
          messageId: created.assistant_message_id,
          runId: created.run_id,
        });
        if (conversation?.title === "新对话") {
          const renamed = await renameConversation(
            conversationId,
            question.slice(0, 28),
            user,
          );
          setConversations((current) =>
            current.map((item) =>
              item.conversation_id === conversationId ? renamed : item,
            ),
          );
        }
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "发送消息失败",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [
      connectStream,
      conversations,
      newConversation,
      selectedSkillIds,
      skillMode,
      submitting,
      user,
    ],
  );

  const regenerate = (assistant: ChatMessage) => {
    const assistantIndex = messages.findIndex(
      (message) => message.message_id === assistant.message_id,
    );
    const originalQuestion = messages
      .slice(0, assistantIndex)
      .reverse()
      .find((message) => message.role === "user");
    if (originalQuestion) void submitResearch(originalQuestion.content);
  };

  const runningLive = Object.values(liveMessages).find(
    (message) =>
      message.conversationId === activeConversationId &&
      (message.status === "pending" || message.status === "streaming"),
  );

  const stopGeneration = () => {
    if (runningLive && !runningLive.cancelRequested) {
      void cancelRun(runningLive.runId, user)
        .then(() => {
          setLiveMessages((current) => {
            const state = current[runningLive.messageId];
            return state
              ? {
                  ...current,
                  [runningLive.messageId]: {
                    ...state,
                    cancelRequested: true,
                    connection: "reconnecting",
                  },
                }
              : current;
          });
        })
        .catch((caught) =>
          setError(
            caught instanceof Error ? caught.message : "停止请求失败",
          ),
        );
    }
  };

  const archive = async (conversationId: string) => {
    try {
      await archiveConversation(conversationId, user);
      const remaining = conversations.filter(
        (item) => item.conversation_id !== conversationId,
      );
      setConversations(remaining);
      if (activeConversationId === conversationId) {
        if (remaining[0]) {
          await selectConversation(remaining[0].conversation_id);
        } else {
          activeConversationRef.current = null;
          setActiveConversationId(null);
          setMessages([]);
          setRunBundles({});
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "归档失败");
    }
  };

  const loadLibrary = useCallback(async () => {
    setLoading(true);
    try {
      setArtifacts(await listArtifacts({}, user));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法加载产物库");
    } finally {
      setLoading(false);
    }
  }, [user]);

  const openLibrary = () => {
    setSurface({ kind: "library" });
    setConversationDrawerOpen(false);
    setArtifact(null);
    setInspectorOpen(false);
    void loadLibrary();
  };

  const openArtifact = useCallback(
    async (artifactId: string) => {
      const generation = ++artifactGeneration.current;
      setSurface({ kind: "artifact", artifactId });
      setLoading(true);
      setArtifact(null);
      setArtifactContent(null);
      setArtifactProjection(null);
      setArtifactProjectionError(null);
      setOriginalReportArtifactId(null);
      try {
        const descriptor = await getArtifact(artifactId, user);
        if (generation !== artifactGeneration.current) return;
        setArtifact(descriptor);
        if (descriptor.viewer === "legacy_html") {
          setOriginalReportArtifactId(descriptor.artifact_id);
        }
        if (
          descriptor.status !== "missing" &&
          supportsDailyProjection(descriptor)
        ) {
          try {
            setArtifactProjection(
              await getArtifactProjection(artifactId, user),
            );
          } catch (caught) {
            if (generation === artifactGeneration.current) {
              setArtifactProjectionError(
                caught instanceof Error
                  ? caught.message
                  : "无法生成原生报告",
              );
            }
          }
        } else if (
          descriptor.status !== "missing" &&
          ["native_markdown", "native_json"].includes(descriptor.viewer)
        ) {
          setArtifactContent(await getArtifactText(artifactId, user));
        }
        setError(null);
      } catch (caught) {
        if (generation === artifactGeneration.current) {
          setError(caught instanceof Error ? caught.message : "无法加载产物");
        }
      } finally {
        if (generation === artifactGeneration.current) setLoading(false);
      }
    },
    [user],
  );

  const activeConversation = conversations.find(
    (item) => item.conversation_id === activeConversationId,
  );
  const inspectorBundle = useMemo(
    () =>
      [...messages]
        .reverse()
        .map((message) =>
          message.run_id ? runBundles[message.run_id] : undefined,
        )
        .find((bundle): bundle is RunBundle => Boolean(bundle)) ?? null,
    [messages, runBundles],
  );

  return (
    <div className="app-shell chat-first-shell">
      <ConversationList
        conversations={conversations}
        activeConversationId={activeConversationId}
        mobileOpen={conversationDrawerOpen}
        onSelect={(conversationId) => void selectConversation(conversationId)}
        onNew={() => void newConversation()}
        onArchive={(conversationId) => void archive(conversationId)}
        onClose={() => setConversationDrawerOpen(false)}
        onLibrary={openLibrary}
      />

      <main className="main-surface chat-surface">
        <header className="chat-topbar">
          <button
            className="icon-button conversation-toggle"
            type="button"
            aria-label="打开会话列表"
            title="打开会话列表"
            onClick={() => setConversationDrawerOpen(true)}
          >
            <PanelLeftOpen aria-hidden="true" size={19} />
          </button>
          <div className="chat-title">
            <span className="thread-kicker">研究线程</span>
            <strong>{activeConversation?.title ?? "新对话"}</strong>
            <small>每轮重新检索当前证据</small>
          </div>
          <div className="chat-topbar-actions">
            <button
              className={`model-status-button ${
                llmConfig?.ready ? "ready" : "pending"
              }`}
              type="button"
              aria-label="配置模型"
              title="配置模型"
              onClick={() => {
                setModelSettingsError(null);
                setModelSettingsOpen(true);
              }}
            >
              {llmConfig?.mode === "byok" ? (
                <KeyRound aria-hidden="true" size={13} />
              ) : (
                <BrainCircuit aria-hidden="true" size={14} />
              )}
              {llmConfig?.mode === "byok" ? "自带密钥" : "默认模型"}
              <span aria-hidden="true" />
            </button>
            <span
              className={`agent-status ${runningLive ? "running" : ""}`}
              role="status"
            >
              {runningLive ? (
                <LoaderCircle className="spin" aria-hidden="true" size={13} />
              ) : (
                <span className="agent-status-dot" aria-hidden="true" />
              )}
              {runningLive ? "正在研究" : "空闲"}
            </span>
            <span className="private-mode-badge">
              <LockKeyhole aria-hidden="true" size={13} />
              私有
            </span>
            <span className="demo-stage-badge">
              Demo · 非计分 · Day 1 未开始
            </span>
            <button
              className="icon-button inspector-toggle"
              type="button"
              aria-label="打开研究检查器"
              title="打开研究检查器"
              onClick={() => setInspectorOpen(true)}
            >
              <PanelRightOpen aria-hidden="true" size={19} />
            </button>
          </div>
        </header>

        {error && (
          <div className="global-error" role="alert">
            <span>{userFacingIssue(error)}</span>
            <button type="button" onClick={() => window.location.reload()}>
              <RefreshCw aria-hidden="true" size={15} />
              重试
            </button>
          </div>
        )}

        {surface.kind === "home" && (
          <div className="conversation-surface">
            <MessageThread
              messages={messages}
              skills={skills}
              liveMessages={liveMessages}
              runBundles={runBundles}
              onRegenerate={regenerate}
              onOpenArtifact={(artifactId) => void openArtifact(artifactId)}
              onFollowup={(question) => void submitResearch(question)}
              onStarter={setDraft}
            />
            <div className="chat-composer-dock">
              <Composer
                value={draft}
                taskType="ask"
                disabled={submitting}
                running={Boolean(runningLive)}
                stopRequested={runningLive?.cancelRequested ?? false}
                skills={skills}
                skillMode={skillMode}
                selectedSkillIds={selectedSkillIds}
                onChange={setDraft}
                onSubmit={(question) => void submitResearch(question)}
                onStop={stopGeneration}
                onSkillModeChange={setSkillMode}
                onSkillSelectionChange={setSelectedSkillIds}
              />
            </div>
          </div>
        )}

        {surface.kind === "library" && (
          <ArtifactLibrary
            artifacts={artifacts}
            loading={loading}
            onOpen={openArtifact}
          />
        )}

        {surface.kind === "artifact" && artifact && (
          <ArtifactViewer
            artifact={artifact}
            content={artifactContent}
            loading={loading}
            contentUrl={artifactContentUrl(artifact.artifact_id, user)}
            projection={artifactProjection}
            projectionError={artifactProjectionError}
            originalReportUrl={
              (artifactProjection?.provenance.original_artifact_id ??
              originalReportArtifactId)
                ? artifactContentUrl(
                    artifactProjection?.provenance.original_artifact_id ??
                      originalReportArtifactId!,
                    user,
                  )
                : artifact.viewer === "legacy_html"
                  ? artifactContentUrl(artifact.artifact_id, user)
                  : undefined
            }
            onBack={openLibrary}
            onOpenRun={(runId) => {
              void fetchRunBundle(runId).then((bundle) => {
                setRunBundles((current) => ({
                  ...current,
                  [runId]: bundle,
                }));
                setInspectorOpen(true);
              });
            }}
          />
        )}

        {loading && surface.kind === "home" && messages.length === 0 && (
          <div className="surface-loading">正在恢复会话…</div>
        )}
      </main>

      <ResearchInspector
        bootstrap={bootstrap}
        bundle={inspectorBundle}
        artifact={artifact}
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
      />
      <ModelSettings
        open={modelSettingsOpen}
        config={llmConfig}
        saving={modelSettingsSaving}
        error={modelSettingsError}
        onClose={() => setModelSettingsOpen(false)}
        onSave={(provider, apiKey, model) => {
          void saveBYOK(provider, apiKey, model);
        }}
        onUseBuiltIn={() => {
          void restoreBuiltInLLM();
        }}
      />
    </div>
  );
}
