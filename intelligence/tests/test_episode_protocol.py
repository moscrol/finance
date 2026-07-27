from __future__ import annotations

import dataclasses
import json

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_protocol import (
    EpisodeFinish,
    build_episode_input,
    build_episode_instructions,
    finish_json_schema,
    validate_episode_finish,
)
from intelligence.services.evidence_capabilities import EvidencePlan
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
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(frame: TaskFrame) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="episode-protocol-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data",),
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", 3, 30.0, 0.0),
        trace_parent_id="episode-protocol-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry() -> ResearchToolRegistry:
    def runner(_query: str, _context: AgentToolContext):
        return (
            [],
            "",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="empty",
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情与市场时序",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


def _evidence() -> tuple[AgentEvidence, ...]:
    return (
        AgentEvidence(
            tool="market_data",
            title="A股市场总览",
            detail="截至2026-07-24，上涨家数增加。",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="market-hash",
        ),
    )


def test_finish_schema_is_closed_and_requires_all_fields() -> None:
    schema = finish_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"status", "draft", "gaps", "bindings"}
    binding_schema = schema["properties"]["bindings"]["items"]
    assert "basis" in binding_schema["required"]
    assert binding_schema["properties"]["basis"]["enum"] == [
        "evidence",
        "user_premise",
        "model_reasoning",
    ]


def test_protocol_builds_task_bound_instructions_and_input() -> None:
    frame = _frame()
    context = dataclasses.replace(
        _context(frame),
        conversation_context=(
            "user: 昨天的反弹能持续多久\n"
            "assistant: 基准判断是短周期修复。"
        ),
    )

    instructions = build_episode_instructions(frame, context, _registry())
    task_input = json.loads(build_episode_input(frame, context))

    assert frame.task_frame_hash in instructions
    assert "market_data" in instructions
    assert "不得在答案中暴露内部工具名、provider 或哈希" in instructions
    assert task_input["task_frame"]["task_frame_hash"] == frame.task_frame_hash
    assert task_input["research_contract"]["task_frame_hash"] == (
        frame.task_frame_hash
    )
    assert task_input["latest_data_date"] == "2026-07-24"
    assert task_input["information_cutoff"] == (
        context.information_cutoff.to_dict()
    )
    assert "information_cutoff" in task_input["date_rule"]
    assert "基准判断是短周期修复" in task_input["conversation_context"]
    assert task_input["conversation_context_rule"] == (
        "历史对话仅用于消解指代和延续用户目标，不得当作事实证据"
    )


def test_validate_finish_rejects_unknown_evidence_hash() -> None:
    frame = _frame()
    context = _context(frame)
    value = {
        "status": "completed",
        "draft": "当前判断有直接依据。",
        "gaps": [],
        "bindings": [
            {
                "output_id": "direct_assessment",
                "evidence_hashes": ["unknown-hash"],
                "gap": "",
            }
        ],
    }

    with pytest.raises(ValueError, match="unknown evidence hash"):
        validate_episode_finish(value, context=context, evidence=_evidence())


def test_validate_finish_returns_immutable_value() -> None:
    frame = _frame()
    context = _context(frame)
    finish = validate_episode_finish(
        {
            "status": "completed",
            "draft": "当前更接近条件化修复。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["market-hash"],
                    "gap": "",
                }
            ],
        },
        context=context,
        evidence=_evidence(),
    )

    assert finish == EpisodeFinish(
        status="completed",
        draft="当前更接近条件化修复。",
        gaps=(),
        bindings=finish.bindings,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        finish.status = "partial"  # type: ignore[misc]


def test_validate_finish_accepts_model_reasoning_without_fake_evidence() -> None:
    frame = _frame()
    context = _context(frame)
    context = dataclasses.replace(
        context,
        contract=dataclasses.replace(
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

    finish = validate_episode_finish(
        {
            "status": "completed",
            "draft": "判断新题材时，应先定义可证伪条件，再观察资金接力。",
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
        context=context,
        evidence=(),
    )

    assert finish.bindings == (
        OutputEvidenceBinding(
            "direct_assessment",
            (),
            basis="model_reasoning",
        ),
    )


def test_validate_finish_rejects_basis_that_weakens_evidence_contract() -> None:
    frame = _frame()
    context = _context(frame)

    with pytest.raises(ValueError, match="grounding basis"):
        validate_episode_finish(
            {
                "status": "completed",
                "draft": "当前市场已经转强。",
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
            context=context,
            evidence=(),
        )
