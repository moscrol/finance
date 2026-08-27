"""V8：语义质量删除权收窄。设计 §7.1 ①–⑥，先红后绿。

Spec: docs/superpowers/specs/2026-08-22-v8-semantic-deletion-rights-design.md
"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.runtime.conversation_orchestrator import _with_review_appendix
from intelligence.services.episode_semantic_verifier import (
    SEMANTIC_QUALITY_DOUBT_MARK,
    SemanticEpisodeVerifier,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_ceiling_required_block_degrade import (
    test_degraded_block_annotation_is_visible_on_public_answer,
    test_empty_remainder_of_lost_slot_has_no_apology_banner,
    test_full_wipe_still_keeps_c3_banner,
    test_numeric_unsupported_sentence_is_still_deleted,
    test_partial_mechanical_delete_keeps_remainder_and_degrades,
    test_replay_huangshi_keeps_remainder_without_apology_banner,
    test_replay_taichenguang_keeps_remainder_without_apology_banner,
    test_semantic_quality_reject_keeps_required_block_remainder,
)
from intelligence.tests.test_ceiling_required_block_degrade import _two_slot_structural
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural


def _verify(frame, structural, judge):
    return SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_semantic_quality_reject_keeps_required_sentence_and_marks(
    monkeypatch,
) -> None:
    """① 必需块内语义拒 1 句：句留、存疑标、质检附录；`_repair` 不得吃该句号。"""

    seen: list[tuple[int, ...]] = []
    original = SemanticEpisodeVerifier._repair

    def wrapped(self, **kwargs):
        seen.append(kwargs["rejected_sentence_indexes"])
        return original(self, **kwargs)

    monkeypatch.setattr(SemanticEpisodeVerifier, "_repair", wrapped)

    draft = (
        "【直接判断】当日主线仍是电网设备。"
        "成交额 530.96 亿来自问句日预取。"
        "据此判断延续观察。"
        "【证据边界】仅覆盖 2026-07-23 日频盘面。"
    )
    frame, structural = _two_slot_structural(draft)
    judge = _judge(
        False,
        rejected=(3,),
        issues=("第3句质量不够，证明不了主线延续",),
    )

    result = _verify(frame, structural, judge)

    assert "据此判断延续观察" in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer
    assert "质量不够" in " ".join(result.issues)
    appendix = _with_review_appendix(result.public_answer, result.issues)
    assert "## 输出质检" in appendix
    assert "质量不够" in appendix
    assert appendix.index("据此判断延续观察") < appendix.index("## 输出质检")
    assert all(3 not in indexes for indexes in seen)
    assert result.judge_status == "repaired"


def test_numeric_unsupported_sentence_still_deleted_under_v8() -> None:
    """② W1 ② 回归：无据阈值句仍消失。"""

    test_numeric_unsupported_sentence_is_still_deleted()


def test_unresolved_evidence_ordinal_is_deleted_by_code_gate() -> None:
    """③ 表外 E 号句仍消失；句号由代码产，不靠 LLM 文案。"""

    draft = "市场下跌。据E99显示外部资金将持续流入。"
    frame, structural = _structural(draft)
    result = _verify(frame, structural, _judge(True))

    assert "E99" not in result.public_answer
    assert "市场下跌" in result.public_answer
    assert "unresolved_evidence_ordinal" in " ".join(result.issues)


def test_c_cluster_mechanical_trigger_keeps_rejudge_safety_net() -> None:
    """④ C 簇抽检：机械扳机下 calls 与稿变短原断言仍绿。"""

    frame, structural = _structural(
        "市场下跌。据E99显示下跌。",
        gaps=("外围催化仍待核验",),
    )
    original = structural.outcome
    judge = _judge(
        False,
        rejected=(2,),
        issues=(
            "code=unresolved_evidence_ordinal subject=unresolved_evidence_ordinal "
            ":: cited evidence ordinal is not in this episode's evidence table",
        ),
    )
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.status == "completed"
    assert result.judge_status == "repaired"
    assert len(judge.calls) == 2  # type: ignore[attr-defined]
    repaired = result.verified.outcome
    assert repaired.draft == "市场下跌。"
    assert result.public_answer == "市场下跌。"
    assert repaired.evidence == original.evidence
    assert repaired.gaps == original.gaps


def test_w1_regression_pins_still_green() -> None:
    """⑤ W1 ①③④⑤ + 两案重放仍绿。"""

    test_partial_mechanical_delete_keeps_remainder_and_degrades()
    test_empty_remainder_of_lost_slot_has_no_apology_banner()
    test_full_wipe_still_keeps_c3_banner()
    test_degraded_block_annotation_is_visible_on_public_answer()
    test_replay_huangshi_keeps_remainder_without_apology_banner()
    test_replay_taichenguang_keeps_remainder_without_apology_banner()


def test_v8_primary_pin_keeps_third_sentence_with_doubt_mark() -> None:
    """⑥ 升格主钉：第 3 句留下 + 存疑标。"""

    test_semantic_quality_reject_keeps_required_block_remainder()


def test_replay_semantic_quality_reject_keeps_sentence_with_mark() -> None:
    """§7.3：冻结「语义质量拒句、块未空」；after = 句在 + 标。"""

    payload = json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "v8-semantic-deletion"
            / "semantic-quality-kept.json"
        ).read_text(encoding="utf-8")
    )
    frame, structural = _two_slot_structural(str(payload["draft"]))
    result = _verify(
        frame,
        structural,
        _judge(
            False,
            rejected=tuple(payload["rejected_sentence_indexes"]),
            issues=tuple(payload["issues"]),
        ),
    )
    snippet = str(payload["keep_snippet"])
    assert payload["after"]["keep_snippet_present"] is True
    assert snippet in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer
    assert payload["before"]["keep_snippet_present"] is False


def test_partition_does_not_read_issue_copy() -> None:
    """分流器不得用 issue 文案关键词。"""

    from intelligence.services import episode_semantic_verifier as module

    source = __import__("inspect").getsource(module._partition_rejected_indexes)
    assert "因果" not in source
    assert "质量不够" not in source
    assert "re.search" not in source
