"""单位写在字段名里的证据值：正确复述不挂待核，自拟阈值照挂（2026-10-01 核查）。

方法：真实字段标签（finance_query）造证据行，条件句里正确复述 37 句、自拟阈值 15 句，
喂给 ``_novel_numeric_condition_tokens``。修前 16/37 句正确复述被挂待核，主因是单位住在
字段名里而核验器只认一部分（post986 修过 ``量比%`` 一种形状，本次补齐同家族）：

- ``涨停家数=57`` → 「57 家」；``市盈率TTM=35.2`` → 「35.2 倍」；``上证收盘=3150.12`` → 「3150.12 点」
- ``龙虎榜净买入亿=1.23`` → 「1.23 亿元」；``机构净买入亿=-0.56`` → 「净卖出 5600 万元」
- ``竞价涨幅=2.3`` → 「2.3%」（底层列 auction_pct；5日涨幅 = (close/c5-1)*100）

刻意不放宽：``总市值``（各数据集口径不一）、整数关口（「3150 点」不算 3150.12 的复述）、
多日证据里的凑整写法（「低于 50 家」不能靠恰好是 50 的某一天撑腰）。
"""

from __future__ import annotations

import pytest

from intelligence.tests.test_numeric_note_false_positives import _dated, _flagged

STOCK = (
    "股票代码=600487.SH；股票名称=亨通光电；交易日=2026-09-15；收盘价=10.37；涨跌幅=-5.56；"
    "换手率=2.45；成交额亿=12.36；总市值=255.6；市盈率TTM=35.2；市净率MRQ=2.1；量比%=135.6"
)
MKT = (
    "交易日=2026-09-15；上证收盘=3150.12；上证涨跌幅=0.1786；市场成交额亿=14090.71；"
    "成交额环比%=-17.24；上涨家数=3471；下跌家数=1933；涨停家数=57；跌停家数=11"
)
LIMIT = "股票名称=亨通光电；交易日=2026-09-15；封单金额元=523000000；竞价成交额亿=1.85；竞价涨幅=2.3"
FLOW = "股票名称=亨通光电；交易日=2026-09-15；龙虎榜净买入亿=1.23；机构净买入亿=-0.56"


@pytest.mark.parametrize(
    ("row", "draft"),
    [
        # 修前误挂、修后放行
        (STOCK, "若市盈率回到 35.2 倍（E1）则减仓。"),
        (STOCK, "若市净率回到 2.1 倍（E1）则减仓。"),
        (MKT, "若上证跌破 3150.12 点（E1）则减仓。"),
        (MKT, "若涨停家数低于 57 家（E1）则降级。"),
        (MKT, "若跌停超过 11 家（E1）则降级。"),
        (MKT, "若上涨家数低于 3471 家（E1）则降级。"),
        (LIMIT, "若竞价涨幅超过 2.3%（E1）则确认。"),
        (FLOW, "若龙虎榜净买入超过 1.23 亿元（E1）则确认。"),
        (FLOW, "若机构净卖出超过 0.56 亿元（E1）则减仓。"),
        (FLOW, "若机构净卖出超过 5600 万元（E1）则减仓。"),
        # 修前就放行的对照
        (STOCK, "若收盘价再跌回 10.37 元（E1）则止损。"),
        (STOCK, "若换手率回到 2.45%（E1）则观察。"),
        (STOCK, "若量比再超过 135.6%（E1）则确认。"),
        (MKT, "若成交额低于 1.41 万亿（E1）则降级。"),
        (LIMIT, "若封单低于 5.23 亿（E1）则减仓。"),
    ],
)
def test_correct_restatement_of_unit_named_fields_is_not_flagged(row: str, draft: str) -> None:
    _, verified = _dated(draft, detail=row)
    assert _flagged(verified) == []


@pytest.mark.parametrize(
    ("row", "draft", "token"),
    [
        (MKT, "若涨停家数低于 50 家（E1）则降级。", "50 家"),
        (MKT, "若上涨家数低于 3000 家（E1）则降级。", "3000 家"),
        (MKT, "若上证跌破 3100 点（E1）则减仓。", "3100 点"),
        # 整数关口不算 3150.12 的复述
        (MKT, "若上证跌破 3150 点（E1）则减仓。", "3150 点"),
        (MKT, "若上证跌破 3150.5 点（E1）则减仓。", "3150.5 点"),
        (STOCK, "若市盈率超过 40 倍（E1）则减仓。", "40 倍"),
        (STOCK, "若市盈率回到 35 倍（E1）则减仓。", "35 倍"),
        (STOCK, "若市净率低于 2 倍（E1）则加仓。", "2 倍"),
        (LIMIT, "若竞价涨幅超过 2%（E1）则确认。", "2%"),
        (LIMIT, "若竞价涨幅超过 3.5%（E1）则确认。", "3.5%"),
        (FLOW, "若龙虎榜净买入超过 2 亿元（E1）则确认。", "2 亿元"),
        (FLOW, "若龙虎榜净买入超过 1.2 亿元（E1）则确认。", "1.2 亿元"),
        (FLOW, "若机构净卖出超过 1 亿元（E1）则减仓。", "1 亿元"),
        # 符号写反：证据是净买入 −0.56，回答说净买入 0.56
        (FLOW, "若机构净买入超过 0.56 亿元（E1）则加仓。", "0.56 亿元"),
        (FLOW, "若机构净卖出超过 0.6 亿元（E1）则减仓。", "0.6 亿元"),
        # 口径不明的字段不给单位背书
        (STOCK, "若市值跌破 255.6 亿元（E1）则减仓。", "255.6 亿元"),
    ],
)
def test_fabricated_thresholds_are_still_flagged(row: str, draft: str, token: str) -> None:
    _, verified = _dated(draft, detail=row)
    assert _flagged(verified) == [token]


_MULTI_DAY = "\n".join(
    f"交易日=2026-09-{d:02d}；涨停家数={n}；上涨家数={a}"
    for d, n, a in [(10, 63, 2890), (11, 50, 3000), (12, 72, 3471), (15, 57, 4100)]
)


@pytest.mark.parametrize(
    ("draft", "flagged"),
    [
        # 凑整写法撞上多日中的某一天：不算复述
        ("若涨停家数低于 50 家（E1）则降级。", ["50 家"]),
        ("若上涨家数低于 3000 家（E1）则降级。", ["3000 家"]),
        # 有效位数够的精确值照认
        ("若涨停家数低于 57 家（E1）则降级。", []),
        ("若上涨家数低于 3471 家（E1）则降级。", []),
    ],
)
def test_coarse_counts_cannot_borrow_support_from_one_day_of_many(draft: str, flagged: list[str]) -> None:
    _, verified = _dated(draft, detail=_MULTI_DAY)
    assert _flagged(verified) == flagged


def test_coarse_count_from_a_single_row_is_a_restatement() -> None:
    _, verified = _dated("若涨停家数再跌到 50 家（E1）则降级。", detail="交易日=2026-09-15；涨停家数=50")
    assert _flagged(verified) == []
