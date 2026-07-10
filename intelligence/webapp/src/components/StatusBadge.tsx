import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleX,
  Clock3,
} from "lucide-react";
import type { ArtifactDescriptor, RunStatus } from "../types";

type BadgeStatus = RunStatus | ArtifactDescriptor["status"] | "degraded" | "reconnecting";

const labels: Record<BadgeStatus, string> = {
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  ok: "可用",
  warn: "需核对",
  missing: "文件缺失",
  degraded: "已降级",
  reconnecting: "正在恢复连接",
};

export function StatusBadge({ status }: { status: BadgeStatus }) {
  const Icon =
    status === "completed" || status === "ok"
      ? CheckCircle2
      : status === "failed" || status === "missing"
        ? CircleX
        : status === "warn" || status === "degraded"
          ? AlertTriangle
          : status === "queued"
            ? Clock3
            : CircleDashed;
  return (
    <span className={`status-badge status-${status}`}>
      <Icon aria-hidden="true" size={14} />
      {labels[status]}
    </span>
  );
}
