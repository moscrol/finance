from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _numbered_sentences,
)


CASES_PATH = (
    Path(__file__).parents[1] / "eval" / "cases" / "research_semantic_counterexamples.json"
)


def _cases() -> list[dict[str, object]]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    cases = payload.get("cases")
    assert isinstance(cases, list)
    return cases


def _variants() -> list[tuple[str, dict[str, object], dict[str, object]]]:
    rows = []
    for case in _cases():
        case_id = str(case["id"])
        variants = case["variants"]
        assert isinstance(variants, list)
        for variant in variants:
            assert isinstance(variant, dict)
            rows.append((case_id, case, variant))
    return rows


def test_counterexample_corpus_is_explicit_and_self_consistent() -> None:
    cases = _cases()
    case_ids = [str(case["id"]) for case in cases]
    assert len(case_ids) == len(set(case_ids))
    assert len(cases) >= 8

    for case in cases:
        assert set(case) == {
            "id",
            "finding",
            "source_anchor",
            "question",
            "evidence",
            "variants",
        }
        assert isinstance(case["source_anchor"], str) and case["source_anchor"].strip()
        evidence = case["evidence"]
        assert isinstance(evidence, list) and evidence
        for item in evidence:
            assert set(item) == {"title", "detail"}
            assert item["title"] and item["detail"]

        variants = case["variants"]
        assert isinstance(variants, list) and {item["id"] for item in variants} == {
            "bad",
            "acceptable",
        }
        for variant in variants:
            assert set(variant) == {
                "id",
                "draft",
                "expected_rejected",
                "expected_reason_codes",
                "expected_requirement_statuses",
                "witnesses",
                "rationale",
            }
            sentences = _numbered_sentences(str(variant["draft"]))
            content_indexes = [
                int(row["index"])
                for row in sentences
                if not str(row["text"]).strip().startswith("[E")
            ]
            assert len(content_indexes) == 2
            rejected = variant["expected_rejected"]
            assert isinstance(rejected, list)
            # Corpus indexes identify the two content clauses. The production
            # tokenizer keeps a trailing [E...] marker as its own numbered row.
            assert all(isinstance(index, int) and index in {1, 2} for index in rejected)
            assert len(rejected) == len(set(rejected))
            reason_codes = variant["expected_reason_codes"]
            assert isinstance(reason_codes, dict)
            assert {int(index) for index in reason_codes} == set(rejected)
            statuses = variant["expected_requirement_statuses"]
            witnesses = variant["witnesses"]
            assert isinstance(statuses, list) and len(statuses) == 2
            assert isinstance(witnesses, list) and len(witnesses) == 2
            for status, witness in zip(statuses, witnesses, strict=True):
                assert status in {"fulfilled", "partial", "missing"}
                assert isinstance(witness, list)
                assert (status == "missing") == (not witness)
            assert isinstance(variant["rationale"], str) and variant["rationale"].strip()


def test_expected_sentence_verdicts_are_accepted_by_existing_report_protocol() -> None:
    """The corpus tests the wire contract, not a hidden semantic oracle."""
    for case_id, _case, variant in _variants():
        sentences = _numbered_sentences(str(variant["draft"]))
        content_indexes = [
            int(row["index"])
            for row in sentences
            if not str(row["text"]).strip().startswith("[E")
        ]
        clause_indexes = tuple(int(index) for index in variant["expected_rejected"])
        rejected = tuple(content_indexes[index - 1] for index in clause_indexes)
        reason_codes = variant["expected_reason_codes"]
        payload = {
            "passed": not rejected,
            "rejected_sentence_indexes": list(rejected),
            "issues": [f"第{index}句：离线预期反例" for index in rejected],
            "reason_codes": [
                {
                    "sentence_index": content_indexes[int(index) - 1],
                    "code": str(code),
                }
                for index, code in reason_codes.items()
            ],
        }
        report = SemanticEpisodeVerifier._parse_report(
            payload,
            len(sentences),
            sentences=sentences,
        )
        assert report is not None, case_id
        assert report.passed is (not rejected)
        assert report.rejected_sentence_indexes == rejected
        assert report.reason_code_by_index == {
            content_indexes[int(index) - 1]: str(code)
            for index, code in reason_codes.items()
        }


def test_k3_condition_drift_is_a_delivery_gap_not_a_fact_rejection() -> None:
    case = next(item for item in _cases() if item["id"] == "K3-summary-condition-drift")
    bad = next(item for item in case["variants"] if item["id"] == "bad")

    assert bad["expected_rejected"] == []
    assert bad["expected_reason_codes"] == {}
    assert bad["expected_requirement_statuses"] == ["fulfilled", "partial"]
    assert "订单" in str(bad["rationale"])


@pytest.mark.parametrize("case_id,case,variant", _variants())
def test_bad_and_acceptable_variants_keep_distinct_expected_outcomes(
    case_id: str,
    case: dict[str, object],
    variant: dict[str, object],
) -> None:
    del case
    if variant["id"] == "bad":
        assert case_id != "K3-summary-condition-drift" or variant["expected_rejected"] == []
        assert variant["rationale"]
    else:
        assert variant["expected_rejected"] == []
        assert variant["expected_reason_codes"] == {}
