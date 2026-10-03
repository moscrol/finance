"""Retired template IDs have no authority outside the actual task contract.

Historical event dictionaries remain untouched. New unknown bindings and repair
goals no longer receive special treatment from a template-name list.
"""

from __future__ import annotations

from datetime import date
import json

import pytest

from intelligence.services.episode_protocol import (
    REJECTION_KINDS,
    EpisodeFinishRejection,
    RejectionKind,
    validate_episode_finish,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_contract import (
    InformationCutoff,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.task_frame import TaskFrame
from intelligence.services.track_contract import TRACK_CONTRACT_OUTPUT_ID_SET
from intelligence.tests.test_agent_episode import _successful_runner  # noqa: E402


def _context() -> ResearchRunContext:
    frame = TaskFrame(
        raw_question="固态电池和钠电池两条题材线最近一个月的产业进展与舆论热度对比",
        user_goal="跟踪两条题材线",
        question_type="theme_track",
        subject="固态电池",
        subject_kind="theme",
        market_scope="A股",
        timeframe="最近一个月",
        required_outputs=("change_summary", "tracking_signals"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_tracking_evidence",
        confidence=0.9,
    )
    policy = ResearchPolicy.for_tier("max")
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="track-slot-repair",
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput("change_summary", "变化摘要", ("kb_search",), True),
                RequiredOutput("tracking_signals", "跟踪信号", ("kb_search",), True),
            ),
            allowed_capabilities=("market_data",),
            research_tier="max",
            freshness="current",
            timeframe=frame.timeframe,
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(policy.total_seconds, synthesis_reserve=policy.synthesis_reserve),
        policy=policy,
        trace_parent_id="track-slot-repair",
        today="2026-09-07",
        latest_data_date="2026-09-02",
        information_cutoff=InformationCutoff(date(2026, 9, 7), "requested"),
    )


def _finish(bindings: list[dict]) -> str:
    return json.dumps(
        {
            "status": "completed",
            "draft": "近一个月固态电池热度强于钠电池。复核期限：2026-10-07。下期关注：固态电池涨停家数与成交额。",
            "gaps": [],
            "bindings": bindings,
        },
        ensure_ascii=False,
    )


def _evidence():
    evidence, _obs, _trace = _successful_runner("总览", None)  # type: ignore[arg-type]
    return tuple(evidence)


def _binding(output_id: str) -> dict:
    return {"output_id": output_id, "evidence_hashes": ["evidence-1"], "gap": ""}


@pytest.mark.parametrize("slot", sorted(TRACK_CONTRACT_OUTPUT_ID_SET))
def test_binding_a_retired_template_id_is_an_unknown_output(slot: str) -> None:
    with pytest.raises(EpisodeFinishRejection) as excinfo:
        validate_episode_finish(
            _finish([_binding("change_summary"), _binding(slot)]), context=_context(), evidence=_evidence()
        )
    assert excinfo.value.code == "unknown_output"
    assert excinfo.value.kind is RejectionKind.INTEGRITY
    assert slot in str(excinfo.value)
    assert "expression_slot_binding" not in REJECTION_KINDS


def test_a_truly_unknown_output_is_still_an_integrity_rejection() -> None:
    """对照：不是表达槽的陌生 id 仍按越界输出硬拒——这条地基不动。"""

    with pytest.raises(EpisodeFinishRejection) as excinfo:
        validate_episode_finish(_finish([_binding("made_up_output")]), context=_context(), evidence=_evidence())
    assert excinfo.value.code == "unknown_output"
    assert excinfo.value.kind is RejectionKind.INTEGRITY


def test_binding_only_contract_outputs_is_accepted() -> None:
    finish = validate_episode_finish(
        _finish([_binding("change_summary"), _binding("tracking_signals")]), context=_context(), evidence=_evidence()
    )
    assert finish.status == "completed"


def _goal(*elements: str) -> RepairGoal:
    return RepairGoal(
        episode_id="track-slot-repair",
        repair_goal_id="repair-track-slot-1",
        cycle=1,
        missing_answer_elements=tuple(elements),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=("kb_search:固态电池",),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=2,
        remaining_seconds=30.0,
    )


@pytest.mark.parametrize("output_id", ["track_ttl", "track_next_watch", "change_summary"])
def test_repair_message_does_not_reinterpret_an_obligation_by_its_name(output_id) -> None:
    payload = json.loads(FinanceResearchHarness().repair_goal_message(_goal(output_id), tools_open=False))
    assert payload["missing_answer_elements"] == [output_id]
    assert "expression_elements_note" not in payload
    assert "不要作为 bindings" not in json.dumps(payload, ensure_ascii=False)
