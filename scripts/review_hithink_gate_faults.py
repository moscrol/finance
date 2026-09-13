"""Review-only reproducer for Git-status fail-open and failed report fallback.

Run against a clean disposable checkout of 48242bd4 (not a shared working tree).
The script temporarily creates one untracked marker and removes it in finally.
No production DB is opened by default. Optional --source-db/--parquet replay
against an explicit archived snapshot; all writes remain in a new output dir.
JSON describes observed behavior; this is diagnostic evidence, not a PASS gate.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--output-base", type=Path, required=True)
    ap.add_argument("--source-db", type=Path)
    ap.add_argument("--parquet", type=Path)
    args = ap.parse_args()
    tree = args.tree.resolve()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=tree, text=True):
        ap.error("target checkout must start clean")
    args.output_base.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="gate-qc-", dir=args.output_base.resolve()))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tree, text=True).strip()
    cmd = [sys.executable, str(tree / "scripts/reconcile_hithink_gate.py"),
           "--expect-revision", head]

    collision = out / "not-a-directory"
    collision.write_text("review fixture\n")
    p = subprocess.run([*cmd, "--output-base", str(collision)], cwd=tree,
                       text=True, capture_output=True, timeout=30)
    (out / "collision.stderr").write_text(p.stderr)
    (out / "collision.stdout").write_text(p.stdout)
    result = {"revision": head, "output_collision": {
        "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr}}

    index = out / "corrupt-index"
    index.write_bytes(b"not a git index\n")
    # mkstemp avoids overwriting another agent's artifact.
    fd, name = tempfile.mkstemp(prefix="review-dirty-", suffix=".txt", dir=tree)
    os.close(fd)
    marker = Path(name)
    try:
        actual = subprocess.check_output(["git", "status", "--porcelain"],
                                         cwd=tree, text=True)
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        status = subprocess.run(["git", "status", "--porcelain"], cwd=tree,
                                env=env, text=True, capture_output=True, timeout=30)
        source = args.source_db.resolve() if args.source_db else out / "absent.duckdb"
        invocation = [*cmd, "--source-db", str(source), "--output-base", str(out / "run")]
        if args.parquet:
            invocation.extend(["--parquet", str(args.parquet.resolve())])
        p = subprocess.run(invocation, cwd=tree, env=env, text=True,
                           capture_output=True, timeout=3600)
        (out / "git-index.stdout").write_text(p.stdout)
        (out / "git-index.stderr").write_text(p.stderr)
        result["git_status_error"] = {
            "actual_status": actual, "git_rc": status.returncode,
            "git_stdout": status.stdout, "git_stderr": status.stderr,
            "gate_rc": p.returncode, "gate_stdout": p.stdout,
        }
    finally:
        marker.unlink()
    (out / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(out / "results.json")


if __name__ == "__main__":
    main()
