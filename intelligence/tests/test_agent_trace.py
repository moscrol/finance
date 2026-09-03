"""agent 直调落痕：与 Workbench 同构，且绝不静默换根。"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "agent_trace.py"


def _load() -> ModuleType:
    name = "_agent_trace_under_test"
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def trace() -> ModuleType:
    return _load()


def _write_pair(trace: ModuleType, root: Path, *, diverge: bool) -> tuple[str, str]:
    with trace.AgentRun("左", root=root, user="agent-adhoc") as left:
        with left.step("route.1", "question_router") as step:
            step.output = "lane=research"
        with left.step("retrieve.1", "evidence_search") as step:
            step.output = "hits=3"
    with trace.AgentRun("右", root=root, user="peer-user") as right:
        with right.step("route.1", "question_router") as step:
            step.output = "lane=research"
        name = "answer_synthesis" if diverge else "evidence_search"
        step_id = "synthesize.1" if diverge else "retrieve.1"
        with right.step(step_id, name) as step:
            step.output = "hits=3"
    return left.handle.encode(), right.handle.encode()


def test_refuses_to_guess_the_users_root(trace: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FORESIGHT_USERS_DIR", raising=False)
    with pytest.raises(trace.TraceSetupError, match="没能确定 users 根"):
        trace.open_run("任意题")
    repo_users = Path(__file__).resolve().parents[2] / "intelligence" / "users"
    leaked = list(repo_users.glob("agent-adhoc/runs/*")) if repo_users.is_dir() else []
    assert leaked == []


def test_root_flag_writes_workbench_layout(trace: ModuleType, tmp_path: Path) -> None:
    handle, origin = trace.open_run("光伏怎么看", root=tmp_path)
    mapped = trace.append_step(
        handle, step_id="route.1", name="question_router", output_summary="lane=research"
    )
    trace.close_run(handle)

    run_dir = tmp_path / "agent-adhoc" / "runs" / handle.run_id
    assert origin == "--root"
    assert mapped == "route"
    assert handle.user == "agent-adhoc"
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "trace.jsonl").is_file()
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "completed"
    assert run["question"] == "光伏怎么看"
    step = json.loads((run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert step["name"] == "question_router"
    assert step["step_id"] == "route.1"


def test_env_override_is_restored(trace: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", "/should-not-stick")
    trace.open_run("题", root=tmp_path)
    assert os.environ["FORESIGHT_USERS_DIR"] == "/should-not-stick"

    monkeypatch.delenv("FORESIGHT_USERS_DIR")
    trace.open_run("题2", root=tmp_path)
    assert "FORESIGHT_USERS_DIR" not in os.environ


def test_from_port_reads_the_live_process_root(
    trace: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(trace, "_pid_listening_on", lambda port: 4242)
    monkeypatch.setattr(
        trace, "_process_env", lambda pid: {"FORESIGHT_USERS_DIR": str(tmp_path)}
    )
    handle, origin = trace.open_run("题", from_port=8792)
    assert handle.root == tmp_path.resolve()
    assert "4242" in origin


def test_from_port_without_env_fails_closed(
    trace: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace, "_pid_listening_on", lambda port: 7)
    monkeypatch.setattr(trace, "_process_env", lambda pid: {})
    with pytest.raises(trace.TraceSetupError, match="没有设 FORESIGHT_USERS_DIR"):
        trace.open_run("题", from_port=8792)


def test_unmapped_step_is_rejected(trace: ModuleType, tmp_path: Path) -> None:
    handle, _ = trace.open_run("题", root=tmp_path)
    with pytest.raises(trace.TraceSetupError, match="映射不到 L1"):
        trace.append_step(handle, step_id="misc.1", name="finance_query")
    assert not (handle.run_dir() / "trace.jsonl").exists()


def test_tool_name_maps_when_step_id_carries_vocab(trace: ModuleType, tmp_path: Path) -> None:
    handle, _ = trace.open_run("题", root=tmp_path)
    mapped = trace.append_step(
        handle, step_id="retrieve.finance_query", name="finance_query"
    )
    assert mapped == "retrieve"


def test_agent_run_marks_failed_on_exception(trace: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with trace.AgentRun("题", root=tmp_path) as run:
            with run.step("route.1", "question_router"):
                raise RuntimeError("boom")
    payload = json.loads((run.handle.run_dir() / "run.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    step = json.loads((run.handle.run_dir() / "trace.jsonl").read_text(encoding="utf-8"))
    assert step["status"] == "failed"


def test_compare_equivalent_and_first_divergence(
    trace: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    left, right = _write_pair(trace, tmp_path, diverge=False)
    assert trace.compare(left, right) == 0
    same = json.loads(capsys.readouterr().out)
    assert same["comparison"]["pre_divergence_equivalence"] == "fully_equivalent"

    left, right = _write_pair(trace, tmp_path, diverge=True)
    assert trace.compare(left, right) == 0
    diff = json.loads(capsys.readouterr().out)
    first = diff["comparison"]["first_divergence"]
    assert first["relation"] == "step_mismatch"
    assert first["left_step"] == "retrieve"
    assert first["right_step"] == "synthesize"


def test_compare_accepts_bare_run_id_on_same_root(trace: ModuleType, tmp_path: Path) -> None:
    left, right = _write_pair(trace, tmp_path, diverge=False)
    right_id = trace.RunHandle.decode(right).run_id
    assert (tmp_path / "peer-user" / "runs" / right_id / "trace.jsonl").is_file()
    assert trace.compare(left, right_id) == 0


def test_cli_open_step_close_roundtrip(
    trace: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        trace.main(
            ["open", "--question", "组件怎么对标", "--root", str(tmp_path)]
        )
        == 0
    )
    handle = capsys.readouterr().out.strip().splitlines()[-1]
    assert (
        trace.main(
            [
                "step",
                handle,
                "--step-id",
                "route.1",
                "--name",
                "question_router",
                "--output",
                "lane=research",
            ]
        )
        == 0
    )
    assert trace.main(["close", handle]) == 0
    run_id = trace.RunHandle.decode(handle).run_id
    run_dir = tmp_path / "agent-adhoc" / "runs" / run_id
    assert (run_dir / "trace.jsonl").is_file()


def test_cli_open_without_root_exits_2(
    trace: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORESIGHT_USERS_DIR", raising=False)
    assert trace.main(["open", "--question", "题"]) == 2
