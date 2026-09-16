#!/usr/bin/env python3
"""补 `fact_stock_daily.pct_chg / pre_close` 的「首根 bar 洞」（工单 #40）。

`sync_mootdx_stock_daily._build_rows` 用**同一次抓取窗口内的上一根 bar** 算 `pre_close / pct_chg`，
窗口第一根没有上一根 → 两列留 NULL。2026-06-24 那次回补对一段 SZ 代码（000001–002716）恰好把
2025-09-19（65 只是 09-18）落成了窗口首根，于是当日 `pct_chg` 只有 79%——09-08 填充率闸首次量出。

本脚本只做一件事：对 `pct_chg IS NULL AND pre_close IS NULL` 的行，用**同表上一交易日的 close**
按同一条公式补齐：

    pre_close = round(prev_close, 3)
    pct_chg   = round((close / pre_close - 1) * 100, 2)

实测（2025-09-19 已有的 4064 行）：`pct_chg == round((close/pre_close-1)*100, 2)` 4064/4064、
`pre_close == 上一交易日 close` 4063/4063——这不是另一种口径，是把管线自己的规则补到它漏掉的那几行。
`source` 追加 `+derived:close_ratio`，下游能识别这些行是补的。

不做的事：不重抓（`sync-stock-daily --refresh` 会把区间内全部行的 `updated_at` 推到今天，
是 #27 点名的「重发布冲短河」）；上一交易日行不存在、close 为 0/NULL、或与本日相隔 > 7 个自然日
（长停牌，除权 / 复牌口径不明）的行**留 NULL 并列出**，不猜。

**物理约束（2026-09-08 验收 session 量出的缺陷后加）**：派生值不得越过所属板块的涨跌停档
（主板 10% / 创业板・科创板 20% / 北交所 30%），越过即多半是除权日（潍柴重机 2025-09-19 close
48.21 → 32.43 = 10 转 5，派生 −32.73% 物理上不可能）——这类行**不派生、留 NULL 并列出**。
容差取 1.2 倍档位：ST 5% 与 10% 的归属在库里判不准，涨跌停价的 tick 取整也会让真实封板读成 10.12%，
用 1.2 倍只拦「不可能」的值，不拦「贴着档位」的值。``--revert-violations`` 把已写入的越界派生行撤回
NULL（``source`` 去掉派生后缀）。抽样验收对除权天然零覆盖（核心 50 / 涨停股都按活跃度选），
所以这条断言是全量的，成本几乎为零。

用法：
    python3 scripts/backfill_stock_daily_pct_from_prev_close.py --dates 2025-09-18 2025-09-19 --dry-run
    python3 scripts/backfill_stock_daily_pct_from_prev_close.py --dates 2025-09-18 2025-09-19
    python3 scripts/backfill_stock_daily_pct_from_prev_close.py --dates 2025-09-19 --revert-violations [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from market_feature_store.db import DB_PATH, is_lock_conflict  # noqa: E402

MAX_GAP_DAYS = 7
SOURCE_SUFFIX = "+derived:close_ratio"
# 越界容差：1.2 × 板块档位。只拦物理上不可能的值（除权 / 数据错），不拦贴着涨跌停的真封板。
LIMIT_TOLERANCE = 1.2


def board_limit_pct(code: str) -> float:
    """所属板块的涨跌停档（%）。ST 的 5% 在库里判不准（名字里的 ST 有时不在 5% 规则下），按所在板块给。"""
    c = str(code)
    if c.endswith(".BJ"):
        return 30.0
    if c.startswith(("300", "301", "688", "689")):
        return 20.0
    return 10.0


def limit_violation(code: str, pct: float) -> bool:
    return abs(float(pct)) > board_limit_pct(code) * LIMIT_TOLERANCE


CANDIDATES_SQL = """
WITH holes AS (
    SELECT trade_date, stock_ts_code, close, source
    FROM fact_stock_daily
    WHERE trade_date = ? AND pct_chg IS NULL AND pre_close IS NULL AND close IS NOT NULL AND close > 0
),
prev AS (
    SELECT h.stock_ts_code,
           MAX(p.trade_date) AS prev_date
    FROM holes h
    JOIN fact_stock_daily p
      ON p.stock_ts_code = h.stock_ts_code AND p.trade_date < h.trade_date AND p.close IS NOT NULL AND p.close > 0
    GROUP BY h.stock_ts_code
)
SELECT h.trade_date, h.stock_ts_code, h.close, h.source, pr.prev_date, p.close AS prev_close,
       DATEDIFF('day', pr.prev_date, h.trade_date) AS gap_days
