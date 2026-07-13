import { ChevronDown, Puzzle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ProductSkillDescription, SkillMode } from "../types";

interface SkillPickerProps {
  skills: ProductSkillDescription[];
  mode: SkillMode;
  selectedSkillIds: string[];
  disabled?: boolean;
  onModeChange: (mode: SkillMode) => void;
  onSelectionChange: (skillIds: string[]) => void;
}

export function SkillPicker({
  skills,
  mode,
  selectedSkillIds,
  disabled = false,
  onModeChange,
  onSelectionChange,
}: SkillPickerProps) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);
  const selected = new Set(selectedSkillIds);
  const modeLabel =
    mode === "manual"
      ? "手动指定研究工具"
      : mode === "auto"
        ? "自动选择研究工具"
        : "自动选择并补充指定工具";
  const triggerLabel =
    selectedSkillIds.length > 0
      ? `${modeLabel} · ${selectedSkillIds.length}`
      : modeLabel;

  useEffect(() => {
    if (!open) return;
    const closeOnPointerDown = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !pickerRef.current?.contains(event.target)
      ) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnPointerDown);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnPointerDown);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const toggle = (skillId: string) => {
    if (selected.has(skillId)) {
      onSelectionChange(selectedSkillIds.filter((item) => item !== skillId));
      return;
    }
    if (selectedSkillIds.length < 3) {
      onSelectionChange([...selectedSkillIds, skillId]);
    }
  };

  return (
    <div className="skill-picker" ref={pickerRef}>
      <div className="skill-picker-controls">
        <div className="skill-menu">
          <button
            className="skill-menu-trigger"
            type="button"
            aria-label="选择研究工具"
            aria-expanded={open}
            aria-haspopup="menu"
            disabled={disabled}
            onClick={() => setOpen((current) => !current)}
          >
            <Puzzle aria-hidden="true" size={15} />
            <span>{triggerLabel}</span>
            <ChevronDown aria-hidden="true" size={14} />
          </button>
          {open && (
            <div className="skill-menu-popover" role="menu">
              <div className="skill-menu-heading">
                <strong>研究工具</strong>
                <small>最多指定 3 个；自动模式会根据问题选择所需工具。</small>
              </div>
              {skills.map((skill) => (
                <label className="skill-option" key={skill.skill_id}>
                  <input
                    type="checkbox"
                    checked={selected.has(skill.skill_id)}
                    disabled={
                      disabled ||
                      (!selected.has(skill.skill_id) &&
                        selectedSkillIds.length >= 3)
                    }
                    onChange={() => toggle(skill.skill_id)}
                  />
                  <span>
                    <strong>{skill.name}</strong>
                    <small>{skill.description}</small>
                  </span>
                </label>
              ))}
              {skills.length === 0 && (
                <p className="skill-menu-empty">暂无可用研究工具</p>
              )}
            </div>
          )}
        </div>
        <label className="skill-mode">
          <span className="sr-only">研究工具选择方式</span>
          <select
            aria-label="研究工具选择方式"
            value={mode}
            disabled={disabled}
            onChange={(event) =>
              onModeChange(event.target.value as SkillMode)
            }
          >
            <option value="hybrid">自动选择并补充指定工具</option>
            <option value="manual">手动指定研究工具</option>
            <option value="auto">自动选择研究工具</option>
          </select>
        </label>
      </div>
      {selectedSkillIds.length > 0 && (
        <div className="skill-chips" aria-label="已选研究工具">
          {selectedSkillIds.map((skillId) => {
            const skill = skills.find((item) => item.skill_id === skillId);
            if (!skill) return null;
            return (
              <span className="skill-chip" key={skillId}>
                {skill.name}
                <button
                  type="button"
                  aria-label={`移除 ${skill.name}`}
                  disabled={disabled}
                  onClick={() => toggle(skillId)}
                >
                  <X aria-hidden="true" size={13} />
                </button>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
