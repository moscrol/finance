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


def _package_tree_fingerprint(package_root: Path) -> tuple[str, int]:
    """Hash one ``intelligence/`` tree by path + content of every module.

    Returns ``("", 0)`` when the tree is absent, so callers can tell "no tree
    to compare" apart from "compared and differed".
    """

    if not package_root.is_dir():
        return ("", 0)
    digest = hashlib.sha256()
    counted = 0
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            body = path.read_bytes()
        except OSError:
            # An unreadable module still changes what runs; record the path so
            # the fingerprint moves rather than silently matching.
            digest.update(str(path.relative_to(package_root)).encode("utf-8"))
            digest.update(b"\0<unreadable>\n")
            counted += 1
            continue
        digest.update(str(path.relative_to(package_root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(body).hexdigest().encode("ascii"))
        digest.update(b"\n")
        counted += 1
    return (digest.hexdigest(), counted)


def loaded_package_root() -> Path:
    """Return the ``intelligence/`` directory this very module was imported from.

    Deliberately derived from ``__file__`` rather than ``PYTHONPATH``,
    ``WORKBENCH_REPO_ROOT`` or an import of the top-level package: those say
    what someone *intended* to load.  ``__file__`` is the only source that
    reports what actually got loaded, which is the whole point of this check.
    """

    return Path(__file__).resolve().parents[1]


def build_runtime_provenance(code_root: str | Path) -> dict[str, object]:
    """Return stable process identity without exposing secrets or env values.

    ``source_revision`` describes the **git checkout at** ``code_root``, which is
    not necessarily the code this process executes.  Production runs from a
    standalone snapshot on ``PYTHONPATH`` while ``code_root`` still points at the
    repository, so a health payload carrying only that field reports a revision
    the process may never have loaded.

    That is not hypothetical.  On 2026-08-08 health reported ``9380b3b9`` while
    the snapshot was missing 14 modules and the whole ``intelligence/runtime/``
    package; three separate fixes were verified as "live" against a version
    number that described a different directory.  A merge updates the repository
    and therefore this field, but never the snapshot -- so the number moves
    forward exactly when it is most likely to be wrong.

    The ``loaded_*`` fields below close that gap by hashing the tree this module
    was actually imported from and comparing it with the repository's tree, so
    the payload can state drift instead of implying freshness.

    Cost: called once per process (``create_app``) and the result is reused by
    every health response, so the two tree walks are startup-time, not
    per-request.
    """

    root = Path(code_root).expanduser().resolve()
    revision = _git_output(root, "rev-parse", "HEAD")
    dirty = bool(_git_output(root, "status", "--porcelain"))
    dependencies = _dependency_versions()
    fingerprint_payload = "\n".join(
        f"{name}={version}" for name, version in sorted(dependencies.items())
    ).encode("utf-8")

    loaded_root = loaded_package_root()
    loaded_fingerprint, loaded_modules = _package_tree_fingerprint(loaded_root)
    repo_package = root / loaded_root.name
    repo_fingerprint, repo_modules = _package_tree_fingerprint(repo_package)
    # Tri-state on purpose. ``None`` means "no repository tree to compare with"
    # (a snapshot-only deploy); collapsing that into ``False`` would cry drift
    # where none is knowable, and into ``True`` would repeat the original bug of
    # implying agreement that was never checked.
    if not loaded_fingerprint or not repo_fingerprint:
        code_matches_repo: bool | None = None
    else:
        code_matches_repo = loaded_fingerprint == repo_fingerprint

    return {
        "source_revision": revision or "unknown",
        "source_dirty": dirty,
        "code_root": str(root),
        # Where the running code really came from. Differs from ``code_root``
        # whenever a snapshot or a second worktree is on ``PYTHONPATH``.
        "loaded_code_root": str(loaded_root),
        "loaded_tree_fingerprint": loaded_fingerprint or "unknown",
        "loaded_module_count": loaded_modules,
        "repo_tree_fingerprint": repo_fingerprint or "unknown",
        "repo_module_count": repo_modules,
        "code_matches_repo": code_matches_repo,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_prefix": str(Path(sys.prefix).resolve()),
        "dependency_fingerprint": hashlib.sha256(fingerprint_payload).hexdigest(),
        "dependencies": dependencies,
    }
