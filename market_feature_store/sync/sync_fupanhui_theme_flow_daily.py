"""同步题材资金面板到 DuckDB。

优先复盘会公开 API `/data/theme/panels`（编辑部格子）。
抓不到时用当日板块成分的 `fund_flow_1d` 加总替代——篮子不同，问的仍是
「这组股票今天钱进了还是出了」。替代行的 source 为
`local:sector-basket:fund_flow_1d`，不冒充复盘会面板。
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..db import connect, init_db
from ..sources import fupanhui_source as fs
from .sync_theme_capital_from_baskets import SOURCE_PREFIX as BASKET_SOURCE
from .sync_theme_capital_from_baskets import sync_from_sector_baskets

FUPANHUI_SOURCE = "fupanhui:public-api/data/theme/panels"

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


def _write_fupanhui_panels(con, trade_date: str, panels: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for panel in panels:
        theme_code = panel.get("theme_code") or panel.get("code", "")
        theme_name = panel.get("theme_name") or panel.get("name", "")
        if not theme_code:
            continue
        rows.append(
            (
                trade_date,
                theme_code,
                theme_name,
                panel.get("total_fund") or panel.get("fund"),
                panel.get("total_amount") or panel.get("amount"),
                panel.get("stock_count") or panel.get("count"),
                FUPANHUI_SOURCE,
                now,
            )
        )
    if rows:
        con.executemany(UPSERT_SQL, rows)
    return len(rows)


def sync(trade_date: str) -> dict:
    """同步某日题材资金。有复盘会面板用面板，否则用板块篮子加总。

    Returns: {"panels": int, "source": str, "fupanhui_error": str|None}
    """
    fupanhui_error = None
    panels: list[dict] = []
    try:
        panels = fs.get_theme_panels(trade_date) or []
    except Exception as exc:  # noqa: BLE001 — 上游空/挂都走本地篮子
        fupanhui_error = f"{type(exc).__name__}: {exc}"
        print(f"theme-flow fupanhui 失败，改用板块篮子: {fupanhui_error}", flush=True)

    if panels:
        init_db()
        con = connect()
        try:
            n = _write_fupanhui_panels(con, trade_date, panels)
        finally:
            con.close()
        return {
            "panels": n,
            "source": FUPANHUI_SOURCE,
            "fupanhui_error": None,
        }

    result = sync_from_sector_baskets(trade_date)
    result["fupanhui_error"] = fupanhui_error
    if result["panels"] == 0:
        print(
            f"theme-flow {trade_date} 复盘会空且板块成分无可用资金（未写入），"
            f"source_prefix={BASKET_SOURCE}",
            flush=True,
        )
    else:
        print(
            f"theme-flow {trade_date} 用板块篮子加总 {result['panels']} 行 "
            f"source={result['source']}",
            flush=True,
        )
    return result
