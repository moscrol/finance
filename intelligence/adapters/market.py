from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store import query as market_query
from market_feature_store.db import DB_PATH
from market_feature_store.signals import DOUBLE_RED_SQL


MARKET_DAILY_COLUMNS = [
    "trade_date",
    "market_stage",
    "stage_day",
    "ice_point",
    "total_amount",
    "amount_vs_yesterday_pct",
    "amount_ma20",
    "volume_ratio",
    "volume_state",
    "advancers",
    "limit_up",
    "limit_down",
    "sh_week_ma",
    "sh_deviation_pct",
    "top3_industry_ratio",
    "concentration_state",
    "industry_1",
    "industry_1_ratio",
    "industry_2",
    "industry_2_ratio",
    "industry_3",
    "industry_3_ratio",
    "note",
    "source",
    "updated_at",
    "strength_avg_pct",
    "strength_amount_pct",
    "strength_amount",
    "strength_marginal_pct",
    "strength_yesterday_avg_pct",
    "strength_ma5_avg_pct",
    "strength_ma20_avg_pct",
    "strength_status",
    "strength_source",
    "strength_updated_at",
    "stock_high_count_history",
    "stock_high_count_3y",
    "stock_high_count_2y",
    "stock_high_count_1y",
    "stock_high_count_120d",
    "stock_high_count_60d",
    "stock_high_count_20d",
    "stock_high_source",
    "stock_high_updated_at",
    "sh_index_close",
    "sh_index_pct_chg",
    "sh_index_open",
    "sh_index_high",
    "sh_index_low",
    "sh_index_volume",
    "sh_index_amount",
    "sh_index_source",
    "sh_index_updated_at",
]

ALLOWED_TABLES = {
    "dim_sector",
    "fact_limit_advance_daily",
    "fact_market_daily",
    "fact_sector_daily",
    "fact_sector_period_rank_daily",
    "fact_sector_stock_daily",
    "fact_stock_daily",
    "fact_stock_high_daily",
    "fact_sw_l1_daily",
    "fact_theme_limit_heat_daily",
    "fact_theme_limit_stock_daily",
}

BROAD_HIGH_DIRECTION_THEMES = {
    "芯片",
    "芯片概念",
    "机器人",
    "机器人概念",
    "人工智能",
    "DeepSeek",
    "DeepSeek概念",
    "AI应用",
    "AI智能体",
    "光伏",
    "储能",
    "军工",
    "固态电池",
    "低空经济",
}


