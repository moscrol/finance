from __future__ import annotations

import json
import time
import urllib.parse
from datetime import date, datetime

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


HEAT_COLUMNS = {
    "sector_name": "TEXT",
    "dimension": "TEXT",
    "scope": "TEXT",
    "data_stage": "TEXT",
    "is_realtime": "BOOLEAN",
    "source_update_time": "TIMESTAMP",
    "market_limit_up_count": "INTEGER",
    "limit_up_count": "INTEGER",
    "total_count": "INTEGER",
    "limit_up_ratio": "DOUBLE",
    "market_share": "DOUBLE",
    "fd_amount": "DOUBLE",
    "rank": "INTEGER",
    "top_stocks_json": "TEXT",
}
STOCK_COLUMNS = {
    "sector_name": "TEXT",
    "stock_name": "TEXT",
    "price": "DOUBLE",
    "pct_chg": "DOUBLE",
    "pct_chg_3d": "DOUBLE",
    "pct_chg_5d": "DOUBLE",
    "pct_chg_10d": "DOUBLE",
    "pct_chg_20d": "DOUBLE",
    "amount": "DOUBLE",
    "vol": "DOUBLE",
    "circ_mv": "DOUBLE",
    "total_mv": "DOUBLE",
    "sw_l1": "TEXT",
    "sw_l2": "TEXT",
    "sw_l3": "TEXT",
    "ths_concept_top": "TEXT",
    "fund_flow_1d": "DOUBLE",
    "fund_flow_5d": "DOUBLE",
    "limit_times": "INTEGER",
    "limit_status": "TEXT",
    "first_limit_time": "TEXT",
    "last_limit_time": "TEXT",
    "open_times": "INTEGER",
    "leader_plate": "TEXT",
    "leader_sub_plate": "TEXT",
    "theme_names_json": "TEXT",
    "up_stat": "TEXT",
    "up_stat_days": "INTEGER",
    "up_stat_boards": "INTEGER",
    "high_status": "TEXT",
    "high_status_label": "TEXT",
    "fd_amount": "DOUBLE",
    "limit_update_time": "TIMESTAMP",
}
FETCH_TIMEOUT_MS = 20000
CDP_SINGLE_TIMEOUT = 90
CDP_BATCH_TIMEOUT = 60

