from __future__ import annotations

from intelligence.services import llm_refine


def _clear_provider_env(monkeypatch) -> None:
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
    calls: list[tuple[str, list[dict]]] = []
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
    ):
        del messages, timeout, temperature, tool_choice
        calls.append((provider.name, tools))
        if provider.name == "primary":
            raise OSError("primary unavailable")
        return {"content": "done"}

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: _providers())
    monkeypatch.setattr(llm_refine, "_post_chat_message", fake_post)

    message, provider, reason = llm_refine.chat_with_tools(
        [{"role": "user", "content": "hello"}],
        tools,
        timeout=10,
    )

    assert message == {"content": "done"}
    assert provider is not None
    assert provider.name == "fallback"
    assert reason == ""
    assert calls == [("primary", tools), ("fallback", tools)]


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
