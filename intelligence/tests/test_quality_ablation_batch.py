"""Frozen batch through the real scoring adapter and a fake HTTP boundary."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
from subprocess import CompletedProcess

import pytest

from intelligence.eval import judge_validity as validity
from intelligence.services import grok_cli_judge, llm_refine
from intelligence.tests.judge_validity_fixtures import writer_provenance
from intelligence.tests.test_llm_call_provenance import Response, body
from scripts import run_quality_ablation as run


@pytest.fixture
def judge(monkeypatch):
    provider = llm_refine.LLMProvider("judge", "fake", "https://judge.invalid/v1", "grok-4")
    monkeypatch.setitem(run._JUDGE_OVERRIDE, "provider", provider)
    return provider


def artifact():
    questions = [{"case_id": f"q{i}", "text": f"Question {i}", "as_of": "2026-09-01"} for i in range(2)]
    manifest = validity.new_manifest(questions, ["kb-rag"], run.build_judge_spec())
    answers = []
    for q in questions:
        for arm in ("baseline", "kb-rag"):
            answer = f"{q['text']} / {arm}"
            provenance = writer_provenance(answer)
            provenance.update(receipt_verified=True, receipt_id=answer,
                              question_sha256=validity.canonical_hash({"text": q["text"], "as_of": q["as_of"]}))
            answers.append(validity.stamp_answer(manifest, {
                "case_id": q["case_id"], "arm": arm, "ok": True, "answer": answer,
                "writer_provenance": provenance,
            }))
    return {"kind": "quality_ablation", "schema_version": 2, "status": "incomplete",
            "questions": questions, "answers": answers,
            "manifest": validity.bind_answers(manifest, answers)}


def score_response(model="grok-4", score=3):
    return Response(body(json.dumps(dict.fromkeys(run.RUBRIC_DIMENSIONS, score)), model=model))


def test_real_scoring_chain_seals_eligible_batch_and_checkpoints_selected_attempt(judge, monkeypatch, tmp_path):
    data = artifact()
    output = tmp_path / "batch.json"
    run.write_artifact(output, data, create=True)
    calls = []
    def transport(request, timeout=0.0, **kwargs):
        prior = json.loads(output.read_text())
        assert prior["manifest"]["answer_manifest"] is not None
        calls.append(json.loads(request.data))
        if len(calls) > 1:
            assert prior["call_ledger"]["call_count"] == len(calls) - 1
        return score_response()
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", transport)
    run.finish_judging(data, seed=1, persist=lambda: run.write_artifact(output, data))
    assert len(calls) == 6
    assert all(p["max_tokens"] == 1000 and p["temperature"] == 0.1 for p in calls)
    assert data["status"] == "complete"
    assert data["judging_validity"]["valid"], data["judging_validity"]
    assert data["aggregates"]["kb-rag"]["decision"] == "callable"
    assert json.loads(output.read_text())["manifest"]["state"] == "sealed"
    records = {r["attempt_id"]: r for r in data["call_ledger"]["records"]}
    for answer in data["answers"]:
        verdict = answer["judge"]
        assert records[verdict["selected_attempt_id"]]["result_sha256"] == validity.text_hash(verdict["raw_content"])


@pytest.mark.parametrize("model", [None, "gpt-5", "unrecognized"])
def test_changed_or_unknown_response_stops_after_one_call_with_receipt(judge, monkeypatch, tmp_path, model):
    data = artifact()
    calls = []
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *a, **k: calls.append(1) or score_response(model))
    output = tmp_path / "invalid.json"
    run.write_artifact(output, data, create=True)
    run.finish_judging(data, seed=1, persist=lambda: run.write_artifact(output, data))
    saved = json.loads(output.read_text())
    assert len(calls) == 1
    assert saved["manifest"]["state"] == "invalid"
    assert saved["call_ledger"]["call_count"] == 1
    assert saved["aggregates"]["kb-rag"]["decision"] == "no_call"


def test_interruption_retains_completed_attempt_and_invalidates_batch(judge, monkeypatch, tmp_path):
    data = artifact()
    calls = []
    def transport(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt()
        return score_response()
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", transport)
    output = tmp_path / "partial.json"
    run.write_artifact(output, data, create=True)
    with pytest.raises(KeyboardInterrupt):
        run.finish_judging(data, seed=1, persist=lambda: run.write_artifact(output, data))
    saved = json.loads(output.read_text())
    assert saved["status"] == "incomplete"
    assert saved["call_ledger"]["call_count"] >= 1
    assert saved["manifest"]["state"] == "invalid"
    assert saved["aggregates"]["kb-rag"]["decision"] == "no_call"


def test_main_saves_before_ask_and_routes_all_scores_through_batch(judge, monkeypatch, tmp_path):
    path = tmp_path / "main.json"
    monkeypatch.setattr(run, "require_llm_ready", lambda: None)
    monkeypatch.setattr(run, "resolve_judge", lambda **kw: {
        "override": judge, "composer": "gpt-5", "judge": "grok-4", "independence": "independent", "reason": "fixture"})
    def ask(question, **kwargs):
        frozen = json.loads(path.read_text())
        assert frozen["manifest"]["run_manifest_sha256"]
        assert frozen["manifest"]["answer_manifest"] is None
        answer = question.case_id + str(len(frozen["answers"]))
        p = writer_provenance(answer)
        p.update(receipt_verified=True, receipt_id=answer, question_sha256=validity.canonical_hash({"text": question.text, "as_of": question.as_of}))
        return {"ok": True, "answer": answer, "writer_provenance": p}
    monkeypatch.setattr(run, "run_ask", ask)
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *a, **kw: score_response())
    assert run.main(["--output", str(path), "--components", "kb-rag", "--max-questions", "2", "--calibration-repeats", "1"]) == 0
    saved = json.loads(path.read_text())
    assert saved["judging_validity"]["valid"], saved["judging_validity"]
    assert saved["schema_version"] == 2


@pytest.mark.parametrize("text", ["短答", "无法确认，没有足够证据。"])
def test_run_ask_verifies_own_receipt_and_accepts_short_delivery(judge, monkeypatch, text):
    def process(cmd, **kwargs):
        receipt_id = cmd[cmd.index("--call-provenance-id") + 1]
        receipt = Path(cmd[cmd.index("--call-provenance-json") + 1])
        receipt.write_text(json.dumps({
            "receipt_id": receipt_id, "question_sha256": validity.canonical_hash({"text": "q", "as_of": "2026-09-01"}),
            "raw_output_sha256": validity.text_hash(text + "\n"), "answer_sha256": validity.text_hash(text),
            "delivery_state": "delivered", "status": "completed",
        }))
        return SimpleNamespace(stdout=text + "\n", returncode=1, stderr="")
    monkeypatch.setattr(run.subprocess, "run", process)
    result = run.run_ask(run.Question("q", "q", "2026-09-01"), extra_env={}, extra_flags=(), exports_dir="unused", timeout=5)
    assert result["ok"] is True
    assert result["writer_provenance"]["receipt_verified"] is True


@pytest.mark.parametrize("field,value", [("receipt_id", "other"), ("raw_output_sha256", "0" * 64)])
def test_run_ask_rejects_receipt_from_other_output(judge, monkeypatch, field, value):
    def process(cmd, **kwargs):
        receipt = Path(cmd[cmd.index("--call-provenance-json") + 1])
        p = {"receipt_id": cmd[cmd.index("--call-provenance-id") + 1],
             "question_sha256": validity.canonical_hash({"text": "q", "as_of": "2026-09-01"}),
             "raw_output_sha256": validity.text_hash("answer"), "answer_sha256": validity.text_hash("answer"),
             "delivery_state": "delivered", "status": "completed"}
        p[field] = value
        receipt.write_text(json.dumps(p))
        return SimpleNamespace(stdout="answer", returncode=0, stderr="")
    monkeypatch.setattr(run.subprocess, "run", process)
    assert not run.run_ask(run.Question("q", "q", "2026-09-01"), extra_env={}, extra_flags=(), exports_dir="unused", timeout=5)["ok"]


def test_old_receipt_cannot_claim_valid_by_omitting_manifest(judge):
    data = artifact()
    for answer in data["answers"]:
        answer["judge"] = {"scored": True, "scores": dict.fromkeys(run.RUBRIC_DIMENSIONS, 3), "total": 15}
    result = run.aggregate_components(data["answers"], ["kb-rag"], noise_floor={
        "measured": True, "sigma": 2, "sd_delta_single_question": 0,
    })["kb-rag"]
    assert result["decision"] == "no_call"
    assert "unsupported_schema" in result["judging_validity"]["reason_codes"]


def test_unknown_identity_in_invalid_json_does_not_spend_format_retry(judge, monkeypatch):
    calls = []
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *a, **k: calls.append(1) or Response(body("not JSON")))
    result = run.judge_answer(run.Question("q", "q", "2026-09-01"), "answer", spec=run.build_judge_spec())
    assert len(calls) == 1
    assert result["reason"] == "judge_identity_unknown"
    assert len(result["attempt_records"]) == 1


def test_closing_a_batch_prevents_reusing_finish(judge, monkeypatch):
    data = artifact()
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *a, **k: score_response())
    run.finish_judging(data, seed=1)
    calls = []
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *a, **k: calls.append(1) or score_response())
    with pytest.raises(ValueError, match="open"):
        run.finish_judging(data, seed=1)
    assert not calls


def test_coverage_excludes_blank_delivery_and_non_finite_scores():
    data = artifact()
    scored = {"scored": True, "scores": dict.fromkeys(run.RUBRIC_DIMENSIONS, 3), "total": 15}
    for answer in data["answers"]:
        answer["judge"] = deepcopy(scored)
    data["answers"][0]["answer"] = "   "          # ok=True，但没有可评正文
    data["answers"][1]["judge"]["total"] = float("nan")   # scored 标了 True，数却不可用
    assert run.batch_coverage(data) == {
        "registered": 4, "collected": 4, "delivered": 3, "scored": 3, "failed_attempts": 0,
    }


def test_cli_judge_receives_quality_schema_and_effective_effort(judge, monkeypatch):
    provider = replace(judge, transport="cli", base_url="cli://grok")
    monkeypatch.setitem(run._JUDGE_OVERRIDE, "provider", provider)
    monkeypatch.setenv("LLM_JUDGE_GROK_BIN", "/fixture/grok")
    monkeypatch.setenv("LLM_JUDGE_GROK_EFFORT", "high")
    original = grok_cli_judge.complete_grok_cli
    def runner(argv, **kwargs):
        schema = json.loads(argv[argv.index("--json-schema") + 1])
        assert set(run.RUBRIC_DIMENSIONS).issubset(schema["properties"])
        assert argv[argv.index("--reasoning-effort") + 1] == "high"
        return CompletedProcess(argv, 0, stdout=json.dumps({"model": "grok-4", "text": json.dumps(dict.fromkeys(run.RUBRIC_DIMENSIONS, 3))}), stderr="")
    monkeypatch.setattr(grok_cli_judge, "complete_grok_cli", lambda *a, **k: original(*a, **k, runner=runner))
    spec = run.build_judge_spec()
    result = run.judge_answer(run.Question("q", "q", "2026-09-01"), "answer", spec=spec)
    assert result["scored"], result
    assert spec["thinking"]["reasoning_effort"] == "high"
    assert spec["temperature"] is None