HEAT_UPSERT_SQL = """
    INSERT INTO fact_theme_limit_heat_daily
        (trade_date, sector_ts_code, sector_name, dimension, scope, data_stage,
         is_realtime, source_update_time, market_limit_up_count, limit_up_count,
         total_count, limit_up_ratio, market_share, fd_amount, rank,
         top_stocks_json, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, sector_ts_code, dimension, scope) DO UPDATE SET
        sector_name = excluded.sector_name,
        data_stage = excluded.data_stage,
        is_realtime = excluded.is_realtime,
        source_update_time = excluded.source_update_time,
        market_limit_up_count = excluded.market_limit_up_count,
        limit_up_count = excluded.limit_up_count,
        total_count = excluded.total_count,
        limit_up_ratio = excluded.limit_up_ratio,
        market_share = excluded.market_share,
        fd_amount = excluded.fd_amount,
        rank = excluded.rank,
        top_stocks_json = excluded.top_stocks_json,
        source = excluded.source,
        updated_at = excluded.updated_at
"""
STOCK_UPSERT_SQL = """
    INSERT INTO fact_theme_limit_stock_daily
        (trade_date, sector_ts_code, sector_name, stock_ts_code, stock_name,
         price, pct_chg, pct_chg_3d, pct_chg_5d, pct_chg_10d, pct_chg_20d,
         amount, vol, circ_mv, total_mv, sw_l1, sw_l2, sw_l3, ths_concept_top,
         fund_flow_1d, fund_flow_5d, limit_times, limit_status, first_limit_time,
         last_limit_time, open_times, leader_plate, leader_sub_plate,
         theme_names_json, up_stat, up_stat_days, up_stat_boards, high_status,
         high_status_label, fd_amount, limit_update_time, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, sector_ts_code, stock_ts_code) DO UPDATE SET
        sector_name = excluded.sector_name,
        stock_name = excluded.stock_name,
        price = excluded.price,
        pct_chg = excluded.pct_chg,
        pct_chg_3d = excluded.pct_chg_3d,
        pct_chg_5d = excluded.pct_chg_5d,
        pct_chg_10d = excluded.pct_chg_10d,
        pct_chg_20d = excluded.pct_chg_20d,
        amount = excluded.amount,
        vol = excluded.vol,
        circ_mv = excluded.circ_mv,
        total_mv = excluded.total_mv,
        sw_l1 = excluded.sw_l1,
        sw_l2 = excluded.sw_l2,
        sw_l3 = excluded.sw_l3,
        ths_concept_top = excluded.ths_concept_top,
        fund_flow_1d = excluded.fund_flow_1d,
        fund_flow_5d = excluded.fund_flow_5d,
        limit_times = excluded.limit_times,
        limit_status = excluded.limit_status,
        first_limit_time = excluded.first_limit_time,
        last_limit_time = excluded.last_limit_time,
        open_times = excluded.open_times,
        leader_plate = excluded.leader_plate,
        leader_sub_plate = excluded.leader_sub_plate,
        theme_names_json = excluded.theme_names_json,
        up_stat = excluded.up_stat,
        up_stat_days = excluded.up_stat_days,
        up_stat_boards = excluded.up_stat_boards,
        high_status = excluded.high_status,
        high_status_label = excluded.high_status_label,
        fd_amount = excluded.fd_amount,
        limit_update_time = excluded.limit_update_time,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


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


def _parse_datetime(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        return d.replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except ValueError:
            pass
    return None


def _ensure_schema(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_theme_limit_heat_daily (
            trade_date             DATE,
            sector_ts_code         TEXT,
            sector_name            TEXT,
            dimension              TEXT,
            scope                  TEXT,
            data_stage             TEXT,
            is_realtime            BOOLEAN,
            source_update_time     TIMESTAMP,
            market_limit_up_count  INTEGER,
            limit_up_count         INTEGER,
            total_count            INTEGER,
            limit_up_ratio         DOUBLE,
            market_share           DOUBLE,
            fd_amount              DOUBLE,
            rank                   INTEGER,
            top_stocks_json        TEXT,
            source                 TEXT,
            updated_at             TIMESTAMP,
            PRIMARY KEY (trade_date, sector_ts_code, dimension, scope)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_theme_limit_stock_daily (
            trade_date             DATE,
            sector_ts_code         TEXT,
            sector_name            TEXT,
            stock_ts_code          TEXT,
            stock_name             TEXT,
            price                  DOUBLE,
            pct_chg                DOUBLE,
            pct_chg_3d             DOUBLE,
            pct_chg_5d             DOUBLE,
            pct_chg_10d            DOUBLE,
            pct_chg_20d            DOUBLE,
            amount                 DOUBLE,
            vol                    DOUBLE,
            circ_mv                DOUBLE,
            total_mv               DOUBLE,
            sw_l1                  TEXT,
            sw_l2                  TEXT,
            sw_l3                  TEXT,
            ths_concept_top        TEXT,
            fund_flow_1d           DOUBLE,
            fund_flow_5d           DOUBLE,
            limit_times            INTEGER,
            limit_status           TEXT,
            first_limit_time       TEXT,
            last_limit_time        TEXT,
            open_times             INTEGER,
            leader_plate           TEXT,
            leader_sub_plate       TEXT,
            theme_names_json       TEXT,
            up_stat                TEXT,
            up_stat_days           INTEGER,
            up_stat_boards         INTEGER,
            high_status            TEXT,
            high_status_label      TEXT,
            fd_amount              DOUBLE,
            limit_update_time      TIMESTAMP,
            source                 TEXT,
            updated_at             TIMESTAMP,
            PRIMARY KEY (trade_date, sector_ts_code, stock_ts_code)
        )
        """
    )
    for name, typ in HEAT_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_theme_limit_heat_daily ADD COLUMN IF NOT EXISTS {name} {typ}")
    for name, typ in STOCK_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_theme_limit_stock_daily ADD COLUMN IF NOT EXISTS {name} {typ}")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_heat_date ON fact_theme_limit_heat_daily(trade_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_heat_sector ON fact_theme_limit_heat_daily(sector_ts_code)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_heat_rank ON fact_theme_limit_heat_daily(trade_date, rank)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_stock_date ON fact_theme_limit_stock_daily(trade_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_stock_sector ON fact_theme_limit_stock_daily(sector_ts_code)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_stock_stock ON fact_theme_limit_stock_daily(stock_ts_code)")


