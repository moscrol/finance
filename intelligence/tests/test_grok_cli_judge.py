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


def test_synthesize_messages_routes_cli_provider_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """shadow 链 grounding judge 走 synthesize_messages：cli provider 必须走 CLI。

    回归锚：修复前该路径把 cli://grok 当 HTTP URL 交给 urllib，发包前抛
    URLError → 每轮 judge_unavailable（生产 m/n 轮同形，存证误标 zhipu）。
    """
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    monkeypatch.setattr(
        "intelligence.services.grok_cli_judge.complete_grok_cli",
        lambda *_args, **_kwargs: (
            '{"passed":true,"rejected_sentence_indexes":[],"issues":[]}'
        ),
    )

    def forbid_http(*_args, **_kwargs):
        raise AssertionError("CLI judge must not post /chat/completions")

    monkeypatch.setattr(llm_refine, "_post_chat_synthesis", forbid_http)
    provider = llm_refine.judge_provider()
    assert provider is not None
    with llm_refine.provider_override(provider):
        result, reason = llm_refine.synthesize_messages(
            [{"role": "user", "content": '{"sentences":["a"]}'}],
            timeout=20,
        )
    assert reason == ""
    assert result is not None
    assert result.provider == provider.name
    assert result.finish_reason == "stop"
    assert json.loads(result.answer)["passed"] is True


def test_synthesize_messages_cli_output_too_long_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    monkeypatch.setattr(
        "intelligence.services.grok_cli_judge.complete_grok_cli",
        lambda *_args, **_kwargs: "x" * 64,
    )
    provider = llm_refine.judge_provider()
    assert provider is not None
    with llm_refine.provider_override(provider):
        result, reason = llm_refine.synthesize_messages(
            [{"role": "user", "content": "q"}],
            timeout=20,
            max_chars=8,
        )
    assert result is None
    assert reason == "LLM 合成输出超长，已降级为模板"


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


# --- CLI 失败分类（2026-08-27 四臂对照实测立案） ---------------------------
#
# 生产实测：38 题里 8 题（21%）拿到 judge_status=unavailable +
# issues=["semantic judge provider error"]，整篇答案被丢弃、用户只拿到存根。
# 追下来是一条完整的信息丢失链：
#
#   grok CLI 抽风（空输出 / 非零退出）
#     → RuntimeError("GrokCliEmpty")
#     → _failure_reason 只取 type(exc).__name__ → "RuntimeError"   ← 消息在这里丢
#     → _stable_semantic_judge_error 认不出 → retryable=False
#     → MAX_SEMANTIC_JUDGE_ATTEMPTS=3 的重试额度一次没用
#
# 重试机制本来就在，是被误判成永久故障短路掉的。


def test_failure_reason_keeps_grok_cli_marker_instead_of_bare_class() -> None:
    """CLI 的失败种类必须活着走到分类器。

    只返回 `RuntimeError` 会把「空输出」「非零退出」「JSON 坏了」三种
    完全不同的故障压成同一个不可分辨的桶，既不能重试也不能诊断。
    """

    assert llm_refine._failure_reason(RuntimeError("GrokCliEmpty")) == "grok_cli_empty"
    assert (
        llm_refine._failure_reason(RuntimeError("GrokCliInvalidJson"))
        == "grok_cli_invalid_json"
    )
    assert (
        llm_refine._failure_reason(RuntimeError("GrokCliEmptyPrompt"))
        == "grok_cli_empty_prompt"
    )


def test_failure_reason_does_not_leak_cli_stderr() -> None:
    """`GrokCliExit {rc}: {stderr}` 的 stderr 不许进原因串。

    `_failure_reason` 的契约是「可聚合且不含敏感串」；stderr 可能带路径、
    token、提示词片段。只保留稳定的种类标记。
    """

    leaky_stderr = "/Users/secret/path token=abc123 boom"  # path-literal-ok: 脱敏测试的输入必须像真家目录
    reason = llm_refine._failure_reason(RuntimeError(f"GrokCliExit 1: {leaky_stderr}"))
    assert reason == "grok_cli_exit"
    for leaked in ("secret", "token", "abc123", "boom", "/Users"):
        assert leaked not in reason


def test_grok_cli_kind_survives_complete_to_both_judge_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """故障种类必须活着穿过 `complete()` 抵达两道闸门。

    第一版只断言 `_stable_semantic_judge_error("grok_cli_empty")` 可重试就收工，
    但 `complete()` 产出的串是 `LLM 调用失败（{type(exc).__name__}）`——**消息正文
    不进那个串**。于是那段匹配从未触发，是读起来像修好了的死代码。
    所以本测试从 `complete()` 的真实返回值起判，不自己拼串。
    """

    from intelligence.services.episode_semantic_verifier import (
        _stable_semantic_judge_error,
    )

    provider = llm_refine.LLMProvider(
        "judge", "secret", grok_cli.CLI_GROK_URL, "grok-4.6", transport="cli"
    )

    def boom(*_args, **_kwargs):
        raise grok_cli.GrokCliEmptyResponse("GrokCliEmpty")

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *a, **k: [provider])
    monkeypatch.setattr(grok_cli, "complete_grok_cli", boom)

    content, _used, reason = llm_refine.complete([{"role": "user", "content": "hi"}])

    assert content is None
    # 闸门一：要不要重试
    issue, retryable, _correlated = _stable_semantic_judge_error(reason)
    assert issue == "semantic judge transient provider error", reason
    assert retryable is True, reason
    # 闸门二：带声明发稿 还是 整篇扣住
    assert llm_refine.stable_llm_fallback_reason(reason) == "empty_response", reason


def test_grok_cli_exit_is_retryable_but_still_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非零退出可重试，但**不**放进软发稿档——两道闸门各判各的。

    反向锁：防止把「CLI 抽风」一律等同于「空响应」而顺手放宽严格层。
    """

    from intelligence.services.episode_semantic_verifier import (
        _stable_semantic_judge_error,
    )

    provider = llm_refine.LLMProvider(
        "judge", "secret", grok_cli.CLI_GROK_URL, "grok-4.6", transport="cli"
    )

    def boom(*_args, **_kwargs):
        raise grok_cli.GrokCliExit("GrokCliExit 1: boom")

    monkeypatch.setattr(llm_refine, "detect_providers", lambda *a, **k: [provider])
    monkeypatch.setattr(grok_cli, "complete_grok_cli", boom)

    _content, _used, reason = llm_refine.complete([{"role": "user", "content": "hi"}])

    _issue, retryable, _c = _stable_semantic_judge_error(reason)
    assert retryable is True, reason
    assert llm_refine.stable_llm_fallback_reason(reason) == "provider_unavailable", reason


def test_empty_prompt_is_caller_bug_not_transient() -> None:
    """反向锁：提示词为空重试也还是空，不许被放宽带进瞬时档。"""

    from intelligence.services.episode_semantic_verifier import (
        _stable_semantic_judge_error,
    )

    reason = f"LLM 调用失败（{grok_cli.GrokCliEmptyPrompt.__name__}）"
    issue, retryable, _c = _stable_semantic_judge_error(reason)
    assert retryable is False
    assert issue == "semantic judge invalid provider response"


def test_failure_reason_regressions_for_non_grok_exceptions() -> None:
    """反向锁：不能为了认 grok 就改掉既有压平规则。"""

    assert llm_refine._failure_reason(TimeoutError("whatever")) == "timeout"
    assert llm_refine._failure_reason(ValueError("boom")) == "ValueError"
    assert llm_refine._failure_reason(RuntimeError("unrelated")) == "RuntimeError"
