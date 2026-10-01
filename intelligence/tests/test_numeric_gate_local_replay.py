"""真实 Mac 存证里的数值误报与串字段支持：只重放确定性门禁，不调用模型。"""

from dataclasses import replace

import pytest

from intelligence.tests.test_numeric_note_false_positives import _dated, _flagged


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("6.49→12.11", []),
        ("6.49→12.12", ["6.49→12.12"]),
        # 两个已知端点不能为分析者自拟的区间背书。
        ("6.49-12.11", ["6.49-12.11"]),
        ("6.49至12.11", ["6.49至12.11"]),
    ],
)
def test_price_transition_checks_both_endpoints(change: str, expected: list[str]) -> None:
    _, verified = _dated(
        f"若累计涨幅过大（{change} 元，E1），则注意风险。",
        detail="交易日=2026-07-13；收盘价=6.49\n交易日=2026-07-23；收盘价=12.11",
    )
    assert _flagged(verified) == expected


def test_price_transition_cannot_use_an_unbound_endpoint() -> None:
    _, verified = _dated(
        "若累计涨幅过大（6.49→12.11 元，E1→E2），则注意风险。",
        detail="交易日=2026-07-13；收盘价=6.49",
    )
    second = replace(
        verified.outcome.evidence[0], content_hash="UNBOUND_CLOSE",
        detail="交易日=2026-07-23；收盘价=12.11",
    )
    verified = replace(verified, outcome=replace(
        verified.outcome, evidence=(*verified.outcome.evidence, second),
    ))
    assert _flagged(verified) == ["6.49→12.11"]


@pytest.mark.parametrize(
    ("label", "direction", "value", "expected"),
    [
        ("成交额环比", "缩量", "10.27", []),
        ("成交额环比%", "缩量", "10.27", []),
        ("成交额环比", "缩量", "10.28", ["10.28%"]),
        ("成交额环比", "放量", "10.27", ["10.27%"]),
        ("量比", "缩量", "10.27", ["10.27%"]),
    ],
)
def test_legacy_market_amount_change_has_percent_unit(
    label: str, direction: str, value: str, expected: list[str],
) -> None:
    _, verified = _dated(
        f"若成交额环比再次{direction}{value}%（E1），则暂缓进攻。",
        detail=f"交易日=2026-07-22；{label}=-10.27",
    )
    assert _flagged(verified) == expected


@pytest.mark.parametrize(
    ("draft", "expected"),
    [
        ("若热度跌回1–2家则降级（E1）。", ["2家"]),
        ("若涨停家数跌回2家则降级（E1）。", ["2家"]),
        ("若跌停家数升到2家则降级（E1）。", []),
        ("若涨停降到2家且跌停升到2家则降级（E1）。", ["2家"]),
        ("若跌停升到2家且涨停降到2家则降级（E1）。", ["2家"]),
        ("若涨停降到14家且跌停升到2家则降级（E1）。", []),
    ],
)
def test_count_support_preserves_the_metric_for_each_occurrence(draft: str, expected: list[str]) -> None:
    _, verified = _dated(draft, detail="涨停家数=1；跌停家数=2\n涨停家数=14")
    assert _flagged(verified) == expected


def test_valuation_fields_cannot_support_each_other() -> None:
    _, verified = _dated("若市盈率回到2.1倍则加仓（E1）。", detail="市盈率TTM=35.2；市净率MRQ=2.1")
    assert _flagged(verified) == ["2.1倍"]


@pytest.mark.parametrize(
    ("draft", "detail", "expected"),
    [
        ("若有57家涨停，则市场情绪较强（E1）。", "涨停家数=57", []),
        ("若涨停家数下跌至14家，则降级（E1）。", "涨停家数=14；下跌家数=2", []),
        ("若涨停家数上涨至2家，则升级（E1）。", "涨停家数=14；上涨家数=2", ["2家"]),
        ("若涨停家数维持14家、2家跌停，则情绪仍强（E1）。", "涨停家数=14；跌停家数=2", []),
        ("若涨停家数从14家上涨到24家，则升级（E1）。", "涨停家数=14\n涨停家数=24", []),
        ("若涨停家数从14家上涨到24家，则升级（E1）。", "涨停家数=14；上涨家数=24", ["24家"]),
        ("若累计涨幅过大（6.49→12.11 元，E1），则注意风险。", "收盘价=6.49；换手率=12.11", ["6.49→12.11"]),
    ],
)
def test_numeric_metric_survives_direction_words_and_inversion(draft, detail, expected):
    _, verified = _dated(draft, detail=detail)
    assert _flagged(verified) == expected
