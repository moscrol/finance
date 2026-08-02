"""judge 报的句号跟 harness 的编号对不上，按它引用的原文重新定位。

harness 按「带 marker 的正文行」编号，judge 按自己的读法编号。实测
run_20260731_034344_300179：judge 收到 5 句、报的是第 5 和第 7 句，而它引用的原文
「外围强势可能对A股相关板块形成情绪传导」在第 4 句、「能否扭转弱势取决于增量资金…」
在第 1 句——偏移量还不固定。照序号修 = 删掉第 5 句，两条真正越界的反而留在正文里。
看板里「judge 报 index 2、描述的却是第 3 句」说的就是这件事。
"""
from __future__ import annotations

from intelligence.services.answer_model import (
    GroundingJudgeReport,
    _judge_issue_quotes,
    parse_grounded_sentences,
    resolve_judge_sentence_indexes,
)

CLAIM = "generic:rebound_case"


def _line(text: str) -> str:
    return f"{text} <!-- claim_ids={CLAIM}; evidence_atom_ids=; claim_type=inference -->"


ANSWER = "\n".join(
    (
        _line("盘后的利好催化能否扭转弱势取决于增量资金能否将利好传导至个股广度的改善。"),
        _line("指数下跌0.62%，成交23425.75亿，上涨家数仅1768家。"),
        _line("主线题材集中在消费零售、半导体与AI算力三个方向。"),
        _line("美股半导体大涨，外围强势可能对A股相关板块形成情绪传导。"),
        _line("当前市场的核心矛盾在于短线弱势与盘后催化的对冲。"),
    )
)
SENTENCES, _UNBOUND = parse_grounded_sentences(ANSWER)

# judge 实际返回的形状：issues 是对象，被 parser 转成字符串后仍带 reason 原文。
REAL_ISSUES = (
    "{'sentence_index': 5, 'reason': \"句中将A股主线'半导体'等同于美股"
    "'费城半导体指数'的成分股，存在跨市场主体偷换；原文的'外围强势可能对A股相关板块"
    "形成情绪传导'属于未被证据支撑的因果跳跃。\"}",
    "{'sentence_index': 7, 'reason': \"将盘后的回购/增持公告直接定性为'潜在利好催化'，"
    "属于把候选新闻升级为既定事实利好；'能否扭转弱势取决于增量资金能否将利好传导至"
    "个股广度的改善'引入了未被claim覆盖的因果断言。\"}",
)


def test_quotes_are_paired_by_the_same_delimiter() -> None:
    """允许「" 开头 ' 结尾」会让整串错位一格，抽出跨引号的碎片，一条都定位不到。"""
    quotes = _judge_issue_quotes(REAL_ISSUES[1])

    assert "能否扭转弱势取决于增量资金能否将利好传导至个股广度的改善" in quotes


def test_the_quoted_text_wins_over_the_reported_index() -> None:
    report = GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(5,),
        issues=REAL_ISSUES,
    )

    assert resolve_judge_sentence_indexes(report, SENTENCES) == (1, 4)


def test_an_unquotable_issue_falls_back_to_its_own_index() -> None:
    report = GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(2,),
        issues=("{'sentence_index': 2, 'reason': '语义越界'}",),
    )

    assert resolve_judge_sentence_indexes(report, SENTENCES) == (2,)


def test_the_legacy_shape_without_issues_keeps_the_reported_indexes() -> None:
    """judge 只给序号不给理由时行为不变。"""
    report = GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(2, 3),
        issues=(),
    )

    assert resolve_judge_sentence_indexes(report, SENTENCES) == (2, 3)


def test_out_of_range_indexes_are_still_dropped() -> None:
    report = GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(2, 99),
        issues=(),
    )

    assert resolve_judge_sentence_indexes(report, SENTENCES) == (2,)


def test_an_ambiguous_quote_does_not_pick_a_sentence() -> None:
    """引文命中多句时无法定位，退回它自己报的序号，不能瞎猜一句。"""
    report = GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(3,),
        # 「利好传导」在第 1 句和第 4 句都出现。
        issues=("{'sentence_index': 3, 'reason': '原文的\\'利好传导至个股\\'越界'}",),
    )

    assert resolve_judge_sentence_indexes(report, SENTENCES) == (3,)


def test_repair_drops_the_sentences_the_judge_actually_meant() -> None:
    """后果验证：按序号修会删掉无辜的第 5 句，越界的第 1、4 句留在正文里。"""
    from intelligence.services import answer_model as am

    claim = am.make_claim(
        claim_id=CLAIM,
        text="若跌停家数收缩、上涨家数扩大，则技术性修复更可信。",
        claim_type="expectation",
        theme="A股市场",
        status=am.ClaimStatus.INFERRED,
        evidence_ids=("G1",),
    )
    spec = am.AnswerSpec(
        research_spec=am.resolve_answer_profile("明天怎么走", "A股市场", "forecast"),
        summary=(),
        verified_facts=(),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        candidate_facts=(claim,),
        next_actions=(),
        sources=(
            am.EvidenceRef(
                evidence_id="G1",
                source="本地市场数据",
                detail="2026-07-30：涨停/跌停 52/74。",
                tier="L4_structured",
                source_date="2026-07-30",
            ),
        ),
        system_notices=(),
    )
    report = GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(5,),
        issues=REAL_ISSUES,
    )

    resolved = resolve_judge_sentence_indexes(report, SENTENCES)
    repaired = am.repair_grounded_composer_answer(
        ANSWER, spec, rejected_sentence_indexes=resolved, drop_invalid=True
    )

    assert repaired is not None
    # 两条真正越界的被删掉
    assert "外围强势可能对A股相关板块形成情绪传导" not in repaired
    assert "能否扭转弱势取决于增量资金" not in repaired
    # 被 judge 错报的那一句是无辜的，必须留下
    assert "当前市场的核心矛盾在于" in repaired
