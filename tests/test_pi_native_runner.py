"""Offline contracts for the Pi-native experiment runner."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pi_native_runner", REPO / "integrations/pi/run_native.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


@pytest.fixture
def frozen(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    _git(code, "init", "-q")
    (code / "backend.py").write_text("VALUE = 1\n")
    skill = code / "skills/finance-mode/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("methodology\n")
    _git(code, "add", "backend.py", "skills/finance-mode/SKILL.md")
    _git(code, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    root = tmp_path / "run"
    (root / "kit").mkdir(parents=True)
    (root / "kit/bridge.py").write_text("bridge\n")
    (root / "market_feature_store.duckdb").write_bytes(b"fixture database")
    (root / "rag-bindings.json").write_text('{"generation":"fixture"}')
    plan = {
        "code_root": str(code), "revision": _git(code, "rev-parse", "HEAD"), "dirty": False,
        "database_sha256": runner.digest(root / "market_feature_store.duckdb"),
        "kit_hashes": {"bridge.py": runner.digest(root / "kit/bridge.py")},
        "skill_hashes": {"finance-mode": runner.digest(skill)},
        "runner_sha256": runner.digest(Path(runner.__file__)),
        "rag_bindings": str(root / "rag-bindings.json"),
        "rag_bindings_sha256": runner.digest(root / "rag-bindings.json"),
    }
    return code, root, plan


def test_unchanged_plan_passes(frozen):
    _, root, plan = frozen
    runner.verify_plan(plan, root)


@pytest.mark.parametrize("change", ["tracked", "untracked", "runner", "rag"])
def test_freeze_rejects_changes_even_when_git_head_does_not_move(frozen, change):
    code, root, plan = frozen
    if change == "tracked":
        (code / "backend.py").write_text("VALUE = 2\n")
    elif change == "untracked":
        (code / "injected.py").write_text("VALUE = 2\n")
    elif change == "runner":
        plan["runner_sha256"] = "different-runner"
    else:
        (root / "rag-bindings.json").write_text('{"generation":"different"}')
    assert _git(code, "rev-parse", "HEAD") == plan["revision"]
    with pytest.raises((AssertionError, RuntimeError, ValueError)):
        runner.verify_plan(plan, root)


def test_top_level_tool_allowlist_keeps_financial_tools(tmp_path):
    plan = {"code_root": str(REPO), "pi_bin": "pi", "os_skill": "finance-mode",
            "app_skills": ["finance-market-review"], "model": "glm-5.3-flash",
            "thinking": "low", "subagents": False}
    command = runner.pi_command(plan, tmp_path, "test")
    assert set(command[command.index("--tools") + 1].split(",")) == {"read", "finance_call"}
    assert "--no-approve" in command
    plan["subagents"] = True
    command = runner.pi_command(plan, tmp_path, "test")
    assert "spawn_sub_agent" in command[command.index("--tools") + 1].split(",")


@pytest.mark.parametrize("exit_code,reason,admission,text,expected", [
    (0, "stop", True, "answer", True),
    (0, "error", True, "partial answer", False),
    (0, "length", True, "partial answer", False),
    (0, "stop", False, "answer", False),
    (124, "stop", True, "answer", False),
    (0, "stop", True, "", False),
])
def test_transport_success_requires_complete_model_admitted_answer(exit_code, reason, admission, text, expected):
    arm = {"exit": exit_code, "stop_reason": reason, "model_admission": admission,
           "answer_chars": len(text)}
    assert runner.arm_completed(arm) is expected


def test_jsonl_reader_does_not_split_unicode_line_separators(tmp_path):
    source = tmp_path / "events.jsonl"
    source.write_text(json.dumps({"text": "a\u2028b\u2029c"}, ensure_ascii=False) + "\n")
    assert runner.read_jsonl(source) == [{"text": "a\u2028b\u2029c"}]


def test_keychain_reference_is_resolved_without_a_shell(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "fixture-key\n", "")

    monkeypatch.setattr(runner.subprocess, "run", run)
    expression = "$(security find-generic-password -a fixture-user -s finance-fixture -w 2>/dev/null || true)"
    assert runner.resolve_api_key(expression) == "fixture-key"
    assert calls[0][0] == ["/usr/bin/security", "find-generic-password", "-a", "fixture-user",
                            "-s", "finance-fixture", "-w"]
    assert not calls[0][1].get("shell", False)


@pytest.mark.parametrize("value", [None, "$KEY", "${KEY}", "$(curl example.invalid)",
    "$(security find-generic-password -a fixture -s fixture -w; echo nope)"])
def test_unsafe_or_unresolved_credentials_fail_before_transport(value, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("must not execute an arbitrary credential command")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    with pytest.raises((ValueError, RuntimeError)):
        runner.resolve_api_key(value)


def test_literal_key_does_not_spawn_a_process(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("literal credentials do not need a subprocess")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    assert runner.resolve_api_key("fixture-key") == "fixture-key"