FROM holes h
LEFT JOIN prev pr ON pr.stock_ts_code = h.stock_ts_code
LEFT JOIN fact_stock_daily p ON p.stock_ts_code = h.stock_ts_code AND p.trade_date = pr.prev_date
ORDER BY h.stock_ts_code
"""

UPDATE_SQL = """
UPDATE fact_stock_daily
SET pre_close = ?, pct_chg = ?, source = ?, updated_at = ?
WHERE trade_date = ? AND stock_ts_code = ? AND pct_chg IS NULL AND pre_close IS NULL
"""


def _connect(db_path: Path, *, read_only: bool, retries: int = 8) -> duckdb.DuckDBPyConnection:
    """8792 按请求开只读连接，写锁会间歇冲突；等一等再试，不放弃也不硬抢。"""
    last: Exception | None = None
    for _ in range(retries):
        try:
            return duckdb.connect(str(db_path), read_only=read_only)
        except duckdb.IOException as exc:
            if not is_lock_conflict(exc):
                raise
            last = exc
            time.sleep(2.5)
    raise SystemExit(f"拿不到 DuckDB 锁（{retries} 次）：{last}")


def plan(con: duckdb.DuckDBPyConnection, date: str) -> tuple[list[tuple], list[dict]]:
    """返回 (可补的行, 不补的行与原因)。"""
    rows = con.execute(CANDIDATES_SQL, [date]).fetchall()
    todo: list[tuple] = []
    skipped: list[dict] = []
    for trade_date, code, close, source, prev_date, prev_close, gap_days in rows:
        if prev_date is None or prev_close is None:
            skipped.append({"stock_ts_code": code, "reason": "no_prev_close"})
            continue
        if gap_days is not None and int(gap_days) > MAX_GAP_DAYS:
            skipped.append({"stock_ts_code": code, "reason": f"gap_days={gap_days}>{MAX_GAP_DAYS}", "prev_date": str(prev_date)})
            continue
        pre = round(float(prev_close), 3)
        pct = round((float(close) / pre - 1) * 100, 2)
        if limit_violation(code, pct):
            # 越过档位 = 物理上不可能的涨跌幅：多半是除权日（例：10 转 5 → 收盘直接掉三分之一）。
            # 库里没有除权表，算不出真值，就不给值——留 NULL 让下游看得见缺口。
            skipped.append({"stock_ts_code": code, "reason": f"limit_violation:possible_ex_rights pct={pct} > {board_limit_pct(code)}×{LIMIT_TOLERANCE}", "prev_date": str(prev_date), "prev_close": pre, "close": float(close)})
            continue
        new_source = str(source or "unknown")
        if SOURCE_SUFFIX not in new_source:
            new_source += SOURCE_SUFFIX
        todo.append((pre, pct, new_source, str(trade_date), code, str(prev_date)))
    return todo, skipped


REVERT_SCAN_SQL = """
SELECT trade_date, stock_ts_code, stock_name, pre_close, close, pct_chg, source
FROM fact_stock_daily
WHERE trade_date = ? AND source LIKE ? AND pct_chg IS NOT NULL
"""
REVERT_SQL = """
UPDATE fact_stock_daily
SET pre_close = NULL, pct_chg = NULL, source = ?, updated_at = ?
WHERE trade_date = ? AND stock_ts_code = ? AND source LIKE ?
"""


def plan_revert(con: duckdb.DuckDBPyConnection, date: str) -> list[dict]:
    """已写入的派生行里越过档位的那些：撤回 NULL 的计划。"""
    out: list[dict] = []
    for trade_date, code, name, pre, close, pct, source in con.execute(REVERT_SCAN_SQL, [date, f"%{SOURCE_SUFFIX}%"]).fetchall():
        if pct is not None and limit_violation(code, pct):
            out.append({
                "trade_date": str(trade_date), "stock_ts_code": code, "stock_name": (name or "").strip("\x00"),
                "pre_close": pre, "close": close, "pct_chg": pct,
                "restore_source": str(source).replace(SOURCE_SUFFIX, ""),
                "reason": f"limit_violation:possible_ex_rights (> {board_limit_pct(code)}×{LIMIT_TOLERANCE})",
            })
    return out


def fill_stats(con: duckdb.DuckDBPyConnection, date: str) -> dict:
    n, n_pct, n_pre = con.execute(
        "SELECT COUNT(*), COUNT(pct_chg), COUNT(pre_close) FROM fact_stock_daily WHERE trade_date = ?", [date]
    ).fetchone()
    return {"rows": n, "pct_chg": n_pct, "pre_close": n_pre, "pct_fill": round(100.0 * n_pct / n, 2) if n else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dates", nargs="+", required=True, help="交易日 YYYY-MM-DD，可多个")
    ap.add_argument("--db-path", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--revert-violations", action="store_true", help="把已写入的越界派生行撤回 NULL（除权日误派生的修正）")
    args = ap.parse_args(argv)

    db_path = Path(args.db_path).expanduser()
    report: dict = {"db_path": str(db_path), "dry_run": bool(args.dry_run), "dates": {}}

    if args.revert_violations:
        ro = _connect(db_path, read_only=True)
        try:
            plans_rv = {d: plan_revert(ro, d) for d in args.dates}
            for d in args.dates:
                report["dates"][d] = {"before": fill_stats(ro, d), "to_revert": plans_rv[d]}
        finally:
            ro.close()
        if not args.dry_run and any(plans_rv.values()):
            now = datetime.now()
            con = _connect(db_path, read_only=False)
            try:
                con.execute("BEGIN TRANSACTION")
                for d, items in plans_rv.items():
                    for it in items:
                        con.execute(REVERT_SQL, [it["restore_source"], now, it["trade_date"], it["stock_ts_code"], f"%{SOURCE_SUFFIX}%"])
                con.execute("COMMIT")
                for d in args.dates:
                    report["dates"][d]["after"] = fill_stats(con, d)
            except Exception:
                con.execute("ROLLBACK")
                raise
            finally:
                con.close()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            for d, info in report["dates"].items():
                print(f"{d}: 越界派生行 {len(info['to_revert'])} 条" + (f" → 已撤回，pct_chg 填充 {info['after']['pct_fill']}%" if "after" in info else ""))
                for it in info["to_revert"]:
                    print(f"    {it['stock_ts_code']} {it['stock_name']} pre={it['pre_close']} close={it['close']} pct={it['pct_chg']}  {it['reason']}")
        return 0

    ro = _connect(db_path, read_only=True)
    plans: dict[str, tuple[list[tuple], list[dict]]] = {}
    try:
        for d in args.dates:
            plans[d] = plan(ro, d)
            report["dates"][d] = {"before": fill_stats(ro, d), "to_fill": len(plans[d][0]), "skipped": plans[d][1]}
    finally:
        ro.close()

    if not args.dry_run:
        now = datetime.now()
        con = _connect(db_path, read_only=False)
        try:
            con.execute("BEGIN TRANSACTION")
            for d, (todo, _) in plans.items():
                for pre, pct, src, trade_date, code, _prev in todo:
                    con.execute(UPDATE_SQL, [pre, pct, src, now, trade_date, code])
            con.execute("COMMIT")
            for d in args.dates:
                report["dates"][d]["after"] = fill_stats(con, d)
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        for d, info in report["dates"].items():
            b = info["before"]
            line = f"{d}: 行 {b['rows']} · pct_chg 填充 {b['pct_fill']}% → 计划补 {info['to_fill']} 行，跳过 {len(info['skipped'])}"
            if "after" in info:
                line += f" → 补后 {info['after']['pct_fill']}%"
            print(line)
            for s in info["skipped"][:20]:
                print(f"    跳过 {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
