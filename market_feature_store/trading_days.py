# -*- coding: utf-8 -*-
"""交易日判定（全链路共享）与「行情是否到货」判定——**两件事，两组函数**。

## 为什么拆开（工单 #52）

旧实现用「当日 `fact_stock_daily` 行数 >= 3000」代理「今天是不是交易日」。
库可读但当天 0 行时返回 `(False, approximate=False)`——把**同步失败的真交易日**
自信地判成休市。2026-09-11（周五、真交易日、0 行）实测命中：
`run_l2_pipeline.sh` 打印「非交易日，跳过」并 `exit 0`，静默报成功、什么都没干。

「今天开不开市」是日历事实，与「今天的数据到没到」正交：

| 问题 | 函数 | 判据 |
|---|---|---|
| 今天开不开市？ | `trading_day_verdict()` | env 覆盖 → 周末 → 未来 → 交易所公告休市表。**不读任何行情表** |
| 今天的行情到没到？ | `market_data_state()` | `fact_stock_daily` 当日行数 |

## 三值，不是二值

`TRADING` / `CLOSED` / `UNKNOWN`。休市表没有该年份 → `UNKNOWN`，不猜任何一边。
调用方拿到 `UNKNOWN` **不得静默跳过**：要么执行并记一行告警，要么显式报错——
L2 的上游日包自己会失败得很响，比 `exit 0` 好。

`_SSE_CLOSURES` 是全仓休市表的**单一事实源**；`intelligence/services/trading_calendar.py`
反向 import 它（低层被高层引用，方向合法）。不得再建第二张表。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

#: 判定「当日行情已到货」的行数下限：全市场 A 股约 5500 只。
#: 注意这条线**只用于数据面**（`market_data_state`），不再参与交易日判定。
MIN_DAILY_ROWS = 3000

TRADING = "trading"
CLOSED = "closed"
UNKNOWN = "unknown"

#: 上交所公告休市表（单一事实源）。缺年份即 `UNKNOWN`——宁可不判，不猜。
#: 周末不进表：任何年份周末都休市，判定里单独一条。
_SSE_CLOSURES: dict[int, frozenset[date]] = {
    2026: frozenset(
        {
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 2, 16),
            date(2026, 2, 17),
            date(2026, 2, 18),
            date(2026, 2, 19),
            date(2026, 2, 20),
            date(2026, 2, 23),
            date(2026, 4, 6),
            date(2026, 5, 1),
            date(2026, 5, 4),
            date(2026, 5, 5),
            date(2026, 6, 19),
            date(2026, 9, 25),
            date(2026, 10, 1),
            date(2026, 10, 2),
            date(2026, 10, 5),
            date(2026, 10, 6),
            date(2026, 10, 7),
        }
    ),
}


def closed_dates(year: int) -> frozenset[date] | None:
    """该年交易所公告休市表；**未登记该年返回 `None`，不是空集合**。

    `None`（不知道这年怎么休）和 `frozenset()`（这年一天都不休）是两件事，
    调用方靠这个区别决定要不要 fail closed。跨模块读休市表走这个函数，
    不要直接碰 `_SSE_CLOSURES`——那张 dict 是实现细节，公开契约是本函数。
    """
    return _SSE_CLOSURES.get(year)


@dataclass(frozen=True)
class TradingDayVerdict:
    """交易日判定结果。`source` 记判据，便于日志/台账复核为什么这么判。"""

    verdict: str  # TRADING / CLOSED / UNKNOWN
    reason: str  # 人读原因，可直接打进日志
    source: str  # env_override / weekend / future / sse_closure / sse_calendar / calendar_year_missing

    @property
    def is_trading(self) -> bool:
        return self.verdict == TRADING

    @property
    def is_closed(self) -> bool:
        return self.verdict == CLOSED

    @property
    def is_unknown(self) -> bool:
        return self.verdict == UNKNOWN

    def __str__(self) -> str:  # 日志友好
        return f"{self.verdict}({self.source}): {self.reason}"


def _coerce(d: date | str | None) -> date:
    if d is None:
        return date.today()
    if isinstance(d, str):
        return datetime.strptime(d, "%Y-%m-%d").date()
    return d


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def trading_day_verdict(d: date | str | None = None) -> TradingDayVerdict:
    """这天 A 股开不开市。**纯日历判定，不读库、不看行情、不管同步跑没跑。**

    判定顺序（任一命中即返回）：

    1. env 覆盖 `L2_FORCE_TRADE_DAY` / `L2_FORCE_NON_TRADE_DAY`（排障用）
    2. 周末 → `CLOSED`（任何年份成立，不依赖休市表）
    3. 未来日期 → `CLOSED`（source=future）。语义是「这天还没发生，不预写」，
       与「休市」共用 `CLOSED` 是为了让调用方只处理三个分支；判据写在 `source` 里，
       日志可区分。
    4. 该年休市表命中 → `CLOSED`；该年休市表存在但未命中且是工作日 → `TRADING`
    5. 该年不在休市表里 → `UNKNOWN`（fail open 给调用方决定，不猜）
    """
    day = _coerce(d)

    if _env_flag("L2_FORCE_TRADE_DAY"):
        return TradingDayVerdict(TRADING, "L2_FORCE_TRADE_DAY 强制判交易日", "env_override")
    if _env_flag("L2_FORCE_NON_TRADE_DAY"):
        return TradingDayVerdict(CLOSED, "L2_FORCE_NON_TRADE_DAY 强制判休市", "env_override")

    if day.weekday() >= 5:
        name = "周六" if day.weekday() == 5 else "周日"
        return TradingDayVerdict(CLOSED, f"{day.isoformat()} 是{name}，A股休市", "weekend")

    if day > date.today():
        return TradingDayVerdict(
            CLOSED, f"{day.isoformat()} 是未来日期，尚未发生（不预写）", "future"
        )

    closures = closed_dates(day.year)
    if closures is None:
        return TradingDayVerdict(
            UNKNOWN,
            f"{day.year} 年的交易所休市表未登记，无法判定 {day.isoformat()} 是否交易日",
            "calendar_year_missing",
        )
    if day in closures:
        return TradingDayVerdict(
            CLOSED, f"{day.isoformat()} 在交易所公告休市表内", "sse_closure"
        )
    return TradingDayVerdict(
        TRADING, f"{day.isoformat()} 是工作日且不在休市表内", "sse_calendar"
    )


def is_trading_day(d: date | str | None = None, *, db_path: str | None = None) -> bool:
    """兼容入口：这天**该不该当作交易日处理**。

    `UNKNOWN` 返回 **True**——判不出来时按「要干活」处理，让下游真实失败暴露出来，
    而不是静默跳过（那正是 2026-09-11 丢掉一整天 L2 的形状）。
    需要区分三值的调用方改用 `trading_day_verdict()`。

    `db_path` 参数保留只为兼容旧签名：交易日判定已不读库，传了也不用。
    """
    del db_path  # 判定不再依赖行情库；保留形参避免调用方 TypeError
    return not trading_day_verdict(d).is_closed


def is_trading_day_detailed(
    d: date | str | None = None, *, db_path: str | None = None
) -> tuple[bool, bool]:
    """兼容入口：`(该不该当作交易日, 是否判不确定)`。

    第二个分量语义已改：旧版是「DuckDB 不可读所以按工作日近似」，
    新版是「休市表缺该年份，判定为 UNKNOWN」。两者都表示「这个结论不可尽信」。
    """
    del db_path
    verdict = trading_day_verdict(d)
    return (not verdict.is_closed), verdict.is_unknown


# --------------------------------------------------------------------------
# 数据面：行情到没到。与上面的交易日判定正交。
# --------------------------------------------------------------------------

PRESENT = "present"
PARTIAL = "partial"
MISSING = "missing"
DATA_UNKNOWN = "unknown"


def _db_path() -> str | None:
    env = os.environ.get("MARKET_FEATURE_STORE_DB") or os.environ.get("FINANCE_DATA_ROOT")
    if env and env.endswith(".duckdb"):
        return env
    if env:
        candidate = Path(env) / "db" / "market_feature_store.duckdb"
        if candidate.exists():
            return str(candidate)
    return None


def market_data_rows(d: date | str | None = None, *, db_path: str | None = None) -> int | None:
    """当日 `fact_stock_daily` 行数；库不可读返回 `None`（≠ 0 行）。

    不缓存：行情随时可能补进来，缓存会让补数后的复查读到旧结论。
    """
    day = _coerce(d)
    path = db_path if db_path is not None else _db_path()
    if path is None:
        return None
    try:
        import duckdb

        with duckdb.connect(path, read_only=True) as con:
            row = con.execute(
                "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?",
                [day.isoformat()],
            ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return None


def market_data_state(d: date | str | None = None, *, db_path: str | None = None) -> str:
    """当日行情到货状态：`present` / `partial` / `missing` / `unknown`。

    `partial` 是「有行但不足 `MIN_DAILY_ROWS`」——同步跑了一半。
    `unknown` 是「库读不了」，与「库能读但当天 0 行」（`missing`）必须分开：
    前者不知道，后者知道没有。
    """
    rows = market_data_rows(d, db_path=db_path)
    if rows is None:
        return DATA_UNKNOWN
    if rows == 0:
        return MISSING
    if rows < MIN_DAILY_ROWS:
        return PARTIAL
    return PRESENT


def describe(d: date | str | None = None, *, db_path: str | None = None) -> str:
    """一行诊断串，供脚本日志直接打印。两个问题都答，不混在一起。"""
    day = _coerce(d)
    verdict = trading_day_verdict(day)
    return (
        f"{day.isoformat()} calendar={verdict.verdict}({verdict.source}) "
        f"data={market_data_state(day, db_path=db_path)}"
    )


def recent_trading_dates(n: int = 5, *, end: date | None = None) -> list[date]:
    """最近 n 个交易日（含 end，默认今天），供日志/门禁展示。

    `UNKNOWN` 的日子不计入——这里要的是「确定是交易日」的清单，
    与 `is_trading_day()` 的「该不该干活」是不同问题，故不复用它。
    """
    out: list[date] = []
    day = end or date.today()
    guard = 0
    while len(out) < n and guard < 400:
        if trading_day_verdict(day).is_trading:
            out.append(day)
        day = day - timedelta(days=1)
        guard += 1
    return out
