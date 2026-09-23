from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

from intelligence.eval import knevo_regression as regression
from scripts import workbench_probe


def _modified_suite(tmp_path, change):
    payload = json.loads(regression.DEFAULT_SUITE.read_text())
    change(payload)
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(payload, ensure_ascii=False))
    return path


def test_coverage_is_derived_from_q18_candidates_and_three_original_packs():
    cases = regression.load_suite()
    candidate = json.loads((regression.DEFAULT_SUITE.parent / "knevo_q18_candidate_cases.json").read_text())
    ids = {case.case_id for case in cases}
    assert {case["id"] for group in candidate["groups"] for case in group["cases"]} <= ids
    assert {f"K260917-pack{i}" for i in (1, 2, 3)} <= ids
    assert "Q14-news-layers" in ids
    payload = json.loads(regression.DEFAULT_SUITE.read_text())
    assert {cid for case in payload["cases"] for cid in case.get("criteria_ids", [])} == {
        f"K260917-0{i}" for i in range(1, 8)
    }


def test_original_questions_are_byte_identical_and_contain_all_eight_questions():
    root = regression.REPO / "docs/learning/knevo-distill/batches/2026-09-17-three-packs"
    manifest = json.loads((root / "manifest.json").read_text())
    for group in manifest["groups"]:
        n = group["group"]
        case = regression.select_case(regression.DEFAULT_SUITE, f"K260917-pack{n}")
        assert case.question.encode() == (root / f"q{n}-question.txt").read_bytes()
        assert case.question_sha256 == group["question_sha256"]
        assert all(f"{i}. " in case.question for i in range(1, 9))
    assert hashlib.sha256((root / manifest["original_file"]).read_bytes()).hexdigest() == manifest["original_sha256"]


@pytest.mark.parametrize("change", [
    lambda p: p.update(status="blind_benchmark"),
    lambda p: p.update(cases=[]),
    lambda p: p["cases"].append(p["cases"][0]),
    lambda p: p["cases"][0].update(id="../escape"),
    lambda p: p["cases"][0].update(pass_rules=[]),
    lambda p: p["cases"][0].update(not_tested=""),
    lambda p: p["cases"][0].update(mode="real_storage"),
    lambda p: p["cases"][0].update(question_file="README.md"),
    lambda p: p["cases"][-1].update(question_sha256="0" * 64),
    lambda p: p["cases"][-1].update(question_file="../README.md"),
    lambda p: p["cases"][0].update(source="does-not-exist.md"),
])
def test_bad_suite_refused(tmp_path, change):
    with pytest.raises(ValueError):
        regression.load_suite(_modified_suite(tmp_path, change))


