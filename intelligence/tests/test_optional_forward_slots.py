"""可选前瞻槽（Optional Forward Slots）——离线钉。

Spec: docs/superpowers/specs/2026-08-24-optional-forward-slots-addendum.md
台账: R-20260824-20

分两步落地，本文件按步分节：
- §1 数值门豁免放宽（spec §5 案甲，钉 6/7/8）——对现存契约零行为变化。
- §2 装配层挂槽 + 动态提示规则（spec §4 案甲 + §3.2，钉 1-5/9-12）。
"""

from __future__ import annotations

import pytest

from intelligence.services.episode_semantic_verifier import (
    _novel_numeric_condition_indexes,
)
from intelligence.services.research_contract import (
    FORWARD_HYPOTHESIS_OUTPUT_IDS,
    RequiredOutput,
)
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
