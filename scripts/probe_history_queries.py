#!/usr/bin/env python3
"""Replay explicit HistoryQuery specs, checking actual model projection for omissions.

Developer smoke probe, NOT a product door, independent arithmetic audit, or LLM
quality test. Opens only the caller's canonical DB read-only; creates a NEW output
directory for originals + receipts. No user ledger, market writes or model calls.
Prevents a hand-written summary from hiding nulls, input scope, or clipped fields.

python scripts/probe_history_queries.py --db DB --recipe queries.json --output NEW_DIR
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.historical_research.episode import _model_projection  # noqa: E402
from intelligence.services.historical_research.query import HistoryQuery, HistoryQuerySpec  # noqa: E402
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    cutoff = InformationCutoff(date.fromisoformat(recipe["information_cutoff"]), "requested")
    queries = recipe["queries"]
    if not isinstance(queries, dict) or not queries or len(queries) > 20:
        parser.error("recipe requires 1..20 named queries")
    specs = {name: HistoryQuerySpec.from_arguments(value) for name, value in queries.items()}
    if any(not isinstance(name, str) or not name.isidentifier() for name in specs):
        parser.error("query names must be identifiers, not file paths")
    if not args.db.is_file():
        parser.error("database missing")
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "recipe_sha256": digest(args.recipe), "artifact_root": str(args.output.resolve()),
        "db_path": str(args.db.resolve()), "information_cutoff": recipe["information_cutoff"],
        "read_only": True,
        "entry": "HistoryQuery service + model projection; NOT live LLM/Workbench E2E or independent arithmetic",
        "code_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                        sorted((ROOT / "intelligence/services/historical_research").glob("*.py"))},
        "results": {},
    }
    failures = False
    for name, spec in specs.items():
        try:
            payload = HistoryQuery(args.db).run(spec, information_cutoff=cutoff,
                                               deadline=ResearchDeadline.from_timeout(30))
            artifact = args.output / f"{name}.json"
            artifact.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
            blocks = _model_projection(payload, "run/history-query-" + "a" * 64 + ".json")
            omissions = [json.loads(block[1]) for block in blocks
                         if json.loads(block[1]).get("projection_status")]
            failures |= bool(omissions)
            receipt["results"][name] = {
                "query_id": payload["query_id"], "artifact_sha256": digest(artifact),
                "matched": payload["total_matched"], "preview_count": payload["returned_count"],
                "model_blocks": len(blocks), "model_omissions": omissions, "gaps": payload["gaps"],
                "universe": {k: v for k, v in payload.get("universe", {}).items() if k != "entity_codes"},
                "preview": [{k: v for k, v in row.items() if k not in ("path", "feature_coverage")}
                            for row in payload["preview"]],
            }
        except (ValueError, OSError) as exc:
            failures = True
            receipt["results"][name] = {"error": str(exc), "type": type(exc).__name__}
    (args.output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output / "receipt.json")
    return int(failures)


if __name__ == "__main__":
    raise SystemExit(main())
