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


def _status(expected: int, completed: int, failures: list[dict]) -> str:
    if not failures and expected > 0 and completed == expected:
        return "complete"
    # 有成功题材时降级写入（上游偶发单题材空 groups，不阻断全日主线落库）
    if completed > 0:
        return "degraded"
    return "failed"


def sync(
    trade_date: str,
    *,
    attempts: int = 3,
    retry_delay: float = 0.5,
) -> dict:
    """同步某日的主线题材和个股。

    优先完整抓取；若部分题材 stocks 为空/失败，仍原子写入已成功的题材+个股
    （status=degraded），避免单题材空响应拖死全日质量门。全部失败则不写入。
    """
    now = datetime.utcnow().isoformat()
    source = "fupanhui:public-api/topics"

    themes = None
    last_theme_error = None
    for attempt in range(max(1, attempts)):
        if attempt:
            time.sleep(retry_delay * attempt)
        try:
            candidate = fs.get_mainline_themes(trade_date)
            if candidate:
                themes = candidate
                break
            last_theme_error = RuntimeError("empty theme list")
        except Exception as exc:  # noqa: BLE001
            last_theme_error = exc
    if themes is None:
        return {
            "themes": 0,
            "stocks": 0,
            "expected_themes": 0,
            "completed_themes": 0,
            "failures": [{"scope": "themes", "error": str(last_theme_error)}],
            "status": "failed",
        }

    theme_rows = []
    stock_rows = []
    failures = []
    completed = 0
    for t in themes:
        tc = str(t.get("theme_code") or "").strip()
        tn = str(t.get("theme_name") or "").strip()
        if not tc:
            failures.append(
                {"scope": "theme", "theme_code": "", "theme_name": tn, "error": "missing theme_code"}
            )
            continue
        data = None
        last_error = None
        for attempt in range(max(1, attempts)):
            if attempt:
                time.sleep(retry_delay * attempt)
            try:
                candidate = fs.get_mainline_stocks(trade_date, tc)
                groups = candidate.get("groups") or []
                has_stock = any(
                    str(stock.get("ts_code") or "").strip()
                    for group in groups
                    for stock in (group.get("stocks") or [])
                )
                if not has_stock:
                    last_error = RuntimeError("empty groups or stock list")
                    continue
                data = candidate
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if data is None:
            failures.append(
                {
                    "scope": "stocks",
                    "theme_code": tc,
                    "theme_name": tn,
                    "error": str(last_error),
                }
            )
            continue
        groups = data.get("groups") or []
        rows = []
        for g in groups:
            gt = g.get("groupType", "")
            for s in g.get("stocks") or []:
                stock_ts_code = str(s.get("ts_code") or "").strip()
                if not stock_ts_code:
                    continue
                rows.append((
                    trade_date,
                    tc,
                    tn,
                    gt,
                    stock_ts_code,
                    s.get("name", ""),
                    s.get("price"),
                    s.get("changePct"),
                    s.get("amount"),
                    source,
                    now,
                ))
        if not rows:
            failures.append(
                {
                    "scope": "stocks",
                    "theme_code": tc,
                    "theme_name": tn,
                    "error": "empty groups or stock list",
                }
            )
            continue
        # 仅登记有个股的题材，避免质量门报“有题材无个股”
        theme_rows.append((
            trade_date,
            tc,
            tn,
            t.get("sector_count"),
            t.get("min_sort"),
            source,
            now,
        ))
        stock_rows.extend(rows)
        completed += 1
        time.sleep(0.3)

    status = _status(len(themes), completed, failures)
    if status == "failed":
        return {
            "themes": 0,
            "stocks": 0,
            "expected_themes": len(themes),
            "completed_themes": completed,
            "failures": failures,
            "status": status,
        }

    init_db()
    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM fact_mainline_stock_daily WHERE trade_date = ?", [trade_date])
        con.execute("DELETE FROM fact_mainline_theme_daily WHERE trade_date = ?", [trade_date])
        con.executemany(THEME_UPSERT, theme_rows)
        con.executemany(STOCK_UPSERT, stock_rows)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return {
        "themes": len(theme_rows),
        "stocks": len(stock_rows),
        "expected_themes": len(themes),
        "completed_themes": completed,
        "failures": failures,
        "status": status,
    }
