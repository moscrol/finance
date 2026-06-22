"""同步复盘会每日主线题材 + 主线个股到 DuckDB。

数据源: fupanhui.com 公开 API（无需登录）
  - /topics/mainline-themes  → fact_mainline_theme_daily
  - /topics/mainline-stocks  → fact_mainline_stock_daily
"""
from __future__ import annotations

import time
from datetime import datetime

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


THEME_UPSERT = """
    INSERT INTO fact_mainline_theme_daily
        (trade_date, theme_code, theme_name, sector_count, min_sort,
         source, updated_at)
    VALUES (?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, theme_code) DO UPDATE SET
        theme_name = excluded.theme_name,
        sector_count = excluded.sector_count,
        min_sort = excluded.min_sort,
        source = excluded.source,
        updated_at = excluded.updated_at
"""

STOCK_UPSERT = """
    INSERT INTO fact_mainline_stock_daily
        (trade_date, theme_code, theme_name, group_type, stock_ts_code,
         stock_name, price, pct_chg, amount, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, theme_code, stock_ts_code) DO UPDATE SET
        theme_name = excluded.theme_name,
        group_type = excluded.group_type,
        stock_name = excluded.stock_name,
        price = excluded.price,
        pct_chg = excluded.pct_chg,
        amount = excluded.amount,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def sync(trade_date: str) -> dict:
    """同步某日的主线题材和个股。

    Returns: {"themes": int, "stocks": int}
    """
    now = datetime.utcnow().isoformat()
    source = "fupanhui:public-api/topics"

    # 获取主线题材
    themes = fs.get_mainline_themes(trade_date)
    if not themes:
        return {"themes": 0, "stocks": 0}

    init_db()
    con = connect()

    theme_rows = []
    for t in themes:
        theme_rows.append((
            trade_date,
            t.get("theme_code", ""),
            t.get("theme_name", ""),
            t.get("sector_count"),
            t.get("min_sort"),
            source,
            now,
        ))

    con.executemany(THEME_UPSERT, theme_rows)

    # 获取每个主线的个股
    stock_count = 0
    for t in themes:
        tc = t.get("theme_code", "")
        tn = t.get("theme_name", "")
        if not tc:
            continue
        time.sleep(0.3)  # 简单限流
        try:
            data = fs.get_mainline_stocks(trade_date, tc)
        except fs.FupanhuiError:
            continue
        groups = data.get("groups") or []
        stock_rows = []
        for g in groups:
            gt = g.get("groupType", "")
            for s in g.get("stocks") or []:
                stock_rows.append((
                    trade_date,
                    tc,
                    tn,
                    gt,
                    s.get("ts_code", ""),
                    s.get("name", ""),
                    s.get("price"),
                    s.get("changePct"),
                    s.get("amount"),
                    source,
                    now,
                ))
        if stock_rows:
            con.executemany(STOCK_UPSERT, stock_rows)
            stock_count += len(stock_rows)

    con.close()
    return {"themes": len(theme_rows), "stocks": stock_count}