@dataclass(frozen=True)
class MarketAdapter:
    db_path: str | Path | None = None

    @property
    def resolved_db_path(self) -> Path:
        return Path(self.db_path).expanduser() if self.db_path else DB_PATH

    def connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.resolved_db_path), read_only=True)

    def health(self) -> dict[str, Any]:
        if self.db_path is None:
            return {"ok": True, "db_path": str(self.resolved_db_path), "data": market_query.health(), "warnings": [], "errors": []}
        con = self.connect()
        try:
            tables = con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_name
                """
            ).fetchall()
            return {"ok": True, "db_path": str(self.resolved_db_path), "tables": [row[0] for row in tables], "warnings": [], "errors": []}
        except Exception as exc:
            return {"ok": False, "db_path": str(self.resolved_db_path), "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def latest_date(self, table: str = "fact_market_daily") -> str | None:
        self._validate_table(table)
        con = self.connect()
        try:
            row = con.execute(f"SELECT MAX(trade_date) FROM {table}").fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            con.close()

    def get_market_daily(self, date: str | None = None) -> dict[str, Any]:
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_market_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "data": None, "warnings": ["fact_market_daily has no rows"], "errors": []}
            row = con.execute(
                f"SELECT {', '.join(MARKET_DAILY_COLUMNS)} FROM fact_market_daily WHERE trade_date = ?",
                [trade_date],
            ).fetchone()
            if row is None:
                return {"found": False, "trade_date": str(trade_date), "data": None, "warnings": ["market daily row not found"], "errors": []}
            data = {column: self._serialize_value(value) for column, value in zip(MARKET_DAILY_COLUMNS, row)}
            data["_source_meta"] = self._source_meta(
                table="fact_market_daily",
                entity="market",
                valid_time=data.get("trade_date"),
                source_time=data.get("updated_at"),
                source=data.get("source"),
            )
            return {"found": True, "trade_date": str(data["trade_date"]), "data": data, "warnings": [], "errors": []}
        except Exception as exc:
            return {"found": False, "trade_date": date, "data": None, "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def get_capacity_sectors(self, date: str | None = None, top: int = 3) -> dict[str, Any]:
        market = self.get_market_daily(date)
        if not market["found"]:
            return {
                "found": False,
                "trade_date": market["trade_date"],
                "capacity_sectors": [],
                "warnings": market["warnings"],
                "errors": market["errors"],
            }
        data = market["data"]
        sectors = []
        for rank in range(1, 4):
            name = data.get(f"industry_{rank}")
            ratio = data.get(f"industry_{rank}_ratio")
            if not name:
                continue
            sectors.append({
                "rank": rank,
                "name": name,
                "ratio": ratio,
                "capacity_type": self._capacity_type(ratio),
                "_source_meta": data.get("_source_meta", {}),
                "_source_fields": {
                    "name": f"industry_{rank}",
                    "ratio": f"industry_{rank}_ratio",
                },
            })
        return {
            "found": True,
            "trade_date": market["trade_date"],
            "market_stage": data.get("market_stage"),
            "top3_industry_ratio": data.get("top3_industry_ratio"),
            "capacity_sectors": sectors[:top],
            "warnings": [],
            "errors": [],
        }

    def get_double_red_themes(self, date: str | None = None, top: int = 50) -> dict[str, Any]:
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_sector_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "themes": [], "warnings": ["fact_sector_daily has no rows"], "errors": []}
            sector_count = con.execute(
                "SELECT COUNT(*) FROM fact_sector_daily WHERE trade_date = ?",
                [trade_date],
            ).fetchone()[0]
            if sector_count == 0:
                return {"found": False, "trade_date": str(trade_date), "themes": [], "warnings": ["sector daily rows not found"], "errors": []}
            capacity = self.get_capacity_sectors(str(trade_date), top=3)
            capacity_names = {item["name"] for item in capacity.get("capacity_sectors", [])}
            rows = con.execute(
                f"""
                SELECT sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount,
                       source, updated_at
                FROM fact_sector_daily
                WHERE trade_date = ? AND {DOUBLE_RED_SQL}
                ORDER BY diff_ratio DESC, amount DESC
                LIMIT ?
                """,
                [trade_date, top],
            ).fetchall()
            columns = [
                "sector_ts_code",
                "sector_name",
                "sw_l1",
                "pct_chg",
                "diff_ratio",
                "amount",
                "source",
                "updated_at",
            ]
            themes = []
            for row in rows:
                item = {column: self._serialize_value(value) for column, value in zip(columns, row)}
                item["in_capacity_top3"] = item.get("sw_l1") in capacity_names
                item["_source_meta"] = self._source_meta(
                    table="fact_sector_daily",
                    entity=item.get("sector_ts_code") or item.get("sector_name"),
                    valid_time=trade_date,
                    source_time=item.get("updated_at"),
                    source=item.get("source"),
                )
                themes.append(item)
            return {
                "found": True,
                "trade_date": str(trade_date),
                "definition": DOUBLE_RED_SQL,
                "count": len(themes),
                "themes": themes,
                "warnings": capacity.get("warnings", []),
                "errors": capacity.get("errors", []),
            }
        except Exception as exc:
            return {"found": False, "trade_date": date, "themes": [], "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def get_limit_heat_themes(self, date: str | None = None, limit: int = 30) -> dict[str, Any]:
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_theme_limit_heat_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "themes": [], "warnings": ["fact_theme_limit_heat_daily has no rows"], "errors": []}
            rows = con.execute(
                """
                SELECT sector_name, limit_up_count, total_count, market_share, fd_amount,
                       rank, source, updated_at
                FROM fact_theme_limit_heat_daily
                WHERE trade_date = ? AND COALESCE(limit_up_count, 0) >= 2
                ORDER BY limit_up_count DESC, market_share DESC
                LIMIT ?
                """,
                [trade_date, limit],
            ).fetchall()
            columns = [
                "sector_name",
                "limit_up_count",
                "total_count",
                "market_share",
                "fd_amount",
                "rank",
                "source",
                "updated_at",
            ]
            themes = []
            for row in rows:
                item = {column: self._serialize_value(value) for column, value in zip(columns, row)}
                item["score"] = min(4 + float(item.get("limit_up_count") or 0) * 0.35, 18)
                item["_source_meta"] = self._source_meta(
                    table="fact_theme_limit_heat_daily",
                    entity=item.get("sector_name"),
                    valid_time=trade_date,
                    source_time=item.get("updated_at"),
                    source=item.get("source"),
                )
                themes.append(item)
            return {"found": True, "trade_date": str(trade_date), "count": len(themes), "themes": themes, "warnings": [], "errors": []}
        except Exception as exc:
            return {"found": False, "trade_date": date, "themes": [], "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def get_limit_advance_clusters(self, date: str | None = None) -> dict[str, Any]:
        capacity = self.get_capacity_sectors(date, top=3)
        capacity_names = {item["name"] for item in capacity.get("capacity_sectors", [])}
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_limit_advance_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "themes": [], "warnings": ["fact_limit_advance_daily has no rows"], "errors": []}
            rows = con.execute(
                """
                SELECT theme,
                       COUNT(*) AS stock_count,
                       MAX(boards) AS max_boards,
                       string_agg(stock_name, '、' ORDER BY boards DESC, stock_name) AS stock_names,
                       string_agg(stock_ts_code, '、' ORDER BY boards DESC, stock_name) AS stock_codes,
                       MAX(updated_at) AS updated_at
                FROM fact_limit_advance_daily
                WHERE trade_date = ? AND boards >= 2
                GROUP BY theme
                ORDER BY stock_count DESC, max_boards DESC, theme
                """,
                [trade_date],
            ).fetchall()
            columns = [
                "theme",
                "stock_count",
                "max_boards",
                "stock_names",
                "stock_codes",
                "updated_at",
            ]
            themes = []
            for row in rows:
                item = {column: self._serialize_value(value) for column, value in zip(columns, row)}
                stock_codes = [code for code in str(item.get("stock_codes") or "").split("、") if code]
                dominant_sw = self._dominant_sw_for_stocks(con, str(trade_date), stock_codes)
                in_capacity = dominant_sw.get("sw_l1") in capacity_names
                count = int(item.get("stock_count") or 0)
                max_boards = int(item.get("max_boards") or 0)
                item["sw_l1"] = dominant_sw.get("sw_l1") or ""
                item["dominant_sw_l1"] = dominant_sw.get("sw_l1") or ""
                item["dominant_sw_l1_counts"] = dominant_sw.get("counts", [])[:5]
                item["in_capacity_top3"] = in_capacity
                item["score"] = 65 + count * 8 + max_boards * 4 + (18 if in_capacity else 0) if count >= 2 else 18 + max_boards * 3 + (6 if in_capacity else 0)
                item["advance_stocks"] = self._advance_stocks(con, str(trade_date), str(item.get("theme") or ""))
                item["_source_meta"] = self._source_meta(
                    table="fact_limit_advance_daily",
                    entity=item.get("theme") or "unmapped",
                    valid_time=trade_date,
                    source_time=item.get("updated_at"),
                    source="derived aggregate",
                    derivation={
                        "operation": "group_by",
                        "group_by": ["theme"],
                        "filters": ["boards >= 2"],
                    },
                )
                themes.append(item)
            return {
                "found": True,
                "trade_date": str(trade_date),
                "count": len(themes),
                "themes": themes,
                "warnings": capacity.get("warnings", []),
                "errors": capacity.get("errors", []),
            }
        except Exception as exc:
            return {"found": False, "trade_date": date, "themes": [], "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def get_period_rank_themes(self, date: str | None = None, rank_limit: int = 10) -> dict[str, Any]:
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_sector_period_rank_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "themes": [], "warnings": ["fact_sector_period_rank_daily has no rows"], "errors": []}
            rows = con.execute(
                """
                SELECT period_type, rank, sector_name, change_pct, limit_up_count,
                       badge, source, updated_at
                FROM fact_sector_period_rank_daily
                WHERE trade_date = ? AND rank <= ?
                ORDER BY period_type, rank
                """,
                [trade_date, rank_limit],
            ).fetchall()
            columns = [
                "period_type",
                "rank",
                "sector_name",
                "change_pct",
                "limit_up_count",
                "badge",
                "source",
                "updated_at",
            ]
            raw = [{column: self._serialize_value(value) for column, value in zip(columns, row)} for row in rows]
            seen_periods: dict[str, set[str]] = defaultdict(set)
            for item in raw:
                seen_periods[str(item.get("sector_name") or "")].add(str(item.get("period_type") or ""))
            themes = []
            for item in raw:
                periods = seen_periods[str(item.get("sector_name") or "")]
                item["score"] = 6 + max(0, 11 - int(item.get("rank") or 11)) * 0.8 + max(0, len(periods) - 1) * 5
                item["_source_meta"] = self._source_meta(
                    table="fact_sector_period_rank_daily",
                    entity=item.get("sector_name"),
                    valid_time=trade_date,
                    source_time=item.get("updated_at"),
                    source=item.get("source"),
                )
                themes.append(item)
            return {"found": True, "trade_date": str(trade_date), "count": len(themes), "themes": themes, "warnings": [], "errors": []}
        except Exception as exc:
            return {"found": False, "trade_date": date, "themes": [], "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def get_new_high_directions(self, date: str | None = None, limit: int = 60) -> dict[str, Any]:
        capacity = self.get_capacity_sectors(date, top=3)
        capacity_names = {item["name"] for item in capacity.get("capacity_sectors", [])}
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_stock_high_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "themes": [], "warnings": ["fact_stock_high_daily has no rows"], "errors": []}
            rows = con.execute(
                """
                WITH high_stocks AS (
                  SELECT stock_ts_code, stock_name, primary_high_label, amount, pct_chg,
                         updated_at
                  FROM fact_stock_high_daily
                  WHERE trade_date = ? AND amount IS NOT NULL
                ),
                joined AS (
                  SELECT s.sector_name, s.sw_l1, h.stock_ts_code, h.stock_name,
                         h.primary_high_label, h.amount, h.pct_chg,
                         h.updated_at AS high_updated_at,
                         s.updated_at AS sector_updated_at
                  FROM fact_sector_stock_daily s
                  JOIN high_stocks h ON h.stock_ts_code = s.stock_ts_code
                  WHERE s.trade_date = ? AND s.sector_name IS NOT NULL AND s.sector_name <> ''
                )
                SELECT sector_name,
                       sw_l1,
                       COUNT(DISTINCT stock_ts_code) AS high_count,
                       SUM(amount) AS high_amount,
                       MAX(high_updated_at) AS high_updated_at,
                       MAX(sector_updated_at) AS sector_updated_at
                FROM joined
                GROUP BY 1, 2
                HAVING COUNT(DISTINCT stock_ts_code) >= 2 AND SUM(amount) >= 80
                ORDER BY high_amount DESC NULLS LAST, high_count DESC, sector_name
                LIMIT ?
                """,
                [trade_date, trade_date, limit],
            ).fetchall()
            columns = [
                "sector_name",
                "sw_l1",
                "high_count",
                "high_amount",
                "high_updated_at",
                "sector_updated_at",
            ]
            themes = []
            for row in rows:
                item = {column: self._serialize_value(value) for column, value in zip(columns, row)}
                theme = item.get("sector_name")
                if not theme or theme in BROAD_HIGH_DIRECTION_THEMES:
                    continue
                high_count = int(item.get("high_count") or 0)
                high_amount = float(item.get("high_amount") or 0)
                in_capacity = item.get("sw_l1") in capacity_names
                if high_count < 3 and not in_capacity:
                    continue
                item["in_capacity_top3"] = in_capacity
                item["score"] = 18 + min(high_count * 1.4, 22) + min(high_amount / 80, 18) + (10 if in_capacity else 0)
                source_times = [
                    str(value)
                    for value in (
                        item.get("high_updated_at"),
                        item.get("sector_updated_at"),
                    )
                    if value
                ]
                item["_source_meta"] = self._source_meta(
                    table="fact_stock_high_daily+fact_sector_stock_daily",
                    entity=item.get("sector_name"),
                    valid_time=trade_date,
                    source_time=max(source_times) if source_times else None,
                    source="derived aggregate",
                    derivation={
                        "operation": "join_group_by",
                        "input_tables": [
                            "fact_stock_high_daily",
                            "fact_sector_stock_daily",
                        ],
                        "group_by": ["sector_name", "sw_l1"],
                    },
                )
                themes.append(item)
            return {
                "found": True,
                "trade_date": str(trade_date),
                "count": len(themes),
                "themes": themes,
                "warnings": capacity.get("warnings", []),
                "errors": capacity.get("errors", []),
            }
        except Exception as exc:
            return {"found": False, "trade_date": date, "themes": [], "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def get_theme_stock_signals(self, date: str | None, themes: list[str], limit: int = 10) -> dict[str, Any]:
        con = self.connect()
        try:
            trade_date = date or self._latest_date_with_connection(con, "fact_sector_stock_daily")
            if trade_date is None:
                return {"found": False, "trade_date": None, "signals": {}, "warnings": ["fact_sector_stock_daily has no rows"], "errors": []}
            signals = {}
            for theme in themes:
                if not theme:
                    continue
                signals[theme] = {
                    "strong_stocks": self._strong_stocks(con, str(trade_date), theme, limit),
                    "new_high_stocks": self._new_high_stocks(con, str(trade_date), theme, limit),
                }
                high_count = len(signals[theme]["new_high_stocks"])
                signals[theme]["new_high_cluster_score"] = min(12 + high_count * 2, 26) if high_count >= 2 else 0
            return {"found": True, "trade_date": str(trade_date), "signals": signals, "warnings": [], "errors": []}
        except Exception as exc:
            return {"found": False, "trade_date": date, "signals": {}, "warnings": [], "errors": [str(exc)]}
        finally:
            con.close()

    def market_daily_row(self, date: str) -> dict[str, Any] | None:
        """``fact_market_daily`` 指定交易日整行（无该日→None）。

        用途：可证伪点回检（``market_daily`` metric）核对「某日涨家/涨停/成交额是否达标」。
        """
        con = self.connect()
        try:
            rows = self._rows(con.execute(
                "SELECT * FROM fact_market_daily WHERE trade_date = ?", [date]
            ))
            if not rows:
                return None
            return self._serialized_row(rows[0])
        finally:
            con.close()

    def interval_returns(self, stocks: list[str], start: str, end: str) -> dict[str, dict[str, Any]]:
        """指定个股在 ``[start, end]`` 的区间涨幅（首日 pre_close → 末日 close）。

        ``stocks`` 可填股票名或 ts_code（任一匹配）。返回 ``{名称: {...}, ts_code: {...}}``
        双键映射，便于上游用名称或代码任意一种回查。区间内无行情（停牌/未上市/名称
        不匹配）的个股不会出现在结果里——交由调用方判定为 ``unverifiable``。

        用途：可证伪点回检（``checkpoint recheck``）核对「某股 N 天涨幅是否达标」。
        与 ``market_feature_store`` 的 ``interval_gainers`` 同一套区间口径，只是按指定
        个股精确取数，避免全市场排序的开销。
        """
        names = [str(s).strip() for s in (stocks or []) if str(s).strip()]
        if not names:
            return {}
        con = self.connect()
        try:
            placeholders = ",".join("?" for _ in names)
            rows = self._rows(con.execute(
                f"""
                WITH w AS (
                    SELECT stock_ts_code, stock_name, trade_date, close, pre_close,
                           ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY trade_date) AS rn_asc,
                           ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY trade_date DESC) AS rn_desc,
                           COUNT(*) OVER (PARTITION BY stock_ts_code) AS ndays
                    FROM fact_stock_daily
                    WHERE trade_date >= ? AND trade_date <= ?
                      AND (stock_name IN ({placeholders}) OR stock_ts_code IN ({placeholders}))
                ),
                agg AS (
                    SELECT stock_ts_code, stock_name, ndays,
                           MAX(CASE WHEN rn_asc = 1 THEN pre_close END) AS base_close,
                           MAX(CASE WHEN rn_desc = 1 THEN close END) AS end_close,
                           MIN(trade_date) AS actual_start,
                           MAX(trade_date) AS actual_end
                    FROM w GROUP BY stock_ts_code, stock_name, ndays
                )
                SELECT stock_ts_code, stock_name, ndays, actual_start, actual_end,
                       base_close, end_close,
                       (end_close / base_close - 1) * 100 AS interval_gain
                FROM agg
                WHERE base_close IS NOT NULL AND base_close > 0
                """,
                [start, end, *names, *names],
            ))
            out: dict[str, dict[str, Any]] = {}
            for row in rows:
                record = self._serialized_row(row)
                code = str(record.get("stock_ts_code") or "")
                name = str(record.get("stock_name") or "")
                if name:
                    out[name] = record
                if code:
                    out[code] = record
            return out
        finally:
            con.close()

    @staticmethod
    def _latest_date_with_connection(con: duckdb.DuckDBPyConnection, table: str) -> str | None:
        MarketAdapter._validate_table(table)
        row = con.execute(f"SELECT MAX(trade_date) FROM {table}").fetchone()
        return str(row[0]) if row and row[0] else None

    @staticmethod
    def _rows(cur: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
        names = [description[0] for description in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]

    def _dominant_sw_for_stocks(self, con: duckdb.DuckDBPyConnection, trade_date: str, stock_codes: list[str]) -> dict[str, Any]:
        if not stock_codes:
            return {"sw_l1": "", "counts": []}
        placeholders = ",".join("?" for _ in stock_codes)
        rows = self._rows(con.execute(
            f"""
            SELECT sw_l1, COUNT(*) AS cnt
            FROM fact_sector_stock_daily
            WHERE trade_date = ? AND stock_ts_code IN ({placeholders})
              AND sw_l1 IS NOT NULL AND sw_l1 <> ''
            GROUP BY 1
            ORDER BY cnt DESC, sw_l1
            """,
            [trade_date, *stock_codes],
        ))
        return {"sw_l1": rows[0]["sw_l1"] if rows else "", "counts": [self._serialized_row(row) for row in rows]}

    def _advance_stocks(self, con: duckdb.DuckDBPyConnection, trade_date: str, theme: str) -> list[dict[str, Any]]:
        rows = self._rows(con.execute(
                """
                WITH advance AS (
                  SELECT stock_name, stock_ts_code, boards, pct_chg, updated_at
                  FROM fact_limit_advance_daily
                  WHERE trade_date = ? AND theme = ? AND boards >= 2
                ),
                stock_base AS (
                  SELECT stock_ts_code,
                     MAX(pct_chg) AS pct_chg,
                     MAX(amount) AS amount,
                     MAX(high_status_label) AS high_status_label,
                     MAX(updated_at) AS updated_at
                  FROM fact_sector_stock_daily
                  WHERE trade_date = ?
                    AND stock_ts_code IN (SELECT stock_ts_code FROM advance)
                  GROUP BY stock_ts_code
                ),
                high_base AS (
                  SELECT stock_ts_code, primary_high_label, updated_at
                  FROM fact_stock_high_daily
                  WHERE trade_date = ?
                    AND stock_ts_code IN (SELECT stock_ts_code FROM advance)
                )
                SELECT a.stock_name,
                       a.stock_ts_code,
                       a.boards,
                       COALESCE(s.pct_chg, a.pct_chg) AS pct_chg,
                       s.amount,
                       COALESCE(s.high_status_label, h.primary_high_label) AS high_status_label,
                       GREATEST(a.updated_at, s.updated_at, h.updated_at) AS updated_at
                FROM advance a
                LEFT JOIN stock_base s ON s.stock_ts_code = a.stock_ts_code
                LEFT JOIN high_base h ON h.stock_ts_code = a.stock_ts_code
                ORDER BY a.boards DESC, s.amount DESC NULLS LAST, a.stock_name
                """,
                [trade_date, theme, trade_date, trade_date],
            ))
        out = []
        for row in rows:
            item = self._serialized_row(row)
            item["_source_meta"] = self._source_meta(
                table="fact_limit_advance_daily+fact_sector_stock_daily+fact_stock_high_daily",
                entity=item.get("stock_ts_code") or item.get("stock_name"),
                valid_time=trade_date,
                source_time=item.get("updated_at"),
                source="derived join",
                derivation={
                    "operation": "left_join",
                    "input_tables": [
                        "fact_limit_advance_daily",
                        "fact_sector_stock_daily",
                        "fact_stock_high_daily",
                    ],
                },
            )
            out.append(item)
        return out

    def _strong_stocks(self, con: duckdb.DuckDBPyConnection, trade_date: str, theme: str, limit: int) -> list[dict[str, Any]]:
        rows = self._rows(con.execute(
                """
                SELECT stock_name, stock_ts_code, pct_chg, amount, high_status_label,
                       high_status, sqrt(amount) * pct_chg AS weighted, source, updated_at
                FROM fact_sector_stock_daily
                WHERE trade_date = ? AND sector_name = ? AND pct_chg IS NOT NULL AND amount IS NOT NULL
                ORDER BY weighted DESC NULLS LAST
                LIMIT ?
                """,
                [trade_date, theme, limit],
            ))
        out = []
        for row in rows:
            item = self._serialized_row(row)
            item["_source_meta"] = self._source_meta(
                table="fact_sector_stock_daily",
                entity=item.get("stock_ts_code") or item.get("stock_name"),
                valid_time=trade_date,
                source_time=item.get("updated_at"),
                source=item.get("source"),
            )
            out.append(item)
        return out

    def _new_high_stocks(self, con: duckdb.DuckDBPyConnection, trade_date: str, theme: str, limit: int) -> list[dict[str, Any]]:
        rows = self._rows(con.execute(
                """
                SELECT DISTINCT h.stock_name, h.stock_ts_code,
                       h.primary_high_label AS high_label, h.pct_chg, h.amount,
                       h.source, GREATEST(h.updated_at, s.updated_at) AS updated_at
                FROM fact_stock_high_daily h
                JOIN fact_sector_stock_daily s ON h.trade_date = s.trade_date AND h.stock_ts_code = s.stock_ts_code
                WHERE h.trade_date = ? AND s.sector_name = ?
                ORDER BY h.amount DESC NULLS LAST
                LIMIT ?
                """,
                [trade_date, theme, limit],
            ))
        out = []
        for row in rows:
            item = self._serialized_row(row)
            item["_source_meta"] = self._source_meta(
                table="fact_stock_high_daily+fact_sector_stock_daily",
                entity=item.get("stock_ts_code") or item.get("stock_name"),
                valid_time=trade_date,
                source_time=item.get("updated_at"),
                source=item.get("source"),
                derivation={
                    "operation": "inner_join",
                    "input_tables": [
                        "fact_stock_high_daily",
                        "fact_sector_stock_daily",
                    ],
                },
            )
            out.append(item)
        return out

    def _serialized_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: self._serialize_value(value) for key, value in row.items()}

    @staticmethod
    def _source_meta(
        *,
        table: str,
        entity: object,
        valid_time: object,
        source_time: object,
        source: object,
        derivation: dict[str, object] | None = None,
    ) -> dict[str, object]:
        meta: dict[str, object] = {
            "table": table,
            "entity": str(entity or ""),
            "valid_time": str(valid_time or ""),
            "source_time": str(source_time or ""),
            "source": str(source or table),
            "source_artifact": "db/market_feature_store.duckdb",
        }
        if derivation:
            meta["derivation"] = derivation
        return meta

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    @staticmethod
    def _validate_table(table: str) -> None:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"unsupported table: {table}")

    @staticmethod
    def _capacity_type(ratio: Any) -> str:
        if ratio is None:
            return "unknown"
        if ratio > 25:
            return "super_capacity"
        if ratio > 15:
            return "capacity"
        return "normal"
