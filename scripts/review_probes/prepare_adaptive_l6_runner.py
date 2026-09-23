"""Prepare a fresh L6 controller with content-audit admission, never start it.

Hash-checked historical source is migration input only. No authorization, model
output, verdict or prerequisite receipt is inherited from the sealed batch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.review_probes.prepare_adaptive_l6 import validate_authorization
from scripts.review_probes.prepare_pi_review_repair import replace_once

ARCHIVE = Path(__file__).resolve().parents[2] / "docs/verification/2026-09-23-glm-qc-and-l6/l6"
FILES = ("run_live_l6.py", "glm_l6_shim.py", "check_proxy_offline.py", "launcher-exports.sh")


def validate_deadline_admission(receipt: dict, revision: str) -> None:
    """Recompute strict coverage and timing before admitting any live sidecar."""
    from scripts.review_probes import diagnose_llm_timeout as probe

    current = probe.source_identity()
    if (receipt.get("schema_version") != 3 or current["revision"] != revision
            or current["working_tree_status"]
            or receipt.get("source_before") != current
            or receipt.get("source_after") != current):
        raise ValueError("strict receipt is not bound to this clean candidate")
    cases = receipt.get("cases")
    expected = set(probe.SCENARIOS + probe.JUDGE_SCENARIOS)
    if (not isinstance(cases, list) or len(cases) != len(expected)
            or any(not isinstance(case, dict) or not isinstance(case.get("scenario"), str) for case in cases)
            or {case.get("scenario") for case in cases} != expected):
        raise ValueError("strict receipt must contain every scenario exactly once")
    tolerance = receipt.get("scheduling_tolerance_seconds")
    if type(tolerance) not in (float, int) or not math.isfinite(tolerance) or not 0 <= tolerance <= 0.2:
        raise ValueError("strict scheduling tolerance exceeds admission policy")
    for case in cases:
        name = case["scenario"]
        budget = (0.0 if name in {"zero_deadline", "judge_root_expired"}
                  else 1.2 if name.startswith("synthesis_stream") else 0.8)
        elapsed = case.get("wall_elapsed_seconds")
        if (type(case.get("timeout_input_seconds")) not in (float, int)
                or case["timeout_input_seconds"] != budget
                or type(elapsed) not in (float, int) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError("strict scenario budget or measurement is invalid")
    if (receipt.get("deadline_violations") != [] or receipt.get("coverage_gaps") != []
            or probe.violations(cases, tolerance) or probe.coverage_gaps(cases)):
        raise ValueError("strict receipt has deadline violations or coverage gaps")


def prepare(destination: Path, protocol: dict, archive: Path = ARCHIVE) -> dict:
    validate_authorization(protocol)
    destination = destination.resolve()
    manifest = json.loads((archive / "archive-manifest.json").read_text())
    original = Path(manifest["run_live_l6.py.txt"]["source"]).parent
    if destination.is_relative_to(archive.resolve()) or destination.is_relative_to(original):
        raise ValueError("cannot write into sealed evidence")
    inputs = {}
    for name in FILES:
        path = archive / (name + ".txt")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest[name + ".txt"]["sha256"]:
            raise ValueError(f"sealed source changed: {name}")
        inputs[name] = raw.decode().replace(str(original), str(destination))
    runner = inputs["run_live_l6.py"]
    runner = replace_once(runner, 'CANDIDATE = "31f1b40dd788d36c71da249d59fb769c50d7cd30"\n', "")
    runner = replace_once(runner, 'QUESTIONS = PROTOCOL["questions"]',
                          'QUESTIONS = PROTOCOL["questions"]\n'
                          'CANDIDATE = PROTOCOL["baseline"]["premerge_candidate_revision"]')
    runner = replace_once(runner, "    repo = args.repo.resolve()", "    repo = args.repo.resolve()\n"
                          "    import sys\n    sys.path.insert(0, str(repo))\n"
                          "    from scripts.review_probes.adaptive_l6_batch import await_source_audit, run_audited_batch\n"
                          "    from scripts.review_probes.prepare_adaptive_l6 import validate_authorization\n"
                          "    validate_authorization(PROTOCOL)")
    runner = replace_once(
        runner,
        '    assert not json.loads(Path(__file__).with_name("strict-deadline.json").read_text())["deadline_violations"]',
        '    from scripts.review_probes.prepare_adaptive_l6_runner import validate_deadline_admission\n'
        '    validate_deadline_admission(\n'
        '        json.loads(Path(__file__).with_name("strict-deadline.json").read_text()), CANDIDATE,\n'
        '    )',
    )
    runner = replace_once(
        runner,
        '    assert json.loads(Path(__file__).with_name("positive-control.json").read_text())["verdict"] == "NOT_PASSED"',
        '    regression = json.loads(Path(__file__).with_name("source-regression.json").read_text())\n'
        '    assert regression["status"] == "PASS" and regression["candidate"] == CANDIDATE',
    )
    start = runner.index("        for question in QUESTIONS:\n")
    end = runner.index("    finally:\n", start)
    runner = runner[:start] + '''        def submit(question):
            try:
                return run_question(base, out, user, question, workbench_process)
            except HTTPStatusError as exc:
                return {"id": question["id"], "status": "http_error", "http_status": exc.status}

        def content_audit(question, result, deadline):
            folder = out / question["id"]
            checked = await_source_audit(
                folder / "raw-run/continuous-episode.json", folder / "source-review.json",
                deadline=deadline,
            )
            with (folder / "source-audit.json").open("x") as stream:
                json.dump(checked, stream, ensure_ascii=False, indent=2)
            return checked

        def record_admission(event):
            with (out / "batch-admissions.jsonl").open("a") as stream:
                stream.write(json.dumps({"at": now(), **event}, ensure_ascii=False) + "\\n")
                stream.flush()
                os.fsync(stream.fileno())

        batch = run_audited_batch(
            QUESTIONS, submit=submit, audit_question=content_audit, record=record_admission,
        )
        results = batch["results"]
        stopped_for = batch["stopped_for"]
        dump(out / "batch-result.json", batch)
        if stopped_for:
            dump(out / "batch-blocker.json", stopped_for)
        dump(out / "results.json", results)
        return_code = 0 if batch["all_passed"] else 2
''' + runner[end:]
    inputs["run_live_l6.py"] = runner
    inputs["protocol-coherent.json"] = json.dumps(protocol, ensure_ascii=False, indent=2) + "\n"
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, body in inputs.items():
        with (destination / name).open("x") as stream:
            stream.write(body)
    receipt = {
        "status": "PREPARED_NOT_EXECUTED", "real_model_requests": 0,
        "receipts_inherited": False, "authorization_source": "caller protocol, validated",
        "source_archive": str(archive), "source_audit_seconds": 300,
        "next_question_requires": "exact-Episode source audit PASS within deadline",
        "inputs_sha256": {name: hashlib.sha256(body.encode()).hexdigest() for name, body in inputs.items()},
    }
    with (destination / "runner-preparation.json").open("x") as stream:
        json.dump(receipt, stream, indent=2)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    receipt = prepare(args.destination, json.loads(args.protocol.read_text()))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
