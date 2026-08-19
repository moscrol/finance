"""Grok CLI independent judge: opt-in, isolated cwd, no live network in tests."""

from __future__ import annotations

import json
from subprocess import CompletedProcess

import pytest

from intelligence.services import grok_cli_judge as grok_cli
from intelligence.services import llm_refine


def test_path_presence_does_not_enable_grok_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_JUDGE_BACKEND", raising=False)
    monkeypatch.delenv("LLM_JUDGE", raising=False)
    monkeypatch.delenv("LLM_JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_JUDGE_MODEL", raising=False)
    monkeypatch.setattr(grok_cli.shutil, "which", lambda _name: "/tmp/fake-grok")
    assert llm_refine.judge_provider() is None


def test_explicit_backend_returns_cli_provider_even_if_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    monkeypatch.delenv("LLM_JUDGE_API_KEY", raising=False)
    monkeypatch.setattr(grok_cli.shutil, "which", lambda _name: None)
    provider = llm_refine.judge_provider()
    assert provider is not None
    assert provider.name == "grok-cli-judge"
    assert provider.transport == "cli"
    assert grok_cli.is_cli_judge_provider(provider)
    assert grok_cli.resolve_grok_binary() is None


def test_explicit_grok_backend_wins_over_http_judge_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok")
    monkeypatch.setenv("LLM_JUDGE_API_KEY", "sk-test")
    provider = llm_refine.judge_provider()
    assert provider is not None
    assert provider.transport == "cli"


def test_argv_isolates_empty_cwd_and_forbids_tools() -> None:
    argv = grok_cli.build_grok_judge_argv(
        binary="/tmp/fake-grok",
        cwd="/tmp/grok-judge-empty",
        prompt_file="/tmp/grok-judge-empty/request.txt",
        model="grok-4.6",
        system_prompt="judge-system",
    )
    assert argv[0] == "/tmp/fake-grok"
    assert "--cwd" in argv
    cwd = argv[argv.index("--cwd") + 1]
    assert cwd == "/tmp/grok-judge-empty"
    assert "finance-workspace" not in cwd
    assert "--system-prompt-override" in argv
    assert "--disable-web-search" in argv
    assert "--no-subagents" in argv
    assert "--max-turns" in argv
    deny = argv[argv.index("--disallowed-tools") + 1]
    assert "run_terminal_cmd" in deny
    assert "Agent" in deny
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["required"] == [
        "passed",
        "rejected_sentence_indexes",
        "issues",
    ]


def test_complete_grok_cli_reads_json_text_and_does_not_hit_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_JUDGE_GROK_BIN", "/tmp/fake-grok")
    captured: dict[str, object] = {}

    def runner(argv, **kwargs):
        captured["argv"] = argv
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        payload = {
            "text": '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}',
            "stopReason": "end_turn",
        }
        return CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")

    content = grok_cli.complete_grok_cli(
        llm_refine.LLMProvider(
            "grok-cli-judge",
            "",
            grok_cli.CLI_GROK_URL,
            "grok-4.6",
            transport="cli",
        ),
        [
            {"role": "system", "content": "only JSON"},
            {"role": "user", "content": '{"sentences":[]}'},
        ],
        timeout=8,
        runner=runner,
    )
    report = json.loads(content)
    assert report["passed"] is True
    argv = captured["argv"]
    assert isinstance(argv, list)
    assert "--cwd" in argv
    prompt_file = argv[argv.index("--prompt-file") + 1]
    assert prompt_file.endswith("request.txt")
    assert not prompt_file.endswith(".json")
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["GROK_CLAUDE_SKILLS_ENABLED"] == "false"
    assert env["GROK_MEMORY"] == "0"


def test_complete_routes_cli_provider_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    monkeypatch.setattr(
        "intelligence.services.grok_cli_judge.complete_grok_cli",
        lambda *_args, **_kwargs: (
            '{"passed":false,"rejected_sentence_indexes":[1],"issues":["x"]}'
        ),
    )

    def forbid_http(*_args, **_kwargs):
        raise AssertionError("CLI judge must not post /chat/completions")

    monkeypatch.setattr(llm_refine, "_post_chat", forbid_http)
    provider = llm_refine.judge_provider()
    assert provider is not None
    with llm_refine.provider_override(provider):
        content, used, reason = llm_refine.complete(
            [{"role": "user", "content": '{"sentences":["a"]}'}],
            timeout=20,
        )
    assert reason == ""
    assert used is provider
    assert json.loads(content or "{}")["passed"] is False


def test_missing_binary_is_unavailable_not_correlated_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    monkeypatch.delenv("LLM_JUDGE_GROK_BIN", raising=False)
    monkeypatch.setattr(grok_cli.shutil, "which", lambda _name: None)
    provider = llm_refine.judge_provider()
    assert provider is not None
    with llm_refine.provider_override(provider):
        content, used, reason = llm_refine.complete(
            [{"role": "user", "content": '{"sentences":[]}'}],
            timeout=20,
        )
    assert content is None
    assert used is provider
    assert "FileNotFoundError" in reason or "GrokCli" in reason
