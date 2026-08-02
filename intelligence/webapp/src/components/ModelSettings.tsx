import {
  BrainCircuit,
  CheckCircle2,
  KeyRound,
  ShieldCheck,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import type {
  LLMConfig,
  LLMProviderId,
} from "../types";

const providerOptions: Array<{
  id: LLMProviderId;
  label: string;
  model: string;
  baseUrl: string;
}> = [
  { id: "zhipu", label: "智谱 GLM", model: "glm-5.2", baseUrl: "https://open.bigmodel.cn/api/paas/v4" },
  { id: "openai", label: "OpenAI", model: "gpt-5.6-sol", baseUrl: "https://api.openai.com/v1" },
  { id: "deepseek", label: "DeepSeek", model: "deepseek-chat", baseUrl: "https://api.deepseek.com/v1" },
  { id: "moonshot", label: "Kimi", model: "moonshot-v1-8k", baseUrl: "https://api.moonshot.cn/v1" },
  { id: "dashscope", label: "通义千问", model: "qwen-plus", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
];

interface ModelSettingsProps {
  open: boolean;
  config: LLMConfig | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (
    provider: LLMProviderId,
    apiKey: string,
    baseUrl: string,
    model: string,
    remember: boolean,
  ) => void;
  onUseBuiltIn: () => void;
  onForgetSaved: () => void;
}

export function ModelSettings({
  open,
  config,
  saving,
  error,
  onClose,
  onSave,
  onUseBuiltIn,
  onForgetSaved,
}: ModelSettingsProps) {
  const [provider, setProvider] = useState<LLMProviderId>("zhipu");
  const [model, setModel] = useState("glm-5.2");
  const [baseUrl, setBaseUrl] = useState(providerOptions[0].baseUrl);
  const [apiKey, setApiKey] = useState("");
  const [remember, setRemember] = useState(false);

  useEffect(() => {
    if (!open) return;
    const nextProvider = config?.mode === "byok" && config.provider
      ? config.provider
      : "zhipu";
    const preset = providerOptions.find((item) => item.id === nextProvider);
    setProvider(nextProvider);
    setModel(config?.mode === "byok" && config.model
      ? config.model
      : preset?.model ?? "");
    setBaseUrl(preset?.baseUrl ?? "");
    setApiKey("");
    setRemember(false);
  }, [config, open]);

  if (!open) return null;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSave(provider, apiKey.trim(), baseUrl.trim(), model.trim(), remember);
  };

  return (
    <div className="model-settings-backdrop">
      <section
        className="model-settings"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-settings-title"
      >
        <header className="model-settings-header">
          <div>
            <span className="eyebrow">MODEL</span>
            <h2 id="model-settings-title">模型连接</h2>
            <p>默认开箱即用，也可以临时接入自己的模型密钥。</p>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭模型设置"
            onClick={onClose}
          >
            <X aria-hidden="true" size={18} />
          </button>
        </header>

        <div className="model-choice-grid">
          <button
            className={`model-choice ${config?.mode !== "byok" ? "active" : ""}`}
            type="button"
            onClick={onUseBuiltIn}
            disabled={saving}
          >
            <span className="model-choice-icon" aria-hidden="true">
              <BrainCircuit size={20} />
            </span>
            <span>
              <strong>Foresight 默认模型</strong>
              <small>无需配置，由 Foresight 托管</small>
            </span>
            <span
              className={`model-readiness ${
                config?.built_in_ready ? "ready" : "pending"
              }`}
            >
              {config?.built_in_ready ? "可用" : "待配置"}
            </span>
          </button>

          <div className={`model-choice byok ${config?.mode === "byok" ? "active" : ""}`}>
            <span className="model-choice-icon" aria-hidden="true">
              <KeyRound size={20} />
            </span>
            <span>
              <strong>自带密钥</strong>
              <small>使用你的 Provider 与用量额度</small>
            </span>
            {config?.mode === "byok" && (
              <CheckCircle2 className="model-choice-check" aria-label="当前启用" size={17} />
            )}
          </div>
        </div>

        <form className="byok-form" onSubmit={submit}>
          <div className="byok-form-heading">
            <div>
              <strong>配置自带密钥</strong>
              <small>支持 OpenAI-compatible Chat Completions</small>
            </div>
            <span className="session-only-badge">
              {config?.credential_persisted ? "已安全保存" : "仅本次服务会话"}
            </span>
          </div>
          <div className="byok-fields">
            <label>
              <span>Provider</span>
              <select
                aria-label="选择模型服务商"
                value={provider}
                onChange={(event) => {
                  const next = event.target.value as LLMProviderId;
                  const preset = providerOptions.find((item) => item.id === next);
                  setProvider(next);
                  setModel(preset?.model ?? "");
                  setBaseUrl(preset?.baseUrl ?? "");
                }}
              >
                {providerOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Model</span>
              <input
                aria-label="模型名称"
                value={model}
                maxLength={128}
                onChange={(event) => setModel(event.target.value)}
                placeholder="glm-5.2"
                required
              />
            </label>
            <label className="byok-url-field">
              <span>Base URL</span>
              <input
                aria-label="模型 Base URL"
                type="url"
                value={baseUrl}
                maxLength={2048}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="https://api.openai.com/v1"
                required
              />
            </label>
            <label className="byok-key-field">
              <span>API Key</span>
              <input
                aria-label="模型 API Key"
                type="password"
                value={apiKey}
                minLength={8}
                maxLength={4096}
                autoComplete="new-password"
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="仅在内存中使用"
                required
              />
            </label>
          </div>
          <label className="byok-remember-control">
            <input
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
            />
            <span>
              <strong>在此 Mac 安全记住</strong>
              <small>保存到 macOS Keychain，服务重启后自动复用</small>
            </span>
          </label>
          <div className="byok-security-note">
            <ShieldCheck aria-hidden="true" size={16} />
            <span>
              {remember
                ? "密钥仅写入 macOS Keychain，不进入对话、日志或研究产物。"
                : "密钥只在当前服务内存中使用，重启后自动清除。"}
            </span>
          </div>
          {config?.saved_credential_available && (
            <div className="saved-credential-row">
              <span>此 Mac 已保存一个模型连接。</span>
              <button
                type="button"
                onClick={onForgetSaved}
                disabled={saving}
              >
                删除已保存密钥
              </button>
            </div>
          )}
          {error && <p className="model-settings-error" role="alert">{error}</p>}
          <footer className="model-settings-actions">
            <button className="secondary-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? "正在连接…" : "使用自带密钥"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
