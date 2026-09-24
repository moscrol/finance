"""Producer/validator wire compatibility and merged billing/provenance records."""

from dataclasses import replace
import json
from subprocess import CompletedProcess

import pytest

from intelligence.call_identity import IDENTITY_NOT_CALLED, IDENTITY_REPORTED, IDENTITY_UNREPORTED
from intelligence.eval.judge_validity import validate_judging_batch
from intelligence.services import grok_cli_judge, llm_refine
from intelligence.tests.judge_validity_fixtures import NOW, valid_batch
from intelligence.tests.test_llm_call_provenance import MESSAGES, PROVIDER, Response, body, text_hash


def test_identity_wire_values_and_uncalled_defaults_are_stable():
    assert (IDENTITY_NOT_CALLED, IDENTITY_UNREPORTED, IDENTITY_REPORTED) == (
        "not_called", "unreported", "reported",
    )
    record = llm_refine.LLMCallRecord("chat", "fixture", "requested", "failed", 0)
    assert record.identity_state == "not_called"
    with llm_refine.call_provenance_scope("unused", "judge") as context:
        assert context.identity_state == "not_called"


@pytest.mark.parametrize("role", ["writer", "judge", "calibration"])
@pytest.mark.parametrize("reported", [True, False])
def test_recorded_identity_is_consumed_by_the_batch_gate(monkeypatch, role, reported):
    batch = valid_batch()
    answers, calibration, manifest, floor = batch
    if role == "writer":
        target = answers[0]["writer_provenance"]["records"][0]
        reason = "writer_identity_unknown"
    else:
        verdict = answers[0]["judge"] if role == "judge" else calibration[0]["repeats"][0]
        target = verdict["attempt_records"][0]
        reason = "judge_identity_unknown"
    metadata = {"model": target["reported_model"]} if reported else {}
    monkeypatch.setattr(llm_refine.urllib.request, "urlopen", lambda *a, **k: Response(body(**metadata)))
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("contract", role) as context:
        llm_refine._post_chat(PROVIDER, MESSAGES, 5)
    observed = ledger.records_for_call("contract")[0]
    assert observed["identity_state"] == context.identity_state == ("reported" if reported else "unreported")
    # Only replace the identity evidence; keep the fixture's frozen batch bindings.
    target.update(identity_state=observed["identity_state"], reported_model=observed["reported_model"])
    result = validate_judging_batch(answers, calibration, manifest, now=NOW, noise_floor=floor)
    assert result["valid"] is reported
    if not reported:
        assert reason in result["reason_codes"]


@pytest.mark.parametrize("role", ["writer", "judge", "calibration"])
@pytest.mark.parametrize("state", ["not_called", "unreported", "reported-typo", None])
def test_nonreported_identity_never_qualifies_even_with_a_model_name(role, state):
    answers, calibration, manifest, floor = valid_batch()
    if role == "writer":
        target = answers[0]["writer_provenance"]["records"][0]
    else:
        verdict = answers[0]["judge"] if role == "judge" else calibration[0]["repeats"][0]
        target = verdict["attempt_records"][0]
    target["identity_state"] = state
    result = validate_judging_batch(answers, calibration, manifest, now=NOW, noise_floor=floor)
    assert not result["valid"]
    assert ("writer_identity_unknown" if role == "writer" else "judge_identity_unknown") in result["reason_codes"]


@pytest.mark.parametrize("transport", ["http", "cli"])
@pytest.mark.parametrize("reported", [True, False])
@pytest.mark.parametrize("has_usage", [True, False])
def test_billing_and_identity_survive_both_ledger_projections(monkeypatch, transport, reported, has_usage):
    metadata = {"model": "served", "id": "response", "request_id": "request"} if reported else {}
    usage = {"usage": {"input_tokens": 11, "output_tokens": 7}} if has_usage else {}
    provider = PROVIDER
    if transport == "http":
        monkeypatch.setattr(llm_refine.urllib.request, "urlopen", lambda *a, **k: Response(body(**metadata, **usage)))
    else:
        original = grok_cli_judge.complete_grok_cli
        monkeypatch.setattr(grok_cli_judge, "resolve_grok_binary", lambda: "/fixture/grok")

        def runner(argv, **kwargs):
            return CompletedProcess(argv, 0, stdout=json.dumps({"text": "answer", **metadata, **usage}), stderr="")

        monkeypatch.setattr(grok_cli_judge, "complete_grok_cli", lambda *a, **k: original(*a, **k, runner=runner))
        provider = replace(PROVIDER, base_url="cli://grok", transport="cli")
    with llm_refine.call_ledger_scope() as ledger, llm_refine.call_provenance_scope("both", "judge"), llm_refine.call_purpose("judge"):
        dispatch = llm_refine._post_chat if transport == "http" else llm_refine._complete_cli_judge
        content = dispatch(provider, MESSAGES, 5)
    summary = ledger.summary()
    record = ledger.records_for_call("both")[0]
    assert summary["records"] == [record]
    assert record["identity_state"] == ("reported" if reported else "unreported")
    assert record["reported_model"] == metadata.get("model")
    assert record["result_sha256"] == text_hash(content)
    assert record["purpose"] == "judge"
    if has_usage:
        assert (record["input_tokens"], record["output_tokens"]) == (11, 7)
        assert record["usage_source"] == ("api" if transport == "http" else "cli")
    elif transport == "cli":
        assert record["usage_source"] == "estimated"
        assert summary["estimated_share"] > 0
    else:
        assert "usage_source" not in record
    assert summary["input_tokens_total"] == record.get("input_tokens", 0)
    assert summary["output_tokens_total"] == record.get("output_tokens", 0)
    assert json.loads(json.dumps(summary))["records"] == [record]
