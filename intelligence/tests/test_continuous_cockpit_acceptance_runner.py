from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import socket

import pytest

from scripts import run_continuous_cockpit_acceptance as runner


SECRET = "cockpit-secret-must-not-leak"
REVISION = "a" * 40


def _health(identity: runner.RunnerIdentity, runtime_id: str = "runtime-1") -> dict:
    return {
        "status": "healthy",
        "runtime": {
            "runtime_instance_id": runtime_id,
            "source_revision": identity.revision,
            "source_dirty": False,
            "code_root": identity.code_root,
            "import_root": identity.code_root,
            "continuous_agent": {"mode": identity.mode},
            "agent_runtime": {
                "backend": identity.backend,
                "model": identity.model,
                "provider_label": identity.provider_label,
                "provider_protocol": identity.provider_protocol,
                "provider_chain_size": 1,
                "ready": True,
            },
        },
    }


def test_load_cockpit_key_requires_first_non_empty_key(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"api-keys": [SECRET]}), encoding="utf-8")

    assert runner.load_cockpit_api_key(config) == SECRET

    config.write_text(json.dumps({"api-keys": []}), encoding="utf-8")
    with pytest.raises(runner.RunnerError) as exc_info:
        runner.load_cockpit_api_key(config)
    assert SECRET not in str(exc_info.value)


def test_child_env_removes_all_other_provider_secrets(tmp_path: Path) -> None:
    inherited = {
        "GLM_API_KEY": "old-glm",
        "ZHIPU_API_KEY": "old-zhipu",
        "DEEPSEEK_API_KEY": "old-deepseek",
        "OPENAI_API_KEY": "old-openai",
        "PYTHONPATH": "/wrong/root",
        "KEEP_ME": "yes",
    }
    env = runner.build_child_env(
        api_key=SECRET,
        code_root=tmp_path / "code",
        data_root=tmp_path / "data",
        users_root=tmp_path / "users",
        inherited=inherited,
    )

    assert env["OPENAI_API_KEY"] == SECRET
    assert env["AGENT_RUNTIME_BACKEND"] == "sdk_gpt"
    assert env["ASK_CONTINUOUS_RUNTIME"] == "on"
    assert env["AGENT_RUNTIME_PROVIDER_LABEL"] == "cockpit_local"
    assert env["KEEP_ME"] == "yes"
    assert env["PYTHONPATH"] == str((tmp_path / "code").resolve())
    for name in runner.PROVIDER_SECRET_ENV - {"OPENAI_API_KEY"}:
        assert name not in env


def test_protocol_smoke_sends_only_bounded_responses_request(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_request(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        if url.endswith("/models"):
            return {"data": [{"id": "gpt-5.6-sol"}]}
        return {
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "text": "OK"}]}],
        }

    monkeypatch.setattr(runner, "_request_json", fake_request)
    result = runner.cockpit_protocol_smoke(api_key=SECRET)

    assert result == {
        "models_ok": True,
        "model": "gpt-5.6-sol",
        "response_status": "completed",
        "output_ok": True,
    }
    assert calls[0]["url"].endswith("/models")
    assert calls[1]["url"].endswith("/responses")
    assert calls[1]["payload"] == {
        "model": "gpt-5.6-sol",
        "input": "Reply exactly OK.",
        "max_output_tokens": 16,
        "store": False,
    }
    assert all(call["api_key"] == SECRET for call in calls)
    assert SECRET not in json.dumps(result, ensure_ascii=False)


def test_clean_checkout_and_production_port_gates(monkeypatch, tmp_path: Path) -> None:
    def dirty_capture(command, *, cwd):
        del cwd
        if command[1] == "status":
            return " M private-file"
        return REVISION

    monkeypatch.setattr(runner, "_capture", dirty_capture)
    with pytest.raises(runner.RunnerError, match="dirty"):
        runner.clean_revision(tmp_path)

    with pytest.raises(runner.RunnerError, match="8792"):
        runner.ensure_port_available(8792)


def test_occupied_port_is_rejected() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    try:
        with pytest.raises(runner.RunnerError, match="占用"):
            runner.ensure_port_available(port)
    finally:
        sock.close()


