"""Reproduce ARL-0005's quarantined leads, not its invalid verdict authority.

Finite, read-only counterexamples through the real semantic/public verifier.
Three complete review sentences are verbatim. The count case expands the
review's abbreviated prefix; this is an explicit producer reconstruction.
The formatted-marker case completes the review's marker-only fragment with a
matching period/value: fixing a marker must not erase the underlying unknown.
No network/model; judge=llm is a deterministic success stub, not natural QA.
Two existing controls stay separate. Exit 0=all pass, 1=behavior failure,
2=identity/execution error. Keep the original failures; no xfail/relaxed oracle.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

from check_delivery_fact_retention import _identity


MARK = "〔比率对应关系待核对〕"
CASES = (
    ("independent-percent-delta", "2026中报含金量为1.588，同比增长12%。", "preserve", None, "review-verbatim"),
    ("independent-count", "2026中报含金量为1.588，样本量120。", "preserve", None, "review-ellipsis-prefix-expanded"),
    ("explicit-basis-points", "2026中报含金量实际为158.7bp。", "withhold", "158.7", "review-verbatim"),
    ("anaphoric-semicolon", "收入可核[E1]，2026中报含金量待核对；该比率为1.587。", "withhold", "1.587", "review-verbatim"),
    ("formatted-uncertainty-marker", "〔比率对应关系**待核对**〕2026中报含金量为1.588。", "marker", None, "review-marker-fragment-completed-with-matching-ratio"),
)
CONTROLS = (
    ("matching-ratio", "2026中报含金量为1.588。", "preserve", None, "existing-control"),
    ("explicit-semicolon", "收入可核[E1]，2026中报含金量待核对；实际为1.587。", "withhold", "1.587", "existing-control"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    args = parser.parse_args()
    root = args.code_root.resolve()
    report = {
        "scope": "ARL-0005 invalid-output leads, finite engineering reproduction only",
        "model_calls": 0,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    try:
        before = _identity(root)
        report["before"] = before
        if before["status"] or before["revision"] != args.expect_revision:
            raise ValueError("clean_exact_revision_required")
        sys.path.insert(0, str(root))
        from intelligence.services import episode_semantic_verifier as verifier
        from intelligence.services import research_delivery_checks as checks
        from intelligence.services.research_contract import ResearchDeadline
        from intelligence.tests import test_episode_semantic_verifier as fixture
        from intelligence.tests import test_research_delivery_checks as financial_fixture
        for module in (verifier, checks, fixture, financial_fixture):
            if not Path(module.__file__).resolve().is_relative_to(root):
                raise ValueError("import_root_mismatch")
        report["financial_fixture_sha256"] = hashlib.sha256(Path(financial_fixture.__file__).read_bytes()).hexdigest()
        cases = []
        for mode in ("off", "llm"):
            for name, draft, behavior, wrong, origin in (*CASES, *CONTROLS):
                frame, structural = fixture._structural(draft, detail="收入可核。", traces=(financial_fixture.TRACE,))
                structural = replace(structural, outcome=replace(
                    structural.outcome, evidence=(*structural.outcome.evidence, *financial_fixture._financial_evidence()),
                ))
                findings = checks.calculation_copy_findings(draft, structural.outcome.evidence)
                local_repaired = checks.remove_findings(draft, findings)
                with patch.dict("os.environ", {"ASK_SEMANTIC_JUDGE": mode}):
                    result = verifier.SemanticEpisodeVerifier(judge_fn=lambda request: {
                        "passed": True, "rejected_sentence_indexes": [], "issues": [],
                    }).verify(frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(10))
                expectations = {
                    "fixture_structurally_complete": structural.verified_status == "completed",
                    "draft_and_evidence_unchanged": result.verified.outcome == structural.outcome,
                    "final_recheck_idempotent": verifier.recheck_material_public_delivery(result) == result,
                    "explicit_citation_retained": "[E1]" not in draft or "[E1]" in result.public_answer,
                }
                if behavior == "preserve":
                    expectations.update(
                        no_false_local_gap=not findings,
                        no_false_partial=result.status == "completed",
                        independent_content_unchanged=result.public_answer == draft,
                        no_unnecessary_repair=not result.repair_output_ids and not result.delivery_repair_notes,
                    )
                else:
                    expectations.update(
                        local_check_exercised=bool(findings),
                        unverified_not_completed=result.status == "partial",
                        same_turn_repair_requested=bool(result.gap_output_ids and result.repair_output_ids and result.delivery_repair_notes),
                    )
                    if behavior == "withhold":
                        expectations["wrong_value_withheld_or_explicitly_unverified"] = wrong not in result.public_answer or (
                            MARK in result.public_answer and "不能视为已核算结论" in result.public_answer
                        )
                    else:
                        # One formatted marker already states uncertainty; do not add
                        # a second plain one or silently certify by removing both.
                        expectations.update(
                            first_local_edit_does_not_duplicate_marker=local_repaired == draft,
                            exactly_one_visible_marker=re.sub(r"[*`]+", "", result.public_answer).count(MARK) == 1,
                            existing_marker_and_value_retained=draft in result.public_answer,
                        )
                cases.append({
                    "name": name, "control": name in {c[0] for c in CONTROLS},
                    "draft": draft, "input_origin": origin,
                    "judge_mode": mode, "judge_stubbed": mode == "llm",
                    "local_codes": [f.code for f in findings], "local_repaired": local_repaired,
                    "public_answer": result.public_answer, "status": result.status,
                    "gap_output_ids": list(result.gap_output_ids),
                    "repair_output_ids": list(result.repair_output_ids),
                    "delivery_repair_notes": list(result.delivery_repair_notes),
                    "checks": expectations, "passed": all(expectations.values()),
                })
        after = _identity(root)
        report.update(after=after, target_unchanged=before == after, cases=cases)
        if before != after:
            raise ValueError("target_changed")
        passed = sum(case["passed"] for case in cases)
        report.update(passed=passed, failed=len(cases) - passed, status="passed" if passed == len(cases) else "not_passed")
    except Exception as exc:
        report.update(status="error", error_type=type(exc).__name__)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
