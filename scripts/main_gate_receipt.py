"""Read one gate receipt, never a shared latest pointer.

The shell owns the run identity; pytest owns the result. Both must agree.
An explicit baseline comparison is diagnostic, not permission to merge red tests.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_receipt(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("receipt must be an object")
    counts = data.get("counts")
    if not isinstance(counts, dict) or any(
        type(counts.get(key)) is not int or counts[key] < 0
        for key in ("passed", "failed", "error", "skipped")
    ):
        raise ValueError("invalid counts")
    if sum(counts[key] for key in ("passed", "failed", "error")) == 0:
        raise ValueError("zero executed tests")
    status = data.get("exit_status")
    if type(status) is not int or status not in (0, 1):
        raise ValueError("missing exit_status or incomplete pytest run")
    failed = data.get("failed_ids")
    if not isinstance(failed, list) or any(not isinstance(x, str) or not x for x in failed):
        raise ValueError("invalid failed_ids")
    if len(failed) != counts["failed"] + counts["error"] or bool(failed) != bool(status):
        raise ValueError("exit_status, counts and failed_ids disagree")
    if not isinstance(data.get("target"), str):
        raise ValueError("missing target")
    if data.get("dependency_gate_bypassed") is not False:
        raise ValueError("dependency gate was bypassed or is unknown")
    if data.get("interpreter") != sys.executable:
        raise ValueError("interpreter mismatch")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt")
    parser.add_argument("--baseline")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--pytest-exit", type=int)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    try:
        latest = load_receipt(args.receipt)
        if latest.get("revision") != args.revision:
            raise ValueError("receipt revision does not match the tested revision")
        if not args.allow_dirty and (
            latest.get("dirty") is not False or type(latest.get("worktree_dirty_total")) is not int
            or latest["worktree_dirty_total"] != 0
        ):
            raise ValueError("receipt is dirty or dirty state is unknown")
        if args.pytest_exit is not None:
            if latest.get("tree") != args.tree:
                raise ValueError("receipt tree does not match this run")
            if latest["exit_status"] != args.pytest_exit:
                raise ValueError("receipt exit_status does not match pytest process")
        counts, failed = latest["counts"], sorted(latest["failed_ids"])
        print(f"== receipt {args.receipt}")
        print(f"   revision={latest['revision'][:12]} dirty={latest.get('dirty')} "
              f"target={latest['target']}")
        print("   " + " ".join(f"{key}={value}" for key, value in counts.items()))
        for nodeid in failed:
            print(f"   RED {nodeid}")
        if not args.baseline:
            return latest["exit_status"]
        base = load_receipt(args.baseline)
        if base.get("dirty") is not False or base.get("worktree_dirty_total") != 0:
            raise ValueError("baseline is dirty or dirty state is unknown")
        if base["target"] != latest["target"]:
            raise ValueError("baseline target differs from this run")
        new_red = sorted(set(failed) - set(base["failed_ids"]))
        gone_red = sorted(set(base["failed_ids"]) - set(failed))
        print(f"== baseline comparison only (not a merge gate): {args.baseline}")
        for nodeid in new_red:
            print(f"   NEW RED {nodeid}")
        for nodeid in gone_red:
            print(f"   FIXED {nodeid}")
        passed_ok = counts["passed"] >= base["counts"]["passed"]
        print(f"   same_red_set={not new_red and not gone_red} passed_non_decreasing={passed_ok}")
        return 0 if not new_red and passed_ok else 3
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"gate receipt refused: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
