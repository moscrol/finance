from __future__ import annotations

import json

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
