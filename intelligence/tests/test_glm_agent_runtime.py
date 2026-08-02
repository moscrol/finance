from __future__ import annotations

import json
import threading

import pytest

from intelligence.services import llm_refine
from intelligence.services.glm_agent_runtime import (
    GLMAgentRuntime,
    GLMModelClient,
)
from intelligence.services.episode_finalizer import EpisodeFinalizer
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


def _provider(name: str) -> LLMProvider:
    return LLMProvider(
        name=name,
        api_key=f"{name}-secret",
        base_url=f"https://{name}.example.invalid/v1",
        model=f"{name}-model",
    )


def _provider_script(**responses):
    calls: list[str] = []

    def complete_fn(**kwargs):
        provider = llm_refine.detect_provider()
        name = provider.name if provider is not None else ""
        calls.append(name)
        message, reason = responses[name]
        return message, provider, reason

    complete_fn.calls = calls
    return complete_fn


def test_runtime_accepts_one_shared_client_and_finalizer() -> None:
    client = GLMModelClient(providers=())
    finalizer = EpisodeFinalizer(client)

    runtime = GLMAgentRuntime(
        client=client,
        finalizer=finalizer,
    )

    assert runtime._episode._model is client
    assert runtime._episode._finalizer is finalizer


def test_runtime_falls_through_transient_primary_failure_and_counts_attempts() -> None:
    client = GLMModelClient(
        providers=(_provider("glm"), _provider("openai")),
        complete_fn=_provider_script(
            glm=(None, "TimeoutError"),
            openai=({"content": "ok", "tool_calls": []}, ""),
        ),
    )

    turn = client.complete(
        messages=[{"role": "user", "content": "q"}],
        tools=[],
        timeout=5,
    )

    assert turn.provider_name == "openai"
    assert turn.provider_attempts == 2
    assert turn.content == "ok"


def test_glm_adapter_preserves_provider_usage_without_prompt_payload() -> None:
    client = GLMModelClient(
        providers=(_provider("glm"),),
        complete_fn=lambda **_kwargs: (
            {
                "content": "ok",
                "tool_calls": [],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 35,
                },
            },
            _provider("glm"),
            "",
        ),
    )

    turn = client.complete(messages=[], tools=[], timeout=5)

    assert turn.input_tokens == 120
    assert turn.output_tokens == 35
    assert "usage" not in turn.to_dict()


def test_runtime_does_not_retry_same_provider_after_auth_failure() -> None:
    complete_fn = _provider_script(
        glm=(None, "LLM 调用 HTTP 401"),
        openai=({"content": "ok", "tool_calls": []}, ""),
    )
    client = GLMModelClient(
        providers=(_provider("glm"), _provider("openai")),
        complete_fn=complete_fn,
    )

    turn = client.complete(messages=[], tools=[], timeout=5)

    assert turn.provider_name == "openai"
    assert turn.provider_attempts == 2
    assert complete_fn.calls == ["glm", "openai"]


def test_runtime_cancellation_stops_before_fallback_provider() -> None:
    cancelled = threading.Event()
    calls: list[str] = []

    def complete_fn(**kwargs):
        del kwargs
        provider = llm_refine.detect_provider()
        assert provider is not None
        calls.append(provider.name)
        cancelled.set()
        return None, provider, "TimeoutError"

    turn = GLMModelClient(
        providers=(_provider("glm"), _provider("openai")),
        complete_fn=complete_fn,
        is_cancelled=cancelled.is_set,
    ).complete(messages=[], tools=[], timeout=5)

    assert calls == ["glm"]
    assert turn.provider_attempts == 1
    assert turn.error == "cancelled"


def test_agent_runtime_propagates_cancellation_to_provider_chain() -> None:
    cancelled = threading.Event()
    calls: list[str] = []

    def complete_fn(**kwargs):
        del kwargs
        provider = llm_refine.detect_provider()
        assert provider is not None
        calls.append(provider.name)
        cancelled.set()
        return None, provider, "TimeoutError"

    frame = TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )
    contract = ResearchTaskContract(
        task_id="runtime-cancel-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(RequiredOutput("direct_assessment", "直接判断", (), True),),
        allowed_capabilities=(),
        research_tier="quick",
        task_frame_hash=frame.task_frame_hash,
    )
    context = ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(5.0),
        policy=ResearchPolicy("quick", 1, 5.0, 0.0),
        trace_parent_id="runtime-cancel-test",
    )
    runtime = GLMAgentRuntime(
        providers=(_provider("glm"), _provider("openai")),
        complete_fn=complete_fn,
        is_cancelled=cancelled.is_set,
    )

    outcome = runtime.run(
        task_frame=frame,
        context=context,
        registry=ResearchToolRegistry(()),
    )

    assert calls == ["glm"]
    assert outcome.stop_reason == "cancelled"
    assert outcome.usage.llm_calls == 1


