from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.error

import pytest

from intelligence import cli
from intelligence.services import llm_refine
from intelligence.services.ask import AskResult
from intelligence.services.ask_clarify import ClarifyDecision
from intelligence.summary import WorkflowSummary
from intelligence.workflows import ask as ask_workflow


def test_ask_receipt_binds_short_answer_without_changing_stdout(tmp_path, monkeypatch, capsys):
    answer = "  short answer\n\n"
    result = AskResult("question", "2026-09-14", None, None, None)
    result.found_graph = True
    summary = WorkflowSummary("ask", "WARN", "2026-09-14T00:00:00Z")
    monkeypatch.setattr(ask_workflow, "run_ask", lambda _options: (summary, result, answer))
    arguments = ["ask", "question", "--date", "2026-09-14", "--no-score"]

    assert cli.main(arguments) == 0
    original = capsys.readouterr().out
    destination = tmp_path / "receipt.json"
    assert cli.main([
        *arguments,
        "--call-provenance-json", str(destination),
        "--call-provenance-id", "source-attempt-one",
    ]) == 0

    output = capsys.readouterr().out
    receipt = json.loads(destination.read_text())
    assert output == original == answer
    assert receipt["schema_version"] == 1
    assert receipt["receipt_id"] == "source-attempt-one"
    assert receipt["delivery_state"] == "delivered"
    assert receipt["scope"] == "all_successful_ask_calls"
    assert receipt["raw_output_sha256"] == hashlib.sha256(answer.encode()).hexdigest()
    assert receipt["answer_sha256"] == hashlib.sha256(b"short answer").hexdigest()
    assert receipt["question_sha256"] == hashlib.sha256(
        b'{"as_of":"2026-09-14","text":"question"}'
    ).hexdigest()
    assert receipt["records"] == []
    assert receipt["collection_state"] == "not_called"
    assert llm_refine.current_call_ledger() is None


class _Response:
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b'{"model":"served","choices":[{"message":{"content":"body"}}]}'


def test_receipt_covers_calls_and_reuses_outer_budget(tmp_path, monkeypatch, capsys):
    provider = llm_refine.LLMProvider("fixture", "secret", "https://example.invalid/v1", "requested")
    requests = []

    def transport(request, timeout=0.0, **_kwargs):
        requests.append(request)
        if len(requests) == 2:
            raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, None)
        return _Response()

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (provider,))
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", transport)
    messages = [{"role": "user", "content": "question"}]

    def workflow(_options):
        assert llm_refine.complete(messages)[0] is None
        assert llm_refine.complete(messages)[0] == "body"
        assert llm_refine.complete(messages)[0] is None
        result = AskResult("question", "2026-09-14", None, None, None)
        return WorkflowSummary("ask", "FAIL", "start"), result, "refusal"

    monkeypatch.setattr(ask_workflow, "run_ask", workflow)
    destination = tmp_path / "receipt.json"
    with llm_refine.call_ledger_scope(max_calls=3) as outer:
        with llm_refine.call_provenance_scope("earlier-call", "writer"):
            assert llm_refine.complete(messages)[0] == "body"
        assert cli.main([
            "ask", "question", "--no-score",
            "--call-provenance-json", str(destination),
            "--call-provenance-id", "this-call",
        ]) == 1
        assert llm_refine.current_call_ledger() is outer
        assert outer.headroom() == 0
        assert len(outer.records) == 3

    receipt = json.loads(destination.read_text())
    assert receipt["delivery_state"] == "delivered"
    assert receipt["collection_state"] == "captured"
    assert [record["status"] for record in receipt["records"]] == ["failed", "success"]
    assert {record["call_id"] for record in receipt["records"]} == {"this-call"}
    assert {record["phase"] for record in receipt["records"]} == {"writer"}
    assert len({record["attempt_id"] for record in receipt["records"]}) == 2
    assert receipt["records"][1]["reported_model"] == "served"
    assert capsys.readouterr().out == "refusal"


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_exception_keeps_completed_calls_without_claiming_delivery(
    tmp_path, monkeypatch, capsys, error_type,
):
    provider = llm_refine.LLMProvider("fixture", "secret", "https://example.invalid/v1", "requested")
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (provider,))
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", lambda *_a, **_k: _Response())

    def workflow(_options):
        assert llm_refine.complete([{"role": "user", "content": "question"}])[0] == "body"
        print("diagnostic output " * 30)
        raise error_type("private diagnostic text")

    monkeypatch.setattr(ask_workflow, "run_ask", workflow)
    destination = tmp_path / "receipt.json"
    with pytest.raises(error_type):
        cli.main(["ask", "question", "--date", "2026-09-14", "--no-score",
                  "--call-provenance-json", str(destination)])

    output = capsys.readouterr().out
    receipt = json.loads(destination.read_text())
    assert receipt["status"] == "failed"
    assert receipt["error_type"] == error_type.__name__
    assert receipt["delivery_state"] == "no_answer"
    assert receipt["records"][0]["status"] == "success"
    assert receipt["raw_output_sha256"] == hashlib.sha256(output.encode()).hexdigest()
    assert "private diagnostic text" not in destination.read_text()
    assert llm_refine.current_call_ledger() is None


