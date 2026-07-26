from __future__ import annotations

from types import SimpleNamespace
from typing import Any
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.openai_agents_runtime import (
    AgentsSdkRequest,
    AgentsSdkResult,
    OpenAIAgentsRuntime,
    build_agents_model_settings,
    build_glm_sdk_model,
    build_glm_sdk_model_factory,
    build_gpt_sdk_model,
    build_gpt_sdk_model_factory,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场的主线是什么",
        user_goal="判断当前A股市场主线及依据",
        question_type="market_watch",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_a_share_market",
        confidence=0.95,
    )


def _context(
    frame: TaskFrame,
    *,
    max_steps: int = 2,
    allowed_capabilities: tuple[str, ...] = ("mainline_context",),
    timeout: float = 30.0,
    synthesis_reserve: float = 0.0,
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="sdk-runtime-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("mainline_context",),
                True,
            ),
        ),
        allowed_capabilities=allowed_capabilities,
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(
            timeout,
            synthesis_reserve=synthesis_reserve,
        ),
        policy=ResearchPolicy("quick", max_steps, timeout, synthesis_reserve),
        trace_parent_id="sdk-runtime-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry(calls: list[str]) -> ResearchToolRegistry:
    def mainline_runner(query: str, _context: AgentToolContext):
        calls.append(query)
        evidence = AgentEvidence(
            tool="mainline_context",
            title="同日主线结构",
            detail="截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            source="本地正式日报",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="mainline-hash",
        )
        return (
            [evidence],
            "医药是韧性核心，电力是轮动支线。",
            ProviderTrace(
                provider="test:mainline",
                capability="mainline_context",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    def forbidden_runner(query: str, _context: AgentToolContext):
        calls.append(f"forbidden:{query}")
        return ([], "", None)

    def news_runner(query: str, _context: AgentToolContext):
        calls.append(f"news:{query}")
        return ([], "没有新增新闻", None)

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="mainline_context",
                capability="mainline_context",
                description="同日主线与板块结构",
                cost="local",
                freshness="current",
                runner=mainline_runner,
                query_scope="episode",
            ),
            ToolSpec(
                name="forbidden_news",
                capability="news_search",
                description="未授权新闻",
                cost="network",
                freshness="current",
                runner=forbidden_runner,
            ),
            ToolSpec(
                name="market_news",
                capability="market_news",
                description="市场新闻",
                cost="network",
                freshness="current",
                runner=news_runner,
            ),
        )
    )


class SuccessfulFakeSdkRunner:
    def __init__(self) -> None:
        self.tool_names: set[str] = set()

    def __call__(self, request: AgentsSdkRequest) -> AgentsSdkResult:
        self.tool_names = {tool.name for tool in request.tools}
        observation = request.tools[0].invoke("A股 当前主线")
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": observation["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(
            final_output=json.dumps(finish, ensure_ascii=False),
            llm_calls=2,
            input_tokens=1200,
            output_tokens=240,
        )


