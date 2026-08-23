"""W1：判官对必需输出块只有降级权（残块保留 + 标注 + 批评进质检段）。

Spec: docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md §W1
离线 TDD ①–⑤。先红后绿。
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from intelligence.runtime.conversation_orchestrator import _with_review_appendix
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import (
    REQUIRED_OUTPUT_DEGRADED_MARK,
    SEMANTIC_QUALITY_DOUBT_MARK,
    SemanticEpisodeVerifier,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.tests.test_episode_semantic_verifier import (
    _frame,
    _judge,
    _structural,
)

_APOLOGY_MARKERS = ("结构缺口", "现有证据不足", "证据缺口：")


def _two_slot_structural(draft: str):
    frame = replace(
        _frame(),
        required_outputs=("direct_assessment", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="市场成交额与结构观察",
        source="行情快照",
        source_date="2026-07-22",
        content_hash="HASH_PRIVATE_SENTINEL",
    )
    required_outputs = (
        RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        RequiredOutput("evidence_boundary", "证据边界", ("market_data",), True),
    )
    contract = ResearchTaskContract(
        task_id="w1-two-slot",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=required_outputs,
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _verify(frame, structural, judge):
    return SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_partial_mechanical_delete_keeps_remainder_and_degrades() -> None:
    """① 块内 N 句、合法删 1 句 → 残块保留 + missing + 质检 + 块级标注。"""

    draft = (
        "【直接判断】若指数跌破99999点则主线成立。"
        "成交额 530.96 亿来自问句日预取。"
        "据此判断延续观察。"
        "【证据边界】仅覆盖 2026-07-23 日频盘面。"
    )
    frame, structural = _two_slot_structural(draft)
    judge = _judge(True)

    result = _verify(frame, structural, judge)

    assert "成交额 530.96" in result.public_answer
    assert "【证据边界】" in result.public_answer
    assert "99999" not in result.public_answer
    assert "【直接判断】若指数跌破99999点则主线成立" not in result.public_answer
    assert result.gap_output_ids == ("direct_assessment",)
    lost = next(
        item
        for item in result.verified.completion.outputs
        if item.output_id == "direct_assessment"
    )
    assert lost.status == "missing"
    assert REQUIRED_OUTPUT_DEGRADED_MARK in result.public_answer
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer
    joined = " ".join(result.issues)
    assert "numeric_unsupported" in joined
    appendix = _with_review_appendix(result.public_answer, result.issues)
    assert "## 输出质检" in appendix
    assert "numeric_unsupported" in appendix
    assert appendix.index("成交额 530.96") < appendix.index("## 输出质检")


def test_numeric_unsupported_sentence_is_still_deleted() -> None:
    """② 白名单：numeric_unsupported 句仍被删。"""

    draft = (
        "【当前判断】市场偏弱。"
        "若指数跌破99999点则失效。"
        "【证据边界】数据截至2026-07-22。"
    )
    frame, structural = _two_slot_structural(draft)

    result = _verify(frame, structural, _judge(True))

    assert "99999点" not in result.public_answer
    assert "【当前判断】市场偏弱" in result.public_answer
    assert "【证据边界】" in result.public_answer


def test_empty_remainder_of_lost_slot_has_no_apology_banner() -> None:
    """③ 残块为空（块仅一句且该句被合法删除）→ 无该块、不挂道歉横幅。"""

    draft = (
        "【直接判断】若指数跌破99999点则主线成立。"
        "【证据边界】仅覆盖 2026-07-23 日频盘面。"
    )
    frame, structural = _two_slot_structural(draft)

    result = _verify(frame, structural, _judge(True))

    assert "99999点" not in result.public_answer
    assert "【直接判断】" not in result.public_answer
    assert "【证据边界】" in result.public_answer
    assert result.gap_output_ids == ("direct_assessment",)
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer


def test_sanitized_empty_remainder_has_no_apology_banner() -> None:
    """③ 整份剩余被 sanitize 掏空时也不挂「现有证据不足」横幅。"""

    frame, structural = _structural("market_data")
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        ("direct_assessment",),
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )

    assert result.gap_output_ids == ("direct_assessment",)
    assert result.status == "partial"
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer
    assert "现有证据不足" not in result.public_answer


def test_full_wipe_still_keeps_c3_banner() -> None:
    """④ 全灭 → 横幅保留（C3 回归钉）。"""

    frame, structural = _structural(
        "【当前判断】据E90，市场下跌。据E99显示下跌。据E98显示流入。据E97显示反转。"
    )
    calls = 0

    def judge(_request):
        nonlocal calls
        calls += 1
        rejected = 1 if calls == 3 else 2
        return {
            "passed": False,
            "rejected_sentence_indexes": [rejected],
            "issues": [f"第{rejected}句无据"],
        }

    result = _verify(frame, structural, judge)

    assert result.repair_withheld is True
    assert "repair_wiped_all_outputs" in " ".join(result.issues)
    assert "【当前判断】据E90，市场下跌" in result.public_answer
    assert result.gap_output_ids == ()
    assert REQUIRED_OUTPUT_DEGRADED_MARK not in result.public_answer


def test_degraded_block_annotation_is_visible_on_public_answer() -> None:
    """⑤ 降级块标注在公开稿可见。"""

    draft = (
        "【直接判断】当日主线仍是电网设备。"
        "成交额 530.96 亿来自问句日预取。"
        "【证据边界】仅覆盖日频盘面。"
    )
    frame, structural = _two_slot_structural(draft)
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        ("direct_assessment",),
        judge_issues=("semantic repair removed required output: direct_assessment",),
        correlated_judge=True,
    )

    assert REQUIRED_OUTPUT_DEGRADED_MARK in result.public_answer
    assert "成交额 530.96" in result.public_answer
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer


def test_degrade_note_does_not_dump_contract_or_point_at_removed_appendix() -> None:
    """厨房 8820：降级前缀把 _OUTPUT_DESCRIPTIONS 和「详见输出质检」端上桌。"""

    long_assessment = (
        "列出观察名单：股票名称 + 六位代码 + 角色（机会 / 出清或风险），"
        "不得只写行业形容词"
    )
    long_boundary = (
        "给出条件化情景树：路径分支 + 同一现象的互斥因果假说"
        "（裁决须带证据编号，裁不了写并立）"
    )
    frame = replace(
        _frame(),
        required_outputs=("direct_assessment", "evidence_boundary"),
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="市场成交额与结构观察",
        source="行情快照",
        source_date="2026-07-22",
        content_hash="HASH_PRIVATE_SENTINEL",
    )
    contract = ResearchTaskContract(
        task_id="w1-contract-leak",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                long_assessment,
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "evidence_boundary",
                long_boundary,
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data",),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    draft = (
        "【直接判断】当日主线仍是电网设备。"
        "成交额 530.96 亿来自问句日预取。"
        "【证据边界】仅覆盖日频盘面。"
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
            OutputEvidenceBinding("evidence_boundary", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    structural = verify_episode_outcome(contract, outcome)
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        ("direct_assessment",),
        judge_issues=("semantic repair removed required output: direct_assessment",),
        correlated_judge=True,
    )

    assert REQUIRED_OUTPUT_DEGRADED_MARK in result.public_answer
    assert "成交额 530.96" in result.public_answer
    assert "详见「输出质检」" not in result.public_answer
    assert "六位代码" not in result.public_answer
    assert "不得只写行业形容词" not in result.public_answer
    assert "互斥因果假说" not in result.public_answer


def test_semantic_quality_reject_keeps_required_block_remainder() -> None:
    """V8 主钉：第 3 句语义否决留下 + 存疑标；残块保留、不挂横幅。"""

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
    assert SEMANTIC_QUALITY_DOUBT_MARK in result.public_answer
    assert "【直接判断】当日主线仍是电网设备" in result.public_answer
    assert "成交额 530.96" in result.public_answer
    assert "质量不够" in " ".join(result.issues)
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer


_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ceiling-degrade"


def _replay_marker_loss(name: str):
    payload = json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))
    lost = tuple(payload["lost_output_ids"])
    frame, structural = _structural(str(payload["wiped_draft"]))
    result = SemanticEpisodeVerifier(
        judge_fn=_judge(True)
    )._marker_loss_partial_public(
        frame,
        structural,
        lost,
        judge_issues=("semantic repair removed required output",),
        correlated_judge=True,
    )
    return payload, result


def test_replay_huangshi_keeps_remainder_without_apology_banner() -> None:
    payload, result = _replay_marker_loss("huangshi-direct-assessment.json")
    assert payload["before_had_banner"] is True
    assert result.gap_output_ids == tuple(payload["lost_output_ids"])
    assert REQUIRED_OUTPUT_DEGRADED_MARK in result.public_answer
    for snippet in payload["must_keep"]:
        assert snippet in result.public_answer
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer


def test_replay_taichenguang_keeps_remainder_without_apology_banner() -> None:
    payload, result = _replay_marker_loss("taichenguang-counterpoint.json")
    assert payload["before_had_banner"] is True
    assert result.gap_output_ids == tuple(payload["lost_output_ids"])
    assert REQUIRED_OUTPUT_DEGRADED_MARK in result.public_answer
    for snippet in payload["must_keep"]:
        assert snippet in result.public_answer
    for banner in _APOLOGY_MARKERS:
        assert banner not in result.public_answer
