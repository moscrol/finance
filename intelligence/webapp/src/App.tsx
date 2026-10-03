import {
  BrainCircuit,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  Moon,
  PanelLeftOpen,
  PanelRightOpen,
  RefreshCw,
  Sun,
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
  getCredits,
  getFollowups,
  forgetSavedLLM,
  getLLMConfig,
  getPerspectives,
  getRun,
  getRunArtifactText,
  getRunContext,
  getRunReport,
  getResearchEvolution,
  getResearchEvolutionCatalog,
  getResearchProject,
  postResearchEvolutionAction,
  postResearchEvolutionBinding,
  getSkills,
  getTrace,
  getWorkbenchOverview,
  listArtifacts,
  listConversations,
  renameConversation,
  runEventsUrl,
  selectBuiltInLLM,
} from "./api";
import { ArtifactLibrary } from "./components/ArtifactLibrary";
import { ArtifactViewer } from "./components/ArtifactViewer";
import { BoardCalendarDashboard } from "./components/BoardCalendarDashboard";
import { Composer } from "./components/Composer";
import { ConversationList } from "./components/ConversationList";
import { DecodeTitle } from "./components/DecodeTitle";
import { MessageThread } from "./components/MessageThread";
import { ModelSettings } from "./components/ModelSettings";
import { OutputWorkbench } from "./components/OutputWorkbench";
import { ResearchInspector } from "./components/ResearchInspector";
import { StaleDataBanner } from "./components/StaleDataBanner";
import { TechBackdrop } from "./components/TechBackdrop";
import { LimitUpDashboard } from "./components/river/LimitUpDashboard";
import { RiverWorkbench } from "./components/river/RiverHome";
import { applyTheme, getInitialTheme, type WorkbenchTheme } from "./theme";
import "./river.css";
import "./theme-tech.css";
import { supportsDailyProjection } from "./dailyReports";
import { userFacingIssue } from "./displayText";
import {
  applyChatStreamEvent,
  createLiveMessageState,
  parseStreamEnvelopeJson,
  StreamEventDeduper,
} from "./streamEvents";
import { chatEventTypes } from "./streamEventRegistry";
import { deduplicateTrace } from "./trace";
import type {
  ArtifactDescriptor,
  Bootstrap,
  ChatMessage,
  Conversation,
  CreditsSummary,
  DailyReportProjection,
  FollowupContinuation,
  MaintenanceLaunchRef,
  CreateMessageResponse,
  LiveMessageState,
  LLMConfig,
  LLMProviderId,
  PerspectiveDescription,
  PerspectiveMode,
  ProductSkillDescription,
  ResearchEvolutionActionResult,
  ResearchEvolutionView,
  ResearchProject,
  Run,
  RunBundle,
  SkillMode,
  Surface,
  WorkbenchOverview,
  WorkbenchSection,
} from "./types";

interface StreamIdentity {
  conversationId: string;
  messageId: string;
  runId: string;
}

function isPublishedTerminalRun(
  run: Run, identity: StreamIdentity,
): run is Run & { status: "completed" | "failed" | "cancelled" } {
  return (
    run.run_id === identity.runId &&
    run.session_id === identity.conversationId &&
    !run.delivery_pending &&
    ["completed", "failed", "cancelled"].includes(run.status) &&
    run.publication?.status === "published" &&
    run.publication.message_id === identity.messageId
  );
}

