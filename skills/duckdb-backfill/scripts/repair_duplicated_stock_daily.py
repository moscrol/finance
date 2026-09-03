#!/usr/bin/env python3
"""定点修复 fact_stock_daily 被「快照补历史日」污染的整分区。

事故（2026-08-27 取证）：
- 2026-07-20 分区在 07-22 00:36 被 `sync-stock-daily-snapshot` 补写，快照当时装的是
  07-21 收盘数据 → 整分区 5526/5526 行与 07-21 同值（真 07-20 数据丢失）。
- 2026-08-06 分区在 08-09 23:05 被同一方式补写，周末快照里是 08-07（周五）数据 →
  整分区 5534/5534 行与 08-07 同值（真 08-06 数据丢失；例：立新能源真 08-06 跌停
  -9.9%，被覆盖成 +7.96%，方向都反了）。
- 根因：东财快照只反映「最近一个交易日」，`sync_eastmoney_stock_snapshot.py` 的
  docstring（14-15 行）写明了这一点但没有闸门——把快照写到历史 trade_date 上
  行数全对、覆盖率审计全绿，只有相邻日整分区 diff 抓得到。

用法（顺序执行，写库前必须确认写窗口 + 四臂实验已收尾）：
    # 1) 只读扫描：找出所有「相邻日整分区复制」对
    python3 skills/duckdb-backfill/scripts/repair_duplicated_stock_daily.py --scan

    # 2) dry-run（默认）：mootdx 抓真值 → 与 fact_sector_stock_daily 交叉验证 → 只报告
    #    先用 --codes 抽样跑通，再全量 dry-run
    python3 ... --dates 2026-07-20,2026-08-06 --codes 001258,600519,002102
    python3 ... --dates 2026-07-20,2026-08-06

    # 3) 应用（单事务 upsert + 事后指纹核验）
    python3 ... --dates 2026-07-20,2026-08-06 --apply

依赖：mootdx（`pip install mootdx`；.venv-workbench 默认未装，装到临时 venv 亦可，
脚本只经 market_feature_store.db 解析库路径，环境不影响写入语义）。
交叉验证源：本库 fact_sector_stock_daily（fupanhui 管线，两次事故均未被污染）。
"""
from __future__ import annotations

import argparse
from datetime import datetime
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from market_feature_store import db  # noqa: E402
from market_feature_store.sync import sync_mootdx_stock_daily as m  # noqa: E402

SCAN_SQL = """
WITH f AS (
  SELECT trade_date, COUNT(*) AS n,
         SUM(hash(stock_name, close, pct_chg, amount, pre_close)) AS fp
  FROM fact_stock_daily GROUP BY trade_date
)
SELECT a.trade_date AS d1, b.trade_date AS d2, a.n
FROM f a JOIN f b
  ON b.trade_date = (SELECT MIN(trade_date) FROM f WHERE trade_date > a.trade_date)
WHERE a.fp = b.fp AND a.n = b.n
ORDER BY a.trade_date
"""

# 交叉验证容差：两源都是当日收盘口径，价差应为 0；留 1 分钱防浮点/复权尾差。
PRICE_TOL = 0.011
PCT_TOL = 0.5  # fupanhui 与「相邻前复权收盘推算」的涨跌幅口径差，实测 <0.1，留余量


def cmd_scan() -> int:
    con = db.connect(read_only=True)
    try:
        rows = con.execute(SCAN_SQL).fetchall()
    finally:
        con.close()
    if not rows:
        print("未发现相邻日整分区复制。")
        return 0
    print("相邻日整分区复制（前一日疑似被后一日快照覆盖，需回补前一日）：")
    for d1, d2, n in rows:
        print(f"  {d1} == {d2}  ({n} 行)")
    return 1


def fetch_true_rows(dates: list[str], codes: list[str] | None, offset: int,
                    timeout: int) -> tuple[list[tuple], list[tuple[str, str]]]:
    """mootdx 逐只抓取，返回 (目标日期行, 失败清单)。行结构与 m.COLS 一致。"""
    from mootdx.quotes import Quotes

    client = Quotes.factory(market="std")
    universe = m.get_universe(client)
    if codes:
        wanted = set(codes)
        universe = [(c, n) for c, n in universe if c in wanted]
    start = min(dates)
    now = datetime.now()
    targets = set(dates)
    rows: list[tuple] = []
    failures: list[tuple[str, str]] = []
    for seen, (code, name) in enumerate(universe, start=1):
        try:
            df = m._fetch_bars(client, code, offset, qfq=False, timeout=timeout)
        except Exception as e:  # noqa: BLE001 — 失败记账后继续，不卡整批
            failures.append((code, type(e).__name__))
            continue
        if df is None or len(df) == 0:
            failures.append((code, "empty"))
            continue
        recs = m._build_rows(df, code, name, start, now, "mootdx")
        rows.extend(r for r in recs if r[0] in targets)
        if seen % 500 == 0:
            print(f"  [{seen}/{len(universe)}] 已取 {len(rows)} 行 失败 {len(failures)}",
                  file=sys.stderr, flush=True)
    return rows, failures