def test_runtime_forwards_one_turn_settings_to_each_provider() -> None:
    providers = (_provider("glm"), _provider("openai"))
    messages = [{"role": "user", "content": "q"}]
    tools = [{"type": "function", "function": {"name": "lookup"}}]
    calls: list[tuple[str, dict[str, object]]] = []

    def complete_fn(**kwargs):
        provider = llm_refine.detect_provider()
        assert provider is not None
        calls.append((provider.name, kwargs))
        if provider.name == "glm":
            return None, provider, "TimeoutError"
        return {"content": "ok", "tool_calls": []}, provider, ""

    turn = GLMModelClient(
        model="shared-model",
        providers=providers,
        complete_fn=complete_fn,
    ).complete(messages=messages, tools=tools, timeout=5)

    assert turn.content == "ok"
    assert turn.provider_attempts == 2
    assert [provider for provider, _ in calls] == ["glm", "openai"]
    first = calls[0][1]
    second = calls[1][1]
    assert first["messages"] is second["messages"] is messages
    assert first["tools"] is second["tools"] is tools
    for key in ("model_override", "temperature", "tool_choice", "disable_thinking"):
        assert first[key] == second[key]
    assert first["model_override"] == "shared-model"
    assert first["temperature"] == 0.0
    assert first["tool_choice"] == "auto"
    assert first["disable_thinking"] is True
    assert 0.0 < second["timeout"] <= first["timeout"] <= 5
    assert [entry["status"] for entry in turn._provider_trace] == [
        "failed",
        "success",
    ]


def test_real_adapter_without_explicit_providers_uses_one_explicit_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = (_provider("glm"), _provider("openai"))
    calls: list[str] = []

    def complete_fn(**kwargs):
        del kwargs
        configured = llm_refine.detect_providers()
        for provider in configured:
            calls.append(provider.name)
            if provider.name == "glm":
                continue
            return {"content": "ok", "tool_calls": []}, provider, ""
        return None, configured[0] if configured else None, "TimeoutError"

    monkeypatch.setattr(llm_refine, "chat_with_tools", complete_fn)

    def detect_providers(_model=None):
        overridden = llm_refine._PROVIDER_OVERRIDE.get()
        return (overridden,) if overridden is not None else providers

    monkeypatch.setattr(
        llm_refine,
        "detect_providers",
        detect_providers,
    )

    turn = GLMModelClient().complete(messages=[], tools=[], timeout=5)

    assert turn.content == "ok"
    assert turn.provider_name == "openai"
    assert turn.provider_attempts == 2
    assert calls == ["glm", "openai"]
    assert [entry["provider"] for entry in turn._provider_trace] == calls


def test_real_default_single_provider_keeps_legacy_transient_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider("glm")
    calls: list[str] = []

    def complete_fn(**kwargs):
        del kwargs
        selected = llm_refine.detect_provider()
        assert selected is not None
        calls.append(selected.name)
        if len(calls) == 1:
            return None, selected, "TimeoutError"
        return {"content": "ok", "tool_calls": []}, selected, ""

    monkeypatch.setattr(llm_refine, "chat_with_tools", complete_fn)

    def detect_providers(_model=None):
        overridden = llm_refine._PROVIDER_OVERRIDE.get()
        return (overridden,) if overridden is not None else (provider,)

    monkeypatch.setattr(llm_refine, "detect_providers", detect_providers)

    turn = GLMModelClient().complete(messages=[], tools=[], timeout=5)

    assert calls == ["glm", "glm"]
    assert turn.content == "ok"
    assert turn.provider_attempts == 2
    assert [entry["status"] for entry in turn._provider_trace] == [
        "failed",
        "success",
    ]


