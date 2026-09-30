#!/usr/bin/env python3
"""Development entry point. doctor is read-only; bootstrap requires --install.

Smoke runs a bounded, synthetic research example, not live acceptance or a merge
 gate. It uses a temporary home/data root and blocks Python network connections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from code_map import collect_status
from workspace_env import git, load_spec, python_path

ROOT = Path(__file__).resolve().parents[1]


def locked_packages(path: Path, seen: set[Path] | None = None) -> dict[str, str]:
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        raise ValueError(f"cyclic lock include: {path.name}")
    seen.add(path)
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            entries = locked_packages(path.parent / line[3:].strip(), seen)
        else:
            name, sep, version = line.partition("==")
            if not sep or not name or not version or any(c in line for c in ";<> []"):
                raise ValueError(f"expected an exact pin: {line}")
            entries = {name: version}
        for name, version in entries.items():
            if name in pins and pins[name] != version:
                raise ValueError(f"conflicting pin: {name}")
            pins[name] = version
    seen.remove(path)
    return pins


def probe_python(python: Path, pins: dict[str, str], modules: list[str]) -> dict:
    code = """
import importlib.metadata as md, importlib.util, json, platform, sys
pins, modules = json.loads(sys.argv[1])
versions = {}
for name in pins:
    try:
        versions[name] = md.version(name)
    except md.PackageNotFoundError:
        versions[name] = None
print(json.dumps(dict(python=platform.python_version(), executable=sys.executable,
    versions=versions, missing_modules=[m for m in modules if importlib.util.find_spec(m) is None])))
