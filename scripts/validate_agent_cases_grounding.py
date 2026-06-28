from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "intelligence" / "eval" / "cases" / "agent_cases.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def entity_concepts(entities: dict[str, Any], name: str) -> set[str]:
    payload = entities.get(name)
    if not isinstance(payload, dict):
        return set()
    concepts = payload.get("concepts", {})
    return set(concepts.keys()) if isinstance(concepts, dict) else set()


def exposed_to_any(entities: dict[str, Any], name: str, concepts: list[str]) -> bool:
    keys = entity_concepts(entities, name)
    return any(c in keys for c in concepts)


def validate_case(case: dict[str, Any], entities: dict[str, Any], graph_concepts: set[str]) -> dict[str, Any]:
    concepts = [str(c) for c in case.get("expect_concepts", [])]
    gate = float(case.get("entity_recall_gate", 0.5))
    concept_missing = [c for c in concepts if c not in graph_concepts]

    expect = [str(e) for e in case.get("expect_entities", [])]
    expect_hit = [e for e in expect if exposed_to_any(entities, e, concepts)]
    expect_miss = [e for e in expect if e not in expect_hit]
    expect_rate = (len(expect_hit) / len(expect)) if expect else 1.0

    forbid = [str(e) for e in case.get("forbid_entities", [])]
    # A forbid entity is only meaningful if it is a real KB entity that is simply
    # NOT in this theme. If it appears under one of the case concepts, the case is
    # mislabeled (the "trap" is actually a constituent) -> violation.
    forbid_violations = [e for e in forbid if exposed_to_any(entities, e, concepts)]
    forbid_unknown = [e for e in forbid if e not in entities]

    ok = (not concept_missing) and (expect_rate >= gate) and (not forbid_violations)
    return {
        "id": case.get("id"),
        "concepts": concepts,
        "concept_missing": concept_missing,
        "expect_total": len(expect),
        "expect_hit": expect_hit,
        "expect_miss": expect_miss,
        "expect_rate": round(expect_rate, 4),
        "entity_recall_gate": gate,
        "rate_ok": expect_rate >= gate,
        "forbid_violations": forbid_violations,
        "forbid_unknown": forbid_unknown,
        "ok": ok,
    }


def validate_grounding(cases: list[dict[str, Any]], entities: dict[str, Any], graph_concepts: set[str]) -> dict[str, Any]:
    results = [validate_case(case, entities, graph_concepts) for case in cases]
    return {
        "case_count": len(results),
        "passed": all(r["ok"] for r in results),
        "failed_ids": [r["id"] for r in results if not r["ok"]],
        "cases": results,
    }


def case_to_grounding_dict(case: Any) -> dict[str, Any]:
    """Normalize a case (dict or CaseSpec-like object) into the validator shape."""
    def get(key: str, default: Any) -> Any:
        if isinstance(case, dict):
            return case.get(key, default)
        return getattr(case, key, default)

    return {
        "id": get("id", None),
        "expect_concepts": list(get("expect_concepts", []) or []),
        "expect_entities": list(get("expect_entities", []) or []),
        "forbid_entities": list(get("forbid_entities", []) or []),
        "entity_recall_gate": float(get("entity_recall_gate", 0.5) or 0.5),
    }


def grounding_report_for_kb(cases: list[Any], kb_wiki: str | Path) -> dict[str, Any] | None:
    """Validate cases against a KB wiki root. Returns ``None`` (skip) when the KB
    relations are not present, so offline callers degrade gracefully."""
    rel = Path(kb_wiki).expanduser() / "relations"
    entity_file = rel / "entity_exposures.json"
    concept_file = rel / "concept_graph.json"
    if not (entity_file.exists() and concept_file.exists()):
        return None
    entities = load_json(entity_file).get("entities", {})
    graph_concepts = set(load_json(concept_file).get("concepts", {}))
    case_dicts = [case_to_grounding_dict(c) for c in cases]
    return validate_grounding(case_dicts, entities, graph_concepts)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Cases Grounding Validation",
        "",
        f"- **case_count**: {report['case_count']}",
        f"- **passed**: {report['passed']}",
        f"- **failed_ids**: `{json.dumps(report['failed_ids'], ensure_ascii=False)}`",
        "",
        "| case | ok | concept缺失 | expect命中 | 命中率 | 闸 | forbid违规 | forbid未知 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report["cases"]:
        lines.append(
            "| {id} | {ok} | {cm} | {hit}/{tot} | {rate:.0%} | {gate:.0%} | {viol} | {unk} |".format(
                id=r["id"],
                ok="✅" if r["ok"] else "❌",
                cm="、".join(r["concept_missing"]) or "-",
                hit=len(r["expect_hit"]),
                tot=r["expect_total"],
                rate=r["expect_rate"],
                gate=r["entity_recall_gate"],
                viol="、".join(r["forbid_violations"]) or "-",
                unk="、".join(r["forbid_unknown"]) or "-",
            )
        )
    lines.append("")
    return "\n".join(lines)


def resolve_kb_wiki(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    sys.path.insert(0, str(ROOT))
    from intelligence.paths import default_paths

    return default_paths().knowledge_wiki


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate that agent eval cases are grounded in the knowledge base")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--kb-wiki", default=None, help="Knowledge wiki root (contains relations/); default env/auto")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wiki = resolve_kb_wiki(args.kb_wiki)
    rel = wiki / "relations"
    entities = load_json(rel / "entity_exposures.json").get("entities", {})
    graph_concepts = set(load_json(rel / "concept_graph.json").get("concepts", {}))
    cases = load_json(Path(args.cases).expanduser()).get("cases", [])
    report = validate_grounding(cases, entities, graph_concepts)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
