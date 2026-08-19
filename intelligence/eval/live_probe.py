"""Traceable live probe: sidecar + POST /api/runs + on-disk run artifacts.

This is the official replacement for in-process ``answer_query`` probes that
could only describe the final answer. It starts a one-shot sidecar with
``WORKBENCH_GROUNDED_PRESENTER=0`` (marker lane), posts ``/api/runs``, and
reads the run directory — never the public trace projection, which strips
prompts.

Does not touch production 8792.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from intelligence.services.ask_llm_context import LLM_CONTEXT_FILENAME
from intelligence.services.judge_degrade import split_degrade_from_payloads

STALE_MARK = "⚠️已被新证据取代"
RESERVED_PORTS = frozenset({8792, 8793, 8795, 8799, 8801})
PORT_SCAN = range(8796, 8821)
LIVE_LOCK_PATH = Path("/tmp/finance-8792-live.lock")
DEFAULT_LAUNCHER = Path.home() / ".local/bin" / "start-finance-workbench"
DEFAULT_PYTHON = (
    Path.home() / "finance-workspace-private" / ".venv-workbench" / "bin" / "python"
)
DEFAULT_OUT_DIR = Path.home() / ".finance-runtime" / "live-probe-traceability"
DEFAULT_USER = "live-probe"
RUN_ARTIFACTS = (
    "trace.jsonl",
    "run.json",
    "report.json",
    "answer.md",
    LLM_CONTEXT_FILENAME,
    "summary.json",
)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ProbeBlocked(RuntimeError):
    """Refused to start: live lock, reserved/busy port, or missing key."""


@dataclass(frozen=True)
class SidecarSpec:
    port: int
    repo_root: Path
    python: Path
    launcher: Path
    users_dir: Path
    user: str


@dataclass
class ProbeInspection:
    stale_marker_present: bool
    evidence_grade: str
    first_hand: bool
    answer_mentions_stale: bool
    stale_marker_files: list[str]
    prompt_present: bool
    prompt_text: str
    steps: list[dict[str, Any]]
    tools: list[dict[str, Any]]


def port_is_listening(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def choose_port(
    *,
    preferred: int,
    is_busy: Callable[[int], bool],
) -> int:
    candidates: list[int] = []
    if preferred not in RESERVED_PORTS:
        candidates.append(preferred)
    candidates.extend(port for port in PORT_SCAN if port != preferred)
    for port in candidates:
        if port in RESERVED_PORTS:
            continue
        if not is_busy(port):
            return port
    raise ProbeBlocked("no free sidecar port in 8796-8820")


def assert_safe_to_start(
    *,
    lock_path: Path,
    port: int,
    is_busy: Callable[[int], bool],
) -> None:
    if lock_path.exists():
        raise ProbeBlocked(f"live.lock present: {lock_path}")
    if port in RESERVED_PORTS:
        raise ProbeBlocked(f"port {port} is reserved for other workbench instances")
    if is_busy(port):
        raise ProbeBlocked(f"port {port} is already listening")


def sidecar_zsh(spec: SidecarSpec) -> str:
    """Source launcher exports only; never execute its production uvicorn."""

    launcher = shlex.quote(str(spec.launcher))
    repo = shlex.quote(str(spec.repo_root))
    python = shlex.quote(str(spec.python))
    users = shlex.quote(str(spec.users_dir))
    user = shlex.quote(spec.user)
    port = str(int(spec.port))
    return f"""
set -euo pipefail
set -a
. <(grep '^export ' {launcher})
set +a
export WORKBENCH_GROUNDED_PRESENTER=0
export WORKBENCH_PERSIST_LLM_CONTEXT=1
export RAG_WORKER_ENABLED=0
export WORKBENCH_REPO_ROOT={repo}
export PYTHONPATH={repo}
export FORESIGHT_USERS_DIR={users}
export FORESIGHT_USER={user}
if [[ -z "${{FORESIGHT_BUILTIN_LLM_API_KEY:-}}${{OPENAI_API_KEY:-}}" ]]; then
  print -u2 -- "sidecar: no LLM key after sourcing launcher exports"
  exit 1
