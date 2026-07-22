from __future__ import annotations

from unittest.mock import patch

from intelligence.services.llm_refine import (
    LLMProvider,
    detect_provider,
    provider_override,
)
from intelligence.services.llm_settings import SessionLLMSettings


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
