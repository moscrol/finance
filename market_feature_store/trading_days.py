# -*- coding: utf-8 -*-
"""交易日判定（全链路共享）。

目标：把「是否交易日」的判断收敛到一处，避免夜间调度、L2 状态写入、
质量门禁各自为政导致的状态覆写（如 8.6 逐笔缺失被当作「非交易日」掩盖，
或非交易日把历史 complete 降级成 failed）。

判定优先级（自上而下，任一命中即返回）：
1. 显式 env 覆盖 L2_FORCE_TRADE_DAY / L2_FORCE_NON_TRADE_DAY（排障用）
2. 周末（周六/周日）→ 非交易日
3. 未来日期 → 非交易日（不预写）
4. 本地 DuckDB fact_stock_daily：当日有完整日线（行数 >= MIN_DAILY_ROWS）→ 交易日
   （节假日/临时停市天然无日线；这也与夜间复盘「同步段」的落库口径一致）
5. 回退：DuckDB 不可读时按工作日（周一~周五）近似判定，并在返回值中标记 approximate

注意：**不用 ClickHouse 逐笔表判定**——逐笔可能因数据未到位而缺失（8.6 即如此），
那正是要报告「真交易日 L2 缺失」的场景，不能被当作非交易日跳过。
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

# 判定「当日有完整日线」的行数下限：全市场 A 股约 5000+ 只，缺失到该线以下视为
# 日线未同步（不算交易日）。真实休市日该表当日无行，天然不命中。
MIN_DAILY_ROWS = 3000

_DB_CACHE: dict[str, bool | None] = {}


def _db_path() -> str | None:
    env = os.environ.get("MARKET_FEATURE_STORE_DB") or os.environ.get(
        "FINANCE_DATA_ROOT"
    )
    if env and env.endswith(".duckdb"):
        return env
    if env:
        candidate = Path(env) / "db" / "market_feature_store.duckdb"
        if candidate.exists():
            return str(candidate)
    return None


def _fact_stock_daily_count(d: date, path: str | None = None) -> int | None:
    """返回当日 fact_stock_daily 行数；不可读返回 None（调用方回退近似判定）。

    path 为 None 时按 env 解析默认库；显式传入 db_path 时用它（不可读即回退）。
    """
    if path is None:
        path = _db_path()
    if path is None:
        return None
    try:
        import duckdb

        with duckdb.connect(path, read_only=True) as con:
            row = con.execute(
                "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?",
                [d.isoformat()],
            ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return None


def is_trading_day(d: date | str | None = None, *, db_path: str | None = None) -> bool:
    """d 是否为 A 股交易日（默认今天）。返回 (bool, approximate) 的兼容单值。"""
    return is_trading_day_detailed(d, db_path=db_path)[0]


def is_trading_day_detailed(
    d: date | str | None = None, *, db_path: str | None = None
) -> tuple[bool, bool]:
    """返回 (is_trading_day, approximate)。approximate=True 表示按工作日近似（DuckDB 不可读）。"""
    if d is None:
        d = date.today()
    elif isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()

    # 1. 显式覆盖
    if os.environ.get("L2_FORCE_TRADE_DAY", "").strip().lower() in {"1", "true", "yes"}:
        return True, False
    if os.environ.get("L2_FORCE_NON_TRADE_DAY", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return False, False

    # 2. 周末
    if d.weekday() >= 5:
        return False, False

    # 3. 未来
    if d > date.today():
        return False, False

    # 4. 本地日线
    if db_path is None:
        db_path = _db_path()
    if db_path is not None:
        cache_key = f"{db_path}:{d.isoformat()}"
        if cache_key in _DB_CACHE:
            return _DB_CACHE[cache_key], False
        n = _fact_stock_daily_count(d, path=db_path)
        if n is not None:
            result = n >= MIN_DAILY_ROWS
            _DB_CACHE[cache_key] = result
            return result, False

    # 5. 回退：工作日近似
    return d.weekday() < 5, True


def recent_trading_dates(n: int = 5, *, end: date | None = None) -> list[date]:
    """返回最近 n 个交易日（含 end，默认今天），供日志/门禁展示。"""
    out: list[date] = []
    d = end or date.today()
    while len(out) < n:
        if is_trading_day(d):
            out.append(d)
        d = d - __import__("datetime").timedelta(days=1)
    return out