fi
mkdir -p {users}
cd {repo}
exec {python} -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port {port}
""".strip()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def inspect_run_dir(run_dir: Path) -> ProbeInspection:
    llm_text = _read_text(run_dir / LLM_CONTEXT_FILENAME)
    trace_text = _read_text(run_dir / "trace.jsonl")
    answer_text = _read_text(run_dir / "answer.md")
    stale_files: list[str] = []
    if STALE_MARK in llm_text:
        stale_files.append(LLM_CONTEXT_FILENAME)
    if STALE_MARK in trace_text:
        stale_files.append("trace.jsonl")
    if LLM_CONTEXT_FILENAME in stale_files:
        grade = "llm_context"
    elif "trace.jsonl" in stale_files:
        grade = "trace"
    else:
        grade = "absent"
    first_hand = grade != "absent"
    steps: list[dict[str, Any]] = []
    for line in trace_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            steps.append(payload)
    prompt_parts: list[str] = []
    tools: list[dict[str, Any]] = []
    if llm_text:
        try:
            context = json.loads(llm_text)
        except json.JSONDecodeError:
            context = {}
        if isinstance(context, dict):
            for key in ("prepared_synthesis_messages", "synthesis_messages"):
                messages = context.get(key) or []
                if isinstance(messages, list):
                    for message in messages:
                        if isinstance(message, dict) and isinstance(
                            message.get("content"), str
                        ):
                            prompt_parts.append(message["content"])
            traces = context.get("provider_traces") or []
            if isinstance(traces, list):
                for item in traces:
                    if isinstance(item, dict):
                        tools.append(item)
    if not tools:
        for step in steps:
            retrieval = step.get("retrieval")
            if isinstance(retrieval, dict) and retrieval:
                tools.append(
                    {
                        "step_id": step.get("step_id"),
                        "name": step.get("name"),
                        "sources": retrieval.get("sources"),
                        "citation_counts": retrieval.get("citation_counts"),
                        "started_at": step.get("started_at"),
                        "finished_at": step.get("finished_at"),
                    }
                )
    return ProbeInspection(
        stale_marker_present=first_hand,
        evidence_grade=grade,
        first_hand=first_hand,
        answer_mentions_stale=STALE_MARK in answer_text,
        stale_marker_files=stale_files,
        prompt_present=bool(prompt_parts),
        prompt_text="\n\n".join(prompt_parts),
        steps=steps,
        tools=tools,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def degrade_counts_from_run_dir(run_dir: Path) -> dict[str, int]:
    """Split probe degrades so vendor jitter does not pollute content A/B."""

    report = _load_json_object(run_dir / "report.json")
    summary = _load_json_object(run_dir / "summary.json")
    run = _load_json_object(run_dir / "run.json")
    degrades = run.get("degrades") or summary.get("degrades") or []
    return split_degrade_from_payloads(degrades, report, summary, run)


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with _OPENER.open(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise ProbeBlocked(f"expected JSON object from {url}")
    return body


def post_ask(base_url: str, *, question: str, user: str) -> str:
    payload = _request_json(
        "POST",
        f"{base_url.rstrip('/')}/api/runs",
        payload={
            "question": question,
            "user": user,
            "task_type": "ask",
            "compose": True,
        },
        timeout=30,
    )
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ProbeBlocked(f"POST /api/runs returned no run_id: {payload!r}")
    return run_id


def wait_for_run(
    base_url: str,
    run_id: str,
    *,
    user: str,
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    url = (
        f"{base_url.rstrip('/')}/api/runs/{urllib.parse.quote(run_id, safe='')}"
        f"?{urllib.parse.urlencode({'user': user})}"
    )
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last = _request_json("GET", url, timeout=10)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(1)
            continue
        status = last.get("status")
        if status in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(1)
    raise ProbeBlocked(f"run {run_id} did not finish within {timeout:.0f}s: {last}")


def wait_for_health(base_url: str, *, timeout: float = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    url = f"{base_url.rstrip('/')}/api/health"
    last_error = "not contacted"
    while time.monotonic() < deadline:
        try:
            payload = _request_json("GET", url, timeout=5)
            status = payload.get("status") or payload.get("ready")
            if status in {"healthy", "ready", True, "ok"}:
                return payload
            last_error = f"status={status!r}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ProbeBlocked) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise ProbeBlocked(f"sidecar health not ready within {timeout:.0f}s: {last_error}")


def copy_run_artifacts(run_dir: Path, dest: Path) -> dict[str, str]:
    dest.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name in RUN_ARTIFACTS:
        src = run_dir / name
        if not src.is_file():
            continue
        target = dest / name
        target.write_bytes(src.read_bytes())
        copied[name] = str(target)
    return copied


def _ps_args(pid: int) -> str:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "args="],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def stop_sidecar(pid: int, port: int) -> None:
    args = _ps_args(pid)
    if not args:
        return
    if f"--port {port}" not in args:
        raise ProbeBlocked(
            f"pid {pid} argv does not contain --port {port}; refusing to kill: {args[:200]}"
        )
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not _ps_args(pid):
            return
        time.sleep(0.2)
    os.kill(pid, signal.SIGKILL)


def start_sidecar(spec: SidecarSpec, *, log_path: Path, timeout: float = 60) -> int:
    assert_safe_to_start(
        lock_path=LIVE_LOCK_PATH,
        port=spec.port,
        is_busy=port_is_listening,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    script = sidecar_zsh(spec)
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            ["zsh", "-c", script],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    try:
        wait_for_health(f"http://127.0.0.1:{spec.port}", timeout=timeout)
    except Exception:
        stop_sidecar(process.pid, spec.port)
        raise
    return process.pid


def run_dir_for(users_dir: Path, user: str, run_id: str) -> Path:
    return users_dir / user / "runs" / run_id


def write_receipt(
    path: Path,
    *,
    query: str,
    run_id: str,
    inspection: ProbeInspection,
    artifacts: dict[str, str],
    extra: dict[str, Any],
) -> None:
    payload = {
        "query": query,
        "run_id": run_id,
        "stale_marker": STALE_MARK,
        "inspection": asdict(inspection),
        "artifacts": artifacts,
        **extra,
    }
    # Full prompt lives in llm_context.json; keep the receipt grep-able but short.
    inspection_view = dict(payload["inspection"])
    prompt = str(inspection_view.get("prompt_text") or "")
    inspection_view["prompt_chars"] = len(prompt)
    inspection_view["prompt_preview"] = prompt[:1200]
    inspection_view.pop("prompt_text", None)
    payload["inspection"] = inspection_view
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_python(repo_root: Path) -> Path:
    local = repo_root / ".venv-workbench" / "bin" / "python"
    if local.is_file():
        return local
    if DEFAULT_PYTHON.is_file():
        return DEFAULT_PYTHON
    return Path("python3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="sidecar live probe that writes grep-able LLM context + trace.jsonl",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="start sidecar (unless --attach), POST /api/runs, copy artifacts")
    ask.add_argument("question")
    ask.add_argument("--slug", default="live-sample")
    ask.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ask.add_argument("--port", type=int, default=8796)
    ask.add_argument("--repo-root", type=Path, default=Path.cwd())
    ask.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    ask.add_argument("--python", type=Path, default=None)
    ask.add_argument("--user", default=DEFAULT_USER)
    ask.add_argument("--timeout", type=float, default=300)
    ask.add_argument("--keep-sidecar", action="store_true")
    ask.add_argument("--attach", default="", help="existing sidecar base URL, e.g. http://127.0.0.1:8796")

    inspect = sub.add_parser("inspect", help="inspect an existing run directory")
    inspect.add_argument("run_dir", type=Path)

    start = sub.add_parser("start-sidecar", help="start sidecar and print pid/port")
    start.add_argument("--port", type=int, default=8796)
    start.add_argument("--repo-root", type=Path, default=Path.cwd())
    start.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    start.add_argument("--python", type=Path, default=None)
    start.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    start.add_argument("--user", default=DEFAULT_USER)

    stop = sub.add_parser("stop-sidecar", help="stop sidecar by pid file")
    stop.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)

    args = parser.parse_args(argv)

    if args.cmd == "inspect":
        inspection = inspect_run_dir(args.run_dir)
        print(json.dumps(asdict(inspection), ensure_ascii=False, indent=2))
        return 0 if inspection.first_hand or not inspection.answer_mentions_stale else 2

    if args.cmd == "stop-sidecar":
        meta_path = args.out_dir / "sidecar.json"
        if not meta_path.is_file():
            raise SystemExit(f"no sidecar.json under {args.out_dir}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stop_sidecar(int(meta["pid"]), int(meta["port"]))
        print(f"stopped pid {meta['pid']} port {meta['port']}")
        return 0

    repo_root = args.repo_root.resolve()
    python = args.python or _resolve_python(repo_root)
    users_dir = args.out_dir / "users"
    spec = SidecarSpec(
        port=choose_port(preferred=args.port, is_busy=port_is_listening)
        if args.cmd != "ask" or not args.attach
        else args.port,
        repo_root=repo_root,
        python=python,
        launcher=args.launcher,
        users_dir=users_dir,
        user=args.user,
    )

    if args.cmd == "start-sidecar":
        pid = start_sidecar(spec, log_path=args.out_dir / "sidecar.err.log")
        meta = {"pid": pid, "port": spec.port, "users_dir": str(users_dir)}
        (args.out_dir / "sidecar.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        print(json.dumps(meta, indent=2))
        return 0

    started_pid: int | None = None
    started = time.monotonic()
    if args.attach:
        base_url = args.attach.rstrip("/")
        wait_for_health(base_url, timeout=15)
        users_dir = Path(os.environ.get("FORESIGHT_USERS_DIR") or users_dir)
    else:
        pid = start_sidecar(spec, log_path=args.out_dir / "sidecar.err.log")
        started_pid = pid
        (args.out_dir / "sidecar.json").write_text(
            json.dumps({"pid": pid, "port": spec.port}, indent=2),
            encoding="utf-8",
        )
        base_url = f"http://127.0.0.1:{spec.port}"
    try:
        run_id = post_ask(base_url, question=args.question, user=args.user)
        status = wait_for_run(
            base_url, run_id, user=args.user, timeout=args.timeout
        )
        run_dir = run_dir_for(users_dir, args.user, run_id)
        dest = args.out_dir / args.slug
        artifacts = copy_run_artifacts(run_dir, dest)
        inspection = inspect_run_dir(dest if artifacts else run_dir)
        receipt = args.out_dir / f"{args.slug}.json"
        degrade_split = degrade_counts_from_run_dir(dest if artifacts else run_dir)
        write_receipt(
            receipt,
            query=args.question,
            run_id=run_id,
            inspection=inspection,
            artifacts=artifacts,
            extra={
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "base_url": base_url,
                "run_status": status.get("status"),
                "run_dir": str(run_dir),
                "grounded_presenter": "0",
                "repo_root": str(repo_root),
                "evidence_grade": inspection.evidence_grade,
                "judge_unavailable_count": degrade_split["judge_unavailable_count"],
                "content_degraded_count": degrade_split["content_degraded_count"],
            },
        )
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "receipt": str(receipt),
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                    "stale_marker_present": inspection.stale_marker_present,
                    "stale_marker_files": inspection.stale_marker_files,
                    "prompt_present": inspection.prompt_present,
                    "evidence_grade": inspection.evidence_grade,
                    "first_hand": inspection.first_hand,
                    "answer_mentions_stale": inspection.answer_mentions_stale,
                    "judge_unavailable_count": degrade_split["judge_unavailable_count"],
                    "content_degraded_count": degrade_split["content_degraded_count"],
                    "steps": [
                        {
                            "step_id": step.get("step_id"),
                            "name": step.get("name"),
                            "started_at": step.get("started_at"),
                            "finished_at": step.get("finished_at"),
                        }
                        for step in inspection.steps
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        if started_pid is not None and not args.keep_sidecar:
            stop_sidecar(started_pid, spec.port)


if __name__ == "__main__":
    raise SystemExit(main())
