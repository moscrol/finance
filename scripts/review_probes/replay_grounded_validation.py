"""Replay saved composer drafts without retrieval, generation or a model judge.

Prevents counting newly generated answers or template supplements as conclusions
retained by a validator fix. Binds the exact source and input bytes, preserves the
original artifacts and refuses to overwrite an output. Exit 0 means replayed,
NOT quality passed or publicly delivered. Run separately against each clean code
root, then compare only rows with identical input_sha256.

Usage: python scripts/review_probes/replay_grounded_validation.py
    --code-root WORKTREE --expect-revision SHA --run-dir RUN [--run-dir RUN ...]
    --output NEW_JSON
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


SOURCES = (
    "intelligence/services/answer_model.py",
    "intelligence/eval/grounded_replay.py",
)
INPUTS = ("run.json", "answer_spec.json", "grounded_composer_shadow.json")


def _identity(root: Path) -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    return {
        "code_root": str(root),
        "revision": git("rev-parse", "HEAD"),
        "status": git("status", "--porcelain"),
        "source_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in SOURCES
        },
    }


def _replay_run(run: Path, model, decode_spec) -> dict:
    # Hash and parse the same reads, not files reread after validation.
    original = {name: (run / name).read_bytes() for name in INPUTS}
    record = json.loads(original["run.json"])
    question = record.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("run question is required; do not silently replay without date anchors")
    shadow = json.loads(original["grounded_composer_shadow.json"])
    raw = shadow.get("raw_answer")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("run has no composer draft; templates and Episode answers are not drafts")
    payload = json.loads(original["answer_spec.json"])
    normalizations = []
    # Some historical AnswerSpecs serialize null; the existing parser wants str.
    if payload["research_spec"].get("company_scope") is None:
        payload["research_spec"]["company_scope"] = "-"
        normalizations.append("research_spec.company_scope:null-or-missing->dash")
    spec = decode_spec(payload)
    canonical = model.rebind_entity_claim_ids(
        model.canonicalize_grounded_claim_ids(raw, spec), spec,
    )
    errors = [issue for issue in model.validate_grounded_composer_answer(
        canonical, spec, question=question,
    ) if issue.severity == "error"]
    repaired = model.repair_grounded_composer_answer(
        canonical, spec, drop_invalid=True, question=question,
    ) if errors else canonical
    raw_body = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    repaired_body = re.sub(r"<!--.*?-->", "", repaired or "", flags=re.DOTALL)
    if any((run / name).read_bytes() != data for name, data in original.items()):
        raise RuntimeError("input_changed_during_replay")
    return {
        "run_id": record.get("run_id", run.name),
        "run_dir": str(run), "question": question,
        "input_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in original.items()},
        "normalizations": normalizations,
        "raw_chars": len(raw_body), "repaired_chars": len(repaired_body),
        "errors": [{"code": issue.code, "message": issue.message} for issue in errors],
        "canonical_answer": canonical, "repaired_answer": repaired,
        "repaired_body": repaired_body,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", required=True, type=Path)
    parser.add_argument("--expect-revision")
    parser.add_argument("--run-dir", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.code_root.expanduser().resolve()
    try:
        if args.output.exists():
            raise FileExistsError("output_exists")
        before = _identity(root)
        if before["status"]:
            raise ValueError("target_must_be_clean")
        if args.expect_revision and before["revision"] != args.expect_revision:
            raise ValueError("target_revision_mismatch")
        sys.path.insert(0, str(root))
        from intelligence.services import answer_model as model
        from intelligence.eval import grounded_replay as replay

        for module, name in zip((model, replay), SOURCES):
            if Path(module.__file__).resolve() != (root / name).resolve():
                raise RuntimeError("import_root_mismatch")
        rows = [_replay_run(run.expanduser().resolve(), model, replay.answer_spec_from_payload)
                for run in args.run_dir]
        after = _identity(root)
        if before != after:
            raise RuntimeError("target_changed_during_replay")
        report = {
            "status": "replayed_not_quality_acceptance", "model_calls": 0,
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "before": before, "after": after, "rows": rows,
        }
        with args.output.open("x", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"replay-grounded-validation: {exc}", file=sys.stderr)
        return 2
    print(f"Replayed {len(rows)} frozen drafts; this is not quality acceptance: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
