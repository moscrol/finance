import { PanelRightOpen, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  artifactContentUrl,
  createRun,
  getArtifact,
  getArtifactProjection,
  getArtifactText,
  getBootstrap,
  getFollowups,
  getRun,
  getRunArtifactText,
  getRunContext,
  getTrace,
  listArtifacts,
  runEventsUrl,
} from "./api";
import { ArtifactLibrary } from "./components/ArtifactLibrary";
import { ArtifactViewer } from "./components/ArtifactViewer";
import { Composer } from "./components/Composer";
import { ResearchHome } from "./components/ResearchHome";
import { ResearchInspector } from "./components/ResearchInspector";
import { RunView } from "./components/RunView";
import { Sidebar } from "./components/Sidebar";
import { supportsDailyProjection } from "./dailyReports";
import { deduplicateTrace, upsertTraceStep } from "./trace";
import type {
  ArtifactDescriptor,
  Bootstrap,
  DailyReportProjection,
  Run,
  RunBundle,
  Surface,
  TraceStep,
  Workflow,
} from "./types";

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

export default function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [surface, setSurface] = useState<Surface>({ kind: "home" });
  const [draft, setDraft] = useState("");
  const [taskType, setTaskType] = useState("ask");
  const [submitting, setSubmitting] = useState(false);
  const [runBundle, setRunBundle] = useState<RunBundle | null>(null);
  const [connection, setConnection] = useState<"connected" | "reconnecting">("connected");
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
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runRequestGeneration = useRef(0);
  const artifactRequestGeneration = useRef(0);

  const user = bootstrap?.user;

  const refreshBootstrap = useCallback(async () => {
    try {
      const next = await getBootstrap(user);
      setBootstrap(next);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workbench 初始化失败");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refreshBootstrap();
  }, [refreshBootstrap]);

  const loadRunBundle = useCallback(
    async (
      runId: string,
      generation = ++runRequestGeneration.current,
    ) => {
      setLoading(true);
      setRunBundle(null);
      try {
        const run = await getRun(runId, user);
        if (generation !== runRequestGeneration.current) return;
        const answerArtifact = run.artifacts.find((item) => item.path === "answer.md");
        const [trace, followups, context, registeredArtifacts, answer] = await Promise.all([
          getTrace(runId, user),
          getFollowups(runId, user),
          getRunContext(runId, user),
          listArtifacts({ category: "run" }, user),
          answerArtifact
            ? getRunArtifactText(runId, answerArtifact.path, user).catch(() => null)
            : Promise.resolve(null),
        ]);
        if (generation !== runRequestGeneration.current) return;
        setRunBundle({
          run,
          trace: deduplicateTrace(trace),
          followups,
          context,
          answer,
          registeredArtifacts: registeredArtifacts.filter(
            (item) => item.related_run_id === runId,
          ),
        });
        setArtifact(null);
        setError(null);
      } catch (caught) {
        if (generation === runRequestGeneration.current) {
          setError(caught instanceof Error ? caught.message : "无法加载研究运行");
        }
      } finally {
        if (generation === runRequestGeneration.current) {
          setLoading(false);
        }
      }
    },
    [user],
  );

  const openRun = useCallback(
    (runId: string) => {
      artifactRequestGeneration.current += 1;
      const generation = ++runRequestGeneration.current;
      setSurface({ kind: "run", runId });
      setRunBundle(null);
      setArtifact(null);
      setArtifactContent(null);
      setArtifactProjection(null);
      setArtifactProjectionError(null);
      setOriginalReportArtifactId(null);
      setInspectorOpen(false);
      void loadRunBundle(runId, generation);
    },
    [loadRunBundle],
  );

  const activeRunId = runBundle?.run.run_id;
  const activeRunStatus = runBundle?.run.status;

  useEffect(() => {
    const run = runBundle?.run;
    if (!run || surface.kind !== "run" || terminalStatuses.has(run.status)) return;

    const generation = runRequestGeneration.current;
    const events = new EventSource(runEventsUrl(run.run_id, user));
    events.onopen = () => setConnection("connected");
    events.addEventListener("step", (event) => {
      if (generation !== runRequestGeneration.current) return;
      const step = JSON.parse((event as MessageEvent<string>).data) as TraceStep;
      setRunBundle((current) =>
        current
          ? {
              ...current,
              trace: upsertTraceStep(current.trace, step),
            }
          : current,
      );
    });
    events.addEventListener("run", (event) => {
      if (generation !== runRequestGeneration.current) return;
      const nextRun = JSON.parse((event as MessageEvent<string>).data) as Run;
      setRunBundle((current) => (current ? { ...current, run: nextRun } : current));
      events.close();
      void loadRunBundle(nextRun.run_id, generation);
      void refreshBootstrap();
    });
    events.onerror = () => setConnection("reconnecting");
    return () => events.close();
  }, [
    activeRunId,
    activeRunStatus,
    loadRunBundle,
    refreshBootstrap,
    runBundle?.run,
    surface.kind,
    user,
  ]);

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
    runRequestGeneration.current += 1;
    artifactRequestGeneration.current += 1;
    setSurface({ kind: "library" });
    setRunBundle(null);
    setArtifact(null);
    setArtifactContent(null);
    setArtifactProjection(null);
    setArtifactProjectionError(null);
    setOriginalReportArtifactId(null);
    setInspectorOpen(false);
    void loadLibrary();
  };

  const openArtifact = useCallback(
    async (artifactId: string) => {
      runRequestGeneration.current += 1;
      const generation = ++artifactRequestGeneration.current;
      setSurface({ kind: "artifact", artifactId });
      setLoading(true);
      setRunBundle(null);
      setArtifact(null);
      setArtifactContent(null);
      setArtifactProjection(null);
      setArtifactProjectionError(null);
      setOriginalReportArtifactId(null);
      setInspectorOpen(false);
      try {
        const descriptor = await getArtifact(artifactId, user);
        if (generation !== artifactRequestGeneration.current) return;
        setArtifact(descriptor);
        if (descriptor.viewer === "legacy_html") {
          setOriginalReportArtifactId(descriptor.artifact_id);
        }
        if (descriptor.status !== "missing" && supportsDailyProjection(descriptor)) {
          try {
            const projection = await getArtifactProjection(artifactId, user);
            if (generation !== artifactRequestGeneration.current) return;
            setArtifactProjection(projection);
          } catch (caught) {
            if (generation === artifactRequestGeneration.current) {
              try {
                const candidates = await listArtifacts(
                  { category: descriptor.category, date: descriptor.date ?? undefined },
                  user,
                );
                if (generation !== artifactRequestGeneration.current) return;
                const original = candidates.find(
                  (candidate) => candidate.viewer === "legacy_html",
                );
                setOriginalReportArtifactId(original?.artifact_id ?? null);
              } catch {
                if (generation !== artifactRequestGeneration.current) return;
              }
              setArtifactProjectionError(
                caught instanceof Error ? caught.message : "无法生成原生报告",
              );
            }
          }
        } else if (
          descriptor.status !== "missing" &&
          ["native_markdown", "native_json"].includes(descriptor.viewer)
        ) {
          const content = await getArtifactText(artifactId, user);
          if (generation !== artifactRequestGeneration.current) return;
          setArtifactContent(content);
        }
        if (generation === artifactRequestGeneration.current) {
          setError(null);
        }
      } catch (caught) {
        if (generation === artifactRequestGeneration.current) {
          setError(caught instanceof Error ? caught.message : "无法加载产物");
        }
      } finally {
        if (generation === artifactRequestGeneration.current) {
          setLoading(false);
        }
      }
    },
    [user],
  );

  const submitResearch = useCallback(
    async (
      question: string,
      parentRunId?: string | null,
      taskTypeOverride?: string,
    ) => {
      setSubmitting(true);
      try {
        const created = await createRun(
          question,
          taskTypeOverride ?? taskType,
          user,
          parentRunId,
        );
        setDraft("");
        setTaskType("ask");
        openRun(created.run_id);
        void refreshBootstrap();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "创建研究失败");
      } finally {
        setSubmitting(false);
      }
    },
    [openRun, refreshBootstrap, taskType, user],
  );

  const handleWorkflow = (workflow: Workflow) => {
    if (workflow.id === "daily" && workflow.artifact_id) {
      void openArtifact(workflow.artifact_id);
      return;
    }
    runRequestGeneration.current += 1;
    artifactRequestGeneration.current += 1;
    setSurface({ kind: "home" });
    setRunBundle(null);
    setArtifact(null);
    setArtifactContent(null);
    setArtifactProjection(null);
    setArtifactProjectionError(null);
    setOriginalReportArtifactId(null);
    setTaskType(workflow.task_type);
    setDraft(workflow.prompt);
  };

  const showHome = () => {
    runRequestGeneration.current += 1;
    artifactRequestGeneration.current += 1;
    setSurface({ kind: "home" });
    setRunBundle(null);
    setArtifact(null);
    setArtifactContent(null);
    setArtifactProjection(null);
    setArtifactProjectionError(null);
    setOriginalReportArtifactId(null);
    setTaskType("ask");
    setInspectorOpen(false);
  };

  const surfaceIdentity =
    surface.kind === "run"
      ? `run:${surface.runId}`
      : surface.kind === "artifact"
        ? `artifact:${surface.artifactId}`
        : surface.kind;

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [surfaceIdentity]);

  return (
    <div className="app-shell">
      <Sidebar
        bootstrap={bootstrap}
        surface={surface}
        onHome={showHome}
        onLibrary={openLibrary}
        onOpenRun={openRun}
        onWorkflow={handleWorkflow}
      />

      <main className="main-surface">
        <div className="mobile-topbar">
          <strong>Market Intelligence</strong>
          <button
            className="icon-button inspector-toggle"
            type="button"
            aria-label="打开研究检查器"
            onClick={() => setInspectorOpen(true)}
          >
            <PanelRightOpen aria-hidden="true" size={19} />
          </button>
        </div>

        {error && (
          <div className="global-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => window.location.reload()}>
              <RefreshCw aria-hidden="true" size={15} />
              重试
            </button>
          </div>
        )}

        {surface.kind === "home" && (
          <ResearchHome
            bootstrap={bootstrap}
            draft={draft}
            taskType={taskType}
            submitting={submitting}
            onDraftChange={setDraft}
            onSubmit={(question) => void submitResearch(question)}
            onWorkflow={handleWorkflow}
            onOpenRun={openRun}
          />
        )}

        {surface.kind === "library" && (
          <ArtifactLibrary artifacts={artifacts} loading={loading} onOpen={openArtifact} />
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
            onOpenRun={openRun}
          />
        )}

        {surface.kind === "run" && runBundle && (
          <>
            <RunView
              bundle={runBundle}
              connection={connection}
              onOpenRun={openRun}
              onOpenArtifact={(artifactId) => void openArtifact(artifactId)}
              onFollowup={(question) => {
                void submitResearch(question, runBundle.run.run_id, "ask");
              }}
            />
            <div className="run-composer-dock">
              <Composer
                compact
                value={draft}
                taskType="ask"
                disabled={submitting}
                onChange={setDraft}
                onSubmit={(question) =>
                  void submitResearch(question, runBundle.run.run_id, "ask")
                }
              />
            </div>
          </>
        )}

        {loading && surface.kind === "run" && !runBundle && (
          <div className="surface-loading">正在读取研究运行…</div>
        )}
      </main>

      <button
        className="floating-inspector-button"
        type="button"
        aria-label="打开研究检查器"
        onClick={() => setInspectorOpen(true)}
      >
        <PanelRightOpen aria-hidden="true" size={18} />
      </button>
      <ResearchInspector
        bundle={runBundle}
        artifact={artifact}
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
      />
    </div>
  );
}
