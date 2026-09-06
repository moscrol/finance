#!/usr/bin/env python3
"""时间长河 PIT 完备性审计：这条河有多长是可 strict 重放的。

背景。`intelligence/eval/fidelity_replay.py:_pit_where` 用 ``updated_at < as_of + 1 day``
作严格 PIT 边界；缺列时整表返回 ``AND FALSE``。但 `market_feature_store/schema.sql:10`
把 ``updated_at`` 定义成「刷新时间」，各 sync 一律 ``ON CONFLICT DO UPDATE SET
updated_at = excluded.updated_at``——**重发布会把整段历史的时间戳推到今天**。
所以「盘面/题材/资金/个股/板块」各轨能不能 as-of 重放，不取决于交易日，取决于那批数据
最后一次被写是什么时候。本脚本把这件事量出来。

三个读数：

1. 逐表：strict 日 / 总日，以及 ``updated_at - trade_date`` 滞后分布；
2. 跨轨联立：同一天各轨都 strict 的交集——``slice(T, C)`` 真正能出
   ``pit_grade=strict`` 的日子就是这个交集，不是任何单表的读数；
3. 覆盖起点：strict 区间的首日，即「这条河的可重放段从哪天开始」。

用法::

    python3 scripts/river_pit_audit.py                 # 人读
    python3 scripts/river_pit_audit.py --json          # 收据

不改库，只读。数据库不存在时 fail closed（退出码 2），不自动创建。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_DB = "db/market_feature_store.duckdb"

# 轨 → 该轨的核心表。**轨名与顺序必须和 `intelligence/services/river.py:TRACKS` 一致**
# （六个维度由终局 §3 + F9 钦定）：同一份「六条轨是哪六条」存两处必漂，漂的时候没人知道。
# 一条轨多表时，第一张是骨干表——联立交集只用骨干，多算一张就是给交集加一道未必必要的门。
# 判断轨（checkpoints.jsonl）不在本库里，按 `gap` 处理，不放进交集分母。
TRACKS: dict[str, list[str]] = {
    "盘面 market": [
        "fact_sector_daily",  # 双红判据所在，且实测是全库最短的一条
        "fact_market_daily",
        "fact_theme_limit_heat_daily",
        "fact_stock_high_daily",
        "fact_limit_advance_daily",
    ],
    "题材 theme": ["fact_theme_limit_stock_daily", "fact_mainline_theme_daily"],
    "舆论 opinion": ["fact_research_report_catalog"],
    "资金 capital": ["fact_sector_stock_daily", "fact_theme_flow_daily", "fact_dragon_tiger_daily"],
    "个股 stock": ["fact_stock_daily", "fact_core_stock_daily"],
}

# 不是每张表都用 (trade_date, updated_at)。研报目录用 (report_date, created_at)，
# 而 created_at 恰恰是**全库唯一没被批量重写抹平**的记录时刻（实测：updated_at 去重
# 只剩 1 天，created_at 有 104 个不同日期）——写死列名会把这条轨误判成不可 PIT。
DATE_COL: dict[str, str] = {"fact_research_report_catalog": "report_date"}
RECORDED_COL: dict[str, str] = {"fact_research_report_catalog": "created_at"}

# 累计轨：读取面按 `date <= as_of` 取（覆盖密度是累计量，不是当日事件），
# 所以「那天有没有新增一条」和「那天能不能读出这条轨」是两回事。
# 把它塞进逐日交集会得到一个由审计口径造出来的 0——那不是数据的问题，是量法的问题。
CUMULATIVE: frozenset[str] = frozenset({"fact_research_report_catalog"})

BACKBONE = {track: tables[0] for track, tables in TRACKS.items()}
DAILY_BACKBONE = {t: tb for t, tb in BACKBONE.items() if tb not in CUMULATIVE}

LAG_BUCKETS = (
    ("strict (<=0d)", None, 0),
    ("1~7d", 1, 7),
    ("8~30d", 8, 30),
    ("31~180d", 31, 180),
    (">180d", 181, None),
)


def _connect(db_path: Path) -> Any:
    try:
        import duckdb
    except ImportError:  # pragma: no cover - 环境问题，不是逻辑问题
        print("需要 duckdb：用 .venv-workbench/bin/python 跑本脚本", file=sys.stderr)
        raise SystemExit(2)
    if not db_path.exists():
        print(f"数据库不存在：{db_path}（不自动创建）", file=sys.stderr)
        raise SystemExit(2)
    return duckdb.connect(str(db_path), read_only=True)


def _columns(con: Any, table: str) -> set[str]:
    """用 ``information_schema`` 而不是 ``PRAGMA table_info``。

    后者对 VIEW 静默返回空，而 ``fact_sector_daily`` / ``fact_sector_stock_daily``
    正是 VIEW——用 PRAGMA 会把「有这列」读成「没这列」，且不报错。
    """
    rows = con.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table],
    ).fetchall()
    return {str(r[0]) for r in rows}


def audit_table(con: Any, table: str) -> dict[str, Any]:
    date_col = DATE_COL.get(table, "trade_date")
    rec_col = RECORDED_COL.get(table, "updated_at")
    cols = _columns(con, table)
    if date_col not in cols:
        return {"table": table, "status": f"no_{date_col}"}
    if rec_col not in cols:
        # _pit_where 对没有记录时刻的表返回 AND FALSE：strict 下整表读不到任何行。
        return {"table": table, "status": f"no_{rec_col}", "strict_days": 0}

    rows = con.execute(
        f"""
        WITH d AS (
            SELECT CAST({date_col} AS DATE) AS td,
                   COUNT(*) AS n,
                   SUM(CASE WHEN {rec_col} IS NULL THEN 1 ELSE 0 END) AS n_null,
                   -- 按日期比较而不是时间戳：语义与 _pit_where 的
                   -- `rec < date + 1 day` 等价，但能同时吃下 TIMESTAMP 与带时区的
                   -- VARCHAR（研报目录的 created_at 就是后者），也与切片里
                   -- `recorded_at[:10] <= cutoff` 的口径一致。
                   SUM(CASE WHEN {rec_col} IS NOT NULL
                             AND CAST({rec_col} AS DATE) <= CAST({date_col} AS DATE)
                            THEN 1 ELSE 0 END) AS n_pit,
                   DATE_DIFF('day', CAST({date_col} AS DATE),
                             CAST(MIN({rec_col}) AS DATE)) AS lag_d
            FROM {table}
            GROUP BY 1
        )
        SELECT td, n, n_null, n_pit, lag_d FROM d ORDER BY td
        """  # noqa: S608 - 表名与列名都来自本文件内的白名单，不接受外部输入
    ).fetchall()
    if not rows:
        return {"table": table, "status": "empty", "strict_days": 0}

    strict_days = [str(r[0]) for r in rows if r[1] and r[3] == r[1]]
    lag_hist: dict[str, int] = {name: 0 for name, _, _ in LAG_BUCKETS}
    lag_hist["updated_at 为 NULL"] = 0
    for _td, _n, _n_null, _n_pit, lag in rows:
        if lag is None:
            lag_hist["updated_at 为 NULL"] += 1
            continue
        for name, lo, hi in LAG_BUCKETS:
            if (lo is None or lag >= lo) and (hi is None or lag <= hi):
                lag_hist[name] += 1
                break
    return {
        "table": table,
        "status": "ok",
        "rows": sum(r[1] for r in rows),
        "total_days": len(rows),
        "strict_days": len(strict_days),
        "strict_pct": round(len(strict_days) / len(rows) * 100, 1),
        "strict_from": strict_days[0] if strict_days else None,
        "strict_to": strict_days[-1] if strict_days else None,
        "span": [str(rows[0][0]), str(rows[-1][0])],
        "lag_hist": lag_hist,
        "_strict_set": strict_days,
    }


def run(db_path: Path) -> dict[str, Any]:
    con = _connect(db_path)
    try:
        per_table: dict[str, dict[str, Any]] = {}
        for tables in TRACKS.values():
            for table in tables:
                per_table[table] = audit_table(con, table)
    finally:
        con.close()

    # 联立：交集才是 slice(T, C) 能出 strict 的日子。任一轨为空 → 交集为空，如实报。
    # 只对逐日轨取交集，累计轨（舆论）单列——理由见 CUMULATIVE 的注释。
    backbone_sets: dict[str, set[str]] = {}
    for track, table in DAILY_BACKBONE.items():
        backbone_sets[track] = set(per_table[table].get("_strict_set") or [])
    intersection = sorted(set.intersection(*backbone_sets.values())) if backbone_sets else []

    # 哪条轨在卡脖子：去掉它之后交集能长多少。
    bottleneck: list[dict[str, Any]] = []
    for track in backbone_sets:
        others = [s for t, s in backbone_sets.items() if t != track]
        without = sorted(set.intersection(*others)) if others else []
        bottleneck.append(
            {
                "track": track,
                "table": BACKBONE[track],
                "own_strict_days": len(backbone_sets[track]),
                "intersection_without": len(without),
            }
        )
    bottleneck.sort(key=lambda x: -x["intersection_without"])

    return {
        "db": str(db_path),
        "per_table": {k: {kk: vv for kk, vv in v.items() if kk != "_strict_set"} for k, v in per_table.items()},
        "daily_tracks": sorted(DAILY_BACKBONE),
        "joint_strict_days": len(intersection),
        "joint_strict_dates": intersection,
        "cumulative_tracks": {
            track: {
                "table": table,
                "strict_days": per_table[table].get("strict_days"),
                "total_days": per_table[table].get("total_days"),
            }
            for track, table in BACKBONE.items()
            if table in CUMULATIVE
        },
        "bottleneck": bottleneck,
    }


def render(result: dict[str, Any]) -> str:
    out: list[str] = []
    out.append(f"时间长河 PIT 完备性审计  db={result['db']}")
    out.append("")
    out.append(f"{'轨':<14} {'表':<34} {'行数':>10} {'总日':>5} {'strict':>7} {'占比':>6}  strict 区间")
    for track, tables in TRACKS.items():
        for table in tables:
            r = result["per_table"][table]
            if r.get("status") != "ok":
                out.append(f"{track:<14} {table:<34} {r.get('status'):>10}")
                continue
            rng = f"{r['strict_from']}~{r['strict_to']}" if r["strict_from"] else "—"
            out.append(
                f"{track:<14} {table:<34} {r['rows']:>10,} {r['total_days']:>5} "
                f"{r['strict_days']:>7} {r['strict_pct']:>5.1f}%  {rng}"
            )
    out.append("")
    daily = "、".join(result["daily_tracks"])
    out.append(f"逐日轨联立可 strict 重放：{result['joint_strict_days']} 天（{daily}）")
    if result["joint_strict_dates"]:
        shown = result["joint_strict_dates"]
        out.append(f"  {shown if len(shown) <= 12 else shown[:12] + ['…']}")
    for track, info in result["cumulative_tracks"].items():
        out.append(
            f"累计轨 {track}：{info['strict_days']}/{info['total_days']} 天 strict"
            "（按 date <= as_of 取，不参与逐日交集）"
        )
    out.append("")
    out.append("卡脖子的轨（去掉它之后交集能长到多少天）：")
    for b in result["bottleneck"]:
        out.append(
            f"  去掉 {b['track']}（{b['table']}，自身 {b['own_strict_days']} 天）"
            f" → 交集 {b['intersection_without']} 天"
        )
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB))
    ap.add_argument("--json", action="store_true", help="输出 JSON 收据")
    args = ap.parse_args()

    result = run(Path(args.db).expanduser())
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
