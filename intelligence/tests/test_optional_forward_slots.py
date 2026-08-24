"""可选前瞻槽（Optional Forward Slots）——离线钉。

Spec: docs/superpowers/specs/2026-08-24-optional-forward-slots-addendum.md
台账: R-20260824-20

分两步落地，本文件按步分节：
- §1 数值门豁免放宽（spec §5 案甲，钉 6/7/8）——对现存契约零行为变化。
- §2 装配层挂槽 + 动态提示规则（spec §4 案甲 + §3.2，钉 1-5/9-12）。
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import (
    _ADVISORY_OUTPUT_IDS,
    build_episode_context,
)
from intelligence.services.episode_protocol import (
    EpisodeFinishRejection,
    _question_type_rules,
    validate_episode_finish,
)
from intelligence.services.episode_semantic_verifier import (
    _novel_numeric_condition_indexes,
)
from intelligence.services.research_contract import (
    FORWARD_HYPOTHESIS_OUTPUT_IDS,
    RequiredOutput,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.tests.test_episode_semantic_verifier import _structural

# 稿里这个阈值不在证据里——数值门只有在豁免触发时才会放它过。
_UNSUPPORTED_THRESHOLD_DRAFT = (
    "【当前判断】市场偏弱。若指数跌破3870点则失效。【证据边界】数据截至2026-07-22。"
)
_CONDITION_SENTENCE = [
    {"index": 0, "text": "若指数跌破3870点则失效。"},
]

_EVIDENCE_ASSESSMENT = RequiredOutput(
    "direct_assessment", "直接判断", ("market_data",), True
)
_EVIDENCE_BOUNDARY = RequiredOutput(
    "evidence_boundary", "证据边界", ("market_data",), True
)


def _forward_slot(
    output_id: str,
    *,
    required: bool,
    grounding_mode: str = "model_reasoning",
) -> RequiredOutput:
    return RequiredOutput(
        output_id,
        f"{output_id} 描述",
        (),
        required,
        grounding_mode,  # type: ignore[arg-type]
    )


def _condition_indexes(required_outputs: tuple[RequiredOutput, ...]):
    """跑数值门的条件句豁免判定，返回被判「无据」的句号。"""

    _, verified = _structural(
        _UNSUPPORTED_THRESHOLD_DRAFT,
        required_outputs=required_outputs,
    )
    return _novel_numeric_condition_indexes(_CONDITION_SENTENCE, verified)


# --------------------------------------------------------------------------
# §1 数值门豁免放宽（spec §5 案甲）
# --------------------------------------------------------------------------


@pytest.mark.parametrize("output_id", sorted(FORWARD_HYPOTHESIS_OUTPUT_IDS))
def test_optional_forward_slot_exempts_condition_threshold(output_id: str) -> None:
    """钉 6：可选前瞻槽签 model_reasoning 时，条件句阈值不再进机械删除。

    这是本单的目的本身。改动前 ``item.required and`` 会把 required=False 的
    前瞻槽滤掉 → condition_items 为空 → 豁免不触发 → 阈值句照删。
    """

    indexes = _condition_indexes(
        (
            _EVIDENCE_ASSESSMENT,
            _EVIDENCE_BOUNDARY,
            _forward_slot(output_id, required=False),
        )
    )

    assert indexes == ()


def test_contract_without_forward_slot_still_deletes_threshold() -> None:
    """钉 7：无前瞻槽的契约照删——V8 回归锚的同形断言。

    与 ``test_numeric_unsupported_sentence_is_still_deleted`` 同一形状：
    本单绕开那条钉靠的是换动刀位置，不是放宽它。
    """

    indexes = _condition_indexes((_EVIDENCE_ASSESSMENT, _EVIDENCE_BOUNDARY))

    assert indexes == (0,)


@pytest.mark.parametrize("blocker_required", [True, False])
def test_mixed_signing_does_not_exempt(blocker_required: bool) -> None:
    """钉 8：混合签约 fail-closed 向证据侧。

    契约里只要有**一个** evidence 签约的前瞻槽，豁免就不触发（``all()`` 语义）。
    ``blocker_required`` 两档同时覆盖 spec §5.2 的零行为变化论证腿 2——W2 不可达
    降级产出的正是 ``required=False`` 且仍 evidence 的槽。
    """

    indexes = _condition_indexes(
        (
            _EVIDENCE_ASSESSMENT,
            _EVIDENCE_BOUNDARY,
            _forward_slot(
                "invalidation_conditions",
                required=blocker_required,
                grounding_mode="evidence",
            ),
            _forward_slot("scenario_paths", required=False),
        )
    )

    assert indexes == (0,)


def test_required_forward_slot_still_exempts() -> None:
    """零行为变化腿 4：market_forecast 那样的必选前瞻槽，改前改后都豁免。"""

    indexes = _condition_indexes(
        (
            _EVIDENCE_ASSESSMENT,
            _EVIDENCE_BOUNDARY,
            _forward_slot("scenario_paths", required=True),
        )
    )

    assert indexes == ()


def test_advisory_optional_slot_does_not_exempt() -> None:
    """可选性本身不是豁免理由——只有**前瞻**槽才进 condition_items。

    prior_recall 这类 advisory 槽 required=False，但它不在
    ``FORWARD_HYPOTHESIS_OUTPUT_IDS`` 里，不该让阈值句蒙混过关。
    这条钉防的是「把过滤条件放得太宽」那种过头修法。
    """

    indexes = _condition_indexes(
        (
            _EVIDENCE_ASSESSMENT,
            _EVIDENCE_BOUNDARY,
            _forward_slot("prior_recall", required=False, grounding_mode="user_premise"),
        )
    )

    assert indexes == (0,)


# --------------------------------------------------------------------------
# §2 装配层挂槽 + 动态提示规则（spec §4 案甲 + §3.2）
# --------------------------------------------------------------------------

_FORWARD_SIGNAL_QUESTION = "当前 A 股后市会怎么走"
_NO_SIGNAL_QUESTION = "固态电池产业链的核心环节有哪些"


def _task_frame(
    *,
    question: str,
    question_type: str,
    required_outputs: tuple[str, ...],
    user_goal: str = "形成条件化判断",
) -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal=user_goal,
        question_type=question_type,
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="当前",
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _contract_outputs(frame: TaskFrame):
    # task_id 唯一：`research_contract` 按 episode 登记活跃根预算，重名直接抛
    # 「root budget already exists」，与被测行为无关。
    context = build_episode_context(
        frame,
        task_id=f"forward-slots-{uuid4().hex}",
    )
    return context, {
        item.output_id: item for item in context.contract.required_outputs
    }


def test_forward_signal_mounts_optional_slots() -> None:
    """钉 1：非前瞻题型 + 前瞻信号 → 三槽以可选 model_reasoning 挂上。"""

    frame = _task_frame(
        question=_FORWARD_SIGNAL_QUESTION,
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )

    _, outputs = _contract_outputs(frame)

    for output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS:
        item = outputs[output_id]
        assert item.required is False
        assert item.grounding_mode == "model_reasoning"
        assert item.evidence_types == ()
    # 原有槽的必选性与签法不受影响。
    assert outputs["evidence_boundary"].required is True
    assert outputs["evidence_boundary"].grounding_mode == "evidence"


def test_native_forward_question_type_is_untouched() -> None:
    """钉 2：market_forecast 逐字段不变——不重复挂、不降级必选前瞻槽。"""

    frame = _task_frame(
        question=_FORWARD_SIGNAL_QUESTION,
        question_type="market_forecast",
        required_outputs=(
            "direct_assessment",
            "scenario_paths",
            "continuation_conditions",
            "invalidation_conditions",
            "evidence_boundary",
        ),
    )

    context, outputs = _contract_outputs(frame)

    assert len(context.contract.required_outputs) == len(
        set(context.contract.required_outputs)
    )
    for output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS:
        item = outputs[output_id]
        assert item.required is True, "必选前瞻槽不得被本单降级"
        assert item.grounding_mode == "model_reasoning"


def test_existing_forward_slot_blocks_mounting() -> None:
    """钉 3：契约已有前瞻槽 → 交集判据拦下，evidence 签约保持。

    market_technical 的失效位应来自行情数据（支撑/均线是可查的），
    「技术位必须可查」这条下限不因前瞻信号而失守。
    """

    frame = _task_frame(
        question=_FORWARD_SIGNAL_QUESTION,
        question_type="market_technical",
        required_outputs=(
            "direct_assessment",
            "invalidation_conditions",
            "evidence_boundary",
        ),
    )

    _, outputs = _contract_outputs(frame)

    assert "scenario_paths" not in outputs
    assert "continuation_conditions" not in outputs
    assert outputs["invalidation_conditions"].required is True
    assert outputs["invalidation_conditions"].grounding_mode == "evidence"


def test_no_forward_signal_does_not_mount() -> None:
    """钉 4：同题型、无前瞻信号 → 不挂。"""

    frame = _task_frame(
        question=_NO_SIGNAL_QUESTION,
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )

    _, outputs = _contract_outputs(frame)

    assert not FORWARD_HYPOTHESIS_OUTPUT_IDS & set(outputs)


def test_evidence_free_task_does_not_mount() -> None:
    """钉 5：方法论题不挂——数值门整体豁免已覆盖，挂槽纯属污染契约。"""

    frame = _task_frame(
        question="均线怎么看",
        question_type="methodology_discussion",
        required_outputs=("method", "evidence_boundary"),
        user_goal="讲清方法",
    )

    _, outputs = _contract_outputs(frame)

    assert not FORWARD_HYPOTHESIS_OUTPUT_IDS & set(outputs)


def test_mounted_slots_do_not_block_completed() -> None:
    """钉 9：不绑三槽照样 completed——可选性真的生效。"""

    frame = _task_frame(
        question=_FORWARD_SIGNAL_QUESTION,
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )
    context, _ = _contract_outputs(frame)
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="市场成交额与结构观察",
        source="行情快照",
        source_date="2026-07-22",
        content_hash="HASH_PRIVATE_SENTINEL",
    )
    finish = json.dumps(
        {
            "status": "completed",
            "draft": "【直接回答】结构偏强。【证据边界】数据截至2026-07-22。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": item.output_id,
                    # 绑定跟着签法走：这道题命中 #72，direct_answer 本就是
                    # model_reasoning，与本单挂的三槽无关。
                    "evidence_hashes": (
                        ["E1"] if item.grounding_mode == "evidence" else []
                    ),
                    "basis": item.grounding_mode,
                }
                for item in context.contract.required_outputs
                if item.required
            ],
        }
    )

    result = validate_episode_finish(
        json.loads(finish),
        context=context,
        evidence=(evidence,),
    )

    assert result.status == "completed"


def test_binding_forward_slot_with_evidence_basis_is_rejected() -> None:
    """钉 10：可选前瞻槽绑 basis=evidence 仍被 basis_mismatch 拒。

    闸门是既有的；本钉确认挂槽没把它绕过去。**模型知不知道该报
    model_reasoning 是另一回事**，那由钉 11 管——两条缺一，这一格就从
    「闸门回归」变成生产必经的失败路径。
    """

    frame = _task_frame(
        question=_FORWARD_SIGNAL_QUESTION,
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )
    context, _ = _contract_outputs(frame)
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场快照",
        detail="市场成交额与结构观察",
        source="行情快照",
        source_date="2026-07-22",
        content_hash="HASH_PRIVATE_SENTINEL",
    )
    payload = {
        "status": "partial",
        "draft": "【情景路径】若指数跌破3870点则转弱。",
        "gaps": [],
        "bindings": [
            {
                "output_id": "scenario_paths",
                "evidence_hashes": ["E1"],
                "basis": "evidence",
            }
        ],
    }

    with pytest.raises(EpisodeFinishRejection) as excinfo:
        validate_episode_finish(payload, context=context, evidence=(evidence,))

    assert excinfo.value.code == "basis_mismatch"


def test_prompt_tells_the_model_which_basis_to_use() -> None:
    """钉 11：提示词必须带得动 basis——§3.2 的坑本坑。

    契约渲染只发 id/description/evidence_types/required，`grounding_mode`
    不在其中；模型对齐不了一个它看不见的字段，而 basis 默认是 evidence。
    没有这条动态规则，模型每绑一次这三格就被整份拒一次。
    """

    frame = _task_frame(
        question=_FORWARD_SIGNAL_QUESTION,
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )
    context, _ = _contract_outputs(frame)

    rules = _question_type_rules(frame, context)

    assert "model_reasoning" in rules
    assert "basis 用 model_reasoning" in rules
    # 可选性也要说明，否则模型会为了填格硬凑情景（§4.2 的误触发代价）。
    assert "不绑不算失败" in rules


def test_prompt_rule_absent_without_mounted_slots() -> None:
    """钉 11 的对照：没挂槽的题不该拿到这条规则。"""

    frame = _task_frame(
        question=_NO_SIGNAL_QUESTION,
        question_type="general_finance_qa",
        required_outputs=("direct_answer", "evidence_boundary"),
    )
    context, _ = _contract_outputs(frame)

    assert "basis 用 model_reasoning" not in _question_type_rules(frame, context)


def test_advisory_set_is_not_mutated() -> None:
    """钉 12：可选性不外溢——三槽绝不能被塞进全局 advisory 集合。

    塞进去会把 market_forecast 的**必选**前瞻槽一起降成可选。这条直接断言
    集合内容，不依赖钉 2 间接覆盖。
    """

    assert not FORWARD_HYPOTHESIS_OUTPUT_IDS & _ADVISORY_OUTPUT_IDS
