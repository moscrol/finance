"""Canonical Market Feature Store 的只读板块分析数据适配器。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import duckdb

from ..db import DB_PATH


class SectorDataProvider:
    """把 canonical fact_* 行映射为回测和信号引擎使用的字典结构。"""

    _REQUIRED_RELATIONS = ("fact_market_daily", "fact_sector_daily")

    def __init__(self, db_path: str | Path = DB_PATH):
        path = Path(db_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"canonical DuckDB 不存在: {path}")
        self._conn = duckdb.connect(str(path), read_only=True)
        try:
            self._check_relations()
        except Exception:
            self._conn.close()
            raise

    def _check_relations(self) -> None:
        names = {
            row[0]
            for row in self._conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()
        }
        missing = [name for name in self._REQUIRED_RELATIONS if name not in names]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"canonical DuckDB 缺少关系: {joined}")

    def get_sector_price_matrix(
        self,
        start: str,
        end: str,
    ) -> dict[str, dict[str, float]]:
        rows = self._conn.execute(
            """
            SELECT trade_date, sector_ts_code, pct_chg
            FROM fact_sector_daily
            WHERE trade_date BETWEEN ? AND ?
              AND pct_chg IS NOT NULL
            ORDER BY trade_date, sector_ts_code
            """,
            [start, end],
        ).fetchall()
        matrix: dict[str, dict[str, float]] = defaultdict(dict)
        for trade_date, sector_ts_code, pct_chg in rows:
            matrix[str(trade_date)][sector_ts_code] = float(pct_chg)
        return dict(matrix)

    def get_sector_marginal(self, trade_date: str) -> dict[str, dict]:
        rows = self._conn.execute(
            """
            SELECT sector_ts_code, sector_name, diff_ratio, pct_chg, amount
            FROM fact_sector_daily
            WHERE trade_date = ?
            ORDER BY sector_ts_code
            """,
            [trade_date],
        ).fetchall()
        return {
            sector_ts_code: {
                "sector": sector_name,
                "diff_ratio": float(diff_ratio) if diff_ratio is not None else None,
                "pct_chg": float(pct_chg) if pct_chg is not None else None,
                "amount": float(amount) if amount is not None else None,
            }
            for sector_ts_code, sector_name, diff_ratio, pct_chg, amount in rows
        }

    def get_market_data(self, start: str, end: str) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT trade_date, total_amount, amount_vs_yesterday_pct,
                   limit_up, limit_down, sh_week_ma, sh_deviation_pct
            FROM fact_market_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [start, end],
        ).fetchall()
        return [
            {
                "date": str(row[0]),
                "volume": row[1],
                "volume_change": row[2],
                "limit_up": row[3],
                "limit_down": row[4],
                "week_ma": row[5],
                "deviation": row[6],
            }
            for row in rows
        ]

    def get_advancers(self, start: str, end: str) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT trade_date, advancers,
                   AVG(advancers) OVER (
                       ORDER BY trade_date
                       ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                   ) AS ma5
            FROM fact_market_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [start, end],
        ).fetchall()
        return [
            {
                "date": str(trade_date),
                "count": count,
                "ma5": float(ma5) if ma5 is not None else None,
            }
            for trade_date, count, ma5 in rows
        ]

    def get_trading_dates(self, start: str, end: str) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT DISTINCT trade_date
            FROM fact_sector_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            [start, end],
        ).fetchall()
        return [str(row[0]) for row in rows]

    def get_date_range(self) -> tuple[str | None, str | None]:
        row = self._conn.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM fact_sector_daily"
        ).fetchone()
        if not row or row[0] is None or row[1] is None:
            return None, None
        return str(row[0]), str(row[1])

    def close(self) -> None:
        self._conn.close()
