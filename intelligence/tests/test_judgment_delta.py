"""判断增量筛材料（q17 Q8 回灌 / R4 收窄版）的验收判据。

复核笔记给的两条判据逐条落在这里：
1. 同一材料包灌入大量重复利好 → 线索集合与待验证问题不变；
2. 加入一条有力反证 → 它必须进入模型可见窗口，且排在确认性材料之前。

第 2 条配一条**反向对照**（``counter_floor=0`` 时反证掉出窗口）：没有它，这个样本
就证明不了保底子句在干活——十三条材料、窗口十二位，反证碰巧留下也说得通。
"""

from __future__ import annotations

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.evidence_window import select_agent_evidence
from intelligence.services.judgment_delta import (
    ROLE_COUNTER,
    ROLE_NEW_FACT,
    ROLE_REPEAT,
    ROLE_UNVERIFIED,
    build_judgment_delta_guidance,
    build_judgment_delta_guidance_for_episode,
    classify_material,
    classify_role,
    counter_evidence_floor_order,
    episode_judgment_delta_rule,
    judgment_delta_guidance_for_query,
    judgment_delta_receipt,
    missing_judgment_delta_elements,
    parse_judgment_delta_intent,
)

QUERY = "英维克这笔液冷订单怎么看"


def _item(
    title: str,
    detail: str = "",
    source: str = "媒体",
    source_date: str = "2026-09-10",
    **kwargs: object,
) -> AgentEvidence:
    return AgentEvidence(
        tool="news_search",
        title=title,
        detail=detail or "公司公告中标 3.2 亿元液冷订单",
        source=source,
        source_date=source_date,
        **kwargs,  # type: ignore[arg-type]
    )


def _duplicate_flood(count: int) -> list[AgentEvidence]:
    """同一笔订单的 N 篇转述稿：标题带各家媒体的体例噪声，主干一致。"""
    outlets = ("财联社", "证券时报", "新浪财经", "东方财富", "第一财经", "智通财经")
    return [
        _item(
            f"【{outlets[i % len(outlets)]}】英维克中标3.2亿元液冷订单",
            source=f"{outlets[i % len(outlets)]}-{i}",
        )
        for i in range(count)
    ]


# 真实的「被淹没」形状：反证来自弱源、措辞里一个问句关键词都没有，相关性分天然垫底。
# 若把它写成「交易所公告称订单终止」，它自己就能排第一，样本也就证明不了保底子句。
_COUNTER = AgentEvidence(
    tool="web_search",
    title="客户资本开支指引下修",
    detail="海外客户三季度资本开支指引下修 15%",
    source="行业数据库",
    source_date="2026-09-10",
)


# ——————————————————————————————————————————— 判据 1：重复灌入不改变线索集合
def test_duplicate_flood_does_not_change_the_lead_set() -> None:
    few = classify_material([*_duplicate_flood(2), _COUNTER])
    many = classify_material([*_duplicate_flood(20), _COUNTER])

    assert len(few.leads) == len(many.leads) == 2
    assert {lead.role for lead in few.leads} == {lead.role for lead in many.leads}
    assert few.open_questions == many.open_questions
    # 合并数随灌入量涨，线索数不涨——这正是「合并」与「丢弃」的区别。
    assert few.merged_count == 1
    assert many.merged_count == 19


def test_merging_keeps_every_source() -> None:
    digest = classify_material(_duplicate_flood(6))
    lead = digest.leads[0]

    assert lead.duplicate_count == 6
    assert len(lead.sources) == 6
    assert "重复报道已并，出处保留" in digest.to_inline_note()


def test_no_material_is_dropped() -> None:
    """边界：不按「非主线」丢信息。每条输入都落在某条线索里。"""
    pack = [*_duplicate_flood(5), _COUNTER, _item("传闻英维克在谈第二笔订单")]
    digest = classify_material(pack)

    assert sum(lead.duplicate_count for lead in digest.leads) == len(pack)
    assert digest.input_count == len(pack)


