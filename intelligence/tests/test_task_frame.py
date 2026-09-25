from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from intelligence.services.query_understanding import QueryEnvelope, understand_query
from intelligence.services.task_frame import (
    TaskFrame,
    build_task_frame,
    derive_required_outputs,
    is_weekly_calendar_question,
    rebase_task_frame,
    strip_default_a_share_search_token,
)


# 不命中 _explicit_required_outputs 四条正则中的任何一条，所以 rebase/build 都会
# 真的走进 _clean_outputs 分支。若换成会命中的措辞（如「和…哪个更…主线」），
# explicit 分支会直接返回，下面两条测试就测不到过滤，抽掉过滤也不会变红。
_NON_EXPLICIT_QUESTION = "固态电池产业链怎么分"
_THEME_ANALYSIS_DEFAULTS = ("direct_assessment", "chain_mapping", "counterpoint")


def _theme_frame(required_outputs: tuple[str, ...]) -> TaskFrame:
    return TaskFrame(
        raw_question=_NON_EXPLICIT_QUESTION,
        user_goal="梳理固态电池产业链",
        question_type="theme_analysis",
        subject="固态电池",
        subject_kind="theme",
        market_scope="A股",
        timeframe=None,
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )


def test_rebound_horizon_builds_stable_a_share_task_frame() -> None:
    question = "昨天的反弹能持续多久"

    envelope = understand_query(question)
    frame = envelope.task_frame

    assert frame is not None
    assert frame.raw_question == question
    assert frame.question_type == "market_forecast"
    assert frame.market_scope == "A股"
    assert frame.subject == "A股市场"
    assert frame.subject != question
    assert frame.timeframe == "最近交易日"
    assert {
        "current_baseline",
        "duration_assessment",
        "continuation_conditions",
        "invalidation_conditions",
        "evidence_boundary",
    }.issubset(frame.required_outputs)
    assert frame.to_dict()["task_frame_hash"] == frame.task_frame_hash
    with pytest.raises(FrozenInstanceError):
        frame.market_scope = "美股"  # type: ignore[misc]


