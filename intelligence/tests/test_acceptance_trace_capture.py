from __future__ import annotations

import json

import pytest

from intelligence.api.app import _public_trace_step
from intelligence.eval import acceptance


def _diagnostic() -> dict[str, object]:
    return {
        "state": "rejected",
        "reason_code": "claim_binding_failed",
        "detail": "candidate answer had no evidence-bound claim",
        "prepared_message_count": 2,
        "candidate_claim_count": 1,
        "bound_claim_count": 0,
    }


def test_public_trace_exposes_only_whitelisted_synthesis_diagnostic() -> None:
    raw = {
        "step_id": "synthesize",
        "name": "answer_synthesis",
        "status": "completed",
        "output_summary": json.dumps(
            {
                "diagnostic": {
                    **_diagnostic(),
                    "prompt": "private prompt",
                    "evidence_body": "private evidence",
                }
            },
            ensure_ascii=False,
        ),
    }

    public = _public_trace_step(raw)

    assert public["diagnostic"] == _diagnostic()
    assert "private prompt" not in json.dumps(public, ensure_ascii=False)
    assert "private evidence" not in json.dumps(public, ensure_ascii=False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", 1),
        ("reason_code", ["claim_binding_failed"]),
        ("detail", {"prompt": "PRIVATE_PROMPT", "evidence_body": "PRIVATE_EVIDENCE"}),
        ("prepared_message_count", "2"),
        ("candidate_claim_count", True),
        ("bound_claim_count", -1),
    ],
)
def test_public_trace_rejects_malformed_diagnostic_shape(
    field: str,
    value: object,
) -> None:
    diagnostic = _diagnostic()
    diagnostic[field] = value
    raw = {
        "step_id": "synthesize",
        "name": "answer_synthesis",
        "status": "completed",
        "output_summary": json.dumps({"diagnostic": diagnostic}, ensure_ascii=False),
    }

    public = _public_trace_step(raw)

    assert "diagnostic" not in public
    serialized = json.dumps(public, ensure_ascii=False)
    assert "PRIVATE_PROMPT" not in serialized
    assert "PRIVATE_EVIDENCE" not in serialized


@pytest.mark.parametrize(
    "detail",
    [
        "prompt=PRIVATE_PROMPT",
        "evidence_body=PRIVATE_EVIDENCE",
        "Authorization: Bearer PRIVATE_SECRET",
        "internal receipt at /tmp/private-trace.json",
        "internal receipt at /private/tmp/private-trace.json",
        "internal receipt at /Users/a77/private-trace.json",
    ],
)
def test_public_trace_rejects_unsafe_diagnostic_detail(detail: str) -> None:
    diagnostic = _diagnostic()
    diagnostic["detail"] = detail
    raw = {
        "step_id": "synthesize",
        "name": "answer_synthesis",
        "status": "completed",
        "output_summary": json.dumps({"diagnostic": diagnostic}, ensure_ascii=False),
    }

    public = _public_trace_step(raw)

    assert "diagnostic" not in public
    serialized = json.dumps(public, ensure_ascii=False)
    assert "PRIVATE_" not in serialized
    assert "/tmp/" not in serialized
    assert "/private/tmp/" not in serialized
    assert "/Users/" not in serialized


def test_acceptance_capture_reads_answer_synthesis_diagnostic(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 30.0):
        del timeout
        if url.endswith("/context"):
            return {"evidence": [], "gaps": []}
        if url.endswith("/trace"):
            return [
                {
                    "name": "synthesize",
                    "status": "completed",
                    "diagnostic": {
                        **_diagnostic(),
                        "prompt": "must not be retained",
                    },
                }
            ]
        raise AssertionError(url)

    monkeypatch.setattr(acceptance, "_get", fake_get)
    trace = acceptance.TurnTrace(question="q", run_id="run-1")

    acceptance._fill_run_detail("http://base", trace)

    assert trace.synthesis_diagnostic == _diagnostic()
    assert trace.trace_steps == ["synthesize"]


def test_acceptance_capture_forwards_user_to_run_detail_endpoints(monkeypatch) -> None:
    requested: list[str] = []

    def fake_get(url: str, timeout: float = 30.0):
        del timeout
        requested.append(url)
        if "/context?" in url:
            return {"evidence": [{"status": "hit"}], "gaps": []}
        if "/trace?" in url:
            return [
                {
                    "name": "synthesize",
                    "status": "completed",
                    "diagnostic": _diagnostic(),
                }
            ]
        raise AssertionError(url)

    monkeypatch.setattr(acceptance, "_get", fake_get)
    trace = acceptance.TurnTrace(question="q", run_id="run-1")

    acceptance._fill_run_detail("http://base", trace, user="default user")

    assert requested == [
        "http://base/api/runs/run-1/context?user=default+user",
        "http://base/api/runs/run-1/trace?user=default+user",
    ]
    assert trace.evidence_bound == 1
    assert trace.synthesis_diagnostic == _diagnostic()


def test_acceptance_capture_keeps_old_trace_compatible(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 30.0):
        del timeout
        if url.endswith("/context"):
            return {"evidence": [], "gaps": []}
        return [{"name": "synthesize", "status": "completed"}]

    monkeypatch.setattr(acceptance, "_get", fake_get)
    trace = acceptance.TurnTrace(question="q", run_id="run-1")

    acceptance._fill_run_detail("http://base", trace)

    assert trace.synthesis_diagnostic == {}
