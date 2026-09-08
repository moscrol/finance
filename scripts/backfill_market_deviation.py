#!/usr/bin/env python3
"""回填 `fact_market_daily` 的周均线与偏离度，并补上一直缺失的来源标记。

背景（2026-09-05 实测）
----------------------
`sh_deviation_pct` 只有 221/413 天有值，缺的不是零星的天，是**一整段**：
2024-12 ~ 2025-09 全空（201 天），2025-10 起满覆盖。这一列是 2025 年 10 月
才开始采的，之前从来没有过值。

口径已经验明，不是猜的。拿 221 天真值比对八个候选：

    日 MA5          MAE   3.70 点（0.070%）   ← 就是它
    日 MA10         MAE  21.74
    日 MA20         MAE  49.37
    周 MA55         MAE 271.54（6.377%）      ← 不是 55 周均线
    日 MA275(≈55周) MAE 242.71

「周均线」指的是**一周的均线 = 5 个交易日**。公式也验过：
`偏离度 == (收盘 / 周均线 − 1) × 100`，221 天 MAE 0.0258。

残差 3.70 点不是零，因为 fupanhui 用它自己的指数序列，我们用
`akshare:stock_zh_index_daily:sh000001`。量级 0.07%。

为什么必须同时加来源列
--------------------
`sync_fupanhui_market_deviation.py` 现在**算出了来源却从不写库**：成功抓到
tooltip 时置 `data["source"]="tooltip"`，失败回退时 `_compute_deviation_fallback`
置 `"ma_recompute"`，而那条 UPDATE 只写 `sh_week_ma / sh_deviation_pct /
updated_at`——来源被返回给调用方然后丢掉。

所以**现存 221 天里哪些是抓来的、哪些已经是复算的，现在就分不出来**。
只有写入层知道这个值，它却扔了。不补这一列，本次回填只是把已有的盲区扩大。

现存行一律标 `unknown_preexisting`，不标 `tooltip`——我们证不了。
（线索：221 天里有 41 天与本地 MA5 完全相同(±0.01)，疑似当时就走了复算兜底。
但这是推断不是事实，不写进数据。）

为什么这 0.07% 值得在意
--------------------
词表里 +1.5 / −2.5 是**指数阶段判定**的两条线，而实测触到 +1.5 的只有 9 天、
跌破 −2.5 的只有 4 天——都是罕见事件。一个 0.07% 的源差异在阈值附近可能多算
或少算一天，所以来源必须可分辨，让下游自己决定要不要混用。

用法::

    python3 scripts/backfill_market_deviation.py            # dry-run（默认）
    python3 scripts/backfill_market_deviation.py --apply    # 真写
    python3 scripts/backfill_market_deviation.py --verify   # 只核对，不写

只补 `sh_deviation_pct IS NULL` 的行，**不覆盖任何已有值**。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_DB = "db/market_feature_store.duckdb"
MA_WINDOW = 5  # 「周均线」= 一周 = 5 个交易日，见模块注释的口径验证
SOURCE_BACKFILL = "ma5_recompute_backfill"
SOURCE_UNKNOWN = "unknown_preexisting"


def _ensure_source_column(con: Any) -> bool:
    """加 `sh_week_ma_source`。已存在则不动。返回是否新建。"""
    cols = {
        r[0]
        for r in con.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='main' AND table_name='fact_market_daily'
            """
        ).fetchall()
    }
    if "sh_week_ma_source" in cols:
        return False
    con.execute("ALTER TABLE fact_market_daily ADD COLUMN sh_week_ma_source VARCHAR")
    return True


def compute_backfill(con: Any) -> list[dict[str, Any]]:
    """算出待补的行。纯计算，不写库——dry-run 和 apply 走同一条路径。"""
    rows = con.execute(
        """
        SELECT CAST(trade_date AS DATE) AS d, sh_index_close, sh_week_ma, sh_deviation_pct
        FROM fact_market_daily ORDER BY trade_date
        """
    ).fetchall()
    closes = [r[1] for r in rows]
    out: list[dict[str, Any]] = []
    for i, (d, close, ma, dev) in enumerate(rows):
        if dev is not None:
            continue  # 已有值，一律不覆盖
        if close is None or i < MA_WINDOW - 1:
            continue  # 收盘缺失、或历史不够一个窗口 → 不补，留 NULL
        window = closes[i - MA_WINDOW + 1 : i + 1]
        if any(c is None for c in window):
            continue
        new_ma = sum(float(c) for c in window) / MA_WINDOW
        if not new_ma:
            continue
        out.append(
            {
                "trade_date": str(d),
                "sh_week_ma": round(new_ma, 2),
                "sh_deviation_pct": round((float(close) / new_ma - 1) * 100, 2),
                "existing_ma": ma,
            }
        )
    return out