def test_llm_alignment_can_only_supplement_code_owned_semantics() -> None:
    question = "昨天的反弹能持续多久"
    envelope = understand_query(question)
    content = """{
      "user_goal": "判断本轮反弹大致还能延续多久",
      "required_outputs": ["volume_confirmation"],
      "assumptions": ["把反弹理解为最近一个交易日的市场修复"],
      "ambiguities": ["观察窗口未明确，先按未来五个交易日评估"],
      "subject": "美股",
      "market_scope": "美股",
      "timeframe": "2020-01-01",
      "evidence_policy": "no_evidence"
    }"""

    frame = build_task_frame(
        question,
        envelope,
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert frame.user_goal == "判断本轮反弹大致还能延续多久"
    assert "volume_confirmation" not in frame.required_outputs
    assert "观察窗口未明确，先按未来五个交易日评估" in frame.ambiguities
    assert frame.clarification_question is None
    assert frame.subject == "A股市场"
    assert frame.market_scope == "A股"
    assert frame.timeframe == "最近交易日"
    assert frame.evidence_policy == "current_market_scenarios"


def test_llm_alignment_cannot_append_unowned_required_output() -> None:
    question = "固态电池产业链怎么分"
    envelope = understand_query(question)
    content = """{
      "user_goal": "梳理固态电池产业链",
      "required_outputs": ["llm_invented_output"],
      "assumptions": [],
      "ambiguities": []
    }"""

    frame = build_task_frame(
        question,
        envelope,
        llm_complete=lambda _messages: (content, object(), ""),
    )

    assert "chain_mapping" in frame.required_outputs
    assert "llm_invented_output" not in frame.required_outputs


@pytest.mark.parametrize(
    ("question", "required_outputs"),
    (
        (
            "低空经济和商业航天，未来一个月哪个更可能成为A股主线，为什么",
            {
                "comparison_conclusion",
                "supporting_evidence",
                "counterpoint",
                "invalidation_conditions",
            },
        ),
        (
            "如果电力板块涨停家数很多但成交占比和核心股承接下降，还能算主线吗",
            {
                "direct_assessment",
                "causal_chain",
                "counterpoint",
                "verification_conditions",
            },
        ),
        (
            "一个没有历史胜率的新题材，应该如何判断它是主线候选还是一天噪音",
            {
                "method",
                "evidence_hierarchy",
                "failure_modes",
                "verification_path",
            },
        ),
        (
            "那它什么时候算失效",
            {"invalidation_conditions", "supporting_evidence"},
        ),
    ),
)
def test_task_frame_preserves_explicit_long_tail_output_shape(
    question: str,
    required_outputs: set[str],
) -> None:
    frame = understand_query(question).task_frame

    assert frame is not None
    assert required_outputs.issubset(frame.required_outputs)


@pytest.mark.parametrize(
    ("question_type", "evidence_policy", "required_outputs"),
    (
        (
            "quick_fact",
            "current_fact_evidence",
            {"fact_value", "as_of_date", "evidence_boundary"},
        ),
        (
            "theme_track",
            "theme_tracking_evidence",
            {"change_summary", "supporting_evidence", "tracking_signals"},
        ),
        (
            "kol_review",
            "source_critique_evidence",
            {"claim_summary", "evidence_assessment", "biases_and_gaps"},
        ),
        (
            "comparison_analog",
            "comparable_multi_source_evidence",
            {"comparison_dimensions", "key_differences", "limits_of_analogy"},
        ),
        (
            "trade_advice",
            "conditional_thesis_evidence",
            {"conditional_thesis", "risk_signals", "invalidation_conditions"},
        ),
    ),
)
def test_route_table_types_keep_explicit_task_frame_semantics(
    question_type: str,
    evidence_policy: str,
    required_outputs: set[str],
) -> None:
    frame = build_task_frame(
        "按这个问题给出直接判断",
        QueryEnvelope(
            question_type=question_type,
            subject_kind="unknown",
            subject=None,
            decision_goal="回答用户的金融问题",
            timeframe=None,
            matched_by="explicit",
            confidence=0.9,
        ),
    )

    assert frame.question_type == question_type
    assert frame.evidence_policy == evidence_policy
    assert required_outputs.issubset(frame.required_outputs)
    assert frame.question_type != "general_finance_qa"


def test_task_frame_keeps_question_type_independent_from_shared_evidence_policy() -> None:
    frame = TaskFrame(
        raw_question="寻找历史类比",
        user_goal="比较相似性与差异",
        subject="AI行情",
        subject_kind="theme",
        market_scope="A股",
        timeframe=None,
        required_outputs=("comparison_dimensions",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="comparable_multi_source_evidence",
        confidence=0.9,
        question_type="comparison_analog",
    )

    restored = TaskFrame.from_dict(frame.to_dict())

    assert frame.question_type == "comparison_analog"
    assert restored is not None
    assert restored.question_type == "comparison_analog"


def test_task_frame_restores_legacy_payload_without_explicit_question_type() -> None:
    frame = build_task_frame(
        "2015互联网泡沫和现在AI行情有什么异同",
        QueryEnvelope(
            question_type="comparison_analog",
            subject_kind="theme",
            subject="AI行情",
            decision_goal="比较历史类比",
            timeframe=None,
            matched_by="explicit",
            confidence=0.9,
        ),
    )
    legacy_payload = frame.to_dict()
    legacy_payload.pop("question_type")

    restored = TaskFrame.from_dict(legacy_payload)

    assert restored is not None
    assert restored.question_type == "comparison_analog"


def test_rebase_drops_blank_output_ids_like_the_build_path() -> None:
    # 变异测试：把 rebase_task_frame 里的 _clean_outputs 换回裸 _merge_strings，
    # 本条必红——后者只过滤 falsy，而 "  " 是 truthy，会活着进 required_outputs。
    #
    # 空白 output_id 当不了槽位名，留着只会让 marker 覆盖的分母虚高一位。
    # 更要紧的是：build 路（derive_required_outputs）已经丢掉它，
    # 继承路若保留，同一个答案会因「frame 由哪条路造的」而被两个分母打分。
    frame = _theme_frame(_THEME_ANALYSIS_DEFAULTS)

    rebased = rebase_task_frame(
        frame,
        question_type="theme_analysis",
        subject="固态电池",
        required_outputs=("chain_mapping", "  ", "\t", "risk_signals"),
    )

    assert "  " not in rebased.required_outputs
    assert "\t" not in rebased.required_outputs
    assert all(item.strip() for item in rebased.required_outputs)
    # 真实槽位一个不少，过滤只针对空白。
    assert "risk_signals" in rebased.required_outputs
    assert set(_THEME_ANALYSIS_DEFAULTS).issubset(rebased.required_outputs)


def test_both_required_output_producers_share_one_blank_filter() -> None:
    # 两个 producer 都写 frame.required_outputs：build 路 derive_required_outputs，
    # 继承路 rebase_task_frame。03cb32fb 把 marker 覆盖判定提到 services 让两个
    # 引擎共用同一张表，producer 侧口径若还是两份，那次统一就被抵消了。
    blank_extra = ("  ",)

    built = derive_required_outputs(
        "theme_analysis",
        _NON_EXPLICIT_QUESTION,
        extra=blank_extra,
    )
    rebased = rebase_task_frame(
        _theme_frame(_THEME_ANALYSIS_DEFAULTS),
        question_type="theme_analysis",
        subject="固态电池",
        required_outputs=blank_extra,
    ).required_outputs

    assert built == rebased == _THEME_ANALYSIS_DEFAULTS


# --- 确定性日历事实注入（R15-C1/C2 生产形状） ------------------------------


def test_weekend_date_in_question_injects_non_trading_assumption() -> None:
    """「2026-07-25 市场怎么样」烧完整条研究链后答「证据不足」——
    而它是周六这件事一行日历代码就能判定。注入假设让模型直接回答。"""

    question = "2026-07-25 市场怎么样"
    frame = build_task_frame(question, understand_query(question))

    notes = [item for item in frame.assumptions if "休市" in item]
    assert notes, frame.assumptions
    assert "周六" in notes[0]
    assert "2026-07-24" in notes[0]


def test_holiday_metric_question_injects_closure_assumption() -> None:
    """「涨停家数」不带任何旧关键词也必须被认成财务问题（C2 形状），
    否则春节休市的日历事实整条落空。"""

    question = "2026-02-17 涨停家数多少"
    frame = build_task_frame(question, understand_query(question))

    notes = [item for item in frame.assumptions if "休市" in item]
    assert notes, frame.assumptions
    assert "2026-02-13" in notes[0]


def test_trading_day_date_injects_nothing() -> None:
    question = "2026-07-23 市场怎么样"
    frame = build_task_frame(question, understand_query(question))

    assert not [item for item in frame.assumptions if "休市" in item]


_CALENDAR_PROBE = "周末发酵了什么新闻？下周（8月24日-8月28日）有什么大事？"


def test_weekly_calendar_detector_needs_window_and_event() -> None:
    assert is_weekly_calendar_question(_CALENDAR_PROBE)
    assert is_weekly_calendar_question("下周有什么大事")
    assert not is_weekly_calendar_question("周末发酵了什么新闻？")
    assert not is_weekly_calendar_question("昨天的反弹能持续多久")
    assert not is_weekly_calendar_question("液冷题材现在怎么看")


def test_weekly_calendar_question_does_not_inherit_a_share_default() -> None:
    frame = build_task_frame(_CALENDAR_PROBE, understand_query(_CALENDAR_PROBE))

    assert frame.market_scope == "跨市场"
    assert "按A股市场理解" not in frame.assumptions


def test_explicit_a_share_calendar_keeps_named_market() -> None:
    question = "下周A股有什么大事？"
    frame = build_task_frame(question, understand_query(question))

    assert frame.market_scope == "A股"
    assert "按A股市场理解" not in frame.assumptions


def test_search_token_strips_default_a_share_on_calendar_only() -> None:
    cleaned, note = strip_default_a_share_search_token(
        "下周 A股 重要事件",
        _CALENDAR_PROBE,
    )
    assert "A股" not in cleaned
    assert "重要事件" in cleaned
    assert note

    kept, empty = strip_default_a_share_search_token(
        "下周 A股 重要事件",
        "下周A股有什么大事？",
    )
    assert kept == "下周 A股 重要事件"
    assert empty == ""

    unchanged, silent = strip_default_a_share_search_token(
        "周末 国常会 算力",
        _CALENDAR_PROBE,
    )
    assert unchanged == "周末 国常会 算力"
    assert silent == ""