def test_sdk_runtime_exposes_only_authorized_tools_and_returns_outcome() -> None:
    frame = _frame()
    calls: list[str] = []
    fake = SuccessfulFakeSdkRunner()

    outcome = OpenAIAgentsRuntime(
        runner=fake,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    assert fake.tool_names == {"mainline_context"}
    assert outcome.status == "completed"
    assert outcome.bindings[0].evidence_hashes == ("mainline-hash",)
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1
    assert calls == ["A股 当前主线"]


def test_sdk_runtime_preserves_typed_tool_schema_and_arguments() -> None:
    frame = _frame()
    received: list[dict[str, object]] = []
    typed_schema = {
        "type": "object",
        "properties": {
            "dataset": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["dataset", "limit"],
        "additionalProperties": False,
    }

    def runner(value: object, _context: AgentToolContext):
        assert isinstance(value, dict)
        received.append(value)
        evidence = AgentEvidence(
            tool="finance_query",
            title="市场结构",
            detail="截至2026-07-24，上证指数当日上涨1.2%。",
            source="本地结构化市场数据",
            source_date="2026-07-24",
            evidence_tier="L4_structured",
            content_hash="finance-query-hash",
        )
        return (
            [evidence],
            evidence.detail,
            ProviderTrace(
                provider="test:finance_query",
                capability="finance_query",
                status="success",
                result_count=1,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="结构化金融查询",
                cost="local",
                freshness="current",
                runner=runner,
                parameters=typed_schema,
                parse_arguments=lambda arguments: (
                    dict(arguments),
                    str(arguments["dataset"]),
                ),
            ),
        )
    )
    captured_schema: dict[str, object] = {}

    def sdk_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tool = request.tools[0]
        captured_schema.update(tool.parameters)
        observation = tool.invoke({"dataset": "market_daily", "limit": 5})
        return AgentsSdkResult(
            final_output=json.dumps(
                {
                    "status": "completed",
                    "draft": "截至2026-07-24，上证指数当日上涨1.2%。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": observation["evidence_hashes"],
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            llm_calls=2,
        )

    OpenAIAgentsRuntime(
        runner=sdk_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(
            frame,
            allowed_capabilities=("finance_query",),
        ),
        registry=registry,
    )

    assert captured_schema == typed_schema
    assert received == [{"dataset": "market_daily", "limit": 5}]


def test_sdk_runtime_reserves_part_of_synthesis_budget_for_verifier() -> None:
    frame = _frame()
    captured: list[float] = []
    successful = SuccessfulFakeSdkRunner()

    def capture_timeout(request: AgentsSdkRequest) -> AgentsSdkResult:
        captured.append(request.timeout)
        return successful(request)

    outcome = OpenAIAgentsRuntime(
        runner=capture_timeout,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(frame, timeout=30.0, synthesis_reserve=10.0),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert len(captured) == 1
    assert 26.0 <= captured[0] < 27.0


def test_sdk_stage_close_instructs_finalization_without_public_gap() -> None:
    frame = _frame()
    observations: list[dict[str, object]] = []

    def stage_closed_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        observations.append(request.tools[0].invoke("A股 当前主线"))
        finish = {
            "status": "partial",
            "draft": "基于当前可用信息，暂不确认主线。",
            "gaps": ["仍缺少同日主线证据"],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": [],
                    "gap": "仍缺少同日主线证据",
                }
            ],
        }
        return AgentsSdkResult(json.dumps(finish, ensure_ascii=False), 1)

    outcome = OpenAIAgentsRuntime(
        runner=stage_closed_runner,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(frame, timeout=10.0, synthesis_reserve=10.0),
        registry=_registry([]),
    )

    assert observations == [
        {
            "status": "closed",
            "tool": "mainline_context",
            "error": "research_stage_closed",
            "instruction": "研究取证阶段已结束，请使用已有信息完成终止回答。",
        }
    ]
    assert "research_stage_closed" not in outcome.gaps
    assert outcome.status == "partial"


def test_sdk_runtime_turns_tool_budget_exhaustion_into_a_partial_gap() -> None:
    frame = _frame()
    tool_errors: list[str] = []

    def over_budget_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        tools = {tool.name: tool for tool in request.tools}
        first = tools["mainline_context"].invoke("A股 当前主线")
        second = tools["market_news"].invoke("A股 主线新闻")
        tool_errors.append(str(second.get("error") or ""))
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": first["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(json.dumps(finish, ensure_ascii=False), 2)

    outcome = OpenAIAgentsRuntime(
        runner=over_budget_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(
            frame,
            max_steps=1,
            allowed_capabilities=("mainline_context", "market_news"),
        ),
        registry=_registry([]),
    )

    assert tool_errors == ["tool_budget_exhausted"]
    assert outcome.status == "partial"
    assert "tool_budget_exhausted" in outcome.gaps
    assert outcome.usage.tool_calls == 1


def test_sdk_provider_factories_preserve_endpoint_specific_settings() -> None:
    glm_model = build_glm_sdk_model(
        api_key="test-key",
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        model="glm-5.2",
        timeout=12.0,
    )
    glm_settings = build_agents_model_settings("sdk_glm")
    gpt_model = build_gpt_sdk_model("gpt-5.6-sol")
    gpt_settings = build_agents_model_settings("sdk_gpt")

    assert type(glm_model).__name__ == "OpenAIChatCompletionsModel"
    assert gpt_model == "gpt-5.6-sol"
    assert glm_settings.temperature == 0.0
    assert glm_settings.parallel_tool_calls is False
    assert glm_settings.extra_body == {"thinking": {"type": "disabled"}}
    assert gpt_settings.parallel_tool_calls is False
    assert gpt_settings.reasoning.effort == "high"
    assert gpt_settings.verbosity == "medium"
    assert gpt_settings.store is False


def test_gpt_sdk_factory_builds_explicit_responses_client() -> None:
    model_factory = build_gpt_sdk_model_factory(
        api_key="session-secret",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
        timeout=12.0,
    )

    model, close = model_factory()

    assert type(model).__name__ == "OpenAIResponsesModel"
    assert str(model._client.base_url) == "http://localhost:57244/v1/"
    assert callable(close)
    asyncio.run(close())


def test_default_sdk_runner_uses_local_tools_and_disables_trace_export(
    monkeypatch,
) -> None:
    from agents import Runner

    frame = _frame()
    seen: dict[str, Any] = {}
    model = "fake-sdk-model"
    model_settings = build_agents_model_settings("sdk_glm")
    close_calls = 0

    async def close_model() -> None:
        nonlocal close_calls
        close_calls += 1

    async def fake_run(
        agent,
        user_input,
        *,
        context,
        max_turns,
        run_config,
        **_kwargs,
    ):
        seen.update(
            {
                "agent": agent,
                "input": user_input,
                "context": context,
                "max_turns": max_turns,
                "run_config": run_config,
            }
        )
        raw = await agent.tools[0].on_invoke_tool(
            None,
            json.dumps({"query": "A股 当前主线"}, ensure_ascii=False),
        )
        observation = json.loads(raw)
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": observation["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        usage = SimpleNamespace(requests=2, input_tokens=900, output_tokens=180)
        return SimpleNamespace(
            final_output=json.dumps(finish, ensure_ascii=False),
            context_wrapper=SimpleNamespace(usage=usage),
        )

    monkeypatch.setattr(Runner, "run", fake_run)
    outcome = OpenAIAgentsRuntime(
        backend="sdk_glm",
        model_name="glm-5.2",
        model_settings=model_settings,
        model_factory=lambda: (model, close_model),
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert seen["agent"].model == model
    assert seen["agent"].model_settings is model_settings
    assert seen["run_config"].tracing_disabled is True
    assert seen["run_config"].trace_include_sensitive_data is False
    assert seen["run_config"].tool_execution.max_function_tool_concurrency == 1
    assert outcome.usage.llm_calls == 2
    assert close_calls == 1


def test_sdk_runtime_allows_one_finish_only_recovery() -> None:
    frame = _frame()
    runner_calls = 0
    research_calls: list[str] = []

    def repairing_runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 1:
            request.tools[0].invoke("A股 当前主线")
            return AgentsSdkResult("not-json", 1, 500, 80, 1)

        assert request.tools == ()
        assert "只输出一个 JSON 对象" in request.instructions
        assert "研究阶段已经关闭" in request.instructions
        assert '"invalid_output": "not-json"' in request.input
        assert '"required_outputs"' in request.input
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["mainline-hash"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(
            json.dumps(finish, ensure_ascii=False),
            1,
            300,
            60,
            1,
        )

    outcome = OpenAIAgentsRuntime(
        runner=repairing_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(research_calls),
    )

    assert runner_calls == 2
    assert research_calls == ["A股 当前主线"]
    assert outcome.status == "completed"
    assert outcome.stop_reason == "sdk_finalization_recovered"
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1
    runtime_event = next(
        event for event in outcome.events if event.kind == "runtime_result"
    )
    assert runtime_event.payload["input_tokens"] == 800
    assert runtime_event.payload["output_tokens"] == 140


def test_sdk_runtime_translates_model_turn_limit_without_fallback() -> None:
    from agents.exceptions import MaxTurnsExceeded

    frame = _frame()

    def turn_limited(request: AgentsSdkRequest) -> AgentsSdkResult:
        request.tools[0].invoke("A股 当前主线")
        raise MaxTurnsExceeded("turn limit")

    outcome = OpenAIAgentsRuntime(
        runner=turn_limited,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "sdk_turn_limit"
    assert "sdk_turn_limit" in outcome.gaps
    assert outcome.evidence[0].content_hash == "mainline-hash"
    assert outcome.usage.tool_calls == 1


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("auth_unavailable: no auth available", "sdk_auth_unavailable"),
        ("status code: 429 rate limit", "sdk_rate_limited"),
        ("status code: 503 service unavailable", "sdk_upstream_unavailable"),
        ("connection error", "sdk_transport_unavailable"),
    ),
)
def test_sdk_runtime_classifies_provider_infrastructure_failures(
    message: str,
    expected: str,
) -> None:
    frame = _frame()

    def unavailable(_request: AgentsSdkRequest) -> AgentsSdkResult:
        raise RuntimeError(message)

    outcome = OpenAIAgentsRuntime(
        runner=unavailable,
        backend="sdk_gpt",
        model_name="gpt-5.6-sol",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "failed"
    assert outcome.stop_reason == expected
    assert outcome.gaps == (expected,)


def test_sdk_finish_recovery_failure_stops_after_two_model_calls() -> None:
    frame = _frame()
    runner_calls = 0

    def broken_recovery(request: AgentsSdkRequest) -> AgentsSdkResult:
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 1:
            request.tools[0].invoke("A股 当前主线")
            return AgentsSdkResult("not-json", 1)
        raise RuntimeError("provider unavailable during finalization")

    outcome = OpenAIAgentsRuntime(
        runner=broken_recovery,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert runner_calls == 2
    assert outcome.status == "partial"
    assert outcome.stop_reason == "sdk_invalid_finish"
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1


def test_sdk_recovers_reasoning_finish_without_requiring_fake_evidence() -> None:
    frame = _frame()
    context = _context(frame, allowed_capabilities=())
    context = replace(
        context,
        contract=replace(
            context.contract,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    (),
                    True,
                    grounding_mode="model_reasoning",
                ),
            ),
            allowed_capabilities=(),
        ),
    )
    runner_calls = 0

    def repair_reasoning(request: AgentsSdkRequest) -> AgentsSdkResult:
        nonlocal runner_calls
        runner_calls += 1
        assert request.tools == ()
        if runner_calls == 1:
            return AgentsSdkResult("not-json", 1)
        return AgentsSdkResult(
            json.dumps(
                {
                    "status": "completed",
                    "draft": "先定义可证伪条件，再逐日更新判断。",
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": "direct_assessment",
                            "evidence_hashes": [],
                            "basis": "model_reasoning",
                            "gap": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            1,
        )

    outcome = OpenAIAgentsRuntime(
        runner=repair_reasoning,
        backend="sdk_glm",
        model_name="glm-5.2",
    ).run(
        task_frame=frame,
        context=context,
        registry=_registry([]),
    )

    assert runner_calls == 2
    assert outcome.status == "completed"
    assert outcome.stop_reason == "sdk_finalization_recovered"
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 0
    assert outcome.bindings[0].basis == "model_reasoning"


@pytest.mark.skipif(
    os.environ.get("RUN_OPENAI_AGENTS_LIVE") != "1",
    reason="real OpenAI Agents SDK smoke is opt-in",
)
def test_real_sdk_glm_smoke() -> None:
    api_key = os.environ["FORESIGHT_BUILTIN_LLM_API_KEY"]
    base_url = os.environ.get(
        "FORESIGHT_BUILTIN_LLM_BASE_URL",
        "https://open.bigmodel.cn/api/coding/paas/v4",
    )
    model_name = os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL", "glm-5.2")
    frame = _frame()
    context = _context(frame, timeout=90.0)
    calls: list[str] = []
    model_factory = build_glm_sdk_model_factory(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        timeout=90.0,
    )
    outcome = OpenAIAgentsRuntime(
        backend="sdk_glm",
        model_name=model_name,
        model_factory=model_factory,
    ).run(
        task_frame=frame,
        context=context,
        registry=_registry(calls),
    )
    verified = verify_episode_outcome(context.contract, outcome)
    payload = {
        "runtime_backend": "sdk_glm",
        "verified_status": verified.verified_status,
        "outcome": outcome.to_dict(),
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    Path("/tmp/sdk-glm-smoke.json").write_text(serialized, encoding="utf-8")

    assert api_key not in serialized
    assert outcome.status in {"completed", "partial"}
    assert outcome.evidence
    assert outcome.stop_reason in {"model_finish", "sdk_finalization_recovered"}
    assert calls
