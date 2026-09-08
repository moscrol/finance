#!/usr/bin/env python3
"""切主前的覆盖对账：新源换掉旧源，日历上会不会静默少几天。

防的失败形状（2026-09-08 工单 #41 E 实发）：新数据源在**当前**这几天更全、
更权威，于是消费方直接把读口换过去；但新源的历史深度比旧源短，日历前段
整段没有行。行数、一致率、抽样都看不出来——它们只比两边**都有**的那些日子。
标签变 NULL 不报错，构建照样绿，下游读到的是「那天没有龙虎榜」。

实测：`fact_dragon_tiger_hithink` 只回溯一年，直接替换
`fact_dragon_tiger_daily` 让授课框架 416 天日历里 166 天的 `tf.dragon_*`
变空；处方是「按日回退」——新源那天有行用新源，整天没有才用旧源，
合并后覆盖 408 天，比旧源单独的 405 天还多 3 天。

所以切主前跑这个，退出码非 0 就说明裸切会掉日子，必须写回退分支。

用法：
    python3 scripts/source_switch_coverage_diff.py \\
        --old fact_dragon_tiger_daily --new fact_dragon_tiger_hithink
    # 只数「值非空」的行：
    python3 scripts/source_switch_coverage_diff.py \\
        --old fact_dragon_tiger_daily:net_amount \\
        --new fact_dragon_tiger_hithink:net_value

退出码：0 = 裸切不掉日子；1 = 裸切会掉日子（需要按日回退）；2 = 参数或表有问题。
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

DEFAULT_DB = Path(__file__).resolve().parent.parent / "db" / "market_feature_store.duckdb"


@dataclass(frozen=True)
class Side:
    """一个源：表名 + 可选的「值必须非空」列。"""

    table: str
    value_column: str | None

    @classmethod
    def parse(cls, raw: str) -> "Side":
        table, _, column = raw.partition(":")
        if not table:
            raise ValueError(f"源写法应是 TABLE 或 TABLE:COLUMN，得到 {raw!r}")
        return cls(table=table, value_column=column or None)

    def days_sql(self, date_column: str) -> str:
        where = f" WHERE {self.value_column} IS NOT NULL" if self.value_column else ""
        return f"SELECT DISTINCT {date_column} AS d FROM {self.table}{where}"

    def __str__(self) -> str:
        return f"{self.table}:{self.value_column}" if self.value_column else self.table


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = ?",
        [name],
    ).fetchone()
    return bool(row and row[0])


def compare(
    con: duckdb.DuckDBPyConnection,
    *,
    old: Side,
    new: Side,
    calendar_table: str,
    date_column: str,
) -> dict:
    """返回逐月与合计的覆盖对账。日历是分母，两个源各自与它对齐。"""

    for name in (calendar_table, old.table, new.table):
        if not _table_exists(con, name):
            raise LookupError(f"表不存在：{name}")

    sql = f"""
    WITH cal AS (SELECT DISTINCT {date_column} AS d FROM {calendar_table}),
    o AS ({old.days_sql(date_column)}),
    n AS ({new.days_sql(date_column)})
    SELECT
        strftime(cal.d, '%Y-%m') AS ym,
        COUNT(*) AS cal_days,
        COUNT(o.d) AS old_days,
        COUNT(n.d) AS new_days,
        COUNT(*) FILTER (WHERE o.d IS NOT NULL OR n.d IS NOT NULL) AS merged_days,
        COUNT(*) FILTER (WHERE o.d IS NOT NULL AND n.d IS NULL) AS lost_by_switch,
        COUNT(*) FILTER (WHERE n.d IS NOT NULL AND o.d IS NULL) AS gained_by_switch
    FROM cal
    LEFT JOIN o ON o.d = cal.d
    LEFT JOIN n ON n.d = cal.d
    GROUP BY 1 ORDER BY 1
    """
    months = [
        {
            "ym": r[0], "cal_days": r[1], "old_days": r[2], "new_days": r[3],
            "merged_days": r[4], "lost": r[5], "gained": r[6],
        }
        for r in con.execute(sql).fetchall()
    ]
    total = {
        key: sum(m[key] for m in months)
        for key in ("cal_days", "old_days", "new_days", "merged_days", "lost", "gained")
    }
    return {"months": months, "total": total, "old": str(old), "new": str(new)}


def render(result: dict, *, calendar_table: str) -> str:
    t = result["total"]
    lines = [
        "=" * 72,
        "切主覆盖对账 — 裸切会不会在日历上静默少几天",
        "=" * 72,
        f"  日历      {calendar_table}（{t['cal_days']} 天）",
        f"  旧源      {result['old']}：{t['old_days']} 天",
        f"  新源      {result['new']}：{t['new_days']} 天",
        f"  并集      按日回退后：{t['merged_days']} 天",
        "",
        f"  裸切丢失  {t['lost']} 天（旧源有、新源整天没有）",
        f"  裸切新增  {t['gained']} 天（新源有、旧源整天没有）",
        "",
    ]
    if t["lost"]:
        lines += ["  逐月（只列有丢失的月份）：", "    月份      日历  旧源  新源  丢失"]
        for m in result["months"]:
            if m["lost"]:
                lines.append(
                    f"    {m['ym']}   {m['cal_days']:4d}  {m['old_days']:4d}"
                    f"  {m['new_days']:4d}  {m['lost']:4d}"
                )
        lines += [
            "",
            "❌ 裸切会掉日子。消费方必须写「按日回退」：新源那天有行用新源，",
            "   整天没有才用旧源；不要逐行 UNION（同一天两源都有会重复计数）。",
            "",
            f"结论：不通过（裸切丢 {t['lost']} 天，按日回退可覆盖 {t['merged_days']} 天）",
        ]
    else:
        lines += [
            "✅ 新源在日历上完全覆盖旧源，裸切不掉日子。",
            "",
            f"结论：通过（对 {calendar_table} 的 {t['cal_days']} 天成立）",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="切主前的覆盖对账")
    parser.add_argument("--old", required=True, help="旧源，TABLE 或 TABLE:值列")
    parser.add_argument("--new", required=True, help="新源，TABLE 或 TABLE:值列")
    parser.add_argument("--calendar-table", default="fact_market_daily")
    parser.add_argument("--date-column", default="trade_date")
    parser.add_argument(
        "--db",
        default=os.environ.get("MARKET_FEATURE_STORE_DB") or str(DEFAULT_DB),
        help="DuckDB 路径，默认 MARKET_FEATURE_STORE_DB 或仓内主库",
    )
    args = parser.parse_args(argv)

    try:
        old, new = Side.parse(args.old), Side.parse(args.new)
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2
    if not Path(args.db).exists():
        print(f"库不存在：{args.db}", file=sys.stderr)
        return 2

    con = duckdb.connect(args.db, read_only=True)
    try:
        result = compare(
            con, old=old, new=new,
            calendar_table=args.calendar_table, date_column=args.date_column,
        )
    except LookupError as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    finally:
        con.close()

    print(render(result, calendar_table=args.calendar_table))
    return 1 if result["total"]["lost"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
