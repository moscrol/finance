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

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

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

# 辅表查询：基表查询失败 → 整体降级；辅表查询失败 → 对应维度不可用。
# 全历史不可用维退出标准化；窗口内缺维才按共同维覆盖惩罚。查询无行不等于表不存在。
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


@dataclass(frozen=True)
class MarketRegimeVectorResult:
    """只读加载诊断；query_failed 不代表表无行，empty 只说明基表查询范围无行。"""

    vectors: list[dict[str, Any]]
    status: Literal["available", "empty", "query_failed"]
    query_failed_features: tuple[str, ...] = ()


def load_market_regime_vectors(
    con: Any,
    as_of: date | str | None = None,
    *,
    knowledge_cutoff: date | str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """兼容旧二元返回；第二项是旧不可用列表，不作空表或常量的原因证明。"""
    result = load_market_regime_vector_result(con, as_of, knowledge_cutoff=knowledge_cutoff)
    missing = list(result.query_failed_features) if result.status == "available" else list(FEATURES)
    return result.vectors, missing


def load_market_regime_vector_result(
    con: Any,
    as_of: date | str | None = None,
    *,
    knowledge_cutoff: date | str | None = None,
) -> MarketRegimeVectorResult:
    """同一取数实现，保查询失败诊断；不返回 SQL、路径或原始异常。

    ``as_of`` 只截断 trade_date；辅表按基表日期回查，晚于 as_of 的值不可达。
    ``pit_grade`` 沿用 fact_market_daily.updated_at 对单个 cutoff 的标记，未核验辅表
    记录时间或逐日历史版本。晚时间戳可能是迟入库或覆盖修订；缺失/非法时间也降为
    trade_date_only。不传 cutoff 则不赋档位，不猜历史可知性。
    """
    # 老库 / 夹具可能没有 updated_at 列：没有就取 NULL——判不了记录时间，PIT 走 trade_date_only，不猜。
    has_updated_at = False
    try:
        has_updated_at = bool(
            con.execute(
                "select 1 from information_schema.columns "
                "where table_name = 'fact_market_daily' and column_name = 'updated_at' limit 1"
            ).fetchall()
        )
    except Exception:
        has_updated_at = False
    upd_col = "updated_at" if has_updated_at else "NULL as updated_at"
    base_sql = (
        "select trade_date, total_amount, advancers, limit_up, limit_down, "
        f"sh_deviation_pct, sh_index_pct_chg, {upd_col} "
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
        return MarketRegimeVectorResult([], "query_failed")
    if not base:
        return MarketRegimeVectorResult([], "empty")
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
    cutoff_end: datetime | None = None
    if knowledge_cutoff is not None:
        cutoff_end = datetime.fromisoformat(str(knowledge_cutoff)[:10]) + timedelta(days=1)  # C 当天收盘后写入的也算 C 已知
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
        if cutoff_end is not None:
            stamp = row[7]
            known: bool | None
            if stamp is None:
                known = None
            else:
                try:
                    ts = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(str(stamp))
                    known = ts < cutoff_end
                except ValueError:
                    known = None
            vec["pit_grade"] = "strict" if known is True else "trade_date_only"
        for feat in _AUX_QUERIES:
            vec[feat] = aux_maps.get(feat, {}).get(day) if feat in aux_maps else None
        vectors.append(vec)
    return MarketRegimeVectorResult(vectors, "available", tuple(missing))

