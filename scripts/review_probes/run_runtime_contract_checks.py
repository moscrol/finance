"""Replay runtime contract mutations with sandboxed effects and named witnesses.

Reuses run_extraction_mutations.py from an explicitly pinned, clean candidate.
Requires macOS sandbox-exec. Output must be new and outside the candidate;
raw failures and disposable worktrees are retained on failure. This is host
replay of pre-existing author tests, not independent K3 acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.review_probes.runtime_identity_effects.run_checks import identity, sha  # noqa: E402

PYTHON = sys.executable
PROFILE: Path
TEST_ROOT = "intelligence/tests/"
GROUPS = {
    "runtime": ("runtime_contract_mutations.json", [
        TEST_ROOT + "test_episode_persistence_failure.py",
        TEST_ROOT + "test_model_turn_completion_boundary.py",
        TEST_ROOT + "test_workbench_api.py::test_sse_emits_terminal_message_arriving_between_reads",
    ]),
    "writer": ("episode_writer_mutations.json", [TEST_ROOT + "test_episode_writer.py"]),
    "reentry": ("episode_writer_reentry_mutations.json", [TEST_ROOT + "test_episode_writer_reentry.py"]),
}


def dump(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sandbox_run(command, **kwargs):
    if "pytest" not in command:
        return subprocess.run(command, **kwargs)
    junit = Path(command[command.index("--junitxml") + 1])
    stage = junit.parent / junit.stem
    stage.mkdir()
    for name in ("tmp", "users", "home"):
        (stage / name).mkdir()
    entry = stage / "entry.py"
    entry.write_text(
        "import sys\nfrom pathlib import Path\nimport intelligence.userspace as u\n"
        f"u.USERS_DIR=Path({str(stage / 'users')!r})\n"
        "import pytest\nraise SystemExit(pytest.main(sys.argv[1:]))\n"
    )
    actual = ["/usr/bin/sandbox-exec", "-f", str(PROFILE), PYTHON, "-B", str(entry),
              *command[command.index("pytest") + 1:], "--basetemp=" + str(stage / "pytest")]
    env = {**kwargs["env"], "HOME": str(stage / "home"), "TMPDIR": str(stage / "tmp"),
           "FORESIGHT_USERS_DIR": str(stage / "users"), "FORESIGHT_LLM_KEYCHAIN": "0"}
    record = {"command": actual, "cwd": str(kwargs["cwd"]), "env": env, "timeout": 120}
    with (stage / "raw.log").open("xb") as log:
        proc = subprocess.Popen(actual, cwd=kwargs["cwd"], env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=log, start_new_session=True)
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            record["timeout_reached"] = True
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    record["exit_code"] = proc.returncode
    record["raw_sha256"] = hashlib.sha256((stage / "raw.log").read_bytes()).hexdigest()
    dump(stage / "process.json", record)
    return subprocess.CompletedProcess(actual, proc.returncode, (stage / "raw.log").read_text(), "")


def cases(path):
    root = ET.parse(path).getroot()
    result = {}
    for case in root.iter("testcase"):
        key = (case.get("classname"), case.get("name"))
        assert key not in result, ("duplicate case", key)
        result[key] = case
    return result


def validate_definitions(candidate: Path, definition_path: Path):
    mutations = json.loads(definition_path.read_text())
    if not mutations or len({m["id"] for m in mutations}) != len(mutations):
        raise ValueError("empty or duplicate mutation definitions")
    problems = []
    for mutation in mutations:
        path = (candidate / mutation["path"]).resolve()
        if not path.is_relative_to(candidate.resolve()):
            raise ValueError("mutation path escapes candidate")
        source = path.read_text()
        count = source.count(mutation["old"])
        if count != 1:
            problems.append((mutation["id"], "anchor matches", count))
            continue
        compile(source.replace(mutation["old"], mutation["new"], 1), str(path), "exec")
    if problems:
        raise ValueError(f"mutation preflight failed: {problems}")


def audit(output):
    report = json.loads((output / "results.json").read_text())
    definitions = json.loads((output / "definitions.json").read_text())
    baseline = cases(output / "baseline.xml")
    assert baseline and report["complete"] and report["final_status"] == ""
    restored = cases(output / "restored-full.xml")
    assert set(restored) == set(baseline)
    assert all(len(case) == 0 for case in [*baseline.values(), *restored.values()])
    witnesses = []
    for mutation in definitions:
        ident, targets = mutation["id"], set(mutation["targets"])
        expected = {key for key in baseline if key[1].split("[", 1)[0] in targets}
        assert {key[1].split("[", 1)[0] for key in expected} == targets
        red, green = cases(output / f"{ident}-red.xml"), cases(output / f"{ident}-green.xml")
        assert set(red) == set(green) == expected, (ident, "collection differs")
        failures = []
        for key, case in red.items():
            assert case.find("error") is None and case.find("skipped") is None
            failure = case.find("failure")
            if failure is not None:
                message = failure.get("message", "")
                assertion = message.startswith(("AssertionError:", "assert ", "Failed: DID NOT RAISE "))
                explicit_failure = ident == "tool_intent_fence" and message == "Failed: unpersisted intent reached executor"
                assert assertion or explicit_failure, (ident, key, message)
                if ident == "inbox_suspend_does_not_drain_delivery":
                    assert message == "Failed: DID NOT RAISE <class 'TimeoutError'>", (ident, "not a semantic witness", message)
                failures.append({"classname": key[0], "name": key[1], "message": message})
        assert {row["name"].split("[", 1)[0] for row in failures} == targets, ident
        assert all(len(case) == 0 for case in green.values()), ident
        witnesses.append({"mutation": ident, "collected": len(red), "failures": failures})
    return {"baseline": len(baseline), "mutations": witnesses, "accepted": True}


def main():
    global PROFILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=GROUPS, required=True)
    args = parser.parse_args()
    candidate, root = args.candidate.resolve(), args.output.resolve()
    if root.is_relative_to(candidate) or candidate.is_relative_to(root):
        parser.error("output must be external to candidate")
    before = identity(candidate)
    if before != {"revision": args.expect_revision, "status": ""}:
        parser.error(f"candidate must be clean and pinned: {before}")
    if not Path("/usr/bin/sandbox-exec").exists():
        parser.error("macOS sandbox-exec is required")
    root.mkdir(parents=True, exist_ok=False)
    scratch = root / "scratch"
    scratch.mkdir()
    PROFILE = root / "host.sb"
    PROFILE.write_text(
        '(version 1)\n(allow default)\n(deny file-write*)\n'
        f'(allow file-write* (subpath {json.dumps(str(root))}) (literal "/dev/null"))\n'
        '(deny network*)\n'
        + ''.join(
            f'(deny file-read* (subpath {json.dumps(str(Path.home() / name))}))\n'
            for name in (".claude", ".pi", ".ssh", "Library/Keychains",
                         "Library/Application Support/mirasim-sidecar")
        )
    )
    definitions, tests = GROUPS[args.group]
    output = root / "mutations"
    runner = candidate / "scripts/review_probes/run_extraction_mutations.py"
    spec = importlib.util.spec_from_file_location("committed_runner", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Only the delegated pytest subprocess is sandboxed; git creates scratch worktrees.
    module.subprocess = types.SimpleNamespace(run=sandbox_run, check_output=subprocess.check_output)
    previous_cwd, previous_argv, previous_temp = Path.cwd(), sys.argv, tempfile.tempdir
    record = {"revision": args.expect_revision, "group": args.group,
              "role": "host replay of pre-existing author tests; not K3 independent acceptance",
              "wrapper_sha256": sha(Path(__file__)), "runner_sha256": sha(runner),
              "before": before, "accepted": False}
    try:
        validate_definitions(candidate, candidate / "scripts/review_probes" / definitions)
        os.chdir(candidate)
        tempfile.tempdir = str(scratch)
        sys.argv = ["committed_runner", "--revision", args.expect_revision, "--output", str(output),
                    "--definitions", "scripts/review_probes/" + definitions, "--tests", *tests]
        module.main()
        record.update(audit(output))
    except Exception as error:
        record["error"] = repr(error)
        raise
    finally:
        os.chdir(previous_cwd)
        sys.argv, tempfile.tempdir = previous_argv, previous_temp
        record["after"] = identity(candidate)
        record["candidate_unchanged"] = before == record["after"]
        record["inputs_unchanged"] = record["wrapper_sha256"] == sha(Path(__file__)) and record["runner_sha256"] == sha(runner)
        record["accepted"] = record["accepted"] and record["candidate_unchanged"] and record["inputs_unchanged"]
        dump(root / "host-audit.json", record)
    if not record["accepted"]:
        raise RuntimeError("candidate or inputs changed during replay")
    print(json.dumps({"group": args.group, "baseline": record["baseline"], "mutations": len(record["mutations"]), "accepted": True}))


if __name__ == "__main__":
    main()
