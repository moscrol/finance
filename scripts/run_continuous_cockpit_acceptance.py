#!/usr/bin/env python3
"""Run a gated Continuous Harness acceptance suite against local Cockpit.

The runner owns one short-lived child Workbench process.  It deliberately does
not import ``intelligence.api.app`` in the parent process: importing the module
would construct the global FastAPI app before the isolated environment is in
place and could make the test observe the wrong repository or provider.

Only the child receives the Cockpit key.  The key is never printed, put in a
command argument, or written to a receipt.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Iterator, Mapping, Sequence
import urllib.error
import urllib.request


DEFAULT_COCKPIT_CONFIG = (
    Path.home() / ".antigravity_cockpit/codex_local_access_sidecar/config.json"
)
DEFAULT_COCKPIT_BASE_URL = "http://127.0.0.1:57244/v1"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_PORT = 8801
DEFAULT_USER = "linxiaoqi5111"
DEFAULT_TIMEOUT = 300.0

# The child must not inherit a second provider family.  Values are removed by
# name only; the runner never reads or logs their values.
PROVIDER_SECRET_ENV = frozenset(
    {
        "LLM_API_KEY",
        "FORESIGHT_BUILTIN_LLM_API_KEY",
        "ZHIPU_API_KEY",
        "GLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
    }
)

CANARY_CASES = (
    "A4-dual-red",
    "B6-sellside-distillation",
    "C8-nonexistent-table",
    "C10-multi-turn-consistency",
)


class RunnerError(RuntimeError):
    """A safety gate or an acceptance prerequisite failed."""


@dataclass(frozen=True)
class RunnerIdentity:
    revision: str
    code_root: str
    mode: str = "on"
    backend: str = "sdk_gpt"
    model: str = DEFAULT_MODEL
    provider_label: str = "cockpit_local"
    provider_protocol: str = "openai_responses"

    def as_expected_args(self) -> tuple[str, ...]:
        return (
            "--expected-revision",
            self.revision,
            "--expected-code-root",
            self.code_root,
            "--expected-mode",
            self.mode,
            "--expected-backend",
            self.backend,
            "--expected-model",
            self.model,
            "--expected-provider-label",
            self.provider_label,
            "--expected-provider-protocol",
            self.provider_protocol,
        )


@dataclass(frozen=True)
class ServerContext:
    process: subprocess.Popen[Any]
    base_url: str
    identity: RunnerIdentity
    health: Mapping[str, Any]
    env: Mapping[str, str]


def load_cockpit_api_key(path: Path = DEFAULT_COCKPIT_CONFIG) -> str:
    """Read only the first sidecar key, failing closed without echoing it."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"Cockpit 配置不可读：{type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise RunnerError("Cockpit 配置格式无效：根节点必须是对象")
    keys = payload.get("api-keys")
    if not isinstance(keys, list) or not keys:
        raise RunnerError("Cockpit 配置缺少 api-keys")
    key = keys[0]
    if not isinstance(key, str) or not key.strip():
        raise RunnerError("Cockpit 配置的第一把 api key 无效")
    return key.strip()


def _capture(command: Sequence[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RunnerError(f"命令不可执行：{command[0]}") from exc
    if result.returncode != 0:
        raise RunnerError(f"命令失败：{command[0]}（exit={result.returncode}）")
    return result.stdout.strip()


def clean_revision(code_root: Path) -> str:
    """Require a clean checkout and return its exact 40-character revision."""

    root = code_root.expanduser().resolve()
    if not root.is_dir():
        raise RunnerError("code root 不存在或不是目录")
    status = _capture(
        ("git", "status", "--porcelain", "--untracked-files=all"), cwd=root
    )
    if status:
        raise RunnerError("code checkout dirty；先提交或另建干净 worktree")
    revision = _capture(("git", "rev-parse", "HEAD"), cwd=root)
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise RunnerError("无法取得完整 git revision")
    return revision


def ensure_port_available(port: int, *, host: str = "127.0.0.1") -> None:
    if port == 8792:
        raise RunnerError("拒绝使用生产端口 8792")
    if not 1024 <= int(port) <= 65535:
        raise RunnerError("隔离端口必须在 1024-65535 之间")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port)))
    except OSError as exc:
        raise RunnerError(f"端口 {port} 已被占用或不可用") from exc
    finally:
        sock.close()