"""
    proc = subprocess.run(
        [str(python), "-I", "-c", code, json.dumps([pins, modules])],
        text=True, capture_output=True, check=True, timeout=30,
    )
    return json.loads(proc.stdout)


def map_sources(root: Path) -> list[dict]:
    manifest = json.loads((root / "docs/agent-maps.json").read_text(encoding="utf-8"))
    roots = {
        "repo": root,
        "agent-memory": Path(os.environ.get("FWP_AGENT_MEMORY", str(root / ".agent-memory"))).expanduser(),
        "harness-reference": Path(os.environ.get("FWP_HARNESS_REFERENCE", str(Path.home() / "harness-reference"))).expanduser(),
    }
    rows = []
    for item in manifest["maps"]:
        row = dict(id=item["id"], source=item["source"], validation="not_run")
        owner = roots[item["repo"]]
        try:
            ref = item.get("ref")
            if ref:
                content = subprocess.run(
                    ["git", "-C", str(owner), "show", f"{ref}:{item['source']}"],
                    capture_output=True, check=True, timeout=10,
                ).stdout
                row["revision"] = git(owner, "rev-parse", ref)
            else:
                content = (owner / item["source"]).read_bytes()
                row["revision"] = git(owner, "rev-parse", "HEAD")
                row["dirty"] = bool(git(owner, "status", "--porcelain"))
            row.update(availability="present", sha256=hashlib.sha256(content).hexdigest())
        except (OSError, ValueError, subprocess.SubprocessError):
            row["availability"] = "unavailable"
        rows.append(row)
    return rows


def doctor(root: Path, *, frontend: bool = False) -> dict:
    spec = load_spec(root)
    python = python_path(root, spec)
    report = dict(
        schema_version="workspace-doctor/v1", tree=str(root),
        revision=git(root, "rev-parse", "HEAD"),
        branch=git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        dirty=bool(git(root, "status", "--porcelain")),
        interpreter=str(python), scope="offline_development", production_verified=False,
        errors=[], warnings=[],
    )
    try:
        report["baseline"] = dict(
            ref="origin/main", revision=git(root, "rev-parse", "origin/main"),
            ahead_behind=git(root, "rev-list", "--left-right", "--count", "HEAD...origin/main"),
            fetched=False,
        )
    except subprocess.SubprocessError:
        report["warnings"].append("local origin/main unavailable; GitHub baseline not verified")
    pins = locked_packages(root / spec["development_lock"])
    try:
        probe = probe_python(python, pins, spec["required_modules"])
        report["environment"] = probe
        if probe["python"] != spec["python_version"]:
            report["errors"].append(f"Python must match {spec['python_version']}")
        drift = {name: dict(expected=version, actual=probe["versions"][name])
                 for name, version in pins.items() if probe["versions"][name] != version}
        report["dependency_drift"] = drift
        if drift or probe["missing_modules"]:
            report["errors"].append("development dependencies do not match the lock")
    except (OSError, ValueError, subprocess.SubprocessError):
        report["errors"].append("configured Python is unavailable; run bootstrap --help")
    report["code_map"], _ = collect_status(root)
    if report["code_map"]["status"] != "ready":
        report["warnings"].append("code map is not ready; no architecture completeness claim")
    report["maps"] = map_sources(root)
    report["warnings"].append("map source availability is not semantic or production verification")
    if frontend:
        package = json.loads((root / "intelligence/webapp/package.json").read_text())
        expected_pnpm = package["packageManager"].split("@", 1)[1]
        for cmd, expected in ((["node", "--version"], str(spec["node_major"])),
                              (["pnpm", "--version"], expected_pnpm)):
            try:
                version = subprocess.run(cmd, capture_output=True, text=True, check=True,
                                         timeout=10).stdout.strip().lstrip("v")
                actual = version.split(".")[0] if cmd[0] == "node" else version
                if actual != expected:
                    report["errors"].append(f"{cmd[0]} expected {expected}, got {version}")
            except (OSError, subprocess.SubprocessError):
                report["errors"].append(f"{cmd[0]} unavailable")
    report["status"] = "blocked" if report["errors"] else "ready"
    return report


def bootstrap(root: Path, python: str, *, install: bool) -> int:
    spec = load_spec(root)
    target = root / ".venv-workbench"
    print(f"Target: {target}\nLock: {spec['development_lock']}", flush=True)
    if not install:
        print("Plan only. --install creates this local venv and downloads pinned dependencies.")
        return 0
    # Never upgrade a shared/existing environment, including a symlink to one.
    if target.exists() or target.is_symlink():
        raise ValueError("local venv already exists; refusing to modify it (use doctor)")
    probe = probe_python(Path(python), {}, [])
    if probe["python"] != spec["python_version"]:
        raise ValueError(f"bootstrap Python must be {spec['python_version']}")
    locked_packages(root / spec["development_lock"])
    subprocess.run([python, "-m", "venv", str(target)], check=True, timeout=90)
    local = target / "bin/python"
    subprocess.run([str(local), "-m", "pip", "install", "--disable-pip-version-check",
                    "-r", str(root / spec["development_lock"])],
                   cwd=root, check=True, timeout=600)
    subprocess.run([str(local), "-m", "pip", "check"], check=True, timeout=30)
    return 0


def smoke(root: Path) -> int:
    spec = load_spec(root)
    python = python_path(root, spec)
    tests = spec["smoke_tests"]
    with tempfile.TemporaryDirectory(prefix="fwp-smoke-") as temp:
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "TMPDIR", "SYSTEMROOT", "LANG"}}
        env.update(HOME=temp, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1",
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", FWP_TEST_RECEIPT="0",
                   FINANCE_WS=temp, MARKET_FEATURE_STORE_DB=f"{temp}/absent.duckdb",
                   KB_ROOT=f"{temp}/kb", ENTITY_ANCHOR_SECURITIES_DB="0")
        print(f"Synthetic offline smoke: {git(root, 'rev-parse', 'HEAD')}\nPython: {python}", flush=True)
        result = subprocess.run(
            [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "-p", "scripts.workspace_smoke_guard", *tests],
            cwd=root, env=env, timeout=120,
        )
        return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("doctor", help="read-only environment and map provenance")
    check.add_argument("--frontend", action="store_true")
    build = sub.add_parser("bootstrap", help="plan or install a new local Python venv")
    build.add_argument("--python", default=sys.executable, help="base Python matching the contract")
    build.add_argument("--install", action="store_true")
    sub.add_parser("smoke", help="isolated synthetic research regression, no live model/data")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            report = doctor(ROOT, frontend=args.frontend)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return int(report["status"] != "ready")
        if args.command == "bootstrap":
            return bootstrap(ROOT, args.python, install=args.install)
        return smoke(ROOT)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # Subprocess stdout/stderr can contain provider credentials. Do not dump it.
        print(f"workspace {args.command} failed: {type(exc).__name__}", file=sys.stderr)
        if isinstance(exc, (ValueError, KeyError)):
            print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
