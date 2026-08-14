#!/usr/bin/env python3
"""复盘会公开资产质检：结构门（全窗口）+ 公开 API 抽查对账。只读，不写库。

用法（repo 根目录或任意 cwd）：
    python3 skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py
    QA_SAMPLE=2026-07-01,2025-06-03 python3 skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py

- DB 路径走 market_feature_store.db（MARKET_FEATURE_STORE_DB 可覆盖）。
- QA_SAMPLE 逗号分隔交易日；不设则用内置 8 日（含两次事故日 / 美股休市日 / 窗口端点）。
- 随机抽样建议固定种子从 fact_market_daily 日历里抽，收据里记种子，保证可复现。
- 退出码 0=通过，1=有 FAIL。抽查依赖公开 API 当时仍返回同样的值（历史日实测稳定）。

为什么不只数行数：本仓踩过「拷昨日行改日期，覆盖率全绿、值是空壳」的坑，
所以必须有一层拿库里的值和源头逐项对（keywords 数组 / DJI close / core top5+收盘 /
dragon 净额 / 相似日集合 / leader 当日 as-of / auction 行数 / reg_pool 代码集合）。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from market_feature_store.db import DB_PATH  # noqa: E402

DB = str(DB_PATH)
BASE = "https://fupanhui.com/api/v1/client"
WINDOW = ("2025-01-02", "2026-08-12")
SAMPLE = [s.strip() for s in os.environ.get("QA_SAMPLE", "").split(",") if s.strip()] or [
    "2026-08-12",
    "2026-06-02",
    "2026-03-03",
    "2026-01-27",
    "2025-11-27",
    "2025-07-18",
    "2025-04-18",
    "2025-01-02",
]
FAILS: list[str] = []
WARNS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"FAIL  {msg}")


def warn(msg: str) -> None:
    WARNS.append(msg)
    print(f"WARN  {msg}")


def ok(msg: str) -> None:
    print(f"OK    {msg}")


def api_get(path: str, params: dict | None = None) -> dict:
    q = "?" + urllib.parse.urlencode(params) if params else ""
    url = f"{BASE}{path}{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        parsed = json.loads(resp.read().decode())
    if isinstance(parsed, dict) and "data" in parsed:
        return parsed["data"] if isinstance(parsed["data"], dict) else {}
    return parsed if isinstance(parsed, dict) else {}


def close_eq(a, b, rel=1e-4, abs_tol=0.02) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if fa == fb:
        return True
    scale = max(abs(fa), abs(fb), 1.0)
    return abs(fa - fb) <= max(abs_tol, rel * scale)


def dstr(v) -> str:
    if v is None:
        return ""
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def keywords_from_summary(data: dict) -> list[str]:
    raw = data.get("keywords") if isinstance(data, dict) else None
    parts: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                text = str(item.get("name") or item.get("keyword") or item.get("text") or "").strip()
            else:
                text = str(item).strip()
            if text:
                parts.append(text)
    elif isinstance(raw, str) and raw.strip():
        parts = [raw.strip()]
    return parts


def structural(con) -> None:
    print("\n=== A. 结构 / 日历对齐 ===")
    cal_n = con.execute(
        "SELECT COUNT(*) FROM fact_market_daily WHERE trade_date BETWEEN ? AND ?",
        list(WINDOW),
    ).fetchone()[0]
    if cal_n != 390:
        fail(f"窗口交易日 {cal_n} != 390")
    else:
        ok(f"窗口 {WINDOW[0]}~{WINDOW[1]} = {cal_n} 日")

    checks = [
        ("keywords", "SELECT COUNT(*) FROM fact_market_daily WHERE trade_date BETWEEN ? AND ? AND summary_keywords IS NOT NULL AND summary_keywords <> ''"),
        ("core_stocks", "SELECT COUNT(DISTINCT trade_date) FROM fact_core_stock_daily WHERE trade_date BETWEEN ? AND ?"),
        ("dragon", "SELECT COUNT(DISTINCT trade_date) FROM fact_dragon_tiger_daily WHERE trade_date BETWEEN ? AND ?"),
        ("reg_pool", "SELECT COUNT(DISTINCT effective_date) FROM fact_regulation_pool_daily WHERE effective_date BETWEEN ? AND ?"),
        ("leader", "SELECT COUNT(DISTINCT trade_date) FROM fact_leader_height_daily WHERE trade_date BETWEEN ? AND ?"),
        ("global_idx", "SELECT COUNT(DISTINCT trade_date) FROM fact_global_index_daily WHERE trade_date BETWEEN ? AND ?"),
        ("global_stk", "SELECT COUNT(DISTINCT trade_date) FROM fact_global_stock_daily WHERE trade_date BETWEEN ? AND ?"),
    ]
    for name, sql in checks:
        n = con.execute(sql, list(WINDOW)).fetchone()[0]
        if n != 390:
            fail(f"{name} 覆盖 {n}/390")
        else:
            ok(f"{name} 390/390")

    failed_ops = con.execute(
        """
        SELECT COUNT(*) FROM ops_pipeline_run_daily
        WHERE pipeline='fupanhui-public-assets' AND status='failed'
        """
    ).fetchone()[0]
    if failed_ops:
        fail(f"ops failed={failed_ops}")
    else:
        ok("ops failed=0")

    print("\n=== B. 主键 / 空壳 / 值域 ===")
    dup_core = con.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT trade_date, stock_ts_code, COUNT(*) c
          FROM fact_core_stock_daily GROUP BY 1,2 HAVING COUNT(*)>1
        )
        """
    ).fetchone()[0]
    if dup_core:
        fail(f"core_stocks 重复主键 {dup_core}")
    else:
        ok("core_stocks 无重复主键")

    core_n = con.execute(
        """
        SELECT MIN(n), MAX(n) FROM (
          SELECT COUNT(*) n FROM fact_core_stock_daily
          WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date
        )
        """,
        list(WINDOW),
    ).fetchone()
    if core_n[0] != 50 or core_n[1] != 50:
        fail(f"core_stocks 每日行数 min={core_n[0]} max={core_n[1]} 期望恒为 50")
    else:
        ok("core_stocks 每日恰好 50 行")

    g_n = con.execute(
        """
        SELECT MIN(n), MAX(n) FROM (
          SELECT COUNT(*) n FROM fact_global_index_daily
          WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date
        )
        """,
        list(WINDOW),
    ).fetchone()
    if g_n[0] != 5 or g_n[1] != 5:
        fail(f"global_index 每日行数 min={g_n[0]} max={g_n[1]} 期望恒为 5")
    else:
        ok("global_index 每日恰好 5 只指数")

    bad_kw = con.execute(
        """
        SELECT COUNT(*) FROM fact_market_daily
        WHERE trade_date BETWEEN ? AND ?
          AND summary_keywords IS NOT NULL AND summary_keywords <> ''
          AND json_valid(summary_keywords) IS NOT TRUE
        """,
        list(WINDOW),
    ).fetchone()[0]
    if bad_kw:
        fail(f"keywords 非法 JSON {bad_kw} 行")
    else:
        ok("keywords 全部是合法 JSON")

    null_close = con.execute(
        """
        SELECT COUNT(*) FROM fact_core_stock_daily
        WHERE trade_date BETWEEN ? AND ? AND close IS NULL
        """,
        list(WINDOW),
    ).fetchone()[0]
    if null_close:
        fail(f"core_stocks close 空值 {null_close}")
    else:
        ok("core_stocks close 无空值")

    null_dji = con.execute(
        """
        SELECT COUNT(*) FROM fact_global_index_daily
        WHERE trade_date BETWEEN ? AND ? AND code='DJI' AND (close IS NULL OR close < 1000)
        """,
        list(WINDOW),
    ).fetchone()[0]
    if null_dji:
        fail(f"DJI close 空/过小 {null_dji}")
    else:
        ok("DJI close 值域正常")

    h_rng = con.execute(
        """
        SELECT MIN(height), MAX(height), COUNT(*) FILTER (WHERE height IS NULL)
        FROM fact_leader_height_daily WHERE trade_date BETWEEN ? AND ?
        """,
        list(WINDOW),
    ).fetchone()
    if h_rng[2]:
        fail(f"leader height 空值 {h_rng[2]}")
    elif h_rng[0] is None or h_rng[0] < 1 or h_rng[1] > 20:
        fail(f"leader height 值域 {h_rng[0]}~{h_rng[1]} 超出 1~20")
    else:
        ok(f"leader height 值域 {h_rng[0]}~{h_rng[1]}")

    print("\n=== C. 跨日拷贝（空壳回填）===")
    clone_core = con.execute(
        """
        WITH fp AS (
          SELECT trade_date, string_agg(stock_ts_code, ',' ORDER BY rank) codes
          FROM fact_core_stock_daily
          WHERE trade_date BETWEEN ? AND ?
          GROUP BY 1
        )
        SELECT COUNT(*) FROM fp a
        JOIN fp b ON b.trade_date = (
          SELECT MAX(trade_date) FROM fact_market_daily
          WHERE trade_date < a.trade_date AND trade_date >= ?
        )
        WHERE a.codes = b.codes
        """,
        [WINDOW[0], WINDOW[1], WINDOW[0]],
    ).fetchone()[0]
    if clone_core > 8:
        fail(f"core_stocks 与前日代码完全相同 {clone_core} 天（像拷昨日）")
    elif clone_core:
        warn(f"core_stocks 与前日代码完全相同 {clone_core} 天（可能是名单未变）")
    else:
        ok("core_stocks 无跨日完全克隆")

    clone_dji = con.execute(
        """
        WITH d AS (
          SELECT trade_date, close FROM fact_global_index_daily
          WHERE code='DJI' AND trade_date BETWEEN ? AND ?
        )
        SELECT COUNT(*) FROM d a
        JOIN d b ON b.trade_date = (
          SELECT MAX(trade_date) FROM fact_market_daily
          WHERE trade_date < a.trade_date AND trade_date >= ?
        )
        WHERE a.close = b.close
        """,
        [WINDOW[0], WINDOW[1], WINDOW[0]],
    ).fetchone()[0]
    if clone_dji > 40:
        fail(f"DJI 收盘与前日完全相同 {clone_dji} 天（过多）")
    else:
        ok(f"DJI 收盘与前日完全相同 {clone_dji} 天（美股休市可接受）")

    print("\n=== D. 接口空结果是否像真缺口 ===")
    auc_empty = con.execute(
        """
        SELECT MIN(trade_date), MAX(trade_date), COUNT(*)
        FROM ops_pipeline_run_daily
        WHERE pipeline='fupanhui-public-assets' AND step='auction' AND status='empty'
        """
    ).fetchone()
    auc_min = con.execute(
        "SELECT MIN(trade_date) FROM fact_auction_stock_daily"
    ).fetchone()[0]
    ok(f"auction empty ops {auc_empty[2]} 日 {dstr(auc_empty[0])}~{dstr(auc_empty[1])}；有数自 {dstr(auc_min)}")
    if dstr(auc_min) > "2026-01-20":
        fail(f"auction 有数起点 {auc_min} 晚于预期 2026-01-16")

    map_empty = con.execute(
        """
        SELECT COUNT(*) FROM ops_pipeline_run_daily
        WHERE pipeline='fupanhui-public-assets' AND step='historical_mapping' AND status='empty'
        """
    ).fetchone()[0]
    ok(f"historical_mapping empty ops {map_empty} 日")


