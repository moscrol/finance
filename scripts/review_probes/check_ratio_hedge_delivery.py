"""ARL-0003 blocker: a '待核对' hedge must not certify a later ratio value.

Read-only finite probe through the real verifier and final recheck. Judge llm
is a deterministic success stub, not a natural model answer. No network/model.
Uses the existing retention probe's clean-revision/hash identity guard.
Exit 0=all cases pass; 1=behavioral failure; 2=target/identity/execution error.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from check_delivery_fact_retention import _identity


DRAFTS = (
    "收入可核[E1]，2026中报含金量待核对，实际为1.587。",
    "收入可核[E1]，2026中报含金量为待核对，实际为1.587。",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    args = parser.parse_args()
    root = args.code_root.resolve()
    report = {"scope": "ARL-0003 finite real-exit counterexample; not natural QA",
              "model_calls": 0, "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
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
            for draft in DRAFTS:
                frame, structural = fixture._structural(draft, detail="收入可核。", traces=(financial_fixture.TRACE,))
                structural = replace(structural, outcome=replace(
                    structural.outcome, evidence=(*structural.outcome.evidence, *financial_fixture._financial_evidence()),
                ))
                with patch.dict("os.environ", {"ASK_SEMANTIC_JUDGE": mode}):
                    result = verifier.SemanticEpisodeVerifier(judge_fn=lambda request: {
                        "passed": True, "rejected_sentence_indexes": [], "issues": [],
                    }).verify(frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(10))
                expectations = {
                    "local_check_exercised": bool(checks.calculation_copy_findings(draft, structural.outcome.evidence)),
                    "unverified_not_completed": result.status == "partial",
                    "same_turn_repair_requested": bool(result.gap_output_ids and result.repair_output_ids and result.delivery_repair_notes),
                    "wrong_value_withheld_or_explicitly_unverified": "1.587" not in result.public_answer or (
                        "〔比率对应关系待核对〕" in result.public_answer and "不能视为已核算结论" in result.public_answer
                    ),
                    "fact_and_citation_retained": "收入可核[E1]" in result.public_answer,
                    "draft_and_evidence_unchanged": result.verified.outcome == structural.outcome,
                    "final_recheck_idempotent": verifier.recheck_material_public_delivery(result) == result,
                }
                cases.append({"draft": draft, "judge_mode": mode, "judge_stubbed": mode == "llm",
                              "public_answer": result.public_answer, "status": result.status,
                              "checks": expectations, "passed": all(expectations.values())})
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
