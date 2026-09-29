"""待核说明的误报形状（2026-09-29 L6 批 5 U2）：句中短日期、显式正号、百分比字段。

标注模式下，误报不再删句，却会在公开稿里写「未在证据中找到出处」——而那个数就在所引
证据里。三种形状各自只放行确定的那一种写法；区间、带单位的数、未绑定的引用照旧受审。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _novel_numeric_condition_tokens,
    _numbered_sentences,
    numeric_condition_unsupported,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural

ROW_0915 = "股票代码=300308.SZ；交易日=2026-09-15；收盘价=864.01；UP偏离度=-6.58；涨跌幅=-5.72；换手率=2.45"


def _dated(draft: str, *, source_date: str = "2026-09-15", detail: str = ROW_0915):
    frame, verified = _structural(draft, detail=detail)
    evidence = replace(verified.outcome.evidence[0], source_date=source_date)
    return frame, replace(verified, outcome=replace(verified.outcome, evidence=(evidence,)))


def _with_second_row(verified, *, source_date: str, bound: bool):
    """追加 E2：另一天的行情行，可选是否绑进回答。"""

    second = replace(
        verified.outcome.evidence[0], content_hash="SECOND_ROW", source_date=source_date,
        detail=ROW_0915.replace("2026-09-15", source_date),
    )
    bindings = verified.outcome.bindings
    if bound:
        first, *rest = bindings
        bindings = (replace(first, evidence_hashes=(*first.evidence_hashes, "SECOND_ROW")), *rest)
    return replace(verified, outcome=replace(
        verified.outcome, evidence=(*verified.outcome.evidence, second), bindings=bindings,
    ))


def _flagged(verified) -> list[str]:
    sentences = _numbered_sentences(verified.outcome.draft)
    return [token for tokens in _novel_numeric_condition_tokens(sentences, verified).values() for token in tokens]


@pytest.mark.parametrize("draft", [
    "若再像 9-15 那样放量跌破 UP 线（E1）则趋势转弱。",
    "若出现 9-15（E1）式的放量下跌则止损。",
    "技术上若 9-15 曾跌破 UP 线（偏离度 -6.58，E1）的形态重演，则趋势转弱。",
])
def test_short_date_anchored_by_its_cited_row_is_a_date(draft):
    _, verified = _dated(draft)
    assert not numeric_condition_unsupported(verified)


@pytest.mark.parametrize("draft", [
    # 本句没有引用：无单位区间与日期字面分不开，照旧当数量审。
    "若再像 9-15 那样放量跌破 UP 线则趋势转弱。",
    # 带单位就是数量，引用也救不了。
    "若回撤持续 9-15 天（E1）则趋势转弱。",
    "若市盈率落到 9-15 倍（E1）则降级。",
    "若市盈率落到 **9-15** 倍（E1）则降级。",
    "若换手升到 9-15%（E1）则过热。",
    # 小数续位不是日期。
    "若市盈率落到 9-15.5（E1）则降级。",
    # ``7月9-15`` 是日区间，不是 9 月 15 日。
    "若 7月9-15 那样连续放量（E1）则趋势转强。",
])
def test_short_date_shape_that_is_still_a_quantity(draft):
    _, verified = _dated(draft)
    assert numeric_condition_unsupported(verified)


def test_short_date_needs_the_cited_row_to_carry_that_date():
    # 引用的 E1 是 09-12 那一行；全篇别处恰好有 09-15 的已绑定证据也不算。
    _, verified = _dated("若再像 9-15 那样放量跌破 UP 线（E1）则趋势转弱。", source_date="2026-09-12")
    assert numeric_condition_unsupported(verified)
    elsewhere = _with_second_row(verified, source_date="2026-09-15", bound=True)
    assert numeric_condition_unsupported(elsewhere)


def test_short_date_cited_but_unbound_row_does_not_count():
    frame, verified = _dated("若再像 9-15 那样放量跌破 UP 线（E2）则趋势转弱。", source_date="2026-09-12")
    unbound = _with_second_row(verified, source_date="2026-09-15", bound=False)
    assert numeric_condition_unsupported(unbound)
    bound = _with_second_row(verified, source_date="2026-09-15", bound=True)
    assert not numeric_condition_unsupported(bound)


@pytest.mark.parametrize("draft,supported", [
    ("若偏离度自 +1.05 回落至负值（E1）则转弱。", True),
    ("若偏离度自 +1.06 回落至负值（E1）则转弱。", False),
    ("若换手升到 +2.45%（E1）以上则过热。", True),
])
def test_explicit_plus_sign_is_the_same_number(draft, supported):
    _, verified = _dated(draft, detail="交易日=2026-09-15；UP偏离度=1.05；换手率=2.45")
    assert numeric_condition_unsupported(verified) is not supported


@pytest.mark.parametrize("draft,supported", [
    ("若再现单日 -5.72% 的放量下跌（E1）则止损。", True),
    ("若再现单日 -5.7% 的放量下跌（E1）则止损。", True),
    ("若再现单日 -5.8% 的放量下跌（E1）则止损。", False),
    ("若换手率跌破 2.45%（E1）则人气转弱。", True),
    ("若振幅超过 7.1%（E1）则波动放大。", True),
])
def test_percent_fields_carry_their_unit(draft, supported):
    _, verified = _dated(draft, detail="交易日=2026-09-15；涨跌幅=-5.72；换手率=2.45；振幅=7.1")
    assert numeric_condition_unsupported(verified) is not supported


def test_percent_unit_is_bound_only_by_those_fields():
    # 偏离度、收盘价这类字段的裸数不获 % 资格。
    _, verified = _dated("若再现 -5.72% 的偏离（E1）则止损。", detail="交易日=2026-09-15；UP偏离度=-5.72")
    assert numeric_condition_unsupported(verified)


def test_u2_shape_keeps_only_the_analyst_thresholds_in_the_note(monkeypatch):
    """U2 句 21 的形状：先例日期与跌幅都出自所引那一行，只剩分析者自定的阈值被点名。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    draft = "- 若单日成交 >250 亿且收跌 >5%（对齐 9-14 的 -5.72%/239 亿放量下跌形态，E1）则转入防守。"
    detail = "交易日=2026-09-14；收盘价=873；涨跌幅=-5.72；成交额亿=239.368；换手率=2.45"
    frame, verified = _dated(draft, source_date="2026-09-14", detail=detail)
    assert sorted(_flagged(verified)) == sorted(["250 亿", "5%"])
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert "（待核：「250 亿」、「5%」未在证据中找到出处）" in result.public_answer
    assert "-5.72" not in result.public_answer.split("（待核：")[1]