def cross_validate(con, rows: list[tuple]) -> dict:
    """新行 vs fact_sector_stock_daily（fupanhui 源）对账。"""
    import pandas as pd

    df = pd.DataFrame(rows, columns=m.COLS)
    con.register("_repair_df", df)
    try:
        summary = con.execute(f"""
        WITH ref AS (
          SELECT trade_date, stock_ts_code,
                 ANY_VALUE(price) AS ref_price, ANY_VALUE(pct_chg) AS ref_pct
          FROM fact_sector_stock_daily
          WHERE trade_date IN (SELECT DISTINCT trade_date::DATE FROM _repair_df)
          GROUP BY 1, 2
        ),
        joined AS (
          SELECT r.trade_date::DATE AS d, r.stock_ts_code, r.close, r.pct_chg,
                 ref.ref_price, ref.ref_pct
          FROM _repair_df r LEFT JOIN ref
            ON ref.trade_date = r.trade_date::DATE
           AND ref.stock_ts_code = r.stock_ts_code
        )
        SELECT d, COUNT(*) AS new_rows,
               COUNT(ref_price) AS matched,
               SUM(CASE WHEN ref_price IS NOT NULL
                         AND ABS(close - ref_price) > {PRICE_TOL} THEN 1 ELSE 0 END) AS price_mismatch,
               SUM(CASE WHEN ref_pct IS NOT NULL
                         AND ABS(pct_chg - ref_pct) > {PCT_TOL} THEN 1 ELSE 0 END) AS pct_mismatch
        FROM joined GROUP BY d ORDER BY d
        """).fetchall()
    finally:
        con.unregister("_repair_df")
    return {str(d): {"new_rows": n, "matched": mt, "price_mismatch": pm, "pct_mismatch": qm}
            for d, n, mt, pm, qm in summary}


def cmd_repair(dates: list[str], codes: list[str] | None, offset: int,
               timeout: int, apply: bool) -> int:
    print(f"目标日期: {dates}  模式: {'APPLY' if apply else 'dry-run'}")
    rows, failures = fetch_true_rows(dates, codes, offset, timeout)
    per_date = {d: sum(1 for r in rows if r[0] == d) for d in dates}
    print(f"mootdx 取得 {len(rows)} 行（按日 {per_date}），失败 {len(failures)} 只")
    if not rows:
        print("无可写行，退出。")
        return 2

    con = db.connect(read_only=not apply)
    try:
        for d in dates:
            cur = con.execute(
                "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?", [d]
            ).fetchone()[0]
            print(f"  库内 {d} 现有 {cur} 行；本次将覆盖 {per_date.get(d, 0)} 行"
                  f"（其余 {max(cur - per_date.get(d, 0), 0)} 行 mootdx 未覆盖，保持原值并需在报告标注）")
        checks = cross_validate(con, rows)
        bad = 0
        for d, c in checks.items():
            print(f"  交叉验证 {d}: 新行 {c['new_rows']}，fupanhui 可对账 {c['matched']}，"
                  f"价差超容差 {c['price_mismatch']}，涨跌幅超容差 {c['pct_mismatch']}")
            bad += c["price_mismatch"]
        if bad > max(3, len(rows) // 1000):
            print("交叉验证失败行过多，拒绝写入。先人工核对两源口径。")
            return 3
        if not apply:
            print("dry-run 结束（未写库）。确认后加 --apply。")
            return 0

        import pandas as pd
        _buf_df = pd.DataFrame(rows, columns=m.COLS)  # noqa: F841
        con.register("_buf_df", _buf_df)
        try:
            con.execute("BEGIN")
            con.execute(m.BULK_UPSERT_SQL)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.unregister("_buf_df")
        remaining = con.execute(SCAN_SQL).fetchall()
        dup_left = [str(r[0]) for r in remaining]
        print(f"已写入。事后扫描：剩余整分区复制对 = {dup_left or '无'}")
        return 0 if not any(d in dup_left for d in dates) else 4
    finally:
        con.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan", action="store_true", help="只读扫描相邻日整分区复制")
    p.add_argument("--dates", default="", help="逗号分隔的待修复 trade_date")
    p.add_argument("--codes", default="", help="逗号分隔 6 位代码，抽样 dry-run 用")
    p.add_argument("--offset", type=int, default=80, help="mootdx 每只拉的日线根数")
    p.add_argument("--timeout", type=int, default=8, help="单只 bars 超时秒")
    p.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    args = p.parse_args()
    if args.scan:
        return cmd_scan()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    if not dates:
        p.error("需要 --scan 或 --dates")
    codes = [c.strip() for c in args.codes.split(",") if c.strip()] or None
    return cmd_repair(dates, codes, args.offset, args.timeout, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
