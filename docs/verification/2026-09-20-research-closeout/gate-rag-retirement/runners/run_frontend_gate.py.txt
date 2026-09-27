#!/usr/bin/env python3
"""Run the frontend checks with a receipt tied to the tested checkout.

A command's zero exit code does not prove which source it tested. Capture HEAD
and the whole Git status before and after, refuse dirty/moving checkouts, and
keep every run in a new external directory. Sampling does not detect edits
that are made and restored between the two observations; use an isolated tree.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


COMMANDS = (
    ("pnpm", "install", "--frozen-lockfile"),
    ("pnpm", "lint"),
    ("pnpm", "typecheck"),
    ("pnpm", "test"),
    ("pnpm", "build"),
    ("pnpm", "test:e2e"),
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identity(tree: Path) -> dict:
    def git(*args: str) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=tree, check=True, capture_output=True, timeout=30
        ).stdout

    root = Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve()
    if root != tree:
        raise ValueError("--tree must be the Git checkout root")
    revision = git("rev-parse", "HEAD").decode().strip()
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    if git("rev-parse", "HEAD").decode().strip() != revision:
        raise ValueError("HEAD changed while recording identity")
    return {
        "recorded_at": now(),
        "revision": revision,
        "dirty": bool(status),
        "status_porcelain_z": status.decode("utf-8", errors="replace"),
    }


def run_gate(
    tree: Path,
    output: Path,
    expected_revision: str,
    *,
    commands=COMMANDS,
    env: dict[str, str] | None = None,
) -> int:
    tree, output = tree.resolve(), output.resolve()
    if output.is_relative_to(tree):
        raise ValueError("--output must be outside the tested checkout")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": 1,
        "leaf": "frontend",
        "tree": str(tree),
        "revision": expected_revision,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "started_at": now(),
        "identity_before": None,
        "identity_after": None,
        "dirty": None,
        "identity_stable": False,
        "complete": False,
        "checks": [],
        "exit_code": None,
    }

    def save() -> None:
        temporary = output / "frontend.json.tmp"
        temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(output / "frontend.json")

    save()
    try:
        before = receipt["identity_before"] = identity(tree)
        if before["revision"] != expected_revision or before["dirty"]:
            raise ValueError("initial checkout is dirty or differs from --expect-revision")
        for index, command in enumerate(commands):
            log = output / f"frontend-{index}.log.txt"
            started = time.monotonic()
            with log.open("wb") as stream:
                try:
                    result = subprocess.run(
                        list(command), cwd=tree / "intelligence/webapp", env=env,
                        stdout=stream, stderr=subprocess.STDOUT,
                    )
                    code = result.returncode
                except OSError as exc:
                    stream.write(str(exc).encode())
                    code = 127
            data = log.read_bytes()
            receipt["checks"].append({
                "command": list(command), "exit_code": code,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "log": log.name, "log_bytes": len(data),
                "log_sha256": hashlib.sha256(data).hexdigest(),
            })
            save()
            print(json.dumps({"command": list(command), "exit_code": code}), flush=True)
            if index == 0 and code:
                break
        receipt["complete"] = len(receipt["checks"]) == len(commands) and bool(commands)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        receipt["error"] = str(exc)
    finally:
        try:
            receipt["identity_after"] = identity(tree)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            receipt["identity_error"] = str(exc)
        before, after = receipt["identity_before"], receipt["identity_after"]
        if before is not None and after is not None:
            receipt["dirty"] = before["dirty"] or after["dirty"]
            receipt["identity_stable"] = (
                before["revision"] == after["revision"] == expected_revision
                and not receipt["dirty"]
            )
        receipt["exit_code"] = (
            2 if not receipt["identity_stable"] or "error" in receipt
            else 0 if receipt["complete"] and all(
                check["exit_code"] == 0 for check in receipt["checks"]
            ) else 1
        )
        receipt["finished_at"] = now()
        save()
    return receipt["exit_code"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--workbench-port", type=int, default=18981)
    parser.add_argument("--re06-port", type=int, default=18984)
    args = parser.parse_args()
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR") if key in os.environ}
    env.update({
        "CI": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "WORKBENCH_PYTHON": args.python,
        "WORKBENCH_E2E_PORT": str(args.workbench_port),
        "RE06_E2E_PORT": str(args.re06_port),
        "RE06_E2E_URL": f"http://127.0.0.1:{args.re06_port}",
    })
    try:
        code = run_gate(args.tree, args.output, args.expect_revision, env=env)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps({"receipt": str(args.output.resolve() / "frontend.json"), "exit_code": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
