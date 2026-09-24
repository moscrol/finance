"""Measure overlapping help probes without weakening import-failure coverage.

Compare a pinned finance revision with the working candidate, using identical
copied KB code and its explicit interpreter. Only help is executed, with a
sanitized environment and the startup experiment's network/import guard.
Synthetic concurrent bursts are not evidence of production traffic or latency.
Outputs are private, immutable-by-convention receipts; existing output is refused.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from threading import Barrier, Lock
import time
from types import ModuleType
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from intelligence.services import kb_rag  # noqa: E402
from scripts.review_probes.check_rag_cli_startup import (  # noqa: E402
    CODE_PATHS, GUARD, environment, inventory,
)


def load_baseline(revision: str) -> tuple[ModuleType, str, str]:
    commit = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "--verify", revision + "^{commit}"], text=True,
    ).strip()
    source = subprocess.check_output([
        "git", "-C", str(REPO), "show", f"{commit}:intelligence/services/kb_rag.py",
    ])
    name = "_rag_probe_comparison_baseline"
    module = ModuleType(name)
    module.__file__ = str(REPO / "intelligence/services/kb_rag.py")
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module, commit, hashlib.sha256(source).hexdigest()


def burst(probe, wiki: Path, concurrency: int) -> dict:
    barrier = Barrier(concurrency)
    lock = Lock()
    children = []
    original = subprocess.Popen

    def launch(*args, **kwargs):
        child = original(*args, **kwargs)
        with lock:
            children.append(child)
        return child

    def invoke():
        barrier.wait(timeout=10)
        return probe(wiki).to_dict()

    started = time.monotonic()
    with patch.object(subprocess, "Popen", side_effect=launch):
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(invoke) for _ in range(concurrency)]
            results = [future.result(timeout=15) for future in futures]
    return {
        "concurrency": concurrency,
        "child_count": len(children),
        "all_children_reaped": all(p.returncode is not None for p in children),
        "wall_ms": round((time.monotonic() - started) * 1000, 3),
        "probes": results,
    }


def summarize(rows: list[dict]) -> dict:
    values = [row["wall_ms"] for row in rows]
    return {
        "n": len(rows), "min_ms": min(values), "median_ms": statistics.median(values),
        "max_ms": max(values), "child_counts": [row["child_count"] for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--kb-code-root", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    if not 2 <= args.samples <= 30 or not 2 <= args.concurrency <= 16:
        parser.error("samples must be 2..30; concurrency must be 2..16")
    source, out = args.kb_code_root.resolve(), args.output_dir.resolve()
    if out.exists() or out.is_relative_to(source):
        parser.error("output must be new and outside the KB source")
    os.umask(0o077)
    baseline, commit, baseline_sha = load_baseline(args.baseline_revision)
    before = inventory(source)
    tracked = [Path(__file__), REPO / "scripts/review_probes/check_rag_cli_startup.py",
               REPO / "intelligence/services/kb_rag.py", REPO / "intelligence/services/kb_code_identity.py",
               REPO / "intelligence/services/rag_worker.py"]
    finance_hashes = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    out.mkdir(parents=True, mode=0o700)
    code, home, guard = out / "kb", out / "home", out / "guard"
    for relative in CODE_PATHS:
        src, dst = source / relative, code / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
    home.mkdir()
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(GUARD)
    env = {
        "PATH": os.defpath, "HOME": str(home), "PYTHONPATH": str(guard),
        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "KB_RAG_CODE_ROOT": str(code), "KB_RAG_PYTHON": args.python,
        "KB_VAULT": str(code / "wiki"), "RAG_INDEX_DIR": str(code / "index"),
        "RAG_MODEL": "hash", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    }
    probes = {"baseline": baseline.probe_rag_cli, "candidate": kb_rag.probe_rag_cli}
    rows = []
    with environment(env):
        for i in range(args.samples):
            for name in (probes if i % 2 == 0 else reversed(probes)):
                for count in (1, args.concurrency):
                    row = {"arm": name, "sample": i, "fault": "none",
                           **burst(probes[name], code / "wiki", count)}
                    rows.append(row)
                    (out / f"{name}-{i}-{count}.json").write_text(json.dumps(row, indent=2) + "\n")
        for fault in ("broken", "delay"):
            os.environ["STARTUP_IMPORT_FAULT"] = fault
            for name, probe in probes.items():
                row = {"arm": name, "fault": fault, **burst(probe, code / "wiki", args.concurrency)}
                rows.append(row)
                (out / f"{name}-{fault}.json").write_text(json.dumps(row, indent=2) + "\n")
    checks = {
        "normal_help_compatible": all(
            p["query_protocol_compatible"] for r in rows if r["fault"] == "none" for p in r["probes"]
        ),
        "import_fault_preserved": all(
            p["failure_kind"] == {"broken": "nonzero_exit", "delay": "timeout"}[r["fault"]]
            for r in rows if r["fault"] != "none" for p in r["probes"]
        ),
        "baseline_spawns_per_call": all(r["child_count"] == r["concurrency"] for r in rows if r["arm"] == "baseline"),
        "candidate_single_flight": all(r["child_count"] == 1 for r in rows if r["arm"] == "candidate"),
        "children_reaped": all(r["all_children_reaped"] for r in rows),
        "no_completed_cache": not kb_rag._PROBE_FLIGHTS,
        "source_and_copy_unchanged": before == inventory(source) == inventory(code),
        "finance_sources_unchanged": finance_hashes == {
            str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked
        },
    }
    timings = {f"{arm}-{count}": summarize([
        r for r in rows if r["arm"] == arm and r["concurrency"] == count and r["fault"] == "none"
    ]) for arm in probes for count in (1, args.concurrency)}
    receipt = {
        "baseline_commit": commit, "baseline_module_sha256": baseline_sha,
        "finance_head": subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
        "finance_source_hashes": finance_hashes, "kb_source_root": str(source), "kb_source_hashes": before,
        "python": args.python, "python_version": subprocess.check_output([args.python, "--version"], text=True).strip(),
        "rows": rows, "checks": checks, "timings": timings,
        "production_concurrency_measured": False, "historical_timeout_fixed": False,
        "production_quality_verified": False, "deployment_authorized": False,
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"checks": checks, "timings": timings, "receipt": str(out / "receipt.json")}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
