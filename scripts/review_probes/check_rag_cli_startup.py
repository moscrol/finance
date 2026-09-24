"""Compare RAG CLI snapshots without mistaking faster help for runtime health.

Copies only CLI/RAG code into a new private output directory. All indexes and
access logs belong to those copies. Uses hash embeddings and synthetic pages;
never uses the caller's model, index, vault, credentials, or production worker.
A passing experiment is not deployment approval: broken imports can still pass
lazy help. Preserve the receipt and raw outputs, including failed commands.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from intelligence.services.kb_rag import probe_rag_cli  # noqa: E402

CODE_PATHS = ("scripts/rag_index.py", "skills/lib/rag", "skills/lib/repo_paths.py", "skills/lib/access_log.py")
GUARD = '''import os, socket, sys, time

def deny_network(*args, **kwargs):
    raise RuntimeError("network forbidden in startup experiment")
socket.socket.connect = deny_network
socket.create_connection = deny_network

class ImportFault:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "rag.retrieval":
            mode = os.environ.get("STARTUP_IMPORT_FAULT")
            if mode == "delay":
                time.sleep(6)
            elif mode == "broken":
                raise ImportError("injected retrieval import failure")
sys.meta_path.insert(0, ImportFault())
'''


def inventory(root: Path) -> dict[str, str]:
    files = []
    for relative in CODE_PATHS:
        path = root / relative
        files.extend(path.rglob("*.py") if path.is_dir() else [path])
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


@contextmanager
def environment(env):
    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def run(argv, cwd, env, out, label, *, timeout=5, stdin=None):
    started = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, input=stdin, capture_output=True,
                              text=True, timeout=timeout, check=False)
        code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = None, exc.stdout or "", exc.stderr or ""
        timed_out = True
    elapsed = round((time.monotonic() - started) * 1000, 3)
    hashes = {}
    for suffix, text in (("stdout", stdout), ("stderr", stderr)):
        data = text.encode() if isinstance(text, str) else text
        (out / f"{label}.{suffix}").write_bytes(data)
        hashes[suffix] = hashlib.sha256(data).hexdigest()
    return {"label": label, "argv": list(map(str, argv)), "exit_code": code,
            "elapsed_ms": elapsed, "timeout": timed_out, "output_sha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()
    if not 2 <= args.samples <= 50:
        parser.error("--samples must be between 2 and 50")
    sources = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    out = args.output_dir.resolve()
    if out.exists() or any(out.is_relative_to(root) for root in sources.values()):
        parser.error("output must be new and outside both source snapshots")
    os.umask(0o077)
    finance_paths = (
        Path(__file__), REPO / "scripts/rag_query_worker.py",
        REPO / "intelligence/services/kb_rag.py", REPO / "intelligence/services/kb_code_identity.py",
    )
    finance_hashes = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in finance_paths}
    before = {name: inventory(root) for name, root in sources.items()}
    out.mkdir(parents=True, mode=0o700)
    guard = out / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(GUARD)
    setups = {}
    copied = {}
    for name, source in sources.items():
        code = out / name
        for relative in CODE_PATHS:
            src, dst = source / relative, code / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(src, dst)
        copied[name] = inventory(code)
        wiki = code / "wiki"
        (wiki / "concepts").mkdir(parents=True)
        (wiki / "concepts/alpha.md").write_text("# Alpha\n\nalpha order confirmed.\n")
        home = out / f"{name}-home"
        home.mkdir()
        env = {"PATH": os.defpath, "HOME": str(home), "PYTHONPATH": str(guard),
               "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "KB_VAULT": str(wiki), "RAG_INDEX_DIR": str(code / "index"),
               "KB_RAG_CODE_ROOT": str(code), "KB_RAG_PYTHON": args.python,
               "RAG_MODEL": "hash", "KB_ACCESS_LOG_PATH": str(code / "access.jsonl"),
               "RAG_WORKER_KEEPALIVE_SECONDS": "0", "HF_HUB_OFFLINE": "1",
               "TRANSFORMERS_OFFLINE": "1"}
        setups[name] = code, env
    commands, probes, checks = [], {}, {}
    for i in range(args.samples):
        for name in (sources if i % 2 == 0 else reversed(sources)):
            code, env = setups[name]
            commands.append(run([args.python, str(code / "scripts/rag_index.py"), "query", "--help"],
                                code, env, out, f"{name}-help-{i}"))
    for name, (code, env) in setups.items():
        cli = [args.python, str(code / "scripts/rag_index.py")]
        for fault in ("none", "delay", "broken"):
            faulty = {**env, "STARTUP_IMPORT_FAULT": fault}
            with environment(faulty):
                probes[f"{name}-{fault}"] = probe_rag_cli(code / "wiki").to_dict()
            if fault == "broken":
                commands.append(run([*cli, "query", "alpha", "--mode", "bm25", "--json"],
                                    code, faulty, out, f"{name}-broken-query"))
        commands.append(run([*cli, "build", "--model", "hash"], code, env, out, f"{name}-build", timeout=30))
        for mode in ("bm25", "hybrid"):
            query = ["query", "alpha", "--model", "hash", "--mode", mode, "--json"]
            label = f"{name}-{mode}-cli"
            commands.append(run([*cli, *query], code, env, out, label, timeout=30))
            requests = "".join(json.dumps({"id": str(i), "argv": query}) + "\n" for i in range(2))
            worker_label = f"{name}-{mode}-worker"
            commands.append(run([args.python, str(REPO / "scripts/rag_query_worker.py"),
                                 "--kb-root", str(code), "--index-dir", env["RAG_INDEX_DIR"]],
                                code, env, out, worker_label, timeout=30, stdin=requests))
            try:
                cli_payload = json.loads((out / f"{label}.stdout").read_text())
                cli_hits = cli_payload.get("hits", []) if isinstance(cli_payload, dict) else cli_payload
                rows = [json.loads(line) for line in (out / f"{worker_label}.stdout").read_text().splitlines()]
                worker_hits = [json.loads(row["stdout"]) for row in rows]
                worker_hits = [p.get("hits", []) if isinstance(p, dict) else p for p in worker_hits]
                checks[worker_label] = (
                    len(rows) == 2 and [row["id"] for row in rows] == ["0", "1"]
                    and all(row["returncode"] == 0 and row["model_load_count"] == 1 for row in rows)
                    and bool(cli_hits) and all([h["page_id"] for h in hits] == [h["page_id"] for h in cli_hits]
                                              for hits in worker_hits)
                )
            except (ValueError, KeyError, TypeError):
                checks[worker_label] = False
    checks["finance_sources_unchanged"] = finance_hashes == {
        str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in finance_paths
    }
    checks["source_unchanged"] = before == {name: inventory(root) for name, root in sources.items()}
    checks["copies_match_sources"] = copied == before
    checks["copies_unchanged"] = copied == {name: inventory(code) for name, (code, _) in setups.items()}
    checks["normal_probes_compatible"] = all(probes[f"{name}-none"]["query_protocol_compatible"] for name in sources)
    checks["baseline_delay_detected"] = probes["baseline-delay"]["failure_kind"] == "timeout"
    checks["candidate_delay_bypassed"] = probes["candidate-delay"]["query_protocol_compatible"]
    checks["baseline_broken_detected"] = probes["baseline-broken"]["failure_kind"] == "nonzero_exit"
    checks["candidate_help_masks_broken_runtime"] = probes["candidate-broken"]["query_protocol_compatible"]
    checks["query_import_fault_exercised"] = all(
        "injected retrieval import failure" in (out / f"{name}-broken-query.stderr").read_text()
        for name in sources
    )
    checks["command_results"] = all(
        c["exit_code"] not in (None, 0) if c["label"].endswith("broken-query") else c["exit_code"] == 0
        for c in commands
    )
    checks["help_output_unchanged"] = (out / "baseline-help-0.stdout").read_bytes() == (out / "candidate-help-0.stdout").read_bytes()
    timings = {}
    for name in sources:
        values = [c["elapsed_ms"] for c in commands if c["label"].startswith(name + "-help-")]
        timings[name] = {"n": len(values), "min_ms": min(values), "median_ms": statistics.median(values), "max_ms": max(values)}
    version = subprocess.check_output([args.python, "--version"], text=True).strip()
    receipt = {"source_roots": {k: str(v) for k, v in sources.items()}, "source_hashes": before,
               "python": args.python, "python_version": version, "finance_head": subprocess.check_output(
                   ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
               "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "finance_source_hashes": finance_hashes,
               "commands": commands, "probes": probes, "checks": checks, "timings": timings,
               "production_compatibility_verified": False, "historical_root_cause_proven": False,
               "strict_disk_cold_start": False, "deployment_authorized": False}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(out / "receipt.json"), "checks": checks, "timings": timings}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
