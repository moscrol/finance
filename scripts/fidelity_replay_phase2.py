#!/usr/bin/env python3
"""Build the deterministic 50–100 date Phase 2 sampling plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.phase2_sampling import (  # noqa: E402
    build_phase2_plan,
    write_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--seed",
        default="fidelity-replay-phase2-v1",
    )
    args = parser.parse_args(argv)
    plan, registry = build_phase2_plan(
        db_path=args.db,
        repo_root=args.repo_root,
        start=args.start,
        end=args.end,
        count=args.count,
        seed=args.seed,
    )
    output = Path(args.out_dir).expanduser()
    plan_path = output / "phase2.selection.json"
    registry_path = output / "phase2.registry.json"
    write_json(plan_path, plan)
    write_json(registry_path, registry)
    print(
        json.dumps(
            {
                "selected_count": plan["selected_count"],
                "selected_strata": plan["selected_strata"],
                "decision_eligible": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"written: {plan_path}")
    print(f"written: {registry_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
