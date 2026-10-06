"""Read response identities from workbench ledgers, never from request labels."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path

import pytest

from intelligence.eval import model_admission as ma
from intelligence.services.llm_refine import LLMCallRecord
from intelligence.services.episode_store import JsonlEpisodeStore

MODEL = "glm-5.3-flash"


def _record(**overrides):
    payload = asdict(LLMCallRecord(
        caller="synthesis", provider="zhipu", model="request-label",
        status="success", elapsed_ms=1, requested_model="request-label",
        reported_model=MODEL, identity_state="reported", identity_conflict=False,
        attempt_id="attempt-1",
    ))
    return {**payload, **overrides}


def _step(records):
    return {"step_id": "llm_budget", "name": "llm_call_ledger", "status": "completed",
            "output_summary": json.dumps({"summary": "display only", "records": records})}


def _trace(tmp_path, *steps):
    path = tmp_path / "trace.jsonl"
    path.write_text("\n".join(json.dumps(step) for step in steps) + "\n", encoding="utf-8")
    return path


def _check(path, **kwargs):
    results = ma.check_paths([path], [MODEL], **kwargs)
    return results, ma.overall_exit_code(results)


@pytest.mark.parametrize("directory", (False, True), ids=("file", "directory"))
def test_workbench_trace_admits_only_response_reported_identity(tmp_path, directory):
    path = _trace(tmp_path, _step([_record()]))
    results, code = _check(tmp_path if directory else path)
    assert code == 0
    assert results[0].served == {MODEL: 1}
    assert results[0].source == str(path)


@pytest.mark.parametrize("directory", (False, True), ids=("file", "directory"))
def test_progress_prose_and_structured_telemetry_can_coexist_with_ledger(tmp_path, directory):
    from intelligence.services.agent_runtime import EpisodeEvent
    from intelligence.services.episode_progress import project_episode_progress
    from intelligence.services.run_store import RunStore

    progress = project_episode_progress(EpisodeEvent(
        sequence=1, kind="tool_request", payload={"name": "finance_query"},
    ))
    store = RunStore(root=tmp_path / "runs")
    run = store.create_run(question="probe", task_type="ask")
    for step_id, name, summary in (
        ("menu", "planning", "此步未开放可调用工具。"),
        (progress.key, progress.stage, progress.message),
        ("verification", "verification", "正在核验证据绑定与回答完整性。"),
        ("telemetry", "context_growth", json.dumps({"turn_count": 1})),
        ("llm_budget", "llm_call_ledger", json.dumps({"records": [_record()]})),
    ):
        store.append_step(run.run_id, step_id=step_id, name=name, status="completed",
                          output_summary=summary)
    path = store.run_dir(run.run_id)
    results, code = _check(path if directory else path / "trace.jsonl")
    assert code == 0 and len(results) == 1
    assert results[0].served == {MODEL: 1}
    assert results[0].unreported == results[0].not_reached == 0


@pytest.mark.parametrize("summary", ("", "not-json", "正在核对调用台账。"))
@pytest.mark.parametrize("name", ("llm_call_ledger", "sub_research", "branch_failed"))
def test_identity_bearing_steps_cannot_disguise_broken_payloads_as_prose(tmp_path, summary, name):
    path = _trace(tmp_path, {"name": name, "output_summary": summary}, _step([_record()]))
    assert _check(path)[1] == 2


@pytest.mark.parametrize("summary", ('{"episode_ref":', "[broken", '[{"kind":"branch_failed"'))
def test_json_like_telemetry_cannot_disguise_truncation_as_prose(tmp_path, summary):
    path = _trace(tmp_path, {"name": "research", "output_summary": summary}, _step([_record()]))
    assert _check(path)[1] == 2


def test_plain_progress_without_ledger_is_not_model_evidence(tmp_path):
    path = _trace(tmp_path, {"name": "planning", "output_summary": "已形成研究计划。"})
    assert _check(path)[1] == 2
    (tmp_path / ma.EPISODE_FILENAME).write_text(json.dumps({"events": [
        {"kind": "model_turn", "payload": {"served_model": MODEL}},
    ]}))
    results, code = _check(tmp_path)
    assert code == 0 and len(results) == 1


def test_progress_prose_does_not_hide_top_level_child_reference(tmp_path):
    path = _trace(tmp_path, _step([_record()]), {
        "name": "research", "output_summary": "一项补充研究已返回证据。",
        "episode_ref": {"episode_id": "missing-child"},
    })
    assert _check(path)[1] == 2


def test_structured_branch_inside_progress_stage_is_still_checked(tmp_path):
    path = _trace(tmp_path, _step([_record()]), {
        "name": "research", "output_summary": json.dumps({"events": [{
            "kind": "branch_completed", "payload": {"served_models": ["wrong-model"]},
        }]}),
    })
    assert _check(path)[1] == 1


def test_wrong_response_model_overrides_matching_request(tmp_path):
    path = _trace(tmp_path, _step([_record(
        reported_model="wrong-model", model=MODEL, requested_model=MODEL,
    )]))
    results, code = _check(path)
    assert code == 1
    assert results[0].unexpected == {"wrong-model": 1}


@pytest.mark.parametrize("reported", (None, "", "  "))
@pytest.mark.parametrize("status", ("success", "failed"))
def test_unreported_attempt_is_not_replaced_by_request_or_success(tmp_path, reported, status):
    path = _trace(tmp_path, _step([
        _record(), _record(attempt_id="attempt-2", reported_model=reported,
                           identity_state="unreported", status=status, model=MODEL, requested_model=MODEL),
    ]))
    results, code = _check(path)
    assert code == 2
    assert results[0].unreported == 1 and results[0].not_reached == 0
    assert _check(path, allow_unreported=True)[1] == 0


@pytest.mark.parametrize("override", (
    {"identity_conflict": True}, {"identity_conflict": "false"},
    {"identity_state": "unreported"}, {"identity_state": "unknown"},
    {"identity_state": "not_called", "reported_model": None},
    {"reported_model": 5.3}, {"status": "pending"}, {"status": []},
), ids=("conflict", "bad-conflict-type", "state-conflict", "unknown-state", "not-called-ledger",
        "bad-model-type", "unfinished", "bad-status-type"))
def test_inconsistent_or_malformed_identity_cannot_be_admitted(tmp_path, override):
    path = _trace(tmp_path, _step([_record(), _record(attempt_id="attempt-2", **override)]))
    assert _check(path, allow_unreported=True)[1] == 2


@pytest.mark.parametrize("key", ("reported_model", "identity_state", "identity_conflict"))
def test_missing_identity_fields_fail_closed_even_with_another_good_call(tmp_path, key):
    record = _record(attempt_id="attempt-2")
    record.pop(key)
    path = _trace(tmp_path, _step([_record(), record]))
    assert _check(path, allow_unreported=True)[1] == 2


def test_a_failed_attempt_with_a_response_still_proves_its_model(tmp_path):
    path = _trace(tmp_path, _step([_record(status="failed")]))
    assert _check(path)[1] == 0  # Model identity, not successful output or answer quality.


def test_mismatch_has_priority_over_conflict(tmp_path):
    path = _trace(tmp_path, _step([_record(reported_model="wrong-model", identity_conflict=True)]))
    assert _check(path)[1] == 1


@pytest.mark.parametrize("summary", ("{broken", "[]", "{}", '{"records": {}}', '{"records": [null]}'))
def test_broken_ledger_cannot_be_hidden_by_another_good_snapshot(tmp_path, summary):
    bad = _step([])
    bad["output_summary"] = summary
    path = _trace(tmp_path, bad, _step([_record()]))
    assert _check(path)[1] == 2


def test_repeated_cumulative_snapshots_do_not_double_count_attempts(tmp_path):
    path = _trace(tmp_path, _step([_record()]), _step([_record(), _record(attempt_id="attempt-2")]))
    results, code = _check(path)
    assert code == 0 and results[0].served == {MODEL: 2}


def test_last_snapshot_cannot_erase_earlier_mismatch(tmp_path):
    path = _trace(tmp_path, _step([_record(reported_model="wrong-model")]), _step([]))
    assert _check(path)[1] == 1


def test_conflicting_reuse_of_attempt_id_is_not_deduplicated_away(tmp_path):
    path = _trace(tmp_path, _step([_record()]), _step([_record(reported_model="wrong-model")]))
    assert _check(path)[1] == 1


def test_matching_trace_does_not_override_missing_episode_child(tmp_path):
    _trace(tmp_path, _step([_record()]))
    (tmp_path / ma.EPISODE_FILENAME).write_text(json.dumps({"events": [
        {"kind": "model_turn", "payload": {"served_model": MODEL}},
        {"kind": "branch_completed", "payload": {"llm_calls": 1, "episode_ref": {"episode_id": "missing"}}},
    ]}))
    assert _check(tmp_path)[1] == 2


@pytest.mark.parametrize("branch,code", (
    ({"kind": "branch_failed", "payload": {"status": "failed", "llm_calls": 0,
        "llm_calls_known": False, "error": "branch_worker_exception:RuntimeError"}}, 2),
    ({"kind": "branch_completed", "payload": {"llm_calls": 1, "served_models": ["wrong-model"]}}, 1),
), ids=("unknown-calls", "mismatch"))
def test_episode_sibling_cannot_hide_trace_only_branch_evidence(tmp_path, branch, code):
    _trace(tmp_path, {"name": "sub_research", "output_summary": json.dumps({"events": [branch]})})
    (tmp_path / ma.EPISODE_FILENAME).write_text(json.dumps({"events": [
        {"kind": "model_turn", "payload": {"served_model": MODEL}},
    ]}))
    assert _check(tmp_path / "trace.jsonl")[1] == code
    results, directory_code = _check(tmp_path)
    assert directory_code == code
    assert len(results) == 2


def test_plain_episode_trace_without_ledger_does_not_add_a_spurious_failure(tmp_path):
    _trace(tmp_path, {"step_id": "intent", "name": "controller", "output_summary": "{}"})
    (tmp_path / ma.EPISODE_FILENAME).write_text(json.dumps({"events": [
        {"kind": "model_turn", "payload": {"served_model": MODEL}},
    ]}))
    results, code = _check(tmp_path)
    assert code == 0 and len(results) == 1
    assert _check(tmp_path / "trace.jsonl")[1] == 2


@pytest.mark.parametrize("child_model", (MODEL, "wrong-model"), ids=("matching", "mismatch"))
def test_episode_references_in_encoded_trace_payload_are_followed(tmp_path, child_model):
    path = _trace(tmp_path, _step([_record()]), {
        "step_id": "research", "name": "sub_research",
        "output_summary": json.dumps({"episode_ref": {"episode_id": "child:1"}}),
    })
    store = tmp_path / "store"
    child = JsonlEpisodeStore(store).episode_dir("child:1")
    child.mkdir(parents=True)
    (child / "events.jsonl").write_text(json.dumps({"kind": "model_turn", "payload": {"served_model": child_model}}))
    assert _check(path)[1] == 2
    results, code = _check(path, episode_store_roots=[store])
    assert code == (0 if child_model == MODEL else 1)
    assert len(results) == 2


def test_malformed_encoded_step_cannot_hide_child_references(tmp_path):
    path = _trace(tmp_path, _step([_record()]), {
        "step_id": "research", "name": "sub_research", "output_summary": '{"episode_ref":',
    })
    assert _check(path)[1] == 2


def test_trace_mismatch_survives_another_steps_broken_json(tmp_path):
    bad = _step([])
    bad["output_summary"] = "{broken"
    path = _trace(tmp_path, bad, _step([_record(reported_model="wrong-model")]))
    assert _check(path)[1] == 1


@pytest.mark.parametrize("records", ([], [_record(reported_model=None, identity_state="unreported")]))
def test_zero_returned_identities_never_admit_even_with_override(tmp_path, records):
    path = _trace(tmp_path, _step(records))
    assert _check(path, allow_unreported=True)[1] == 2


def test_missing_attempt_id_does_not_erase_a_record(tmp_path):
    record = _record(attempt_id=None)
    path = _trace(tmp_path, _step([record, record]))
    results, code = _check(path)
    assert code == 0 and results[0].served == {MODEL: 2}


def test_trace_reference_cycle_and_bad_ref_are_rejected(tmp_path):
    store = tmp_path / "store"
    a = JsonlEpisodeStore(store).episode_dir("a")
    b = JsonlEpisodeStore(store).episode_dir("b")
    for directory, target in ((a, "b"), (b, "a")):
        directory.mkdir(parents=True)
        (directory / "events.jsonl").write_text(json.dumps({
            "kind": "model_turn", "payload": {"served_model": MODEL, "episode_ref": {"episode_id": target}},
        }))
    path = _trace(tmp_path, _step([_record()]), {
        "name": "sub_research", "output_summary": json.dumps({"episode_ref": {"episode_id": "a"}}),
    })
    assert _check(path, episode_store_roots=[store])[1] == 2
    path = _trace(tmp_path, _step([_record()]), {
        "name": "sub_research", "output_summary": json.dumps({"episode_ref": {}}),
    })
    assert _check(path, episode_store_roots=[store])[1] == 2


def test_branch_unknown_call_count_in_trace_does_not_become_zero(tmp_path):
    path = _trace(tmp_path, _step([_record()]), {
        "name": "sub_research", "output_summary": json.dumps({"events": [{
            "kind": "branch_failed", "payload": {"status": "failed", "llm_calls": 0,
                "llm_calls_known": False, "error": "branch_worker_exception:RuntimeError"},
        }]}),
    })
    assert _check(path)[1] == 2


def test_trace_config_or_top_level_models_are_never_response_evidence(tmp_path):
    path = _trace(tmp_path, {"name": "configure", "model": MODEL, "served_model": MODEL,
                             "output_summary": json.dumps({"model": MODEL})})
    assert _check(path)[1] == 2


def test_trace_does_not_infer_expected_model_from_requests(tmp_path):
    path = _trace(tmp_path, _step([_record(model=MODEL, requested_model=MODEL)]))
    results = ma.check_paths([path], (), expect_configured=True)
    assert ma.overall_exit_code(results) == 2


@pytest.mark.parametrize("reported,code", ((MODEL, 0), ("wrong-model", 1), (None, 2)))
def test_real_response_recorder_and_run_store_feed_admission(monkeypatch, tmp_path, reported, code):
    from intelligence.services import llm_refine
    from intelligence.services.run_store import RunStore
    from intelligence.tests.test_llm_call_ledger_usage import _http_provider, _install_http

    body = {"choices": [{"message": {"content": "answer"}}]}
    if reported is not None:
        body["model"] = reported
    _install_http(monkeypatch, body)
    with llm_refine.call_ledger_scope() as ledger:
        llm_refine._post_chat(_http_provider(), [{"role": "user", "content": "probe"}], timeout=1)
    store = RunStore(root=tmp_path / "runs")
    run = store.create_run(question="probe", task_type="ask")
    store.append_step(run.run_id, step_id="llm_budget", name="llm_call_ledger", status="completed",
                      output_summary=json.dumps(ledger.summary()))
    assert _check(store.run_dir(run.run_id))[1] == code


def test_cli_reads_run_directory_without_allow_unreported(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location(
        "trace_admission_cli", Path(__file__).resolve().parents[2] / "scripts/check_model_admission.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    path = _trace(tmp_path, _step([_record()]))
    assert cli.main([str(tmp_path), "--expect-model", MODEL, "--no-episode-store", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["results"][0]["source"] == str(path)
    assert result["results"][0]["served"] == {MODEL: 1}