def test_explicit_single_provider_does_not_retry_transient_failure() -> None:
    provider = _provider("glm")
    calls = 0

    def complete_fn(**_kwargs):
        nonlocal calls
        calls += 1
        return None, provider, "TimeoutError"

    turn = GLMModelClient(
        providers=(provider,),
        complete_fn=complete_fn,
    ).complete(messages=[], tools=[], timeout=5)

    assert calls == 1
    assert turn.provider_attempts == 1
    assert [entry["status"] for entry in turn._provider_trace] == ["failed"]


def test_legacy_invalid_envelope_is_recorded_as_failed_trace() -> None:
    provider = _provider("glm")
    turn = GLMModelClient(
        complete_fn=lambda **_kwargs: (
            {"content": "invalid", "tool_calls": 0},
            provider,
            "",
        )
    ).complete(messages=[], tools=[], timeout=5)

    assert turn.error == "invalid_tool_calls"
    assert turn.provider_attempts == 1
    assert turn._provider_trace == (
        {
            "provider": "glm",
            "status": "failed",
            "reason": "invalid_tool_calls",
        },
    )


def test_provider_trace_is_scoped_to_each_concurrent_complete() -> None:
    providers = (_provider("glm"), _provider("openai"))
    synchronized_returns = threading.Barrier(2)
    client = GLMModelClient(
        providers=providers,
        complete_fn=lambda **_kwargs: (
            None,
            llm_refine.detect_provider(),
            f"TimeoutError:{threading.current_thread().name}",
        )
        if llm_refine.detect_provider().name == "glm"
        else (
            {
                "content": threading.current_thread().name,
                "tool_calls": [],
            },
            llm_refine.detect_provider(),
            "",
        ),
    )
    original_with_trace = client._with_provider_trace

    def synchronized_with_trace(turn, trace):
        synchronized_returns.wait(timeout=5)
        return original_with_trace(turn, trace)

    client._with_provider_trace = synchronized_with_trace
    results: dict[str, object] = {}
    errors: list[BaseException] = []

    def run() -> None:
        tag = threading.current_thread().name
        try:
            results[tag] = client.complete(messages=[], tools=[], timeout=5)
        except BaseException as exc:  # pragma: no cover - assertion below
            errors.append(exc)

    threads = [
        threading.Thread(target=run, name="turn-a"),
        threading.Thread(target=run, name="turn-b"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert set(results) == {"turn-a", "turn-b"}
    for tag, raw_turn in results.items():
        turn = raw_turn
        assert turn.content == tag
        assert turn.provider_attempts == 2
        assert turn._provider_trace[0]["reason"] == f"TimeoutError:{tag}"
        assert turn._provider_trace[1]["provider"] == "openai"


@pytest.mark.parametrize("timeout", (0.0, 0.001))
def test_runtime_deadline_before_first_provider_records_zero_attempts(
    timeout: float,
) -> None:
    calls = 0

    def complete_fn(**_kwargs):
        nonlocal calls
        calls += 1
        return {"content": "unexpected", "tool_calls": []}, _provider("glm"), ""

    turn = GLMModelClient(
        providers=(_provider("glm"),),
        complete_fn=complete_fn,
    ).complete(messages=[], tools=[], timeout=timeout)

    assert turn.provider_attempts == 0
    assert calls == 0


def test_runtime_budget_rejection_before_first_http_records_zero_attempts() -> None:
    provider = _provider("glm")
    client = GLMModelClient(
        providers=(provider,),
        complete_fn=lambda **_kwargs: (
            None,
            None,
            "LLM 调用预算耗尽（本轮上限 0 次尝试），已拒发新调用并降级",
        ),
    )

    turn = client.complete(messages=[], tools=[], timeout=5)

    assert turn.provider_attempts == 0
    assert turn._provider_trace == ()


def test_runtime_empty_provider_tuple_is_honest_unconfigured_zero_attempts() -> None:
    turn = GLMModelClient(providers=()).complete(
        messages=[],
        tools=[],
        timeout=5,
    )

    assert turn.provider_attempts == 0
    assert "未配置" in turn.error
    assert turn._provider_trace == ()


def test_legacy_runtime_call_ledger_rejection_records_zero_attempts() -> None:
    with llm_refine.call_ledger_scope(max_calls=0) as ledger:
        turn = GLMModelClient().complete(messages=[], tools=[], timeout=5)

    summary = ledger.summary()
    assert turn.provider_attempts == 0
    assert turn._provider_trace == ()
    assert summary["call_count"] == 0
    assert summary["reserved_count"] == 0


@pytest.mark.parametrize("raw_tool_calls", (0, "", {}))
def test_runtime_falls_through_falsy_non_list_tool_calls(
    raw_tool_calls: object,
) -> None:
    def complete_fn(**_kwargs):
        provider = llm_refine.detect_provider()
        assert provider is not None
        if provider.name == "glm":
            return (
                {
                    "content": "invalid",
                    "tool_calls": raw_tool_calls,
                },
                provider,
                "",
            )
        return {"content": "ok", "tool_calls": []}, provider, ""

    turn = GLMModelClient(
        providers=(_provider("glm"), _provider("openai")),
        complete_fn=complete_fn,
    ).complete(messages=[], tools=[], timeout=5)

    assert turn.content == "ok"
    assert turn.provider_name == "openai"
    assert turn.provider_attempts == 2


def test_legacy_injected_callback_still_accepts_empty_envelope() -> None:
    provider = _provider("glm")
    turn = GLMModelClient(
        complete_fn=lambda **_kwargs: (
            {"content": "", "tool_calls": []},
            provider,
            "",
        )
    ).complete(messages=[], tools=[], timeout=5)

    assert turn.provider_name == "glm"
    assert turn.provider_attempts == 1
    assert turn.content == ""
    assert turn.error == ""


def test_glm_client_converts_openai_tool_call_without_provider_leak() -> None:
    captured: dict[str, object] = {}
    provider = LLMProvider(
        name="glm",
        api_key="secret-never-serialize",
        base_url="https://example.invalid/v1",
        model="glm-5.2",
    )

    def complete_fn(**kwargs):
        captured.update(kwargs)
        return (
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "market_data",
                            "arguments": '{"query":"A股"}',
                        },
                    }
                ],
            },
            provider,
            "",
        )

    messages = [{"role": "user", "content": "市场怎么看"}]
    tools = [{"type": "function", "function": {"name": "market_data"}}]
    turn = GLMModelClient("glm-5.2", complete_fn=complete_fn).complete(
        messages=messages,
        tools=tools,
        timeout=9.5,
    )

    assert turn.provider_name == "glm"
    assert turn.error == ""
    assert turn.tool_calls[0].call_id == "call-1"
    assert turn.tool_calls[0].name == "market_data"
    assert turn.tool_calls[0].arguments == {"query": "A股"}
    assert "secret-never-serialize" not in json.dumps(
        turn.to_dict(), ensure_ascii=False
    )
    assert captured == {
        "messages": messages,
        "tools": tools,
        "model_override": "glm-5.2",
        "timeout": 9.5,
        "temperature": 0.0,
        "tool_choice": "auto",
        "disable_thinking": True,
    }


