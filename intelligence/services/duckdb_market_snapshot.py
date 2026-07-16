from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb


BEIJING = ZoneInfo("Asia/Shanghai")
DATE_PATTERN = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
SCHEMA_VERSION = "1.2-duckdb"
MIN_STOCK_ROWS = 4000
MIN_FIELD_COMPLETENESS = 0.98
MAX_STRONG_STOCKS = 80


class DuckDbSnapshotUnavailable(RuntimeError):
    """Raised when DuckDB cannot produce a decision-ready market snapshot."""


@dataclass(frozen=True)
class DuckDbSnapshotCandidate:
    trade_date: str
    document: dict[str, object]
    source_tables: tuple[str, ...]
    source_updated_at: str | None


def build_duckdb_snapshot_candidate(
    db_path: str | Path,
    *,
    target_date: str,
    allow_latest_before: bool = False,
    now: datetime | None = None,
) -> DuckDbSnapshotCandidate:
    if not DATE_PATTERN.fullmatch(target_date):
        raise ValueError("target_date 必须为 YYYY-MM-DD")
    path = Path(db_path).expanduser()
    if not path.is_file():
        raise DuckDbSnapshotUnavailable(f"DuckDB 不存在: {path.name}")

    connection = duckdb.connect(str(path), read_only=True)
    try:
        served_date = _select_trade_date(
            connection,
            target_date=target_date,
            allow_latest_before=allow_latest_before,
        )
        market = _fetch_one_dict(
            connection,
            """
            SELECT market_stage, total_amount, volume_ratio, advancers,
                   limit_up, limit_down,
                   industry_1, industry_1_ratio,
                   industry_2, industry_2_ratio,
                   industry_3, industry_3_ratio,
                   source, updated_at
            FROM fact_market_daily
            WHERE trade_date = ?::DATE
            LIMIT 1
            """,
            [served_date],
        )
        if market is None:
            raise DuckDbSnapshotUnavailable(
                f"fact_market_daily 缺少 {served_date}"
            )

        stock_quality = _fetch_one_dict(
            connection,
            """
            SELECT count(*) AS row_count,
                   count(stock_ts_code) AS code_count,
                   count(pct_chg) AS pct_count,
                   count(amount) AS amount_count,
                   sum(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS advancers,
                   sum(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) AS decliners,
                   max(updated_at) AS source_updated_at
            FROM fact_stock_daily
            WHERE trade_date = ?::DATE
            """,
            [served_date],
        )
        if stock_quality is None:
            raise DuckDbSnapshotUnavailable("fact_stock_daily 查询失败")
        _require_stock_quality(stock_quality)

        strong_stocks = _fetch_all_dicts(
            connection,
            """
            SELECT stock_ts_code, stock_name, pct_chg, amount, updated_at
            FROM fact_stock_daily
            WHERE trade_date = ?::DATE
              AND stock_ts_code IS NOT NULL
              AND stock_name IS NOT NULL
              AND pct_chg >= 7
              AND amount IS NOT NULL
            ORDER BY pct_chg DESC, amount DESC, stock_ts_code
            LIMIT ?
            """,
            [served_date, MAX_STRONG_STOCKS],
        )
        if not strong_stocks:
            raise DuckDbSnapshotUnavailable(
                f"{served_date} 无 pct_chg>=7 的 strong stock"
            )

        themes, theme_table, theme_updated_at = _load_themes(
            connection,
            served_date,
        )
        if not themes:
            raise DuckDbSnapshotUnavailable(f"{served_date} 无可用 theme")

        captured = (now or datetime.now(BEIJING)).astimezone(BEIJING)
        captured_at = captured.isoformat()
        freshness = "fresh" if served_date == target_date else "historical"
        source_tables = (
            "fact_market_daily",
            "fact_stock_daily",
            theme_table,
        )
        source_updated_at = _latest_timestamp(
            market.get("updated_at"),
            stock_quality.get("source_updated_at"),
            theme_updated_at,
        )
        document: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "trade_date": served_date,
            "requested_trade_date": target_date,
            "served_trade_date": served_date,
            "generated_at": captured_at,
            "source": "duckdb:market_feature_store",
            "provider": (
                "duckdb_exact" if freshness == "fresh" else "duckdb_latest"
            ),
            "source_data_date": served_date,
            "source_updated_at": source_updated_at,
            "captured_at": captured_at,
            "freshness": freshness,
            "quality": "complete",
            "source_errors": [],
            "provenance": {
                "source_tables": list(source_tables),
                "source_updated_at": source_updated_at,
                "field_mapping": {
                    "market.amount_ratio": "fact_market_daily.volume_ratio",
                    "market.decliners": "fact_stock_daily.pct_chg < 0",
                },
            },
            "market": {
                "stage": str(market.get("market_stage") or "未知阶段"),
                "total_amount": _number(market.get("total_amount")),
                "amount_ratio": _number(market.get("volume_ratio")),
                "advancers": int(
                    market.get("advancers")
                    or stock_quality.get("advancers")
                    or 0
                ),
                "decliners": int(stock_quality.get("decliners") or 0),
                "limit_up": int(market.get("limit_up") or 0),
                "limit_down": int(market.get("limit_down") or 0),
                "capacity_top3": _capacity_top3(market),
            },
            "themes": themes,
            "strong_stocks": [
                {
                    "stock_name": str(row.get("stock_name") or ""),
                    "stock_ts_code": str(row.get("stock_ts_code") or ""),
                    "concepts": [],
                    "pct_chg": _number(row.get("pct_chg")),
                    "amount": _number(row.get("amount")),
                }
                for row in strong_stocks
            ],
        }
        return DuckDbSnapshotCandidate(
            trade_date=served_date,
            document=document,
            source_tables=source_tables,
            source_updated_at=source_updated_at,
        )
    except duckdb.Error as exc:
        raise DuckDbSnapshotUnavailable(
            f"DuckDB 查询失败: {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        connection.close()


def _select_trade_date(
    connection: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    allow_latest_before: bool,
) -> str:
    operator = "<=" if allow_latest_before else "="
    row = connection.execute(
        f"""
        SELECT max(trade_date)
        FROM fact_market_daily
        WHERE trade_date {operator} ?::DATE
        """,
        [target_date],
    ).fetchone()
    value = row[0] if row else None
    if value is None:
        mode = "或更早日期" if allow_latest_before else ""
        raise DuckDbSnapshotUnavailable(
            f"fact_market_daily 缺少 {target_date}{mode}"
        )
    return _date_text(value)


def _require_stock_quality(quality: dict[str, Any]) -> None:
    row_count = int(quality.get("row_count") or 0)
    if row_count < MIN_STOCK_ROWS:
        raise DuckDbSnapshotUnavailable(
            f"stock rows {row_count} < {MIN_STOCK_ROWS}"
        )
    required = math.ceil(row_count * MIN_FIELD_COMPLETENESS)
    for field in ("code_count", "pct_count", "amount_count"):
        count = int(quality.get(field) or 0)
        if count < required:
            raise DuckDbSnapshotUnavailable(
                f"stock {field} {count}/{row_count} < {MIN_FIELD_COMPLETENESS:.0%}"
            )


def _load_themes(
    connection: duckdb.DuckDBPyConnection,
    trade_date: str,
) -> tuple[list[dict[str, object]], str, object | None]:
    try:
        rows = _fetch_all_dicts(
            connection,
            """
            SELECT theme_name, sector_name, limit_up_count, strength,
                   cycle_status, updated_at
            FROM fact_mainline_sector_daily
            WHERE trade_date = ?::DATE
              AND theme_name IS NOT NULL
            ORDER BY theme_name, sector_name
            """,
            [trade_date],
        )
    except duckdb.Error:
        rows = []
    if rows:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["theme_name"]), []).append(row)
        themes: list[dict[str, object]] = []
        for theme_name, items in grouped.items():
            strengths = [
                value
                for item in items
                if (value := _number(item.get("strength"))) is not None
            ]
            statuses = sorted(
                {
                    str(item["cycle_status"])
                    for item in items
                    if item.get("cycle_status")
                }
            )
            themes.append(
                {
                    "concept": theme_name,
                    "priority_score": max(strengths, default=0.0),
                    "trigger_types": ["duckdb_mainline"],
                    "limit_up_count": sum(
                        int(item.get("limit_up_count") or 0) for item in items
                    ),
                    "new_high_count": None,
                    "strong_stock_count": None,
                    "sectors": [str(item.get("sector_name") or "") for item in items],
                    "cycle_statuses": statuses,
                }
            )
        themes.sort(
            key=lambda item: (
                -float(item["priority_score"]),
                str(item["concept"]),
            )
        )
        return (
            themes,
            "fact_mainline_sector_daily",
            _latest_timestamp(*(row.get("updated_at") for row in rows)),
        )

    rows = _fetch_all_dicts(
        connection,
        """
        SELECT sector_name, pct_chg, amount, diff_ratio, strength, updated_at
        FROM fact_sector_daily
        WHERE trade_date = ?::DATE
          AND sector_name IS NOT NULL
        ORDER BY coalesce(strength, pct_chg) DESC NULLS LAST,
                 amount DESC NULLS LAST,
                 sector_name
        LIMIT 20
        """,
        [trade_date],
    )
    themes = [
        {
            "concept": str(row.get("sector_name") or ""),
            "priority_score": _number(row.get("strength"))
            or _number(row.get("pct_chg"))
            or 0.0,
            "trigger_types": ["duckdb_sector_strength"],
            "limit_up_count": None,
            "new_high_count": None,
            "strong_stock_count": None,
            "pct_chg": _number(row.get("pct_chg")),
            "amount": _number(row.get("amount")),
            "diff_ratio": _number(row.get("diff_ratio")),
        }
        for row in rows
    ]
    return (
        themes,
        "fact_sector_daily",
        _latest_timestamp(*(row.get("updated_at") for row in rows)),
    )


def _capacity_top3(market: dict[str, Any]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index in (1, 2, 3):
        industry = str(market.get(f"industry_{index}") or "").strip()
        ratio = _number(market.get(f"industry_{index}_ratio"))
        if industry:
            result.append({"industry": industry, "ratio": ratio})
    return result


def _fetch_one_dict(
    connection: duckdb.DuckDBPyConnection,
    sql: str,
    parameters: list[object],
) -> dict[str, Any] | None:
    cursor = connection.execute(sql, parameters)
    row = cursor.fetchone()
    if row is None:
        return None
    names = [item[0] for item in cursor.description]
    return dict(zip(names, row, strict=True))


def _fetch_all_dicts(
    connection: duckdb.DuckDBPyConnection,
    sql: str,
    parameters: list[object],
) -> list[dict[str, Any]]:
    cursor = connection.execute(sql, parameters)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _date_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _latest_timestamp(*values: object) -> str | None:
    timestamps = [
        value
        for value in values
        if isinstance(value, (date, datetime))
    ]
    if not timestamps:
        return None
    latest = max(
        value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time())
        for value in timestamps
    )
    return latest.isoformat()
