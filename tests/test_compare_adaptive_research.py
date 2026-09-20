"""The paired probe must collect the right final message and clean up failures."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

from scripts import compare_adaptive_research as probe
from scripts import inspect_adaptive_research as inspection


@pytest.mark.parametrize("failed", [False, True])
def test_probe_waits_for_delivery_and_closes_isolated_sidecar(monkeypatch, tmp_path, failed):
    args = Namespace(
        output=tmp_path, python=Path("python"), launcher=Path("launcher"),
        gateway="http://localhost/gateway", model="test-model", question="test question", timeout=10,
    )
    monkeypatch.setattr(probe, "choose_port", lambda **kwargs: 8807)
    monkeypatch.setattr(probe, "assert_safe_to_start", lambda **kwargs: None)
    monkeypatch.setattr(probe.time, "sleep", lambda _seconds: None)
    commands = []

    class Process:
        terminated = False
        waited = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.waited = True
            return 0

    process = Process()

    def popen(command, **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(probe.subprocess, "Popen", popen)
    calls = []
    run_reads = 0
    secret = "test-credential-not-for-artifacts"

    def request(base, path, payload=None, *, method=None):
        nonlocal run_reads
        assert base == "http://127.0.0.1:8807"
        calls.append((path, method))
        if path == "/api/health":
            return {"runtime": {"loaded_code_root": str(probe.REPO / "intelligence")}}
        if path == "/api/llm/config":
            assert payload["api_key"] == secret
            assert payload["remember"] is False
            return {}
        if method == "DELETE":
            return {}
        if path == "/api/conversations":
            assert payload["user"] == "adaptive-on"
            return {"conversation_id": "conversation"}
        if payload is not None:
            return {"run_id": "new-run", "assistant_message_id": "new-message"}
        if path.startswith("/api/runs/"):
            run_reads += 1
            return {"status": "failed" if failed else "completed", "delivery_pending": run_reads == 1}
        assert run_reads == 2
        return {"messages": [
            {"message_id": "old-message", "content": "wrong old answer"},
            {"message_id": "new-message", "content": "right new answer"},
        ]}

    monkeypatch.setattr(probe, "request", request)
    if failed:
        with pytest.raises(RuntimeError, match="run ended failed"):
            probe.run_arm(args, "on", secret)
        assert not (tmp_path / "on/answer.md").exists()
    else:
        result = probe.run_arm(args, "on", secret)
        assert result["status"] == "completed" and result["run_id"] == "new-run"
        assert (tmp_path / "on/answer.md").read_text() == "right new answer"
        assert json.loads((tmp_path / "on/run.json").read_text())["delivery_pending"] is False
    assert process.terminated and process.waited
    assert ("/api/llm/config?user=adaptive-on", "DELETE") in calls
    assert "WORKBENCH_ADAPTIVE_RESEARCH=on" in commands[0][-1]
    assert all(secret not in path.read_text() for path in tmp_path.rglob("*") if path.is_file())


def test_inspector_reports_activity_without_a_quality_score():
    events = [
        {"sequence": 1, "kind": "model_input", "payload": {"source": "adaptive_research_checkpoint"}},
        {"sequence": 2, "kind": "model_turn", "payload": {"content": "{}", "served_model": "test-model"}},
        {"sequence": 3, "kind": "plan", "payload": {"revision": 1, "perspectives": []}},
        {"sequence": 4, "kind": "tool_request", "payload": {"name": "market_data", "arguments": {}}},
        {"sequence": 5, "kind": "tool_budget_state", "payload": {"runtime_budget": {"research_progress": {"batch": 1, "adaptive_research": {"plan_revision": 1}}}}},
    ]
    result = inspection.summarize({"outcome": {"status": "partial", "gaps": ["unresolved"]}}, events)
    assert result["plan_count"] == 1 and result["checkpoint_count"] == 1
    assert result["feedback_batches"] == 1
    assert result["served_models"] == ["test-model"]
    assert result["declared_gaps"] == ["unresolved"]
    assert result["semantic_quality"].startswith("not_scored")
    assert result["plans"][0]["plan"] == events[2]["payload"]


def test_single_arm_inspection_does_not_claim_paired_controls(monkeypatch, tmp_path):
    fixtures = {
        "protocol.json": {"arms": ["on"]},
        "on/raw-run/continuous-episode.json": {"outcome": {}, "events": []},
        "on/result.json": {"elapsed_seconds": 1},
        "on/health.json": {"runtime": {"loaded_tree_fingerprint": "test"}},
    }
    for name, value in fixtures.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    monkeypatch.setattr(inspection.sys, "argv", ["inspect", str(tmp_path)])
    assert inspection.main() == 0
    controls = json.loads((tmp_path / "inspection/controls.json").read_text())
    assert controls["paired"] is False
    assert controls["same_loaded_code"] is None
    assert controls["same_initial_configuration"] is None


def test_probe_accepts_explicit_single_arm(monkeypatch, tmp_path):
    destination = tmp_path / "single"
    monkeypatch.setenv("PROBE_TEST_KEY", "not-a-real-credential")
    monkeypatch.setattr(probe.sys, "argv", [
        "probe", "--output", str(destination), "--gateway", "http://localhost", "--model", "test",
        "--question", "test", "--key-env", "PROBE_TEST_KEY", "--arms", "on",
    ])
    monkeypatch.setattr(probe.subprocess, "check_output", lambda *args, **kwargs: "test")
    calls = []

    def run_arm(args, arm, key):
        calls.append(arm)
        return {"arm": arm, "status": "completed"}

    monkeypatch.setattr(probe, "run_arm", run_arm)
    assert probe.main() == 0 and calls == ["on"]
    assert json.loads((destination / "protocol.json").read_text())["arms"] == ["on"]


def test_probe_refuses_to_overwrite_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("PROBE_TEST_KEY", "not-a-real-credential")
    monkeypatch.setattr(probe.sys, "argv", [
        "probe", "--output", str(tmp_path), "--gateway", "http://localhost", "--model", "test",
        "--question", "test", "--key-env", "PROBE_TEST_KEY",
    ])
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []
