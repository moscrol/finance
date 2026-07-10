import type { TraceStep } from "./types";

export function upsertTraceStep(
  steps: TraceStep[],
  step: TraceStep,
): TraceStep[] {
  const index = steps.findIndex((item) => item.step_id === step.step_id);
  if (index === -1) return [...steps, step];
  const next = [...steps];
  next[index] = step;
  return next;
}

export function deduplicateTrace(steps: TraceStep[]): TraceStep[] {
  return steps.reduce(upsertTraceStep, []);
}
