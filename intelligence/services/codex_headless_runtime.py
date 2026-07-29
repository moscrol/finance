"""Codex non-interactive adapter used only as a finance quality reference."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import tomllib
from types import MappingProxyType
import urllib.error
import urllib.parse
import urllib.request

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
from intelligence.services.keychain_credentials import normalize_provider_base_url
from intelligence.services.llm_refine import LLMProvider
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
_HEADLESS_PROVIDER_ENV_KEY = "CODEX_HEADLESS_PROVIDER_KEY"
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_ENV_NAME_RE = re.compile(
    r"(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)",
    re.IGNORECASE,
)
_SEALED_CHILD_ENV_KEYS = (
    "HOME",
    "PATH",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TERM",
    "USER",
    "SHELL",
    "FINANCE_TOOL_MAILBOX",
)


@dataclass(frozen=True)
class _HeadlessProviderProjection:
    base_url: str
    wire_api: str
    bearer_token: str = field(repr=False)
    model: str | None = None
    supports_websockets: bool = False

    def __post_init__(self) -> None:
        normalized_url = normalize_provider_base_url(self.base_url)
        wire_api = str(self.wire_api or "").strip().lower()
        token = str(self.bearer_token or "").strip()
        model = str(self.model or "").strip() or None
        if wire_api not in {"responses", "chat"}:
            raise ValueError("unsupported Codex provider wire API")
        if not 8 <= len(token) <= 4096:
            raise ValueError("invalid Codex provider credential")
        if model is not None and not _MODEL_NAME_RE.fullmatch(model):
            raise ValueError("invalid Codex provider model")
        object.__setattr__(self, "base_url", normalized_url)
        object.__setattr__(self, "wire_api", wire_api)
        object.__setattr__(self, "bearer_token", token)
        object.__setattr__(self, "model", model)

    def cli_args(self) -> tuple[str, ...]:
        return (
            "-c",
            'model_provider="headless_projected"',
            "-c",
            'model_providers.headless_projected.name="Headless Projected"',
            "-c",
            f"model_providers.headless_projected.base_url={json.dumps(self.base_url)}",
            "-c",
            "model_providers.headless_projected.env_key="
            f'{json.dumps(_HEADLESS_PROVIDER_ENV_KEY)}',
            "-c",
            f"model_providers.headless_projected.wire_api={json.dumps(self.wire_api)}",
            "-c",
            "model_providers.headless_projected.requires_openai_auth=false",
            "-c",
            "model_providers.headless_projected.supports_websockets="
            f"{str(self.supports_websockets).lower()}",
        )


def _load_headless_provider_projection(
    path: Path,
    *,
    required: bool,
) -> _HeadlessProviderProjection | None:
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        if required:
            raise ValueError("Codex provider config unavailable")
        return None
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        raise ValueError("Codex provider config invalid") from None
    provider_id = str(payload.get("model_provider") or "").strip()
    providers = payload.get("model_providers")
    provider = providers.get(provider_id) if isinstance(providers, dict) else None
    if not provider_id or not isinstance(provider, dict):
        if required:
            raise ValueError("Codex provider config incomplete")
        return None
    env_key = str(provider.get("env_key") or "").strip()
    token = str(provider.get("experimental_bearer_token") or "").strip()
    if not token and env_key:
        token = str(os.environ.get(env_key) or "").strip()
    if not token:
        if required:
            raise ValueError("Codex provider credential unavailable")
        return None
    base_url = str(provider.get("base_url") or "").strip()
    wire_api = str(provider.get("wire_api") or "responses").strip()
    model = str(payload.get("model") or "").strip() or None
    supports_websockets = provider.get("supports_websockets", False)
    if not isinstance(supports_websockets, bool):
        raise ValueError("Codex provider config invalid")
    return _HeadlessProviderProjection(
        base_url=base_url,
        wire_api=wire_api,
        bearer_token=token,
        model=model,
        supports_websockets=supports_websockets,
    )


@dataclass(frozen=True)
class HeadlessCommand:
    args: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str] = field(repr=False)
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
class HeadlessEnvironment:
    """Separate Codex-provider credentials from command-child variables."""

    parent: Mapping[str, str] = field(repr=False)
    command_child_allowlist: tuple[str, ...]

    def __post_init__(self) -> None:
        parent = dict(self.parent)
        if any(
            not isinstance(key, str)
            or not _ENV_NAME_RE.fullmatch(key)
            or not isinstance(value, str)
            for key, value in parent.items()
        ):
            raise ValueError("invalid headless parent environment")
        allowlist = tuple(self.command_child_allowlist)
        if len(set(allowlist)) != len(allowlist) or any(
            not isinstance(key, str) or not _ENV_NAME_RE.fullmatch(key)
            for key in allowlist
        ):
            raise ValueError("invalid command-child environment allowlist")
        if any(_SECRET_ENV_NAME_RE.search(key) for key in allowlist):
            raise ValueError("secret-bearing variables are forbidden in command child")
        object.__setattr__(self, "parent", MappingProxyType(parent))
        object.__setattr__(self, "command_child_allowlist", allowlist)

    def child_values(self) -> dict[str, str]:
        return {
            key: self.parent[key]
            for key in self.command_child_allowlist
            if key in self.parent
        }


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
HeadlessIsolationProbe = Callable[[str, Path], "HeadlessIsolationReceipt"]


@dataclass(frozen=True)
class HeadlessIsolationReceipt:
    status: str
    public_tcp: str
    loopback: str
    unix_socket: str
    live_root_read: str
    codex_version: str
    command_sha256: str

    def __post_init__(self) -> None:
        if self.status not in {"proven", "unproven"}:
            raise ValueError("invalid isolation receipt status")
        if any(
            value not in {"denied", "unexpected_success", "unexpected_error"}
            for value in (
                self.public_tcp,
                self.loopback,
                self.unix_socket,
                self.live_root_read,
            )
        ):
            raise ValueError("invalid isolation probe result")
        if not isinstance(self.codex_version, str) or not self.codex_version.strip():
            raise ValueError("invalid isolation Codex version")
        if not re.fullmatch(r"[0-9a-f]{64}", self.command_sha256):
            raise ValueError("invalid isolation command hash")
        if self.status == "proven" and {
            self.public_tcp,
            self.loopback,
            self.unix_socket,
            self.live_root_read,
        } != {"denied"}:
            raise ValueError("proven isolation receipt must deny every probe")

    @classmethod
    def proven_for_test(cls) -> "HeadlessIsolationReceipt":
        return cls(
            status="proven",
            public_tcp="denied",
            loopback="denied",
            unix_socket="denied",
            live_root_read="denied",
            codex_version="test",
            command_sha256="0" * 64,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "public_tcp": self.public_tcp,
            "loopback": self.loopback,
            "unix_socket": self.unix_socket,
            "live_root_read": self.live_root_read,
            "codex_version": self.codex_version,
            "command_sha256": self.command_sha256,
        }


@dataclass(frozen=True)
class LocalExecCommandRunner:
    """Execute a headless command through the authenticated local exec route."""

    endpoint: str
    token: str

    def __post_init__(self) -> None:
        endpoint = str(self.endpoint or "").strip().rstrip("/")
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("local exec endpoint must use loopback HTTP")
        if not str(self.token or "").strip():
            raise ValueError("local exec token is required")
        object.__setattr__(self, "endpoint", endpoint)

    def __call__(self, command: HeadlessCommand) -> HeadlessProcessResult:
        environment = ["env"]
        environment.extend(
            f"{key}={value}" for key, value in sorted(command.env.items())
        )
        shell_command = shlex.join((*environment, *command.args))
        payload = json.dumps(
            {
                "cmd": shell_command,
                "cwd": str(command.cwd),
                "timeout": min(command.timeout, 600.0),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.endpoint}/api/exec",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=min(command.timeout + 5.0, 605.0),
            ) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return HeadlessProcessResult(
                "",
                f"local exec route HTTP {exc.code}",
                exc.code,
                False,
            )
        except (TimeoutError, urllib.error.URLError):
            return HeadlessProcessResult("", "local exec route unavailable", -1, True)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HeadlessProcessResult("", "local exec route returned invalid JSON", -1)
        if not isinstance(value, dict):
            return HeadlessProcessResult("", "local exec route returned invalid JSON", -1)
        stdout = value.get("stdout")
        stderr = value.get("stderr")
        returncode = value.get("exitCode")
        timed_out = value.get("timedOut")
        return HeadlessProcessResult(
            stdout if isinstance(stdout, str) else "",
            stderr if isinstance(stderr, str) else "",
            returncode if isinstance(returncode, int) and not isinstance(returncode, bool) else -1,
            timed_out if isinstance(timed_out, bool) else False,
        )


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
        transport: str | None = None,
        local_exec_endpoint: str | None = None,
        local_exec_token: str | None = None,
        provider_config_path: Path | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        finalization_floor_ratio: float = 0.65,
        sealed_fixture: bool = False,
        isolation_probe: HeadlessIsolationProbe | None = None,
        instruction_root: Path | None = None,
    ) -> None:
        selected_transport = str(
            transport or os.environ.get("CODEX_HEADLESS_TRANSPORT") or "subprocess"
        ).strip().lower()
        if selected_transport not in {"subprocess", "local_exec"}:
            raise ValueError("unsupported Codex headless transport")
        self._sealed_fixture = bool(sealed_fixture)
        if self._sealed_fixture and selected_transport != "subprocess":
            raise ValueError("sealed fixture requires subprocess transport")
        if instruction_root is not None and not self._sealed_fixture:
            raise ValueError("instruction_root requires sealed fixture mode")
        self._instruction_root = (
            Path(instruction_root).expanduser().resolve()
            if instruction_root is not None
            else None
        )
        if self._instruction_root is not None and not self._instruction_root.is_dir():
            raise ValueError("sealed instruction root is unavailable")
        self._gateway_transport = (
            "mailbox" if selected_transport == "subprocess" else "http"
        )
        self._sandbox_mode = "workspace-write"
        self._enable_gateway_network = selected_transport == "local_exec"
        if provider_config_path is not None and selected_transport != "subprocess":
            raise ValueError(
                "Codex provider projection requires subprocess transport"
            )
        provider_projection = None
        if provider_config_path is not None:
            provider_projection = _load_headless_provider_projection(
                provider_config_path,
                required=True,
            )
        elif command_runner is None and selected_transport == "subprocess":
            codex_home = Path(
                os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
            ).expanduser()
            provider_projection = _load_headless_provider_projection(
                codex_home / "config.toml",
                required=False,
            )
        if command_runner is not None:
            self._command_runner = command_runner
        elif selected_transport == "local_exec":
            endpoint = str(
                local_exec_endpoint
                or os.environ.get("CC_EXEC_URL")
                or f"http://127.0.0.1:{os.environ.get('CC_EXEC_PORT', '28080')}"
            )
            self._command_runner = LocalExecCommandRunner(
                endpoint=endpoint,
                token=str(local_exec_token or os.environ.get("CC_EXEC_TOKEN") or ""),
            )
        else:
            self._command_runner = _run_subprocess
        self._codex_bin = str(
            codex_bin
            or os.environ.get("CODEX_HEADLESS_BIN")
            or shutil.which("codex")
            or "codex"
        )
        cleaned_model = str(model or "").strip()
        self._provider_projection = provider_projection
        self._model = cleaned_model or (
            provider_projection.model if provider_projection is not None else None
        )
        self._reasoning_effort = str(reasoning_effort or "").strip().lower()
        self._is_cancelled = is_cancelled or (lambda: False)
        self._finalization_floor_ratio = float(finalization_floor_ratio)
        self._isolation_probe = isolation_probe or probe_sealed_isolation
        self._isolation_receipt: HeadlessIsolationReceipt | None = None
        if not 0.0 <= self._finalization_floor_ratio <= 1.0:
            raise ValueError("headless finalization floor ratio must be between 0 and 1")
        if self._reasoning_effort not in {
            "none",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError("unsupported Codex reasoning effort")

    @property
    def model_name(self) -> str:
        return self._model or "codex-account-default"

    @property
    def reasoning_effort(self) -> str:
        return self._reasoning_effort

    @property
    def finalization_floor_ratio(self) -> float:
        return self._finalization_floor_ratio

    @property
    def isolation_receipt(self) -> HeadlessIsolationReceipt | None:
        return self._isolation_receipt

    def semantic_providers(self) -> tuple[LLMProvider, ...]:
        projection = self._provider_projection
        if projection is None or not self._model:
            return ()
        return (
            LLMProvider(
                name="openai",
                api_key=projection.bearer_token,
                base_url=projection.base_url,
                model=self._model,
            ),
        )

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
            if self._instruction_root is not None:
                _materialize_instruction_tree(self._instruction_root, run_dir)
            if self._sealed_fixture:
                try:
                    self._isolation_receipt = self._isolation_probe(
                        self._codex_bin,
                        run_dir,
                    )
                except (OSError, ValueError, subprocess.SubprocessError):
                    self._isolation_receipt = None
                if (
                    self._isolation_receipt is None
                    or self._isolation_receipt.status != "proven"
                ):
                    return _failed_outcome(
                        task_frame,
                        snapshot=_empty_snapshot(),
                        stop_reason="isolation_unproven",
                        gap="isolation_unproven",
                        llm_calls=0,
                    )
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
                transport=self._gateway_transport,
                finalization_floor_ratio=self._finalization_floor_ratio,
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
                    and context.deadline.stage_timeout(
                        context.deadline.remaining()
                    )
                    >= 1.0
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
        timeout = max(
            0.1,
            context.deadline.stage_timeout(context.deadline.remaining()),
        )
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
            timeout=max(
                0.1,
                context.deadline.stage_timeout(context.deadline.remaining()),
            ),
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
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "-c",
            f'model_reasoning_effort="{self._reasoning_effort}"',
        ]
        if self._sealed_fixture:
            args.extend(
                (
                    "-c",
                    'default_permissions="sealed_fixture"',
                    "-c",
                    "permissions.sealed_fixture.filesystem="
                    '{":minimal"="read",":workspace_roots"="write",'
                    '"/opt/homebrew"="read"}',
                    "-c",
                    "permissions.sealed_fixture.workspace_roots="
                    f"{{{json.dumps(str(run_dir))}=true}}",
                    "-c",
                    "sandbox_workspace_write.network_access=false",
                    "-c",
                    "sandbox_workspace_write.exclude_tmpdir_env_var=true",
                    "-c",
                    "sandbox_workspace_write.exclude_slash_tmp=true",
                    "-c",
                    "allow_login_shell=false",
                )
            )
        else:
            args[5:5] = ("--sandbox", self._sandbox_mode)
        if self._enable_gateway_network:
            args.extend(
                (
                    "-c",
                    "sandbox_workspace_write.network_access=true",
                    "-c",
                    "sandbox_workspace_write.exclude_tmpdir_env_var=true",
                    "-c",
                    "sandbox_workspace_write.exclude_slash_tmp=true",
                )
            )
        if self._provider_projection is not None:
            args.extend(self._provider_projection.cli_args())
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
        if self._sealed_fixture and os.environ.get("OPENAI_API_KEY"):
            env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        env.update(environment)
        if self._provider_projection is not None:
            env[_HEADLESS_PROVIDER_ENV_KEY] = (
                self._provider_projection.bearer_token
            )
        headless_environment = HeadlessEnvironment(
            parent=env,
            command_child_allowlist=(
                _SEALED_CHILD_ENV_KEYS if self._sealed_fixture else ()
            ),
        )
        if self._sealed_fixture:
            args.extend(_sealed_child_environment_args(headless_environment))
        return HeadlessCommand(
            args=tuple(args),
            cwd=run_dir,
            env=headless_environment.parent,
            timeout=timeout,
        )

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
                    "isolation": (
                        self._isolation_receipt.to_dict()
                        if self._isolation_receipt is not None
                        else None
                    ),
                    "mailbox_exchanges": [
                        item.to_dict() for item in snapshot.mailbox_exchanges
                    ],
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


def _sealed_child_environment_args(
    environment: HeadlessEnvironment,
) -> tuple[str, ...]:
    allowlist = list(environment.command_child_allowlist)
    values = environment.child_values()
    args: list[str] = [
        "-c",
        "shell_environment_policy.inherit=none",
        "-c",
        "shell_environment_policy.ignore_default_excludes=false",
        "-c",
        "shell_environment_policy.include_only="
        f"{json.dumps(allowlist, ensure_ascii=True, separators=(',', ':'))}",
    ]
    for key in sorted(values):
        args.extend(
            (
                "-c",
                f"shell_environment_policy.set.{key}="
                f"{json.dumps(values[key], ensure_ascii=True)}",
            )
        )
    return tuple(args)


def sealed_environment_policy_payload() -> dict[str, object]:
    return {
        "shell_environment_policy": {
            "inherit": "none",
            "ignore_default_excludes": False,
            "include_only": list(_SEALED_CHILD_ENV_KEYS),
        },
        "allow_login_shell": False,
        "network_access": False,
        "filesystem": {
            ":minimal": "read",
            ":workspace_roots": "write",
            "/opt/homebrew": "read",
        },
    }


def _materialize_instruction_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("sealed instruction tree cannot contain symlinks")
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(mode=0o755, parents=True, exist_ok=True)
            continue
        if not path.is_file():
            raise ValueError("sealed instruction tree contains unsupported entry")
        if destination.exists():
            raise ValueError("sealed instruction tree collides with runtime files")
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        destination.chmod(0o444)


def probe_sealed_isolation(
    codex_bin: str,
    cwd: Path,
) -> HeadlessIsolationReceipt:
    """Prove OS-level denial without spending a model call."""

    binary = str(codex_bin or "").strip()
    working_directory = Path(cwd).resolve()
    if not binary or not working_directory.is_dir():
        raise ValueError("invalid isolation probe inputs")
    probe_home = working_directory / ".codex-isolation-probe"
    probe_home.mkdir(mode=0o700)
    live_root = Path(__file__).resolve().parents[2] / "AGENTS.md"
    probe_script = """import json
