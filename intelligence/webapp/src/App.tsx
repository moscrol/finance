import { PanelRightOpen, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  artifactContentUrl,
  createRun,
  getArtifact,
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
import type {
  ArtifactDescriptor,
  Bootstrap,
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
  const [loading, setLoading] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    async (runId: string) => {
      setLoading(true);
      try {
        const run = await getRun(runId, user);
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
        setRunBundle({
          run,
          trace,
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
        setError(caught instanceof Error ? caught.message : "无法加载研究运行");
      } finally {
        setLoading(false);
      }
    },
    [user],
  );

  const openRun = useCallback(
    (runId: string) => {
      setSurface({ kind: "run", runId });
      setInspectorOpen(false);
      void loadRunBundle(runId);
    },
    [loadRunBundle],
  );

  const activeRunId = runBundle?.run.run_id;
  const activeRunStatus = runBundle?.run.status;

  useEffect(() => {
    const run = runBundle?.run;
    if (!run || surface.kind !== "run" || terminalStatuses.has(run.status)) return;

    const events = new EventSource(runEventsUrl(run.run_id, user));
    events.onopen = () => setConnection("connected");
    events.addEventListener("step", (event) => {
      const step = JSON.parse((event as MessageEvent<string>).data) as TraceStep;
      setRunBundle((current) =>
        current
          ? {
              ...current,
              trace: [...current.trace, step],
            }
          : current,
      );
    });
    events.addEventListener("run", (event) => {
      const nextRun = JSON.parse((event as MessageEvent<string>).data) as Run;
      setRunBundle((current) => (current ? { ...current, run: nextRun } : current));
      events.close();
      void loadRunBundle(nextRun.run_id);
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
    setSurface({ kind: "library" });
    setArtifact(null);
    setInspectorOpen(false);
    void loadLibrary();
  };

  const openArtifact = useCallback(
    async (artifactId: string) => {
      setSurface({ kind: "artifact", artifactId });
      setLoading(true);
      setArtifactContent(null);
      setInspectorOpen(false);
      try {
        const descriptor = await getArtifact(artifactId, user);
        setArtifact(descriptor);
        setRunBundle(null);
        if (
          descriptor.status !== "missing" &&
          ["native_markdown", "native_json"].includes(descriptor.viewer)
        ) {
          setArtifactContent(await getArtifactText(artifactId, user));
        }
        setError(null);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "无法加载产物");
      } finally {
        setLoading(false);
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
    setSurface({ kind: "home" });
    setTaskType(workflow.task_type);
    setDraft(workflow.prompt);
  };

  const showHome = () => {
    setSurface({ kind: "home" });
    setRunBundle(null);
    setArtifact(null);
    setTaskType("ask");
    setInspectorOpen(false);
  };

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
