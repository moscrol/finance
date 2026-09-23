"""Prepare a fresh L6 controller with content-audit admission, never start it.

Hash-checked historical source is migration input only. No authorization, model
output, verdict or prerequisite receipt is inherited from the sealed batch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.review_probes.prepare_adaptive_l6 import validate_authorization
from scripts.review_probes.prepare_pi_review_repair import replace_once

ARCHIVE = Path(__file__).resolve().parents[2] / "docs/verification/2026-09-23-glm-qc-and-l6/l6"
FILES = ("run_live_l6.py", "glm_l6_shim.py", "check_proxy_offline.py", "launcher-exports.sh")


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
