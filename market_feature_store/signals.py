from __future__ import annotations

from decimal import Decimal


DOUBLE_RED_SQL = "pct_chg > 0 AND diff_ratio > 10 AND amount > 500"
DOUBLE_RED_DESCRIPTION = "题材涨幅为正、边际量大于 10 且成交额大于 500 亿。"


def is_double_red(pct_chg: object, diff_ratio: object, amount: object) -> bool:
    values = (pct_chg, diff_ratio, amount)
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) for value in values):
        return False
    return float(pct_chg) > 0 and float(diff_ratio) > 10 and float(amount) > 500