@pytest.mark.parametrize("clarify,answer,expected_state", [
    (True, "please clarify", "clarification"),
    (False, "", "no_answer"),
])
def test_early_result_records_true_delivery_state(
    tmp_path, monkeypatch, clarify, answer, expected_state,
):
    result = AskResult("question", "2026-09-14", None, None, None)
    if clarify:
        result.clarify = ClarifyDecision(needs_clarification=True)
    monkeypatch.setattr(ask_workflow, "run_ask", lambda _options: (
        WorkflowSummary("ask", "WARN", "start"), result, answer,
    ))
    destination = tmp_path / "receipt.json"
    assert cli.main(["ask", "question", "--no-score",
                     "--call-provenance-json", str(destination)]) == 0
    receipt = json.loads(destination.read_text())
    assert receipt["status"] == "completed"
    assert receipt["delivery_state"] == expected_state
    assert receipt["collection_state"] == "not_called"


def test_existing_receipt_is_not_overwritten_or_reused(tmp_path, monkeypatch):
    destination = tmp_path / "receipt.json"
    destination.write_text("old receipt")

    def unexpected_call(_options):
        pytest.fail("must reject receipt conflict before asking")

    monkeypatch.setattr(ask_workflow, "run_ask", unexpected_call)
    assert cli.main(["ask", "question", "--no-score",
                     "--call-provenance-json", str(destination)]) == 2
    assert destination.read_text() == "old receipt"


def test_receipt_path_conflicting_with_another_output_is_rejected_before_ask(tmp_path, monkeypatch):
    destination = tmp_path / "receipt.json"

    def unexpected_call(_options):
        pytest.fail("must reject aliased output paths before asking")

    monkeypatch.setattr(ask_workflow, "run_ask", unexpected_call)
    assert cli.main(["ask", "question", "--no-score", "--summary-json", str(destination),
                     "--call-provenance-json", str(destination)]) == 2
    assert not destination.exists()


def test_real_subprocess_receipt_matches_stdout_bytes_and_uses_unique_ids(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    command = [sys.executable, "-m", "intelligence.cli", "ask", "", "--no-score",
               "--no-modules", "--no-wiki-rag", "--date", "2026-09-14"]
    ordinary = subprocess.run(command, cwd=repository, capture_output=True, timeout=30, check=True)
    ids = []
    for index in range(2):
        destination = tmp_path / f"receipt-{index}.json"
        result = subprocess.run(
            [*command, "--call-provenance-json", str(destination)],
            cwd=repository, capture_output=True, timeout=30, check=True,
        )
        receipt = json.loads(destination.read_text())
        assert result.stdout == ordinary.stdout
        assert result.stderr == ordinary.stderr
        assert receipt["raw_output_sha256"] == hashlib.sha256(result.stdout).hexdigest()
        assert receipt["answer_sha256"] == hashlib.sha256(result.stdout.strip()).hexdigest()
        assert receipt["delivery_state"] == "clarification"
        assert receipt["records"] == []
        ids.append(receipt["receipt_id"])
    assert len(set(ids)) == 2
