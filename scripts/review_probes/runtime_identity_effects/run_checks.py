"""Run repaired K3-derived probes and verify named mutation failures.

Host-authored, not a K3 independent verdict. No candidate files are edited.
The caller must supply a clean candidate and a new, external output directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "probe"
IDENTITY_FAILURES = {
    "test_wrong_user_refused_and_nothing_is_written",
    "test_wrong_conversation_run_and_message_refused[conversation_id]",
    "test_wrong_conversation_run_and_message_refused[run_id]",
    "test_wrong_conversation_run_and_message_refused[assistant_message_id]",
    "test_malformed_episode_identity_refused_and_nothing_written",
    "test_binding_asymmetry_refuses_without_writing[bound_checkpoint]",
    "test_binding_asymmetry_refuses_without_writing[unbound_checkpoint]",
}
BUDGET_FAILURES = {
    "test_spend_gate_refuses_unreconciled_and_has_no_forgetful_default",
    "test_restore_registers_the_window_once_and_never_spends_the_balance",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(candidate: Path) -> dict[str, str]:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(candidate), *args], text=True,
            env={"PATH": os.environ["PATH"], "GIT_OPTIONAL_LOCKS": "0"}, timeout=30,
        ).strip()
    return {"revision": git("rev-parse", "HEAD"), "status": git("status", "--porcelain")}


def dump(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def junit_verdict(path: Path, expected_failures: set[str], total: int) -> dict[str, object]:
    cases = ET.parse(path).getroot().findall(".//testcase")
    errors = [c.attrib for c in cases if c.find("error") is not None]
    skipped = [c.attrib for c in cases if c.find("skipped") is not None]
    failures = {
        c.attrib["name"]: {"type": f.get("type"), "message": f.get("message"), "text": f.text}
        for c in cases if (f := c.find("failure")) is not None
    }
    valid_failure = all(
        f["message"].startswith("Failed: DID NOT RAISE ") for f in failures.values()
    )
    return {
        "collected": len(cases), "passed": len(cases) - len(failures) - len(errors) - len(skipped),
        "failures": failures, "errors": errors, "skipped": skipped,
        "accepted": len(cases) == total and not errors and not skipped
        and set(failures) == expected_failures and valid_failure,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate, output = args.candidate.resolve(), args.output.resolve()
    if output.is_relative_to(candidate) or candidate.is_relative_to(output):
        parser.error("output must be external to the candidate tree")
    before = identity(candidate)
    if before != {"revision": args.expect_revision, "status": ""}:
        parser.error(f"candidate is not the expected clean revision: {before}")
    output.mkdir(parents=True, exist_ok=False)
    watched = [Path(__file__).resolve(), *sorted(PROBE.glob("*.py"))]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in watched}
    dump(output / "inputs.json", {"candidate": str(candidate), "identity": before, "sha256": hashes})
    all_probes = [PROBE / "identity_checks.py", PROBE / "effects_checks.py"]
    stages = [
        ("baseline", "", all_probes, set(), 16),
        ("identity-mutant", "identity", [all_probes[0]], IDENTITY_FAILURES, 11),
        ("budget-mutant", "budget", [all_probes[1]], BUDGET_FAILURES, 5),
        ("restored-baseline", "", all_probes, set(), 16),
    ]
    results = []
    for label, mutation, targets, expected_failures, total in stages:
        out = output / label
        out.mkdir()
        for name in ("users", "tmp"):
            (out / name).mkdir()
        env = {
            "HOME": str(out), "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C.UTF-8",
            "PYTHONPATH": str(candidate), "PYTHONDONTWRITEBYTECODE": "1",
            "K3_CANDIDATE": str(candidate), "K3_MUTATION": mutation,
            "FORESIGHT_USERS_DIR": str(out / "users"), "FWP_TEST_RECEIPT": "0",
            "GIT_OPTIONAL_LOCKS": "0", "TMPDIR": str(out / "tmp"),
        }
        wrapper = (
            "import sys\nfrom pathlib import Path\nimport intelligence.userspace as u\n"
            f"u.USERS_DIR = Path({str(out / 'users')!r})\n"
            "import pytest\nraise SystemExit(pytest.main(sys.argv[1:]))\n"
        )
        (out / "entry.py").write_text(wrapper)
        command = [
            sys.executable, "-B", str(out / "entry.py"), "-q", "-p", "no:cacheprovider",
            "--basetemp=" + str(out / "pytest"), "--junitxml=" + str(out / "junit.xml"),
            *map(str, targets),
        ]
        start = time.monotonic()
        record = {"label": label, "command": command, "env": env,
                  "started_at": datetime.now(timezone.utc).isoformat()}
        with (out / "output.log").open("xb") as log:
            try:
                run = subprocess.run(
                    command, cwd=candidate, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=log, timeout=120,
                )
                record["exit_code"] = run.returncode
            except (subprocess.TimeoutExpired, OSError) as error:
                record.update(exit_code=None, execution_error=type(error).__name__)
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        try:
            record["junit"] = junit_verdict(out / "junit.xml", expected_failures, total)
        except (OSError, ET.ParseError, KeyError, AttributeError) as error:
            record["junit"] = {"accepted": False, "parse_error": str(error)}
        record["accepted"] = record["exit_code"] == (1 if expected_failures else 0) and record["junit"]["accepted"]
        record["output_sha256"] = sha(out / "output.log")
        dump(out / "execution.json", record)
        results.append(record)
        print(json.dumps({"stage": label, "exit_code": record["exit_code"], "accepted": record["accepted"]}), flush=True)
    after = identity(candidate)
    hashes_after = {str(p.relative_to(ROOT)): sha(p) for p in watched}
    accepted = all(r["accepted"] for r in results) and before == after and hashes == hashes_after
    dump(output / "receipt.json", {
        "author": "host-repaired K3-derived probes; not K3 independent acceptance",
        "before": before, "after": after, "source_hashes": hashes,
        "candidate_unchanged": before == after, "probes_unchanged": hashes == hashes_after,
        "accepted": accepted, "results": results,
    })
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
