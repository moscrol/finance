"""Fail when local claim rejection also erases an independently sourced fact.

A punctuation-only counterexample: identical fact/citation + false inference,
joined by a full stop, semicolon or comma. Runs the actual semantic verifier
with its judge disabled or replaced by a deterministic success response; no
model, network, data fetch, production service or source mutation is involved.
This is a finite engineering check, NOT a natural-answer quality evaluation.

Usage: .venv-workbench/bin/python scripts/review_probes/check_delivery_fact_retention.py
       --code-root CLEAN_WORKTREE [--expect-revision FULL_SHA]
Prints JSON only. Exit 0 = all six cases pass, 1 = behavioral rejection,
2 = invalid/dirty target or execution error. A known failure is never xfailed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


FACT = "中报原文披露了收入"
FALSE_INFERENCE = "但查询返回空白，因此公司没有公告。"
SOURCES = (
    "intelligence/services/research_delivery_checks.py",
    "intelligence/services/episode_semantic_verifier.py",
    "intelligence/tests/test_episode_semantic_verifier.py",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _identity(root: Path) -> dict:
    return {
        "code_root": str(root),
        "revision": _git(root, "rev-parse", "HEAD"),
        "status": _git(root, "status", "--porcelain"),
        "source_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in SOURCES
        },
    }


def _run_cases(root: Path) -> list[dict]:
    sys.path.insert(0, str(root))
    from intelligence.services import episode_semantic_verifier as verifier
    from intelligence.services import research_delivery_checks as checks
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.tests import test_episode_semantic_verifier as fixture

    # Do not silently test a different import root than the recorded Git target.
    for module, name in zip((checks, verifier, fixture), SOURCES):
        if Path(module.__file__).resolve() != (root / name).resolve():
            raise RuntimeError("import_root_mismatch")
    trace = ProviderTrace(
        provider="agent:l3_lookup", capability="l3_lookup", status="request_error"
    )
    cases = []
    for mode in ("off", "llm"):
        for separator in ("。", "；", "，"):
            draft = f"{FACT}[E1]{separator}{FALSE_INFERENCE}"
            frame, structural = fixture._structural(
                draft, detail=f"{FACT}。", title="中报原文", source="fixture",
                traces=(trace,),
            )
            with patch.dict("os.environ", {"ASK_SEMANTIC_JUDGE": mode}):
                result = verifier.SemanticEpisodeVerifier(
                    judge_fn=lambda request: {
                        "passed": True, "rejected_sentence_indexes": [], "issues": [],
                    }
                ).verify(
                    frame=frame, structurally_verified=structural,
                    deadline=ResearchDeadline.from_timeout(10),
                )
            expectations = {
                "fixture_structurally_complete": structural.verified_status == "completed",
                "false_inference_rejected": "因此公司没有公告" not in result.public_answer,
                "independent_fact_retained": FACT in result.public_answer,
                "explicit_citation_retained": "[E1]" in result.public_answer,
                "bound_evidence_retained": result.delivery_retained_evidence_hashes
                    == (structural.outcome.evidence[0].content_hash,),
                "original_evidence_unchanged": result.verified.outcome.evidence
                    == structural.outcome.evidence,
                "coverage_gap_explained": "不能据此断言公司没有公告" in result.public_answer,
                "failure_not_upgraded": result.status == "partial",
                "local_check_exercised": any(
                    "disclosure_absence_inference" in issue for issue in result.issues
                ),
                "final_recheck_idempotent": verifier.recheck_material_public_delivery(result)
                    == result,
            }
            cases.append({
                "judge_mode": mode, "judge_stubbed": mode == "llm",
                "separator": separator, "draft": draft,
                "public_answer": result.public_answer,
                "status": result.status, "checks": expectations,
                "passed": all(expectations.values()),
            })
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--expect-revision")
    args = parser.parse_args(argv)
    root = args.code_root.expanduser().resolve()
    report = {
        "scope": "finite_engineering_counterexample_not_natural_answer_acceptance",
        "model_calls": 0,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    try:
        before = _identity(root)
        report["before"] = before
        if before["status"]:
            raise ValueError("target_must_be_clean")
        if args.expect_revision and before["revision"] != args.expect_revision:
            raise ValueError("target_revision_mismatch")
        cases = _run_cases(root)
        after = _identity(root)
        report.update(after=after, target_unchanged=after == before, cases=cases)
        if after != before:
            raise RuntimeError("target_changed_during_probe")
        passed = sum(case["passed"] for case in cases)
        report.update(
            status="passed" if passed == len(cases) else "not_passed",
            passed=passed, failed=len(cases) - passed,
        )
    except Exception as exc:
        report.update(status="error", error_type=type(exc).__name__)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
