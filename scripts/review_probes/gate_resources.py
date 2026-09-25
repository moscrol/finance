"""Observe local gate admission without killing or reserving another owner's work.

Match pytest by executable/module, not by optional reporting flags. This is a
point-in-time observation, not a machine-wide lock. Recheck before every leaf.
Only explicit owned process groups may be excluded during monitoring.
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

GIB = 1024**3


def is_pytest_process(executable: str, command: str) -> bool:
    name = Path(executable).name.lower()
    if re.fullmatch(r"py(?:test|\.test)(?:-?[0-9.]+)?", name):
        return True
    if not re.fullmatch(r"python(?:[0-9.]+)?", name):
        return False
    try:
        args = shlex.split(command)
    except ValueError:
        # ps is not an argv transport; ambiguous Python output must not fail open.
        return "pytest" in command or "py.test" in command
    skip_value = False
    for index, arg in enumerate(args[1:], 1):
        if skip_value:
            skip_value = False
            continue
        if arg in {"-W", "-X", "--check-hash-based-pycs"}:
            skip_value = True
            continue
        if arg == "-m":
            return index + 1 < len(args) and args[index + 1] == "pytest"
        if arg.startswith("-m"):
            return arg == "-mpytest"
        if arg.startswith("-c"):
            return False
        if not arg.startswith("-"):
            return bool(re.fullmatch(r"py(?:test|\.test)(?:-?[0-9.]+|\.py)?", Path(arg).name))
    return False


def pytest_processes(snapshot: str, *, excluded_groups: frozenset[int] = frozenset()) -> list[dict]:
    found = []
    for line in snapshot.splitlines():
        if not line.strip():
            continue
        parts = line.split(None, 4)
        if len(parts) != 5:
            raise ValueError("incomplete process snapshot")
        pid, group, state, executable, command = parts
        pid, group = int(pid), int(group)
        if "Z" in state or group in excluded_groups:
            continue
        if is_pytest_process(executable, command):
            found.append({"pid": pid, "pgid": group, "command": command})
    return found


def decision(snapshot: str, disk_free: int, *, minimum_free: int = 12 * GIB,
             excluded_groups: frozenset[int] = frozenset()) -> dict:
    foreign = pytest_processes(snapshot, excluded_groups=excluded_groups)
    return {"admitted": not foreign and disk_free >= minimum_free,
            "foreign_pytest": foreign, "disk_free_bytes": disk_free,
            "minimum_free_bytes": minimum_free, "excluded_groups": sorted(excluded_groups),
            "scope": "point-in-time; all detected pytest processes, not just full suites; no reservation"}


def observe(path: Path, *, minimum_free: int = 12 * GIB,
            excluded_groups: frozenset[int] = frozenset()) -> dict:
    snapshot = subprocess.check_output(
        ["ps", "-ww", "-axo", "pid=,pgid=,stat=,ucomm=,args="], text=True, timeout=10)
    result = decision(snapshot, shutil.disk_usage(path).free,
                      minimum_free=minimum_free, excluded_groups=excluded_groups)
    result["observed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--minimum-gib", type=int, default=12)
    parser.add_argument("--exclude-pgid", type=int, action="append", default=[])
    args = parser.parse_args()
    if args.minimum_gib <= 0 or any(group <= 0 for group in args.exclude_pgid):
        parser.error("minimum and process groups must be positive")
    try:
        result = observe(args.path, minimum_free=args.minimum_gib * GIB,
                         excluded_groups=frozenset(args.exclude_pgid))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result = {"admitted": False, "error": str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["admitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
