"""Author-proposed semantic examples; scripted reports test plumbing, not an LLM."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess

import pytest

from intelligence.services import episode_semantic_verifier as verifier_module
from intelligence.services import llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeOutcome,
    SemanticEpisodeVerifier,
    _judge_report_tools,
    _judge_system_prompt,
    _numbered_sentences,
    dumps_judge_request,
    recheck_research_requirement_delivery,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_research_requirement_review import _case

CASES_PATH = (
    Path(__file__).parents[1] / "eval/cases/research_semantic_counterexamples.json"
)
CORPUS = json.loads(CASES_PATH.read_text(encoding="utf-8"))
VARIANTS = [
    pytest.param(case, variant, id=f"{case['id']}-{variant['id']}")
    for case in CORPUS["cases"]
    for variant in case["variants"]
]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("counterexample test attempted network, subprocess, or real model")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(llm_refine, "complete", forbidden)
    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: ())
    monkeypatch.setattr(verifier_module, "recheck_enabled", lambda: False)
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")


def _request(case, variant):
    frame, verified = _case(case["question"], variant["draft"])
    evidence = tuple(
        AgentEvidence(
            tool="market_data",
            title=item["title"],
            detail=item["detail"],
            source="synthetic offline fixture, not a financial source",
            source_date=CORPUS["cutoff"],
            content_hash=sha256(
                json.dumps(item, ensure_ascii=False).encode()
            ).hexdigest(),
        )
        for item in case["evidence"]
    )
    outcome = replace(
        verified.outcome,
        evidence=evidence,
        bindings=tuple(
            replace(
                binding, evidence_hashes=tuple(item.content_hash for item in evidence)
            )
            for binding in verified.outcome.bindings
        ),
    )
    verified = verify_episode_outcome(verified.contract, outcome)
    assert verified.verified_status == "completed", verified.issues
    request = SemanticEpisodeVerifier()._judge_request(
        frame, verified, _numbered_sentences(outcome.draft)
    )
    return frame, verified, request


def _scripted_report(request, variant):
    """Labels are deliberately supplied by the test author, never inferred."""
    checks = []
    for row, status, witnesses in zip(
        request["requirement_review"],
        variant["expected_requirement_statuses"],
        variant["witnesses"],
        strict=True,
    ):
        assert len(row["parts"]) == 1
        checks.append(
            {
                "question_id": row["question_id"],
                "parts": [
                    {
                        "part_index": row["parts"][0]["part_index"],
                        "status": status,
                        "answer_sentence_indexes": witnesses,
                        "reason": variant["rationale"],
                        "missing_aspects": []
                        if status == "fulfilled"
                        else [variant["rationale"]],
                    }
                ],
            }
        )
    return {
        "passed": not variant["expected_rejected"],
        "rejected_sentence_indexes": variant["expected_rejected"],
        "issues": [
            f"第{index}句：{variant['rationale']}"
            for index in variant["expected_rejected"]
        ],
        "reason_codes": [
            {"sentence_index": int(index), "code": code}
            for index, code in variant["expected_reason_codes"].items()
        ],
        "requirement_checks": checks,
    }


def _parse(payload, request):
    return SemanticEpisodeVerifier._parse_report(
        payload,
        len(request["sentences"]),
        requirement_review=request["requirement_review"],
        sentences=request["sentences"],
    )


def _statuses(report):
    return [
        part["status"] for row in report.requirement_checks for part in row["parts"]
    ]


def test_corpus_scope_and_pairs_are_explicit():
    assert CORPUS["schema_version"] == 1
    assert CORPUS["scope"] == "offline_adapted_counterexamples"
    assert CORPUS["cutoff"] == "2026-09-21"
    assert (
        CORPUS["provenance"]["status"]
        == "author_proposed_not_independently_adjudicated"
    )
    cases = CORPUS["cases"]
    assert len(cases) == len({case["id"] for case in cases}) == 8
    assert {case["finding"] for case in cases} == {"K2", "K3", "K4", "K5", "K7"}
    for case in cases:
        assert case["source_anchor"].strip()
        assert len(case["variants"]) == 2
        variants = {item["id"]: item for item in case["variants"]}
        assert set(variants) == {"bad", "acceptable"}
        assert variants["bad"]["draft"] != variants["acceptable"]["draft"]
        assert variants["bad"]["expected_requirement_statuses"] == [
            "fulfilled",
            "partial",
        ]
        assert variants["acceptable"]["expected_rejected"] == []
        assert variants["acceptable"]["expected_reason_codes"] == {}
        expected = ["fulfilled", "partial" if case["finding"] == "K2" else "fulfilled"]
        assert variants["acceptable"]["expected_requirement_statuses"] == expected
        if case["finding"] == "K3":
            assert variants["bad"]["expected_rejected"] == []
        else:
            assert variants["bad"]["expected_rejected"] == [2]


@pytest.mark.parametrize("case,variant", VARIANTS)
def test_production_request_carries_original_requirements_and_evidence(case, variant):
    frame, verified, request = _request(case, variant)
    assert request["question"] == case["question"]
    assert request["sentences"] == [
        {"index": index, "text": text}
        for index, text in enumerate(variant["draft"].splitlines(), 1)
    ]
    assert [row["question_id"] for row in request["requirement_review"]] == ["q1", "q2"]
    assert [row["text"] for row in request["requirement_review"]] == [
        question.text for question in frame.material_contract.questions
    ]
    assert [row["parts"] for row in request["requirement_review"]] == [
        [{"part_index": 1, "text": question.text}]
        for question in frame.material_contract.questions
    ]
    for row, original in zip(
        request["evidence_registry"], case["evidence"], strict=True
    ):
        assert row["title"] == original["title"]
        assert row["detail"] == original["detail"]
    assert [row["evidence_id"] for row in request["evidence_registry"]] == ["E1"]
    assert request["output_bindings"][0]["evidence_ids"] == ["E1"]
    serialized = dumps_judge_request(request)
    assert json.loads(serialized) == request
    for item in verified.outcome.evidence:
        assert item.content_hash not in serialized
    assert "expected_rejected" not in serialized and "rationale" not in serialized
    assert (
        "requirement_checks"
        in _judge_report_tools(request)[0]["function"]["parameters"]["required"]
    )
    assert "requirement_checks" in _judge_system_prompt(request)


@pytest.mark.parametrize("case,variant", VARIANTS)
@pytest.mark.parametrize("wire", ["json", "tool", "injected"])
def test_scripted_reports_round_trip_through_existing_consumers(case, variant, wire):
    _, _, request = _request(case, variant)
    payload = _scripted_report(request, variant)
    if wire == "json":
        report = _parse(json.dumps(payload, ensure_ascii=False), request)
    elif wire == "tool":
        report = SemanticEpisodeVerifier._parse_tool_report(
            ModelTurn(
                content="",
                tool_calls=(
                    ModelToolCall("offline", "submit_grounding_report", payload),
                ),
            ),
            len(request["sentences"]),
            requirement_review=request["requirement_review"],
            sentences=request["sentences"],
        )
    else:
        calls = []

        def judge(received):
            calls.append(received)
            return deepcopy(payload)

        call = SemanticEpisodeVerifier._invoke_injected(judge, request, 1, True)
        assert calls == [request]
        assert not call.unavailable
        report = call.report
    assert report is not None
    assert report.passed is (not variant["expected_rejected"])
    assert report.rejected_sentence_indexes == tuple(variant["expected_rejected"])
    assert report.reason_code_by_index == {
        int(index): code for index, code in variant["expected_reason_codes"].items()
    }
    assert _statuses(report) == variant["expected_requirement_statuses"]
    for row, witnesses in zip(
        report.requirement_checks, variant["witnesses"], strict=True
    ):
        assert row["parts"][0]["answer_sentences"] == [
            request["sentences"][index - 1] for index in witnesses
        ]


@pytest.mark.parametrize("case,variant", VARIANTS)
def test_final_delivery_preserves_scripted_coverage_gaps(case, variant):
    _, verified, request = _request(case, variant)
    report = _parse(_scripted_report(request, variant), request)
    assert report is not None
    # Seed a completed outcome to isolate the final coverage consumer. This is
    # not a replay of the sentence-repair loop or a semantic judgment.
    initial = SemanticEpisodeOutcome(
        verified=verified,
        status="completed",
        public_answer=variant["draft"],
        judge_status="passed" if report.passed else "repaired",
        requirement_checks=report.requirement_checks,
    )
    result = recheck_research_requirement_delivery(initial)
    partial = "partial" in variant["expected_requirement_statuses"]
    assert result.status == ("partial" if partial else "completed")
    assert _statuses(result) == variant["expected_requirement_statuses"]
    assert result.repair_output_ids == (("requirement_q2",) if partial else ())
    for sentence in request["sentences"]:
        assert sentence["text"] in result.public_answer


@pytest.mark.parametrize("variant_id", ["bad", "acceptable"])
def test_k3_full_verifier_respects_coverage_without_inventing_fact_rejection(
    variant_id,
):
    case = next(row for row in CORPUS["cases"] if row["finding"] == "K3")
    variant = next(row for row in case["variants"] if row["id"] == variant_id)
    frame, verified, _ = _request(case, variant)
    calls = []

    def judge(request):
        calls.append(request)
        return _scripted_report(request, variant)

    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(15),
    )
    assert len(calls) == 1
    assert result.status == ("partial" if variant_id == "bad" else "completed")
    assert result.rejected_claim_indexes == ()
    assert _statuses(result) == variant["expected_requirement_statuses"]


def test_witness_presence_is_not_a_semantic_oracle():
    case = next(row for row in CORPUS["cases"] if row["finding"] == "K3")
    variant = next(row for row in case["variants"] if row["id"] == "bad")
    _, verified, request = _request(case, variant)
    dishonest = _scripted_report(request, variant)
    part = dishonest["requirement_checks"][1]["parts"][0]
    part.update(
        status="fulfilled", missing_aspects=[], reason="Scripted false positive."
    )
    report = _parse(dishonest, request)
    assert report is not None
    initial = SemanticEpisodeOutcome(
        verified=verified,
        status="completed",
        public_answer=variant["draft"],
        judge_status="passed",
        requirement_checks=report.requirement_checks,
    )
    assert recheck_research_requirement_delivery(initial).status == "completed"
    # Removing the witness, unlike misunderstanding its meaning, is detectable.
    projected = request["sentences"][0]["text"]
    assert (
        recheck_research_requirement_delivery(initial, projected=projected).status
        == "partial"
    )
