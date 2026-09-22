"""Two open disclosure leads: unlisted venue attribution and unlisted absence wording.

Both were raised by the ARL-0005 review as fragments, completed by the producer,
and are still listed as uncovered in the product door. This probe pins them as
executable counterexamples on an exact clean revision instead of prose.

Lead 1 (false positive): an independently attributed sentence whose venue is not
in the finite attribution list is deleted together with the rejected inference.
Lead 2 (false negative): '本期无任何披露文件' states the same absence as
'零披露' but is outside the absence vocabulary, so the inference survives.

Paired controls use the listed venue and the listed absence wording, so a
failure cannot be explained by the checker being off. Runs the real
SemanticEpisodeVerifier plus the final recheck; judge=llm is a deterministic
success stub, NOT natural answer quality. No network, model, fetch or mutation.
Exit 0=all pass, 1=behavioral failure (expected today), 2=identity/execution error.
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


REJECTED = "因此公司没有公告"
# (name, draft, kind, origin)
CASES = (
    (
        "unlisted-venue-attribution",
        "收入可核[E1]，查询返回空白，因此公司没有公告，深交所互动易显示本期没有公告[E2]。",
        "attributed",
        "review-fragment-completed-by-producer",
    ),
    (
        "listed-venue-control",
        "收入可核[E1]，查询返回空白，因此公司没有公告，巨潮资讯网显示本期没有公告[E2]。",
        "attributed",
        "control-listed-venue",
    ),
    (
        "unlisted-absence-wording",
        "收入可核[E1]，查询返回空白，因此本期无任何披露文件。",
        "absence",
        "review-fragment-completed-by-producer",
    ),
    (
        "listed-absence-control",
        "收入可核[E1]，查询返回空白，因此本期为零披露。",
        "absence",
        "control-listed-wording",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    args = parser.parse_args()
    root = args.code_root.resolve()
    report = {
        "scope": "two uncovered disclosure leads; finite engineering counterexample, not natural answer acceptance",
        "model_calls": 0,
        "network_calls": 0,
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
        report["fixture_sha256"] = hashlib.sha256(
            Path(financial_fixture.__file__).read_bytes()
        ).hexdigest()
        cases = []
        for mode in ("off", "llm"):
            for name, draft, kind, origin in CASES:
                frame, structural = fixture._structural(
                    draft, detail="收入可核。", traces=(financial_fixture.TRACE,)
                )
                first = structural.outcome.evidence[0]
                # A second, independently sourced card so citation retention is
                # observable; it is never bound to the rejected inference.
                structural = replace(structural, outcome=replace(
                    structural.outcome,
                    evidence=(first, replace(
                        first,
                        content_hash="venue-fixture",
                        title="披露来源夹具",
                        detail="本期没有公告",
                    )),
                ))
                findings = checks.disclosure_absence_findings(
                    draft, structural.outcome.traces
                )
                with patch.dict("os.environ", {"ASK_SEMANTIC_JUDGE": mode}):
                    result = verifier.SemanticEpisodeVerifier(judge_fn=lambda request: {
                        "passed": True, "rejected_sentence_indexes": [], "issues": [],
                    }).verify(
                        frame=frame,
                        structurally_verified=structural,
                        deadline=ResearchDeadline.from_timeout(10),
                    )
                attributed_clause = draft.split("，")[-1].rstrip("。")
                expectations = {
                    "fixture_structurally_complete": structural.verified_status == "completed",
                    "independent_income_retained": "收入可核[E1]" in result.public_answer,
                    "draft_and_evidence_unchanged": result.verified.outcome == structural.outcome,
                    "final_recheck_idempotent":
                        verifier.recheck_material_public_delivery(result) == result,
                    "local_check_exercised": bool(findings),
                    "unverified_not_completed": result.status == "partial",
                    "same_turn_repair_requested": bool(
                        result.gap_output_ids and result.repair_output_ids
                    ),
                }
                if kind == "attributed":
                    expectations["rejected_inference_removed"] = (
                        REJECTED not in result.public_answer
                    )
                    # An independently attributed statement must survive the
                    # removal of a neighboring invalid inference.
                    expectations["attributed_fact_and_citation_retained"] = (
                        attributed_clause in result.public_answer
                        and "[E2]" in result.public_answer
                    )
                else:
                    expectations["absence_inference_removed"] = (
                        attributed_clause not in result.public_answer
                    )
                cases.append({
                    "name": name,
                    "kind": kind,
                    "input_origin": origin,
                    "control": origin.startswith("control"),
                    "draft": draft,
                    "judge_mode": mode,
                    "judge_stubbed": mode == "llm",
                    "local_codes": [f.code for f in findings],
                    "public_answer": result.public_answer,
                    "status": result.status,
                    "checks": expectations,
                    "passed": all(expectations.values()),
                })
        after = _identity(root)
        report.update(after=after, target_unchanged=before == after, cases=cases)
        if before != after:
            raise ValueError("target_changed")
        passed = sum(case["passed"] for case in cases)
        report.update(
            passed=passed,
            failed=len(cases) - passed,
            status="passed" if passed == len(cases) else "not_passed",
            controls_passed=sum(c["passed"] for c in cases if c["control"]),
            controls_total=sum(1 for c in cases if c["control"]),
        )
    except Exception as exc:
        report.update(status="error", error_type=type(exc).__name__, error=str(exc)[:200])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
