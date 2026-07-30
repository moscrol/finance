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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date

from ..db import connect, init_db
from ..sector_universe import (
    MemberResult,
    SectorUniverseStore,
    SectorUniverseValidationError,
)
from ..sources import fupanhui_source as fs

# 一个板块最多重试几次后停止占用当日配额 (回执仍保留, 供夜间编排审计)。
MEMBER_MAX_ATTEMPTS = 3


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
    chunk: int = 10,
) -> dict:
    """批量回补某交易日的成分股快照。

    按 chunk 一次 CDP eval 并发抓一批板块, 逐板块写入即提交;
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
        dim = _load_sector_dim(con)
        td = _parse_date(trade_date) if trade_date else _latest_trade_date(con)
    finally:
        con.close()

    if not dim:
        raise RuntimeError("dim_sector 为空, 请先运行 sync-sectors")
    if td is None:
        raise RuntimeError("无目标交易日, 请先运行 sync-sector-daily 或显式传 --trade-date")

    td_str = td.isoformat()
    now = datetime.now()
    rows_written = 0
    failures = []
    status_counts: Counter[str] = Counter()

    con = connect()
    try:
        store = SectorUniverseStore(con)
        # 分母来自已发布宇宙的声明, 不是"抓到多少算多少"。没有已发布表头就
        # fail-closed: 宁可不抓, 也不能凭 dim_sector 的物理身份写成分。
        try:
            snapshot = store.published_snapshot(td)
        except SectorUniverseValidationError as exc:
            raise RuntimeError(
                f"{td_str} 无唯一已发布板块宇宙, 请先运行 sync-sectors 发布快照: {exc}"
            ) from None

        # 取工作: 由回执驱动, 而非"当日已有行 = 已完成"。后者看不见抓错、
        # 抓漏和从未尝试的差别; 前者能。
        if sector:
            ts_code = _resolve_sector(dim, sector)
            if not ts_code:
                raise RuntimeError(f"未找到板块: {sector}")
            todo = [ts_code]
        else:
            work = store.next_member_work(
                snapshot.snapshot_id,
                limit=int(limit) if limit else snapshot.sector_count,
                max_attempts=MEMBER_MAX_ATTEMPTS,
            )
            todo = [item.sector_ts_code for item in work]
            if not only_missing:
                # 显式全量重抓: 仍按公平顺序, 只是不排除已成功的板块。
                todo = [row.sector_ts_code for row in snapshot.sectors]
                if limit:
                    todo = todo[: int(limit)]
        chunk_size = max(int(chunk), 1)
        for start in range(0, len(todo), chunk_size):
            batch_codes = todo[start:start + chunk_size]
            payloads: dict[str, dict] = {}
            t_eval = time.time()
            try:
                raw = fs.get_sector_stocks_batch(batch_codes, trade_date=td_str)
                for ts_code in batch_codes:
                    entry = raw.get(ts_code) or {}
                    payloads[ts_code] = {
                        "trade_date": entry.get("td"),
                        "stocks": [_slim_to_full(s) for s in entry.get("st") or []],
                    }
            except Exception:  # noqa: BLE001
                # 批量 eval 失败 -> 降级逐板块单抓
                for ts_code in batch_codes:
                    try:
                        payloads[ts_code] = fs.get_sector_stocks(ts_code, trade_date=td_str)
                    except Exception as e:  # noqa: BLE001
                        failures.append((ts_code, str(e)))
            t_eval = time.time() - t_eval
            all_codes = [
                s.get("ts_code")
                for payload in payloads.values()
                for s in payload.get("stocks", [])
                if s.get("ts_code")
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
            for ts_code, payload in payloads.items():
                stocks = payload.get("stocks", [])
                if not stocks:
                    # 空结果也要留回执: "provider 说没有" 和 "我们没问到"
                    # 是两回事, 混在一起就又变回静默丢失。
                    receipt = store.record_member_result(
                        snapshot.snapshot_id, ts_code, MemberResult.empty()
                    )
                    status_counts[receipt.status] += 1
                    failures.append((ts_code, "empty stocks"))
                    continue
                members = []
                for s in stocks:
                    code = s.get("ts_code")
                    if not code:
                        continue
                    cap = cap_map.get(code, {})
                    members.append({
                        "ts_code": code,
                        "name": s.get("name"),
                        "price": s.get("price"),
                        "pct_chg": s.get("pct_chg"),
                        "amount": s.get("amount"),
                        "pct_chg_3d": s.get("pct_chg_3d"),
                        "pct_chg_5d": s.get("pct_chg_5d"),
                        "pct_chg_10d": s.get("pct_chg_10d"),
                        "pct_chg_20d": s.get("pct_chg_20d"),
                        "high_status": s.get("high_status"),
                        "high_status_label": s.get("high_status_label"),
                        "limit_times": s.get("limit_times"),
                        "fund_flow_1d": s.get("fund_flow_1d"),
                        "fund_flow_5d": s.get("fund_flow_5d"),
                        "sw_industry": s.get("sw_industry"),
                        "leader_plate": s.get("leader_plate"),
                        "leader_sub_plate": None,
                        "role_tags_json": json.dumps(
                            s.get("role_tags") or [], ensure_ascii=False
                        ),
                        "circ_mv": s.get("circ_mv"),
                        "float_mcap_yi": cap.get("float_mcap_yi"),
                        "total_mcap_yi": cap.get("total_mcap_yi"),
                        "free_float_mcap_yi": None,
                        "mcap_source": cap.get("mcap_source"),
                        "source": "fupanhui",
                        "updated_at": now,
                    })
                served = _parse_date(payload.get("trade_date")) or td
                receipt = store.record_member_result(
                    snapshot.snapshot_id,
                    ts_code,
                    MemberResult.success(
                        served_date=served.isoformat(), stocks=tuple(members)
                    ),
                )
                status_counts[receipt.status] += 1
                if receipt.status == "success":
                    rows_written += receipt.actual_stock_count or 0
                else:
                    failures.append((ts_code, receipt.last_error_code or receipt.status))
            if sleep:
                time.sleep(sleep)

        # 经 store 取数：物理代际表只允许 sector_universe 直接访问。
        grand_total = store.member_generation_row_count()
        done_today = con.execute(
            """
            SELECT COUNT(*) FROM ops_sector_member_sync_daily
            WHERE trade_date = ? AND snapshot_id = ? AND status = 'success'
            """,
            [td, snapshot.snapshot_id],
        ).fetchone()[0]
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    # 分母是快照声明的板块数, 不是 dim_sector 的物理行数——后者可能包含
    # 当日已退市/未纳入的身份, 用它当分母会把覆盖率算高。
    return {
        "trade_date": td_str,
        "snapshot_id": snapshot.snapshot_id,
        "processed": sum(status_counts.values()),
        "status_counts": dict(status_counts),
        "rows_written": rows_written,
        "failures": failures,
        "sectors_done_today": done_today,
        "sectors_total": snapshot.sector_count,
        "sectors_remaining": snapshot.sector_count - done_today,
        "declared_relationship_count": snapshot.declared_relationship_count,
        "table_total": grand_total,
    }