def test_glm_client_preserves_full_message_history_on_every_call() -> None:
    calls: list[list[dict[str, object]]] = []

    def complete_fn(**kwargs):
        calls.append(kwargs["messages"])
        return {"content": "done", "tool_calls": []}, None, ""

    client = GLMModelClient(complete_fn=complete_fn)
    first = [{"role": "user", "content": "问题"}]
    second = [
        *first,
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "call-1", "content": "raw result"},
    ]

    client.complete(messages=first, tools=[], timeout=5.0)
    client.complete(messages=second, tools=[], timeout=5.0)

    assert calls == [first, second]


def test_glm_client_returns_stable_error_for_unavailable_provider() -> None:
    client = GLMModelClient(
        complete_fn=lambda **_kwargs: (None, None, "provider unavailable")
    )

    turn = client.complete(messages=[], tools=[], timeout=5.0)

    assert turn.content == ""
    assert turn.tool_calls == ()
    assert turn.provider_name == ""
    assert turn.error == "provider unavailable"


@pytest.mark.parametrize(
    "transient_reason",
    (
        "LLM 调用失败（TimeoutError）",
        "LLM 调用失败（RemoteDisconnected）",
        "LLM 调用失败（URLError）",
    ),
)
def test_glm_client_retries_one_transient_error_within_the_same_turn(
    transient_reason: str,
) -> None:
    provider = LLMProvider(
        name="glm",
        api_key="secret",
        base_url="https://example.invalid/v1",
        model="glm-5.2",
    )
    calls: list[dict[str, object]] = []

    def complete_fn(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return None, provider, transient_reason
        return {"content": "done", "tool_calls": []}, provider, ""

    messages = [{"role": "user", "content": "目前市场主线是什么"}]
    tools = [{"type": "function", "function": {"name": "market_data"}}]
    turn = GLMModelClient("glm-5.2", complete_fn=complete_fn).complete(
        messages=messages,
        tools=tools,
        timeout=5.0,
    )

    assert turn.content == "done"
    assert turn.error == ""
    assert turn.provider_attempts == 2
    assert len(calls) == 2
    assert calls[0]["messages"] == calls[1]["messages"] == messages
    assert calls[0]["tools"] == calls[1]["tools"] == tools
    assert 0.0 < calls[1]["timeout"] <= calls[0]["timeout"] <= 5.0


def test_glm_client_does_not_retry_a_non_transient_provider_error() -> None:
    calls: list[dict[str, object]] = []

    def complete_fn(**kwargs):
        calls.append(kwargs)
        return None, None, "LLM 调用 HTTP 400"

    turn = GLMModelClient(complete_fn=complete_fn).complete(
        messages=[],
        tools=[],
        timeout=5.0,
    )

    assert turn.error == "LLM 调用 HTTP 400"
    assert len(calls) == 1


def test_glm_client_rejects_malformed_tool_arguments_at_adapter_seam() -> None:
    provider = LLMProvider("glm", "secret", "https://example.invalid", "glm-5.2")
    client = GLMModelClient(
        complete_fn=lambda **_kwargs: (
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "market_data",
                            "arguments": "not-json",
                        },
                    }
                ],
            },
            provider,
            "",
        )
    )

    turn = client.complete(messages=[], tools=[], timeout=5.0)

    assert turn.tool_calls == ()
    assert turn.provider_name == "glm"
    assert turn.error == "invalid_tool_arguments:call-1"