def python_executable_path(value: str) -> str:
    """Return an absolute executable path without resolving venv symlinks.

    ``Path.resolve()`` follows ``.venv/bin/python`` to the base interpreter.
    Executing that target directly drops the virtualenv's prefix and installed
    dependencies, so the Workbench child can fail before health is available.
    """

    expanded = Path(value).expanduser()
    if expanded.is_absolute():
        candidate = expanded
    else:
        discovered = shutil.which(str(expanded))
        if not discovered:
            raise RunnerError("Python executable 不存在")
        candidate = Path(discovered)
    absolute = Path(os.path.abspath(candidate))
    if not absolute.is_file() or not os.access(absolute, os.X_OK):
        raise RunnerError("Python executable 不可执行")
    return str(absolute)


def build_child_env(
    *,
    api_key: str,
    code_root: Path,
    data_root: Path,
    users_root: Path,
    base_url: str = DEFAULT_COCKPIT_BASE_URL,
    model: str = DEFAULT_MODEL,
    user: str = DEFAULT_USER,
    inherited: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a provider-isolated environment without exposing secret values."""

    if not api_key.strip():
        raise RunnerError("Cockpit api key 为空")
    env = dict(inherited or os.environ)
    for name in PROVIDER_SECRET_ENV:
        env.pop(name, None)
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "OPENAI_API_KEY": api_key,
            "OPENAI_BASE_URL": base_url.rstrip("/"),
            "LLM_BASE_URL": base_url.rstrip("/"),
            "LLM_MODEL": model,
            "OPENAI_AGENT_MODEL": model,
            "AGENT_RUNTIME_PROVIDER_LABEL": "cockpit_local",
            "AGENT_RUNTIME_BACKEND": "sdk_gpt",
            "ASK_CONTINUOUS_RUNTIME": "on",
            "WORKBENCH_REPO_ROOT": str(code_root.expanduser().resolve()),
            "FINANCE_WS": str(data_root.expanduser().resolve()),
            "FORESIGHT_USERS_DIR": str(users_root.expanduser().resolve()),
            "FORESIGHT_USER": user,
            # Force imports to resolve from this worktree, not an editable
            # install or a parent checkout left in the caller's environment.
            "PYTHONPATH": str(code_root.expanduser().resolve()),
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
    )
    return env


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    api_key: str | None = None,
    timeout: float = 15.0,
) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        status = getattr(exc, "code", None)
        suffix = f" status={status}" if status is not None else ""
        raise RunnerError(f"HTTP 请求失败{suffix}：{method} {url}") from exc
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"HTTP 返回不是 JSON：{method} {url}") from exc


def _text_from_response(payload: Mapping[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct

    parts: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("type") in {"output_text", "text"}:
                text = value.get("text")
                if isinstance(text, str):
                    parts.append(text)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload.get("output"))
    return "".join(parts)


def cockpit_protocol_smoke(
    *,
    api_key: str,
    base_url: str = DEFAULT_COCKPIT_BASE_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Verify the local OpenAI-compatible endpoint with a bounded request."""

    models_payload = _request_json(
        f"{base_url.rstrip('/')}/models",
        api_key=api_key,
        timeout=timeout,
    )
    models = models_payload.get("data") if isinstance(models_payload, Mapping) else None
    model_ids = {
        str(item.get("id"))
        for item in (models or [])
        if isinstance(item, Mapping) and item.get("id")
    }
    if model not in model_ids:
        raise RunnerError(f"Cockpit /models 未提供 {model}")
    response = _request_json(
        f"{base_url.rstrip('/')}/responses",
        method="POST",
        payload={
            "model": model,
            "input": "Reply exactly OK.",
            "max_output_tokens": 16,
            "store": False,
        },
        api_key=api_key,
        timeout=timeout,
    )
    if not isinstance(response, Mapping):
        raise RunnerError("Cockpit /responses 返回格式无效")
    response_status = str(response.get("status") or "")
    output_ok = _text_from_response(response).strip() == "OK"
    if response_status != "completed" or not output_ok:
        raise RunnerError("Cockpit /responses 冒烟未返回 completed/OK")
    return {
        "models_ok": True,
        "model": model,
        "response_status": response_status,
        "output_ok": output_ok,
    }


def _health_projection(health: Mapping[str, Any]) -> dict[str, Any]:
    runtime = health.get("runtime")
    if not isinstance(runtime, Mapping):
        return {}
    agent = runtime.get("agent_runtime")
    if not isinstance(agent, Mapping):
        agent = {}
    return {
        "status": health.get("status"),
        "runtime_instance_id": runtime.get("runtime_instance_id"),
        "source_revision": runtime.get("source_revision"),
        "source_dirty": runtime.get("source_dirty"),
        "code_root": runtime.get("code_root"),
        "import_root": runtime.get("import_root"),
        "continuous_mode": (runtime.get("continuous_agent") or {}).get("mode")
        if isinstance(runtime.get("continuous_agent"), Mapping)
        else None,
        "backend": agent.get("backend"),
        "model": agent.get("model"),
        "provider_label": agent.get("provider_label"),
        "provider_protocol": agent.get("provider_protocol"),
        "provider_chain_size": agent.get("provider_chain_size"),
        "ready": agent.get("ready"),
    }


def validate_health(
    health: Mapping[str, Any],
    identity: RunnerIdentity,
) -> tuple[bool, tuple[str, ...]]:
    observed = _health_projection(health)
    failures: list[str] = []
    if observed.get("status") != "healthy":
        failures.append("health.status")
    if observed.get("source_revision") != identity.revision:
        failures.append("health.source_revision")
    if observed.get("source_dirty") is not False:
        failures.append("health.source_dirty")
    if observed.get("code_root") != identity.code_root:
        failures.append("health.code_root")
    if observed.get("import_root") != identity.code_root:
        failures.append("health.import_root")
    if observed.get("continuous_mode") != identity.mode:
        failures.append("health.continuous_mode")
    for field in (
        "backend",
        "model",
        "provider_label",
        "provider_protocol",
    ):
        if observed.get(field) != getattr(identity, field):
            failures.append(f"health.{field}")
    if observed.get("provider_chain_size") != 1:
        failures.append("health.provider_chain_size")
    if observed.get("ready") is not True:
        failures.append("health.agent_runtime.ready")
    if not str(observed.get("runtime_instance_id") or "").strip():
        failures.append("health.runtime_instance_id")
    return not failures, tuple(failures)


def wait_for_health(
    *,
    base_url: str,
    identity: RunnerIdentity,
    timeout: float = 90.0,
    poll_seconds: float = 1.0,
) -> Mapping[str, Any]:
    deadline = time.monotonic() + timeout
    last_failures: tuple[str, ...] = ("health.unavailable",)
    while time.monotonic() < deadline:
        try:
            health = _request_json(f"{base_url}/api/health", timeout=5.0)
            if isinstance(health, Mapping):
                ok, failures = validate_health(health, identity)
                if ok:
                    return health
                last_failures = failures
        except RunnerError:
            pass
        time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
    raise RunnerError("Workbench health 未达到预期身份：" + ",".join(last_failures))


def _terminate_child(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass


@contextmanager
def isolated_server(
    *,
    code_root: Path,
    data_root: Path,
    users_root: Path,
    port: int,
    identity: RunnerIdentity,
    api_key: str,
    python_executable: str,
    base_url: str = DEFAULT_COCKPIT_BASE_URL,
    model: str = DEFAULT_MODEL,
    user: str = DEFAULT_USER,
    health_timeout: float = 90.0,
) -> Iterator[ServerContext]:
    """Start and clean up only the child process created by this runner."""

    ensure_port_available(port)
    env = build_child_env(
        api_key=api_key,
        code_root=code_root,
        data_root=data_root,
        users_root=users_root,
        base_url=base_url,
        model=model,
        user=user,
    )
    command = [
        python_executable,
        "-m",
        "uvicorn",
        "intelligence.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=str(code_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise RunnerError("隔离 Workbench 无法启动") from exc
    server_url = f"http://127.0.0.1:{port}"
    try:
        health = wait_for_health(
            base_url=server_url,
            identity=identity,
            timeout=health_timeout,
        )
        yield ServerContext(
            process=process,
            base_url=server_url,
            identity=identity,
            health=health,
            env=env,
        )
    finally:
        _terminate_child(process)


def _acceptance_output_path(output_dir: Path, label: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{stamp}-{label}.json"
    # A second invocation in the same second must never overwrite a receipt.
    index = 0
    candidate = path
    while candidate.exists():
        index += 1
        candidate = output_dir / f"{stamp}-{label}-{index}.json"
    return candidate


def invoke_acceptance(
    *,
    code_root: Path,
    base_url: str,
    user: str,
    timeout: float,
    identity: RunnerIdentity,
    output_path: Path,
    case_ids: Sequence[str] = (),
    python_executable: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    command = [
        python_executable,
        "-m",
        "intelligence.eval.acceptance",
        "run",
        "--base",
        base_url,
        "--user",
        user,
        "--timeout",
        str(timeout),
        "--output",
        str(output_path),
        *identity.as_expected_args(),
    ]
    for case_id in case_ids:
        command.extend(("--case", case_id))
    try:
        result = subprocess.run(
            command,
            cwd=str(code_root),
            env=dict(env) if env is not None else None,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RunnerError("Continuous acceptance 命令无法启动") from exc
    if result.returncode != 0:
        raise RunnerError(
            f"Continuous acceptance 命令失败（exit={result.returncode}）；"
            "请查看对应的非敏感输出收据"
        )
    try:
        record = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerError("acceptance 输出收据不可读") from exc
    if not isinstance(record, dict):
        raise RunnerError("acceptance 输出收据格式无效")
    return record


def require_layer1(record: Mapping[str, Any], *, label: str) -> Mapping[str, Any]:
    if record.get("acceptance_eligible") is not True:
        raise RunnerError(f"{label} preflight 或 Layer 1 不合格")
    summary = record.get("execution_summary")
    if not isinstance(summary, Mapping) or summary.get("layer1_eligible") is not True:
        raise RunnerError(f"{label} execution_summary.layer1_eligible=false")
    return summary


def _default_output_dir(code_root: Path) -> Path:
    return code_root / "tmp" / "continuous-cockpit-acceptance"


def run_suite(args: argparse.Namespace) -> Path:
    code_root = Path(args.code_root).expanduser().resolve()
    data_root = Path(args.data_root).expanduser().resolve()
    users_root = Path(args.users_root).expanduser().resolve()
    python_executable = python_executable_path(str(args.python))
    revision = clean_revision(code_root)
    identity = RunnerIdentity(
        revision=revision,
        code_root=str(code_root),
        model=str(args.model),
    )
    api_key = load_cockpit_api_key(Path(args.cockpit_config).expanduser())
    # This smoke occurs before starting Workbench and therefore cannot be
    # mistaken for a successful local server health check.
    smoke = cockpit_protocol_smoke(
        api_key=api_key,
        base_url=args.cockpit_base_url,
        model=identity.model,
        timeout=args.http_timeout,
    )
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else _default_output_dir(code_root)
    )
    users_root.mkdir(parents=True, exist_ok=True)
    with isolated_server(
        code_root=code_root,
        data_root=data_root,
        users_root=users_root,
        port=args.port,
        identity=identity,
        api_key=api_key,
        python_executable=python_executable,
        base_url=args.cockpit_base_url,
        model=identity.model,
        user=args.user,
        health_timeout=args.health_timeout,
    ) as server:
        gate_path = _acceptance_output_path(output_dir, "canary")
        gate = invoke_acceptance(
            code_root=code_root,
            base_url=server.base_url,
            user=args.user,
            timeout=args.turn_timeout,
            identity=identity,
            output_path=gate_path,
            case_ids=CANARY_CASES,
            python_executable=python_executable,
            env=server.env,
        )
        gate_summary = require_layer1(gate, label="canary")
        health_after_gate = _request_json(f"{server.base_url}/api/health", timeout=10)
        ok, failures = validate_health(health_after_gate, identity)
        if not ok:
            raise RunnerError("canary 后运行身份漂移：" + ",".join(failures))
        if (
            health_after_gate.get("runtime", {}).get("runtime_instance_id")
            != server.health.get("runtime", {}).get("runtime_instance_id")
        ):
            raise RunnerError("canary 前后 runtime_instance_id 漂移")

        full_path: Path | None = None
        full_summary: Mapping[str, Any] | None = None
        if args.suite == "full":
            full_path = _acceptance_output_path(output_dir, "full")
            full = invoke_acceptance(
                code_root=code_root,
                base_url=server.base_url,
                user=args.user,
                timeout=args.turn_timeout,
                identity=identity,
                output_path=full_path,
                case_ids=(),
                python_executable=python_executable,
                env=server.env,
            )
            full_summary = require_layer1(full, label="full")
            if (
                full_summary.get("total_turns") != 30
                or full_summary.get("path_matches") != 30
                or full_summary.get("continuous_episode_turns") != 28
                or full_summary.get("valid_episode_receipts") != 28
            ):
                raise RunnerError("full Layer 1 计数未达到 30/30、28/28 目标")

        receipt_path = _acceptance_output_path(output_dir, "runner")
        receipt = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "suite": args.suite,
            "code_root": str(code_root),
            "data_root": str(data_root),
            "port": args.port,
            "identity": {
                "revision": identity.revision,
                "code_root": identity.code_root,
                "mode": identity.mode,
                "backend": identity.backend,
                "model": identity.model,
                "provider_label": identity.provider_label,
                "provider_protocol": identity.provider_protocol,
            },
            "cockpit_smoke": smoke,
            "health": _health_projection(server.health),
            "canary": {
                "path": str(gate_path),
                "execution_summary": gate_summary,
            },
            "full": (
                {
                    "path": str(full_path),
                    "execution_summary": full_summary,
                }
                if full_path is not None
                else None
            ),
        }
        try:
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                errors="strict",
            )
        except OSError as exc:
            raise RunnerError("runner 收据写入失败") from exc
    return receipt_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="在隔离 Workbench 进程中用 Cockpit 验收 Continuous Harness"
    )
    parser.add_argument("--suite", choices=("canary", "full"), default="canary")
    parser.add_argument("--code-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--data-root",
        default=os.environ.get("FINANCE_WS")
        or str(Path(__file__).resolve().parents[1]),
    )
    parser.add_argument("--users-root", default="")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cockpit-config", default=str(DEFAULT_COCKPIT_CONFIG))
    parser.add_argument("--cockpit-base-url", default=DEFAULT_COCKPIT_BASE_URL)
    parser.add_argument("--output-dir")
    parser.add_argument("--health-timeout", type=float, default=90.0)
    parser.add_argument("--http-timeout", type=float, default=15.0)
    parser.add_argument("--turn-timeout", type=float, default=DEFAULT_TIMEOUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.users_root:
        args.users_root = str(
            Path(args.code_root).expanduser().resolve()
            / "tmp"
            / "continuous-cockpit-users"
        )
    try:
        receipt = run_suite(args)
    except RunnerError as exc:
        print(f"❌ Cockpit Continuous 验收停止：{exc}")
        return 2
    print(f"✅ Cockpit Continuous 验收完成，收据：{receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
