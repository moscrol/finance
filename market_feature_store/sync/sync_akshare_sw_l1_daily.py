from __future__ import annotations

from datetime import date, datetime, timedelta
import time

from ..db import connect, init_db


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
        except ValueError:
            pass
    return None


def _num(value):
    if value is None:
        return None
    try:
        text = str(value).replace(",", "").strip()
        if text in ("", "-", "--", "nan", "None"):
            return None
        return float(text)
    except Exception:
        return None


def _pick(row: dict, *names):
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _target_dates(con, trade_date: str | None, days: int) -> list[date]:
    if trade_date:
        end = _parse_date(trade_date)
        if not end:
            raise RuntimeError(f"无效交易日: {trade_date}")
    else:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        end = _parse_date(row[0]) if row else None
        if not end:
            raise RuntimeError("fact_market_daily 无交易日")
    rows = con.execute(
        """
        SELECT trade_date
        FROM fact_market_daily
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        [end, int(days)],
    ).fetchall()
    return [r[0] for r in reversed(rows)]


def _industry_ratio(row: dict, sw_l1: str):
    for idx in (1, 2, 3):
        if row.get(f"industry_{idx}") == sw_l1:
            return _num(row.get(f"industry_{idx}_ratio"))
    return None


def _market_ratio_rows(con, dates: list[date]) -> dict[tuple[date, str], float]:
    if not dates:
        return {}
    placeholders = ",".join("?" for _ in dates)
    rows = con.execute(
        f"""
        SELECT trade_date, industry_1, industry_1_ratio, industry_2, industry_2_ratio, industry_3, industry_3_ratio
        FROM fact_market_daily
        WHERE trade_date IN ({placeholders})
        """,
        dates,
    ).fetchall()
    out = {}
    for trade_date, i1, r1, i2, r2, i3, r3 in rows:
        for name, ratio in ((i1, r1), (i2, r2), (i3, r3)):
            if name:
                out[(trade_date, name)] = _num(ratio)
    return out


def _fetch_sw_l1_codes() -> list[dict]:
    import akshare as ak

    df = ak.sw_index_first_info()
    rows = []
    for raw in df.to_dict("records"):
        code = str(_pick(raw, "行业代码", "指数代码", "代码") or "").replace(".SI", "")
        name = str(_pick(raw, "行业名称", "指数名称", "名称") or "").strip()
        if code and name:
            rows.append({"code": code, "name": name})
    return rows


def _fetch_hist_by_code(code: str, start: date, end: date) -> dict[date, dict]:
    import akshare as ak

    df = ak.index_hist_sw(symbol=code, period="day")
    out = {}
    for raw in df.to_dict("records"):
        trade_date = _parse_date(_pick(raw, "日期", "date"))
        if not trade_date or trade_date < start or trade_date > end:
            continue
        close = _num(_pick(raw, "收盘", "close"))
        pre_close = None
        out[trade_date] = {
            "close": close,
            "pre_close": pre_close,
            "pct_chg": None,
            "amount": _num(_pick(raw, "成交额", "amount")),
            "source": f"akshare:index_hist_sw:{code}",
        }
    ordered = sorted(out)
    prev_close = None
    for trade_date in ordered:
        close = out[trade_date]["close"]
        out[trade_date]["pre_close"] = prev_close
        out[trade_date]["pct_chg"] = ((close / prev_close - 1) * 100) if close is not None and prev_close else None
        if close is not None:
            prev_close = close
    return out


def _fetch_realtime() -> dict[str, dict]:
    import akshare as ak

    df = ak.index_realtime_sw(symbol="一级行业")
    out = {}
    for raw in df.to_dict("records"):
        code = str(_pick(raw, "指数代码", "代码") or "").strip()
        name = str(_pick(raw, "指数名称", "名称") or "").strip()
        close = _num(_pick(raw, "最新价", "收盘"))
        pre_close = _num(_pick(raw, "昨收盘", "昨收"))
        pct_chg = ((close / pre_close - 1) * 100) if close is not None and pre_close else None
        if code and name:
            out[name] = {
                "code": code,
                "close": close,
                "pre_close": pre_close,
                "pct_chg": pct_chg,
                "amount": _num(_pick(raw, "成交额")),
                "source": f"akshare:index_realtime_sw:{code}",
            }
    return out


def sync_akshare_sw_l1_daily(trade_date: str | None = None, days: int = 20) -> dict:
    init_db()
    con = connect()
    try:
        dates = _target_dates(con, trade_date, days)
        if not dates:
            raise RuntimeError("无目标交易日")
        start, end = dates[0], dates[-1]
        wanted_dates = set(dates)
        ratios = _market_ratio_rows(con, dates)
        focus_names = {name for _d, name in ratios}
        industries_all = _fetch_sw_l1_codes()
        industries = [item for item in industries_all if not focus_names or item["name"] in focus_names]
        by_name = {item["name"]: item for item in industries_all}
        records: dict[tuple[date, str], dict] = {}
        failures = []
        for item in industries:
            try:
                hist = _fetch_hist_by_code(item["code"], start - timedelta(days=10), end)
            except Exception as exc:
                failures.append({"sw_l1": item["name"], "code": item["code"], "error": str(exc)})
                continue
            for d in wanted_dates:
                if d in hist:
                    records[(d, item["name"])] = {
                        "trade_date": d,
                        "sw_l1_code": item["code"],
                        "sw_l1": item["name"],
                        **hist[d],
                    }
            time.sleep(0.2)
        realtime = _fetch_realtime()
        for name, item in realtime.items():
            if name in by_name:
                records[(end, name)] = {
                    "trade_date": end,
                    "sw_l1_code": item["code"],
                    "sw_l1": name,
                    "close": item["close"],
                    "pre_close": item["pre_close"],
                    "pct_chg": item["pct_chg"],
                    "amount": item["amount"],
                    "source": item["source"],
                }
        now = datetime.now()
        rows = []
        for key in sorted(records):
            rec = records[key]
            rows.append((
                rec["trade_date"], rec["sw_l1_code"], rec["sw_l1"], rec.get("close"), rec.get("pre_close"),
                rec.get("pct_chg"), rec.get("amount"), ratios.get((rec["trade_date"], rec["sw_l1"])),
                rec.get("source"), now,
            ))
        con.execute("BEGIN TRANSACTION")
        con.executemany(
            """
            INSERT INTO fact_sw_l1_daily
                (trade_date, sw_l1_code, sw_l1, close, pre_close, pct_chg, amount, fupanhui_ratio, source, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (trade_date, sw_l1) DO UPDATE SET
                sw_l1_code = excluded.sw_l1_code,
                close = excluded.close,
                pre_close = excluded.pre_close,
                pct_chg = excluded.pct_chg,
                amount = excluded.amount,
                fupanhui_ratio = excluded.fupanhui_ratio,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        con.execute("COMMIT")
        stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date), COUNT(fupanhui_ratio)
            FROM fact_sw_l1_daily
            """
        ).fetchone()
        current = con.execute(
            """
            SELECT sw_l1, pct_chg, fupanhui_ratio, source
            FROM fact_sw_l1_daily
            WHERE trade_date = ?
            ORDER BY sw_l1
            """,
            [end],
        ).fetchall()
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()
    return {
        "trade_date": end.isoformat(),
        "target_dates": len(dates),
        "industries": len(industries),
        "rows_written": len(rows),
        "table_total": stats[0],
        "table_dates": stats[1],
        "date_min": str(stats[2]) if stats[2] else None,
        "date_max": str(stats[3]) if stats[3] else None,
        "ratio_count": stats[4],
        "current": current,
        "failures": failures,
    }
