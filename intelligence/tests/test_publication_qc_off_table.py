"""公开稿不上质检章。核验结果只进 issues / 控制面。

现场：run_20260824_125037_303405、run_20260824_125258_079058
模型草稿没有【质检】，核验器往 public_answer 盖「存疑/降级」。
"""

from __future__ import annotations

from intelligence.services.episode_semantic_verifier import (
    REQUIRED_OUTPUT_DEGRADED_MARK,
    SEMANTIC_QUALITY_DOUBT_MARK,
    SemanticEpisodeVerifier,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_ceiling_required_block_degrade import _two_slot_structural
from intelligence.tests.test_episode_semantic_verifier import _judge


def test_public_answer_has_no_qc_stamps_when_required_sentence_is_doubted() -> None:
    draft = (
        "【直接判断】当日主线仍是电网设备。"
        "成交额 530.96 亿来自问句日预取。"
        "据此判断延续观察。"
        "【证据边界】仅覆盖 2026-07-23 日频盘面。"
    )
    frame, structural = _two_slot_structural(draft)
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(
            False,
            rejected=(3,),
            issues=("第3句质量不够，证明不了主线延续",),
        )
    ).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert "据此判断延续观察" in result.public_answer
    assert "【质检" not in result.public_answer
    assert SEMANTIC_QUALITY_DOUBT_MARK not in result.public_answer
    assert REQUIRED_OUTPUT_DEGRADED_MARK not in result.public_answer
    assert "质量不够" in " ".join(result.issues)
    assert result.judge_status == "repaired"
