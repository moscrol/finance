from __future__ import annotations

from intelligence.services import llm_refine


def _clear_provider_env(monkeypatch) -> None:
    for env_key in (
        "FORESIGHT_BUILTIN_LLM_API_KEY",
        "FORESIGHT_BUILTIN_LLM_BASE_URL",
        "FORESIGHT_BUILTIN_LLM_MODEL",
    ):
        monkeypatch.delenv(env_key, raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    for _name, env_key, _base, _model in llm_refine._PROVIDERS:
        monkeypatch.delenv(env_key, raising=False)


def test_detect_providers_preserves_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-environment-value")
    configured = llm_refine.LLMProvider(
        name="explicit",
        api_key="test-override-value",
        base_url="https://override.example/v1",
        model="override-model",
    )

    with llm_refine.provider_override(configured):
        providers = llm_refine.detect_providers("requested-model")

    assert len(providers) == 1
    assert providers[0].name == "explicit"
    assert providers[0].model == "requested-model"


def test_generic_provider_keeps_priority_over_provider_specific_keys(
    monkeypatch,
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "test-generic-value")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-value")

    providers = llm_refine.detect_providers()

    assert [provider.name for provider in providers] == ["custom"]


def test_provider_specific_keys_use_deterministic_order(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-moonshot-value")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-value")

    providers = llm_refine.detect_providers()

    assert [provider.name for provider in providers] == ["deepseek", "moonshot"]


def test_managed_builtin_provider_precedes_provider_specific_keys(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_API_KEY", "test-managed-value")
    monkeypatch.setenv(
        "FORESIGHT_BUILTIN_LLM_BASE_URL",
        "https://managed.example/v1",
    )
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_MODEL", "managed-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-value")

    providers = llm_refine.detect_providers()

    assert [provider.name for provider in providers] == ["zhipu", "deepseek"]
    assert providers[0].api_key == "test-managed-value"
    assert providers[0].base_url == "https://managed.example/v1"
    assert providers[0].model == "managed-model"

    overridden = llm_refine.detect_providers("requested-model")

    assert overridden[0].model == "requested-model"


def _providers() -> tuple[llm_refine.LLMProvider, ...]:
    return (
        llm_refine.LLMProvider(
            name="primary",
            api_key="test-primary-value",
            base_url="https://primary.example/v1",
            model="primary-model",
        ),
        llm_refine.LLMProvider(
            name="fallback",
            api_key="test-fallback-value",
            base_url="https://fallback.example/v1",
            model="fallback-model",
        ),
    )


def test_complete_falls_back_to_next_configured_provider(monkeypatch) -> None:
    calls: list[str] = []

    def fake_post(provider, messages, timeout, temperature):
        del messages, timeout, temperature
        calls.append(provider.name)
        if provider.name == "primary":
            raise OSError("primary unavailable")
        return "fallback answer"

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: _providers())
    monkeypatch.setattr(llm_refine, "_post_chat", fake_post)

    content, provider, reason = llm_refine.complete(
        [{"role": "user", "content": "hello"}],
        timeout=10,
    )

    assert content == "fallback answer"
    assert provider is not None
    assert provider.name == "fallback"
    assert reason == ""
    assert calls == ["primary", "fallback"]


def test_tool_chat_falls_back_without_losing_tool_contract(monkeypatch) -> None:
    calls: list[tuple[str, list[dict], bool | None]] = []
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "search",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    def fake_post(
        provider,
        messages,
        timeout,
        temperature,
        *,
        tools,
        tool_choice,
        disable_thinking,
    ):
        del messages, timeout, temperature, tool_choice
        calls.append((provider.name, tools, disable_thinking))
        if provider.name == "primary":
            raise OSError("primary unavailable")
        return {"content": "done"}

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: _providers())
    monkeypatch.setattr(llm_refine, "_post_chat_message", fake_post)

    message, provider, reason = llm_refine.chat_with_tools(
        [{"role": "user", "content": "hello"}],
        tools,
        timeout=10,
        disable_thinking=True,
    )

    assert message == {"content": "done"}
    assert provider is not None
    assert provider.name == "fallback"
    assert reason == ""
    assert calls == [
        ("primary", tools, True),
        ("fallback", tools, True),
    ]


def test_all_provider_failures_are_normalized_without_credentials(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: _providers())
    monkeypatch.setattr(
        llm_refine,
        "_post_chat",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("private diagnostic must not leak")
        ),
    )

    content, provider, reason = llm_refine.complete(
        [{"role": "user", "content": "hello"}],
        timeout=10,
    )

    assert content is None
    assert provider is not None
    assert provider.name == "fallback"
    assert "primary" in reason
    assert "fallback" in reason
    assert "private diagnostic" not in reason
    assert all(item.api_key not in reason for item in _providers())


def _clear_judge_env(monkeypatch) -> None:
    for env_key in (
        "LLM_JUDGE_BACKEND",
        "LLM_JUDGE_GROK_BIN",
        "LLM_JUDGE_API_KEY",
        "LLM_JUDGE_BASE_URL",
        "LLM_JUDGE_MODEL",
        "LLM_JUDGE_FALLBACK_API_KEY",
        "LLM_JUDGE_FALLBACK_BASE_URL",
        "LLM_JUDGE_FALLBACK_MODEL",
    ):
        monkeypatch.delenv(env_key, raising=False)


def test_judge_provider_chain_appends_explicit_fallback(monkeypatch) -> None:
    """R-20260829-03：grok-cli 主 + 显式备胎词表 → 两级链，主判官解析不变。"""

    _clear_provider_env(monkeypatch)
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    monkeypatch.setenv("LLM_JUDGE_MODEL", "grok-4.6")
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_API_KEY", "test-fallback-key")
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_BASE_URL", "https://relay.invalid/v1")
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_MODEL", "gpt-5.6-sol")
    chain = llm_refine.judge_provider_chain()
    assert [item.name for item in chain] == ["grok-cli-judge", "judge-fallback"]
    assert chain[0].transport == "cli" and chain[0].model == "grok-4.6"
    assert chain[1].base_url == "https://relay.invalid/v1"
    assert chain[1].model == "gpt-5.6-sol"
    assert chain[0] == llm_refine.judge_provider(), "链首必须与单主解析全等"


def test_judge_provider_chain_without_fallback_stays_single(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("LLM_JUDGE_API_KEY", "test-judge-key")
    chain = llm_refine.judge_provider_chain()
    assert [item.name for item in chain] == ["judge"]


def test_judge_provider_chain_requires_primary(monkeypatch) -> None:
    """只配备胎不配主判官 = 未接线：空链，调用方保持原有回落。"""

    _clear_provider_env(monkeypatch)
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_API_KEY", "test-fallback-key")
    assert llm_refine.judge_provider_chain() == ()


def test_judge_provider_chain_dedupes_identical_fallback(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("LLM_JUDGE_API_KEY", "test-judge-key")
    monkeypatch.setenv("LLM_JUDGE_BASE_URL", "https://same.invalid/v1")
    monkeypatch.setenv("LLM_JUDGE_MODEL", "same-model")
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_API_KEY", "another-key")
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_BASE_URL", "https://same.invalid/v1")
    monkeypatch.setenv("LLM_JUDGE_FALLBACK_MODEL", "same-model")
    assert [item.name for item in llm_refine.judge_provider_chain()] == ["judge"]


def test_judge_provider_chain_never_auto_adds_composer(monkeypatch) -> None:
    """红线：合成主链 provider 永不自动进判官链（不静默退回相关自审）。"""

    _clear_provider_env(monkeypatch)
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-composer-key")
    assert llm_refine.judge_provider_chain() == ()
