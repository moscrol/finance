"""Pin ARL-0004's observations despite its invalid PASS/PARTIAL verdict.

Read-only original inputs through the real public verifier and final recheck.
A correct ratio with an independent ordinal/amount/period should not become an
unknown. An explicit wrong ratio must not disappear behind units or punctuation.
The findings are reproduction leads, not valid independent approval. No network
or natural model; judge=llm is a deterministic success stub. Two positive controls
are separate from the six newly reported counterexamples. Exit 0=all assertions
pass, 1=behavior failure, 2=identity/execution error. Do not xfail the red cases.
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


# Original wording from the quarantined ARL-0004 output, not improved paraphrases.
CASES = (
    ("independent-ordinal", "2026中报含金量为1.588，行业排名第3。", "preserve", None),
    ("independent-thousands-amount", "2026中报含金量为1.588，同期经营现金流1,234.56亿元[E1]。", "preserve", None),
    ("neighbor-genitive-period", "2026中报含金量为1.588，2025中报的含金量为0.289。", "preserve", None),
    ("explicit-ratio-currency-unit", "2026中报含金量为1.587元/元。", "withhold", "1.587"),
    ("explicit-ratio-points-unit", "2026中报含金量实际为158.7个百分点。", "withhold", "158.7"),
    ("hedge-semicolon", "收入可核[E1]，2026中报含金量待核对；实际为1.587。", "withhold", "1.587"),
)
CONTROLS = (
    ("matching-ratio", "2026中报含金量为1.588。", "preserve", None),
    ("repaired-comma-hedge", "收入可核[E1]，2026中报含金量待核对，实际为1.587。", "withhold", "1.587"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    args = parser.parse_args()
    root = args.code_root.resolve()
    report = {"scope": "ARL-0004 counterexample reproduction, not valid review or natural QA",
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
            for name, draft, behavior, wrong in (*CASES, *CONTROLS):
                frame, structural = fixture._structural(draft, detail="收入可核。", traces=(financial_fixture.TRACE,))
                structural = replace(structural, outcome=replace(
                    structural.outcome, evidence=(*structural.outcome.evidence, *financial_fixture._financial_evidence()),
                ))
                findings = checks.calculation_copy_findings(draft, structural.outcome.evidence)
                with patch.dict("os.environ", {"ASK_SEMANTIC_JUDGE": mode}):
                    result = verifier.SemanticEpisodeVerifier(judge_fn=lambda request: {
                        "passed": True, "rejected_sentence_indexes": [], "issues": [],
                    }).verify(frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(10))
                expectations = {
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
                        wrong_value_withheld_or_explicitly_unverified=wrong not in result.public_answer or (
                            "〔比率对应关系待核对〕" in result.public_answer and "不能视为已核算结论" in result.public_answer
                        ),
                    )
                cases.append({"name": name, "control": name in {c[0] for c in CONTROLS},
                              "draft": draft, "judge_mode": mode, "judge_stubbed": mode == "llm",
                              "local_codes": [f.code for f in findings], "public_answer": result.public_answer,
                              "status": result.status, "gap_output_ids": list(result.gap_output_ids),
                              "repair_output_ids": list(result.repair_output_ids),
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
