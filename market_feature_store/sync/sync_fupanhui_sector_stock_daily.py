"""同步 fact_sector_stock_daily: 板块成分股每日全量快照。

数据源: fupanhui sector-cycle stocks (单板块单日)。
逐板块抓取 (一次一个板块, 对服务器更温和), 单板块写完即提交, 可中断可续跑。
用 --limit 分批增量, 默认跳过当日已抓板块 (resume)。
"""
from __future__ import annotations

import time
from datetime import datetime, date

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _load_sector_dim(con):
    rows = con.execute(
        "SELECT sector_ts_code, sector_name, sw_l1 FROM dim_sector"
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _latest_trade_date(con):
    row = con.execute("SELECT MAX(trade_date) FROM fact_sector_daily").fetchone()
    return row[0] if row else None


def _resolve_sector(dim, sector: str):
    """把 --sector 参数 (代码或名称) 解析为 ts_code。"""
    if sector in dim:
        return sector
    for ts_code, (name, _sw) in dim.items():
        if name == sector:
            return ts_code
    return None


UPSERT_SQL = """
    INSERT INTO fact_sector_stock_daily
        (trade_date, sector_ts_code, sector_name, sw_l1,
         stock_ts_code, stock_name, price, pct_chg, amount,
         pct_chg_5d, pct_chg_10d, pct_chg_20d,
         fund_flow_1d, fund_flow_5d, sw_industry,
         leader_plate, leader_sub_plate, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, sector_ts_code, stock_ts_code) DO UPDATE SET
        sector_name = excluded.sector_name,
        sw_l1 = excluded.sw_l1,
        stock_name = excluded.stock_name,
        price = excluded.price,
        pct_chg = excluded.pct_chg,
        amount = excluded.amount,
        pct_chg_5d = excluded.pct_chg_5d,
        pct_chg_10d = excluded.pct_chg_10d,
        pct_chg_20d = excluded.pct_chg_20d,
        fund_flow_1d = excluded.fund_flow_1d,
        fund_flow_5d = excluded.fund_flow_5d,
        sw_industry = excluded.sw_industry,
        leader_plate = excluded.leader_plate,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def sync_fact_sector_stock_daily(
    trade_date: str | None = None,
    sector: str | None = None,
    limit: int | None = None,
    only_missing: bool = True,
    sleep: float = 0.3,
) -> dict:
    """逐板块回补某交易日的成分股快照。

    一次一个板块调 API, 写完即提交; 默认跳过当日已抓板块, 可多次短命令续跑。
    参数:
      trade_date  指定交易日, 留空取 fact_sector_daily 最新日。
      sector      只抓单个板块 (代码或名称)。
      limit       本次最多抓多少个板块。
      only_missing 跳过当日已抓板块 (续跑)。
      sleep       板块间隔秒数。
    """
    init_db()
    con = connect()
    try:
        dim = _load_sector_dim(con)
        td = _parse_date(trade_date) if trade_date else _latest_trade_date(con)
        done = set()
        if td is not None:
            done = {
                r[0] for r in con.execute(
                    "SELECT DISTINCT sector_ts_code FROM fact_sector_stock_daily WHERE trade_date = ?",
                    [td],
                ).fetchall()
            }
    finally:
        con.close()

    if not dim:
        raise RuntimeError("dim_sector 为空, 请先运行 sync-sectors")
    if td is None:
        raise RuntimeError("无目标交易日, 请先运行 sync-sector-daily 或显式传 --trade-date")

    # 确定本次要抓的板块
    if sector:
        ts_code = _resolve_sector(dim, sector)
        if not ts_code:
            raise RuntimeError(f"未找到板块: {sector}")
        todo = [ts_code]
    else:
        todo = list(dim.keys())
        if only_missing:
            todo = [c for c in todo if c not in done]
        if limit:
            todo = todo[:limit]

    td_str = td.isoformat()
    now = datetime.now()
    processed = 0
    rows_written = 0
    failures = []

    con = connect()
    try:
        for ts_code in todo:
            name, sw_l1 = dim.get(ts_code, (ts_code, None))
            try:
                payload = fs.get_sector_stocks(ts_code, trade_date=td_str)
            except Exception as e:  # noqa: BLE001
                failures.append((ts_code, str(e)))
                continue
            snap_date = _parse_date(payload.get("trade_date")) or td
            rows = []
            for s in payload.get("stocks", []):
                code = s.get("ts_code")
                if not code:
                    continue
                rows.append((
                    snap_date, ts_code, name, sw_l1,
                    code, s.get("name"), s.get("price"), s.get("pct_chg"), s.get("amount"),
                    s.get("pct_chg_5d"), s.get("pct_chg_10d"), s.get("pct_chg_20d"),
                    s.get("fund_flow_1d"), s.get("fund_flow_5d"), s.get("sw_industry"),
                    s.get("leader_plate"), None, "fupanhui", now,
                ))
            con.execute("BEGIN TRANSACTION")
            con.execute(
                "DELETE FROM fact_sector_stock_daily WHERE trade_date = ? AND sector_ts_code = ?",
                [snap_date, ts_code],
            )
            if rows:
                con.executemany(UPSERT_SQL, rows)
            con.execute("COMMIT")
            processed += 1
            rows_written += len(rows)
            if sleep:
                time.sleep(sleep)

        grand_total = con.execute(
            "SELECT COUNT(*) FROM fact_sector_stock_daily"
        ).fetchone()[0]
        done_today = con.execute(
            "SELECT COUNT(DISTINCT sector_ts_code) FROM fact_sector_stock_daily WHERE trade_date = ?",
            [td],
        ).fetchone()[0]
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    return {
        "trade_date": td_str,
        "processed": processed,
        "rows_written": rows_written,
        "failures": failures,
        "sectors_done_today": done_today,
        "sectors_total": len(dim),
        "sectors_remaining": len(dim) - done_today,
        "table_total": grand_total,
    }