def _get_distribution(trade_date: str, dimension: str, scope: str):
    return fs.api_get(
        "/api/v1/client/watchlist/limit-distribution",
        {"trade_date": trade_date, "dimension": dimension, "mode": "auto", "scope": scope},
        timeout=120,
    )


def _get_sector_stocks(code: str, trade_date: str, dimension: str, scope: str):
    query = urllib.parse.urlencode({
        "code": code,
        "trade_date": trade_date,
        "dimension": dimension,
        "mode": "auto",
        "scope": scope,
    })
    url = json.dumps(f"/api/v1/client/watchlist/limit-distribution/stocks?{query}")
    js = (
        "(async()=>{"
        "const token=localStorage.getItem('user_token')||'';"
        f"const TIMEOUT_MS={FETCH_TIMEOUT_MS};"
        "const ctrl=new AbortController();"
        "const timer=setTimeout(()=>ctrl.abort(),TIMEOUT_MS);"
        f"let r;try{{r=await fetch({url},{{headers:{{Authorization:'Bearer '+token}},signal:ctrl.signal}});}}finally{{clearTimeout(timer);}}"
        "const j=await r.json();"
        "const d=j.data||{};"
        "const stocks=(d.stocks||[]).filter(s=>s&&(s.limit_status||s.limit_times)).map(s=>({"
        "ts_code:s.ts_code,name:s.name,price:s.price,pct_chg:s.pct_chg,pct_chg_3d:s.pct_chg_3d,"
        "pct_chg_5d:s.pct_chg_5d,pct_chg_10d:s.pct_chg_10d,pct_chg_20d:s.pct_chg_20d,"
        "amount:s.amount,vol:s.vol,circ_mv:s.circ_mv,total_mv:s.total_mv,sw_l1_name:s.sw_l1_name,"
        "sw_l2_name:s.sw_l2_name,sw_l3_name:s.sw_l3_name,ths_concept_top:s.ths_concept_top,"
        "fund_flow_1d:s.fund_flow_1d,fund_flow_5d:s.fund_flow_5d,limit_times:s.limit_times,"
        "limit_status:s.limit_status,first_limit_time:s.first_limit_time,last_limit_time:s.last_limit_time,"
        "open_times:s.open_times,leader_plate:s.leader_plate,leader_sub_plate:s.leader_sub_plate,"
        "theme_names:s.theme_names,up_stat:s.up_stat,up_stat_days:s.up_stat_days,up_stat_boards:s.up_stat_boards,"
        "high_status:s.high_status,high_status_label:s.high_status_label,extra:s.extra"
        "}));"
        "return JSON.stringify({trade_date:d.trade_date,dimension:d.dimension,code:d.code,name:d.name,total:d.total,stocks});"
        "})()"
    )
    raw = fs.cdp_eval(js, timeout=CDP_SINGLE_TIMEOUT)
    return json.loads(raw) if raw else {"stocks": []}


