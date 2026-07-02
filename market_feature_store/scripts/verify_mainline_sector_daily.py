"""fact_mainline_sector_daily 最小验证脚本。

验证项:
  1. init_db 后表 fact_mainline_sector_daily 存在;
  2. 对指定交易日跑同步能写入数据 (sectors > 0);
  3. 重复跑一次, 行数不重复膨胀 (幂等);
  4. 查询 AI算力 / 半导体 / 有色金属 能看到对应板块和 cycle_status。

用法:
    python3 -m market_feature_store.scripts.verify_mainline_sector_daily [--trade-date 2026-06-30]

注意: 会真实调用复盘会公开 API 并写入本地 DuckDB (库文件已 .gitignore, 不入库)。
可用环境变量 MARKET_FEATURE_STORE_DB 指向样本库自测, 不污染生产库。
"""
from __future__ import annotations

import argparse
import sys

from ..db import connect, init_db, list_tables
from ..sync.sync_fupanhui_mainline_sector_daily import sync

TABLE = "fact_mainline_sector_daily"
SPOT_THEMES = ["AI算力", "半导体", "有色金属"]


def _count(con, trade_date: str) -> int:
    return con.execute(
        f"SELECT COUNT(*) FROM {TABLE} WHERE CAST(trade_date AS VARCHAR) = ?",
        [trade_date],
    ).fetchone()[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="验证 fact_mainline_sector_daily")
    ap.add_argument("--trade-date", default="2026-06-30", help="交易日 YYYY-MM-DD")
    args = ap.parse_args()
    td = args.trade_date
    ok = True

    # 1) 建表 + 表存在
    init_db()
    con = connect(read_only=True)
    try:
        tables = list_tables(con)
    finally:
        con.close()
    exists = TABLE in tables
    print(f"[1] 表存在: {exists}")
    ok = ok and exists

    # 2) 首次同步写入
    r1 = sync(td)
    print(f"[2] 首次同步 {td}: themes={r1['themes']} sectors={r1['sectors']} failures={len(r1['failures'])}")
    ok = ok and r1["sectors"] > 0

    con = connect(read_only=True)
    try:
        c1 = _count(con, td)
    finally:
        con.close()

    # 3) 重复同步幂等
    sync(td)
    con = connect(read_only=True)
    try:
        c2 = _count(con, td)
    finally:
        con.close()
    idempotent = c1 == c2
    status = "OK" if idempotent else "膨胀!"
    print(f"[3] 幂等: 第一次 {c1} 行, 第二次 {c2} 行 -> {status}")
    ok = ok and idempotent

    # 4) 抽查命名题材
    con = connect(read_only=True)
    try:
        for name in SPOT_THEMES:
            rows = con.execute(
                f"""
                SELECT sector_name, cycle_status, cycle_level, today_pct
                FROM {TABLE}
                WHERE CAST(trade_date AS VARCHAR) = ? AND theme_name = ?
                ORDER BY sort_no
                """,
                [td, name],
            ).fetchall()
            found = bool(rows)
            ok = ok and found
            detail = ", ".join(f"{r[0]}({r[1]})" for r in rows) or "(无)"
            print(f"[4] {name}: {len(rows)} 板块 -> {detail}")
    finally:
        con.close()

    print(f"\n结果: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
