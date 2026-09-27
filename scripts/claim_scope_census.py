#!/usr/bin/env python3
"""Count explicit frozen claim-scope artifacts without network or model calls."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


def census(paths: list[Path]) -> dict[str, Any]:
    modes: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    present = hits = degraded = invalid = 0
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        semantic = payload.get("semantic_verifier") or {}
        receipt = semantic.get("claim_scope") if "semantic_verifier" in payload else payload
        if not isinstance(receipt, dict) or "mode" not in receipt:
            modes["missing"] += 1
            continue
        mode = receipt["mode"]
        modes[str(mode)] += 1
        invalid += "claim_scope_mode_invalid" in receipt or "claim_scope_mode_unsupported" in receipt
        if mode != "advisory":
            continue
        present += 1
        hits += bool(receipt["issue_count"])
        degraded += bool(receipt["degraded"])
        rules.update(set(receipt["rules_hit"]))
    return {
        "denominator": "explicit_artifacts",
        "artifact_count": len(paths),
        "advisory_count": present,
        "hit_count": hits,
        "degraded_count": degraded,
        "invalid_or_unsupported_count": invalid,
        "presence_rate": present / len(paths) if paths else None,
        "hit_rate_among_advisory": hits / present if present else None,
        "modes": dict(modes),
        "rules_hit_counts": dict(rules),
        "boundary": "Descriptive known-pattern counts, not answer quality or recall.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps(census(args.artifacts), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
