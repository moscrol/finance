"""Read-only preflight for the daily generation code/data split.

A safe parent is not a safe write destination: existing descendant links can
redirect date/user/status/output files into CODE_ROOT. Inspect metadata, not
file contents, including links to otherwise legitimate external persistence.
This is a static configuration guard, not an OS sandbox or a symlink-race lock.
"""
from __future__ import annotations

from datetime import date
import os
from pathlib import Path
from typing import TYPE_CHECKING

from intelligence import userspace
from intelligence.paths import ProjectPaths, default_paths
from intelligence.services.episode_store import resolve_episode_store_root

if TYPE_CHECKING:
    from intelligence.workflows.daily_review import DailyReviewOptions


def _outside_code(path: Path, *, code: Path, data: Path) -> Path:
    resolved = (data / path.expanduser()).resolve()
    if resolved.is_relative_to(code):
        raise ValueError(f"generation writable path is in CODE_ROOT: {path} -> {resolved}")
    return resolved


def _validate_write_tree(path: Path, *, code: Path, data: Path, seen: set[Path]) -> None:
    """Resolve every existing descendant, following external safe dirs only once.

    Checking just symlinks yielded by rglob is insufficient: rglob doesn't descend
    into linked directories. A safe external user dir can contain another link
    back to CODE_ROOT. Cycles are harmless once each physical directory is seen.
    Files are never read and directories/files are never created by this check.
    """
    pending = [path]
    while pending:
        resolved = _outside_code(pending.pop(), code=code, data=data)
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_dir():
            pending.extend(resolved.iterdir())


def validate_generation_paths(
    options: DailyReviewOptions,
    *,
    code_root: Path,
    summary_json: str | None = None,
    paths: ProjectPaths | None = None,
) -> None:
    """Validate selected plan paths before gates, subprocesses or metrics write.

    Production callers enter through run_daily_generation.py. Other daily CLI
    callers keep their existing contract; this helper never changes their env.
    Missing direct executables fail at the usual runner boundary, never search
    DATA_ROOT. Existing direct executables must resolve to a regular code file.
    """
    from intelligence.workflows.daily_review import build_daily_review_plan, filter_plan

    paths = paths or default_paths()
    code, data = code_root.resolve(strict=True), paths.finance_root.resolve(strict=True)
    # Dates become path components as well as SQL keys; don't admit path traversal.
    if date.fromisoformat(options.date).isoformat() != options.date:
        raise ValueError("generation date must be YYYY-MM-DD")
    base_plan = build_daily_review_plan(options, paths)
    plan, _ = filter_plan(base_plan, options)
    names = {step.name for step in plan}

    targets = [paths.market_exports, paths.review_daily_root / options.date,
               paths.review_workbench.parent, userspace.user_space(options.user).root,
               # Children use the environment's user unless they have their own --user.
               userspace.user_space(None).root,
               resolve_episode_store_root(),
               data / "skills/daily-full-review/state"]
    if "export-increment" in names:
        targets.append(Path(os.environ.get("DUCKDB_SNAPSHOT_OUT_ROOT") or data / "db/snapshots") / "increments")
    if "checkpoint-recheck" in names:
        from intelligence.services.checkpoints import RECHECK_VAULT_SUBDIR, resolve_recheck_vault

        vault, _ = resolve_recheck_vault(userspace.user_space(None).root)
        targets.append(vault / RECHECK_VAULT_SUBDIR / f"{options.date}.md")
    if summary_json:
        # A single output file is not a whole external directory to scan.
        _outside_code(Path(summary_json), code=code, data=data)
    seen: set[Path] = set()
    for target in targets:
        _validate_write_tree(target, code=code, data=data, seen=seen)
    for step in plan:
        for output in step.outputs:
            _outside_code(Path(output), code=code, data=data)
        if step.argv[2] != "-m":
            executable = Path(step.argv[2])
            if executable.exists() or executable.is_symlink():
                resolved = executable.resolve(strict=True)
                if not resolved.is_relative_to(code) or not resolved.is_file():
                    raise ValueError(f"generation code escapes FINANCE_CODE_ROOT: {executable}")
