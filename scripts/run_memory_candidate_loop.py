#!/usr/bin/env python3
"""user_memory 离线候选更新链 CLI（S6）：run 产候选过 gate，trace 归因反查。

用法（夜间挂载 launchd/cron 由用户自配，本脚本只保证幂等可重跑）::

    # 跑一轮（幂等：重跑第二次零新候选）；--dry-run 只报告不落盘
    python -m scripts.run_memory_candidate_loop run [--user ID | --user-dir PATH] [--dry-run] [--json]

    # 归因反查：给任一 accepted 经验（promotion.candidate_id / content_sha256 /
    # 经验原文），一步查到来源记录 ids
    python -m scripts.run_memory_candidate_loop trace --candidate-id mc-xxxx
    python -m scripts.run_memory_candidate_loop trace --sha <content_sha256>
    python -m scripts.run_memory_candidate_loop trace --content "经验原文"

候选生命周期与留档格式见 docs/learning/memory-candidate-lifecycle.md。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence import userspace
from intelligence.services import memory_candidate_loop as loop


def _resolve_root(args: argparse.Namespace) -> Path:
    if args.user_dir:
        return Path(args.user_dir).expanduser()
    return userspace.user_space(args.user).root


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--user", default=None, help="用户 id（默认 FORESIGHT_USER/default）")
    parser.add_argument(
        "--user-dir",
        default=None,
        help="直接指定用户台账目录（优先于 --user；夹具/测试用）",
    )


def _print_run_summary(summary: dict) -> None:
    scanned = summary["scanned"]
    print(f"memory-candidate-loop · 用户目录 {summary['user_dir']}")
    print(
        "扫描：corrections {corrections} · checkpoints {checkpoints} · "
        "verdicts {verdicts} · interactions {interactions}".format(**scanned)
    )
    print(
        f"候选：规则提议 {summary['proposed']}（新 {summary['new']}，"
        f"已在档跳过 {summary['skipped_existing']}）"
    )
    print(
        f"门禁：accepted {summary['accepted']} · rejected {summary['rejected']}"
        f"（全部留档带理由：{summary['archive_path']}）"
    )
    if summary["dry_run"]:
        print("[dry-run] 未落盘：不写候选档、不写晋升。以下为本会落盘的候选：")
    for row in summary["candidates"]:
        target = f"→{row['promoted_to']}" if row.get("promoted_to") else ""
        reason = row["gate"]["reason"]
        content = row["content"][:60]
        print(
            f"- {row['candidate_id']} [{row['status']}{target}] "
            f"rule={row['trigger_rule']} reason={reason} 「{content}」"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_memory_candidate_loop",
        description="user_memory 离线候选更新链：规则产候选 → memory_gate 裁决 → 留档/晋升",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="跑一轮候选更新（幂等，可 --dry-run）")
    _add_target_args(run_parser)
    run_parser.add_argument("--dry-run", action="store_true", help="只报告，不写任何文件")
    run_parser.add_argument("--json", action="store_true", help="输出机器可读 JSON summary")

    trace_parser = sub.add_parser("trace", help="归因反查：候选/经验 → 来源记录 ids")
    _add_target_args(trace_parser)
    key = trace_parser.add_mutually_exclusive_group(required=True)
    key.add_argument("--candidate-id", help="候选 id（accepted 经验的 promotion.candidate_id）")
    key.add_argument("--sha", help="内容 SHA-256（promotion.content_sha256）")
    key.add_argument("--content", help="经验原文（自动取 SHA-256 再查）")

    args = parser.parse_args(argv)
    root = _resolve_root(args)

    if args.command == "run":
        summary = loop.run_loop(root, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            _print_run_summary(summary)
        return 0

    archive = loop.load_candidate_archive(root / loop.CANDIDATES_FILENAME)
    sha = args.sha
    if args.content:
        sha = hashlib.sha256(args.content.strip().encode("utf-8")).hexdigest()
    rows = loop.trace_candidate(
        archive, candidate_id=args.candidate_id, content_sha256=sha
    )
    if not rows:
        print("未找到匹配候选（确认候选档路径与 candidate_id/sha）", file=sys.stderr)
        return 2
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
