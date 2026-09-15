#!/usr/bin/env python3
"""区间契约 CLI（工单 #35 / G-02c）：``window`` 看一段区间的切片序列、覆盖矩阵与逐日 PIT；``cluster`` 是原有聚类入口。

    # 一段区间：逐日 pit_grade + 覆盖矩阵 + cumulative 派生对象
    python3 scripts/river_window.py window --start 2026-08-03 --end 2026-08-28 --entity 半导体 [--cutoff 2026-08-28] [--json]

    # 顺手算派生对象（只收单日切片可判的注册标签）
    python3 scripts/river_window.py window --start ... --end ... --entity 半导体 --streak dual_red_strict --transition market_stage

    # 原有聚类入口（现在必须声明 cutoff）
    python3 scripts/river_window.py cluster 2026-07-01 2026-07-15 --cutoff 2026-09-01 [--before 0 --after 9]

区间不落库不缓存：每次现算；``C < end`` 会被拒绝，``C > end`` 要显式 ``--allow-hindsight``。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services import river_derive, river_window_contract  # noqa: E402


def cmd_window(args: argparse.Namespace) -> int:
    win = river_window_contract.window(
        args.start,
        args.end,
        args.entity,
        knowledge_cutoff=args.cutoff,
        allow_hindsight=args.allow_hindsight,
        require_strict=args.require_strict,
        db_path=args.db_path,
        checkpoints_path=args.checkpoints_path,
    )
    derived = list(win.derived)
    for label in args.streak or []:
        derived.append(river_derive.derive_streak(win, label, gap_policy=args.gap_policy))
    for label in args.transition or []:
        derived.append(river_derive.derive_transitions(win, label, gap_policy=args.gap_policy))
    for spec in args.first_event or []:
        track, _, otype = spec.partition(":")
        if not track or not otype:
            raise SystemExit(f"--first-event 形状是 track:object_type，收到 {spec!r}")
        derived.append(river_derive.derive_first_event(win, track, otype))
    if args.json:
        out = win.to_dict()
        out["derived"] = [o.to_dict() for o in derived]
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    print(river_window_contract.render(win))
    if len(derived) > len(win.derived):
        print("\n  派生（本次追加）：")
        for o in derived[len(win.derived):]:
            p = o.payload
            summary = {k: p.get(k) for k in ("status", "longest", "current", "count", "first_day") if k in p}
            print(f"    {o.object_type:<12} {p.get('derivation_rule', {}).get('name')}  {summary}  gaps={p.get('gaps_applied')}")
    return 0


def cmd_cluster(args: argparse.Namespace) -> int:
    from intelligence.services import river_window as rw

    argv = list(args.anchors) + ["--cutoff", args.cutoff, "--before", str(args.before), "--after", str(args.after), "--threshold", str(args.threshold)]
    if args.checkpoints:
        argv += ["--checkpoints", args.checkpoints]
    if args.json:
        argv.append("--json")
    old = sys.argv
    try:
        sys.argv = ["river_window", *argv]
        return int(rw.main())
    finally:
        sys.argv = old


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    w = sub.add_parser("window", help="一段区间的切片序列 / 覆盖 / PIT / 派生对象")
    w.add_argument("--start", required=True)
    w.add_argument("--end", required=True)
    w.add_argument("--entity", required=True)
    w.add_argument("--cutoff", default=None, help="knowledge_cutoff；缺省 = end")
    w.add_argument("--allow-hindsight", action="store_true")
    w.add_argument("--require-strict", action="store_true")
    w.add_argument("--streak", action="append", help="注册标签名，可重复")
    w.add_argument("--transition", action="append", help="注册标签名，可重复")
    w.add_argument("--first-event", action="append", help="track:object_type，可重复")
    w.add_argument("--gap-policy", default="unverifiable", choices=river_derive.GAP_POLICIES)
    w.add_argument("--db-path", default=None)
    w.add_argument("--checkpoints-path", default=None)
    w.add_argument("--json", action="store_true")
    w.set_defaults(func=cmd_window)

    c = sub.add_parser("cluster", help="原有：锚点窗口六维签名 + 层次聚类（现在必须给 --cutoff）")
    c.add_argument("anchors", nargs="+")
    c.add_argument("--cutoff", required=True)
    c.add_argument("--before", type=int, default=0)
    c.add_argument("--after", type=int, default=9)
    c.add_argument("--threshold", type=float, default=1.0)
    c.add_argument("--checkpoints", default=None)
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_cluster)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
