from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from intelligence.summary import WorkflowStep


def tail_lines(text: str, limit: int = 20) -> list[str]:
    lines = text.splitlines()
    return lines[-limit:]


def command_line(argv: Sequence[str]) -> str:
    return " ".join(str(item) for item in argv)


def _status_json_path(argv: Sequence[str]) -> Path | None:
    items = [str(item) for item in argv]
    if "--status-json" not in items:
        return None
    index = items.index("--status-json")
    if index + 1 >= len(items):
        return None
    return Path(items[index + 1]).expanduser()


def _load_structured_result(path: Path | None) -> tuple[dict[str, object] | None, str | None]:
    if path is None:
        return None, None
    if not path.is_file():
        return None, f"structured status file not found: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid structured status file {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"structured status must be a JSON object: {path}"
    return payload, None


def run_command_step(
    name: str,
    argv: Sequence[str],
    cwd: str | Path,
    outputs: list[str] | None = None,
    timeout_sec: float | None = None,
) -> WorkflowStep:
    started = time.monotonic()
    status_path = _status_json_path(argv)
    if status_path is not None:
        try:
            status_path.unlink(missing_ok=True)
        except OSError as exc:
            return WorkflowStep(
                name=name,
                status="FAIL",
                command=command_line(argv),
                returncode=None,
                duration_sec=round(time.monotonic() - started, 3),
                outputs=outputs or [],
                errors=[f"failed to clear stale structured status: {exc}"],
            )
    try:
        process = subprocess.Popen(
            [str(item) for item in argv],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        duration = round(time.monotonic() - started, 3)
        structured_result, structured_error = _load_structured_result(status_path)
        timeout_label = f"{timeout_sec:g}" if timeout_sec is not None else "configured"
        return WorkflowStep(
            name=name,
            status="FAIL",
            command=command_line(argv),
            returncode=process.returncode,
            duration_sec=duration,
            stdout_tail=tail_lines(stdout),
            stderr_tail=tail_lines(stderr),
            outputs=outputs or [],
            warnings=[structured_error] if structured_error else [],
            errors=[f"command timed out after {timeout_label} seconds"],
            structured_result=structured_result,
        )
    except Exception as exc:
        duration = round(time.monotonic() - started, 3)
        return WorkflowStep(
            name=name,
            status="FAIL",
            command=command_line(argv),
            returncode=None,
            duration_sec=duration,
            outputs=outputs or [],
            errors=[f"failed to start command: {exc}"],
        )

    duration = round(time.monotonic() - started, 3)
    status = "PASS" if process.returncode == 0 else "FAIL"
    structured_result, structured_error = _load_structured_result(status_path)
    return WorkflowStep(
        name=name,
        status=status,
        command=command_line(argv),
        returncode=process.returncode,
        duration_sec=duration,
        stdout_tail=tail_lines(stdout),
        stderr_tail=tail_lines(stderr),
        outputs=outputs or [],
        warnings=[structured_error] if structured_error else [],
        errors=[] if process.returncode == 0 else [f"command failed with returncode {process.returncode}"],
        structured_result=structured_result,
    )
