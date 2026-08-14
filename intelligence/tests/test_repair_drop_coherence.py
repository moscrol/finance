"""删句之后剩下的正文必须还读得通。

``repair_grounded_composer_answer(drop_invalid=True)`` 丢掉一句时，不看后一句是否
以回指连接词开头。实测两次：

- 一次答案开头就是悬空的「但」。
- run_20260731_024144_312047：judge 判掉第 5 句「若次日跌停家数明显收缩、上涨家数
  扩大…则技术性修复更可信」（理由是把「技术性修复更可信」擅自升级成「可能形成有参与
  价值的反弹」），第 6 句「反之，如果仅仅依靠权重股拉升指数…」原样保留。于是小标题
  「## 反弹情景的条件与验证框架」下面第一句就是「反之」，读者看到的是半截话。

处理方式是删掉失去前件的连接词，不是连带删掉整句——那一句本身合规且有绑定，因为
前一句被判掉就跟着丢，等于让一次 judge 拒绝吃掉两句话。
"""
from __future__ import annotations

from intelligence.services import answer_model as am
from intelligence.services.answer_model import _strip_backref_connective

CLAIM_ID = "generic:rebound_case"
CLAIM_TEXT = "若跌停家数收缩、上涨家数扩大，则技术性修复更可信。"


def _spec() -> am.AnswerSpec:
    claim = am.make_claim(
        claim_id=CLAIM_ID,
        text=CLAIM_TEXT,
        claim_type="expectation",
        theme="A股市场",
        status=am.ClaimStatus.INFERRED,
        evidence_tier="L4_structured",
        evidence_ids=("G1",),
    )
    return am.AnswerSpec(
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
                source="本地市场数据 · 预测盘面窗口",
                detail="2026-07-30：涨停/跌停 52/74。",
                tier="L4_structured",
                source_date="2026-07-30",
            ),
        ),
        system_notices=(),
    )


def _line(text: str) -> str:
    return f"{text} <!-- claim_ids={CLAIM_ID}; evidence_atom_ids=; claim_type=inference -->"


# --- 连接词剥离本身 --------------------------------------------------------


def test_strips_the_connective_and_keeps_the_rest_of_the_sentence() -> None:
    line = _line("反之，如果仅仅依靠权重股拉升指数，那只能界定为弱反抽。")

    assert _strip_backref_connective(line).startswith("如果仅仅依靠权重股拉升指数")


def test_keeps_words_that_only_start_like_a_connective() -> None:
    """「但凡」「但愿」不是转折，剥掉头一个字会把句子改成另一个意思。"""
    for text in ("但凡出现放量就该警惕。", "但愿明天能企稳。"):
        line = _line(text)

        assert _strip_backref_connective(line) == line


def test_longer_connective_wins_over_its_prefix() -> None:
    line = _line("但是，成交并未萎缩。")

    assert _strip_backref_connective(line).startswith("成交并未萎缩")


def test_list_prefix_survives_the_strip() -> None:
    line = f"- {_line('因此，需要观察量能。')}"

    assert _strip_backref_connective(line).startswith("- 需要观察量能")


def test_line_that_is_only_a_connective_is_reported_as_empty() -> None:
    assert _strip_backref_connective(_line("然而")) == ""


def test_sentence_without_a_connective_is_untouched() -> None:
    line = _line("市场承压明显，成交放量。")

    assert _strip_backref_connective(line) == line


# --- 接进 repair 之后的行为 -----------------------------------------------


def test_repair_does_not_leave_the_survivor_dangling() -> None:
    """判掉第 1 句后，第 2 句不能以「反之」开头出现在正文里。"""
    spec = _spec()
    rejected_first = _line("若次日跌停收缩，则可能形成有参与价值的反弹。")
    kept_second = _line("反之，如果仅仅依靠权重股拉升指数，那只能界定为弱反抽。")

    repaired = am.repair_grounded_composer_answer(
        f"{rejected_first}\n{kept_second}",
        spec,
        rejected_sentence_indexes=(1,),
        drop_invalid=True,
    )

    assert repaired is not None
    assert "有参与价值" not in repaired
    assert "如果仅仅依靠权重股拉升指数" in repaired
    assert "反之" not in repaired


def test_repair_keeps_the_connective_when_its_antecedent_survives() -> None:
    """没有丢句就不该动模型的措辞。"""
    spec = _spec()
    first = _line(CLAIM_TEXT)
    second = _line("反之，如果广度改善，弱势解释就要让位。")

    repaired = am.repair_grounded_composer_answer(
        f"{first}\n{second}",
        spec,
        drop_invalid=True,
    )

    assert repaired is not None
    assert "反之" in repaired


def test_repair_strips_across_an_intervening_heading() -> None:
    """删掉的句子和幸存句之间插一个小标题，悬空关系照样存在。"""
    spec = _spec()
    rejected_first = _line("若次日跌停收缩，则可能形成有参与价值的反弹。")
    kept_second = _line("反之，如果仅仅依靠权重股拉升指数，那只能界定为弱反抽。")

    repaired = am.repair_grounded_composer_answer(
        f"{rejected_first}\n\n## 反弹情景的条件与验证框架\n\n{kept_second}",
        spec,
        rejected_sentence_indexes=(1,),
        drop_invalid=True,
    )

    assert repaired is not None
    assert "反之" not in repaired
    assert "## 反弹情景的条件与验证框架" in repaired


def test_repair_does_not_cascade_into_dropping_the_second_sentence() -> None:
    """一次 judge 拒绝只应该吃掉一句话。"""
    spec = _spec()
    rejected_first = _line("若次日跌停收缩，则可能形成有参与价值的反弹。")
    kept_second = _line("反之，如果仅仅依靠权重股拉升指数，那只能界定为弱反抽。")

    repaired = am.repair_grounded_composer_answer(
        f"{rejected_first}\n{kept_second}",
        spec,
        rejected_sentence_indexes=(1,),
        drop_invalid=True,
    )

    assert repaired is not None
    assert "弱反抽" in repaired
