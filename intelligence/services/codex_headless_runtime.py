"""Codex non-interactive adapter used only as a finance quality reference."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
from types import MappingProxyType

from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    public_agent_evidence,
)
from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
    expand_episode_snapshot_bindings,
    finish_json_schema,
    validate_episode_finish,
)
from intelligence.services.headless_tool_gateway import (
    HeadlessGatewaySnapshot,
    HeadlessToolGateway,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


_EXTERNAL_ACTION_ITEM_TYPES = frozenset(
    {
        "web_search",
        "web_search_call",
        "mcp_tool_call",
        "file_change",
        "computer_use",
    }
)
_SAFE_ENV_KEYS = (
    "HOME",
    "PATH",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TERM",
    "USER",
    "SHELL",
    "CODEX_HOME",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)


@dataclass(frozen=True)
class HeadlessCommand:
    args: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    timeout: float

    def __post_init__(self) -> None:
        if not self.args or any(not isinstance(item, str) or not item for item in self.args):
            raise ValueError("headless command args must be non-empty strings")
        if not isinstance(self.cwd, Path) or not self.cwd.is_dir():
            raise ValueError("headless command cwd must be an existing directory")
        if self.timeout <= 0:
            raise ValueError("headless command timeout must be positive")
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "cwd", self.cwd.resolve())
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))


@dataclass(frozen=True)
class HeadlessProcessResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise ValueError("headless process output must be text")
        if isinstance(self.returncode, bool) or not isinstance(self.returncode, int):
            raise ValueError("headless returncode must be an integer")
        if not isinstance(self.timed_out, bool):
            raise ValueError("headless timed_out must be a boolean")


HeadlessCommandRunner = Callable[[HeadlessCommand], HeadlessProcessResult]


@dataclass(frozen=True)
class _ParsedJSONL:
    final_text: str
    thread_id: str
    input_tokens: int | None
    output_tokens: int | None
    completed_turns: int
    issues: tuple[str, ...]


class CodexHeadlessRuntime:
    """Run one immutable finance task through `codex exec`."""

    def __init__(
        self,
        *,
        command_runner: HeadlessCommandRunner | None = None,
        codex_bin: str | None = None,
        model: str | None = None,
        reasoning_effort: str = "high",
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._command_runner = command_runner or _run_subprocess
        self._codex_bin = str(codex_bin or shutil.which("codex") or "codex")
        cleaned_model = str(model or "").strip()
        self._model = cleaned_model or None
        self._reasoning_effort = str(reasoning_effort or "").strip().lower()
        self._is_cancelled = is_cancelled or (lambda: False)
        if self._reasoning_effort not in {
            "none",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError("unsupported Codex reasoning effort")

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome:
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")
        if self._is_cancelled():
            return _failed_outcome(
                task_frame,
                snapshot=_empty_snapshot(),
                stop_reason="cancelled",
                gap="本轮执行已取消",
                llm_calls=0,
            )

        with tempfile.TemporaryDirectory(prefix="finance-codex-headless-") as raw_dir:
            run_dir = Path(raw_dir)
            schema_path = run_dir / "episode-finish.schema.json"
            schema_path.write_text(
                json.dumps(finish_json_schema(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with HeadlessToolGateway(
                registry=registry,
                context=context,
                is_cancelled=self._is_cancelled,
                run_dir=run_dir,
            ) as gateway:
                command = self._build_command(
                    task_frame=task_frame,
                    context=context,
                    registry=registry,
                    gateway=gateway,
                    schema_path=schema_path,
                    run_dir=run_dir,
                )
                process = self._command_runner(command)
                snapshot = gateway.snapshot()
                parsed = _parse_jsonl(
                    process.stdout,
                    authorized_wrapper=gateway.wrapper_path,
                )
                recovered = False
                llm_calls = 1
                finish_issue = _finish_issue(
                    process=process,
                    parsed=parsed,
                    context=context,
                    snapshot=snapshot,
                )
                if (
                    finish_issue in {"headless_invalid_finish", "headless_no_finish"}
                    and snapshot.evidence
                    and context.deadline.remaining() >= 1.0
                ):
                    repair_command = self._build_repair_command(
                        task_frame=task_frame,
                        context=context,
                        snapshot=snapshot,
                        gateway=gateway,
                        schema_path=schema_path,
                        run_dir=run_dir,
                        failure_reason=finish_issue,
                    )
                    llm_calls += 1
                    repair_process = self._command_runner(repair_command)
                    repair_parsed = _parse_jsonl(
                        repair_process.stdout,
                        authorized_wrapper=gateway.wrapper_path,
                        allow_gateway_commands=False,
                    )
                    repair_snapshot = gateway.snapshot()
                    repair_issue = _finish_issue(
                        process=repair_process,
                        parsed=repair_parsed,
                        context=context,
                        snapshot=repair_snapshot,
                    )
                    parsed = _merge_parsed_usage(parsed, repair_parsed)
                    process = repair_process
                    snapshot = repair_snapshot
                    if repair_issue is None:
                        recovered = True
                    else:
                        parsed = _parsed_with_issue(parsed, repair_issue)
                elif finish_issue is not None:
                    parsed = _parsed_with_issue(parsed, finish_issue)

        return self._to_outcome(
            task_frame=task_frame,
            context=context,
            registry=registry,
            process=process,
            parsed=parsed,
            snapshot=snapshot,
            recovered=recovered,
            llm_calls=llm_calls,
        )

    def _build_command(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        gateway: HeadlessToolGateway,
        schema_path: Path,
        run_dir: Path,
    ) -> HeadlessCommand:
        timeout = max(0.1, context.deadline.remaining())
        prompt = _headless_prompt(
            task_frame=task_frame,
            context=context,
            registry=registry,
            wrapper_path=gateway.wrapper_path,
        )
        return self._command_from_prompt(
            prompt=prompt,
            schema_path=schema_path,
            run_dir=run_dir,
            environment=gateway.subprocess_environment(),
            timeout=timeout,
        )

    def _build_repair_command(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        snapshot: HeadlessGatewaySnapshot,
        gateway: HeadlessToolGateway,
        schema_path: Path,
        run_dir: Path,
        failure_reason: str,
    ) -> HeadlessCommand:
        evidence = [public_agent_evidence(item) for item in snapshot.evidence]
        prompt = (
            "研究阶段已经关闭，禁止调用任何工具或运行命令。"
            "上一份终止输出未通过固定 JSON 协议；只修复终止 envelope，"
            "不得增加新事实。只能使用下面列出的证据哈希，缺失输出必须写 gap。"
            "只输出符合给定 schema 的 JSON 对象。\n"
            f"失败原因：{failure_reason}\n"
            f"任务：{build_episode_input(task_frame, context)}\n"
            f"证据：{json.dumps(evidence, ensure_ascii=False)}\n"
            f"现有缺口：{json.dumps(list(snapshot.gaps), ensure_ascii=False)}"
        )
        return self._command_from_prompt(
            prompt=prompt,
            schema_path=schema_path,
            run_dir=run_dir,
            environment=gateway.subprocess_environment(),
            timeout=max(0.1, context.deadline.remaining()),
        )

    def _command_from_prompt(
        self,
        *,
        prompt: str,
        schema_path: Path,
        run_dir: Path,
        environment: Mapping[str, str],
        timeout: float,
    ) -> HeadlessCommand:
        args = [
            self._codex_bin,
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "-c",
            f'model_reasoning_effort="{self._reasoning_effort}"',
        ]
        if self._model is not None:
            args.extend(("-m", self._model))
        args.extend(
            (
                "-C",
                str(run_dir),
                prompt,
            )
        )
        env = _safe_environment()
        env.update(environment)
        return HeadlessCommand(args=tuple(args), cwd=run_dir, env=env, timeout=timeout)

    def _to_outcome(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        process: HeadlessProcessResult,
        parsed: _ParsedJSONL,
        snapshot: HeadlessGatewaySnapshot,
        recovered: bool,
        llm_calls: int,
    ) -> AgentOutcome:
        issues = list(parsed.issues)
        if process.timed_out:
            issues.append("headless_timeout")
        elif process.returncode != 0:
            issues.append("headless_process_failed")
        if self._is_cancelled():
            issues.append("cancelled")

        finish = None
        if not issues and parsed.final_text:
            try:
                finish = validate_episode_finish(
                    parsed.final_text,
                    context=context,
                    evidence=snapshot.evidence,
                )
            except ValueError:
                issues.append("headless_invalid_finish")
        elif not parsed.final_text and not issues:
            issues.append("headless_no_finish")

        unique_issues = tuple(dict.fromkeys(issues))
        events = [
            EpisodeEvent(
                1,
                "task",
                {
                    "question": task_frame.raw_question,
                    "task_frame": task_frame.to_dict(),
                    "task_frame_hash": task_frame.task_frame_hash,
                },
            ),
            *snapshot.events,
        ]
        events.append(
            EpisodeEvent(
                len(events) + 1,
                "runtime_result",
                {
                    "runtime": "codex_headless",
                    "model": self._model or "codex-account-default",
                    "reasoning_effort": self._reasoning_effort,
                    "thread_id": parsed.thread_id,
                    "input_tokens": parsed.input_tokens,
                    "output_tokens": parsed.output_tokens,
                    "issues": list(unique_issues),
                },
            )
        )

        gaps = list(snapshot.gaps)
        for issue in unique_issues:
            if issue not in gaps:
                gaps.append(issue)
        if finish is not None:
            for gap in finish.gaps:
                if gap not in gaps:
                    gaps.append(gap)
            bindings = expand_episode_snapshot_bindings(
                bindings=finish.bindings,
                evidence=snapshot.evidence,
                registry=registry,
            )
            status = finish.status
            draft = finish.draft
            stop_reason = (
                "headless_finalization_recovered" if recovered else "model_finish"
            )
        else:
            bindings = ()
            status = "partial" if snapshot.evidence else "failed"
            draft = ""
            stop_reason = _stop_reason(unique_issues)

        events.append(
            EpisodeEvent(
                len(events) + 1,
                "finish",
                {
                    "status": status,
                    "stop_reason": stop_reason,
                    "gaps": gaps,
                },
            )
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=draft,
            evidence=snapshot.evidence,
            traces=snapshot.traces,
            gaps=tuple(gaps),
            stop_reason=stop_reason,
            events=tuple(events),
            bindings=bindings,
            usage=AgentUsage(
                llm_calls=llm_calls,
                tool_calls=snapshot.executed_count,
                invalid_actions=len(unique_issues),
            ),
        )


def _safe_environment() -> dict[str, str]:
    env = {key: os.environ[key] for key in _SAFE_ENV_KEYS if os.environ.get(key)}
    existing_no_proxy = os.environ.get("NO_PROXY", "")
    entries = [item.strip() for item in existing_no_proxy.split(",") if item.strip()]
    for loopback in ("127.0.0.1", "localhost"):
        if loopback not in entries:
            entries.append(loopback)
    env["NO_PROXY"] = ",".join(entries)
    return env


def _headless_prompt(
    *,
    task_frame: TaskFrame,
    context: ResearchRunContext,
    registry: ResearchToolRegistry,
    wrapper_path: Path,
) -> str:
    tools = ", ".join(
        spec.name
        for spec in registry.authorized_specs(
            context.contract.allowed_capabilities
        )
    )
    return (
        f"{build_episode_instructions(task_frame, context, registry)}\n\n"
        "你运行在隔离目录。只能通过下列唯一命令调用金融工具：\n"
        f"{wrapper_path} TOOL 'QUERY'\n"
        f"TOOL 只能是：{tools}。每次命令必须恰好包含工具名和一个查询。"
        "禁止运行其他 shell 命令，禁止读取文件，禁止使用内置 Web、MCP、"
        "文件编辑或计算机控制。工具返回的 evidence_hashes 才能进入 bindings。"
        "完成后只输出符合给定 schema 的 JSON 对象，不输出前言或代码围栏。\n\n"
        f"{build_episode_input(task_frame, context)}"
    )


def _parse_jsonl(
    text: str,
    *,
    authorized_wrapper: Path,
    allow_gateway_commands: bool = True,
) -> _ParsedJSONL:
    final_text = ""
    thread_id = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    completed_turns = 0
    issues: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            issues.append("malformed_headless_jsonl")
            continue
        if not isinstance(event, dict):
            issues.append("malformed_headless_event")
            continue
        event_type = str(event.get("type") or "")
        if event_type == "thread.started":
            thread_id = str(event.get("thread_id") or "")
            continue
        if event_type == "turn.completed":
            completed_turns += 1
            usage = event.get("usage")
            if isinstance(usage, dict):
                input_tokens = _optional_non_negative_int(usage.get("input_tokens"))
                output_tokens = _optional_non_negative_int(usage.get("output_tokens"))
            continue
        if event_type in {"turn.failed", "error"}:
            issues.append(_headless_error_kind(event))
            continue
        if event_type != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            issues.append("malformed_headless_item")
            continue
        item_type = str(item.get("type") or "")
        if item_type == "agent_message":
            text_value = item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                final_text = text_value.strip()
            continue
        if item_type == "command_execution":
            if not allow_gateway_commands:
                issues.append("tool_call_during_finalization_recovery")
            elif not _authorized_command(item.get("command"), authorized_wrapper):
                issues.append("unauthorized_headless_action")
            exit_code = item.get("exit_code")
            if isinstance(exit_code, int) and not isinstance(exit_code, bool):
                if exit_code != 0:
                    issues.append("headless_command_failed")
            continue
        if item_type in _EXTERNAL_ACTION_ITEM_TYPES:
            issues.append("unauthorized_headless_action")
    return _ParsedJSONL(
        final_text=final_text,
        thread_id=thread_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        completed_turns=completed_turns,
        issues=tuple(dict.fromkeys(issues)),
    )


def _finish_issue(
    *,
    process: HeadlessProcessResult,
    parsed: _ParsedJSONL,
    context: ResearchRunContext,
    snapshot: HeadlessGatewaySnapshot,
) -> str | None:
    if process.timed_out:
        return "headless_timeout"
    if parsed.issues:
        return parsed.issues[0]
    if process.returncode != 0:
        return "headless_process_failed"
    if not parsed.final_text:
        return "headless_no_finish"
    try:
        validate_episode_finish(
            parsed.final_text,
            context=context,
            evidence=snapshot.evidence,
        )
    except ValueError:
        return "headless_invalid_finish"
    return None


def _merge_parsed_usage(
    initial: _ParsedJSONL,
    recovery: _ParsedJSONL,
) -> _ParsedJSONL:
    return _ParsedJSONL(
        final_text=recovery.final_text or initial.final_text,
        thread_id=recovery.thread_id or initial.thread_id,
        input_tokens=_sum_optional_counts(
            initial.input_tokens,
            recovery.input_tokens,
        ),
        output_tokens=_sum_optional_counts(
            initial.output_tokens,
            recovery.output_tokens,
        ),
        completed_turns=initial.completed_turns + recovery.completed_turns,
        issues=tuple(dict.fromkeys((*initial.issues, *recovery.issues))),
    )


def _parsed_with_issue(parsed: _ParsedJSONL, issue: str) -> _ParsedJSONL:
    return _ParsedJSONL(
        final_text=parsed.final_text,
        thread_id=parsed.thread_id,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        completed_turns=parsed.completed_turns,
        issues=tuple(dict.fromkeys((*parsed.issues, issue))),
    )


def _sum_optional_counts(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)


def _authorized_command(value: object, wrapper: Path) -> bool:
    if isinstance(value, str):
        try:
            tokens = shlex.split(value)
        except ValueError:
            return False
    elif isinstance(value, (list, tuple)) and all(
        isinstance(item, str) for item in value
    ):
        tokens = list(value)
    else:
        return False
    return len(tokens) == 3 and Path(tokens[0]).resolve() == wrapper.resolve()


def _optional_non_negative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _headless_error_kind(event: Mapping[str, object]) -> str:
    message = event.get("message")
    if not isinstance(message, str):
        nested = event.get("error")
        message = nested.get("message") if isinstance(nested, Mapping) else ""
    normalized = str(message or "").casefold()
    if "usage limit" in normalized:
        return "headless_usage_limit"
    if "model" in normalized and "not supported" in normalized:
        return "headless_model_unsupported"
    return "headless_turn_failed"


def _stop_reason(issues: tuple[str, ...]) -> str:
    for reason in (
        "cancelled",
        "headless_timeout",
        "headless_usage_limit",
        "headless_model_unsupported",
        "unauthorized_headless_action",
        "headless_process_failed",
        "headless_invalid_finish",
        "headless_no_finish",
    ):
        if reason in issues:
            return reason if reason != "unauthorized_headless_action" else "headless_protocol_rejected"
    return "headless_protocol_rejected"


def _empty_snapshot() -> HeadlessGatewaySnapshot:
    return HeadlessGatewaySnapshot((), (), (), (), 0, 0)


def _failed_outcome(
    task_frame: TaskFrame,
    *,
    snapshot: HeadlessGatewaySnapshot,
    stop_reason: str,
    gap: str,
    llm_calls: int,
) -> AgentOutcome:
    return AgentOutcome(
        task_frame_hash=task_frame.task_frame_hash,
        status="partial" if snapshot.evidence else "failed",
        draft="",
        evidence=snapshot.evidence,
        traces=snapshot.traces,
        gaps=tuple(dict.fromkeys((*snapshot.gaps, gap))),
        stop_reason=stop_reason,
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": task_frame.task_frame_hash},
            ),
        ),
        bindings=(),
        usage=AgentUsage(llm_calls=llm_calls, tool_calls=snapshot.executed_count),
    )


def _run_subprocess(command: HeadlessCommand) -> HeadlessProcessResult:
    started = time.monotonic()
    process = subprocess.Popen(
        command.args,
        cwd=command.cwd,
        env=dict(command.env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=command.timeout)
        return HeadlessProcessResult(stdout, stderr, process.returncode, False)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        elapsed = max(0.0, time.monotonic() - started)
        return HeadlessProcessResult(
            stdout,
            f"headless timeout after {elapsed:.3f}s",
            process.returncode if process.returncode is not None else -1,
            True,
        )


__all__ = [
    "CodexHeadlessRuntime",
    "HeadlessCommand",
    "HeadlessCommandRunner",
    "HeadlessProcessResult",
]