def _get_sector_stocks_batch(items: list[dict], trade_date: str, dimension: str, scope: str, batch: int = 6):
    slim = [{"code": item.get("code"), "name": item.get("name")} for item in items if item.get("code")]
    items_json = json.dumps(slim, ensure_ascii=False)
    td_json = json.dumps(trade_date)
    dimension_json = json.dumps(dimension)
    scope_json = json.dumps(scope)
    js = (
        "(async()=>{"
        f"const items={items_json};"
        f"const tradeDate={td_json};"
        f"const dimension={dimension_json};"
        f"const scope={scope_json};"
        "const token=localStorage.getItem('user_token')||'';"
        "const out={};"
        f"const BATCH={int(batch)};"
        f"const TIMEOUT_MS={FETCH_TIMEOUT_MS};"
        "async function one(item){"
        "const q=new URLSearchParams({code:item.code,trade_date:tradeDate,dimension,mode:'auto',scope}).toString();"
        "try{"
        "const ctrl=new AbortController();"
        "const timer=setTimeout(()=>ctrl.abort(),TIMEOUT_MS);"
        "let r;try{r=await fetch('/api/v1/client/watchlist/limit-distribution/stocks?'+q,{headers:{Authorization:'Bearer '+token},signal:ctrl.signal});}finally{clearTimeout(timer);}"
        "const j=await r.json();"
        "const d=j.data||{};"
        "const stocks=(d.stocks||[]).filter(s=>s&&(s.limit_status||s.limit_times)).map(s=>({"
        "ts_code:s.ts_code,name:s.name,price:s.price,pct_chg:s.pct_chg,pct_chg_3d:s.pct_chg_3d,"
        "pct_chg_5d:s.pct_chg_5d,pct_chg_10d:s.pct_chg_10d,pct_chg_20d:s.pct_chg_20d,"
        "amount:s.amount,vol:s.vol,circ_mv:s.circ_mv,total_mv:s.total_mv,sw_l1_name:s.sw_l1_name,"
        "sw_l2_name:s.sw_l2_name,sw_l3_name:s.sw_l3_name,ths_concept_top:s.ths_concept_top,"
        "fund_flow_1d:s.fund_flow_1d,fund_flow_5d:s.fund_flow_5d,limit_times:s.limit_times,"
        "limit_status:s.limit_status,first_limit_time:s.first_limit_time,last_limit_time:s.last_limit_time,"
        "open_times:s.open_times,leader_plate:s.leader_plate,leader_sub_plate:s.leader_sub_plate,"
        "theme_names:s.theme_names,up_stat:s.up_stat,up_stat_days:s.up_stat_days,up_stat_boards:s.up_stat_boards,"
        "high_status:s.high_status,high_status_label:s.high_status_label,extra:s.extra"
        "}));"
        "out[item.code]={trade_date:d.trade_date,dimension:d.dimension,code:d.code||item.code,name:d.name||item.name,total:d.total,stocks};"
        "}catch(e){out[item.code]={code:item.code,name:item.name,total:null,stocks:[],error:String(e)}}"
        "}"
        "for(let i=0;i<items.length;i+=BATCH){await Promise.all(items.slice(i,i+BATCH).map(one));}"
        "return JSON.stringify(out);"
        "})()"
    )
    raw = fs.cdp_eval(js, timeout=CDP_BATCH_TIMEOUT)
    return json.loads(raw) if raw else {}


