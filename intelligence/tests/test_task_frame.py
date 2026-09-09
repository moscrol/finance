from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from intelligence.services.query_understanding import QueryEnvelope, understand_query
from intelligence.services.task_frame import (
    MISSING_MATERIAL_CLARIFICATION,
    TaskFrame,
    align_task_frame,
    build_task_frame,
    derive_required_outputs,
    is_weekly_calendar_question,
    rebase_task_frame,
    resolve_task_frame_clarification,
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


# 2026-09-04 预算矩阵 B6 两次开闸 run 里对齐模型真实写出的 ambiguities（题面
# 「2026-07-23 把这份卖方材料提纯一下…」没附材料）。修前两条都认不出 → None →
# 研究车道 → 模型稿「材料缺失请提供原文」被结构校验丢弃、发布层换成证据不足模板。
_B6_QUESTION = "2026-07-23 把这份卖方材料提纯一下，哪些是硬事实、哪些只能进图谱、哪些只能进观察列表"
_B6_AMBIGUITIES = (
    "'这份卖方材料'所指文档完全缺失，需用户提供原文或粘贴内容",
    "'这份卖方材料'具体指哪份：需用户提供材料原文、文件、标题或来源链接，"
    "当前上下文中不存在任何可指代的对象；材料的发布时间与覆盖标的是否与 timeframe "
    "2026-07-23 一致也待确认。",
)


def _b6_frame() -> TaskFrame:
    return build_task_frame(_B6_QUESTION, understand_query(_B6_QUESTION))


@pytest.mark.parametrize("ambiguity", _B6_AMBIGUITIES)
def test_missing_material_ambiguity_asks_for_the_material(ambiguity: str) -> None:
    frame = _b6_frame()
    assert frame.clarification_question is None

    content = f'{{"user_goal": "提纯卖方材料", "assumptions": [], "ambiguities": ["{ambiguity}"]}}'
    aligned = align_task_frame(frame, content)

    assert aligned.clarification_question == MISSING_MATERIAL_CLARIFICATION
    assert ambiguity in aligned.ambiguities


@pytest.mark.parametrize(
    "ambiguity",
    (
        # 模型自己给了默认处置：不是阻塞，不追问（否则每条「先按…」都会变成一轮追问）。
        "研报发布日期未提供，先按 2026-07-23 处理",
        "材料口径未给出，默认按公告口径继续",
        # 没有材料名词：现有行为，仍不追问（对应上面 test_llm_alignment_* 那条）。
        "观察窗口未明确，先按未来五个交易日评估",
        "三档分级的判据边界未定义，需确认按默认证据政策还是用户自定义标准执行",
    ),
)
def test_non_blocking_ambiguity_does_not_ask_for_material(ambiguity: str) -> None:
    content = f'{{"user_goal": "x", "assumptions": [], "ambiguities": ["{ambiguity}"]}}'
    aligned = align_task_frame(_b6_frame(), content)
    assert aligned.clarification_question is None


def test_missing_material_answer_is_not_read_as_a_subject() -> None:
    aligned = align_task_frame(
        _b6_frame(),
        f'{{"user_goal": "提纯", "assumptions": [], "ambiguities": ["{_B6_AMBIGUITIES[0]}"]}}',
    )
    pasted = "【卖方研报正文】公司 2026 年上半年新签订单 12 亿元，同比增长 40%；" * 6

    resumed = resolve_task_frame_clarification(aligned, pasted)

    # 主体 / 类型原样保留——贴进来的是材料，不是主体名；修前这里会被 _safe_subject
    # 判掉再默认成「A股市场 / market_pattern」，把提纯题改写成盘面题。
    assert resumed.subject == aligned.subject
    assert resumed.subject_kind == aligned.subject_kind
    assert resumed.question_type == aligned.question_type
    assert resumed.clarification_question is None
    assert resumed.ambiguities == ()
    assert any("补充了材料原文" in item for item in resumed.assumptions)


def test_rebound_clarification_answer_still_resolves_subject() -> None:
    # 原有主体澄清路径不受材料分支影响。
    question = "这个反弹还能持续多久"
    frame = build_task_frame(question, understand_query(question))
    assert frame.clarification_question == "你希望我围绕哪个明确主体继续判断？"

    resumed = resolve_task_frame_clarification(frame, "美股")

    assert resumed.subject == "美国股市"
    assert resumed.market_scope == "美股"
    assert resumed.clarification_question is None


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


# --- 输入理解层（2026-09-09，05 单） -------------------------------------------------

import json  # noqa: E402
from dataclasses import replace  # noqa: E402

from intelligence.services.task_frame import (  # noqa: E402
    MISSING_MATERIAL_AMBIGUITY,
    render_task_understanding,
    task_frame_requires_retrieval,
)
from intelligence.services.user_task import (  # noqa: E402
    METHOD_STATUS_UNVERIFIED,
    Hypothesis,
    MaterialRef,
    MethodCandidate,
    material_id_for,
)

_REPORT = (
    "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n\n"
    "一、核心观点\n公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年，"
    "预计 2027 年一季度满产。管理层在电话会中表示下游两家电池厂已完成 A 样验证。\n\n"
    "二、关键数据\n2026 年上半年新签订单 12 亿元，同比增长 40%；毛利率 31.5%（去年同期 27.2%）。\n\n"
    "三、我们的判断\n我们认为硫化物路线将在 2027 年替代氧化物成为主流，公司 A 是最大受益者，目标价上调 30%。"
)
_REPORT_QUESTION = "这篇研报的核心逻辑站得住吗？帮我分开哪些是硬事实、哪些只是推测"
_EMPTY_CONTEXT = "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n## 最近消息原文\n（无历史消息）"


def _frame_for(question: str, **kwargs) -> TaskFrame:
    return build_task_frame(question, understand_query(question), **kwargs)


def test_input_understanding_fields_default_empty_and_stay_out_of_payload() -> None:
    frame = _frame_for("明天你怎么看")
    payload = frame.to_dict()

    for key in ("user_premises", "materials", "referenced_material_ids", "competing_explanations", "method_candidates"):
        assert key not in payload
    assert TaskFrame.from_dict(payload) == frame
    # 旧写法：13 个位置参数照常可用，与带默认值的同帧同哈希。
    legacy = TaskFrame(
        frame.raw_question, frame.user_goal, frame.question_type, frame.subject, frame.subject_kind,
        frame.market_scope, frame.timeframe, frame.required_outputs, frame.assumptions, frame.ambiguities,
        frame.clarification_question, frame.evidence_policy, frame.confidence,
    )
    assert legacy.task_frame_hash == frame.task_frame_hash


def test_input_understanding_fields_round_trip_through_dict() -> None:
    frame = replace(
        _theme_frame(_THEME_ANALYSIS_DEFAULTS),
        user_premises=("龙头不涨了（用户观察）",),
        materials=(MaterialRef("m-abc", "table", "表格：板块", 120, headers=("板块", "涨停家数"), rows=5),),
        referenced_material_ids=("m-abc",),
        competing_explanations=(Hypothesis("退潮", "双红消失", ("涨停家数",)),),
        method_candidates=(MethodCandidate("龙头断板", "板块回流", "未说明", ("大盘缩量",)),),
    )
    payload = frame.to_dict()

    assert payload["materials"][0]["headers"] == ["板块", "涨停家数"]
    assert payload["method_candidates"][0]["status"] == METHOD_STATUS_UNVERIFIED
    restored = TaskFrame.from_dict(payload)
    assert restored == frame
    assert restored.task_frame_hash == frame.task_frame_hash
    assert restored.task_frame_hash != _theme_frame(_THEME_ANALYSIS_DEFAULTS).task_frame_hash


def test_pasted_report_routes_on_the_question_and_registers_the_material() -> None:
    frame = _frame_for(f"{_REPORT}\n\n{_REPORT_QUESTION}")

    assert frame.question_type == "kol_review"
    assert frame.raw_question.startswith("【卖方摘要")
    assert len(frame.materials) == 1
    material = frame.materials[0]
    assert material.kind == "pasted_text"
    assert material.material_id == material_id_for(_REPORT)
    assert "2026-08-28" in material.dates
    assert any(material.material_id in item for item in frame.assumptions)
    # 材料里的日期不是用户要查的交易日：不得触发日历休市假设。
    assert not any("休市" in item for item in frame.assumptions)
    assert frame.clarification_question is None


def test_pasted_table_keeps_headers_on_the_frame() -> None:
    table = "板块\t涨停家数\t成交额(亿)\t成交额环比\n固态电池\t14\t612\t+18%\n液冷\t9\t388\t-6%"
    frame = _frame_for(f"{table}\n\n从这张表看哪条线最强，量能跟得上吗")

    assert frame.materials[0].kind == "table"
    assert frame.materials[0].headers == ("板块", "涨停家数", "成交额(亿)", "成交额环比")
    assert frame.question_type != "dated_market_review"


def test_unbound_line_market_feel_asks_once_then_continues_as_theme() -> None:
    frame = _frame_for("龙头不涨了，是不是这条线要退潮了")

    assert frame.clarification_question == "你希望我围绕哪个明确主体继续判断？"
    assert frame.subject is None
    assert [item.label for item in frame.competing_explanations][0] == "主线退潮"
    assert frame.user_premises == ("龙头不涨了（用户观察）",)
    assert frame.user_goal.startswith("区分竞争解释")

    resumed = resolve_task_frame_clarification(frame, "固态电池")

    assert resumed.subject == "固态电池"
    assert resumed.subject_kind == "theme"
    assert resumed.clarification_question is None
    assert resumed.competing_explanations == frame.competing_explanations


def test_named_market_feel_gets_discriminating_goal_without_clarification() -> None:
    frame = _frame_for("固态电池主线最近有没有走弱")

    assert frame.subject == "固态电池"
    assert frame.clarification_question is None
    assert frame.user_goal.startswith("区分竞争解释（退潮")
    assert all(item.observables for item in frame.competing_explanations)


def test_paraphrase_keeps_goal_and_clarification() -> None:
    a = _frame_for("龙头不涨了，是不是这条线要退潮了")
    b = _frame_for("龙头开始不涨了，这条线是不是要退潮")

    assert a.user_goal == b.user_goal
    assert a.competing_explanations == b.competing_explanations
    assert bool(a.clarification_question) == bool(b.clarification_question)


def test_nickname_pair_becomes_comparison_subjects_with_assumption() -> None:
    frame = _frame_for("宁王和迪王现在谁的估值更贵")

    assert frame.subject == "宁德时代、比亚迪"
    assert frame.subject_kind == "company"
    assert any("宁王=宁德时代" in item and "迪王=比亚迪" in item for item in frame.assumptions)
    assert frame.clarification_question is None


def test_method_description_is_recorded_as_unverified_candidate() -> None:
    frame = _frame_for("我的经验是龙头连板断了以后板块一般还有一次回流，这次固态电池也会这样吗")

    assert frame.subject == "固态电池"
    assert frame.user_premises == ("龙头连板断了以后板块一般还有一次回流",)
    assert len(frame.method_candidates) == 1
    assert frame.method_candidates[0].condition == "龙头连板断了"
    assert frame.method_candidates[0].status == METHOD_STATUS_UNVERIFIED
    assert any("未经历史验证" in item for item in frame.assumptions)
    assert [item.label for item in frame.competing_explanations] == ["分歧后回流", "分歧转退潮"]


def test_missing_material_asks_deterministically_only_when_context_is_known() -> None:
    question = "2026-07-23 把这份卖方材料提纯一下，哪些是硬事实、哪些只能进图谱、哪些只能进观察列表"

    known_empty = _frame_for(question, conversation_context=_EMPTY_CONTEXT)
    assert known_empty.clarification_question == MISSING_MATERIAL_CLARIFICATION
    assert MISSING_MATERIAL_AMBIGUITY in known_empty.ambiguities
    assert known_empty.materials == ()
    # 没有凭标题编出任何材料内容。
    assert not any("硫化物" in item or "亿元" in item for item in known_empty.assumptions)

    unknown = _frame_for(question)
    assert unknown.clarification_question is None
    assert unknown.ambiguities == ()


def test_material_reference_binds_to_earlier_material_in_context() -> None:
    block = (
        "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n## 最近消息原文\n"
        f"user: {_REPORT}\n\n{_REPORT_QUESTION}\nassistant: 硬事实有三条……"
    )
    frame = _frame_for("这篇里提到的产能数字有官方来源吗", conversation_context=block)

    assert frame.referenced_material_ids == (material_id_for(_REPORT),)
    assert frame.clarification_question is None
    assert any(material_id_for(_REPORT) in item for item in frame.assumptions)
    assert task_frame_requires_retrieval(frame)


def test_material_clarification_answer_attaches_material_identity() -> None:
    aligned = align_task_frame(
        _b6_frame(),
        f'{{"user_goal": "提纯", "assumptions": [], "ambiguities": ["{_B6_AMBIGUITIES[0]}"]}}',
    )
    resumed = resolve_task_frame_clarification(aligned, _REPORT)

    assert resumed.question_type == aligned.question_type
    assert [item.material_id for item in resumed.materials] == [material_id_for(_REPORT)]
    assert any(material_id_for(_REPORT) in item for item in resumed.assumptions)
    assert resumed.clarification_question is None


def test_align_task_frame_merges_model_supplied_input_understanding() -> None:
    frame = _frame_for("龙头不涨了，是不是这条线要退潮了")
    content = json.dumps(
        {
            "user_goal": "判断固态电池是否退潮",
            "assumptions": [],
            "ambiguities": [],
            "user_premises": ["用户认为龙头是风向标"],
            "competing_explanations": [
                {"label": "主线退潮", "claim": "重复的", "observables": ["x"]},
                {"label": "外资流出", "claim": "北向资金撤离", "observables": ["北向净流入"]},
            ],
            "method_candidates": [
                {"condition": "龙头不涨", "expectation": "板块退潮", "applicability": "任何时候", "status": "verified"}
            ],
        },
        ensure_ascii=False,
    )

    aligned = align_task_frame(frame, content)

    assert "用户认为龙头是风向标" in aligned.user_premises
    assert aligned.user_premises[0] == "龙头不涨了（用户观察）"
    labels = [item.label for item in aligned.competing_explanations]
    assert labels.count("主线退潮") == 1
    assert labels[-1] == "外资流出"
    assert aligned.method_candidates[0].status == METHOD_STATUS_UNVERIFIED


def test_render_task_understanding_lists_what_the_frame_holds() -> None:
    frame = _frame_for(f"{_REPORT}\n\n{_REPORT_QUESTION}")
    text = render_task_understanding(frame)

    assert "研究对象" in text and "要判断" in text and "需要的产出" in text
    assert material_id_for(_REPORT) in text
    assert "2026-08-28" in text

    feel = render_task_understanding(_frame_for("龙头不涨了，是不是这条线要退潮了"))
    assert "竞争解释" in feel and "待澄清" in feel
