"""同步 fact_sector_stock_daily: 板块成分股每日全量快照。

数据源: fupanhui sector-cycle stocks。
按 chunk 批量抓取 (一次 CDP eval 内并发抓一批板块, 大幅减少浏览器往返),
单板块写完即提交, 可中断可续跑; chunk 失败自动降级为逐板块单抓。
用 --limit 分批增量, 默认跳过当日已抓板块 (resume)。
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date

from ..db import connect, init_db, get_published_snapshot_id
from ..sector_universe import MemberResult, MemberWorkItem, SectorUniverseStore
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


def _ensure_columns(con):
    """fact_sector_stock_daily 已重构为 VIEW；确保底层 generation 表列存在。"""
    cols = {
        "pct_chg_3d": "DOUBLE",
        "high_status": "TEXT",
        "high_status_label": "TEXT",
        "limit_times": "INTEGER",
        "role_tags_json": "TEXT",
        "circ_mv": "DOUBLE",
        "float_mcap_yi": "DOUBLE",
        "total_mcap_yi": "DOUBLE",
        "free_float_mcap_yi": "DOUBLE",
        "mcap_source": "TEXT",
    }
    for name, typ in cols.items():
        con.execute(f"ALTER TABLE fact_sector_stock_daily_generation ADD COLUMN IF NOT EXISTS {name} {typ}")


def _plain_code(ts_code: str) -> str:
    return str(ts_code).split(".")[0]


def _tencent_symbol(ts_code: str) -> str:
    code = _plain_code(ts_code)
    if str(ts_code).upper().endswith(".BJ"):
        return f"bj{code}"
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith("8"):
        return f"bj{code}"
    return f"sz{code}"


_CAP_CACHE: dict[str, dict] = {}
_CAP_WORKERS = 8


def _fetch_cap_batch(batch: list[str]) -> str | None:
    url = "https://qt.gtimg.cn/q=" + ",".join(batch)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for _cap_attempt in range(4):
        try:
            return urllib.request.urlopen(req, timeout=15).read().decode("gbk", "ignore")
        except Exception:
            if _cap_attempt < 3:
                time.sleep(1.5 * (_cap_attempt + 1))
    return None


def _tencent_market_caps(ts_codes: list[str]) -> dict[str, dict]:
    ts_codes = [c for c in ts_codes if c]
    need = [c for c in ts_codes if c not in _CAP_CACHE]
    symbols = [_tencent_symbol(c) for c in need]
    if not symbols:
        return {c: _CAP_CACHE[c] for c in ts_codes if c in _CAP_CACHE}
    out = _CAP_CACHE
    batches = [symbols[i:i + 80] for i in range(0, len(symbols), 80)]
    with ThreadPoolExecutor(max_workers=min(_CAP_WORKERS, len(batches))) as pool:
        texts = list(pool.map(_fetch_cap_batch, batches))
    for text in texts:
        if text is None:
            continue
        for line in text.strip().split(";"):
            if not line.strip() or '="' not in line:
                continue
            key = line.split("=")[0].split("_")[-1]
            vals = line.split('"')[1].split("~")
            if len(vals) < 46:
                continue
            code = key[2:]
            ts_code = f"{code}.SH" if key.startswith("sh") else (f"{code}.BJ" if key.startswith("bj") else f"{code}.SZ")

            def num(idx):
                try:
                    return float(vals[idx]) if vals[idx] else None
                except (TypeError, ValueError, IndexError):
                    return None

            out[ts_code] = {
                "float_mcap_yi": num(44),
                "total_mcap_yi": num(45),
                "mcap_source": "tencent",
            }
    return {c: _CAP_CACHE[c] for c in ts_codes if c in _CAP_CACHE}


UPSERT_SQL = """
    INSERT INTO fact_sector_stock_daily_generation
        (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, sw_l1,
         stock_ts_code, stock_name, price, pct_chg, amount,
         pct_chg_3d, pct_chg_5d, pct_chg_10d, pct_chg_20d,
         high_status, high_status_label, limit_times,
         fund_flow_1d, fund_flow_5d, sw_industry,
         leader_plate, leader_sub_plate, role_tags_json,
         circ_mv, float_mcap_yi, total_mcap_yi, free_float_mcap_yi, mcap_source,
         source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code) DO UPDATE SET
        sector_name = excluded.sector_name,
        sw_l1 = excluded.sw_l1,
        stock_name = excluded.stock_name,
        price = excluded.price,
        pct_chg = excluded.pct_chg,
        amount = excluded.amount,
        pct_chg_3d = excluded.pct_chg_3d,
        pct_chg_5d = excluded.pct_chg_5d,
        pct_chg_10d = excluded.pct_chg_10d,
        pct_chg_20d = excluded.pct_chg_20d,
        high_status = excluded.high_status,
        high_status_label = excluded.high_status_label,
        limit_times = excluded.limit_times,
        fund_flow_1d = excluded.fund_flow_1d,
        fund_flow_5d = excluded.fund_flow_5d,
        sw_industry = excluded.sw_industry,
        leader_plate = excluded.leader_plate,
        leader_sub_plate = excluded.leader_sub_plate,
        role_tags_json = excluded.role_tags_json,
        circ_mv = excluded.circ_mv,
        float_mcap_yi = excluded.float_mcap_yi,
        total_mcap_yi = excluded.total_mcap_yi,
        free_float_mcap_yi = excluded.free_float_mcap_yi,
        mcap_source = excluded.mcap_source,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def _slim_to_full(stock: dict) -> dict:
    """把 get_sector_stocks_batch 的 slim 键还原为单板块 API 的完整键名。"""
    return {
        "ts_code": stock.get("c"),
        "name": stock.get("n"),
        "price": stock.get("p"),
        "pct_chg": stock.get("pc"),
        "amount": stock.get("a"),
        "pct_chg_3d": stock.get("p3"),
        "pct_chg_5d": stock.get("p5"),
        "pct_chg_10d": stock.get("p10"),
        "pct_chg_20d": stock.get("p20"),
        "fund_flow_1d": stock.get("f1"),
        "fund_flow_5d": stock.get("f5"),
        "sw_industry": stock.get("sw"),
        "leader_plate": stock.get("lp"),
        "high_status": stock.get("hs"),
        "high_status_label": stock.get("hl"),
        "limit_times": stock.get("lt"),
        "role_tags": stock.get("rt"),
        "circ_mv": stock.get("cm"),
    }


