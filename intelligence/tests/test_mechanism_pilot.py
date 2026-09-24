from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import urllib.error

import pytest

from intelligence.eval import mechanism_pilot as pilot
from intelligence.services import llm_refine
from intelligence.services.research_validation.contracts import digest


@pytest.fixture
def suite():
    return json.loads(pilot.SUITE.read_text(encoding="utf-8"))


@pytest.fixture
def study(tmp_path):
    directory = tmp_path / "study"
    protocol = pilot.prepare(directory)
    return directory, protocol


@pytest.fixture
def provider(monkeypatch):
    value = llm_refine.LLMProvider("test", "not-a-real-key", "https://invalid.example/v1", "fixed-model")
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *args, **kwargs: value)
    return value


def answer(case, **changes):
    result = {
        "organization": "A bounded research note.",
        "counterevidence_ids": case["answer_key"]["counterevidence_ids"],
        "next_check": case["answer_key"]["next_check"],
        "reason": "Inspect the specified evidence.",
        "change_condition": "Revise when the stated condition changes.",
    }
    result.update(changes)
    return json.dumps(result)


def fake_completion(monkeypatch, protocol, *, fail_arm=None):
    seen = []
    by_question = {c["question"]: c for c in protocol["suite"]["cases"]}

    def complete(messages, **kwargs):
        llm_refine._reserve_llm_call()
        seen.append((messages, kwargs))
        if fail_arm and messages[0]["content"].endswith(pilot.ARM_INSTRUCTIONS[fail_arm]):
            return None, "test provider failure"
        case = by_question[json.loads(messages[1]["content"])["question"]]
        return llm_refine.SynthesisResult(answer(case), "test", "fixed-model", "stop"), ""

    monkeypatch.setattr(llm_refine, "synthesize_messages", complete)
    return seen


def test_prepare_equal_inputs_and_no_gold(study):
    _, protocol = study
    for case in protocol["suite"]["cases"]:
        cells = [c for c in protocol["cells"] if c["case_id"] == case["case_id"]]
        assert cells[0]["messages"][1] == cells[1]["messages"][1]
        public = json.loads(cells[0]["messages"][1]["content"])
        assert set(public) == {"question", "facts", "options"}
        assert "answer_key" not in json.dumps(cells)
        assert case["answer_key"]["rationale"] not in json.dumps(cells, ensure_ascii=False)
    assert [c["arm"] for c in protocol["cells"][:4]] == ["summary", "mechanism", "mechanism", "summary"]
    assert protocol["budget"]["attempts_per_cell"] == 1


def test_gold_can_change_without_changing_model_input(suite):
    case = suite["cases"][0]
    original = pilot.messages_for(case, "mechanism")
    case["answer_key"]["rationale"] = "DO_NOT_EXPOSE_THIS_GOLD"
    assert pilot.messages_for(case, "mechanism") == original


@pytest.mark.parametrize("corruption", ["real", "duplicate", "path", "gold", "unknown_field"])
def test_suite_fail_closed(suite, corruption):
    if corruption == "real":
        suite["source_kind"] = "historical"
    elif corruption == "duplicate":
        suite["cases"][1]["case_id"] = suite["cases"][0]["case_id"]
    elif corruption == "path":
        suite["cases"][0]["case_id"] = "../../elsewhere"
    elif corruption == "gold":
        suite["cases"][0]["answer_key"]["next_check"] = "unknown"
    else:
        suite["cases"][0]["facts"][0]["answer_key"] = "leak"
    with pytest.raises(ValueError):
        pilot.validate_suite(suite)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -1, 0, 181, True])
def test_invalid_budgets_rejected_before_write(tmp_path, timeout):
    with pytest.raises(ValueError):
        pilot.prepare(tmp_path / "absent", timeout=timeout)
    assert not (tmp_path / "absent").exists()


def test_existing_protocol_cannot_be_overwritten(study):
    directory, protocol = study
    before = (directory / "protocol.json").read_bytes()
    with pytest.raises(ValueError, match="write-once"):
        pilot.prepare(directory)
    assert (directory / "protocol.json").read_bytes() == before
    assert pilot._read(pilot._store(directory), "protocol.json") == protocol


