"""同步复盘会题材资金面板到 DuckDB。

数据源: fupanhui.com 公开 API（无需登录）
  - /data/theme/panels → fact_theme_flow_daily
"""
from __future__ import annotations

from datetime import datetime

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


UPSERT_SQL = """
    INSERT INTO fact_theme_flow_daily
        (trade_date, theme_code, theme_name, total_fund, total_amount,
         stock_count, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, theme_code) DO UPDATE SET
        theme_name = excluded.theme_name,
        total_fund = excluded.total_fund,
        total_amount = excluded.total_amount,
        stock_count = excluded.stock_count,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def sync(trade_date: str) -> dict:
    """同步某日的题材资金面板。

    Returns: {"panels": int}
    """
    now = datetime.utcnow().isoformat()
    source = "fupanhui:public-api/data/theme/panels"

    panels = fs.get_theme_panels(trade_date)
    if not panels:
        return {"panels": 0}

    init_db()
    con = connect()

    rows = []
    for p in panels:
        tc = p.get("theme_code") or p.get("code", "")
        tn = p.get("theme_name") or p.get("name", "")
        if not tc:
            continue
        rows.append((
            trade_date,
            tc,
            tn,
            p.get("total_fund") or p.get("fund"),
            p.get("total_amount") or p.get("amount"),
            p.get("stock_count") or p.get("count"),
            source,
            now,
        ))

    if rows:
        con.executemany(UPSERT_SQL, rows)

    con.close()
    return {"panels": len(rows)}
