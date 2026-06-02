"""mootdx 全A股前复权日线 -> fact_stock_daily (回补)。

数据源: mootdx (通达信 TCP 7709), 前复权日线。不封 IP, 免费, 批量快。
逐只抓取并写入, 默认跳过区间内已抓的股票, 可中断/续跑 (类似 sector-stocks)。

amount 统一存为「亿」(mootdx 原始单位为元, /1e8), 与 fact_sector_daily 口径一致。
close 为前复权收盘价; pct_chg / pre_close 由相邻前复权收盘价计算 (即前复权日涨跌幅),
因此区间涨跌幅可用 期末close / 区间首日pre_close - 1 正确得出 (含除权调整)。
"""
from __future__ import annotations

import math
import re
import time
from datetime import datetime

from ..db import connect, init_db

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _isnan(x) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return False

# 沪(6) / 深(0,3) / 北(8x,920) A股代码前缀
A_SHARE_PREFIXES = (
    "600", "601", "603", "605", "688", "689",
    "000", "001", "002", "003", "300", "301",
    "830", "831", "832", "833", "834", "835", "836", "837", "838", "839",
    "870", "871", "872", "873", "920",
)

FLUSH_EVERY = 100  # 每抓多少只 flush 一次

UPSERT_SQL = """
    INSERT INTO fact_stock_daily
        (trade_date, stock_ts_code, stock_name, close, pre_close,
         pct_chg, amount, turnover, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
        stock_name = excluded.stock_name,
        close = excluded.close,
        pre_close = excluded.pre_close,
        pct_chg = excluded.pct_chg,
        amount = excluded.amount,
        turnover = excluded.turnover,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def _ts_code(code: str) -> str:
    if code.startswith("6"):
        return code + ".SH"
    if code.startswith(("0", "3")):
        return code + ".SZ"
    return code + ".BJ"  # 8xx / 920 北交所


def get_universe(client) -> list[tuple[str, str]]:
    """从 mootdx 全证券里按前缀过滤出 A 股, 返回 [(code, name), ...]。"""
    import pandas as pd

    frames = []
    for mkt in (0, 1):
        df = client.stocks(market=mkt)
        if df is not None and not df.empty and "code" in df.columns:
            frames.append(df[["code", "name"]])
    if not frames:
        return []
    allc = pd.concat(frames, ignore_index=True)
    allc["code"] = allc["code"].astype(str)
    mask = allc["code"].str.startswith(A_SHARE_PREFIXES)
    uni = allc[mask].drop_duplicates("code")
    return [(str(c), str(n).strip()) for c, n in zip(uni["code"], uni["name"])]


def _build_rows(df, code: str, name: str, start_date: str, now: datetime) -> list[tuple]:
    """把 mootdx 日线 df 转成 fact_stock_daily 行 (只保留 >= start_date)。"""
    if "datetime" not in df.columns or "close" not in df.columns:
        return []
    df = df.sort_values("datetime")
    closes = df["close"].tolist()
    amounts = df["amount"].tolist() if "amount" in df.columns else [None] * len(closes)
    dts = df["datetime"].tolist()
    ts = _ts_code(code)
    rows = []
    prev_close = None
    for i in range(len(closes)):
        d = str(dts[i])[:10]
        if not _DATE_RE.match(d):  # 跳过 nan / 停牌占位行
            continue
        c = closes[i]
        if c is None or _isnan(c):
            continue
        try:
            close = float(c)
        except (TypeError, ValueError):
            continue
        pre_close = prev_close
        pct = ((close / pre_close - 1) * 100) if (close and pre_close) else None
        amt_yi = None
        if i < len(amounts) and amounts[i] is not None and not _isnan(amounts[i]):
            try:
                amt_yi = float(amounts[i]) / 1e8
            except (TypeError, ValueError):
                amt_yi = None
        if d >= start_date:
            rows.append((
                d, ts, name, close,
                round(pre_close, 3) if pre_close is not None else None,
                round(pct, 2) if pct is not None else None,
                round(amt_yi, 4) if amt_yi is not None else None,
                None, "mootdx:qfq", now,
            ))
        prev_close = close
    return rows


def sync_fact_stock_daily(start_date: str | None = None, offset: int = 180,
                          limit: int | None = None, only_missing: bool = True,
                          sleep: float = 0.0) -> dict:
    """回补全A股前复权日线到 fact_stock_daily。

    start_date: 起始交易日 (YYYY-MM-DD), 默认对齐 fact_market_daily 最早日。
    offset: 每只股票拉取的日线根数 (>= 区间交易日数, 默认180 ≈ 8个月)。
    limit: 本次最多抓多少只 (续跑用)。
    only_missing: True 时跳过区间内已抓的股票 (可续跑)。
    """
    from mootdx.quotes import Quotes

    init_db()
    con = connect()
    try:
        if start_date is None:
            row = con.execute("SELECT MIN(trade_date) FROM fact_market_daily").fetchone()
            start_date = str(row[0]) if row and row[0] else "2025-10-09"

        done = set()
        if only_missing:
            done = {
                r[0] for r in con.execute(
                    "SELECT DISTINCT stock_ts_code FROM fact_stock_daily WHERE trade_date >= ?",
                    [start_date],
                ).fetchall()
            }

        client = Quotes.factory(market="std")
        universe = get_universe(client)
        universe_n = len(universe)
        pending = [(c, n) for c, n in universe if _ts_code(c) not in done]
        if limit:
            pending = pending[:limit]

        now = datetime.now()
        processed = 0
        rows_written = 0
        failures: list[tuple[str, str]] = []
        buf: list[tuple] = []

        def flush():
            nonlocal rows_written
            if not buf:
                return
            con.execute("BEGIN TRANSACTION")
            con.executemany(UPSERT_SQL, buf)
            con.execute("COMMIT")
            rows_written += len(buf)
            buf.clear()

        for code, name in pending:
            try:
                df = client.bars(symbol=code, frequency=9, offset=offset, adjust="qfq")
            except Exception as e:  # noqa: BLE001
                failures.append((code, f"bars:{type(e).__name__}"))
                continue
            if df is None or len(df) == 0:
                failures.append((code, "empty"))
                continue
            recs = _build_rows(df, code, name, start_date, now)
            buf.extend(recs)
            processed += 1
            if processed % FLUSH_EVERY == 0:
                flush()
            if sleep:
                time.sleep(sleep)
        flush()

        total = con.execute("SELECT COUNT(*) FROM fact_stock_daily").fetchone()[0]
        agg = con.execute(
            "SELECT COUNT(DISTINCT stock_ts_code), COUNT(DISTINCT trade_date),"
            " MIN(trade_date), MAX(trade_date) FROM fact_stock_daily"
        ).fetchone()
        done_after = con.execute(
            "SELECT COUNT(DISTINCT stock_ts_code) FROM fact_stock_daily WHERE trade_date >= ?",
            [start_date],
        ).fetchone()[0]
    finally:
        con.close()

    return {
        "start_date": start_date,
        "universe": universe_n,
        "processed": processed,
        "rows_written": rows_written,
        "stocks_done": done_after,
        "stocks_remaining": max(0, universe_n - done_after),
        "table_total": total,
        "distinct_stocks": agg[0],
        "distinct_dates": agg[1],
        "date_min": str(agg[2]) if agg[2] else None,
        "date_max": str(agg[3]) if agg[3] else None,
        "failures": failures,
    }