def test_no_model_is_blocked_without_fake_attempts(study, monkeypatch):
    directory, protocol = study
    monkeypatch.setattr(llm_refine, "detect_provider", lambda: None)
    result = pilot.run(directory)
    assert result == {"status": "blocked", "reason": "no_configured_model", "planned": len(protocol["cells"]), "calls": 0}
    assert not (directory / "attempts").exists()
    report = pilot.report(directory)
    assert all(r["status"] == "not_run" for r in report["rows"])
    assert all(a["completed"] == 0 for a in report["arms"].values())
    assert report["promotion_eligible"] is False


def test_successful_mock_run_has_equal_budgets_and_no_retries(study, provider, monkeypatch):
    directory, protocol = study
    seen = fake_completion(monkeypatch, protocol)
    result = pilot.run(directory)
    expected = len(protocol["suite"]["cases"])
    assert len(seen) == 2 * expected
    assert all(kwargs == seen[0][1] for _, kwargs in seen)
    assert seen[0][1]["max_tokens"] == protocol["budget"]["max_tokens"]
    assert seen[0][1]["timeout"] == protocol["budget"]["timeout_seconds"]
    assert result["paired"]["next_check_correct"] == {
        "complete_pairs": expected, "mechanism_wins": 0, "ties": expected, "summary_wins": 0,
    }
    assert result["workbench_effect_tested"] is False
    assert result["predictive_validity_tested"] is False
    assert pilot.run(directory) == result
    assert len(seen) == 2 * expected
    for response in (directory / "responses").glob("*.json"):
        payload = pilot._read(pilot._store(directory), str(response.relative_to(directory)))
        assert payload["reserved_calls"] == 1
        assert payload["served_model"] is None


def test_model_failures_stay_in_denominator(study, provider, monkeypatch):
    directory, protocol = study
    fake_completion(monkeypatch, protocol, fail_arm="mechanism")
    result = pilot.run(directory)
    n = len(protocol["suite"]["cases"])
    assert result["arms"]["mechanism"]["planned"] == n
    assert result["arms"]["mechanism"]["completed"] == 0
    assert result["arms"]["summary"]["completed"] == n
    assert result["paired"]["next_check_correct"]["complete_pairs"] == 0
    assert sum(r["status"] == "model_failed" for r in result["rows"]) == n


def test_transport_retry_cannot_exceed_one_http_per_cell(study, provider, monkeypatch):
    directory, protocol = study
    seen = []

    def unavailable(*args, **kwargs):
        seen.append(args)
        raise urllib.error.URLError("test outage")

    monkeypatch.setattr(llm_refine.urllib.request, "urlopen", unavailable)
    result = pilot.run(directory)
    assert len(seen) == len(protocol["cells"])
    assert all(r["status"] == "model_failed" for r in result["rows"])
    requests = [json.loads(args[0].data) for args in seen]
    assert all(r["max_tokens"] == protocol["budget"]["max_tokens"] for r in requests)
    assert all(r["temperature"] == protocol["budget"]["temperature"] for r in requests)


def test_interrupted_attempt_is_never_resampled(study, provider, monkeypatch):
    directory, protocol = study

    def crash(*args, **kwargs):
        raise RuntimeError("unexpected interruption")

    monkeypatch.setattr(llm_refine, "synthesize_messages", crash)
    with pytest.raises(RuntimeError):
        pilot.run(directory)
    seen = fake_completion(monkeypatch, protocol)
    result = pilot.run(directory)
    assert len(seen) == len(protocol["cells"]) - 1
    assert result["rows"][0]["status"] == "attempted_without_response"


def test_provider_change_rejected(study, provider, monkeypatch):
    directory, protocol = study
    fake_completion(monkeypatch, protocol)
    pilot.run(directory)
    provider.model = "other-model"
    with pytest.raises(ValueError, match="mixed-model"):
        pilot.run(directory)


def test_changed_thinking_controls_rejected(study, provider, monkeypatch):
    directory, protocol = study
    fake_completion(monkeypatch, protocol)
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    pilot.run(directory)
    monkeypatch.setenv("LLM_REASONING_EFFORT", "high")
    with pytest.raises(ValueError, match="mixed-model"):
        pilot.run(directory)


