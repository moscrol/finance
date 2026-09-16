#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services.forecast_learning import (  # noqa: E402
    approve_reflection,
    reject_reflection,
    render_learning_prompt,
    set_rule_status,
    sync_reflections,
    sync_rule_candidates,
)


DEFAULT_LEDGER = REPO_ROOT / "docs" / "learning" / "forecast-review-ledger"
DEFAULT_LEARNING = REPO_ROOT / "docs" / "learning" / "forecast-lessons"


def _paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    ledger = Path(args.ledger_dir).expanduser()
    learning = Path(args.learning_dir).expanduser()
    return ledger, learning, learning / "lessons.jsonl", learning / "rule_candidates.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="双盲 verdict/批注学习回流")
    parser.add_argument("--ledger-dir", default=str(DEFAULT_LEDGER))
    parser.add_argument("--learning-dir", default=str(DEFAULT_LEARNING))
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync-reflections")
    sync.add_argument("--date", action="append", default=[])
    sync.add_argument("--no-llm", action="store_true")
    sub.add_parser("sync-annotations")

    approve = sub.add_parser("approve-reflection")
    approve.add_argument("reflection")
    approve.add_argument("--id", action="append", default=[])
    reject = sub.add_parser("reject-reflection")
    reject.add_argument("reflection")
    reject.add_argument("--id", action="append", required=True)

    approve_rule = sub.add_parser("approve-rule")
    approve_rule.add_argument("id")
    reject_rule = sub.add_parser("reject-rule")
    reject_rule.add_argument("id")

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    ledger, learning, lessons, rules = _paths(args)
    if args.command == "sync-reflections":
        result = sync_reflections(
            ledger,
            learning,
            dates=args.date,
            use_llm=not args.no_llm,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result["errors"] else 1
    if args.command == "sync-annotations":
        print(json.dumps(sync_rule_candidates(ledger, rules), ensure_ascii=False, indent=2))
        return 0
    if args.command == "approve-reflection":
        result = approve_reflection(args.reflection, lessons, hypothesis_ids=args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "reject-reflection":
        result = reject_reflection(args.reflection, hypothesis_ids=args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command in {"approve-rule", "reject-rule"}:
        status = "approved" if args.command == "approve-rule" else "rejected"
        print(json.dumps(set_rule_status(rules, args.id, status), ensure_ascii=False, indent=2))
        return 0
    print(render_learning_prompt(lessons, rules, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