def test_python_executable_keeps_virtualenv_symlink(tmp_path: Path) -> None:
    base_python = tmp_path / "python-base"
    base_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    base_python.chmod(0o755)
    venv_python = tmp_path / "venv-python"
    venv_python.symlink_to(base_python)

    observed = runner.python_executable_path(str(venv_python))

    assert observed == str(venv_python)
    assert observed != str(base_python.resolve())


def test_invoke_acceptance_command_does_not_put_key_in_command_or_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        output = Path(command[command.index("--output") + 1])
        output.write_text(
            json.dumps({"acceptance_eligible": True, "execution_summary": {"layer1_eligible": True}}),
            encoding="utf-8",
        )
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    identity = runner.RunnerIdentity(revision=REVISION, code_root=str(tmp_path))
    output = tmp_path / "receipt.json"
    record = runner.invoke_acceptance(
        code_root=tmp_path,
        base_url="http://127.0.0.1:8801",
        user="alice",
        timeout=1,
        identity=identity,
        output_path=output,
        case_ids=("A4-dual-red",),
        python_executable="/python",
        env={"OPENAI_API_KEY": SECRET},
    )

    assert record["acceptance_eligible"] is True
    assert SECRET not in json.dumps(captured["command"])
    assert SECRET not in output.read_text(encoding="utf-8")
    assert captured["env"]["OPENAI_API_KEY"] == SECRET


def test_full_suite_runs_canary_then_full_on_same_server(monkeypatch, tmp_path: Path) -> None:
    args = runner.build_parser().parse_args(
        [
            "--suite",
            "full",
            "--code-root",
            str(tmp_path),
            "--data-root",
            str(tmp_path),
            "--users-root",
            str(tmp_path / "users"),
            "--output-dir",
            str(tmp_path / "out"),
            "--port",
            "8803",
        ]
    )
    identity = runner.RunnerIdentity(revision=REVISION, code_root=str(tmp_path.resolve()))
    health = _health(identity)
    calls: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr(runner, "clean_revision", lambda _root: REVISION)
    monkeypatch.setattr(runner, "load_cockpit_api_key", lambda _path: SECRET)
    monkeypatch.setattr(
        runner,
        "cockpit_protocol_smoke",
        lambda **_kwargs: {
            "models_ok": True,
            "model": "gpt-5.6-sol",
            "response_status": "completed",
            "output_ok": True,
        },
    )

    @contextmanager
    def fake_server(**kwargs):
        del kwargs
        yield runner.ServerContext(
            process=None,  # type: ignore[arg-type]
            base_url="http://127.0.0.1:8803",
            identity=identity,
            health=health,
            env={"OPENAI_API_KEY": SECRET},
        )

    monkeypatch.setattr(runner, "isolated_server", fake_server)
    monkeypatch.setattr(runner, "_request_json", lambda *_args, **_kwargs: health)

    def fake_invoke(**kwargs):
        case_ids = tuple(kwargs["case_ids"])
        calls.append((str(kwargs["base_url"]), case_ids))
        output = Path(kwargs["output_path"])
        output.write_text("{}", encoding="utf-8")
        if case_ids:
            summary = {
                "total_turns": 6,
                "path_matches": 6,
                "continuous_episode_turns": 4,
                "valid_episode_receipts": 4,
                "layer1_eligible": True,
            }
        else:
            summary = {
                "total_turns": 30,
                "path_matches": 30,
                "continuous_episode_turns": 28,
                "valid_episode_receipts": 28,
                "layer1_eligible": True,
            }
        return {"acceptance_eligible": True, "execution_summary": summary}

    monkeypatch.setattr(runner, "invoke_acceptance", fake_invoke)

    receipt_path = runner.run_suite(args)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert [item[1] for item in calls] == [runner.CANARY_CASES, ()]
    assert calls[0][0] == calls[1][0]
    assert receipt["suite"] == "full"
    assert receipt["full"]["execution_summary"]["valid_episode_receipts"] == 28
    assert SECRET not in receipt_path.read_text(encoding="utf-8")
