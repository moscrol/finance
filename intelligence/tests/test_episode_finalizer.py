from __future__ import annotations

from copy import deepcopy
import json

import pytest

from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame


class RecordingModel:
    def __init__(self, turn: ModelTurn) -> None:
        self._turn = turn
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append(
            {
                "messages": deepcopy(messages),
                "tools": deepcopy(tools),
                "timeout": timeout,
            }
        )
        return self._turn


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


def _context(frame: TaskFrame, *, timeout: float = 30.0) -> ResearchRunContext:
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="finalizer-test",
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "给出市场结构判断",
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
        ),
        deadline=ResearchDeadline.from_timeout(timeout),
        policy=ResearchPolicy("quick", 3, timeout, 0.0),
        trace_parent_id="finalizer-test",
        today="2026-07-23",
        latest_data_date="2026-07-22",
    )


def _evidence(content_hash: str = "h1") -> AgentEvidence:
    return AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="close=100",
        source="本地行情",
        source_date="2026-07-22",
        evidence_tier="L4",
        content_hash=content_hash,
    )


def test_recovery_contains_task_required_outputs_and_existing_evidence_only() -> None:
    model = RecordingModel(ModelTurn("{}", (), "recording", ""))
    frame = _frame()

    turn = EpisodeFinalizer(model).recover(
        task_frame=frame,
        context=_context(frame),
        evidence=(_evidence("h1"),),
        gaps=("missing news",),
        failure_reason="invalid_model_finish",
    )

    assert len(model.calls) == 1
    sent = model.calls[0]
    assert sent["tools"] == []
    assert len(sent["messages"]) == 2
    assert [message["role"] for message in sent["messages"]] == [
        "system",
        "user",
    ]
    payload = json.loads(sent["messages"][1]["content"])
    assert set(payload) == {
        "task_frame",
        "required_outputs",
        "evidence",
        "gaps",
        "today",
        "latest_data_date",
        "failure_reason",
    }
    assert payload["task_frame"] == frame.to_dict()
    assert payload["required_outputs"] == [
        {
            "output_id": "direct_assessment",
            "description": "给出市场结构判断",
            "evidence_types": ["market_data"],
            "required": True,
            "grounding_mode": "evidence",
        }
    ]
    assert payload["evidence"] == [
        {
            "tool": "market_data",
            "title": "A股市场总览",
            "detail": "close=100",
            "source": "本地行情",
            "source_date": "2026-07-22",
            "evidence_tier": "L4",
            "supports": [],
            "contradicts": [],
            "independent_key": "",
            "freshness": "unknown",
            "content_hash": "h1",
        }
    ]
    assert payload["gaps"] == ["missing news"]
    assert payload["today"] == "2026-07-23"
    assert payload["latest_data_date"] == "2026-07-22"
    assert payload["failure_reason"] == "invalid_model_finish"
    assert "h2" not in json.dumps(sent["messages"], ensure_ascii=False)
    assert turn.tool_calls == ()
    assert 0.0 < sent["timeout"] <= 20.0


def test_recovery_compacts_large_evidence_round_robin_without_minting_hashes() -> None:
    model = RecordingModel(ModelTurn("{}", (), "recording", ""))
    frame = _frame()
    evidence = tuple(
        AgentEvidence(
            tool=tool,
            title=f"{tool}-{index}",
            detail=f"{tool} detail {index} " + ("x" * 800),
            source="本地证据",
            source_date="2026-07-23",
            evidence_tier="L4",
            content_hash=f"{tool}-{index}-hash",
        )
        for index in range(10)
        for tool in ("market_data", "mainline_context")
    )

    EpisodeFinalizer(model).recover(
        task_frame=frame,
        context=_context(frame),
        evidence=evidence,
        gaps=(),
        failure_reason="provider_error",
    )

    payload = json.loads(model.calls[0]["messages"][1]["content"])
    projected = payload["evidence"]
    assert len(projected) == 12
    assert [item["tool"] for item in projected[:4]] == [
        "market_data",
        "mainline_context",
        "market_data",
        "mainline_context",
    ]
    original_hashes = {item.content_hash for item in evidence}
    assert {item["content_hash"] for item in projected} <= original_hashes
    assert all(len(item["detail"]) <= 360 for item in projected)
    assert len(json.dumps(projected, ensure_ascii=False)) < 9_000
    assert "不超过1200字" in model.calls[0]["messages"][0]["content"]


def test_recovery_uses_only_remaining_synthesis_time() -> None:
    model = RecordingModel(ModelTurn("{}", (), "recording", ""))
    frame = _frame()

    EpisodeFinalizer(model, llm_timeout=60.0).recover(
        task_frame=frame,
        context=_context(frame, timeout=0.05),
        evidence=(_evidence(),),
        gaps=(),
        failure_reason="provider_error",
    )

    assert 0.0 < model.calls[0]["timeout"] <= 0.05


@pytest.mark.parametrize(
    "raw_reason, expected_reason",
    [
        ("provider unavailable\nRAW_PROVIDER_SENTINEL " + "x" * 500, "provider_error"),
        (
            "finish must be one JSON object\x00RAW_PARSER_SENTINEL",
            "invalid_model_finish",
        ),
    ],
)
def test_failure_reason_is_stable_and_does_not_leak_raw_exception(
    raw_reason: str,
    expected_reason: str,
) -> None:
    model = RecordingModel(ModelTurn("{}", (), "recording", ""))
    frame = _frame()

    EpisodeFinalizer(model).recover(
        task_frame=frame,
        context=_context(frame),
        evidence=(_evidence(),),
        gaps=(),
        failure_reason=raw_reason,
    )

    payload = json.loads(model.calls[0]["messages"][1]["content"])
    reason = payload["failure_reason"]
    assert reason == expected_reason
    assert len(reason) <= 240
    assert "RAW_PROVIDER_SENTINEL" not in json.dumps(model.calls[0]["messages"])
    assert "RAW_PARSER_SENTINEL" not in json.dumps(model.calls[0]["messages"])
    assert "\n" not in reason
    assert "\x00" not in reason
