#!/usr/bin/env python3
"""差分：同一个谓词的两份实现，在真实数据和类型空间上判定是否一致。

**为什么去重之前必须先跑它。** 两份「看起来一样」的判定函数，阈值相同不代表判定
相同——边界几乎总有出入（`None` / `bool` / 字符串 / `Decimal` 各自怎么处理）。直接
把复印件改成薄包装，等于把一次静默的行为变更混进一次重构里；日后出问题，归因会指
向无辜的地方。

两趟缺一不可：

    real   真实库里的行跑一遍   —— 回答「今天线上会不会翻转」
    types  类型空间跑一遍       —— 回答「哪种输入会翻转」，真实库里可能一条都没有

只有 real 全绿就切，是拿「今天恰好没有那种行」当「不会有那种行」。

用法：
    python3 scripts/diff_predicate_impls.py double-red --db <path> [--limit N]
    python3 scripts/diff_predicate_impls.py double-red --types-only
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.theme_lifecycle_timeline import (  # noqa: E402
    is_double_red as timeline_is_double_red,
)
from market_feature_store.signals import (  # noqa: E402
    is_double_red as canonical_is_double_red,
)


def _canonical(pct: object, diff: object, amount: object) -> bool:
    return canonical_is_double_red(pct, diff, amount)


def _copy(pct: object, diff: object, amount: object) -> bool:
    try:
        return timeline_is_double_red(
            {"pct_chg": pct, "diff_ratio": diff, "amount": amount}
        )
    except (TypeError, ValueError) as exc:
        # 复印件对某些输入会抛而不是返 False——这本身就是一种判定差异，要记下来。
        raise _CopyRaised(str(exc)) from exc


class _CopyRaised(Exception):
    pass


# 类型空间：每一格都是「真实调用点可能喂进来的东西」，不是造出来吓人的。
# 字符串来自 JSON/CSV/夹具；bool 来自把 flag 误当数值；Decimal 来自 DuckDB DECIMAL。
TYPE_CASES: tuple[tuple[str, object, object, object], ...] = (
    ("float 正常命中", 1.5, 12.0, 900.0),
    ("float 正常不命中", 1.5, 8.0, 900.0),
    ("int", 1, 12, 900),
    ("Decimal（DuckDB DECIMAL 列）", Decimal("1.5"), Decimal("12"), Decimal("900")),
    ("None 任一", None, 12.0, 900.0),
    ("字符串数值（JSON/CSV/夹具）", "1.5", "12", "900"),
    ("字符串 amount 单列", 1.5, 12.0, "501"),
    ("bool True 当 1.0", True, 12.0, 900.0),
    ("bool 混进 amount", 1.5, 12.0, True),
    ("边界：恰好等于阈值", 0.0, 10.0, 500.0),
    ("空字符串", "", 12.0, 900.0),
)


def run_types() -> int:
    print("== 类型空间差分 ==")
    diverged = 0
    for label, pct, diff, amount in TYPE_CASES:
        left = _canonical(pct, diff, amount)
        try:
            right = _copy(pct, diff, amount)
            right_repr = str(right)
        except _CopyRaised as exc:
            right_repr = f"raise({exc.__class__.__name__})"
            right = None
        same = right is not None and left == right
        if not same:
            diverged += 1
        mark = "  " if same else "▲ "
        print(f"{mark}{label:<28} 正典={left!s:<5} 复印件={right_repr}")
    print(f"\n类型空间：{len(TYPE_CASES)} 例，判定不同 {diverged} 例")
    return diverged


def run_real(db_path: Path, limit: int) -> int:
    import duckdb

    print(f"== 真实数据差分 == {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            """
            select pct_chg, diff_ratio, amount
            from fact_sector_daily
            where pct_chg is not null or diff_ratio is not null or amount is not null
            limit ?
            """,
            [limit],
        ).fetchall()
    finally:
        con.close()

    types: Counter[str] = Counter()
    diverged: list[tuple] = []
    for pct, diff, amount in rows:
        types[
            f"{type(pct).__name__}/{type(diff).__name__}/{type(amount).__name__}"
        ] += 1
        left = _canonical(pct, diff, amount)
        try:
            right = _copy(pct, diff, amount)
        except _CopyRaised:
            diverged.append((pct, diff, amount, left, "raise"))
            continue
        if left != right:
            diverged.append((pct, diff, amount, left, right))

    print(f"扫描 {len(rows)} 行")
    print("列类型分布：")
    for name, count in types.most_common():
        print(f"  {name:<28} {count}")
    print(f"判定不同：{len(diverged)} 行")
    for sample in diverged[:10]:
        print(f"  ▲ {sample}")
    return len(diverged)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predicate", choices=["double-red"])
    parser.add_argument("--db", default=os.environ.get("MARKET_FEATURE_STORE_DB", ""))
    parser.add_argument("--limit", type=int, default=200000)
    parser.add_argument("--types-only", action="store_true")
    args = parser.parse_args()

    type_diff = run_types()
    if args.types_only:
        return 0

    if not args.db:
        print("\n⚠ 未给 --db，只跑了类型空间。真实数据那趟没跑，不能据此宣布可切。")
        return 2
    real_diff = run_real(Path(args.db), args.limit)

    print("\n== 结论 ==")
    print(f"类型空间判定不同 {type_diff} 例；真实数据判定不同 {real_diff} 行。")
    if real_diff:
        print("真实数据已有翻转 → 切 import 会改变线上行为，先逐条定性。")
    else:
        print("真实数据零翻转 → 该路径可切；类型空间那几例仍要在切之前逐条处置。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
