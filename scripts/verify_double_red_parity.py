#!/usr/bin/env python3
"""§10-8 行为对照：双红收口前后，默认盒的输出必须逐格相同。

**测试全绿不是这条的证据。** 绿只说明测试覆盖到的路径没变；§10-8 要的是拿改前
改后各算一次，把「日报双红个数 / 预取口径 / 🔥 标记数 / 时间线阶段段落」并排比。
渲染与派生路径大多没有单测，正是靠这一趟兜底。

「改前」不靠人重打一遍旧代码——那样比的是我记得的旧逻辑，不是真的旧逻辑。这里用
``git show HEAD:<path>`` 把旧模块原样取出来加载，两份实现同进程跑同一批真实行。

用法：
    python3 scripts/verify_double_red_parity.py --db <path> [--themes 固态电池,信创]
退出码 0 = 逐格相同；1 = 有差异（逐条打印）。
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def load_module_at_head(rel_path: str, name: str, *, shadow: dict | None = None):
    """把 HEAD 上那一版模块原样加载进来。

    取源码而不是复述逻辑：复述会把「我以为的旧行为」当成旧行为，那正是这趟对照
    要排除的东西。

    ``shadow``：加载期间临时把某些点分模块名换成 HEAD 版本。旧 ``asof_prefetch``
    从旧 ``theme_lifecycle_timeline`` 引三个常量，而现在那三个常量已经不在那儿了
    ——不影子化就只能拿到 ImportError，比不成。加载完立刻还原，不污染本进程后面
    要用的「现在」那一版。
    """

    source = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    tmp = Path(tempfile.mkdtemp(prefix="double-red-head-")) / f"{name}.py"
    tmp.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, tmp)
    module = importlib.util.module_from_spec(spec)

    saved: dict = {}
    for dotted, replacement in (shadow or {}).items():
        saved[dotted] = sys.modules.get(dotted)
        sys.modules[dotted] = replacement
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        for dotted, previous in saved.items():
            if previous is None:
                sys.modules.pop(dotted, None)
            else:
                sys.modules[dotted] = previous
    return module


def _head_prefetch_module(name: str):
    """旧 ``asof_prefetch``，连它依赖的旧 ``timeline`` 一起还原。"""

    head_timeline = load_module_at_head(
        "intelligence/services/theme_lifecycle_timeline.py", f"{name}_timeline"
    )
    return load_module_at_head(
        "intelligence/services/asof_prefetch.py",
        name,
        shadow={"intelligence.services.theme_lifecycle_timeline": head_timeline},
    )


def compare_predicate(rows) -> tuple[int, list]:
    """判定逐行对照：HEAD 的 timeline 实现 vs 现在的正典。"""

    head_timeline = load_module_at_head(
        "intelligence/services/theme_lifecycle_timeline.py", "_head_timeline"
    )
    from market_feature_store.signals import is_double_red

    diffs = []
    for pct, diff, amount in rows:
        before = head_timeline.is_double_red(
            {"pct_chg": pct, "diff_ratio": diff, "amount": amount}
        )
        after = is_double_red(pct, diff, amount)
        if before != after:
            diffs.append((pct, diff, amount, before, after))
    return len(rows), diffs


def head_fire_mark_expression() -> str:
    """从 HEAD 的 `daily_review.py` 里把 🔥 那句判断**原文**取出来。

    为什么不直接在本文件里重打一遍那个表达式：

    1. 重打比的是「我记得的旧逻辑」，不是旧逻辑本身——这趟对照的全部意义就是排除
       这一点；
    2. 重打会在本文件里留下第四份阈值复印件，被 `check_double_red_copies.py` 抓住
       ——**而且抓得对**。验证工具豁免自己，是给门禁开的第一个后门。

    定位靠结构（`cell = f"🔥{cell}"` 的前一行 `if`），不靠阈值字面，所以本文件里
    一个阈值都不出现。
    """

    source = subprocess.run(
        ["git", "show", "HEAD:market_feature_store/reports/daily_review.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    for index, line in enumerate(source):
        if line.strip().startswith("cell = f\"\U0001f525"):
            guard = source[index - 1].strip()
            if guard.startswith("if ") and guard.endswith(":"):
                return guard[3:-1]
    raise RuntimeError("在 HEAD 的 daily_review 里找不到 🔥 那句判断")


def compare_fire_marks(rows) -> tuple[int, int, list]:
    """🔥 标记数：日报改前那句内联比较（取自 HEAD 原文）vs 现在的 `is_double_red`。

    外层已经保证 diff/amount 非 None，所以这里照同样的前置条件复现。
    """

    from market_feature_store.signals import is_double_red

    expression = compile(head_fire_mark_expression(), "<head:daily_review>", "eval")
    before_marks = 0
    after_marks = 0
    diffs = []
    for pct, diff, amount in rows:
        if diff is None or amount is None:
            continue
        before = bool(eval(expression, {"__builtins__": {}}, {"pct": pct, "diff": diff, "amount": amount}))
        after = is_double_red(pct, diff, amount)
        before_marks += int(before)
        after_marks += int(after)
        if before != after:
            diffs.append((pct, diff, amount, before, after))
    return before_marks, after_marks, diffs


def compare_single_red(db_path: Path, days: int) -> tuple[int, int, list]:
    """单红计数：日报改前的 SQL（NULL 算单红）vs 正典（NULL 不算）。

    口径已定为「缺数两边都不算」（2026-08-22），所以这一趟**不是**要证明零差异，
    而是要**量出这次口径变更实际影响了多少行**。零 = 今天的数据碰不上这个分歧。
    """

    import duckdb

    from market_feature_store.signals import SINGLE_RED_SQL

    before_sql = "pct_chg > 0 AND diff_ratio > 10 AND (amount <= 500 OR amount IS NULL)"
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        days_rows = con.execute(
            "select distinct trade_date from fact_sector_daily order by trade_date desc limit ?",
            [days],
        ).fetchall()
        before = after = 0
        diffs = []
        for (day,) in days_rows:
            b = con.execute(
                f"select count(*) from fact_sector_daily where trade_date = ? and {before_sql}",
                [day],
            ).fetchone()[0]
            a = con.execute(
                f"select count(*) from fact_sector_daily where trade_date = ? and {SINGLE_RED_SQL}",
                [day],
            ).fetchone()[0]
            before += b
            after += a
            if b != a:
                diffs.append((str(day), b, a))
        return before, after, diffs
    finally:
        con.close()


def compare_caliber() -> tuple[str, str]:
    """预取口径串：HEAD 的 `_CALIBER` vs 现在的。"""

    head_prefetch = _head_prefetch_module("_head_prefetch")
    from intelligence.services import asof_prefetch

    return head_prefetch._CALIBER, asof_prefetch._CALIBER


def compare_dual_red_counts(db_path: Path, days: int) -> tuple[dict, dict]:
    """预取的双红个数：HEAD 的 `dual_red_counts` vs 现在的，同一批交易日。"""

    import duckdb

    head_prefetch = _head_prefetch_module("_head_prefetch2")
    from intelligence.services import asof_prefetch
    from datetime import date

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        raw = con.execute(
            "select distinct trade_date from fact_sector_daily order by trade_date desc limit ?",
            [days],
        ).fetchall()
        dates = tuple(
            item[0] if hasattr(item[0], "isoformat") else date.fromisoformat(str(item[0]))
            for item in raw
        )
        return (
            head_prefetch.dual_red_counts(con, dates),
            asof_prefetch.dual_red_counts(con, dates),
        )
    finally:
        con.close()


def compare_timeline_stages(db_path: Path, themes: tuple[str, ...]) -> list:
    """时间线阶段段落：`is_double_red` 驱动阶段派生，是改动面最大的下游。"""

    import duckdb

    head_timeline = load_module_at_head(
        "intelligence/services/theme_lifecycle_timeline.py", "_head_timeline2"
    )
    from intelligence.services import theme_lifecycle_timeline as now_timeline

    mismatches = []
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for theme in themes:
            rows = now_timeline.load_theme_daily_rows(con, theme)
            if not rows:
                mismatches.append((theme, "无行", "无行", True))
                continue
            before, _ = head_timeline.derive_stages(rows)
            after, _ = now_timeline.derive_stages(rows)
            same = [s.to_payload() for s in before] == [s.to_payload() for s in after]
            mismatches.append((theme, len(before), len(after), same))
    finally:
        con.close()
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--limit", type=int, default=300000)
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--themes", default="固态电池,信创,人形机器人")
    args = parser.parse_args()

    import duckdb

    db_path = Path(args.db)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "select pct_chg, diff_ratio, amount from fact_sector_daily limit ?",
            [args.limit],
        ).fetchall()
    finally:
        con.close()

    failures = 0

    scanned, diffs = compare_predicate(rows)
    print(f"[判定逐行] 扫 {scanned} 行，判定不同 {len(diffs)} 行")
    failures += len(diffs)
    for sample in diffs[:5]:
        print(f"   ▲ {sample}")

    before_marks, after_marks, mark_diffs = compare_fire_marks(rows)
    print(f"[🔥 标记数] 改前 {before_marks} ｜ 改后 {after_marks} ｜ 逐行不同 {len(mark_diffs)}")
    failures += len(mark_diffs) + (before_marks != after_marks)

    head_caliber, now_caliber = compare_caliber()
    same_caliber = head_caliber == now_caliber
    print(f"[预取口径] {'一致' if same_caliber else '不一致'}：{now_caliber}")
    if not same_caliber:
        print(f"   改前：{head_caliber}")
        failures += 1

    before_counts, after_counts = compare_dual_red_counts(db_path, args.days)
    count_diffs = [
        (day, before_counts.get(day), after_counts.get(day))
        for day in sorted(set(before_counts) | set(after_counts))
        if before_counts.get(day) != after_counts.get(day)
    ]
    print(f"[预取双红个数] 比 {len(before_counts)} 个交易日，不同 {len(count_diffs)} 个")
    failures += len(count_diffs)
    for sample in count_diffs[:5]:
        print(f"   ▲ {sample}")

    sr_before, sr_after, sr_diffs = compare_single_red(db_path, args.days)
    print(
        f"[单红计数] 改前（NULL 算单红）{sr_before} ｜ 改后（NULL 不算）{sr_after}"
        f" ｜ 有差异的交易日 {len(sr_diffs)}"
    )
    for sample in sr_diffs[:5]:
        print(f"   ▲ {sample}")

    themes = tuple(t.strip() for t in args.themes.split(",") if t.strip())
    stage_rows = compare_timeline_stages(db_path, themes)
    bad = [row for row in stage_rows if not row[3]]
    print(f"[时间线阶段] 比 {len(stage_rows)} 个题材，段落不同 {len(bad)} 个")
    for theme, before, after, same in stage_rows:
        print(f"   {'✓' if same else '▲'} {theme}：改前 {before} 段 ／ 改后 {after} 段")
    failures += len(bad)

    print()
    if failures:
        print(f"❌ §10-8 未通过：{failures} 处差异")
        return 1
    print("✅ §10-8 通过：默认盒行为与改前逐格一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
