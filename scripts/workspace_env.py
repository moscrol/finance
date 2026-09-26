"""Resolve the target worktree's environment contract using only the stdlib.

A local venv wins; linked worktrees may reuse the common checkout's venv.
Never resolve the Python executable symlink: that discards venv identity.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def load_spec(root: Path) -> dict:
    spec = json.loads((root / "test-environment.json").read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not spec.get("interpreter"):
        raise ValueError("test-environment.json requires interpreter")
    return spec


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        timeout=10, check=True,
    )
    return result.stdout.strip()


def python_path(root: Path, spec: dict | None = None) -> Path:
    root = root.resolve()
    spec = load_spec(root) if spec is None else spec
    override = os.environ.get("FWP_WORKBENCH_PYTHON")
    path = Path(override or spec["interpreter"]).expanduser()
    if path.is_absolute():
        return path
    local = root / path
    environment_root = root / path.parts[0]
    if override or local.exists() or environment_root.exists() or environment_root.is_symlink():
        return local
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    shared = common.parent / path
    return shared if shared.exists() else local


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--run", nargs=argparse.REMAINDER, help="execute with resolved Python")
    args = parser.parse_args()
    try:
        python = python_path(args.repo)
        if args.run is not None:
            if not args.run:
                raise ValueError("--run requires a Python argument")
            raise SystemExit(subprocess.call([str(python), *args.run], cwd=args.repo))
        print(python)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"environment contract unavailable: {exc}\n")
