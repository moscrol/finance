import { Check, CircleDashed, X } from "lucide-react";
import { userFacingStage, userFacingText } from "../displayText";
import type { TraceStep } from "../types";

interface ProgressTimelineProps {
  steps: TraceStep[];
  /** True while the run is still producing steps. */
  active: boolean;
}

function stepText(step: TraceStep): string {
  return userFacingText(step.output_summary || userFacingStage(step.name));
}

/**
 * Render every milestone of a run, not just the newest one.
 *
 * The previous bubble showed `progress[progress.length - 1]` and only while the
 * answer was empty, so a 38-second run read as one static line followed by a
 * wall of text.  Every step the backend already streams is shown here, and the
 * list survives completion (collapsed) so the run stays auditable.
 */
export function ProgressTimeline({ steps, active }: ProgressTimelineProps) {
  if (steps.length === 0) {
    return active ? (
      <div className="message-thinking" role="status">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
        正在检索本轮证据
      </div>
    ) : null;
  }

  const lastIndex = steps.length - 1;
  const list = (
    <ol className="progress-timeline">
      {steps.map((step, index) => {
        const running = step.status === "running";
        const failed = step.status === "failed";
        // Only the newest running step pulses; earlier ones were superseded by
        // a later milestone even if their own status never flipped.
        const current = active && running && index === lastIndex;
        return (
          <li
            key={step.step_id}
            className={[
              "progress-step",
              current ? "is-current" : "",
              failed ? "is-failed" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="progress-step-icon" aria-hidden="true">
              {failed ? (
                <X size={12} />
              ) : current ? (
                <CircleDashed size={12} />
              ) : (
                <Check size={12} />
              )}
            </span>
            <span className="progress-step-text">{stepText(step)}</span>
          </li>
        );
      })}
    </ol>
  );

  if (active) {
    return (
      <div className="progress-timeline-live" role="status" aria-live="polite">
        {list}
      </div>
    );
  }

  return (
    <details className="progress-timeline-done">
      <summary>研究过程（{steps.length} 步）</summary>
      {list}
    </details>
  );
}
