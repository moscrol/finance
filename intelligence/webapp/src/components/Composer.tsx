import { ArrowUp, LoaderCircle, StopCircle } from "lucide-react";
import { FormEvent, KeyboardEvent, useRef } from "react";
import type {
  PerspectiveDescription,
  PerspectiveMode,
  ProductSkillDescription,
  SkillMode,
} from "../types";
import { PerspectivePicker } from "./PerspectivePicker";
import { SkillPicker } from "./SkillPicker";

interface ComposerProps {
  value: string;
  taskType: string;
  disabled?: boolean;
  compact?: boolean;
  running?: boolean;
  stopRequested?: boolean;
  skills?: ProductSkillDescription[];
  perspectives?: PerspectiveDescription[];
  skillMode?: SkillMode;
  selectedSkillIds?: string[];
  perspectiveMode?: PerspectiveMode;
  selectedPerspectiveIds?: string[];
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
  onStop?: () => void;
  onSkillModeChange?: (mode: SkillMode) => void;
  onSkillSelectionChange?: (skillIds: string[]) => void;
  onPerspectiveModeChange?: (mode: PerspectiveMode) => void;
  onPerspectiveSelectionChange?: (perspectiveIds: string[]) => void;
}

// Safari 在输入法上屏时先派发 compositionend，再派发一个 isComposing=false 的
// Enter keydown；两者来自同一次物理按键，间隔远小于人手连按两次回车的间隔。
const IME_COMMIT_GRACE_MS = 50;

export function Composer({
  value,
  taskType,
  disabled = false,
  compact = false,
  running = false,
  stopRequested = false,
  skills = [],
  perspectives = [],
  skillMode = "hybrid",
  selectedSkillIds = [],
  perspectiveMode = "neutral",
  selectedPerspectiveIds = [],
  onChange,
  onSubmit,
  onStop,
  onSkillModeChange,
  onSkillSelectionChange,
  onPerspectiveModeChange,
  onPerspectiveSelectionChange,
}: ComposerProps) {
  const submit = () => {
    const question = value.trim();
    if (!question || disabled || running) return;
    onSubmit(question);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  const composingRef = useRef(false);
  const compositionEndedAtRef = useRef(0);

  const handleCompositionStart = () => {
    composingRef.current = true;
  };

  const handleCompositionEnd = () => {
    composingRef.current = false;
    compositionEndedAtRef.current = performance.now();
  };

  const isImeEnter = (event: KeyboardEvent<HTMLTextAreaElement>) =>
    event.nativeEvent.isComposing ||
    event.nativeEvent.keyCode === 229 ||
    composingRef.current ||
    performance.now() - compositionEndedAtRef.current < IME_COMMIT_GRACE_MS;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    // 中文输入法：候选词未上屏时按回车，浏览器同样派发 key === "Enter" 的 keydown，
    // 这一下是交给输入法的，不能当作发送。
    if (isImeEnter(event)) return;
    event.preventDefault();
    submit();
  };

  return (
    <form
      className={`composer ${compact ? "composer-compact" : ""}`}
      onSubmit={handleSubmit}
      aria-label="研究提问"
    >
      <label className="sr-only" htmlFor={compact ? "followup-composer" : "research-composer"}>
        输入研究问题
      </label>
      <textarea
        id={compact ? "followup-composer" : "research-composer"}
        value={value}
        rows={compact ? 2 : 4}
        placeholder={
          taskType === "ask"
            ? "输入问题，说明对象、时间和想验证的判断…"
            : "补充研究对象或约束后开始…"
        }
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        onCompositionStart={handleCompositionStart}
        onCompositionEnd={handleCompositionEnd}
      />
      <div className="composer-footer">
        <div className="composer-tools">
          {skills.length > 0 &&
            onSkillModeChange &&
            onSkillSelectionChange && (
              <SkillPicker
                skills={skills}
                mode={skillMode}
                selectedSkillIds={selectedSkillIds}
                disabled={disabled || running}
                onModeChange={onSkillModeChange}
                onSelectionChange={onSkillSelectionChange}
              />
            )}
          {onPerspectiveModeChange && onPerspectiveSelectionChange && (
            <PerspectivePicker
              perspectives={perspectives}
              mode={perspectiveMode}
              selectedPerspectiveIds={selectedPerspectiveIds}
              disabled={disabled || running}
              onModeChange={onPerspectiveModeChange}
              onSelectionChange={onPerspectiveSelectionChange}
            />
          )}
          <span className="composer-shortcut">
            Enter 发送 · Shift + Enter 换行
          </span>
        </div>
        {running && onStop ? (
          <button
            className="stop-generation-button"
            type="button"
            aria-label={stopRequested ? "停止请求已提交" : "停止生成"}
            title={stopRequested ? "停止请求已提交" : "停止生成"}
            disabled={stopRequested}
            onClick={onStop}
          >
            <StopCircle aria-hidden="true" size={17} />
            {stopRequested ? "停止请求已提交" : "停止"}
          </button>
        ) : (
          <button
            className="primary-icon-button"
            type="submit"
            aria-label={disabled ? "正在创建研究" : "发送研究问题"}
            title="Enter 发送 · Shift + Enter 换行"
            disabled={disabled || !value.trim()}
          >
            {disabled ? (
              <LoaderCircle className="spin" aria-hidden="true" size={18} />
            ) : (
              <ArrowUp aria-hidden="true" size={18} />
            )}
          </button>
        )}
      </div>
    </form>
  );
}