# ——————————————————————————————————————————— 判据 2：反证进窗口且置顶
def test_counter_evidence_survives_a_flood_of_duplicate_good_news() -> None:
    pack = [*_duplicate_flood(12), _COUNTER]
    window = select_agent_evidence(QUERY, pack)

    assert _COUNTER in window
    assert window[0] is _COUNTER


def test_counter_floor_off_drops_the_counter_evidence() -> None:
    """反向对照：两条新子句都关掉，同一份材料包里的反证就挤不进窗口。

    这条红了才说明上一条测的是新行为，而不是运气——相关性排序把这条弱源反证排在
    十二篇转述稿之后，窗口只有十二位。
    """
    pack = [*_duplicate_flood(12), _COUNTER]
    window = select_agent_evidence(QUERY, pack, counter_floor=0, merge_duplicates=False)

    assert _COUNTER not in window


def test_merging_alone_saves_the_counter_but_does_not_rank_it_first() -> None:
    """两条子句各自管一件事：合并腾出窗口位，保底决定谁在最前。"""
    pack = [*_duplicate_flood(12), _COUNTER]
    window = select_agent_evidence(QUERY, pack, counter_floor=0, merge_duplicates=True)

    assert _COUNTER in window
    assert window[0] is not _COUNTER


def test_floor_order_promotes_at_most_floor_items() -> None:
    counters = [_item(f"订单被终止{i}", detail="客户公告终止合同") for i in range(5)]
    ordered = counter_evidence_floor_order([*_duplicate_flood(3), *counters], floor=2)

    assert ordered[:2] == counters[:2]
    assert len(ordered) == 8


def test_floor_zero_is_identity() -> None:
    pack = [*_duplicate_flood(3), _COUNTER]
    assert counter_evidence_floor_order(pack, floor=0) == pack


# ——————————————————————————————————————————— 角色判定
def test_roles() -> None:
    assert classify_role(_COUNTER) == ROLE_COUNTER
    assert classify_role(_item("英维克中标 3.2 亿元液冷订单")) == ROLE_NEW_FACT
    assert classify_role(_item("传闻英维克在谈第二笔订单", detail="知情人士称尚未公告")) == ROLE_UNVERIFIED
    assert classify_role(_item("液冷赛道持续受关注", detail="行业观点综述")) == ROLE_REPEAT


def test_contradicts_field_wins_over_word_face() -> None:
    """研究循环已标了立场时不再猜词面——这条材料一个反证词都没有。"""
    tagged = _item("英维克产能利用率数据", detail="Q2 产能利用率 61%", contradicts=("h1",))
    assert classify_role(tagged) == ROLE_COUNTER


def test_unverified_material_becomes_an_open_question() -> None:
    digest = classify_material([_item("传闻英维克在谈第二笔大单", detail="知情人士称尚未公告")])

    assert len(digest.open_questions) == 1
    assert "等哪份公开材料能证实" in digest.open_questions[0]


def test_counter_wins_inside_one_event_group() -> None:
    """同一事件里既有确认稿又有终止稿时，这条线索算反证，不被确认稿盖过去。"""
    same_event = [
        _item("英维克中标3.2亿元液冷订单", source="财联社"),
        _item("英维克中标3.2亿元液冷订单被终止", source="交易所公告"),
    ]
    digest = classify_material(same_event)

    assert digest.counter_count >= 1


# ——————————————————————————————————————————— 注入门
def test_material_question_types_route() -> None:
    for question_type in ("theme_analysis", "news_impact", "market_cause", "stock_deep_dive"):
        assert parse_judgment_delta_intent(QUERY, question_type)


def test_quick_and_definition_questions_do_not_route() -> None:
    for question_type in ("quick_fact", "concept_definition", "valuation_estimate", "market_data"):
        assert not parse_judgment_delta_intent(QUERY, question_type)
    assert judgment_delta_guidance_for_query("英维克收盘价多少", "quick_fact") == ""
    assert episode_judgment_delta_rule("英维克收盘价多少", "quick_fact") == ""


