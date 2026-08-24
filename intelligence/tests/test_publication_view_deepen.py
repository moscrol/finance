"""P0-A：加深 view() 出口。活性检查是 view 被执行到、adapter 缝合=0。

接缝（spec 已确认，不测私有拼串）：
- ``session_projection.view(TerminalFacts)``
- ``SemanticEpisodeVerifier._gap_answer`` 只填 TerminalFacts
- ``continuous_turn_adapter`` 不得再把 ``ensure_preplaced_gap_sections`` 缝进公开稿
- ``verify_episode_outcome`` 的 mandatory capability 看 typed receipt 投影
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from intelligence.runtime import continuous_turn_adapter
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
    plan_capabilities_from_receipt,
)
from intelligence.services.mandatory_satisfiability import UNREACHABLE_MANDATORY_GAP
from intelligence.services.episode_issues import IssueCode
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract
from intelligence.services.task_frame import TaskFrame

_ADAPTER = Path(continuous_turn_adapter.__file__)
_QUESTION = "2026-06-11 液冷"


def _theme_frame() -> TaskFrame:
    return TaskFrame(
        raw_question=_QUESTION,
        user_goal="形成条件化判断",
        question_type="theme_analysis",
        subject="液冷温控",
        subject_kind="theme",
        market_scope="A股",
        timeframe="2026-06-11",
        required_outputs=("direct_assessment", "chain_mapping", "counterpoint"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )


def _sector_evidence(index: int) -> AgentEvidence:
    return AgentEvidence(
        tool="finance_query",
        title=f"板块日频行情（2026-06-{11 - index:02d}）",
        detail=f"板块名称=液冷服务器；交易日=2026-06-{11 - index:02d}；涨跌幅=-1.11",
        source="本地结构化数据 · 板块日频行情",
        source_date=f"2026-06-{11 - index:02d}",
        content_hash=f"b2-hash-{index}",
        independent_key=f"duckdb:sector_daily:2026-06-{11 - index:02d}",
    )


def _b2_contract(frame: TaskFrame, *, preplaced: bool = False) -> ResearchTaskContract:
    gap = UNREACHABLE_MANDATORY_GAP if preplaced else ""
    return ResearchTaskContract(
        task_id="b2-liquid-cooling",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接回答用户问题并说明判断强度",
                ("finance_query",),
                True,
                preplaced_gap=gap,
            ),
            RequiredOutput(
                "chain_mapping",
                "产业链层级、角色与关键环节",
                ("finance_query",),
                True,
                preplaced_gap=gap,
            ),
            RequiredOutput(
                "counterpoint",
                "提供主要反证或竞争性解释",
                ("finance_query",),
                True,
                preplaced_gap=gap,
            ),
        ),
        allowed_capabilities=("finance_query",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )


def _b2_verified(
    *,
    draft: str = "",
    fulfilled_direct: bool = False,
    preplaced: bool = False,
    evidence_count: int = 3,
):
    frame = _theme_frame()
    evidence = tuple(_sector_evidence(i) for i in range(evidence_count))
    bindings = (
        OutputEvidenceBinding("direct_assessment", (evidence[0].content_hash,))
        if fulfilled_direct
        else OutputEvidenceBinding("direct_assessment", (), "修复轮未返回可验证的 FINAL_JSON"),
        OutputEvidenceBinding("chain_mapping", (), "修复轮未返回可验证的 FINAL_JSON"),
        OutputEvidenceBinding("counterpoint", (), "修复轮未返回可验证的 FINAL_JSON"),
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft=draft,
        evidence=evidence,
        traces=(),
        gaps=("修复轮未返回可验证的 FINAL_JSON",),
        stop_reason="invalid_repair_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=bindings,
        usage=AgentUsage(llm_calls=2, tool_calls=1),
    )
    return frame, verify_episode_outcome(_b2_contract(frame, preplaced=preplaced), outcome)


def _assert_b2_public_hygiene(answer: str) -> None:
    assert "本轮核验未完成" in answer
    assert "现有证据不足" not in answer
    assert "【结构缺口】" not in answer
    assert "【质检" not in answer
    assert UNREACHABLE_MANDATORY_GAP not in answer


class TestB2ShapedRewrites:
    def test_empty_draft_unfilled_slots_use_user_language(self) -> None:
        frame, verified = _b2_verified()
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
        _assert_b2_public_hygiene(answer)
        assert "这次还核验不了：直接回答用户问题并说明判断强度。" in answer
        assert "这次还核验不了：产业链层级、角色与关键环节。" in answer
        assert "这次还核验不了：提供主要反证或竞争性解释。" in answer
        assert "已取得 3 条证据" in answer

    def test_fulfilled_slot_keeps_public_sentence(self) -> None:
        frame, verified = _b2_verified(
            draft="液冷服务器当日跌 1.11%。",
            fulfilled_direct=True,
        )
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
        _assert_b2_public_hygiene(answer)
        assert "液冷服务器当日跌 1.11%。" in answer
        assert "这次还核验不了：产业链层级、角色与关键环节。" in answer
        assert "这次还核验不了：提供主要反证或竞争性解释。" in answer

    def test_preplaced_gap_does_not_enter_public_answer(self) -> None:
        frame, verified = _b2_verified(preplaced=True)
        answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
        _assert_b2_public_hygiene(answer)
        assert "这次还核验不了：直接回答用户问题并说明判断强度。" in answer


class TestAdapterDoesNotStitchGapSections:
    def test_production_adapter_never_calls_ensure_preplaced_on_public(self) -> None:
        source = _ADAPTER.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_ADAPTER))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "ensure_preplaced_gap_sections")
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "ensure_preplaced_gap_sections"
                )
            )
        ]
        assert calls == []
        assert "ensure_preplaced_gap_sections" not in continuous_turn_adapter.__dict__


class TestTypedReceiptCapabilityProjection:
    def test_finance_query_receipt_satisfies_market_plan_capabilities(self) -> None:
        assert "market_data" in plan_capabilities_from_receipt(tool="finance_query")
        assert "mainline_context" in plan_capabilities_from_receipt(
            tool="finance_query",
            dataset="sector_daily",
        )

    def test_finance_query_evidence_does_not_raise_false_capability(self) -> None:
        frame = _theme_frame()
        evidence = _sector_evidence(0)
        contract = replace(
            _b2_contract(frame),
            evidence_plan=EvidencePlan(
                "current_mainline",
                (
                    EvidenceRequirement("MARKET_DAILY", "market_data", True),
                    EvidenceRequirement("D4", "mainline_context", True),
                ),
            ),
            allowed_capabilities=("finance_query", "market_data", "mainline_context"),
        )
        outcome = AgentOutcome(
            task_frame_hash=frame.task_frame_hash,
            status="partial",
            draft="",
            evidence=(evidence,),
            traces=(),
            gaps=(),
            stop_reason="model_finish",
            events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
            bindings=(
                OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
                OutputEvidenceBinding("chain_mapping", (), "未绑定"),
                OutputEvidenceBinding("counterpoint", (), "未绑定"),
            ),
            usage=AgentUsage(llm_calls=1, tool_calls=1),
        )
        verified = verify_episode_outcome(contract, outcome)
        missing = [
            item
            for item in verified.issue_items
            if item.code == IssueCode.MISSING_MANDATORY_CAPABILITY
        ]
        assert missing == []
        assert verified.mandatory_missing_capabilities == ()
