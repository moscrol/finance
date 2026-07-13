import { Check, LoaderCircle, TriangleAlert } from "lucide-react";
import type {
  ProductSkillDescription,
  SkillInvocationStatus,
} from "../types";

interface SkillInvocationProps {
  skills: ProductSkillDescription[];
  selectedSkillIds: string[];
  invokedSkillIds: string[];
  statuses?: Record<string, SkillInvocationStatus>;
}

export function SkillInvocation({
  skills,
  selectedSkillIds,
  invokedSkillIds,
  statuses = {},
}: SkillInvocationProps) {
  const ids = [...new Set([...selectedSkillIds, ...invokedSkillIds])];
  if (ids.length === 0) return null;
  const selected = new Set(selectedSkillIds);

  return (
    <div className="skill-invocations" aria-label="研究工具">
      {ids.map((skillId) => {
        const skill = skills.find((item) => item.skill_id === skillId);
        if (!skill) return null;
        const status = statuses[skillId] ?? "completed";
        const Icon =
          status === "running" || status === "pending"
            ? LoaderCircle
            : status === "completed"
              ? Check
              : TriangleAlert;
        const statusLabel =
          status === "completed"
            ? "已完成"
            : status === "failed"
              ? "未完成"
              : "研究中";
        return (
          <span
            className={`skill-invocation skill-${status}`}
            key={skillId}
            title={`${skill.name} · ${statusLabel}`}
          >
            <Icon
              className={status === "running" ? "spin" : undefined}
              aria-hidden="true"
              size={13}
            />
            {selected.has(skillId) ? "已指定工具" : "已自动选择"} · {skill.name}
          </span>
        );
      })}
    </div>
  );
}
