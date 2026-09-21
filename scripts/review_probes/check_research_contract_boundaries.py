"""Prove regression tests detect lost requirements and renumbered citations.

Run from the repository root with the workbench Python:
    python scripts/review_probes/check_research_contract_boundaries.py --output DIR

Each mutation runs in a fresh, network-blocked pytest process. Only imported
objects are replaced; repository source and production records are never edited.
DIR must be new. Results include source fingerprints, logs, and JUnit reports.
This is author-side regression sensitivity, not independent or model evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BOUNDARIES = "intelligence/tests/test_research_request_boundaries.py"
CITATIONS = "intelligence/tests/test_public_citation_identity.py"
REQUIREMENTS = "intelligence/tests/test_research_requirement_review.py"
TARGETS = {
    "checklist": f"{BOUNDARIES}::test_frozen_request_keeps_every_requirement_and_its_context[q3]",
    "ranking_target": f"{BOUNDARIES}::test_non_company_ranking_does_not_require_company_matrix",
    "ranking_mixed": f"{BOUNDARIES}::test_real_company_ranking_still_routes",
    "citation_ordinal": f"{CITATIONS}::test_filtered_first_record_does_not_renumber_public_answer",
    "citation_storage": f"{CITATIONS}::test_ledger_identity_survives_filters_duplicate_labels_and_duplicate_hashes",
    "requirement_receipt": f"{REQUIREMENTS}::test_invalid_or_incomplete_receipts_fail_closed[unknown_witness]",
    "requirement_coverage": f"{REQUIREMENTS}::test_missing_branch_preserves_prose_and_downgrades_completion_without_retrieval",
    "requirement_projection": f"{REQUIREMENTS}::test_adapter_final_projection_revokes_receipt_and_preserves_publication_notice",
    "requirement_repair_notes": f"{REQUIREMENTS}::test_real_repair_consumer_receives_original_gap_but_no_new_permission",
    "requirement_repair_budget": f"{REQUIREMENTS}::test_adapter_reenters_once_and_rejudges_without_expanding_tool_budget",
}
SOURCES = (
    "intelligence/services/user_task.py",
    "intelligence/services/ranking_contract.py",
    "intelligence/services/episode_protocol.py",
    "intelligence/services/episode_semantic_verifier.py",
    "intelligence/runtime/continuous_turn_adapter.py",
    "intelligence/runtime/conversation_orchestrator.py",
    "intelligence/services/research_requirement_review.py",
    "intelligence/services/answer_model.py",
    "intelligence/services/repair_coordinator.py",
    "intelligence/services/research_harness.py",
    BOUNDARIES,
    CITATIONS,
    REQUIREMENTS,
    "scripts/review_probes/check_research_contract_boundaries.py",
)


def fingerprint() -> dict[str, str]:
    paths = [ROOT / name for name in SOURCES]
    paths.extend(sorted((ROOT / "intelligence/tests/fixtures/research_requests_0921").glob("*.txt")))
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def block_network(event: str, _args: tuple) -> None:
    if event == "socket.connect":
        raise RuntimeError("offline regression: network connection forbidden")


class Mutation:
    def __init__(self, name: str):
        self.name = name

    def pytest_runtest_makereport(self, item, call):
        if call.when == "call" and call.excinfo is not None:
            item.user_properties.append((
                "probe_assertion_failure", isinstance(call.excinfo.value, AssertionError),
            ))

    def pytest_sessionstart(self, session):
        # conftest has isolated personal state before production imports occur.
        from intelligence.services import ranking_contract, user_task
        from intelligence.runtime import continuous_turn_adapter, conversation_orchestrator

        if self.name == "checklist":
            user_task._request_checklist_ranges = lambda *_args: {}
        elif self.name == "ranking_target":
            ranking_contract._NON_COMPANY_TARGET_RE = re.compile(r"(?!)")
        elif self.name == "ranking_mixed":
            original = ranking_contract.parse_ranking_intent
            ranking_contract.parse_ranking_intent = lambda query, question_type=None: (
                not ranking_contract._NON_COMPANY_TARGET_RE.search(query)
                and original(query, question_type)
            )
        elif self.name == "citation_ordinal":
            original = continuous_turn_adapter._public_citation_projection
            continuous_turn_adapter._public_citation_projection = lambda *args, **kwargs: tuple(
                dict(row, evidence_id=f"E{index}")
                for index, row in enumerate(original(*args, **kwargs), 1)
            )
        elif self.name == "citation_storage":
            original = conversation_orchestrator._sanitize_citation_list
            conversation_orchestrator._sanitize_citation_list = lambda rows: original([
                {key: value for key, value in row.items() if key != "evidence_id"}
                for row in rows
            ])
        elif self.name.startswith("requirement_"):
            from dataclasses import replace
            from intelligence.services import episode_semantic_verifier, repair_coordinator, research_requirement_review

            if self.name == "requirement_receipt":
                episode_semantic_verifier.reconcile_requirement_checks = lambda *_args: ()
            elif self.name in {"requirement_coverage", "requirement_projection"}:
                original = episode_semantic_verifier.recheck_research_requirement_delivery
                replacement = (
                    (lambda outcome, **_kwargs: outcome) if self.name == "requirement_coverage"
                    else (lambda outcome, **_kwargs: original(outcome))
                )
                episode_semantic_verifier.recheck_research_requirement_delivery = replacement
                continuous_turn_adapter.recheck_research_requirement_delivery = replacement
            elif self.name == "requirement_repair_notes":
                research_requirement_review.requirement_repair_notes = lambda *_args: ()
            elif self.name == "requirement_repair_budget":
                original = repair_coordinator.classify_repair_failure
                repair_coordinator.classify_repair_failure = lambda *args, **kwargs: replace(
                    original(*args, **kwargs), contract_rewrite=False,
                )
            else:
                raise ValueError(self.name)
        elif self.name != "baseline":
            raise ValueError(self.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", choices=("baseline", *TARGETS))
    args, pytest_args = parser.parse_known_args()
    if args.child:
        import pytest

        sys.addaudithook(block_network)
        return int(pytest.main(pytest_args, plugins=[Mutation(args.child)]))
    if not args.output or pytest_args:
        parser.error("--output is required; unexpected arguments are not accepted")
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    before = fingerprint()
    report = {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "status": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
        "python": sys.executable,
        "source_sha256": before,
        "runs": [],
        "complete": False,
    }
    env = dict(os.environ, FWP_TEST_RECEIPT="0", PYTHONDONTWRITEBYTECODE="1")
    try:
        for label, mutation in [("baseline", "baseline"), *[(key, key) for key in TARGETS], ("restored", "baseline")]:
            junit = out / f"{label}.xml"
            targets = [BOUNDARIES, CITATIONS, REQUIREMENTS] if mutation == "baseline" else [TARGETS[mutation]]
            command = [sys.executable, str(Path(__file__).resolve()), "--child", mutation,
                       "-q", "--tb=short", "-p", "no:cacheprovider", "--junitxml", str(junit), *targets]
            proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=180)
            (out / f"{label}.txt").write_text(proc.stdout + "\nSTDERR:\n" + proc.stderr, encoding="utf-8")
            cases = list(ET.parse(junit).getroot().iter("testcase"))
            failures = [case.find("failure") for case in cases if case.find("failure") is not None]
            result = {
                "label": label, "command": command, "exit": proc.returncode,
                "cases": len(cases), "failures": len(failures),
                "errors": sum(case.find("error") is not None for case in cases),
                "skipped": sum(case.find("skipped") is not None for case in cases),
                "assertion_failures": sum(
                    case.find("failure") is not None and any(
                        prop.get("name") == "probe_assertion_failure" and prop.get("value") == "True"
                        for prop in case.findall("properties/property")
                    )
                    for case in cases
                ),
            }
            report["runs"].append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            assert cases and result["errors"] == result["skipped"] == 0, result
            red = mutation != "baseline"
            assert proc.returncode == (1 if red else 0), result
            assert (len(failures) > 0) == red, result
            assert result["assertion_failures"] == len(failures), result
        assert fingerprint() == before, "source changed during probe"
        report["complete"] = True
    finally:
        report["source_unchanged"] = fingerprint() == before
        (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
