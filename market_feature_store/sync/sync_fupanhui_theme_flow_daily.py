"""同步题材资金面板到 DuckDB。

数据源优先级：
  1. 复盘会公开 API `/data/theme/panels`——编辑部人工现分组，覆盖题材最细（含
     "美的定增""转债涨停"这类单事件短线分组），但该接口从 2026-09-03 起持续
     返回 401（`docs/data-sources/fupanhui-workspace-asset-inventory-2026-08-12.md`
     §10 记过这条链路另有 IP 级 429，惩罚窗口 ≥1 小时且反复探测可能重置窗口）。
  2. AKShare `stock_fund_flow_concept`——东方财富概念资金流，和复盘会、Wind 均
     无关联，覆盖约 390 个标准概念板块。答不了复盘会那些编辑现造的短线题材
     （实测 387 个 AKShare 概念名只有约 21% 能对上复盘会历史题材名），但作为
     独立于复盘会的兜底，能在复盘会整段拿不到时持续产出。
     `symbol="即时"` 只给「现在」的快照，没有历史日期参数——只能兜底当天，
     回补历史日这条路不通，trade_date 非上海今天时不会尝试。

两条源都写 `fact_theme_flow_daily`，用 `source` 字段区分口径，下游按题材名做
跨日对比时不得把两种口径的行混算成一条时间序列。AKShare 行的 theme_code 加
`ak:` 前缀，避免撞上复盘会自己的题材编码。

单位：两个源都没有在字段里标注单位；用个股数相近的题材互相比较数量级后判断
两边应该都是亿元（[推断]，未找到官方文档确认），如后续证据推翻这个假设，先
查这里再改口径。AKShare 的「流入资金+流出资金」是否等价于复盘会 total_amount
的口径未经证实，没有把握做的字段不编数字——AKShare 来源行的 total_amount 留空。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ..db import connect, init_db
from ..sources import fupanhui_source as fs

_SHANGHAI = ZoneInfo("Asia/Shanghai")

FUPANHUI_SOURCE = "fupanhui:public-api/data/theme/panels"
AKSHARE_SOURCE = "akshare:stock_fund_flow_concept"

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


def _is_shanghai_today(trade_date: str) -> bool:
    try:
        return trade_date == datetime.now(_SHANGHAI).date().isoformat()
    except ValueError:
        return False


def _fetch_fupanhui_panels(trade_date: str) -> list[dict]:
    return fs.get_theme_panels(trade_date) or []


def _fetch_akshare_concept_flow() -> list[dict]:
    """东方财富即时概念资金流。无历史日期参数，只反映调用时刻的快照。"""
    import akshare as ak

    df = ak.stock_fund_flow_concept(symbol="即时")
    if df is None or df.empty:
        return []
    records = []
    for raw in df.to_dict("records"):
        name = str(raw.get("行业") or "").strip()
        if not name:
            continue
        records.append(
            {
                "theme_code": f"ak:{name}",
                "theme_name": name,
                "total_fund": raw.get("净额"),
                "total_amount": None,
                "stock_count": raw.get("公司家数"),
            }
        )
    return records


def _write_rows(con, rows: list[tuple]) -> int:
    if rows:
        con.executemany(UPSERT_SQL, rows)
    return len(rows)


def sync(trade_date: str) -> dict:
    """同步某日题材资金面板。优先复盘会编辑部面板，拿不到时用 AKShare 概念资金流兜底。

    Returns: {"panels": int, "source": str|None, "fupanhui_error": str|None}
    """
    now = datetime.utcnow().isoformat()

    fupanhui_error = None
    try:
        panels = _fetch_fupanhui_panels(trade_date)
    except Exception as exc:  # noqa: BLE001 — 401/429/CDP 卡死都走兜底，先记根因
        panels = []
        fupanhui_error = f"{type(exc).__name__}: {exc}"

    if panels:
        rows = []
        for p in panels:
            tc = p.get("theme_code") or p.get("code", "")
            tn = p.get("theme_name") or p.get("name", "")
            if not tc:
                continue
            rows.append(
                (
                    trade_date,
                    tc,
                    tn,
                    p.get("total_fund") or p.get("fund"),
                    p.get("total_amount") or p.get("amount"),
                    p.get("stock_count") or p.get("count"),
                    FUPANHUI_SOURCE,
                    now,
                )
            )
        if rows:
            init_db()
            con = connect()
            try:
                n = _write_rows(con, rows)
            finally:
                con.close()
            return {"panels": n, "source": FUPANHUI_SOURCE, "fupanhui_error": None}

    if not _is_shanghai_today(trade_date):
        return {"panels": 0, "source": None, "fupanhui_error": fupanhui_error}

    try:
        ak_records = _fetch_akshare_concept_flow()
    except Exception as exc:  # noqa: BLE001 — AKShare 也拿不到就如实返回零
        return {
            "panels": 0,
            "source": None,
            "fupanhui_error": fupanhui_error,
            "akshare_error": f"{type(exc).__name__}: {exc}",
        }

    if not ak_records:
        return {"panels": 0, "source": None, "fupanhui_error": fupanhui_error}

    rows = [
        (
            trade_date,
            r["theme_code"],
            r["theme_name"],
            r["total_fund"],
            r["total_amount"],
            r["stock_count"],
            AKSHARE_SOURCE,
            now,
        )
        for r in ak_records
    ]
    init_db()
    con = connect()
    try:
        n = _write_rows(con, rows)
    finally:
        con.close()
    return {"panels": n, "source": AKSHARE_SOURCE, "fupanhui_error": fupanhui_error}
