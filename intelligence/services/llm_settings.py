from __future__ import annotations

import os
from dataclasses import dataclass
import sys
from threading import Lock
from typing import Protocol

from intelligence.services import llm_refine
from intelligence.services.keychain_credentials import (
    KeychainCredentialError,
    KeychainCredentialStore,
    normalize_provider_base_url,
)
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


class CredentialStore(Protocol):
    def save(self, user_id: str, provider: LLMProvider) -> None: ...
    def load(self, user_id: str) -> LLMProvider | None: ...
    def delete(self, user_id: str) -> None: ...


_AUTO_CREDENTIAL_STORE = object()


def _credential_store_from_environment() -> CredentialStore | None:
    enabled = os.environ.get("FORESIGHT_LLM_KEYCHAIN", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None
    if sys.platform != "darwin":
        return None
    try:
        return KeychainCredentialStore()
    except KeychainCredentialError:
        return None


class SessionLLMSettings:
    def __init__(
        self,
        *,
        credential_store: CredentialStore | None | object = _AUTO_CREDENTIAL_STORE,
    ) -> None:
        self._byok: dict[str, LLMProvider] = {}
        self._active_persisted_users: set[str] = set()
        self._saved_users: set[str] = set()
        self._disabled_users: set[str] = set()
        self._credential_store = (
            _credential_store_from_environment()
            if credential_store is _AUTO_CREDENTIAL_STORE
            else credential_store
        )
        self._lock = Lock()

    def configure_byok(
        self,
        user_id: str,
        *,
        provider_id: str,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        persist: bool = False,
    ) -> LLMProvider:
        preset = PROVIDER_PRESETS[provider_id]
        provider = LLMProvider(
            name=provider_id,
            api_key=api_key,
            base_url=normalize_provider_base_url(base_url or preset.base_url),
            model=model or preset.default_model,
        )
        if persist:
            store = self._credential_store
            if store is None:
                raise KeychainCredentialError("Keychain persistence unavailable")
            store.save(user_id, provider)
        with self._lock:
            self._byok[user_id] = provider
            self._disabled_users.discard(user_id)
            if persist:
                self._active_persisted_users.add(user_id)
                self._saved_users.add(user_id)
            else:
                self._active_persisted_users.discard(user_id)
        return provider

    def byok_provider(self, user_id: str) -> LLMProvider | None:
        with self._lock:
            if user_id in self._disabled_users:
                return None
            provider = self._byok.get(user_id)
        if provider is not None:
            return provider
        store = self._credential_store
        if store is None:
            return None
        try:
            provider = store.load(user_id)
        except KeychainCredentialError:
            return None
        if provider is None:
            return None
        with self._lock:
            if user_id in self._disabled_users:
                return None
            self._byok[user_id] = provider
            self._active_persisted_users.add(user_id)
            self._saved_users.add(user_id)
        return provider

    def clear_byok(self, user_id: str) -> None:
        self.disable_byok(user_id)

    def disable_byok(self, user_id: str) -> None:
        with self._lock:
            self._byok.pop(user_id, None)
            self._active_persisted_users.discard(user_id)
            self._disabled_users.add(user_id)

    def forget_saved_byok(self, user_id: str) -> None:
        store = self._credential_store
        if store is not None:
            store.delete(user_id)
        with self._lock:
            self._byok.pop(user_id, None)
            self._active_persisted_users.discard(user_id)
            self._saved_users.discard(user_id)
            self._disabled_users.add(user_id)

    def clear_all(self) -> None:
        with self._lock:
            self._disabled_users.update(self._saved_users)
            self._byok.clear()
            self._active_persisted_users.clear()

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
        with self._lock:
            credential_persisted = (
                byok is not None and user_id in self._active_persisted_users
            )
            saved_credential_available = user_id in self._saved_users
        return {
            "mode": "byok" if byok is not None else "built_in",
            "display_name": (
                "已保存模型"
                if credential_persisted
                else ("自带密钥" if byok is not None else "Foresight 默认模型")
            ),
            "ready": active is not None,
            "session_only": byok is not None and not credential_persisted,
            "built_in_ready": built_in is not None,
            "provider": active.name if active is not None else None,
            "model": active.model if active is not None else None,
            "credential_persisted": credential_persisted,
            "saved_credential_available": saved_credential_available,
        }
