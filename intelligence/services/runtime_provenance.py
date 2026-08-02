"""Small, read-only runtime identity used by health and acceptance checks.

The Workbench can have multiple checkouts and virtual environments on the same
machine.  A green HTTP health check is not enough if it came from an older
checkout, so expose a non-secret identity for the process that answered it.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import intelligence

_FINGERPRINT_PACKAGES = (
    "fastapi",
    "pydantic",
    "httpx",
    "duckdb",
    "pytest",
)


def _git_output(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip()


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in _FINGERPRINT_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "missing"
    return versions


def build_runtime_provenance(
    code_root: str | Path,
    *,
    runtime_instance_id: str | None = None,
) -> dict[str, object]:
    """Return stable process identity without exposing secrets or env values."""

    root = Path(code_root).expanduser().resolve()
    import_root = Path(intelligence.__file__).resolve().parents[1]
    revision = _git_output(root, "rev-parse", "HEAD")
    dirty = bool(_git_output(root, "status", "--porcelain"))
    dependencies = _dependency_versions()
    fingerprint_payload = "\n".join(
        f"{name}={version}" for name, version in sorted(dependencies.items())
    ).encode("utf-8")
    return {
        "runtime_instance_id": runtime_instance_id or f"runtime_{uuid4().hex}",
        "source_revision": revision or "unknown",
        "source_dirty": dirty,
        "code_root": str(root),
        "import_root": str(import_root),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_prefix": str(Path(sys.prefix).resolve()),
        "dependency_fingerprint": hashlib.sha256(fingerprint_payload).hexdigest(),
        "dependencies": dependencies,
    }
