import { AlertTriangle, Check, Circle, CircleDashed, Minus, X } from "lucide-react";
import { userFacingStage, userFacingText } from "../displayText";
import {
  journeyShowsPhaseTrack,
  type ResearchJourneyModel,
  type ResearchPhaseStatus,
} from "../researchJourney";
import type { TraceStep } from "../types";
import "./researchJourney.css";

interface ResearchJourneyProps {
  model: ResearchJourneyModel;
  connection: "connected" | "reconnecting";
  compact?: boolean;
  announce?: boolean;
  steps?: TraceStep[];
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

function stepText(step: TraceStep): string {
  return userFacingText(step.output_summary.trim() || userFacingStage(step.name));
}

export function ResearchJourney({
  model,
  connection,
  compact = false,
  announce = true,
  steps = [],
}: ResearchJourneyProps) {
  const currentPhase =
    model.currentPhaseIndex === null
      ? null
      : model.phases[model.currentPhaseIndex];
  const caption = currentPhase
    ? `${currentPhase.label} · ${phaseStatusLabels[currentPhase.status]}`
    : null;
  const fallbackAction =
    connection === "reconnecting"
      ? `连接恢复中 · ${model.currentAction}`
      : model.currentAction;
  const showTrack = journeyShowsPhaseTrack(model);
  const liveIndex = steps.length - 1;

  return (
    <section
      className={`research-journey${compact ? " is-compact" : ""}`}
      aria-label="研究进度"
    >
      {steps.length === 0 ? (
        <div
          className={[
            "research-journey-action",
            connection === "reconnecting" ? "is-reconnecting" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          role={announce ? "status" : "note"}
          aria-live={announce ? "polite" : undefined}
          aria-atomic={announce ? "true" : undefined}
        >
          {fallbackAction}
        </div>
      ) : (
        <ol className="research-journey-steps" aria-label="研究步骤" role="list">
          {steps.map((step, index) => {
            const current = index === liveIndex;
            const failed = step.status === "failed";
            const liveRole = current
              ? announce
                ? "status"
                : "note"
              : undefined;
            return (
              <li
                key={step.step_id}
                className={[
                  "research-journey-step",
                  current ? "is-current" : "",
                  failed ? "is-failed" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                role={liveRole}
                aria-live={liveRole === "status" ? "polite" : undefined}
                aria-atomic={liveRole === "status" ? "true" : undefined}
              >
                <span className="research-journey-step-icon" aria-hidden="true">
                  {failed ? (
                    <X size={13} />
                  ) : current && step.status === "running" ? (
                    <CircleDashed size={13} />
                  ) : (
                    <Check size={13} />
                  )}
                </span>
                <span className="research-journey-step-text">
                  {current && connection === "reconnecting"
                    ? `连接恢复中 · ${stepText(step)}`
                    : stepText(step)}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      {showTrack ? (
        <>
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
                  <span className="research-journey-phase-copy sr-only">
                    {phase.label} {statusLabel}
                  </span>
                </li>
              );
            })}
          </ol>
          {caption ? (
            <p className="research-journey-caption" aria-hidden="true">
              {caption}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