def sync_fact_sector_stock_daily(
    trade_date: str | None = None,
    sector: str | None = None,
    limit: int | None = None,
    only_missing: bool = True,
    sleep: float = 0.3,
    chunk: int = 4,
    max_attempts: int = 3,
) -> dict:
    """批量回补某交易日的成分股快照。

    按 chunk 一次 CDP eval 并发抓一批板块, 逐板块写完即提交;
    chunk 失败自动降级为逐板块单抓。默认跳过当日已抓板块, 可多次短命令续跑。
    参数:
      trade_date  指定交易日, 留空取 fact_sector_daily 最新日。
      sector      只抓单个板块 (代码或名称)。
      limit       本次最多抓多少个板块。
      only_missing 跳过当日已抓板块 (续跑)。
      sleep       chunk 间隔秒数。
      chunk       单次 eval 并发抓取的板块数。
    """
    init_db()
    con = connect()
    try:
        _ensure_columns(con)
        dim = _load_sector_dim(con)
        td = _parse_date(trade_date) if trade_date else _latest_trade_date(con)
        if not dim:
            raise RuntimeError("dim_sector 为空, 请先运行 sync-sectors")
        if td is None:
            raise RuntimeError("无目标交易日, 请先运行 sync-sector-daily 或显式传 --trade-date")
        td_str = td.isoformat()
        snapshot_id = get_published_snapshot_id(con, td_str)
        if snapshot_id == "legacy":
            raise RuntimeError(f"{td_str} 无已发布板块快照, 请先运行 sync-sectors")
        store = SectorUniverseStore(con)
        if sector:
            ts_code = _resolve_sector(dim, sector)
            if not ts_code:
                raise RuntimeError(f"未找到板块: {sector}")
            rows = con.execute(
                """
                SELECT u.sector_ts_code, u.sector_name, u.expected_stock_count,
                       m.attempt_count, m.status
                FROM fact_sector_universe_daily AS u
                JOIN ops_sector_member_sync_daily AS m
                  ON m.trade_date = u.trade_date AND m.snapshot_id = u.snapshot_id
                 AND m.sector_ts_code = u.sector_ts_code
                WHERE u.trade_date = ? AND u.snapshot_id = ? AND u.sector_ts_code = ?
                """,
                [td, snapshot_id, ts_code],
            ).fetchall()
            if not rows:
                raise RuntimeError(f"板块 {ts_code} 不在 {td_str} 已发布快照中")
            todo = [MemberWorkItem(*row) for row in rows]
        elif only_missing:
            todo = list(store.next_member_work(snapshot_id, limit=limit or len(dim), max_attempts=max_attempts))
        else:
            rows = con.execute(
                """
                SELECT u.sector_ts_code, u.sector_name, u.expected_stock_count,
                       m.attempt_count, m.status
                FROM fact_sector_universe_daily AS u
                JOIN ops_sector_member_sync_daily AS m
                  ON m.trade_date = u.trade_date AND m.snapshot_id = u.snapshot_id
                 AND m.sector_ts_code = u.sector_ts_code
                WHERE u.trade_date = ? AND u.snapshot_id = ?
                ORDER BY u.sector_ts_code
                LIMIT ?
                """,
                [td, snapshot_id, limit or len(dim)],
            ).fetchall()
            todo = [MemberWorkItem(*row) for row in rows]

        processed = 0
        rows_written = 0
        failures = []
        chunk_size = max(int(chunk), 1)
        for start in range(0, len(todo), chunk_size):
            work_batch = todo[start:start + chunk_size]
            batch_codes = [item.sector_ts_code for item in work_batch]
            payloads: dict[str, dict] = {}
            errors: dict[str, str] = {}
            t_eval = time.time()
            try:
                raw = fs.get_sector_stocks_batch(batch_codes, trade_date=td_str)
                for ts_code in batch_codes:
                    entry = raw.get(ts_code) or {}
                    payloads[ts_code] = {
                        "trade_date": entry.get("td"),
                        "stocks": [_slim_to_full(s) for s in entry.get("st") or []],
                    }
            except Exception:
                for ts_code in batch_codes:
                    try:
                        payloads[ts_code] = fs.get_sector_stocks(ts_code, trade_date=td_str)
                    except Exception as exc:
                        errors[ts_code] = type(exc).__name__
            t_eval = time.time() - t_eval
            all_codes = [
                stock.get("ts_code")
                for payload in payloads.values()
                for stock in payload.get("stocks", [])
                if stock.get("ts_code")
            ]
            t_caps = time.time()
            cap_map = _tencent_market_caps(all_codes)
            t_caps = time.time() - t_caps
            print(
                f"[sector-stocks] chunk {start // chunk_size + 1}/"
                f"{(len(todo) + chunk_size - 1) // chunk_size} "
                f"sectors={len(batch_codes)} stocks={len(all_codes)} "
                f"eval={t_eval:.1f}s caps={t_caps:.1f}s",
                flush=True,
            )
            for item in work_batch:
                if item.sector_ts_code in errors:
                    receipt = store.record_member_result(
                        snapshot_id, item.sector_ts_code, MemberResult.error(errors[item.sector_ts_code])
                    )
                else:
                    payload = payloads.get(item.sector_ts_code, {})
                    stocks = payload.get("stocks", [])
                    if not stocks:
                        receipt = store.record_member_result(
                            snapshot_id, item.sector_ts_code, MemberResult.empty()
                        )
                    else:
                        enriched = []
                        for stock in stocks:
                            cap = cap_map.get(stock.get("ts_code"), {})
                            enriched.append({
                                **stock,
                                "role_tags_json": json.dumps(stock.get("role_tags") or [], ensure_ascii=False),
                                "float_mcap_yi": cap.get("float_mcap_yi"),
                                "total_mcap_yi": cap.get("total_mcap_yi"),
                                "mcap_source": cap.get("mcap_source"),
                                "source": "fupanhui",
                            })
                        receipt = store.record_member_result(
                            snapshot_id,
                            item.sector_ts_code,
                            MemberResult.success(
                                served_date=payload.get("trade_date") or td_str,
                                stocks=enriched,
                            ),
                        )
                processed += 1
                if receipt.status == "success":
                    rows_written += receipt.actual_stock_count or 0
                else:
                    failures.append((receipt.sector_ts_code, receipt.last_error_code or receipt.status))
            if sleep:
                time.sleep(sleep)

        audit = store.completion_audit(
            td_str, declared_tables=frozenset({"fact_sector_stock_daily"})
        )
        grand_total = con.execute(
            "SELECT COUNT(*) FROM fact_sector_stock_daily_generation"
        ).fetchone()[0]
    finally:
        con.close()

    return {
        "trade_date": td_str,
        "processed": processed,
        "rows_written": rows_written,
        "failures": failures,
        "sectors_done_today": audit.success_count,
        "sectors_total": audit.declared_sector_count,
        "sectors_remaining": audit.declared_sector_count - audit.success_count,
        "table_total": grand_total,
    }
