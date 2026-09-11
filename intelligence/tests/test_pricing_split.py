"""产业证据 / 定价状态二分（q17 Q4 回灌 / R5 收窄版）的验收判据。

两件事分开测：
1. **接线**——定价状态问句能不能拿到拥挤度分位（D6 门控）。R1a 的教训是契约层
   再造读数没用，底下那个不通就还是不通，所以这里直接断言门控；
2. **契约**——两段是否分答、没有事前预期源时是否只报价格状态、投票阈值与
   「涨了就是共识」是否被明确挡住。

负例照抄 R1a 的验收口径（「今天信创板块怎么样」「今天哪些板块涨了」必须仍然关着），
防止这次放宽顺手把 D6 变成常开。
"""

from __future__ import annotations

from intelligence.services.market_midterm import midterm_intent_for
from intelligence.services.pricing_split import (
    EVIDENCE_HEADING,
    NO_CONSENSUS_DECLARATION,
    PRICING_HEADING,
    build_pricing_split_guidance,
    build_pricing_split_guidance_for_episode,
    episode_pricing_split_rule,
    is_pricing_state_query,
    missing_pricing_split_elements,
    parse_pricing_split_intent,
    pricing_split_guidance_for_query,
    pricing_split_receipt,
    pricing_split_violations,
)

PRICING_QUESTIONS = (
    "液冷还能追吗",
    "英维克涨这么多了还有空间吗",
    "这波行情是不是已经反映了产业逻辑",
    "算力主线现在是基本面还是情绪",
    "固态电池的预期差还在吗",
    "这个位置是不是已经拥挤了",
)

NON_PRICING_QUESTIONS = (
    "今天信创板块怎么样",
    "今天哪些板块涨了",
    "过去 10 个交易日涨停家数逐日变化",
    "英维克收盘价多少",
    "什么是拥挤度分位",
    "拥挤度怎么算",
)


# ——————————————————————————————————————————— 接线：D6 门控
def test_pricing_questions_now_reach_the_crowding_block() -> None:
    for question in PRICING_QUESTIONS:
        assert is_pricing_state_query(question), question
        assert midterm_intent_for(question) is not None, question


def test_r1a_negative_examples_stay_closed() -> None:
    """放宽不许变常开：这几句一个中期词没有，也不该把 D6 拖起来。"""
    for question in NON_PRICING_QUESTIONS:
        assert not is_pricing_state_query(question), question
        assert midterm_intent_for(question) is None, question


def test_definition_questions_are_excluded_even_with_the_cue_word() -> None:
    assert not is_pricing_state_query("什么是拥挤度")
    assert not is_pricing_state_query("拥挤度指标含义是什么")


# ——————————————————————————————————————————— 注入门
def test_intent_routes_and_excluded_types_do_not() -> None:
    assert parse_pricing_split_intent("液冷还能追吗", "theme_analysis")
    assert not parse_pricing_split_intent("液冷还能追吗", "quick_fact")
    assert not parse_pricing_split_intent("液冷还能追吗", "concept_definition")
    assert pricing_split_guidance_for_query("今天信创板块怎么样", "theme_analysis") == ""
    assert episode_pricing_split_rule("今天信创板块怎么样", "theme_analysis") == ""


def test_guidance_carries_the_narrowed_rules() -> None:
    for text in (build_pricing_split_guidance(), build_pricing_split_guidance_for_episode()):
        assert EVIDENCE_HEADING in text
        assert PRICING_HEADING in text
        assert NO_CONSENSUS_DECLARATION in text
        # 收窄掉的东西必须写成禁令留在契约里，否则下一个人会把 R5 初版的投票阈值捡回来。
        assert "禁止投票式判定" in text
        assert "相对分位" in text
        assert "融资余额" in text
        assert "同时成立" in text


# ——————————————————————————————————————————— 程序核对
_SPLIT_ANSWER = f"""
{EVIDENCE_HEADING}：
- 2026-09-08 公司公告中标 3.2 亿元液冷订单 [E1]，把 2026H2 收入兑现路径的订单环变强。
- 未知项：毛利率口径未披露，缺一份合同分项。

{PRICING_HEADING}：
- 拥挤度分位 92%（近 60 个交易日成交额分布）[E4]，价格已充分反应订单预期。
- {NO_CONSENSUS_DECLARATION}：事前一致预期无可回查来源。
- 未知项：资金主动性数据缺失，记为未知。

结论：产业证据确实增强，但定价已较拥挤，两者同时成立。
"""


def test_split_answer_passes_the_program_check() -> None:
    assert missing_pricing_split_elements(_SPLIT_ANSWER) == ()
    assert pricing_split_violations(_SPLIT_ANSWER) == ()


def test_merged_bull_case_is_caught() -> None:
    merged = "液冷逻辑持续强化，成交放量，情绪高涨，还能继续追。"
    missing = missing_pricing_split_elements(merged)

    assert "industrial_evidence_section" in missing
    assert "pricing_state_section" in missing
    assert "crowding_reading" in missing


def test_vote_threshold_and_price_as_consensus_are_flagged() -> None:
    voted = f"{EVIDENCE_HEADING}：订单落地。{PRICING_HEADING}：拥挤度 40%。六项里满足四项，判定为再确认。"
    assert "vote_threshold" in pricing_split_violations(voted)

    claimed = (
        f"{EVIDENCE_HEADING}：订单落地。{PRICING_HEADING}：拥挤度 40%。"
        "已经涨了这么多，说明市场已经相信这条逻辑。"
    )
    assert "price_as_consensus_proof" in pricing_split_violations(claimed)


# ——————————————————————————————————————————— 交叉样本：同涨幅、不同信息增量
def test_cross_sample_same_move_different_information_delta() -> None:
    """「新订单 + 高拥挤」与「旧消息重提 + 低拥挤」在收据上必须读得出不同。"""
    old_news = f"""
{EVIDENCE_HEADING}：本期无新增产业证据，仅有 6 月旧公告被重新转述。
{PRICING_HEADING}：拥挤度分位 18%，价格反应主要来自资金再定价。
{NO_CONSENSUS_DECLARATION}。
"""
    new_order = pricing_split_receipt(
        _SPLIT_ANSWER, query="液冷还能追吗", question_type="theme_analysis"
    )
    stale = pricing_split_receipt(
        old_news, query="液冷还能追吗", question_type="theme_analysis"
    )

    assert new_order["missing_elements"] == stale["missing_elements"] == []
    assert new_order["violations"] == stale["violations"] == []
    # 两份都合契约，但产业证据段的内容相反——这正是「相同涨幅、不同信息增量应给出
    # 不同解释」要落到的地方；程序只能核对它有没有分开答，解释质量归同题对照实验。
    assert "本期无新增产业证据" in old_news
    assert "本期无新增产业证据" not in _SPLIT_ANSWER


def test_receipt_stays_quiet_on_non_pricing_questions() -> None:
    receipt = pricing_split_receipt("信创今天涨 2%", query="今天信创板块怎么样", question_type="theme_analysis")

    assert receipt["pricing_split_intent"] is False
    assert receipt["missing_elements"] == []
    assert receipt["violations"] == []
