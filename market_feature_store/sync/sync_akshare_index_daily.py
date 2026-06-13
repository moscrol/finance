"""同步指数日线到 fact_market_daily。"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..db import connect, init_db


def _parse_date(value):
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_columns(con) -> None:
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_close DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_pct_chg DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_open DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_high DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_low DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_volume DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_amount DOUBLE")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_source TEXT")
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS sh_index_updated_at TIMESTAMP")


def _pick(row, *names):
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _fetch_akshare_index(symbol: str, start_date: str, end_date: str) -> list[dict]:
    import akshare as ak

    df = ak.stock_zh_index_daily(symbol=symbol)
    if df is None or df.empty:
        return []
    records = []
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    for raw in df.to_dict("records"):
        d = _parse_date(_pick(raw, "date", "日期"))
        if not d:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        records.append({
            "trade_date": d,
            "open": _num(_pick(raw, "open", "开盘")),
            "high": _num(_pick(raw, "high", "最高")),
            "low": _num(_pick(raw, "low", "最低")),
            "close": _num(_pick(raw, "close", "收盘")),
            "volume": _num(_pick(raw, "volume", "成交量")),
            "amount": _num(_pick(raw, "amount", "成交额")),
        })
    records.sort(key=lambda x: x["trade_date"])
    return records


def sync_akshare_index_daily(
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    symbol: str = "sh000001",
) -> dict:
    init_db()
    con = connect()
    try:
        _ensure_columns(con)
        if trade_date:
            target_date = _parse_date(trade_date)
            start = target_date - timedelta(days=10)
            end = target_date
        else:
            target_date = None
            start = _parse_date(start_date) if start_date else None
            end = _parse_date(end_date) if end_date else None
        if not end:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
            end = row[0] if row else datetime.today().date()
        if not start:
            start = end - timedelta(days=45)
        records = _fetch_akshare_index(
            symbol=symbol,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        if not records:
            raise RuntimeError(f"AkShare 未返回指数数据: {symbol} {start}~{end}")
        rows = []
        prev_close = None
        for item in records:
            close = item["close"]
            pct_chg = ((close / prev_close - 1) * 100) if close is not None and prev_close else None
            if target_date is None or item["trade_date"] == target_date:
                rows.append((
                    item["trade_date"],
                    close,
                    pct_chg,
                    item["open"],
                    item["high"],
                    item["low"],
                    item["volume"],
                    item["amount"],
                    f"akshare:stock_zh_index_daily:{symbol}",
                    datetime.now(),
                ))
            if close is not None:
                prev_close = close
        if not rows:
            raise RuntimeError(f"AkShare 返回数据中没有目标交易日: {trade_date or f'{start}~{end}'}")
        con.execute("BEGIN TRANSACTION")
        con.executemany(
            """
            INSERT INTO fact_market_daily
                (trade_date, sh_index_close, sh_index_pct_chg, sh_index_open,
                 sh_index_high, sh_index_low, sh_index_volume, sh_index_amount,
                 sh_index_source, sh_index_updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (trade_date) DO UPDATE SET
                sh_index_close = excluded.sh_index_close,
                sh_index_pct_chg = excluded.sh_index_pct_chg,
                sh_index_open = excluded.sh_index_open,
                sh_index_high = excluded.sh_index_high,
                sh_index_low = excluded.sh_index_low,
                sh_index_volume = excluded.sh_index_volume,
                sh_index_amount = excluded.sh_index_amount,
                sh_index_source = excluded.sh_index_source,
                sh_index_updated_at = excluded.sh_index_updated_at
            """,
            rows,
        )
        con.execute("COMMIT")
        stats = con.execute(
            """
            SELECT COUNT(sh_index_close), MIN(trade_date), MAX(trade_date)
            FROM fact_market_daily
            WHERE sh_index_close IS NOT NULL
            """
        ).fetchone()
        current = con.execute(
            """
            SELECT trade_date, sh_index_close, sh_index_pct_chg
            FROM fact_market_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            [start, end],
        ).fetchone()
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()
    return {
        "symbol": symbol,
        "rows_written": len(rows),
        "date_min": str(stats[1]) if stats[1] else None,
        "date_max": str(stats[2]) if stats[2] else None,
        "close_count": stats[0],
        "current": current,
    }
