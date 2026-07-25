from __future__ import annotations

from unittest.mock import patch

import pytest

from intelligence.services.keychain_credentials import KeychainCredentialError
from intelligence.services.llm_refine import (
    LLMProvider,
    detect_provider,
    provider_override,
)
from intelligence.services.llm_settings import SessionLLMSettings


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.providers: dict[str, LLMProvider] = {}
        self.deleted: list[str] = []
        self.fail_save = False

    def save(self, user_id: str, provider: LLMProvider) -> None:
        if self.fail_save:
            raise KeychainCredentialError("unable to save Keychain credential")
        self.providers[user_id] = provider

    def load(self, user_id: str) -> LLMProvider | None:
        return self.providers.get(user_id)

    def delete(self, user_id: str) -> None:
        self.deleted.append(user_id)
        self.providers.pop(user_id, None)


def test_session_byok_is_scoped_and_secret_is_not_represented() -> None:
    settings = SessionLLMSettings()
    provider = settings.configure_byok(
        "alice",
        provider_id="zhipu",
        api_key="glm-secret-value",
    )

    assert settings.byok_provider("alice") == provider
    assert settings.byok_provider("bob") is None
    assert provider.model == "glm-5.2"
    assert "glm-secret-value" not in repr(provider)
    description = settings.describe("alice")
    serialized_description = repr(description)
    assert "glm-secret-value" not in serialized_description
    assert provider.base_url not in serialized_description
    assert "api_key" not in description
    assert "base_url" not in description

    settings.clear_byok("alice")
    assert settings.byok_provider("alice") is None


def test_session_byok_accepts_loopback_openai_gateway_without_exposing_url() -> None:
    settings = SessionLLMSettings()

    provider = settings.configure_byok(
        "alice",
        provider_id="openai",
        api_key="openai-secret-value",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )

    assert provider.base_url == "http://localhost:57244/v1"
    assert provider.model == "gpt-5.6-sol"
    description = settings.describe("alice")
    assert "base_url" not in description
    assert "57244" not in repr(description)
    assert "openai-secret-value" not in repr(description)


def test_persisted_byok_reloads_in_a_new_settings_instance() -> None:
    store = MemoryCredentialStore()
    first = SessionLLMSettings(credential_store=store)
    persisted = first.configure_byok(
        "alice",
        provider_id="openai",
        api_key="openai-secret-value",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
        persist=True,
    )

    second = SessionLLMSettings(credential_store=store)
    loaded = second.byok_provider("alice")

    assert loaded == persisted
    description = second.describe("alice")
    assert description["credential_persisted"] is True
    assert description["saved_credential_available"] is True
    assert description["session_only"] is False
    assert "openai-secret-value" not in repr(description)
    assert "57244" not in repr(description)


def test_selecting_built_in_disables_but_does_not_delete_saved_byok() -> None:
    store = MemoryCredentialStore()
    settings = SessionLLMSettings(credential_store=store)
    settings.configure_byok(
        "alice",
        provider_id="openai",
        api_key="openai-secret-value",
        persist=True,
    )

    settings.disable_byok("alice")

    with patch.dict("os.environ", {}, clear=True):
        assert settings.provider_for("alice") is None
        description = settings.describe("alice")
    assert description["mode"] == "built_in"
    assert description["saved_credential_available"] is True
    assert store.deleted == []
    assert SessionLLMSettings(credential_store=store).byok_provider("alice") is not None


def test_forget_saved_byok_deletes_keychain_and_active_session() -> None:
    store = MemoryCredentialStore()
    settings = SessionLLMSettings(credential_store=store)
    settings.configure_byok(
        "alice",
        provider_id="openai",
        api_key="openai-secret-value",
        persist=True,
    )

    settings.forget_saved_byok("alice")

    assert store.deleted == ["alice"]
    assert settings.byok_provider("alice") is None
    assert settings.describe("alice")["saved_credential_available"] is False


