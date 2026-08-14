from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

from scripts.agent_review.contract import classify_legacy_records


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def bootstrap_runtime(*, repo: Path, state_root: Path) -> dict[str, object]:
    repo = repo.resolve()
    state_root = state_root.resolve()
    for directory in (
        "requests",
        "claims",
        "verdicts",
        "provisional-verdicts",
        "runs",
        "locks",
        "state",
        "worktrees",
    ):
        (state_root / directory).mkdir(parents=True, exist_ok=True)

    source_directory = Path(__file__).resolve().parent
    source_prompt = source_directory / "REVIEWER_PROMPT.md"
    source_worker = source_directory / "reviewer_worker.sh"
    runtime_prompt = state_root / "REVIEWER_PROMPT.md"
    runtime_worker = state_root / "reviewer-worker.sh"
    shutil.copy2(source_prompt, runtime_prompt)
    shutil.copy2(source_worker, runtime_worker)
    runtime_worker.chmod(0o755)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    classifications = classify_legacy_records(state_root, repo=repo, current_tip=commit)
    classification_payload = {
        review_id: {
            "state": item.state,
            "commit": item.commit,
            "reason": item.reason,
        }
        for review_id, item in classifications.items()
    }
    _atomic_json(state_root / "state/legacy-classification.json", classification_payload)
    metadata: dict[str, object] = {
        "schema_version": 1,
        "source_commit": commit,
        "files": {
            "REVIEWER_PROMPT.md": _sha256(runtime_prompt),
            "reviewer-worker.sh": _sha256(runtime_worker),
        },
        "legacy_records": len(classification_payload),
    }
    _atomic_json(state_root / "state/bootstrap-metadata.json", metadata)
    return metadata


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap agent-review runtime state")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--state-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    metadata = bootstrap_runtime(repo=args.repo, state_root=args.state_root)
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
