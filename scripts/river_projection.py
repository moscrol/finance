#!/usr/bin/env python3
"""上下文投影回放（工单 #34 / G-14）：重算某天某实体的投影、打印哈希，可与台账里的哈希对账。

    # 从真库重算并打印人读投影 + 哈希
    python3 scripts/river_projection.py replay --as-of 2026-09-05 --entity 上证指数

    # 回放：显式 cutoff、任务、预算；--expect 不等即退出码 1（「每条 agent 判断都能回放它当时看到的上下文」）
    python3 scripts/river_projection.py replay --as-of 2026-09-05 --entity 算力租赁 \
        --cutoff 2026-09-05 --task guided_reading --expect cp:0123456789abcdef

    # 离线：从保存的切片 JSON（RiverSlice.to_dict() 形状）重算，不碰库
    python3 scripts/river_projection.py replay --from-json /tmp/slice.json --task guided_reading --json

投影不落库、不缓存：这条命令就是「回放钥匙」的可执行形式——同样的 (source, framework_version,
task, budget, projection_version, label_version) 永远算出同一个哈希。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services import river_projection  # noqa: E402


def _load_source(args: argparse.Namespace) -> dict:
    if args.from_json:
        return json.loads(Path(args.from_json).expanduser().read_text(encoding="utf-8"))
    if not (args.as_of and args.entity):
        raise SystemExit("要么给 --from-json，要么给 --as-of 与 --entity")
    from intelligence.services import river

    sl = river.slice_river(
        args.as_of,
        args.entity,
        knowledge_cutoff=args.cutoff,
        allow_hindsight=bool(args.cutoff and args.cutoff > args.as_of),
        db_path=args.db_path,
        checkpoints_path=args.checkpoints_path,
    )
    return sl.to_dict()


def cmd_replay(args: argparse.Namespace) -> int:
    source = _load_source(args)
    cp = river_projection.project(
        source,
        framework_version=args.framework_version,
        task=args.task,
        budget=args.budget,
    )
    if args.json:
        print(json.dumps(cp.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(river_projection.render(cp))
    if args.expect:
        ok = cp.projection_hash == args.expect
        print(f"\nexpect={args.expect} actual={cp.projection_hash} → {'MATCH' if ok else 'MISMATCH'}")
        return 0 if ok else 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("replay", help="重算投影并打印哈希；--expect 对账")
    p.add_argument("--as-of")
    p.add_argument("--entity")
    p.add_argument("--cutoff", help="knowledge_cutoff；缺省 = as_of")
    p.add_argument("--from-json", help="RiverSlice.to_dict() 形状的 JSON，离线回放")
    p.add_argument("--task", default="guided_reading")
    p.add_argument("--budget", type=int, default=None, help="块数上限；缺省不限")
    p.add_argument("--framework-version", default=None)
    p.add_argument("--db-path", default=None)
    p.add_argument("--checkpoints-path", default=None)
    p.add_argument("--expect", help="期望的 projection_hash（cp:…）；不等退出码 1")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_replay)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