def test_persistence_failure_does_not_activate_or_claim_saved_key() -> None:
    store = MemoryCredentialStore()
    store.fail_save = True
    settings = SessionLLMSettings(credential_store=store)

    with pytest.raises(KeychainCredentialError):
        settings.configure_byok(
            "alice",
            provider_id="openai",
            api_key="openai-secret-value",
            persist=True,
        )

    assert settings.byok_provider("alice") is None
    assert settings.describe("alice")["saved_credential_available"] is False


def test_persist_requires_an_enabled_credential_store() -> None:
    settings = SessionLLMSettings(credential_store=None)

    with pytest.raises(KeychainCredentialError, match="unavailable"):
        settings.configure_byok(
            "alice",
            provider_id="openai",
            api_key="openai-secret-value",
            persist=True,
        )


@pytest.mark.parametrize(
    "base_url",
    (
        "http://api.openai.com/v1",
        "ftp://localhost:57244/v1",
        "http://user:pass@localhost:57244/v1",
        "http://localhost:57244/v1?token=secret",
    ),
)
def test_session_byok_rejects_unsafe_custom_base_url(base_url: str) -> None:
    settings = SessionLLMSettings()

    with pytest.raises(ValueError, match="base URL"):
        settings.configure_byok(
            "alice",
            provider_id="openai",
            api_key="openai-secret-value",
            base_url=base_url,
            model="gpt-5.6-sol",
        )


def test_provider_override_is_request_local_and_honors_model_override() -> None:
    provider = LLMProvider(
        name="zhipu",
        api_key="glm-secret-value",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-5.2",
    )

    with patch.dict("os.environ", {}, clear=True):
        assert detect_provider() is None
        with provider_override(provider):
            assert detect_provider() == provider
            overridden = detect_provider("glm-4-air")
            assert overridden is not None
            assert overridden.model == "glm-4-air"
            assert overridden.api_key == "glm-secret-value"
        assert detect_provider() is None


def test_built_in_model_prefers_managed_glm_over_other_environment_keys() -> None:
    settings = SessionLLMSettings()

    with patch.dict(
        "os.environ",
        {
            "DEEPSEEK_API_KEY": "deepseek-secret",
            "ZHIPU_API_KEY": "glm-managed-secret",
            "FORESIGHT_BUILTIN_LLM_MODEL": "glm-4-air",
        },
        clear=True,
    ):
        provider = settings.provider_for("alice")

    assert provider is not None
    assert provider.name == "zhipu"
    assert provider.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert provider.model == "glm-4-air"
    assert provider.api_key == "glm-managed-secret"


def test_managed_glm_uses_coding_plan_endpoint_by_default() -> None:
    settings = SessionLLMSettings()

    with patch.dict(
        "os.environ",
        {"FORESIGHT_BUILTIN_LLM_API_KEY": "coding-plan-secret"},
        clear=True,
    ):
        provider = settings.provider_for("alice")

    assert provider is not None
    assert provider.name == "zhipu"
    assert provider.base_url == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert provider.model == "glm-5.2"
    assert provider.api_key == "coding-plan-secret"


def test_byok_runtime_provider_chain_contains_only_user_provider() -> None:
    settings = SessionLLMSettings()
    byok = settings.configure_byok(
        "alice",
        provider_id="openai",
        api_key="user-secret",
    )

    with patch.dict(
        "os.environ",
        {"FORESIGHT_BUILTIN_LLM_API_KEY": "managed-secret"},
        clear=True,
    ):
        assert settings.runtime_providers_for("alice") == (byok,)


def test_builtin_runtime_provider_chain_preserves_detected_order() -> None:
    settings = SessionLLMSettings()

    with patch.dict(
        "os.environ",
        {
            "ZHIPU_API_KEY": "glm-secret",
            "OPENAI_API_KEY": "openai-secret",
        },
        clear=True,
    ):
        providers = settings.runtime_providers_for("alice")

    assert tuple(provider.name for provider in providers) == ("zhipu", "openai")
