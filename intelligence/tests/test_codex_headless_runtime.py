from __future__ import annotations

from dataclasses import replace
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shlex
import subprocess
from threading import Thread

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.codex_headless_runtime import (
    CodexHeadlessRuntime,
    HeadlessCommand,
    HeadlessEnvironment,
    HeadlessIsolationReceipt,
    LocalExecCommandRunner,
    HeadlessProcessResult,
    probe_sealed_isolation,
    _headless_prompt,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场的主线是什么",
        user_goal="判断当前A股市场主线及依据",
        question_type="market_watch",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_a_share_market",
        confidence=0.95,
    )


def _context(frame: TaskFrame) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="codex-headless-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("mainline_context",),
                True,
            ),
        ),
        allowed_capabilities=("mainline_context",),
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", 2, 30.0, 0.0),
        trace_parent_id="codex-headless-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry(calls: list[str]) -> ResearchToolRegistry:
    def runner(query: str, _context: AgentToolContext):
        calls.append(query)
        evidence = AgentEvidence(
            tool="mainline_context",
            title="同日主线结构",
            detail="截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            source="本地正式日报",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="mainline-hash",
        )
        return (
            [evidence],
            "医药是韧性核心，电力是轮动支线。",
            ProviderTrace(
                provider="test:mainline",
                capability="mainline_context",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="mainline_context",
                capability="mainline_context",
                description="同日主线与板块结构",
                cost="local",
                freshness="current",
                runner=runner,
                query_scope="episode",
            ),
        )
    )


def _jsonl(
    *,
    wrapper_command: str | None,
    finish: dict[str, object],
    extra_items: tuple[dict[str, object], ...] = (),
) -> str:
    command_events: list[dict[str, object]] = []
    if wrapper_command is not None:
        command_events.append(
            {
            "type": "item.completed",
            "item": {
                "id": "command-1",
                "type": "command_execution",
                "command": wrapper_command,
                "status": "completed",
                "exit_code": 0,
            },
            }
        )
    events = [
        {"type": "thread.started", "thread_id": "thread-headless-test"},
        *command_events,
        *extra_items,
        {
            "type": "item.completed",
            "item": {
                "id": "answer-1",
                "type": "agent_message",
                "text": json.dumps(finish, ensure_ascii=False),
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1200,
                "cached_input_tokens": 500,
                "output_tokens": 240,
                "reasoning_output_tokens": 80,
            },
        },
    ]
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in events)


