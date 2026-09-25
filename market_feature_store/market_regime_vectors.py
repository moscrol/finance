"""每日市场情绪向量（D10 十维底座）的取数层。

这是「一个交易日 = 一个向量」的**唯一**定义与唯一取数口：D10 类比
（``intelligence.services.market_regime_analogs``）和赚钱效应 regime
（``market_feature_store.money_effect_regime``）都从这里拿向量，不各写一套 SQL。

为什么落在 market_feature_store 而不是 intelligence：
    取数只依赖主库表名与双红谓词（``signals.DOUBLE_RED_SQL``），属于数据底座；
    上层 ``intelligence/`` 依赖它是正方向。2026-09-05 之前它住在
    ``market_regime_analogs`` 里，赚钱效应 regime 要接进 ``market_feature_store``
    的盘后日报时若反向 import ``intelligence``，会造出这两个包之间的第一条向上
    依赖——于是把取数层下沉，``market_regime_analogs`` 原地 re-export，
    既有 import 路径与 ``_AUX_QUERIES`` 的棘轮测试都不用改。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from market_feature_store.signals import DOUBLE_RED_SQL

# 每日情绪向量的特征维（键名 = loader 产出的字段名）
FEATURES: tuple[str, ...] = (
    "total_amount",            # 两市成交额（亿）
    "advancers",               # 涨家数
    "limit_up",                # 涨停家数
    "limit_down",              # 跌停家数
    "sh_deviation_pct",        # 上证对周均线偏离度（%）
    "sh_index_pct_chg",        # 上证日涨跌（%）
    "max_boards",              # 连板最高度
    "double_red_theme_count",  # 严格双红题材数（pct>0 & diff>10 & amount>500）
    "top1_theme_share",        # 第一题材涨停份额
    "new_high_count",          # 新高家数
)

# 辅表查询：基表 fact_market_daily 缺失 → 整体降级；辅表缺失 → 对应维度整体缺失
# （进 missing 列表，D10 匹配时按覆盖率降权，regime 规则则 fail closed）。
_AUX_QUERIES: dict[str, str] = {
    "max_boards": (
        "select trade_date, max(boards) from fact_limit_advance_daily group by trade_date"
    ),
    # 谓词按名引用，不再写死字面量：这一份此前既不看 signals 也不看
    # theme_lifecycle，改阈值时 D10 的情绪向量会静默留在旧口径，而它同时
    # 供 Engine A 预取和 Engine B compose——两边一起错，且读数自洽。
    "double_red_theme_count": (
        "select trade_date, count(*) from fact_sector_daily "
        f"where {DOUBLE_RED_SQL} group by trade_date"
    ),
    "top1_theme_share": (
        "select trade_date, max(market_share) from fact_theme_limit_heat_daily group by trade_date"
    ),
    "new_high_count": (
        "select trade_date, count(*) from fact_stock_high_daily group by trade_date"
    ),
}


def load_market_regime_vectors(
    con: Any, as_of: date | str | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """从只读连接拼每日情绪向量。返回 (升序向量列表, 缺失特征名列表)。

    ``as_of`` 非空时只取 ``trade_date <= as_of``。这是唯一的截断点：
    当前窗口签名、z 标准化系数、候选窗口、后续 5/10/20 日事实全部只消费本函数
    的返回值，因此截在这里即可杜绝未来数据。辅表不必再加同一条件——辅表值按
    日期键回查 base 行，as_of 之后的辅表行不可达。
    """
    base_sql = (
        "select trade_date, total_amount, advancers, limit_up, limit_down, "
        "sh_deviation_pct, sh_index_pct_chg "
        "from fact_market_daily"
    )
    params: list[Any] = []
    if as_of is not None:
        base_sql += " where trade_date <= ?"
        params.append(str(as_of))
    base_sql += " order by trade_date asc"
    try:
        base = con.execute(base_sql, params).fetchall()
    except Exception:
        return [], list(FEATURES)
    if not base:
        return [], list(FEATURES)
    missing: list[str] = []
    aux_maps: dict[str, dict[str, float]] = {}
    for feat, sql in _AUX_QUERIES.items():
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            missing.append(feat)
            continue
        aux_maps[feat] = {
            str(r[0]): float(r[1]) for r in rows if r[1] is not None
        }
    vectors: list[dict[str, Any]] = []
    for row in base:
        day = str(row[0])
        vec: dict[str, Any] = {
            "trade_date": day,
            "total_amount": row[1],
            "advancers": row[2],
            "limit_up": row[3],
            "limit_down": row[4],
            "sh_deviation_pct": row[5],
            "sh_index_pct_chg": row[6],
        }
        for feat in _AUX_QUERIES:
            vec[feat] = aux_maps.get(feat, {}).get(day) if feat in aux_maps else None
        vectors.append(vec)
    return vectors, missing
