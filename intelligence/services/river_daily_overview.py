"""Daily-first river projection. Read-only canonical DuckDB views; no model calls.

A point is keyed by sector code AND name (provider renames are not silently spliced).
Missing cells remain null. No cumulative return is calculated across missing sessions.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

MARKET_FIELDS = (
    "sh_index_open", "sh_index_high", "sh_index_low", "sh_index_close", "sh_index_pct_chg",
    "total_amount", "amount_vs_yesterday_pct", "amount_ma20", "advancers", "limit_up", "limit_down",
    "market_stage", "stage_day", "volume_state", "strength_avg_pct", "sh_index_source",
)


def rows(con: Any, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    result = con.execute(sql, params or [])
    names = [item[0] for item in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def clean(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def daily_overview(db_path: Path, *, days: int = 20, end: date | None = None) -> dict[str, Any]:
    if not 5 <= days <= 120:
        raise ValueError("days must be between 5 and 120")
    if not db_path.is_file():
        raise FileNotFoundError("market database is not available")
    import duckdb

    with duckdb.connect(str(db_path), read_only=True) as con:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "fact_market_daily" not in tables:
            raise ValueError("fact_market_daily is unavailable")
        columns = {r[0] for r in con.execute("DESCRIBE fact_market_daily").fetchall()}
        selected = [field if field in columns else f"NULL AS {field}" for field in MARKET_FIELDS]
        calendar = [str(r[0])[:10] for r in con.execute("SELECT DISTINCT CAST(trade_date AS DATE) FROM fact_market_daily ORDER BY 1 DESC LIMIT 800").fetchall()][::-1]
        latest = calendar[-1] if calendar else None
        end_day = end.isoformat() if end else latest
        if not end_day:
            return {"days": [], "calendar": [], "sectors": [], "latest_market_date": None, "latest_sector_date": None,
                    "gaps": ["盘面库没有交易日"], "sector_point_fields": ["pct_chg", "amount", "diff_ratio"]}
        data = rows(con, "SELECT CAST(trade_date AS DATE) AS date," + ",".join(selected)
                    + " FROM fact_market_daily WHERE trade_date <= CAST(? AS DATE) ORDER BY trade_date DESC LIMIT ?", [end_day, days + 19])
        data.reverse()
        # Twenty-session prewarm makes MAs independent of the requested visible range.
        for i, row in enumerate(data):
            for width in [5, 20]:
                values = [r["sh_index_close"] for r in data[max(0, i - width + 1):i + 1]]
                row[f"ma{width}"] = sum(values) / width if len(values) == width and all(v is not None and math.isfinite(v) for v in values) else None
        data = [{k: clean(v) for k, v in row.items()} for row in data[-days:]]
        if not data:
            return {"days": [], "calendar": calendar, "sectors": [], "latest_market_date": latest, "latest_sector_date": None,
                    "gaps": ["指定截止日之前没有盘面数据"], "sector_point_fields": ["pct_chg", "amount", "diff_ratio"]}
        day_index = {row["date"]: i for i, row in enumerate(data)}
        sector_map: dict[tuple[str, str], dict[str, Any]] = {}
        gaps = []
        latest_sector = None
        per_day: dict[str, list[dict[str, Any]]] = {day: [] for day in day_index}
        if "fact_sector_daily" in tables:
            latest_sector = clean(con.execute("SELECT max(trade_date) FROM fact_sector_daily").fetchone()[0])
            for row in rows(con, """SELECT trade_date, sector_ts_code, sector_name, pct_chg, amount, diff_ratio
                                      FROM fact_sector_daily WHERE trade_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                                      ORDER BY trade_date, sector_ts_code, sector_name""", [data[0]["date"], data[-1]["date"]]):
                day = str(row["trade_date"])[:10]
                if day not in day_index:
                    continue
                key = (str(row["sector_ts_code"]), str(row["sector_name"]))
                if key not in sector_map:
                    sector_map[key] = {"id": key[0], "name": key[1], "key": "|".join(key), "points": [None] * len(data)}
                point = [clean(row[k]) for k in ["pct_chg", "amount", "diff_ratio"]]
                existing = sector_map[key]["points"][day_index[day]]
                if existing is not None:
                    # Broken publication uniqueness is data corruption, not a license to ANY_VALUE.
                    raise ValueError(f"duplicate published sector row: {day} {key[0]}")
                sector_map[key]["points"][day_index[day]] = point
                per_day[day].append({"id": key[0], "name": key[1], "pct_chg": point[0], "amount": point[1], "diff_ratio": point[2]})
        else:
            gaps.append("fact_sector_daily 不可用；没有用旧库或昨日值补齐。")
        for row in data:
            group = per_day[row["date"]]
            valid = [item for item in group if item["pct_chg"] is not None]
            row["sector_count"] = len(group)
            row["sector_valid_count"] = len(valid)
            row["sector_up_count"] = sum(item["pct_chg"] > 0 for item in valid)
            row["sector_down_count"] = sum(item["pct_chg"] < 0 for item in valid)
            row["sector_flat_count"] = sum(item["pct_chg"] == 0 for item in valid)
            row["sector_gainers"] = sorted([x for x in valid if x["pct_chg"] > 0], key=lambda x: (-x["pct_chg"], x["id"]))[:8]
            row["sector_losers"] = sorted([x for x in valid if x["pct_chg"] < 0], key=lambda x: (x["pct_chg"], x["id"]))[:8]
            row["sector_amount_leaders"] = sorted([x for x in group if x["amount"] is not None], key=lambda x: (-x["amount"], x["id"]))[:8]
            row["limitup"] = None
        if "fact_limit_advance_daily" in tables:
            advances = rows(con, """SELECT trade_date, stock_ts_code, stock_name, boards, theme, pct_chg
                    FROM fact_limit_advance_daily WHERE trade_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                    ORDER BY trade_date, boards DESC, stock_ts_code""", [data[0]["date"], data[-1]["date"]])
            for item in advances:
                day = str(item["trade_date"])[:10]
                if day not in day_index:
                    continue
                current = data[day_index[day]]
                if current["limitup"] is None:
                    current["limitup"] = {"count": 0, "max_boards": 0, "stocks": []}
                current["limitup"]["count"] += 1
                current["limitup"]["max_boards"] = max(current["limitup"]["max_boards"], int(item["boards"] or 0))
                current["limitup"]["stocks"].append({k: clean(v) for k, v in item.items() if k != "trade_date"})
        else:
            gaps.append("连板台账不可用。")
        gaps.extend([
            "指数当前展示上证；其他 A 股宽基尚未接入此读取面。",
            "板块可能重叠，板块成交额不可相加当作全市场成交额。",
            "缺失数据不是 0；连板当日无明细时无法区分无连板与未入库。",
            "行情为当前 canonical 快照，不冒充当时已入库的严格历史回放。",
        ])
        return {
            "schema_version": 1, "days": data, "calendar": calendar,
            "start": data[0]["date"], "end": data[-1]["date"],
            "latest_market_date": latest, "latest_sector_date": latest_sector,
            "sectors": sorted(sector_map.values(), key=lambda sector: (sector["name"], sector["id"])),
            "sector_point_fields": ["pct_chg", "amount", "diff_ratio"],
            "sector_identity": "provider_code_and_name_no_implicit_alias_merge",
            "knowledge_mode": "current_canonical_snapshot", "amount_unit": "亿元",
            "sources": ["fact_market_daily", "fact_sector_daily (published view)", "fact_limit_advance_daily"],
            "gaps": gaps,
        }
