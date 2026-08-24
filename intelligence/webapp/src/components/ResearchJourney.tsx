import { AlertTriangle, Check, Circle, Minus } from "lucide-react";
import type {
  ResearchJourneyModel,
  ResearchPhaseStatus,
} from "../researchJourney";
import "./researchJourney.css";

interface ResearchJourneyProps {
  model: ResearchJourneyModel;
  connection: "connected" | "reconnecting";
  compact?: boolean;
}

const phaseStatusLabels: Record<ResearchPhaseStatus, string> = {
  waiting: "等待中",
  running: "进行中",
  completed: "已完成",
  skipped: "未执行",
  attention: "需要关注",
};

function PhaseIcon({ status }: { status: ResearchPhaseStatus }) {
  if (status === "completed") return <Check size={12} />;
  if (status === "attention") return <AlertTriangle size={12} />;
  if (status === "skipped") return <Minus size={12} />;
  return <Circle size={10} />;
}

export function ResearchJourney({
  model,
  connection,
  compact = false,
}: ResearchJourneyProps) {
  const currentPhase =
    model.currentPhaseIndex === null
      ? null
      : model.phases[model.currentPhaseIndex];
  const mobileSummary = currentPhase
    ? `阶段 ${model.currentPhaseIndex! + 1}/${model.phases.length} · ${currentPhase.label} · ${phaseStatusLabels[currentPhase.status]}`
    : "研究阶段更新中";
  const action =
    connection === "reconnecting"
      ? `连接恢复中 · ${model.currentAction}`
      : model.currentAction;

  return (
    <section
      className={`research-journey${compact ? " is-compact" : ""}`}
      aria-label="研究进度"
    >
      <div className="research-journey-heading">
        <span>Foresight · {model.runLabel}</span>
        <small>研究旅程</small>
      </div>

      <div className="research-journey-mobile-summary">{mobileSummary}</div>

      <ol className="research-journey-track" aria-label="研究阶段" role="list">
        {model.phases.map((phase, index) => {
          const current = index === model.currentPhaseIndex;
          const statusLabel = phaseStatusLabels[phase.status];
          return (
            <li
              key={phase.id}
              className={[
                "research-journey-phase",
                `is-${phase.status}`,
                current ? "is-current" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-current={current ? "step" : undefined}
              aria-label={`${phase.label}，${statusLabel}`}
            >
              <span className="research-journey-marker" aria-hidden="true">
                <PhaseIcon status={phase.status} />
              </span>
              <span className="research-journey-phase-copy">
                <strong>{phase.label}</strong>
                <small>{statusLabel}</small>
              </span>
            </li>
          );
        })}
      </ol>

      <div
        className={[
          "research-journey-action",
          connection === "reconnecting" ? "is-reconnecting" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {action}
      </div>
    </section>
  );
}
