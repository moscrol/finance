from __future__ import annotations

import json

import pytest

from intelligence.services.glm_agent_runtime import (
    GLMAgentRuntime,
    GLMModelClient,
)
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
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", (), True),
        ),
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
