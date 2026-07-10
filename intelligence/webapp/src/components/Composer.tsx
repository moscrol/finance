import { ArrowUp, LoaderCircle } from "lucide-react";
import { FormEvent, KeyboardEvent } from "react";

interface ComposerProps {
  value: string;
  taskType: string;
  disabled?: boolean;
  compact?: boolean;
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
}

export function Composer({
  value,
  taskType,
  disabled = false,
  compact = false,
  onChange,
  onSubmit,
}: ComposerProps) {
  const submit = () => {
    const question = value.trim();
    if (!question || disabled) return;
    onSubmit(question);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
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
      />
      <div className="composer-footer">
        <span>Enter 发送 · Shift + Enter 换行</span>
        <button
          className="primary-icon-button"
          type="submit"
          aria-label={disabled ? "正在创建研究" : "发送研究问题"}
          disabled={disabled || !value.trim()}
        >
          {disabled ? (
            <LoaderCircle className="spin" aria-hidden="true" size={18} />
          ) : (
            <ArrowUp aria-hidden="true" size={18} />
          )}
        </button>
      </div>
    </form>
  );
}
