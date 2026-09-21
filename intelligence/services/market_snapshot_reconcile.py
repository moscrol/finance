"""快照 ↔ DuckDB 对账（2026-08-12 事故的门禁）。

失败形状：新鲜度门禁（要求方）读 ``market_snapshot/`` 的 ``served_trade_date``，
结构化查询（供给方）读 DuckDB ``fact_market_daily`` 的 ``max(trade_date)``。
两者读**不同的源**，快照超前一天时，供给方带 ``<= floor`` 上界永远追不上 →
每次查询被判「数据仅更新到 X，早于当前所需 Y」→ 证据整批作废 → fail-closed
忠实执行 → citations 空 → 「证据不足」。验收 28 题真值通过 0，单这一条就能解释。

``check_market_snapshot_contract.py`` 原本只校验快照自身格式、不和 DuckDB 对账，
这个洞让上述失效完全静默。本模块保留两个日期的诚实诊断。2026-09-21 起，日期不同只报 WARN，
不宣称已有证据作废；无法读到实际日期仍是对账失败，不等于整项分析不可用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


MARKET_DATE_TABLE = "fact_market_daily"


def reconcile_snapshot_with_market_db(
    snapshot_result: dict[str, Any],
    db_path: str | Path,
) -> dict[str, Any]:
    """对照快照与 DuckDB 的实际日期；差异是提示，不是分析拒绝条件。

    ``snapshot_result`` 是 ``validate_market_snapshot_root`` 的返回值；
    对账表固定为 ``fact_market_daily``，因为供给方新鲜度自检
    （``ask_blocks._market_data_asof``）读的就是它。
    """

    errors: list[str] = []
    warnings: list[str] = []
    served = _served_trade_date(snapshot_result)
    if not served:
        errors.append("快照缺少 served_trade_date，无法对账（fail closed）")

    path = Path(db_path).expanduser()
    db_max: str | None = None
    if not path.is_file():
        errors.append(f"DuckDB 不存在: {path}（无法对账，fail closed）")
    else:
        db_max, db_error = _duckdb_max_trade_date(path)
        if db_error:
            errors.append(db_error)

    if served and db_max and served != db_max:
        if served > db_max:
            warnings.append(
                f"快照 served_trade_date {served} 超前 DuckDB "
                f"{MARKET_DATE_TABLE} max(trade_date) {db_max}："
                "使用已有真实数据继续分析，分别标明日期，不因日期差异降级或拒答。"
            )
        else:
            warnings.append(
                f"快照 served_trade_date {served} 落后 DuckDB "
                f"{MARKET_DATE_TABLE} max(trade_date) {db_max}："
                "各来源按实际日期使用，不把旧快照冒充库内最新数据。"
            )

    return {
        "status": "FAIL" if errors else "WARN" if warnings else "PASS",
        "snapshot_served_trade_date": served,
        "duckdb_max_trade_date": db_max,
        "db_path": str(path),
        "table": MARKET_DATE_TABLE,
        "errors": errors,
        "warnings": warnings,
    }


def _served_trade_date(snapshot_result: dict[str, Any]) -> str:
    summary = snapshot_result.get("summary")
    if isinstance(summary, dict):
        value = str(summary.get("served_trade_date") or "").strip()
        if value:
            return value[:10]
    return str(snapshot_result.get("date") or "").strip()[:10]


def _duckdb_max_trade_date(path: Path) -> tuple[str | None, str | None]:
    try:
        connection = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        return None, f"DuckDB 无法打开: {type(exc).__name__}: {exc}"
    try:
        row = connection.execute(
            f"SELECT max(trade_date) FROM {MARKET_DATE_TABLE}"
        ).fetchone()
    except duckdb.Error as exc:
        return None, (
            f"DuckDB 查询 {MARKET_DATE_TABLE} 失败（表缺失或损坏，fail closed）: "
            f"{type(exc).__name__}: {exc}"
        )
    finally:
        connection.close()
    value = row[0] if row else None
    if value is None:
        return None, f"DuckDB {MARKET_DATE_TABLE} 无任何 trade_date（fail closed）"
    return str(value)[:10], None