def verify(con: Any) -> dict[str, Any]:
    """核对：与本地 MA5 的一致性、按来源的覆盖分布、两条阈值线上的天数。"""
    has_source = bool(
        con.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='main' AND table_name='fact_market_daily'
              AND column_name='sh_week_ma_source'
            """
        ).fetchone()
    )
    src_expr = "COALESCE(sh_week_ma_source, '(未标)')" if has_source else "'(无来源列)'"
    rows = con.execute(
        f"""
        SELECT CAST(trade_date AS DATE), sh_index_close, sh_week_ma, sh_deviation_pct, {src_expr}
        FROM fact_market_daily ORDER BY trade_date
        """  # noqa: S608 - src_expr 是本函数内的两个常量之一，不接受外部输入
    ).fetchall()
    by_source: dict[str, int] = {}
    formula_bad = 0
    for _d, close, ma, dev, src in rows:
        if dev is None:
            by_source["(空)"] = by_source.get("(空)", 0) + 1
            continue
        by_source[src] = by_source.get(src, 0) + 1
        if close and ma and abs((float(close) / float(ma) - 1) * 100 - float(dev)) > 0.05:
            formula_bad += 1
    total = len(rows)
    filled = sum(v for k, v in by_source.items() if k != "(空)")
    hot = con.execute(
        "SELECT COUNT(*) FILTER (WHERE sh_deviation_pct >= 1.5), "
        "COUNT(*) FILTER (WHERE sh_deviation_pct <= -2.5) FROM fact_market_daily"
    ).fetchone()
    return {
        "total_days": total,
        "filled": filled,
        "fill_rate": round(filled / total, 4) if total else 0.0,
        "by_source": dict(sorted(by_source.items())),
        "formula_mismatch_over_0.05pct": formula_bad,
        "days_ge_1.5": hot[0],
        "days_le_-2.5": hot[1],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB))
    ap.add_argument("--apply", action="store_true", help="真写库（缺省只 dry-run）")
    ap.add_argument("--verify", action="store_true", help="只核对现状，不算不写")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    import duckdb

    db = Path(args.db).expanduser()
    if not db.exists():
        raise SystemExit(f"数据库不存在：{db}（不自动创建）")

    # dry-run 与 verify 一律只读：默认不碰库，要写必须显式 --apply。
    con = duckdb.connect(str(db), read_only=True)
    try:
        if args.verify:
            print(json.dumps(verify(con), ensure_ascii=False, indent=2))
            return 0
        pending = compute_backfill(con)
    finally:
        con.close()

    if not args.apply:
        print(f"[dry-run] 待补 {len(pending)} 天，**不覆盖任何已有值**")
        if pending:
            print(f"  区间 {pending[0]['trade_date']} ~ {pending[-1]['trade_date']}")
            print(f"  {'日期':<12}{'周均线':>10}{'偏离度%':>9}")
            for r in pending[:5]:
                print(f"  {r['trade_date']:<12}{r['sh_week_ma']:>10}{r['sh_deviation_pct']:>9}")
            print(f"  …… 共 {len(pending)} 行。加 --apply 才会写库。")
        return 0

    con = duckdb.connect(str(db), read_only=False)
    try:
        created = _ensure_source_column(con)
        # 现存行标 unknown：证不了它们是 tooltip 还是当时就走了复算兜底。
        marked = con.execute(
            "UPDATE fact_market_daily SET sh_week_ma_source = ? "
            "WHERE sh_deviation_pct IS NOT NULL AND sh_week_ma_source IS NULL",
            [SOURCE_UNKNOWN],
        ).fetchall()
        n_marked = con.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE sh_week_ma_source = ?", [SOURCE_UNKNOWN]
        ).fetchone()[0]
        for r in pending:
            con.execute(
                """
                UPDATE fact_market_daily
                SET sh_week_ma = ?, sh_deviation_pct = ?, sh_week_ma_source = ?
                WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
                  AND sh_deviation_pct IS NULL
                """,
                [r["sh_week_ma"], r["sh_deviation_pct"], SOURCE_BACKFILL, r["trade_date"]],
            )
        report = verify(con)
    finally:
        con.close()
    print(f"[apply] 新建来源列={created}  标记存量={n_marked}  回填={len(pending)}  (marked={marked!r})")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
