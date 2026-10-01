"""待核说明的误报形状（2026-09-29 L6 批 5 U2）：句中短日期、显式正号、百分比字段。

标注模式下，误报不再删句，却会在公开稿里写「未在证据中找到出处」——而那个数就在所引
证据里。三种形状各自只放行确定的那一种写法；区间、带单位的数、未绑定的引用照旧受审。

第四种（2026-09-29 post967 切后探针）：单位写在**带限定前缀**的字段名里，
``市场成交额亿=14090.71``、``上证涨跌幅=0.1786``。字段名表只认裸名（``成交额亿``），
前缀一加就退回裸数，与回答里的 ``14090.71亿元`` 维度对不上。

第五种（2026-09-30 post986 切后探针）：百分数字段的 % 没写进名字。finance_query 的
``成交额环比=-17.24``、``量比=76.88`` 都是百分数，回答写 ``17.2%``、``76.9%`` 仍被挂待核。
修在两端：finance_query 把单位写进标签（``成交额环比%``、``量比%``），数值门认「名字以 % 结尾」
的字段。别的数据源里的「量比」多是倍数，所以不把裸名「量比」全局当成百分比。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import duckdb
import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _novel_numeric_condition_tokens,
    _numbered_sentences,
    numeric_condition_unsupported,
)
from intelligence.services.finance_query import FinanceQuery, FinanceQuerySpec
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
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


@pytest.mark.parametrize("draft,detail,supported", [
    # 整数百分比多半是自拟阈值：随便哪行涨跌幅落在容差内都不算出处。
    ("若单日收跌超过 6%（E1）则止损。", "交易日=2026-09-15；涨跌幅=-5.72", False),
    ("若单日涨幅超过 5%（E1）则追高风险加大。", "交易日=2026-09-15；涨跌幅=4.96；换手率=5.3", False),
    # 字段本身就是那个整数，才认。
    ("若单日涨幅再达 5%（E1）则追高风险加大。", "交易日=2026-09-15；涨跌幅=5", True),
])
def test_integer_percent_needs_an_integer_field(draft, detail, supported):
    _, verified = _dated(draft, detail=detail)
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


# 09-29 post967 切后探针原样：run_20260929_233537_056428，证据行即当晚的 E12。
PROBE_ROW_0929 = (
    "交易日=2026-09-29；涨停家数=57；跌停家数=11；市场成交额亿=14090.71；"
    "上证收盘=3830.451；上证涨跌幅=0.1786；量比=76.88"
)


def test_probe_0929_market_amount_is_not_doubted(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    draft = "- **成交额**：全市场约14090.71亿元，量比仅76.88（显著低于20日均量）（E1）。"
    frame, verified = _dated(draft, source_date="2026-09-29", detail=PROBE_ROW_0929)
    # 当晚「20日」的出处是另一张已绑定的主线卡（标题「电子近20日出现9天」），照样带上。
    mainline = replace(
        verified.outcome.evidence[0], content_hash="MAINLINE_0929",
        title="主线持续性：电子近20日出现9天（2026-09-15~2026-09-29）", detail="电子出现天数=9",
    )
    first, *rest = verified.outcome.bindings
    verified = replace(verified, outcome=replace(
        verified.outcome, evidence=(*verified.outcome.evidence, mainline),
        bindings=(replace(first, evidence_hashes=(*first.evidence_hashes, "MAINLINE_0929")), *rest),
    ))
    assert _flagged(verified) == []
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert "待核" not in result.public_answer


@pytest.mark.parametrize("draft,detail,supported", [
    ("若全市场成交额跌破 14090.71亿元（E1）则缩量延续。", "交易日=2026-09-29；市场成交额亿=14090.71", True),
    ("若全市场成交额跌破 1.41万亿元（E1）则缩量延续。", "交易日=2026-09-29；市场成交额亿=14090.71", True),
    ("若竞价成交额超过 12.35 亿（E1）则情绪偏强。", "交易日=2026-09-29；竞价成交额亿=12.35", True),
    ("若全日成交额低于 711亿（E1）则板块降温。", "交易日=2026-09-29；全日成交额亿=711.4", True),
    ("若封单金额低于 3.2亿元（E1）则封板不稳。", "交易日=2026-09-29；封单金额元=320000000", True),
    # 前缀只让单位绑得上，数不对照旧受审。
    ("若全市场成交额跌破 14190.71亿元（E1）则缩量延续。", "交易日=2026-09-29；市场成交额亿=14090.71", False),
    # 字段名不是金额（成交量），前缀救不了。
    ("若成交量跌破 14090.71亿元（E1）则缩量延续。", "交易日=2026-09-29；市场成交量手=14090.71", False),
    # 单位不紧跟在金额名后（占比），不是金额字段。
    ("若成交额占比超过 2.53亿元（E1）则过热。", "交易日=2026-09-29；成交额占比=2.53", False),
    # 大盘成交额天天在 1.5–3 万亿之间：「2 万亿」「2.1 万亿」「20000 亿」是自拟阈值，
    # 按显示精度舍入总能撞上某一天（09-30 回放 950 个存证 run 撞出 4 例），只认数值恰好相等。
    ("若全市场成交额回到 2万亿以上（E1）则企稳确认。", "交易日=2026-09-29；市场成交额亿=21949.97", False),
    ("若全市场成交额站上 2.1 万亿（E1）则升级主线。", "交易日=2026-09-29；市场成交额亿=20950.3", False),
    ("若全市场成交额跌破 20000亿（E1）则退潮确认。", "交易日=2026-09-29；市场成交额亿=19999.6", False),
    ("若全市场成交额跌破 2万亿（E1）则退潮确认。", "交易日=2026-09-29；市场成交额亿=20000", True),
    # 至少 3 位有效数字才是复述：21950 亿是 21949.97 亿的舍入。
    ("若全市场成交额再低于 21950亿（E1）则缩量延续。", "交易日=2026-09-29；市场成交额亿=21949.97", True),
], ids=[
    "market-yi", "market-wanyi", "auction-yi", "fullday-yi", "seal-yuan",
    "wrong-number", "volume-not-money", "share-not-money",
    "threshold-2wanyi", "threshold-2p1wanyi", "threshold-20000yi", "exact-2wanyi", "restated-21950yi",
])
def test_money_unit_in_a_qualified_field_name(draft, detail, supported):
    _, verified = _dated(draft, source_date="2026-09-29", detail=detail)
    assert numeric_condition_unsupported(verified) is not supported


@pytest.mark.parametrize("draft,detail,supported", [
    ("若上证单日涨幅超过 0.18%（E1）则延续修复。", "交易日=2026-09-29；上证涨跌幅=0.1786", True),
    ("若区间涨幅超过 12.3%（E1）则追高风险加大。", "交易日=2026-09-29；10日涨跌幅=12.34", True),
    ("若竞价涨幅超过 3.2%（E1）则高开。", "交易日=2026-09-29；竞价涨跌幅=3.21", True),
    ("若单日最大涨幅超过 9.98%（E1）则过热。", "交易日=2026-09-29；最大单日涨跌幅%=9.98", True),
    ("若上证单日涨幅超过 0.28%（E1）则延续修复。", "交易日=2026-09-29；上证涨跌幅=0.1786", False),
    # 整数百分比规则对带前缀的字段同样成立。
    ("若上证单日涨幅超过 1%（E1）则延续修复。", "交易日=2026-09-29；上证涨跌幅=0.6", False),
    # 「有效涨跌幅行数」是计数，不是百分比字段。
    ("若有效样本超过 5%（E1）则可信。", "交易日=2026-09-29；有效涨跌幅行数=5", False),
], ids=[
    "sse", "window-10d", "auction", "bare-percent-suffix",
    "wrong-number", "integer-rule", "count-not-percent",
])
def test_percent_unit_in_a_qualified_field_name(draft, detail, supported):
    _, verified = _dated(draft, source_date="2026-09-29", detail=detail)
    assert numeric_condition_unsupported(verified) is not supported


# 09-30 post986 切后探针原句：run_20260930_023655_895209。「20日」是模型对量比口径的解释，
# 口径只写在工具说明里、不在证据文本里——它该继续挂待核。
PROBE_SENTENCE_0930 = "两市成交约14090.7亿元，环比萎缩约17.2%，量比76.9%，即成交低于20日均值水平，属于缩量反弹（E1）。"


def _market_daily_detail(tmp_path) -> str:
    """finance_query 真实渲染的 market_daily 证据行：标签写法与数值门是同一份契约。"""

    path = tmp_path / "market.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "create table fact_market_daily(trade_date date, total_amount double,"
            " sh_index_pct_chg double, amount_vs_yesterday_pct double, volume_ratio double)"
        )
        connection.execute(
            "insert into fact_market_daily values (DATE '2026-09-29', 14090.71, 0.1786, -17.24, 76.88)"
        )
    finally:
        connection.close()
    spec = FinanceQuerySpec.from_arguments({
        "dataset": "market_daily",
        "metrics": ["total_amount", "index_return_pct", "amount_change_pct", "volume_ratio"],
        "dimensions": ["trade_date"],
        "filters": [],
        "time_range": {"start": "2026-09-29", "end": "2026-09-29"},
        "group_by": [],
        "order_by": [{"field": "trade_date", "direction": "asc"}],
        "limit": 5,
    })
    result = FinanceQuery(path).run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 9, 29), "requested"),
        deadline=ResearchDeadline.from_timeout(5.0),
    )
    return result.evidence[0].detail


def test_probe_0930_ratio_fields_carry_their_unit_end_to_end(tmp_path):
    detail = _market_daily_detail(tmp_path)
    assert "成交额环比%=-17.24" in detail
    assert "量比%=76.88" in detail
    _, verified = _dated(PROBE_SENTENCE_0930, source_date="2026-09-29", detail=detail)
    assert _flagged(verified) == ["20日"]


def test_bare_ratio_name_is_not_a_percent_field():
    # 旧成交额环比的口径可回查到 amount_vs_yesterday_pct；裸名量比仍有倍数歧义，不能猜。
    detail = "交易日=2026-09-29；市场成交额亿=14090.71；成交额环比=-17.24；量比=76.88"
    _, verified = _dated(PROBE_SENTENCE_0930, source_date="2026-09-29", detail=detail)
    assert sorted(_flagged(verified)) == sorted(["76.9%", "20日"])


@pytest.mark.parametrize("draft,detail,supported", [
    ("若量比回到 76.9%（E1）以上则放量。", "交易日=2026-09-29；量比%=76.88", True),
    ("若量比回到 76.9%（E1）以上则放量。", "交易日=2026-09-29；量比（%）=76.88", True),
    ("若前三行业成交占比超过 35.2%（E1）则过于集中。", "交易日=2026-09-29；前三行业成交占比%=35.21", True),
    ("若量比回到 78.9%（E1）以上则放量。", "交易日=2026-09-29；量比%=76.88", False),
    # 整数百分比规则同样适用。
    ("若量比回到 77%（E1）以上则放量。", "交易日=2026-09-29；量比%=76.88", False),
], ids=["suffix", "paren-suffix", "qualified-suffix", "wrong-number", "integer-rule"])
def test_percent_suffix_in_the_field_name(draft, detail, supported):
    _, verified = _dated(draft, source_date="2026-09-29", detail=detail)
    assert numeric_condition_unsupported(verified) is not supported