def _get_sector_stocks_resilient(items: list[dict], trade_date: str, dimension: str, scope: str, batch: int = 6):
    if not items:
        return {}
    try:
        return _get_sector_stocks_batch(items, trade_date, dimension, scope, batch=batch)
    except Exception as exc:
        if len(items) == 1:
            item = items[0]
            code = item.get("code")
            name = item.get("name")
            return {code: {"code": code, "name": name, "total": None, "stocks": [], "error": str(exc)}}
        mid = len(items) // 2
        left = _get_sector_stocks_resilient(items[:mid], trade_date, dimension, scope, batch=max(batch // 2, 1))
        right = _get_sector_stocks_resilient(items[mid:], trade_date, dimension, scope, batch=max(batch // 2, 1))
        left.update(right)
        return left


def _heat_row(trade_date: date, payload: dict, item: dict, rank: int, now: datetime):
    return (
        trade_date,
        item.get("code"),
        item.get("name"),
        payload.get("dimension"),
        payload.get("scope"),
        payload.get("data_stage"),
        payload.get("is_realtime"),
        _parse_datetime(payload.get("update_time")),
        payload.get("market_limit_up_count"),
        item.get("limit_up_count"),
        item.get("total_count"),
        item.get("limit_up_ratio"),
        item.get("market_share"),
        item.get("fd_amount"),
        rank,
        json.dumps(item.get("top_stocks") or [], ensure_ascii=False),
        "fupanhui:watchlist/limit-distribution",
        now,
    )


def _is_limit_stock(stock: dict) -> bool:
    return bool(stock.get("limit_status") or stock.get("limit_times"))


def _stock_row(trade_date: date, sector_code: str, sector_name: str, stock: dict, now: datetime):
    extra = stock.get("extra") if isinstance(stock.get("extra"), dict) else {}
    return (
        trade_date,
        sector_code,
        sector_name,
        stock.get("ts_code"),
        stock.get("name"),
        stock.get("price"),
        stock.get("pct_chg"),
        stock.get("pct_chg_3d"),
        stock.get("pct_chg_5d"),
        stock.get("pct_chg_10d"),
        stock.get("pct_chg_20d"),
        stock.get("amount"),
        stock.get("vol"),
        stock.get("circ_mv"),
        stock.get("total_mv"),
        stock.get("sw_l1_name"),
        stock.get("sw_l2_name"),
        stock.get("sw_l3_name"),
        stock.get("ths_concept_top"),
        stock.get("fund_flow_1d"),
        stock.get("fund_flow_5d"),
        stock.get("limit_times"),
        stock.get("limit_status"),
        stock.get("first_limit_time"),
        stock.get("last_limit_time"),
        stock.get("open_times"),
        stock.get("leader_plate"),
        stock.get("leader_sub_plate"),
        json.dumps(stock.get("theme_names") or [], ensure_ascii=False),
        stock.get("up_stat"),
        stock.get("up_stat_days"),
        stock.get("up_stat_boards"),
        stock.get("high_status"),
        stock.get("high_status_label"),
        extra.get("fd_amount"),
        _parse_datetime(extra.get("limit_update_time")),
        "fupanhui:watchlist/limit-distribution/stocks",
        now,
    )


def sync_fupanhui_limit_heat(
    trade_date: str | None = None,
    dimension: str = "sector",
    scope: str = "all",
    sector: str | None = None,
    limit: int | None = None,
    sleep: float = 0.1,
    detail_chunk: int = 12,
) -> dict:
    init_db()
    td = trade_date or fs.get_latest_date()
    if not td:
        raise RuntimeError("无目标交易日, 请显式传 --trade-date 或确认复盘会 latest-date 可用")

    payload = _get_distribution(td, dimension, scope)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RuntimeError("复盘会 limit-distribution 未返回 items")
    current_date = _parse_date(payload.get("trade_date")) or _parse_date(td)
    if current_date is None:
        raise RuntimeError(f"无法解析涨停热力图日期: {td}")

    items = [item for item in payload["items"] if item.get("code") and item.get("name")]
    if sector:
        items = [item for item in items if item.get("code") == sector or item.get("name") == sector]
    if limit is not None:
        items = items[:max(int(limit), 0)]
    now = datetime.now()
    heat_rows = [_heat_row(current_date, payload, item, idx + 1, now) for idx, item in enumerate(items)]
    stock_rows = []
    fetched_sectors = []
    failures = []
    stocks_by_sector = {}
    chunk_size = max(int(detail_chunk), 1)
    detail_items = [item for item in items if (item.get("limit_up_count") or 0) > 0]
    total_chunks = (len(detail_items) + chunk_size - 1) // chunk_size if detail_items else 0
    for idx, start in enumerate(range(0, len(detail_items), chunk_size), 1):
        chunk = detail_items[start:start + chunk_size]
        chunk_names = ",".join(str(item.get("name") or item.get("code")) for item in chunk[:3])
        print(f"[limit-heat] detail chunk {idx}/{total_chunks} size={len(chunk)} first={chunk_names}", flush=True)
        chunk_result = _get_sector_stocks_resilient(chunk, current_date.isoformat(), dimension, scope)
        stocks_by_sector.update(chunk_result)
        chunk_errors = sum(1 for value in chunk_result.values() if isinstance(value, dict) and value.get("error"))
        print(f"[limit-heat] detail chunk {idx}/{total_chunks} done errors={chunk_errors}", flush=True)
        if sleep:
            time.sleep(float(sleep))
    for item in items:
        code = item.get("code")
        name = item.get("name")
        try:
            stocks_payload = stocks_by_sector.get(code) or {"stocks": []}
            if stocks_payload.get("error"):
                raise RuntimeError(stocks_payload["error"])
            stocks = stocks_payload.get("stocks") if isinstance(stocks_payload, dict) else []
            limit_stocks = [s for s in stocks if isinstance(s, dict) and s.get("ts_code") and _is_limit_stock(s)]
            stock_rows.extend(_stock_row(current_date, code, name, stock, now) for stock in limit_stocks)
            fetched_sectors.append({"code": code, "name": name, "total": len(stocks), "limit_stocks": len(limit_stocks)})
        except Exception as exc:
            failures.append((code, name, str(exc)))

    full_refresh = sector is None and limit is None
    con = connect()
    try:
        _ensure_schema(con)
        con.execute("BEGIN TRANSACTION")
        success_codes = [item.get("code") for item in items if item.get("code") not in {f[0] for f in failures}]
        if full_refresh:
            con.execute(
                "DELETE FROM fact_theme_limit_heat_daily WHERE trade_date = ? AND dimension = ? AND scope = ?",
                [current_date, dimension, scope],
            )
            if not failures:
                con.execute("DELETE FROM fact_theme_limit_stock_daily WHERE trade_date = ?", [current_date])
            else:
                for code in success_codes:
                    con.execute(
                        "DELETE FROM fact_theme_limit_stock_daily WHERE trade_date = ? AND sector_ts_code = ?",
                        [current_date, code],
                    )
        else:
            for item in items:
                con.execute(
                    "DELETE FROM fact_theme_limit_heat_daily WHERE trade_date = ? AND sector_ts_code = ? AND dimension = ? AND scope = ?",
                    [current_date, item.get("code"), dimension, scope],
                )
                con.execute(
                    "DELETE FROM fact_theme_limit_stock_daily WHERE trade_date = ? AND sector_ts_code = ?",
                    [current_date, item.get("code")],
                )
        if heat_rows:
            con.executemany(HEAT_UPSERT_SQL, heat_rows)
        if stock_rows:
            con.executemany(STOCK_UPSERT_SQL, stock_rows)
        con.execute("COMMIT")
        stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date)
            FROM fact_theme_limit_heat_daily
            """
        ).fetchone()
        stock_stats = con.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_ts_code)
            FROM fact_theme_limit_stock_daily
            """
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
        "trade_date": current_date.isoformat(),
        "dimension": dimension,
        "scope": scope,
        "market_limit_up_count": payload.get("market_limit_up_count"),
        "items_total": len(payload["items"]),
        "items_processed": len(items),
        "heat_rows": len(heat_rows),
        "stock_rows": len(stock_rows),
        "fetched_sectors": fetched_sectors,
        "failures": failures,
        "table_total": stats[0],
        "table_dates": stats[1],
        "date_min": str(stats[2]) if stats[2] else None,
        "date_max": str(stats[3]) if stats[3] else None,
        "stock_table_total": stock_stats[0],
        "stock_table_dates": stock_stats[1],
        "stock_table_stocks": stock_stats[2],
    }