class ValidFakeCodex:
    def __init__(
        self,
        *,
        unauthorized: bool = False,
        shell_wrapped: bool = False,
    ) -> None:
        self.commands: list[HeadlessCommand] = []
        self._unauthorized = unauthorized
        self._shell_wrapped = shell_wrapped

    def __call__(self, command: HeadlessCommand) -> HeadlessProcessResult:
        self.commands.append(command)
        wrapper = command.cwd / "finance-tool"
        tool_command = [str(wrapper), "mainline_context", "A股 当前主线"]
        completed = subprocess.run(
            tool_command,
            cwd=command.cwd,
            env=command.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        tool_result = json.loads(completed.stdout)
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": tool_result["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        extra_items: tuple[dict[str, object], ...] = ()
        if self._unauthorized:
            extra_items = (
                {
                    "type": "item.completed",
                    "item": {
                        "id": "command-2",
                        "type": "command_execution",
                        "command": "ls -la",
                        "status": "completed",
                        "exit_code": 0,
                    },
                },
            )
        wrapper_command = shlex.join(tool_command)
        if self._shell_wrapped:
            wrapper_command = shlex.join(("/bin/zsh", "-lc", wrapper_command))
        return HeadlessProcessResult(
            stdout=_jsonl(
                wrapper_command=wrapper_command,
                finish=finish,
                extra_items=extra_items,
            ),
            stderr="",
            returncode=0,
            timed_out=False,
        )


def test_headless_runtime_returns_shared_agent_outcome() -> None:
    frame = _frame()
    calls: list[str] = []
    fake = ValidFakeCodex()

    outcome = CodexHeadlessRuntime(
        command_runner=fake,
        model="gpt-5.6",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    assert outcome.task_frame_hash == frame.task_frame_hash
    assert outcome.status == "completed"
    assert outcome.draft.startswith("截至2026-07-24")
    assert outcome.bindings[0].evidence_hashes == ("mainline-hash",)
    assert outcome.evidence[0].content_hash == "mainline-hash"
    assert outcome.usage.tool_calls == 1
    assert calls == ["A股 当前主线"]
    assert tuple(event.sequence for event in outcome.events) == tuple(
        range(1, len(outcome.events) + 1)
    )


def test_headless_research_command_preserves_synthesis_reserve() -> None:
    """The child process may consume only the research slice of the deadline."""

    frame = _frame()
    base_context = _context(frame)
    context = replace(
        base_context,
        deadline=ResearchDeadline.from_timeout(30.0, synthesis_reserve=10.0),
    )
    fake = ValidFakeCodex()

    CodexHeadlessRuntime(command_runner=fake).run(
        task_frame=frame,
        context=context,
        registry=_registry([]),
    )

    assert fake.commands
    # Allow a small scheduling drift, but never give the child the full 30s.
    assert 18.0 <= fake.commands[0].timeout <= 20.1


def test_headless_runtime_builds_isolated_read_only_command(monkeypatch) -> None:
    frame = _frame()
    calls: list[str] = []
    fake = ValidFakeCodex()
    monkeypatch.setenv(
        "FORESIGHT_BUILTIN_LLM_API_KEY",
        "PRIVATE_ENV_SECRET_SENTINEL",
    )

    CodexHeadlessRuntime(command_runner=fake).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    command = fake.commands[0]
    assert "--json" in command.args
    assert "--ephemeral" in command.args
    assert "--ignore-user-config" in command.args
    assert command.args[command.args.index("--sandbox") + 1] == "workspace-write"
    assert "--output-schema" in command.args
    assert "-m" not in command.args
    assert "PRIVATE_ENV_SECRET_SENTINEL" not in str(command.env)
    assert "FINANCE_TOOL_MAILBOX" in command.env
    assert "FINANCE_TOOL_GATEWAY_URL" not in command.env
    assert "FINANCE_TOOL_GATEWAY_TOKEN" not in command.env


def test_headless_runtime_projects_only_model_provider_config(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
model = "gpt-5.6-sol"
model_provider = "local_access"

[model_providers.local_access]
name = "Local Access"
base_url = "http://localhost:57244/v1"
wire_api = "responses"
experimental_bearer_token = "HEADLESS_PROVIDER_SECRET_SENTINEL"
requires_openai_auth = false
supports_websockets = false

[mcp_servers.forbidden]
command = "must-not-enter-headless"
""".strip(),
        encoding="utf-8",
    )
    fake = ValidFakeCodex()

    runtime = CodexHeadlessRuntime(
        command_runner=fake,
        provider_config_path=config_path,
    )
    runtime.run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    command = fake.commands[0]
    serialized_args = " ".join(command.args)
    assert "--ignore-user-config" in command.args
    assert 'model_provider="headless_projected"' in command.args
    assert "http://localhost:57244/v1" in serialized_args
    assert "CODEX_HEADLESS_PROVIDER_KEY" in serialized_args
    assert "HEADLESS_PROVIDER_SECRET_SENTINEL" not in serialized_args
    assert "must-not-enter-headless" not in serialized_args
    assert command.env["CODEX_HEADLESS_PROVIDER_KEY"] == (
        "HEADLESS_PROVIDER_SECRET_SENTINEL"
    )
    assert "HEADLESS_PROVIDER_SECRET_SENTINEL" not in repr(command)
    assert command.args[command.args.index("-m") + 1] == "gpt-5.6-sol"
    providers = runtime.semantic_providers()
    assert len(providers) == 1
    assert providers[0].base_url == "http://localhost:57244/v1"
    assert providers[0].model == "gpt-5.6-sol"
    assert providers[0].api_key == "HEADLESS_PROVIDER_SECRET_SENTINEL"
    assert "HEADLESS_PROVIDER_SECRET_SENTINEL" not in repr(providers[0])


def test_sealed_runtime_keeps_provider_secret_parent_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "OPENAI_PARENT_SECRET_SENTINEL")
    monkeypatch.setenv("UNRELATED_SECRET", "UNRELATED_SECRET_SENTINEL")
    fake = ValidFakeCodex()

    CodexHeadlessRuntime(
        command_runner=fake,
        model="gpt-5.6-sol",
        reasoning_effort="medium",
        sealed_fixture=True,
        isolation_probe=lambda _binary, _cwd: HeadlessIsolationReceipt.proven_for_test(),
    ).run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    command = fake.commands[0]
    assert command.env["OPENAI_API_KEY"] == "OPENAI_PARENT_SECRET_SENTINEL"
    assert "UNRELATED_SECRET" not in command.env
    assert "OPENAI_PARENT_SECRET_SENTINEL" not in " ".join(command.args)
    assert "UNRELATED_SECRET_SENTINEL" not in " ".join(command.args)
    assert "shell_environment_policy.inherit=none" in command.args
    assert "allow_login_shell=false" in command.args
    assert "sandbox_workspace_write.network_access=false" in command.args
    assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in command.args
    assert "sandbox_workspace_write.exclude_slash_tmp=true" in command.args
    assert 'default_permissions="sealed_fixture"' in command.args
    assert any(
        item.startswith("permissions.sealed_fixture.filesystem=")
        and '":minimal"="read"' in item
        and '":workspace_roots"="write"' in item
        for item in command.args
    )
    assert "--sandbox" not in command.args
    include_only = next(
        item
        for item in command.args
        if item.startswith("shell_environment_policy.include_only=")
    )
    assert "FINANCE_TOOL_MAILBOX" in include_only
    assert "OPENAI_API_KEY" not in include_only
    assert "CODEX_HEADLESS_PROVIDER_KEY" not in include_only
    child_sets = tuple(
        item
        for item in command.args
        if item.startswith("shell_environment_policy.set.")
    )
    assert any(item.startswith("shell_environment_policy.set.PATH=") for item in child_sets)
    assert any(
        item.startswith("shell_environment_policy.set.FINANCE_TOOL_MAILBOX=")
        for item in child_sets
    )
    assert all("OPENAI_API_KEY" not in item for item in child_sets)


def test_sealed_runtime_materializes_only_sealed_instruction_tree(
    tmp_path: Path,
) -> None:
    instruction = tmp_path / "instruction"
    skill = instruction / "skills" / "finance"
    skill.mkdir(parents=True)
    (instruction / "AGENTS.md").write_text("sealed rules", encoding="utf-8")
    (skill / "SKILL.md").write_text("sealed skill", encoding="utf-8")
    observed: dict[str, object] = {}
    delegate = ValidFakeCodex()

    def runner(command: HeadlessCommand) -> HeadlessProcessResult:
        observed["agents"] = (command.cwd / "AGENTS.md").read_text(encoding="utf-8")
        observed["skill"] = (
            command.cwd / "skills" / "finance" / "SKILL.md"
        ).read_text(encoding="utf-8")
        observed["agents_mode"] = (command.cwd / "AGENTS.md").stat().st_mode & 0o777
        return delegate(command)

    outcome = CodexHeadlessRuntime(
        command_runner=runner,
        model="gpt-5.6-sol",
        sealed_fixture=True,
        instruction_root=instruction,
        isolation_probe=lambda _binary, _cwd: HeadlessIsolationReceipt.proven_for_test(),
    ).run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    assert observed == {
        "agents": "sealed rules",
        "skill": "sealed skill",
        "agents_mode": 0o444,
    }
    runtime_event = next(
        event for event in outcome.events if event.kind == "runtime_result"
    )
    assert runtime_event.payload["isolation"]["status"] == "proven"
    assert len(runtime_event.payload["mailbox_exchanges"]) == 1


def test_headless_environment_rejects_secret_child_allowlist() -> None:
    with pytest.raises(ValueError, match="secret-bearing"):
        HeadlessEnvironment(
            parent={"OPENAI_API_KEY": "secret"},
            command_child_allowlist=("PATH", "OPENAI_API_KEY"),
        )


def test_sealed_runtime_rejects_local_exec_transport() -> None:
    with pytest.raises(ValueError, match="sealed fixture requires subprocess"):
        CodexHeadlessRuntime(
            command_runner=ValidFakeCodex(),
            transport="local_exec",
            sealed_fixture=True,
        )


def test_sealed_runtime_stops_before_model_when_isolation_is_unproven() -> None:
    fake = ValidFakeCodex()
    runtime = CodexHeadlessRuntime(
        command_runner=fake,
        sealed_fixture=True,
        isolation_probe=lambda _binary, _cwd: HeadlessIsolationReceipt(
            status="unproven",
            public_tcp="unexpected_success",
            loopback="denied",
            unix_socket="denied",
            live_root_read="denied",
            codex_version="test",
            command_sha256="a" * 64,
        ),
    )

    outcome = runtime.run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    assert fake.commands == []
    assert outcome.status == "failed"
    assert outcome.stop_reason == "isolation_unproven"
    assert "isolation_unproven" in outcome.gaps
    assert runtime.isolation_receipt is not None
    assert runtime.isolation_receipt.status == "unproven"


@pytest.mark.skipif(
    not Path("/Applications/ChatGPT.app/Contents/Resources/codex").is_file(),
    reason="Codex desktop binary unavailable",
)
def test_installed_codex_sandbox_denies_network_and_unix_socket(
    tmp_path: Path,
) -> None:
    receipt = probe_sealed_isolation(
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        tmp_path,
    )

    assert receipt.status == "proven"
    assert receipt.public_tcp == "denied"
    assert receipt.loopback == "denied"
    assert receipt.unix_socket == "denied"
    assert receipt.live_root_read == "denied"
    assert not (tmp_path / ".codex-isolation-probe").exists()


def test_headless_runtime_forwards_only_an_explicit_model() -> None:
    frame = _frame()
    fake = ValidFakeCodex()

    CodexHeadlessRuntime(
        command_runner=fake,
        model="supported-codex-model",
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    command = fake.commands[0]
    assert command.args[command.args.index("-m") + 1] == "supported-codex-model"


def test_headless_runtime_rejects_non_gateway_command() -> None:
    frame = _frame()
    calls: list[str] = []

    outcome = CodexHeadlessRuntime(
        command_runner=ValidFakeCodex(unauthorized=True),
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    assert outcome.status != "completed"
    assert "unauthorized_headless_action" in outcome.gaps
    assert outcome.bindings == ()


def test_headless_runtime_accepts_codex_shell_wrapped_gateway_command() -> None:
    outcome = CodexHeadlessRuntime(
        command_runner=ValidFakeCodex(shell_wrapped=True),
    ).run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    assert outcome.status == "completed"
    assert outcome.usage.invalid_actions == 0
    assert outcome.bindings[0].evidence_hashes == ("mainline-hash",)


def test_headless_prompt_includes_structured_tool_schema() -> None:
    frame = _frame()
    base_context = _context(frame)
    context = replace(
        base_context,
        contract=replace(
            base_context.contract,
            allowed_capabilities=("finance_query",),
        ),
    )
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="语义金融查询",
                cost="local",
                freshness="current",
                runner=lambda _value, _tool_context: ([], "", ProviderTrace(
                    provider="test",
                    capability="finance_query",
                    status="empty",
                )),
                parameters={
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "string"},
                        "metrics": {"type": "array"},
                    },
                    "required": ["dataset", "metrics"],
                    "additionalProperties": False,
                },
            ),
        )
    )

    prompt = _headless_prompt(
        task_frame=frame,
        context=context,
        registry=registry,
        wrapper_path=Path("/tmp/finance-tool"),
    )

    assert "结构化工具的 QUERY 必须是符合下列 parameters schema" in prompt
    assert '"dataset"' in prompt
    assert '"metrics"' in prompt
    assert "dataset=..." in prompt
    assert "本轮工具执行硬上限 2 次" in prompt
    assert "must_finalize=true" in prompt


def test_headless_runtime_preserves_evidence_when_process_times_out() -> None:
    frame = _frame()
    calls: list[str] = []

    def timed_out(command: HeadlessCommand) -> HeadlessProcessResult:
        wrapper = command.cwd / "finance-tool"
        subprocess.run(
            [str(wrapper), "mainline_context", "A股 当前主线"],
            cwd=command.cwd,
            env=command.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return HeadlessProcessResult("", "timeout", -1, True)

    outcome = CodexHeadlessRuntime(command_runner=timed_out).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    assert outcome.status == "partial"
    assert outcome.stop_reason == "headless_timeout"
    assert outcome.evidence[0].content_hash == "mainline-hash"
    assert "PRIVATE" not in str(outcome.to_dict())


def test_headless_runtime_classifies_account_usage_limit() -> None:
    frame = _frame()

    def usage_limited(_command: HeadlessCommand) -> HeadlessProcessResult:
        return HeadlessProcessResult(
            stdout="\n".join(
                (
                    json.dumps(
                        {"type": "thread.started", "thread_id": "usage-thread"}
                    ),
                    json.dumps(
                        {
                            "type": "error",
                            "message": "You've hit your usage limit. Try again later.",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "turn.failed",
                            "error": {"message": "usage limit"},
                        }
                    ),
                )
            ),
            stderr="",
            returncode=1,
            timed_out=False,
        )

    outcome = CodexHeadlessRuntime(command_runner=usage_limited).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert outcome.status == "failed"
    assert outcome.stop_reason == "headless_usage_limit"
    assert "headless_usage_limit" in outcome.gaps


def test_headless_runtime_allows_one_finish_only_recovery() -> None:
    frame = _frame()
    calls: list[str] = []
    process_calls = 0

    def repairing_runner(command: HeadlessCommand) -> HeadlessProcessResult:
        nonlocal process_calls
        process_calls += 1
        if process_calls == 1:
            wrapper = command.cwd / "finance-tool"
            tool_command = [str(wrapper), "mainline_context", "A股 当前主线"]
            subprocess.run(
                tool_command,
                cwd=command.cwd,
                env=command.env,
                check=True,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            invalid_events = (
                {
                    "type": "thread.started",
                    "thread_id": "initial-invalid-thread",
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "command-1",
                        "type": "command_execution",
                        "command": shlex.join(tool_command),
                        "status": "completed",
                        "exit_code": 0,
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "answer-invalid",
                        "type": "agent_message",
                        "text": "not-json",
                    },
                },
                {"type": "turn.completed", "usage": {"input_tokens": 100}},
            )
            return HeadlessProcessResult(
                "\n".join(json.dumps(item) for item in invalid_events),
                "",
                0,
                False,
            )

        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["mainline-hash"],
                    "gap": "",
                }
            ],
        }
        return HeadlessProcessResult(
            _jsonl(wrapper_command=None, finish=finish),
            "",
            0,
            False,
        )

    outcome = CodexHeadlessRuntime(command_runner=repairing_runner).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "headless_finalization_recovered"
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1
    assert process_calls == 2
    runtime_event = next(
        event for event in outcome.events if event.kind == "runtime_result"
    )
    assert runtime_event.payload["input_tokens"] == 1300
    assert runtime_event.payload["output_tokens"] == 240


def test_headless_recovery_rejects_commands_without_a_third_attempt() -> None:
    frame = _frame()
    process_calls = 0

    def command_in_recovery(command: HeadlessCommand) -> HeadlessProcessResult:
        nonlocal process_calls
        process_calls += 1
        wrapper = command.cwd / "finance-tool"
        if process_calls == 1:
            tool_command = [str(wrapper), "mainline_context", "A股 当前主线"]
            subprocess.run(
                tool_command,
                cwd=command.cwd,
                env=command.env,
                check=True,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            return HeadlessProcessResult(
                _jsonl(wrapper_command=shlex.join(tool_command), finish={}),
                "",
                0,
                False,
            )

        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["mainline-hash"],
                    "gap": "",
                }
            ],
        }
        forbidden_command = shlex.join(
            [str(wrapper), "mainline_context", "A股 再检索一次"]
        )
        return HeadlessProcessResult(
            _jsonl(wrapper_command=forbidden_command, finish=finish),
            "",
            0,
            False,
        )

    outcome = CodexHeadlessRuntime(command_runner=command_in_recovery).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry([]),
    )

    assert process_calls == 2
    assert outcome.status == "partial"
    assert outcome.stop_reason == "headless_protocol_rejected"
    assert "tool_call_during_finalization_recovery" in outcome.gaps
    assert outcome.usage.llm_calls == 2
    assert outcome.usage.tool_calls == 1


@pytest.mark.skipif(
    os.environ.get("RUN_CODEX_HEADLESS_LIVE") != "1",
    reason="real Codex headless smoke is opt-in",
)
def test_real_codex_headless_smoke() -> None:
    frame = _frame()
    calls: list[str] = []

    outcome = CodexHeadlessRuntime(
        model=os.environ.get("CODEX_HEADLESS_MODEL"),
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )
    payload = {
        "runtime_backend": "codex_headless",
        "outcome": outcome.to_dict(),
    }
    Path("/tmp/codex-headless-smoke.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assert outcome.status in {"completed", "partial"}
    assert outcome.evidence
    assert outcome.stop_reason in {"model_finish", "headless_invalid_finish"}
    assert calls
    assert "FINANCE_TOOL_GATEWAY_TOKEN" not in json.dumps(payload)


def test_local_exec_runner_sends_command_and_environment_to_route() -> None:
    received: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            received.append(payload)
            body = json.dumps(
                {
                    "ok": True,
                    "exitCode": 0,
                    "stdout": "jsonl-output",
                    "stderr": "",
                    "timedOut": False,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: object) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        runner = LocalExecCommandRunner(
            endpoint=f"http://127.0.0.1:{server.server_address[1]}",
            token="route-token",
        )
        result = runner(
            HeadlessCommand(
                args=("/Applications/ChatGPT.app/Contents/Resources/codex", "exec", "prompt"),
                cwd=Path.cwd(),
                env={
                    "FINANCE_TOOL_GATEWAY_URL": "http://127.0.0.1:4321",
                    "FINANCE_TOOL_GATEWAY_TOKEN": "gateway-token",
                },
                timeout=12.5,
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result == HeadlessProcessResult("jsonl-output", "", 0, False)
    assert len(received) == 1
    request = received[0]
    assert request["cwd"] == str(Path.cwd())
    assert request["timeout"] == 12.5
    command = str(request["cmd"])
    assert "FINANCE_TOOL_GATEWAY_URL=http://127.0.0.1:4321" in command
    assert "FINANCE_TOOL_GATEWAY_TOKEN=gateway-token" in command
    assert "/Applications/ChatGPT.app/Contents/Resources/codex exec prompt" in command


def test_runtime_can_select_local_exec_transport_without_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            length = int(self.headers.get("Content-Length") or "0")
            received.append(json.loads(self.rfile.read(length).decode("utf-8")))
            stdout = json.dumps(
                {"type": "error", "message": "usage limit reached"}
            )
            body = json.dumps(
                {
                    "ok": False,
                    "exitCode": 1,
                    "stdout": stdout,
                    "stderr": "",
                    "timedOut": False,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: object) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv(
        "CODEX_HEADLESS_BIN",
        "/Applications/ChatGPT.app/Contents/Resources/codex",
    )
    try:
        outcome = CodexHeadlessRuntime(
            transport="local_exec",
            local_exec_endpoint=f"http://127.0.0.1:{server.server_address[1]}",
            local_exec_token="route-token",
        ).run(
            task_frame=_frame(),
            context=_context(_frame()),
            registry=_registry([]),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert received
    assert "/Applications/ChatGPT.app/Contents/Resources/codex" in str(
        received[0]["cmd"]
    )
    assert outcome.status == "failed"
    assert outcome.stop_reason == "headless_usage_limit"


def test_local_exec_command_enables_loopback_without_widening_tmp_roots() -> None:
    """HTTP finance tools need network, while only the ephemeral cwd may be writable."""

    fake = ValidFakeCodex()

    CodexHeadlessRuntime(
        command_runner=fake,
        transport="local_exec",
    ).run(
        task_frame=_frame(),
        context=_context(_frame()),
        registry=_registry([]),
    )

    command = fake.commands[0]
    assert command.args[command.args.index("--sandbox") + 1] == "workspace-write"
    assert "sandbox_workspace_write.network_access=true" in command.args
    assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in command.args
    assert "sandbox_workspace_write.exclude_slash_tmp=true" in command.args
    assert "--dangerously-bypass-approvals-and-sandbox" not in command.args
    assert "--add-dir" not in command.args