def test_symlink_question_outside_repo_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    (repo / "linked.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        regression._repo_file(repo, "linked.txt")


def test_prepare_never_reports_execution_or_semantic_pass_and_cannot_overwrite(tmp_path):
    packet = tmp_path / "packet"
    report = regression.prepare(packet)
    assert report["status"] == "prepared_not_run"
    assert report["automatic_semantic_grading"] is False
    for row in report["cases"]:
        assert row["execution"] == "not_run"
        assert row["semantic_verdict"] == "not_evaluated"
        assert row["run_id"] is None
        assert row["evidence"] == []
        data = (packet / row["question_file"]).read_bytes()
        assert regression.sha256(data) == row["question_sha256"]
        assert "pass_rules" not in data.decode()
    with pytest.raises(FileExistsError):
        regression.prepare(packet)


def test_workbench_sends_only_selected_question_not_rubric(monkeypatch, capsys):
    posts = []
    case = regression.select_case(regression.DEFAULT_SUITE, "Q18-G1b-retrieval-miss")

    def fake_call(base, path, payload=None):
        assert base == "http://localhost:18891"
        if payload is not None:
            posts.append((path, payload))
        if path == "/api/conversations":
            return {"conversation_id": "conv_test"}
        if path.endswith("/messages") and payload is not None:
            return {"run_id": "run_test", "assistant_message_id": "msg_test"}
        if path.startswith("/api/runs/"):
            return {"status": "completed"}
        return [{"message_id": "msg_test", "content": "a delivered answer, not graded"}]

    monkeypatch.setattr(workbench_probe, "_call", fake_call)
    monkeypatch.setattr(sys, "argv", [
        "probe", "--user", "probe-knevo", "--case-set", str(regression.DEFAULT_SUITE),
        "--case-id", case.case_id, "--port", "18891", "--poll-seconds", "0",
    ])
    assert workbench_probe.main() == 0
    assert posts[-1][1]["content"] == case.question
    assert all(rule not in posts[-1][1]["content"] for rule in case.pass_rules)
    output = capsys.readouterr().out
    assert case.question_sha256 in output
    assert "delivery is not semantic acceptance" in output


@pytest.mark.parametrize("extra", [
    [],
    ["--case-id", "Q18-G1b-retrieval-miss"],  # no explicit port
    ["--case-id", "unknown", "--port", "18891"],
    ["--case-id", "Q18-G1b-retrieval-miss", "--port", "0"],
    ["--case-id", "Q18-G1b-retrieval-miss", "--port", "65536"],
    ["--case-id", "Q18-G1b-retrieval-miss", "--port", "18891", "--question", "extra"],
])
def test_invalid_probe_selection_never_calls_http(monkeypatch, extra):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid input reached HTTP")

    monkeypatch.setattr(workbench_probe, "_call", forbidden)
    monkeypatch.setattr(sys, "argv", [
        "probe", "--user", "probe-knevo", "--case-set", str(regression.DEFAULT_SUITE), *extra,
    ])
    with pytest.raises(SystemExit) as exc:
        workbench_probe.main()
    assert exc.value.code == 2


def test_artifact_hint_does_not_claim_a_fixed_user_root():
    hint = workbench_probe._artifacts_hint("probe-knevo", "run_test")
    assert "probe-knevo/runs/run_test" in hint
    assert "FORESIGHT_USERS_DIR" in hint
    assert ".local/share" not in hint


def test_repo_sources_are_real_files():
    for case in regression.load_suite():
        assert (regression.REPO / case.source).is_file()
        assert case.pass_rules and case.fail_rules and case.not_tested
        if case.mode == "material_proxy":
            assert "虚构" in case.question


def _saved_run(tmp_path, case, *, episode=None, report=None):
    directory = tmp_path / "run_test"
    directory.mkdir()
    (directory / "run.json").write_text(json.dumps({
        "run_id": directory.name, "user": "probe-test",
        "question": case.question, "status": "completed",
    }))
    (directory / "answer.md").write_text("证据不足，暂不能可靠回答。")
    for name, value in (("continuous-episode.json", episode), ("report.json", report)):
        if value is not None:
            (directory / name).write_text(json.dumps(value))
    return directory


def test_inspect_fallback_and_internal_pass_never_become_rubric_pass(tmp_path):
    case = regression.load_suite()[0]
    directory = _saved_run(tmp_path, case, episode={
        "task_frame": {"raw_question": case.question, "question_type": "general_finance_qa"},
        "semantic_verifier": {"status": "completed", "judge_status": "repaired"},
        "events": [{"kind": "tool_request", "payload": {"name": "kb_search", "call_id": "c1"}}],
    })
    report = regression.inspect_run(directory, case)
    assert report["transport_status"] == report["internal_semantic_status"] == "completed"
    assert report["semantic_verdict"] == "not_evaluated"
    assert report["tool_requests"] == [{"name": "kb_search", "call_id": "c1"}]
    assert report["frame_question_same_after_strip"] is True
    assert report["frame_source"] == "private_episode"
    assert report["artifact_sha256"]["answer.md"] == regression.sha256((directory / "answer.md").read_bytes())
    assert case.question not in json.dumps(report, ensure_ascii=False)


def test_inspect_missing_audit_is_unknown_and_clarification_keeps_frame_change(tmp_path):
    case = regression.load_suite()[-1]
    directory = _saved_run(tmp_path, case, report={
        "task_type": "clarify", "task_frame": {"raw_question": case.question.replace("D3", "")},
    })
    result = regression.inspect_run(directory, case)
    assert result["tool_audit_available"] is False
    assert result["tool_requests"] is None
    assert result["internal_judge_status"] is None
    assert result["invalid_actions"] is None
    assert result["judge_protocol_failure"] is None
    assert result["material_review_stages"] is None
    assert result["frame_question_same_after_strip"] is False
    assert result["task_type"] == "clarify"
    assert result["frame_source"] == "public_report"
    assert "do not prove the actual model input" in result["boundary"]


@pytest.mark.parametrize("field,value", [("question", "another question"), ("run_id", "run_wrong")])
def test_inspect_refuses_mismatched_case_or_run(tmp_path, field, value):
    case = regression.load_suite()[0]
    directory = _saved_run(tmp_path, case)
    path = directory / "run.json"
    payload = json.loads(path.read_text())
    payload[field] = value
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="match"):
        regression.inspect_run(directory, case)


