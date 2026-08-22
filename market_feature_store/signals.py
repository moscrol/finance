from __future__ import annotations

import math
import re
from decimal import Decimal


# 三个阈值是本仓双红的唯一真本源。SQL 串、中文说明书、判定函数全部由它们生成——
# 不要在任何地方再写一次 0 / 10 / 500，也不要把它们抄进别的模块的模块级常量。
DOUBLE_RED_PCT_MIN = 0.0
DOUBLE_RED_DIFF_MIN = 10.0
DOUBLE_RED_AMOUNT_MIN = 500.0

DOUBLE_RED_SQL = (
    f"pct_chg > {DOUBLE_RED_PCT_MIN:g}"
    f" AND diff_ratio > {DOUBLE_RED_DIFF_MIN:g}"
    f" AND amount > {DOUBLE_RED_AMOUNT_MIN:g}"
)
DOUBLE_RED_DESCRIPTION = (
    f"题材涨幅为正、边际量大于 {DOUBLE_RED_DIFF_MIN:g}"
    f" 且成交额大于 {DOUBLE_RED_AMOUNT_MIN:g} 亿。"
)


def is_double_red(pct_chg: object, diff_ratio: object, amount: object) -> bool:
    """严格双红判定。

    非数值一律 False，不抛：调用方拿到的是判定，不是异常处理义务。`bool` 单独排除
    ——`True` 会被 `float()` 当成 `1.0`，那是把一个标志位悄悄当成了涨幅。
    """

    values = (pct_chg, diff_ratio, amount)
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) for value in values):
        return False
    return (
        float(pct_chg) > DOUBLE_RED_PCT_MIN
        and float(diff_ratio) > DOUBLE_RED_DIFF_MIN
        and float(amount) > DOUBLE_RED_AMOUNT_MIN
    )


# --- 单红 -----------------------------------------------------------------
#
# 单红 = 涨了、边际量也上来了，但**成交额没跟上**。阈值与双红共用同三个数，
# 只有成交额那一条反向。
#
# **成交额缺失既不算单红也不算双红**（2026-08-22 定的口径）。此前三处各写各的：
# 日报把 NULL 算进单红、`ask_blocks` 把 NULL 算进双红、矩阵标缺数——同一行数据被
# 判进互斥的两类，而且都是用户可见输出。
#
# 选「都不算」的理由：另两种写法各自隐含一个没有依据的假设（「没抓到≈量不大」
# 或「没抓到≈量大」）。缺数就是缺数，不拿一个不知道的东西去贴确定的标签。
# SQL 侧天然如此——`NULL <= 500` 求值为 NULL，不成立。
SINGLE_RED_SQL = (
    f"pct_chg > {DOUBLE_RED_PCT_MIN:g}"
    f" AND diff_ratio > {DOUBLE_RED_DIFF_MIN:g}"
    f" AND amount <= {DOUBLE_RED_AMOUNT_MIN:g}"
)
SINGLE_RED_DESCRIPTION = (
    f"题材涨幅为正、边际量大于 {DOUBLE_RED_DIFF_MIN:g}"
    f"，但成交额不超过 {DOUBLE_RED_AMOUNT_MIN:g} 亿；成交额缺失不计入。"
)


def is_single_red(pct_chg: object, diff_ratio: object, amount: object) -> bool:
    """单红判定。成交额缺失 → False（既不是单红，也不会被当成双红）。"""

    values = (pct_chg, diff_ratio, amount)
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) for value in values):
        return False
    return (
        float(pct_chg) > DOUBLE_RED_PCT_MIN
        and float(diff_ratio) > DOUBLE_RED_DIFF_MIN
        and float(amount) <= DOUBLE_RED_AMOUNT_MIN
    )


def is_single_red_row(row: object) -> bool:
    """行形状的单红判定。判定完全委托 `is_single_red`，这里只取字段。"""

    getter = getattr(row, "get", None)
    if getter is None:
        return False
    return is_single_red(getter("pct_chg"), getter("diff_ratio"), getter("amount"))


# --- 开根加权强度 ----------------------------------------------------------
#
# `pct_chg * sqrt(amount)`，**amount 单位是亿元**——`fact_sector_daily.amount` 与
# `fact_sector_stock_daily.amount` 都已经是亿（实测样例 3.9 / 281.49）。
#
# 收口前有四种写法，差别**不在量纲**（`daily_review` 里那个 `amount_yi` 只是
# `max(amount) AS amount_yi` 的别名，同一列同一单位），而在空值/负值怎么挡：
# 有的 `GREATEST(amount,0)`、有的 `amount or 0`、有的靠 WHERE 里的 IS NOT NULL。
#
# 正典的取舍：缺值返回 `None` 而不是 0。返 0 会把「不知道」排成「中性」，和单红
# 那条 NULL 口径同一条纪律。SQL 侧保留 `GREATEST` 夹负值——负成交额是脏数据，
# 开根会得到 NaN 并把整个排序搅乱。
# 列名只允许 ident 或 alias.ident，防止以后有人把用户输入塞进 f-string SQL。
_SQL_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")


def weighted_strength_sql(amount: str = "amount", pct_chg: str = "pct_chg") -> str:
    """开根加权的 SQL 片段。默认等于 ``WEIGHTED_STRENGTH_SQL``；带表别名时改列名。"""

    if not _SQL_IDENT.fullmatch(amount) or not _SQL_IDENT.fullmatch(pct_chg):
        raise ValueError(
            f"weighted_strength_sql 只接受列名/别名，收到 {amount!r}/{pct_chg!r}"
        )
    return f"{pct_chg} * sqrt(GREATEST({amount}, 0))"


WEIGHTED_STRENGTH_SQL = weighted_strength_sql()


def weighted_strength(pct_chg: object, amount: object) -> float | None:
    """开根加权强度；任一值缺失或非数值 → None（不是 0）。"""

    values = (pct_chg, amount)
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) for value in values):
        return None
    return float(pct_chg) * math.sqrt(max(float(amount), 0.0))


def is_double_red_row(row: object) -> bool:
    """行形状的双红判定：`{"pct_chg":…, "diff_ratio":…, "amount":…}`。

    存在的理由是调用点形状不同，不是口径不同——判定完全委托给 `is_double_red`，
    这里只负责取字段。谁都不许再写第二份阈值。
    """

    getter = getattr(row, "get", None)
    if getter is None:
        return False
    return is_double_red(getter("pct_chg"), getter("diff_ratio"), getter("amount"))
