import type { Followup, FollowupContinuation } from "./types";

/**
 * 卡片点击 → 延续坐标。没有 run_id（历史消息缺失、乐观占位）时不造假坐标，
 * 服务端会把这一轮当普通提问；有 run_id 时把种类 / 来源 / 标签 / 原文 / 继承项一起带上。
 */
export function continuationFor(
  followup: Followup,
  runId: string | null | undefined,
): FollowupContinuation | undefined {
  if (!runId) return undefined;
  const continuation: FollowupContinuation = {
    run_id: runId,
    full_prompt: followup.full_prompt || followup.question,
  };
  if (followup.kind) continuation.kind = followup.kind;
  if (followup.source) continuation.source = followup.source;
  if (followup.label) continuation.label = followup.label;
  if (followup.inherits && Object.keys(followup.inherits).length > 0) {
    continuation.inherits = followup.inherits;
  }
  return continuation;
}

export const TRIGGER_STATUS_LABEL: Record<string, string> = {
  hit: "命中",
  miss: "落空",
  partial: "半对",
  unverifiable: "暂无法判定",
  due: "到期待判",
  pending: "跟踪中",
};

export function triggerStatusLabel(status: string): string {
  return TRIGGER_STATUS_LABEL[status] ?? status;
}