export default function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [credits, setCredits] = useState<CreditsSummary | null>(null);
  const [surface, setSurface] = useState<Surface>({ kind: "today" });
  const [marketFocusDate, setMarketFocusDate] = useState<string | null>(null);
  const [theme, setTheme] = useState<WorkbenchTheme>(getInitialTheme);
  useEffect(() => { applyTheme(theme); }, [theme]);
  const [overview, setOverview] = useState<WorkbenchOverview | null>(null);
  const [overviewRefreshing, setOverviewRefreshing] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [skills, setSkills] = useState<ProductSkillDescription[]>([]);
  const [perspectives, setPerspectives] = useState<PerspectiveDescription[]>([]);
  const [runBundles, setRunBundles] = useState<Record<string, RunBundle>>({});
  // 09 连续研究：当前会话的研究项目状态（服务端只读投影），随消息加载一并刷新。
  const [researchProject, setResearchProject] = useState<ResearchProject | null>(
    null,
  );
  // 研究进化：01/02/04 的会话级投影。与研究项目同批刷新；加载失败只让「维护」页显示空态。
  const [researchEvolution, setResearchEvolution] =
    useState<ResearchEvolutionView | null>(null);
  const [evolutionBusy, setEvolutionBusy] = useState(false);
  const [liveMessages, setLiveMessages] = useState<
    Record<string, LiveMessageState>
  >({});
  const [draft, setDraft] = useState("");
  const [skillMode, setSkillMode] = useState<SkillMode>("hybrid");
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
  const [perspectiveMode, setPerspectiveMode] =
    useState<PerspectiveMode>("neutral");
  const [selectedPerspectiveIds, setSelectedPerspectiveIds] = useState<string[]>(
    [],
  );
  const [llmConfig, setLLMConfig] = useState<LLMConfig | null>(null);
  const [modelSettingsOpen, setModelSettingsOpen] = useState(false);
  const [modelSettingsSaving, setModelSettingsSaving] = useState(false);
  const [modelSettingsError, setModelSettingsError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [conversationDrawerOpen, setConversationDrawerOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(
    () => window.innerWidth >= 1180,
  );
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

  // 余额在两个时刻变：提问被受理（预占）与 run 结束（按用量结算、释放预占）。
  // 拉不到就保留上一次的数，展示项不该把主流程带红。
  const refreshCredits = useCallback(() => {
    void getCredits(user)
      .then(setCredits)
      .catch(() => undefined);
  }, [user]);

  const fetchRunBundle = useCallback(
    async (
      runId: string,
      loadArtifacts = () => listArtifacts({ category: "run" }, user),
    ): Promise<RunBundle> => {
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
        loadArtifacts(),
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
    async (conversationId: string) => {
      const generation = ++conversationGeneration.current;
      const nextMessages = await getConversationMessages(conversationId, user);
      const runIds = [
        ...new Set(
          nextMessages
            .map((message) => message.run_id)
            .filter((runId): runId is string => Boolean(runId)),
        ),
      ];
      // Share one listing within this restore, never across users or later refreshes.
      let artifactRequest: ReturnType<typeof listArtifacts> | undefined;
      const loadArtifacts = () => {
        artifactRequest ??= listArtifacts({ category: "run" }, user);
        return artifactRequest;
      };
      const [bundles, project, evolution] = await Promise.all([
        Promise.all(
          runIds.map((runId) =>
            fetchRunBundle(runId, loadArtifacts)
              .then((bundle) => [runId, bundle] as const)
              .catch(() => null),
          ),
        ),
        // 项目视图加载失败不拖死消息加载：只在项目页显示空态。
        // 同步抛错（如接口缺失）也要落进 catch，所以先进 Promise 链再调用。
        Promise.resolve()
          .then(() => getResearchProject(conversationId, user))
          .then((value) => value ?? null)
          .catch(() => null),
        Promise.resolve()
          .then(() => getResearchEvolution(conversationId, user))
          .then((value) => value ?? null)
          .catch(() => null),
      ]);
      const nextBundles = Object.fromEntries(
        bundles.filter(
          (item): item is readonly [string, RunBundle] => item !== null,
        ),
      );
      const applied = activeConversationRef.current === conversationId &&
        conversationGeneration.current === generation;
      if (applied) {
        setMessages(nextMessages);
        setRunBundles(nextBundles);
        setResearchProject(project);
        setResearchEvolution(evolution);
      }
      return { messages: nextMessages, bundles: nextBundles, applied };
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
      events: EventSource,
    ) => {
      if (eventSourceRef.current !== events) return;
      if (finalizingRunRef.current === identity.runId) return;
      finalizingRunRef.current = identity.runId;
      try {
        const loaded = await loadConversationData(identity.conversationId);
        if (!loaded.applied || eventSourceRef.current !== events) return;
        const bundle = loaded.bundles[identity.runId];
        const message = loaded.messages.find((item) =>
          item.role === "assistant" && item.message_id === identity.messageId &&
          item.run_id === identity.runId && item.conversation_id === identity.conversationId,
        );
        if (!bundle || !isPublishedTerminalRun(bundle.run, identity) ||
            !message || message.status !== bundle.run.status) return;
        const status = bundle.run.status;
        clearRunPolling();
        events.close();
        eventSourceRef.current = null;
        setLiveMessages((current) => {
          const state = current[identity.messageId];
          return state?.runId === identity.runId
            ? { ...current, [identity.messageId]: { ...state,
                status, connection: "connected" } }
            : current;
        });
        setConversations(await listConversations(user));
        // 结算发生在 worker 返回之后、SSE 收口之后几毫秒；等两次往返回来再读余额，读到的是结算后的数。
        refreshCredits();
        setLiveMessages((current) => {
          const state = current[identity.messageId];
          if (
            !state ||
            state.runId !== identity.runId ||
            state.answerPhase !== null
          ) {
            return current;
          }
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
    [clearRunPolling, loadConversationData, refreshCredits, user],
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
          if (isPublishedTerminalRun(run, identity)) {
            await finalizeRun(identity, events);
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
          if (isPublishedTerminalRun(nextRun, identity)) {
            void finalizeRun(identity, events);
          }
        } catch {
          setError("运行结束事件格式无效");
        }
      });
    },
    [clearRunPolling, finalizeRun, user],
  );

  const selectConversation = useCallback(
    async (
      conversationId: string,
      options: { closeDrawer?: boolean; openAsk?: boolean } = {},
    ) => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      clearRunPolling();
      activeConversationRef.current = conversationId;
      setActiveConversationId(conversationId);
      if (options.openAsk !== false) {
        setSurface({ kind: "ask" });
      }
      setMessages([]);
      setRunBundles({});
      setResearchProject(null);
      setResearchEvolution(null);
      setLiveMessages({});
      if (options.closeDrawer !== false) {
        setConversationDrawerOpen(false);
      }
      setLoading(true);
      try {
        const loaded = await loadConversationData(conversationId);
        if (!loaded.applied) return;
        const nextMessages = loaded.messages;
        const lastUserMessage = [...nextMessages]
          .reverse()
          .find((message) => message.role === "user");
        setSkillMode(lastUserMessage?.skill_mode ?? "hybrid");
        setSelectedSkillIds(lastUserMessage?.selected_skill_ids ?? []);
        setPerspectiveMode(lastUserMessage?.perspective_mode ?? "neutral");
        setSelectedPerspectiveIds(
          lastUserMessage?.selected_perspective_ids ?? [],
        );
        const pending = [...nextMessages]
          .reverse()
          .find(
            (message) =>
              message.role === "assistant" &&
              message.run_id &&
              (message.status === "pending" ||
                loaded.bundles[message.run_id]?.run.delivery_pending ||
                loaded.bundles[message.run_id]?.run.publication?.status === "pending"),
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
        setCredits(nextBootstrap.credits ?? null);
        const [
          nextConversations,
          nextSkills,
          nextPerspectives,
          nextLLMConfig,
          nextOverview,
        ] = await Promise.all([
          listConversations(nextBootstrap.user),
          getSkills(nextBootstrap.user),
          getPerspectives(nextBootstrap.user),
          getLLMConfig(nextBootstrap.user).catch(() => null),
          getWorkbenchOverview().catch(() => null),
        ]);
        if (disposed) return;
        setConversations(nextConversations);
        setSkills(nextSkills);
        setPerspectives(nextPerspectives);
        setLLMConfig(nextLLMConfig);
        setOverview(nextOverview);
        if (nextConversations[0]) {
          await selectConversation(nextConversations[0].conversation_id, {
            closeDrawer: false,
            openAsk: false,
          });
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

  const refreshOverview = useCallback(async () => {
    setOverviewRefreshing(true);
    try {
      setOverview(await getWorkbenchOverview());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法刷新数据状态");
    } finally {
      setOverviewRefreshing(false);
    }
  }, []);

  const saveBYOK = useCallback(
    async (
      provider: LLMProviderId,
      apiKey: string,
      baseUrl: string,
      model: string,
      remember: boolean,
    ) => {
      setModelSettingsSaving(true);
      setModelSettingsError(null);
      try {
        const configured = await configureLLM({
          provider,
          api_key: apiKey,
          base_url: baseUrl,
          model,
          remember,
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

  const forgetSavedModel = useCallback(async () => {
    setModelSettingsSaving(true);
    setModelSettingsError(null);
    try {
      setLLMConfig(await forgetSavedLLM(user));
    } catch (caught) {
      setModelSettingsError(
        caught instanceof Error ? caught.message : "无法删除已保存的模型密钥",
      );
    } finally {
      setModelSettingsSaving(false);
    }
  }, [user]);

  const newConversation = useCallback(async (): Promise<Conversation> => {
    setLoading(true);
    setSkillMode("hybrid");
    setSelectedSkillIds([]);
    setPerspectiveMode("neutral");
    setSelectedPerspectiveIds([]);
    try {
      const created = await createConversation("新对话", user);
      setConversations((current) => [created, ...current]);
      await selectConversation(created.conversation_id);
      return created;
    } catch (caught) {
      setLoading(false);
      throw caught;
    }
  }, [selectConversation, user]);

  const submitResearch = useCallback(
    async (
      question: string,
      perspectiveOverride?: {
        mode: PerspectiveMode;
        perspectiveIds: string[];
      },
      // 09 连续研究：由「猜你想问」卡片点出时带延续坐标；普通提问不带。
      continuation?: FollowupContinuation,
      // 06 研究进化：「继续核查」启动消息带请求实例坐标（QC V2，首轮也能带）。
      maintenanceLaunch?: MaintenanceLaunchRef,
    ): Promise<CreateMessageResponse | null> => {
      if (submitting) return null;
      setSubmitting(true);
      try {
        const effectivePerspectiveMode =
          perspectiveOverride?.mode ?? perspectiveMode;
        const effectivePerspectiveIds =
          perspectiveOverride?.perspectiveIds ?? selectedPerspectiveIds;
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
          perspective_mode: effectivePerspectiveMode,
          selected_perspective_ids: effectivePerspectiveIds,
          user,
          ...(continuation ? { continuation } : {}),
          ...(maintenanceLaunch
            ? { maintenance_launch: maintenanceLaunch }
            : {}),
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
          perspective_mode: effectivePerspectiveMode,
          selected_perspective_ids: effectivePerspectiveIds,
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
          perspective_mode: effectivePerspectiveMode,
          selected_perspective_ids: effectivePerspectiveIds,
          invoked_skill_ids: [],
          citations: [],
          degrades: [],
        };
        // Any in-flight reload captured the conversation before this new turn.
        // Invalidate it even within the SAME conversation, not only on navigation.
        ++conversationGeneration.current;
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
        refreshCredits();
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
        return created;
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "发送消息失败",
        );
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [
      connectStream,
      conversations,
      newConversation,
      refreshCredits,
      selectedSkillIds,
      selectedPerspectiveIds,
      skillMode,
      perspectiveMode,
      submitting,
      user,
    ],
  );

  /**
   * 研究进化的动作口：管理动作 / 任务选择 / 「继续核查」。
   *
   * 三件事刻意做在这里：
   * 1. 动作后**重新拉一遍投影**——项版本与管理修订都在服务端变了，拿旧投影再点会 409；
   * 2. 「继续核查」用服务端返回的 continuation 走既有 POST 消息入口，不另造一条问答链路；
   * 3. 失败不静默：错误进 `error`，投影保持原样，不伪装成已完成。
   */
  const submitEvolutionAction = useCallback(
    async (body: Record<string, unknown>) => {
      const conversationId = activeConversationRef.current;
      if (!conversationId || evolutionBusy) return;
      const wantsContinue = body.__continue === true;
      const payload = { ...body };
      delete payload.__continue;
      setEvolutionBusy(true);
      try {
        const result = await postResearchEvolutionAction(
          conversationId,
          payload,
          user,
        );
        const isSelectTask = payload.action === "select_task";
        const cont =
          (wantsContinue || isSelectTask) && result.continuation
            ? result.continuation
            : undefined;
        if (cont) {
          const prompt = String(
            cont.full_prompt ??
              (isSelectTask ? "继续这个研究任务" : "继续核查这条判断"),
          );
          // 只有带真实起源 run 的 continuation 才走延续坐标；没有就发普通消息。
          // 「从现在开始跟踪」不许把空 run_id 硬塞成 continuation（后端 min_length=1，会 422）。
          const followup = cont.run_id
            ? (cont as unknown as FollowupContinuation)
            : undefined;
          // QC V2：请求实例坐标随启动消息发出（首轮不依赖 origin run），
          // 服务端回查 rejudge 台账核验当前代际后登记 run 关联。
          const launchItemId = String(cont.maintenance_item_id ?? "");
          const launchRequestId = String(cont.request_event_id ?? "");
          const maintenanceLaunch =
            launchItemId && launchRequestId
              ? { item_id: launchItemId, request_event_id: launchRequestId }
              : undefined;
          const created = await submitResearch(
            prompt,
            undefined,
            followup,
            maintenanceLaunch,
          );
          if (!isSelectTask) {
            // 「继续核查」rejudge：登记「本次维护请求发起了这个 run」的持久化关联；
            // 消息没被接受则退回 open，不留「请求挂着、永远没有 run」的假进行态。
            const itemId = String(payload.item_id ?? "");
            const revision = result.resulting_management_revision;
            const version = payload.expected_item_version;
            const canLink =
              itemId !== "" &&
              version !== undefined &&
              String(version) !== "" &&
              typeof revision === "number";
            if (created?.run_id && canLink) {
              await postResearchEvolutionAction(
                conversationId,
                {
                  action: "link_run",
                  idempotency_key: `link_run:${itemId}:${created.run_id}`,
                  item_id: itemId,
                  run_id: created.run_id,
                  expected_item_version: version,
                  expected_management_revision: revision,
                },
                user,
              );
            } else if (!created && canLink) {
              await postResearchEvolutionAction(
                conversationId,
                {
                  action: "cancel_rejudge",
                  idempotency_key: `cancel_rejudge:${itemId}:${revision}`,
                  item_id: itemId,
                  reason: "消息未被接受，维护项退回待复核",
                  expected_item_version: version,
                  expected_management_revision: revision,
                },
                user,
              ).catch(() => undefined);
              setError("「继续核查」的消息没有被接受，这条待复核已退回未开始状态，可重新发起。");
            }
          } else if (!created) {
            setError("任务已选择，但发起研究的消息没有被接受，请从对话框重发。");
          }
        }
        const refreshed = await getResearchEvolution(conversationId, user).catch(
          () => null,
        );
        if (activeConversationRef.current === conversationId) {
          setResearchEvolution(refreshed);
        }
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "维护动作没有成功，请刷新后重试",
        );
      } finally {
        setEvolutionBusy(false);
      }
    },
    [evolutionBusy, submitResearch, user],
  );

  /** 「从现在开始跟踪」建绑定：服务端解析真实 hash/版本，幂等重试不重复建行。 */
  const submitEvolutionBinding = useCallback(
    async (body: Record<string, unknown>) => {
      const conversationId = activeConversationRef.current;
      if (!conversationId || evolutionBusy) return;
      setEvolutionBusy(true);
      try {
        await postResearchEvolutionBinding(conversationId, body, user);
        const refreshed = await getResearchEvolution(conversationId, user).catch(
          () => null,
        );
        if (activeConversationRef.current === conversationId) {
          setResearchEvolution(refreshed);
        }
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "绑定没有成功，请刷新后重试",
        );
      } finally {
        setEvolutionBusy(false);
      }
    },
    [evolutionBusy, user],
  );

  /** 受控证据目录：建绑定表单选版本时调。 */
  const fetchEvolutionCatalog = useCallback(
    (entity: string, asOf: string) => {
      const conversationId = activeConversationRef.current;
      if (!conversationId) return Promise.reject(new Error("没有活动会话"));
      return getResearchEvolutionCatalog(conversationId, entity, asOf, user);
    },
    [user],
  );

  /** 面板需要读回包的动作（练习作答 / 收据原件）：走同一个 actions 端点，成功后顺手刷新投影。 */
  const runEvolutionAction = useCallback(
    async (body: Record<string, unknown>): Promise<ResearchEvolutionActionResult> => {
      const conversationId = activeConversationRef.current;
      if (!conversationId) throw new Error("没有活动会话");
      const result = await postResearchEvolutionAction(conversationId, body, user);
      const refreshed = await getResearchEvolution(conversationId, user).catch(
        () => null,
      );
      if (activeConversationRef.current === conversationId) {
        setResearchEvolution(refreshed);
      }
      return result;
    },
    [user],
  );

  const regenerate = (assistant: ChatMessage) => {
    const assistantIndex = messages.findIndex(
      (message) => message.message_id === assistant.message_id,
    );
    const originalQuestion = messages
      .slice(0, assistantIndex)
      .reverse()
      .find((message) => message.role === "user");
    if (originalQuestion) {
      void submitResearch(originalQuestion.content, {
        mode: originalQuestion.perspective_mode,
        perspectiveIds: originalQuestion.selected_perspective_ids,
      });
    }
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
          setResearchProject(null);
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
  const activeSection: WorkbenchSection = (
    ["today", "themes", "signals", "validation", "board_calendar", "ladder", "river", "ask"] as const
  ).includes(surface.kind as WorkbenchSection)
    ? (surface.kind as WorkbenchSection)
    : "ask";
  const sectionTitles: Record<WorkbenchSection, [string, string, string]> = {
    today: ["结构化工作台", "今日态势", "市场 · 主线 · 明日验证"],
    themes: ["主题雷达", "主题状态矩阵", "知识共识与盘面确认分轴展示"],
    signals: ["事件收件箱", "晨会边际变化", "只推变化，不重复旧观点"],
    validation: ["回检台", "验证与校准", "机构胜率 · Level2 · 假设回检"],
    board_calendar: ["交易日历", "连板梯队", "按交易日查看 ≥2板 / ≥3板个股"],
    ladder: ["连板复盘", "连板梯队与晋级", "指数同轴 · 逐日阅读 · 同日复盘"],
    river: ["记忆长河", "时间记忆长河", "每日复盘 · 观察验证 · 六轨对齐"],
    ask: ["研究线程", activeConversation?.title ?? "新对话", "每轮重新检索当前证据"],
  };
  const [sectionKicker, sectionTitle, sectionSubtitle] =
    sectionTitles[activeSection];
  const navigateSection = (section: WorkbenchSection) => {
    setSurface({ kind: section });
    setConversationDrawerOpen(false);
    if (window.innerWidth < 1180) {
      setInspectorOpen(false);
    }
  };

  return (
    <div
      className={`app-shell chat-first-shell ${
        inspectorOpen ? "inspector-open" : "inspector-closed"
      }`}
    >
      {theme === "tech" && <TechBackdrop running={Boolean(runningLive)} />}
      <ConversationList
        conversations={conversations}
        activeConversationId={activeConversationId}
        mobileOpen={conversationDrawerOpen}
        onSelect={(conversationId) => void selectConversation(conversationId)}
        onNew={() => void newConversation()}
        onArchive={(conversationId) => void archive(conversationId)}
        onClose={() => setConversationDrawerOpen(false)}
        onLibrary={openLibrary}
        activeSection={activeSection}
        onSection={navigateSection}
        credits={credits}
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
            <span className="thread-kicker">{sectionKicker}</span>
            <strong>{theme === "tech" ? <DecodeTitle text={sectionTitle} /> : sectionTitle}</strong>
            <small>{sectionSubtitle}</small>
          </div>
          <div className="chat-topbar-actions">
            <button
              className="icon-button theme-toggle"
              type="button"
              aria-label={theme === "tech" ? "切换为暖纸主题" : "切换为科技主题"}
              title={theme === "tech" ? "切换为暖纸主题" : "切换为科技主题"}
              aria-pressed={theme === "tech"}
              onClick={() => setTheme(current => current === "tech" ? "paper" : "tech")}
            >
              {theme === "tech" ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
            </button>
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

        {["today", "themes", "signals", "validation", "board_calendar", "river", "ladder"].includes(surface.kind) && overview?.market_freshness && (
          <StaleDataBanner
            freshness={overview.market_freshness}
            viewingDate={surface.kind === "river" || surface.kind === "ladder" ? marketFocusDate : null}
          />
        )}

        {(surface.kind === "home" || surface.kind === "ask") && (
          <div className="conversation-surface">
            <MessageThread
              messages={messages}
              skills={skills}
              liveMessages={liveMessages}
              runBundles={runBundles}
              onRegenerate={regenerate}
              onOpenArtifact={(artifactId) => void openArtifact(artifactId)}
              onFollowup={(question, continuation) =>
                void submitResearch(question, undefined, continuation)
              }
              onStarter={setDraft}
            />
            <div className="chat-composer-dock">
              <Composer
                value={draft}
                taskType="ask"
                disabled={submitting || loading}
                running={Boolean(runningLive)}
                stopRequested={runningLive?.cancelRequested ?? false}
                skills={skills}
                perspectives={perspectives}
                skillMode={skillMode}
                selectedSkillIds={selectedSkillIds}
                perspectiveMode={perspectiveMode}
                selectedPerspectiveIds={selectedPerspectiveIds}
                onChange={setDraft}
                onSubmit={(question) => void submitResearch(question)}
                onStop={stopGeneration}
                onSkillModeChange={setSkillMode}
                onSkillSelectionChange={setSelectedSkillIds}
                onPerspectiveModeChange={setPerspectiveMode}
                onPerspectiveSelectionChange={setSelectedPerspectiveIds}
              />
            </div>
          </div>
        )}

        {(["today", "themes", "signals", "validation"] as const).includes(
          surface.kind as "today" | "themes" | "signals" | "validation",
        ) &&
          overview && (
            <OutputWorkbench
              overview={overview}
              section={
                surface.kind as "today" | "themes" | "signals" | "validation"
              }
              refreshing={overviewRefreshing}
              onRefresh={refreshOverview}
            />
          )}

        {surface.kind === "board_calendar" && <BoardCalendarDashboard
          focusDate={marketFocusDate}
          onOpenLadder={date => { setMarketFocusDate(date); navigateSection("ladder"); }}
        />}

        {surface.kind === "river" && (
          <RiverWorkbench
            focusDate={marketFocusDate}
            onFocusDate={setMarketFocusDate}
            onOpenLadder={date => { setMarketFocusDate(date); navigateSection("ladder"); }}
          />
        )}
        {surface.kind === "ladder" && (
          <LimitUpDashboard
            focusDate={marketFocusDate}
            onFocusDate={setMarketFocusDate}
            onOpenRiver={date => { setMarketFocusDate(date); navigateSection("river"); }}
          />
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

        {loading &&
          (surface.kind === "home" || surface.kind === "ask") &&
          messages.length === 0 && (
          <div className="surface-loading">正在恢复会话…</div>
        )}
        {!loading &&
          !overview &&
          (["today", "themes", "signals", "validation"] as const).includes(
            surface.kind as "today" | "themes" | "signals" | "validation",
          ) && <div className="surface-loading">结构化数据暂不可用</div>}
      </main>

      <ResearchInspector
        bootstrap={bootstrap}
        bundle={inspectorBundle}
        artifact={artifact}
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
        project={researchProject}
        onFollowup={(question, continuation) =>
          void submitResearch(question, undefined, continuation)
        }
        evolution={researchEvolution}
        onEvolutionAction={(body) => void submitEvolutionAction(body)}
        onEvolutionBind={(body) => void submitEvolutionBinding(body)}
        onFetchEvolutionCatalog={fetchEvolutionCatalog}
        runEvolutionAction={runEvolutionAction}
        evolutionBusy={evolutionBusy}
      />
      <ModelSettings
        open={modelSettingsOpen}
        config={llmConfig}
        saving={modelSettingsSaving}
        error={modelSettingsError}
        onClose={() => setModelSettingsOpen(false)}
        onSave={(provider, apiKey, baseUrl, model, remember) => {
          void saveBYOK(provider, apiKey, baseUrl, model, remember);
        }}
        onUseBuiltIn={() => {
          void restoreBuiltInLLM();
        }}
        onForgetSaved={() => {
          void forgetSavedModel();
        }}
      />
    </div>
  );
}