@pytest.mark.parametrize("changes", [
    {"counterevidence_ids": ["f1", "f2", "f3", "f4"]},
    {"counterevidence_ids": ["f1", "f1"]},
    {"counterevidence_ids": ["absent"]},
    {"next_check": "absent"},
    {"next_check": True},
    {"reason": ""},
    {"organization": "x" * 501},
    {"self_score": 1},
])
def test_answer_cannot_game_structural_score(suite, changes):
    case = suite["cases"][0]
    with pytest.raises(ValueError):
        pilot.parse_answer(answer(case, **changes), case)


def test_invalid_model_answer_retains_raw_text(study, provider, monkeypatch):
    directory, protocol = study
    raw = "not JSON; still retained"
    monkeypatch.setattr(llm_refine, "synthesize_messages", lambda *a, **k: (
        llm_refine.SynthesisResult(raw, "test", "fixed-model", "stop"), "",
    ))
    result = pilot.run(directory)
    assert all(r["status"] == "invalid_answer" for r in result["rows"])
    name = "responses/" + protocol["cells"][0]["cell_id"] + ".json"
    assert pilot._read(pilot._store(directory), name)["answer_text"] == raw


def test_wrong_choices_lose_to_correct_arm(study, provider, monkeypatch):
    directory, protocol = study
    cases = {c["question"]: c for c in protocol["suite"]["cases"]}

    def complete(messages, **kwargs):
        case = cases[json.loads(messages[1]["content"])["question"]]
        changes = {}
        if messages[0]["content"].endswith(pilot.ARM_INSTRUCTIONS["summary"]):
            changes = {"counterevidence_ids": [], "next_check": next(
                o["id"] for o in case["options"] if o["id"] != case["answer_key"]["next_check"]
            )}
        return llm_refine.SynthesisResult(answer(case, **changes), "test", "fixed-model", "stop"), ""

    monkeypatch.setattr(llm_refine, "synthesize_messages", complete)
    result = pilot.run(directory)
    n = len(cases)
    for metric in protocol["metrics"]:
        assert result["arms"]["summary"][metric] == 0
        assert result["arms"]["mechanism"][metric] == n
        assert result["paired"][metric] == {
            "complete_pairs": n, "mechanism_wins": n, "ties": 0, "summary_wins": 0,
        }


def test_concurrent_attempt_claims_have_exactly_one_winner(tmp_path):
    store = pilot._store(tmp_path / "concurrency")
    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=5)
        return pilot._write(store, "attempts/case-summary.json", {"binding": "same"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == [False, True]


def test_report_rejects_transplanted_response(study, provider, monkeypatch):
    directory, protocol = study
    fake_completion(monkeypatch, protocol)
    pilot.run(directory)
    paths = sorted((directory / "responses").glob("*.json"))
    paths[0].write_bytes(paths[1].read_bytes())
    with pytest.raises(ValueError, match="binding mismatch"):
        pilot.report(directory)


def test_hash_tampering_fails(study):
    directory, _ = study
    path = directory / "protocol.json"
    doc = json.loads(path.read_text())
    doc["payload"]["suite"]["cases"][0]["answer_key"]["next_check"] = "q2"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="hash mismatch"):
        pilot.report(directory)


def test_report_reads_frozen_suite_not_mutable_source(study, monkeypatch, tmp_path):
    directory, protocol = study
    monkeypatch.setattr(pilot, "SUITE", tmp_path / "not-present.json")
    result = pilot.report(directory)
    assert result["protocol_sha256"] == digest(protocol)


def test_existing_call_ledger_cannot_weaken_budget(study):
    with llm_refine.call_ledger_scope(max_calls=100):
        with pytest.raises(ValueError, match="own its per-call"):
            pilot.run(study[0])


def test_cli_prepare_report_and_blocked_run(tmp_path, monkeypatch, capsys):
    directory = tmp_path / "cli"
    assert pilot.main(["prepare", "--directory", str(directory)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prepared"
    assert pilot.main(["report", "--directory", str(directory)]) == 0
    assert len(json.loads(capsys.readouterr().out)["rows"]) == 12
    monkeypatch.setattr(llm_refine, "detect_provider", lambda: None)
    assert pilot.main(["run", "--directory", str(directory)]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "no_configured_model"
