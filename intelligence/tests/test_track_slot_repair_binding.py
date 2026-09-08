"""跟踪题修复轮：表达槽 id 被当 output 绑时要可修正，不能硬拒（2026-09-07 两轮 theme_track 2/2 复现）。

形状：``track_contract`` 把「TTL / 下期关注 / 四态」缺件以合成 id（``track_ttl`` …）并进
``RepairGoal.missing_answer_elements``；模型看见 id 就当 output 去绑；``validate_episode_finish``
判 ``unknown_output``（INTEGRITY，不回灌不恢复）→ 整轮 ``invalid_repair_finish``。
系统自己要的东西被自己当越界硬拒。两处修：① 绑到表达槽 → ``expression_slot_binding``（FORMAT，
回灌可修正提示）；② REPAIR_GOAL 消息在真有表达槽时多一键说明「写进 draft、不进 bindings」，
其它修复轮的消息逐字节不变。
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
def test_binding_an_expression_slot_is_a_recoverable_format_rejection(slot: str) -> None:
    with pytest.raises(EpisodeFinishRejection) as excinfo:
        validate_episode_finish(
            _finish([_binding("change_summary"), _binding(slot)]), context=_context(), evidence=_evidence()
        )
    assert excinfo.value.code == "expression_slot_binding"
    assert excinfo.value.kind is RejectionKind.FORMAT
    assert REJECTION_KINDS["expression_slot_binding"] is RejectionKind.FORMAT
    message = str(excinfo.value)
    assert slot in message and "写进 draft" in message and "复核期限" in message


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


def test_repair_goal_message_explains_expression_slots_only_when_present() -> None:
    harness = FinanceResearchHarness()
    with_slots = json.loads(
        harness.repair_goal_message(_goal("track_ttl", "track_next_watch", "change_summary"), tools_open=False)
    )
    note = with_slots["expression_elements_note"]
    assert "track_ttl" in note and "track_next_watch" in note and "change_summary" not in note
    assert "不要作为 bindings 的 output_id" in note and "复核期限" in note
    # 没有表达槽的修复轮：消息里没有这一键，形状与拆分前逐字节相同（既有测试钉着）。
    without = json.loads(harness.repair_goal_message(_goal("change_summary"), tools_open=False))
    assert "expression_elements_note" not in without
