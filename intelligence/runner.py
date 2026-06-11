from __future__ import annotations

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


def run_command_step(name: str, argv: Sequence[str], cwd: str | Path, outputs: list[str] | None = None) -> WorkflowStep:
    started = time.monotonic()
    try:
        result = subprocess.run(
            [str(item) for item in argv],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
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
    status = "PASS" if result.returncode == 0 else "FAIL"
    return WorkflowStep(
        name=name,
        status=status,
        command=command_line(argv),
        returncode=result.returncode,
        duration_sec=duration,
        stdout_tail=tail_lines(result.stdout),
        stderr_tail=tail_lines(result.stderr),
        outputs=outputs or [],
        errors=[] if result.returncode == 0 else [f"command failed with returncode {result.returncode}"],
    )
