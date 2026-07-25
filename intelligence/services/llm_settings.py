from __future__ import annotations

import os
from dataclasses import dataclass
import ipaddress
from threading import Lock
from urllib.parse import urlsplit, urlunsplit

from intelligence.services import llm_refine
from intelligence.services.llm_refine import LLMProvider, detect_provider


@dataclass(frozen=True)
class ProviderPreset:
    provider_id: str
    base_url: str
    default_model: str


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "zhipu": ProviderPreset(
        provider_id="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-5.2",
    ),
    "openai": ProviderPreset(
        provider_id="openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
    ),
    "deepseek": ProviderPreset(
        provider_id="deepseek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
    ),
    "moonshot": ProviderPreset(
        provider_id="moonshot",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
    ),
    "dashscope": ProviderPreset(
        provider_id="dashscope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
    ),
}


def normalize_provider_base_url(value: str) -> str:
    """Validate a user-selected model endpoint without retaining URL secrets."""

    cleaned = str(value or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("provider base URL must not be blank")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("provider base URL must use http or https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("provider base URL must not contain credentials or query data")
    if parsed.scheme == "http":
        host = parsed.hostname.lower()
        is_loopback = host == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                is_loopback = False
        if not is_loopback:
            raise ValueError("provider base URL requires https outside loopback")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("provider base URL has an invalid port") from exc
    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))


class SessionLLMSettings:
    def __init__(self) -> None:
        self._byok: dict[str, LLMProvider] = {}
        self._lock = Lock()

    def configure_byok(
        self,
        user_id: str,
        *,
        provider_id: str,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
    ) -> LLMProvider:
        preset = PROVIDER_PRESETS[provider_id]
        provider = LLMProvider(
            name=provider_id,
            api_key=api_key,
            base_url=normalize_provider_base_url(base_url or preset.base_url),
            model=model or preset.default_model,
        )
        with self._lock:
            self._byok[user_id] = provider
        return provider

    def byok_provider(self, user_id: str) -> LLMProvider | None:
        with self._lock:
            return self._byok.get(user_id)

    def clear_byok(self, user_id: str) -> None:
        with self._lock:
            self._byok.pop(user_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._byok.clear()

    def built_in_provider(self) -> LLMProvider | None:
        managed_glm_key = os.environ.get("FORESIGHT_BUILTIN_LLM_API_KEY")
        glm_key = (
            managed_glm_key
            or os.environ.get("ZHIPU_API_KEY")
            or os.environ.get("GLM_API_KEY")
        )
        if glm_key:
            return LLMProvider(
                name="zhipu",
                api_key=glm_key,
                base_url=os.environ.get("FORESIGHT_BUILTIN_LLM_BASE_URL")
                or (
                    "https://open.bigmodel.cn/api/coding/paas/v4"
                    if managed_glm_key
                    else "https://open.bigmodel.cn/api/paas/v4"
                ),
                model=os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL")
                or "glm-5.2",
            )
        return detect_provider()

    def provider_for(self, user_id: str) -> LLMProvider | None:
        return self.byok_provider(user_id) or self.built_in_provider()

    def runtime_providers_for(self, user_id: str) -> tuple[LLMProvider, ...]:
        """Return the provider chain owned by the current session.

        A session-scoped BYOK (bring your own key) provider is intentionally a
        singleton chain: adding a server-managed provider would silently mix
        credentials and violate the user's explicit provider choice.  Built-in
        mode delegates to ``llm_refine.detect_providers`` so its deterministic
        environment order remains the single source of truth.
        """

        byok = self.byok_provider(user_id)
        if byok is not None:
            return (byok,)
        return llm_refine.detect_providers()

    def describe(self, user_id: str) -> dict[str, object]:
        byok = self.byok_provider(user_id)
        built_in = self.built_in_provider()
        active = byok or built_in
        return {
            "mode": "byok" if byok is not None else "built_in",
            "display_name": "自带密钥" if byok is not None else "Foresight 默认模型",
            "ready": active is not None,
            "session_only": byok is not None,
            "built_in_ready": built_in is not None,
            "provider": active.name if active is not None else None,
            "model": active.model if active is not None else None,
        }