def api_spot(con) -> None:
    print(f"\n=== E. 公开 API 抽查（{len(SAMPLE)} 个交易日）===")
    for td in SAMPLE:
        print(f"\n-- {td} --")
        summary = api_get("/reviews/summary", {"trade_date": td})
        api_kw = keywords_from_summary(summary)
        db_kw_raw = con.execute(
            "SELECT summary_keywords FROM fact_market_daily WHERE trade_date = ?",
            [td],
        ).fetchone()
        db_kw = json.loads(db_kw_raw[0]) if db_kw_raw and db_kw_raw[0] else []
        if db_kw != api_kw:
            fail(f"{td} keywords db={db_kw} api={api_kw}")
        else:
            ok(f"{td} keywords {db_kw}")

        g = api_get("/reviews/global-market", {"trade_date": td})
        api_dji = None
        for m in g.get("markets") or []:
            if isinstance(m, dict) and m.get("code") == "DJI":
                api_dji = m.get("close")
                break
        row = con.execute(
            """
            SELECT close, CAST(source_trade_date AS VARCHAR)
            FROM fact_global_index_daily
            WHERE trade_date=? AND code='DJI'
            """,
            [td],
        ).fetchone()
        if not row:
            fail(f"{td} 缺 DJI 行")
        elif not close_eq(row[0], api_dji):
            fail(f"{td} DJI db={row[0]} api={api_dji} src={row[1]}")
        else:
            ok(f"{td} DJI {row[0]} source={row[1]}")

        core = api_get("/core-stocks/list", {"trade_date": td})
        api_codes = [
            str(x.get("ts_code") or "").strip()
            for x in (core.get("stocks") or [])
            if isinstance(x, dict) and x.get("ts_code")
        ]
        db_codes = [
            r[0]
            for r in con.execute(
                """
                SELECT stock_ts_code FROM fact_core_stock_daily
                WHERE trade_date=? ORDER BY rank
                """,
                [td],
            ).fetchall()
        ]
        if api_codes[:5] != db_codes[:5]:
            fail(f"{td} core top5 db={db_codes[:5]} api={api_codes[:5]}")
        elif len(api_codes) != len(db_codes):
            fail(f"{td} core 行数 db={len(db_codes)} api={len(api_codes)}")
        else:
            api_c0 = (core.get("stocks") or [{}])[0]
            db_c0 = con.execute(
                "SELECT close, pct_chg FROM fact_core_stock_daily WHERE trade_date=? AND rank=1",
                [td],
            ).fetchone()
            api_close = api_c0.get("close")
            api_pct = api_c0.get("pct_chg") if api_c0.get("pct_chg") is not None else api_c0.get("pct_change")
            if db_c0 and close_eq(db_c0[0], api_close) and close_eq(db_c0[1], api_pct):
                ok(f"{td} core {len(db_codes)} 只 top1={db_codes[0]} close={db_c0[0]}")
            else:
                fail(f"{td} core#1 close/pct db={db_c0} api=({api_close},{api_pct})")

        dragon = api_get("/data/dragon/list", {"trade_date": td})
        api_items = [x for x in (dragon.get("items") or []) if isinstance(x, dict) and x.get("ts_code")]
        db_n = con.execute(
            "SELECT COUNT(*) FROM fact_dragon_tiger_daily WHERE trade_date=?",
            [td],
        ).fetchone()[0]
        if db_n != len(api_items):
            fail(f"{td} dragon 行数 db={db_n} api={len(api_items)}")
        elif api_items:
            ts0 = str(api_items[0]["ts_code"]).strip()
            db0 = con.execute(
                """
                SELECT net_amount, close FROM fact_dragon_tiger_daily
                WHERE trade_date=? AND stock_ts_code=?
                """,
                [td, ts0],
            ).fetchone()
            if not db0:
                fail(f"{td} dragon 缺 {ts0}")
            elif not close_eq(db0[0], api_items[0].get("net_amount")):
                fail(f"{td} dragon {ts0} net db={db0[0]} api={api_items[0].get('net_amount')}")
            else:
                ok(f"{td} dragon {db_n} 只 {ts0} net={db0[0]}")
        else:
            ok(f"{td} dragon 空列表双方一致")

        mp = api_get("/reviews/historical-mapping", {"trade_date": td})
        api_sim = sorted(
            str(x.get("date") or x.get("trade_date") or "")[:10]
            for x in (mp.get("similar_days") or [])
            if isinstance(x, dict)
        )
        api_sim = [x for x in api_sim if x]
        db_sim = sorted(
            dstr(r[0])
            for r in con.execute(
                "SELECT similar_date FROM fact_historical_mapping WHERE source_date=?",
                [td],
            ).fetchall()
        )
        if api_sim != db_sim:
            fail(f"{td} mapping db={db_sim} api={api_sim}")
        else:
            ok(f"{td} mapping {len(db_sim)} 个相似日")

        ladder = api_get("/reviews/leader-ladder", {"trade_date": td})
        api_h = None
        api_leader = None
        for pt in ladder.get("height_trend") or []:
            if isinstance(pt, dict) and dstr(pt.get("trade_date")) == td:
                api_h = pt.get("height")
                leader = pt.get("leader_stock") if isinstance(pt.get("leader_stock"), dict) else {}
                api_leader = leader.get("ts_code")
                break
        db_h = con.execute(
            "SELECT height, leader_ts_code FROM fact_leader_height_daily WHERE trade_date=?",
            [td],
        ).fetchone()
        if api_h is None and db_h is None:
            warn(f"{td} leader 双方都无该日点")
        elif db_h is None:
            fail(f"{td} leader API height={api_h} 但库无行")
        elif api_h is None:
            warn(f"{td} leader 库有 height={db_h[0]} 但本次 API 序列无该日（接口窗口）")
        elif int(db_h[0]) != int(api_h) or (api_leader and db_h[1] != api_leader):
            fail(f"{td} leader db=({db_h[0]},{db_h[1]}) api=({api_h},{api_leader})")
        else:
            ok(f"{td} leader height={db_h[0]} {db_h[1]}")

        auc = api_get("/data/auction/dashboard", {"trade_date": td})
        api_auc_n = 0
        for panel in auc.get("panels") or []:
            if isinstance(panel, dict):
                api_auc_n += len(panel.get("stocks") or [])
        db_auc_n = con.execute(
            "SELECT COUNT(*) FROM fact_auction_stock_daily WHERE trade_date=?",
            [td],
        ).fetchone()[0]
        if (api_auc_n == 0) != (db_auc_n == 0) or (api_auc_n and api_auc_n != db_auc_n):
            fail(f"{td} auction 行数 db={db_auc_n} api={api_auc_n}")
        else:
            ok(f"{td} auction {db_auc_n} 行")

        pool = api_get("/regulation/pool", {"trade_date": td})
        api_pool = []
        for item in pool.get("items") or []:
            if isinstance(item, dict) and item.get("ts_code"):
                api_pool.append(str(item["ts_code"]).strip())
        db_pool = [
            r[0]
            for r in con.execute(
                """
                SELECT stock_ts_code FROM fact_regulation_pool_daily
                WHERE effective_date=? AND pool_status='safe' ORDER BY 1
                """,
                [td],
            ).fetchall()
        ]
        if sorted(api_pool) != sorted(db_pool):
            only_api = set(api_pool) - set(db_pool)
            only_db = set(db_pool) - set(api_pool)
            if only_db or len(only_api) > 5:
                fail(f"{td} reg_pool 差集 api-db={sorted(only_api)[:8]} db-api={sorted(only_db)[:8]}")
            else:
                warn(f"{td} reg_pool 仅 API 多 {len(only_api)}（可能 waiting）")
        else:
            ok(f"{td} reg_pool {len(db_pool)} 只")


def main() -> int:
    print(f"DB={DB}")
    con = duckdb.connect(DB, read_only=True)
    try:
        structural(con)
        api_spot(con)
    finally:
        con.close()
    print("\n=== 汇总 ===")
    print(f"FAIL {len(FAILS)}  WARN {len(WARNS)}")
    for m in FAILS:
        print(f"  - {m}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
