#!/usr/bin/env python3
"""Offline AIHOT import. Dry run unless --apply; never calls a paid service.

Usage:
  python scripts/import_aihot_attention.py export.json --mapping mapping.json
  python scripts/import_aihot_attention.py export.json --mapping mapping.json --apply
Input: full/default AIHOT /api/v1/items JSON (not minimal projection, not a hot top-10 list).
No model-generated mapping is promoted automatically. A mapping may be empty: imported
unresolved articles remain inspectable, but do not become sector facts or clustered heat.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Script invocation, without editable installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.opinion_attention import adapt_aihot, append_observations, default_ledger_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        observations, errors = adapt_aihot(payload, mapping)
        report = {"mode": "apply" if args.apply else "dry-run", "accepted": len(observations), "errors": errors,
                  "mapped": sum(bool(row["entities"]) for row in observations),
                  "grouped": sum(row["grouping"] == "reviewed" for row in observations),
                  "unknown_sources": sum(not row["participant_key"] for row in observations),
                  "note": "局部导入快照，不代表全网覆盖；无连续采集证明，不判断舆论升降温。"}
        if errors:
            report["note"] = "验证失败，整批不写入；修正输入后重试。"
        elif args.apply:
            report.update(append_observations(args.ledger or default_ledger_path(), observations))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if errors else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "written": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