def test_inspect_zero_calls_requires_episode_event_audit(tmp_path):
    case = regression.load_suite()[0]
    directory = _saved_run(tmp_path, case, episode={"events": []})
    result = regression.inspect_run(directory, case)
    assert result["tool_audit_available"] is True
    assert result["tool_requests"] == []
    assert result["frame_question_same_after_strip"] is None


def test_inspect_preserves_protocol_and_budget_diagnostics_without_private_text(tmp_path):
    case = regression.load_suite()[0]
    failure = {
        "reason_codes": ["material_claim_checks"], "response_chars": 180,
        "response_sha256": "a" * 64, "response_truncated": False,
        "response_json": "PRIVATE_MODEL_RETURN", "future_private_field": "PRIVATE_FUTURE",
    }
    directory = _saved_run(tmp_path, case, episode={
        "events": [{"kind": "invalid_action", "payload": {
            "code": "bad_claim_binding", "kind": "format",
            "disposition": "invalid_model_finish", "reason": "PRIVATE_WRITER_TEXT",
        }}],
        "semantic_verifier": {
            "status": "partial", "judge_status": "unavailable",
            "judge_protocol_failure": failure,
            "material_review_calls": [
                {"stage": "material_review", "unavailable": False,
                 "timeout_asked": 75, "remaining_seconds_at_entry": 150,
                 "request": {"text": "PRIVATE_REQUEST"},
                 "report": {"passed": False, "rejected_sentence_indexes": [4],
                            "issues": ["PRIVATE_JUDGE_REASON"]}},
                {"stage": "nonfactual_review", "unavailable": True,
                 "issue": "semantic judge deadline exhausted",
                 "timeout_asked": 0, "remaining_seconds_at_entry": 0,
                 "protocol_failure": failure},
            ],
        },
    })
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    result = regression.inspect_run(directory, case)
    assert result["invalid_actions"] == [{
        "code": "bad_claim_binding", "kind": "format", "disposition": "invalid_model_finish",
    }]
    assert result["judge_protocol_failure"] == {
        "reason_codes": ["material_claim_checks"], "response_chars": 180,
        "response_sha256": "a" * 64, "response_truncated": False,
    }
    first, second = result["material_review_stages"]
    assert first["report_passed"] is False
    assert first["rejected_sentence_indexes"] == [4]
    assert first["deadline_exhausted"] is False
    assert second["unavailable"] is True
    assert second["deadline_exhausted"] is True
    assert second["remaining_seconds_at_entry"] == 0
    assert second["report_passed"] is None
    assert second["protocol_failure"] == result["judge_protocol_failure"]
    assert result["semantic_verdict"] == "not_evaluated"
    assert "PRIVATE_" not in json.dumps(result)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_inspect_absent_diagnostics_do_not_mean_success(tmp_path):
    case = regression.load_suite()[0]
    directory = _saved_run(tmp_path, case, episode={"events": []})
    result = regression.inspect_run(directory, case)
    assert result["invalid_actions"] == []
    assert result["judge_protocol_failure"] is None
    assert result["material_review_stages"] is None
    assert result["semantic_verdict"] == "not_evaluated"


def test_inspect_refuses_artifact_symlink_outside_run(tmp_path):
    case = regression.load_suite()[0]
    directory = _saved_run(tmp_path, case)
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    (directory / "answer.md").unlink()
    (directory / "answer.md").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        regression.inspect_run(directory, case)


def test_cli_inspects_offline(tmp_path, monkeypatch, capsys):
    case = regression.load_suite()[0]
    directory = _saved_run(tmp_path, case)
    monkeypatch.setattr(sys, "argv", ["regression", "--inspect-run", str(directory), "--case-id", case.case_id])
    assert regression.main() == 0
    assert json.loads(capsys.readouterr().out)["semantic_verdict"] == "not_evaluated"


def test_cli_prepares_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["regression", "--prepare", str(tmp_path / "packet")])
    assert regression.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prepared_not_run"
    assert (Path(tmp_path) / "packet/review-plan.json").is_file()