def test_glm_runtime_runs_episode_through_provider_neutral_adapter() -> None:
    frame = TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )
    contract = ResearchTaskContract(
        task_id="glm-runtime-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(RequiredOutput("direct_assessment", "直接判断", (), True),),
        allowed_capabilities=(),
        research_tier="quick",
        task_frame_hash=frame.task_frame_hash,
    )
    context = ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(10.0),
        policy=ResearchPolicy("quick", 1, 10.0, 0.0),
        trace_parent_id="glm-runtime-test",
    )
    final = json.dumps(
        {
            "status": "partial",
            "draft": "当前缺少行情证据，不能给出确定判断。",
            "gaps": ["缺少行情证据"],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": [],
                    "gap": "缺少行情证据",
                }
            ],
        },
        ensure_ascii=False,
    )
    runtime = GLMAgentRuntime(
        complete_fn=lambda **_kwargs: (
            {"content": final, "tool_calls": []},
            LLMProvider("glm", "secret", "https://example.invalid", "glm-5.2"),
            "",
        )
    )

    outcome = runtime.run(
        task_frame=frame,
        context=context,
        registry=ResearchToolRegistry(()),
    )

    assert outcome.status == "partial"
    assert outcome.draft == "当前缺少行情证据，不能给出确定判断。"
    assert outcome.gaps == ("缺少行情证据",)
    assert outcome.usage.llm_calls == 1


def test_glm_runtime_standard_profile_reserves_a_slow_final_turn() -> None:
    assert GLMAgentRuntime.synthesis_reserve_for_tier("standard") == 75.0


@pytest.mark.parametrize(
    ("question_type", "expected"),
    (
        ("market_cause", 75.0),
        ("market_watch", 75.0),
        ("valuation_estimate", 60.0),
        ("stock_deep_dive", 60.0),
        ("market_forecast", 60.0),
    ),
)
def test_glm_runtime_allocates_budget_by_task_shape(
    question_type: str,
    expected: float,
) -> None:
    assert (
        GLMAgentRuntime.synthesis_reserve_for_task(
            tier="standard",
            question_type=question_type,
        )
        == expected
    )
