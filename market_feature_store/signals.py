from __future__ import annotations

from decimal import Decimal


# 严格双红口径的**唯一**数字出处（R-20260830-03）。
#
# 此前树里有三份互不引用的实现，数值恰好一致所以谁都没发现：
#   ① 本文件：``DOUBLE_RED_SQL`` 里写死字面量（包 / D 块 / market_timeseries 侧）
#   ② ``intelligence/services/theme_lifecycle_timeline``：自己一套
#      ``DOUBLE_RED_PCT/DIFF/AMOUNT``（Engine A 的 ``asof_prefetch`` 走这份）
#   ③ ``intelligence/services/market_regime_analogs``：D10 辅助查询里再写死一次
# 改任一处，另两处静默保持旧口径——而行数/覆盖率类审计永远发现不了，
# 因为每一份自己都自洽。分家线正好压在 A 侧与 B 侧之间。
#
# 现在阈值只在这三行，SQL 谓词**由它们生成**（单一真本源且生成）。
# ``:g`` 保证 0.0/10.0/500.0 渲染成 0/10/500，谓词串与手写版逐字节一致。
DOUBLE_RED_PCT = 0.0
DOUBLE_RED_DIFF = 10.0
DOUBLE_RED_AMOUNT = 500.0

DOUBLE_RED_SQL = (
    f"pct_chg > {DOUBLE_RED_PCT:g} "
    f"AND diff_ratio > {DOUBLE_RED_DIFF:g} "
    f"AND amount > {DOUBLE_RED_AMOUNT:g}"
)
DOUBLE_RED_DESCRIPTION = (
    f"题材涨幅为正、边际量大于 {DOUBLE_RED_DIFF:g} "
    f"且成交额大于 {DOUBLE_RED_AMOUNT:g} 亿。"
)


def is_double_red(pct_chg: object, diff_ratio: object, amount: object) -> bool:
    values = (pct_chg, diff_ratio, amount)
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) for value in values):
        return False
    return (
        float(pct_chg) > DOUBLE_RED_PCT
        and float(diff_ratio) > DOUBLE_RED_DIFF
        and float(amount) > DOUBLE_RED_AMOUNT
    )
