from __future__ import annotations

from intelligence.eval.perspective_narrative import (
    score_compare_extras,
    score_narrative_body,
    strip_answer_header,
)


def test_narrative_body_accepts_prose_with_all_element_groups() -> None:
    body = (
        "按此看，8.18 量能还在状态机的中段。该视角认为核心是量能先于主线，"
        "原文《量能复盘》写过非极小量不断言新主线。盘面数据和这条判断对得上，"
        "成立前提是成交没有掉到极小量。证伪看龙头连续两日缩量。把握不大。"
        "本问未见未知项。"
    )
    result = score_narrative_body(body, titles=("量能复盘",))
    assert result["elements_ok"] is True
    assert result["style_ok"] is True
    assert result["ok"] is True
    assert result["element_hits"]["置信"] is True


def test_confidence_group_hits_grasp_and_probability() -> None:
    result = score_narrative_body(
        "该视角认为方向未变。按此看今天仍是存量。冲突在于板块轮动。"
        "前提是宽度不塌。失效看涨停数腰斩。概率偏低。未知项是隔夜外盘。"
        "2026-08-18 原文提过同一条。",
        titles=(),
    )
    assert result["element_hits"]["置信"] is True
    assert result["elements_ok"] is True


def test_spt_form_headings_fail_style() -> None:
    body = (
        "【SPT视角·量能状态】中段\n"
        "【次日重点观察】①②③\n"
        "【证伪条件】量能腰斩\n"
        "该视角认为量能先行。按此看今天未出新主线。支持和冲突都有。"
        "适用看极小量。置信一般。未知是隔夜。2026-08-18"
    )
    result = score_narrative_body(body, titles=())
    assert result["style_ok"] is False
    assert result["ok"] is False
    assert any("【" in item for item in result["style_violations"])


def test_element_heading_banned_but_numbered_condition_allowed() -> None:
    banned = score_narrative_body(
        "适用条件：成交不掉到极小量\n"
        "该视角认为量能先行。按此看今天未出新主线。对得上。"
        "证伪看缩量。把握一般。未知是隔夜。2026-08-18",
        titles=(),
    )
    assert banned["style_ok"] is False

    allowed = score_narrative_body(
        "该视角认为量能先行。按此看今天未出新主线。对得上。"
        "成立前提是宽度不塌。证伪条件①量能腰斩②龙头连续缩量。"
        "把握一般。本问未见未知项。2026-08-18",
        titles=(),
    )
    assert allowed["style_ok"] is True
    assert allowed["elements_ok"] is True


def test_repeated_header_in_body_is_a_style_violation() -> None:
    body = (
        "当前视角：SPT\n"
        "来源范围：本轮事实证据\n"
        "该视角认为量能先行。按此看今天未出新主线。对得上。"
        "前提是极小量。失效看缩量。信心一般。未知是隔夜。2026-08-18"
    )
    result = score_narrative_body(body, titles=())
    assert result["style_ok"] is False
    assert any("当前视角" in item or "来源范围" in item for item in result["style_violations"])


def test_strip_answer_header_scores_only_llm_body() -> None:
    delivered = (
        "当前视角：SPT\n"
        "来源范围：本轮事实证据 + SPT 独立观点层\n\n"
        "该视角认为量能先行。按此看今天未出新主线。对得上。"
        "前提是极小量。失效看缩量。信心一般。未知是隔夜。2026-08-18"
    )
    body = strip_answer_header(delivered)
    assert not body.startswith("当前视角：")
    result = score_narrative_body(body, titles=())
    assert result["style_ok"] is True
    assert result["elements_ok"] is True


def test_title_backref_counts_as_citation() -> None:
    result = score_narrative_body(
        "该视角认为量能先行。按此看今天未出新主线。对得上。"
        "前提是极小量。失效看缩量。把握一般。未知是隔夜。"
        "回看《量能复盘》同一条。",
        titles=("量能复盘", "无关短题"),
    )
    assert result["element_hits"]["原文回指"] is True


def test_compare_extras_require_conflict_and_ai_reasoning() -> None:
    ok = score_compare_extras("两视角冲突在量能权重，综合判断是 AI 推理，不写成共识。")
    assert ok is True
    missing = score_compare_extras("两边都看多，可以当作事实。")
    assert missing is False
