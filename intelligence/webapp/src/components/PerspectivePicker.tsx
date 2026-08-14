import { ChevronDown, Eye, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type {
  PerspectiveDescription,
  PerspectiveMode,
} from "../types";

interface PerspectivePickerProps {
  perspectives: PerspectiveDescription[];
  mode: PerspectiveMode;
  selectedPerspectiveIds: string[];
  disabled?: boolean;
  onModeChange: (mode: PerspectiveMode) => void;
  onSelectionChange: (perspectiveIds: string[]) => void;
}

export function PerspectivePicker({
  perspectives,
  mode,
  selectedPerspectiveIds,
  disabled = false,
  onModeChange,
  onSelectionChange,
}: PerspectivePickerProps) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);
  const selected = new Set(selectedPerspectiveIds);
  const selectedNames = selectedPerspectiveIds
    .map(
      (perspectiveId) =>
        perspectives.find(
          (perspective) => perspective.perspective_id === perspectiveId,
        )?.display_name,
    )
    .filter((name): name is string => Boolean(name));
  const label =
    mode === "neutral"
      ? "数据中立"
      : mode === "single"
        ? selectedNames[0] ?? "指定 KOL"
        : `多视角 · ${selectedNames.length + 1}`;

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

  const selectMode = (nextMode: PerspectiveMode) => {
    onModeChange(nextMode);
    if (nextMode === "neutral") {
      onSelectionChange([]);
      return;
    }
    if (selectedPerspectiveIds.length === 0 && perspectives[0]) {
      onSelectionChange([perspectives[0].perspective_id]);
    }
    if (nextMode === "single" && selectedPerspectiveIds.length > 1) {
      onSelectionChange([selectedPerspectiveIds[0]]);
    }
  };

  const toggle = (perspectiveId: string) => {
    if (mode === "single") {
      onSelectionChange([perspectiveId]);
      return;
    }
    if (selected.has(perspectiveId)) {
      if (selectedPerspectiveIds.length > 1) {
        onSelectionChange(
          selectedPerspectiveIds.filter((item) => item !== perspectiveId),
        );
      }
      return;
    }
    if (selectedPerspectiveIds.length < 3) {
      onSelectionChange([...selectedPerspectiveIds, perspectiveId]);
    }
  };

  return (
    <div className="perspective-picker" ref={pickerRef}>
      <button
        className="skill-menu-trigger perspective-menu-trigger"
        type="button"
        aria-label="选择分析视角"
        aria-expanded={open}
        aria-haspopup="menu"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <Eye aria-hidden="true" size={15} />
        <span>{label}</span>
        <ChevronDown aria-hidden="true" size={14} />
      </button>
      {open && (
        <div className="skill-menu-popover perspective-menu-popover" role="menu">
          <div className="skill-menu-heading">
            <strong>分析视角</strong>
            <small>事实层与 KOL 观点层隔离；多视角保留冲突，不做多数投票。</small>
          </div>
          <label className="skill-option">
            <input
              type="radio"
              name="perspective-mode"
              checked={mode === "neutral"}
              onChange={() => selectMode("neutral")}
            />
            <span>
              <strong>数据中立</strong>
              <small>仅当前事实证据，不调用 KOL 或个人金融记忆。</small>
            </span>
          </label>
          <label className="skill-option">
            <input
              type="radio"
              name="perspective-mode"
              checked={mode === "single"}
              disabled={perspectives.length === 0}
              onChange={() => selectMode("single")}
            />
            <span>
              <strong>指定 KOL</strong>
              <small>只使用一位 KOL 的画像和原文召回。</small>
            </span>
          </label>
          <label className="skill-option">
            <input
              type="radio"
              name="perspective-mode"
              checked={mode === "compare"}
              disabled={perspectives.length === 0}
              onChange={() => selectMode("compare")}
            />
            <span>
              <strong>多视角并列</strong>
              <small>数据中立与最多 3 个 KOL 分区输出。</small>
            </span>
          </label>
          {mode !== "neutral" && (
            <div className="perspective-options">
              {perspectives.map((perspective) => (
                <label className="skill-option" key={perspective.perspective_id}>
                  <input
                    type={mode === "single" ? "radio" : "checkbox"}
                    name={
                      mode === "single"
                        ? "selected-perspective"
                        : perspective.perspective_id
                    }
                    checked={selected.has(perspective.perspective_id)}
                    disabled={
                      mode === "compare" &&
                      !selected.has(perspective.perspective_id) &&
                      selectedPerspectiveIds.length >= 3
                    }
                    onChange={() => toggle(perspective.perspective_id)}
                  />
                  <span>
                    <strong>{perspective.display_name}</strong>
                    <small>
                      {perspective.article_count} 篇 ·{" "}
                      {perspective.profile_confidence} confidence
                    </small>
                  </span>
                </label>
              ))}
              {perspectives.length === 0 && (
                <p className="skill-menu-empty">
                  暂无 KOL 画像，请先用 perspective init / ingest 建立。
                </p>
              )}
            </div>
          )}
        </div>
      )}
      {mode !== "neutral" && selectedNames.length > 0 && (
        <div className="skill-chips perspective-chips" aria-label="已选视角">
          {selectedNames.map((name, index) => (
            <span className="skill-chip" key={selectedPerspectiveIds[index]}>
              {name}
              {mode === "compare" && selectedPerspectiveIds.length > 1 && (
                <button
                  type="button"
                  aria-label={`移除 ${name}`}
                  disabled={disabled}
                  onClick={() => toggle(selectedPerspectiveIds[index])}
                >
                  <X aria-hidden="true" size={13} />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