from pathlib import Path
import socket

results = {}

def probe(name, action):
    try:
        action()
    except PermissionError as exc:
        results[name] = "denied" if exc.errno == 1 else "unexpected_error"
    except Exception:
        results[name] = "unexpected_error"
    else:
        results[name] = "unexpected_success"

probe("public_tcp", lambda: socket.create_connection(("1.1.1.1", 443), 0.5))

def loopback_bind():
    handle = socket.socket()
    try:
        handle.bind(("127.0.0.1", 0))
    finally:
        handle.close()

probe("loopback", loopback_bind)

def unix_bind():
    handle = socket.socket(socket.AF_UNIX)
    try:
        handle.bind("/private/tmp/codex-sealed-nonallowlisted.sock")
    finally:
        handle.close()

probe("unix_socket", unix_bind)
probe("live_root_read", lambda: Path(__LIVE_ROOT__).read_bytes())
print(json.dumps(results, sort_keys=True))
""".replace("__LIVE_ROOT__", repr(str(live_root)))
    args = (
        binary,
        "sandbox",
        "-c",
        "permissions.sealed_probe.filesystem="
        '{":minimal"="read",":workspace_roots"="write",'
        '"/opt/homebrew"="read"}',
        "-c",
        "permissions.sealed_probe.workspace_roots="
        f"{{{json.dumps(str(working_directory))}=true}}",
        "-P",
        "sealed_probe",
        "-C",
        str(working_directory),
        "--sandbox-state-disable-network",
        str(shutil.which("python3") or "/opt/homebrew/bin/python3"),
        "-c",
        probe_script,
    )
    command_sha256 = hashlib.sha256(
        json.dumps(args, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    env = _safe_environment()
    env["CODEX_HOME"] = str(probe_home)
    env.pop("OPENAI_API_KEY", None)
    env.pop(_HEADLESS_PROVIDER_ENV_KEY, None)
    version = subprocess.run(
        (binary, "--version"),
        cwd=working_directory,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=10.0,
    ).stdout.strip()
    completed = subprocess.run(
        args,
        cwd=working_directory,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        payload = {}
    values = {
        name: (
            str(payload.get(name))
            if payload.get(name) in {
                "denied",
                "unexpected_success",
                "unexpected_error",
            }
            else "unexpected_error"
        )
        for name in ("public_tcp", "loopback", "unix_socket", "live_root_read")
    }
    proven = completed.returncode == 0 and set(values.values()) == {"denied"}
    return HeadlessIsolationReceipt(
        status="proven" if proven else "unproven",
        public_tcp=values["public_tcp"],
        loopback=values["loopback"],
        unix_socket=values["unix_socket"],
        live_root_read=values["live_root_read"],
        codex_version=version or "unknown",
        command_sha256=command_sha256,
    )


def _headless_prompt(
    *,
    task_frame: TaskFrame,
    context: ResearchRunContext,
    registry: ResearchToolRegistry,
    wrapper_path: Path,
) -> str:
    definitions = registry.tool_definitions(context.contract.allowed_capabilities)
    tools = ", ".join(
        str(
            (item.get("function") or {}).get("name")
            if isinstance(item, Mapping)
            else ""
        )
        for item in definitions
    )
    schema_block = json.dumps(definitions, ensure_ascii=False)
    return (
        f"{build_episode_instructions(task_frame, context, registry)}\n\n"
        "你运行在隔离目录。只能通过下列唯一命令调用金融工具：\n"
        f"{wrapper_path} TOOL 'QUERY'\n"
        f"TOOL 只能是：{tools}。每次命令必须恰好包含工具名和一个查询。"
        f"本轮工具执行硬上限 {context.policy.max_steps} 次。每个工具响应都会返回 "
        "budget.remaining_tool_calls 和 budget.must_finalize；"
        "一旦 must_finalize=true，禁止继续调用工具，必须立即使用已有证据输出终止 JSON。"
        "普通 query 工具的 QUERY 是自然语言；snapshot 工具的 QUERY 只作显示；"
        "结构化工具的 QUERY 必须是符合下列 parameters schema 的单行 JSON object，"
        "不得发送 dataset=... 这类自由文本：\n"
        f"工具 schema：{schema_block}\n"
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
    if (
        len(tokens) == 3
        and tokens[0] in {"/bin/zsh", "/bin/bash"}
        and tokens[1] == "-lc"
    ):
        try:
            tokens = shlex.split(tokens[2])
        except ValueError:
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
    "HeadlessEnvironment",
    "HeadlessIsolationProbe",
    "HeadlessIsolationReceipt",
    "HeadlessProcessResult",
    "LocalExecCommandRunner",
    "probe_sealed_isolation",
    "sealed_environment_policy_payload",
]
