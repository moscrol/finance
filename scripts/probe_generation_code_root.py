#!/usr/bin/env python3
"""Independent #50 boundary probe: fail if guarded daily generation escapes its roots.

Runs real launcher/CLI/runner against temporary code/data copies; it reuses only
``tests/test_generation_code_root.py::rig`` for safe fixture SQL/quality results.
No production DB, user state, model, nightly L2 or KB receive is invoked. Each
case gets its own copy; the target checkout is never mutated. Exit 0 = all
predicates hold, 1 = counterexample found, 2 = probe/fixture unavailable.

Run with the project's .venv-workbench interpreter. ``--repo`` can point to a
repaired checkout to rerun the same predicates. JSON contains observations,
not just process exit codes: stale code raising an exception is NOT a guard.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CASES = (
    "summary_full",
    "summary_abbrev",
    "user_subdir_symlink",
    "html_day_symlink",
    "quality_state_symlink",
    "direct_script_symlink_raises",
    "direct_script_symlink_succeeds",
)
STALE_MARKER = "QC_DATA_TREE_SCRIPT_EXECUTED"


def run_case(fixture, case: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"generation-root-{case}-") as directory:
        rig = fixture.rig.__wrapped__(Path(directory))
        code, data, _, _ = rig
        if case in {"summary_full", "summary_abbrev"}:
            option = "--summary-json" if case == "summary_full" else "--summary-j"
            args = ["--dry-run", option, str(code / "qc-summary.json")]
        elif case == "user_subdir_symlink":
            target = code / "qc-user"
            target.mkdir()
            user = data / "app/users/root-test"
            user.parent.mkdir(parents=True)
            user.symlink_to(target, target_is_directory=True)
            # No profile/model needed: the real workflow metrics writer is enough.
            args = ["--only-step", "framework-interpretation"]
        elif case == "html_day_symlink":
            target = code / "qc-report"
            target.mkdir()
            day_dir = data / "复盘/daily" / fixture.DAY
            day_dir.parent.mkdir(parents=True)
            day_dir.symlink_to(target, target_is_directory=True)
            good = fixture.launch(rig, "--only-step", "daily-review")
            # Rejecting all selected write destinations earlier is also safe.
            if good.returncode != 0:
                text = good.stdout + good.stderr
                return dict(case=case, returncode=good.returncode,
                            changed_code_files=[], stale_code_executed=False,
                            root_diagnostic="CODE_ROOT" in text,
                            passed="CODE_ROOT" in text and not list(target.iterdir()))
            args = ["--only-step", "daily-review-html"]
        elif case == "quality_state_symlink":
            target = code / "qc-quality"
            target.mkdir()
            state = data / "skills/daily-full-review/state"
            state.parent.mkdir(parents=True)
            state.symlink_to(target, target_is_directory=True)
            args = ["--only-step", "daily-review"]
        elif case.startswith("direct_script_symlink_"):
            target = data / "scripts/render_daily_review_briefing.py"
            if case.endswith("raises"):
                target.write_text(f"raise RuntimeError({STALE_MARKER!r})\n", encoding="utf-8")
            else:
                target.write_text(f"print({STALE_MARKER!r})\n", encoding="utf-8")
            script = code / "scripts/render_daily_review_briefing.py"
            script.unlink()
            script.symlink_to(target)
            args = ["--only-step", "daily-review-html"]
        else:
            raise ValueError(case)
        before = fixture.inventory(code)
        result = fixture.launch(rig, *args)
        after = fixture.inventory(code)
        changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
        text = result.stdout + result.stderr
        stale_executed = STALE_MARKER in text
        # These are all invalid configurations. Success must mean explicit refusal
        # before code-tree writes / wrong-code execution, not incidental failure.
        root_diagnostic = "CODE_ROOT" in text
        argument_rejected = case == "summary_abbrev" and "unrecognized arguments" in text
        refused = result.returncode != 0 and (root_diagnostic or argument_rejected)
        return dict(case=case, returncode=result.returncode, changed_code_files=changed,
                    stale_code_executed=stale_executed, root_diagnostic=root_diagnostic,
                    argument_rejected=argument_rejected,
                    passed=refused and not changed and not stale_executed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        repo = args.repo.resolve(strict=True)
        spec = importlib.util.spec_from_file_location(
            "generation_root_fixture", repo / "tests/test_generation_code_root.py",
        )
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        # Preserve tools and real HOME for local Python; rig overrides HOME with a
        # temporary directory in every executed child. Do not propagate secrets.
        keep = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
        os.environ.clear()
        os.environ.update(keep)
        results = [run_case(fixture, case) for case in CASES]
        revision = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True,
        ).strip()
        report = dict(revision=revision, interpreter=sys.executable,
                      fixture="temporary SQL/quality fixture; real CLI/runner/writers",
                      cases=results, passed=sum(item["passed"] for item in results),
                      failed=sum(not item["passed"] for item in results))
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        print(output, end="")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        return 1 if report["failed"] else 0
    except (OSError, ValueError, ImportError, AttributeError, subprocess.SubprocessError) as exc:
        print(f"generation boundary probe unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
