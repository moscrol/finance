#!/usr/bin/env python3
"""百分数字段的量纲核验：拿同日原始价格反算，判这一列存的是 3.25（百分数）还是 0.0325（小数）。

背景（2026-10-01 审查第 3 条）：只看一列的最大最小值定不了量纲，会差一百倍。要三样一起看——
供应商定义、采集时有没有换算、同日原始值能不能对上。本仓里前两样的现状：

- 供应商定义：复盘会（fupanhui）2026-09-07 起停采，仓里没有这几个字段的口径文档；
- 采集换算：``sync_fupanhui_public_assets._num`` 只去掉字符串里的 ``%`` 和千分位，不乘不除；
  ``sync_hithink_dragon_auction`` 原样落库。所以库里是什么，就是供应商给的是什么。

剩下能定案的只有第三样，本脚本做的就是它。每项都是「同一只票、同一天」的一对数：

1. ``fact_auction_stock_daily.auction_pct``（复盘会竞价涨幅）↔ 同日 ``fact_stock_daily``
   的 ``(open / pre_close − 1) × 100``：A 股开盘价就是集合竞价成交价；
2. 同表 ``pct_chg`` ↔ ``(close / pre_close − 1) × 100``（同一供应商、同一行的对照列）；
3. ``fact_auction_hithink.auction_pct``（同花顺竞价）↔ **同一行**的
   ``(auction_price / pre_close_price − 1) × 100``；
4. ``fact_global_stock_daily.pct_chg_5d``（海外个股 5 日涨幅）↔ 同一只票按
   ``source_trade_date`` 往前第 5 行收盘价反算；
5. 同表 ``pct_chg`` ↔ 往前第 1 行收盘价反算。

判定看比值 ``字段值 / 反算百分数`` 的中位数与集中度：≈1 → 百分数（标签该加 %）；≈0.01 → 小数
（不加 %，读数时 ×100）；其它 → 定不了，不改标签。反算值绝对值 < 0.5 的配对不进比值（分母太小，
四舍五入就能把比值带飞）。只读：用 read_only 连接，不写库；生产库有写者时请对 APFS 克隆副本跑
（``--db`` 指过去）。

用法::

    python scripts/check_percent_units.py                 # 默认生产库路径（market_feature_store.db）
    python scripts/check_percent_units.py --db /path/to/clone.duckdb --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import duckdb

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MIN_ABS_COMPUTED = 0.5
PERCENT_BAND = (0.95, 1.05)
FRACTION_BAND = (0.0095, 0.0105)
MIN_PAIRS = 20
DECISIVE_SHARE = 0.8

CHECKS: tuple[dict[str, str], ...] = (
    {
        "name": "复盘会竞价涨幅 auction_pct",
        "label": "finance_query auction_stock_daily「竞价涨幅」",
        "tables": "fact_auction_stock_daily,fact_stock_daily",
        "sql": """
            SELECT a.auction_pct, (s.open / s.pre_close - 1) * 100
            FROM fact_auction_stock_daily a
            JOIN fact_stock_daily s ON s.trade_date = a.trade_date AND s.stock_ts_code = a.stock_ts_code
            WHERE a.auction_pct IS NOT NULL AND s.open > 0 AND s.pre_close > 0
        """,
    },
    {
        "name": "复盘会竞价表 pct_chg（对照列）",
        "label": "同表收盘涨跌",
        "tables": "fact_auction_stock_daily,fact_stock_daily",
        "sql": """
            SELECT a.pct_chg, (s.close / s.pre_close - 1) * 100
            FROM fact_auction_stock_daily a
            JOIN fact_stock_daily s ON s.trade_date = a.trade_date AND s.stock_ts_code = a.stock_ts_code
            WHERE a.pct_chg IS NOT NULL AND s.close > 0 AND s.pre_close > 0
        """,
    },
    {
        "name": "同花顺竞价 auction_pct",
        "label": "finance_query auction_hithink「竞价涨跌幅」",
        "tables": "fact_auction_hithink",
        "sql": """
            SELECT auction_pct, (auction_price / pre_close_price - 1) * 100
            FROM fact_auction_hithink
            WHERE auction_pct IS NOT NULL AND auction_price > 0 AND pre_close_price > 0
        """,
    },
    {
        "name": "海外个股 pct_chg_5d",
        "label": "finance_query global_stock_daily「5日涨幅」",
        "tables": "fact_global_stock_daily",
        "sql": """
            SELECT pct_chg_5d, (close / prev5 - 1) * 100 FROM (
                SELECT pct_chg_5d, close,
                       LAG(close, 5) OVER (PARTITION BY ts_code ORDER BY source_trade_date) AS prev5
                FROM (SELECT DISTINCT ts_code, source_trade_date, close, pct_chg_5d
                      FROM fact_global_stock_daily WHERE source_trade_date IS NOT NULL AND close > 0)
            ) WHERE pct_chg_5d IS NOT NULL AND prev5 > 0
        """,
    },
    {
        "name": "海外个股 pct_chg（对照列）",
        "label": "同表 1 日涨跌",
        "tables": "fact_global_stock_daily",
        "sql": """
            SELECT pct_chg, (close / prev1 - 1) * 100 FROM (
                SELECT pct_chg, close,
                       LAG(close, 1) OVER (PARTITION BY ts_code ORDER BY source_trade_date) AS prev1
                FROM (SELECT DISTINCT ts_code, source_trade_date, close, pct_chg
                      FROM fact_global_stock_daily WHERE source_trade_date IS NOT NULL AND close > 0)
            ) WHERE pct_chg IS NOT NULL AND prev1 > 0
        """,
    },
)


def _share(ratios: list[float], band: tuple[float, float]) -> float:
    return sum(band[0] <= r <= band[1] for r in ratios) / len(ratios) if ratios else 0.0


def judge_pairs(pairs: list[tuple[float, float]]) -> dict[str, Any]:
    """一组 (字段值, 反算百分数) → 判定。比值只取反算绝对值 ≥ 0.5 的配对。"""

    ratios = [
        float(field) / float(computed)
        for field, computed in pairs
        if field is not None and computed is not None and abs(float(computed)) >= MIN_ABS_COMPUTED
    ]
    result: dict[str, Any] = {"pairs": len(pairs), "ratio_pairs": len(ratios)}
    if len(ratios) < MIN_PAIRS:
        result.update(verdict="insufficient", median_ratio=None, percent_share=None, fraction_share=None)
        return result
    median = statistics.median(ratios)
    percent_share, fraction_share = _share(ratios, PERCENT_BAND), _share(ratios, FRACTION_BAND)
    if percent_share >= DECISIVE_SHARE:
        verdict = "percent"
    elif fraction_share >= DECISIVE_SHARE:
        verdict = "fraction"
    else:
        verdict = "unclear"
    result.update(
        verdict=verdict,
        median_ratio=round(median, 6),
        percent_share=round(percent_share, 4),
        fraction_share=round(fraction_share, 4),
    )
    return result


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}


def run_checks(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    present = _tables(con)
    results = []
    for check in CHECKS:
        missing = [t for t in check["tables"].split(",") if t not in present]
        row: dict[str, Any] = {"name": check["name"], "label": check["label"]}
        if missing:
            row.update(verdict="table_missing", missing=missing)
        else:
            row.update(judge_pairs(con.execute(check["sql"]).fetchall()))
        results.append(row)
    return results


_ADVICE = {
    "percent": "存的是百分数：标签应写成「…%」",
    "fraction": "存的是小数：标签不加 %，读数 ×100 才是百分数",
    "unclear": "比值不集中：定不了，标签先别改，查这列的写入史",
    "insufficient": f"可比配对不足 {MIN_PAIRS} 对：定不了",
    "table_missing": "表不存在：跳过",
}


def render(results: list[dict[str, Any]], db: str) -> str:
    lines = [f"# 百分数字段量纲核验（{db}，只读）", ""]
    lines.append("| 字段 | 配对 | 进比值 | 比值中位数 | ≈1 占比 | ≈0.01 占比 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in results:
        if row["verdict"] == "table_missing":
            lines.append(f"| {row['name']} | — | — | — | — | — | 表不存在：{'、'.join(row['missing'])} |")
            continue
        def fmt(value: Any) -> str:
            return "—" if value is None else str(value)
        lines.append(
            f"| {row['name']} | {row['pairs']} | {row['ratio_pairs']} | {fmt(row['median_ratio'])} | "
            f"{fmt(row['percent_share'])} | {fmt(row['fraction_share'])} | {row['verdict']} |"
        )
    lines.append("")
    for row in results:
        lines.append(f"- {row['name']}（{row['label']}）：{_ADVICE[row['verdict']]}")
    lines.append("")
    lines.append(
        "- 读法：比值 = 字段值 / 同日原值反算的百分数。≈1 是百分数，≈0.01 是小数；"
        f"判定要求 ≥{int(DECISIVE_SHARE * 100)}% 的配对落在 ±5% 带内。"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=None, help="DuckDB 路径；默认 market_feature_store.db.DB_PATH")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.db:
        db_path = Path(args.db).expanduser()
    else:
        from market_feature_store.db import DB_PATH

        db_path = Path(DB_PATH)
    if not db_path.is_file():
        print(f"库不存在：{db_path}", file=sys.stderr)
        return 2
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        print(f"只读打开失败（多半有活跃写者）：{exc}\n请先克隆一份再用 --db 指过去。", file=sys.stderr)
        return 2
    try:
        results = run_checks(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps({"db": str(db_path), "results": results}, ensure_ascii=False, indent=2))
    else:
        print(render(results, str(db_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