def test_word_face_fallback_only_when_type_missing() -> None:
    assert parse_judgment_delta_intent("液冷这波怎么看")
    assert not parse_judgment_delta_intent("英维克收盘价多少")


def test_guidance_carries_the_narrowed_rules() -> None:
    for text in (build_judgment_delta_guidance(), build_judgment_delta_guidance_for_episode()):
        assert "待验证问题" in text
        assert "裁判变量" in text
        assert "未发现足以推翻主判断的反证" in text
        # 收窄后的两条边界必须留在契约里，否则下一个人会把 R4 初版又捡回来。
        assert "不是主线" in text
        assert "主矛盾可以不止一条" in text
        assert "补关键缺口" in text  # 复用既有下一步词表，不另造


# ——————————————————————————————————————————— 程序核对与收据
_GOOD_ANSWER = """
主判断：订单确实落地，但客户侧存在终止风险。
反证：交易所公告显示该笔合同已被客户终止 [E3]（2026-09-10）。
待验证问题：
- 第二笔订单是否存在 —— 等公司公告或客户招标结果证实
裁判变量：
- 下一份客户资本开支指引 × 三季报窗口 × 若下修则本判断降级
下一步：
- 补关键缺口：调取客户公告原文与合同金额口径
"""


def test_good_answer_has_no_missing_elements() -> None:
    assert missing_judgment_delta_elements(_GOOD_ANSWER) == ()


def test_silent_answer_is_caught() -> None:
    missing = missing_judgment_delta_elements("订单落地，看好液冷方向。")

    assert set(missing) == {
        "counter_evidence",
        "open_questions",
        "decider_variables",
        "next_actions",
    }


def test_receipt_shape() -> None:
    receipt = judgment_delta_receipt(
        _GOOD_ANSWER,
        query=QUERY,
        question_type="theme_analysis",
        materials=[*_duplicate_flood(3), _COUNTER],
        as_of="2026-09-11",
    )

    assert receipt["check"] == "judgment_delta"
    assert receipt["judgment_delta_intent"] is True
    assert receipt["missing_elements"] == []
    assert receipt["decider_variables"]
    assert receipt["material_digest"]["role_counts"][ROLE_COUNTER] == 1
    assert receipt["material_digest"]["merged_count"] == 2


def test_receipt_stays_quiet_on_non_material_questions() -> None:
    receipt = judgment_delta_receipt("收盘价 12.3 元", query="收盘价多少", question_type="quick_fact")

    assert receipt["judgment_delta_intent"] is False
    assert receipt["missing_elements"] == []


# ——————————————————————————————————————————— episode 接缝：契约真到得了模型
def test_material_questions_get_the_contract_in_rules_only() -> None:
    import dataclasses
    import json

    from intelligence.services.episode_protocol import (
        build_episode_input,
        build_episode_instructions,
    )
    from intelligence.tests.test_episode_protocol import _context, _frame, _registry

    frame = dataclasses.replace(_frame(), raw_question=QUERY, question_type="theme_analysis")
    rules = json.loads(build_episode_input(frame, _context(frame), _registry()))[
        "question_type_rules"
    ]

    assert "判断增量表达契约" in rules
    assert "待验证问题" in rules and "裁判变量" in rules
    assert "判断增量表达契约" not in build_episode_instructions(
        frame, _context(frame), _registry()
    )
    for legacy_marker in ("[D6]", "[W7]", "[L1-x]"):
        assert legacy_marker not in rules


def test_quick_fact_questions_keep_rules_unchanged() -> None:
    import dataclasses
    import json

    from intelligence.services.episode_protocol import build_episode_input
    from intelligence.tests.test_episode_protocol import _context, _frame, _registry

    frame = dataclasses.replace(
        _frame(), raw_question="英维克收盘价多少", question_type="quick_fact"
    )
    rules = json.loads(build_episode_input(frame, _context(frame), _registry()))[
        "question_type_rules"
    ]

    assert "判断增量表达契约" not in rules
