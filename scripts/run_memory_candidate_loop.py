#!/usr/bin/env python3
"""user_memory 离线候选环 CLI（书距 S6）：幂等可 dry-run，供夜间 launchd/cron 挂载。

    run   跑一轮：台账 → 规则化候选 → memory_gate → 留档/落盘（--dry-run 不写盘）
    trace 归因反查：候选 id / 内容哈希前缀 / 晋升行 ts → 来源记录 ids

挂载示例（挂载本身留给用户）：
    .venv-workbench/bin/python scripts/run_memory_candidate_loop.py run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services.memory_candidate_loop import (  # noqa: E402
    run_candidate_loop,
    trace_candidate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="user_memory 离线候选更新链")
    parser.add_argument("--user", default=None, help="用户 id（默认 default）")
    parser.add_argument(
        "--users-root",
        default=None,
        help="直接指向台账目录（测试/夹具用，覆盖 --user 解析）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="跑一轮候选环")
    run.add_argument("--dry-run", action="store_true", help="只报告，不写任何文件")

    trace = sub.add_parser("trace", help="按候选 id / 内容哈希前缀 / 晋升行 ts 反查来源")
    trace.add_argument("query")

    args = parser.parse_args(argv)
    if args.command == "run":
        report = run_candidate_loop(
            user=args.user,
            users_root=args.users_root,
            dry_run=args.dry_run,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    matches = trace_candidate(args.query, user=args.user, users_root=args.users_root)
    print(json.dumps(matches, ensure_ascii=False, indent=2))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
