"""Serial L6 admission: completed transport never authorizes the next question.

The runner must supply a source review for the exact immutable Episode. Missing,
late, malformed or non-PASS audits stop the batch before any next submission.
No model calls, credentials or financial-review judgments live in this module.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time
from collections.abc import Callable, Sequence

from scripts.review_probes.audit_adaptive_l6 import audit, fingerprint


def await_source_audit(
    episode_path: Path,
    review_path: Path,
    *,
    deadline: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    episode_hash = fingerprint(episode_path)
    while clock() < deadline:
        if review_path.is_file():
            review = json.loads(review_path.read_text())
            result = audit(
                json.loads(episode_path.read_text()), review,
                episode_sha256=episode_hash,
            )
            if fingerprint(episode_path) != episode_hash:
                raise ValueError("Episode changed during source review")
            if clock() >= deadline:
                break
            return result
        sleep(min(0.1, max(0.0, deadline - clock())))
    return {"verdict": "BLOCKED_SOURCE_AUDIT_TIMEOUT", "episode_sha256": episode_hash}


def run_audited_batch(
    questions: Sequence[dict],
    *,
    submit: Callable[[dict], dict],
    audit_question: Callable[[dict, dict, float], dict],
    record: Callable[[dict], None],
    audit_seconds: float = 300,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    if not math.isfinite(audit_seconds) or not 0 < audit_seconds <= 300:
        raise ValueError("source audit must have a finite window of at most 300 seconds")
    ids = [q["id"] for q in questions]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("batch must contain unique question ids")
    results: list[dict] = []
    blocker = None
    for question in questions:
        # Persist admission before the effect. No retry, prefetch or concurrent submit.
        record({"event": "submit_admitted", "question": question["id"]})
        result = submit(question)
        results.append(result)
        if result.get("status") != "completed" or result.get("delivery_pending"):
            blocker = {"question": question["id"], "reason": "run_not_completed"}
        else:
            deadline = clock() + audit_seconds
            record({"event": "awaiting_source_audit", "question": question["id"]})
            try:
                checked = audit_question(question, result, deadline)
                if clock() >= deadline:
                    checked = {"verdict": "BLOCKED_SOURCE_AUDIT_TIMEOUT"}
            except Exception as exc:
                checked = {"verdict": "BLOCKED_SOURCE_AUDIT_ERROR", "error_type": type(exc).__name__}
            result["source_audit"] = checked
            if checked.get("verdict") != "PASS":
                blocker = {"question": question["id"], "reason": checked.get("verdict") or "audit_missing_verdict"}
            record({"event": "source_audit_complete", "question": question["id"], "audit": checked})
        if blocker:
            record({"event": "batch_stopped", **blocker})
            break
    return {"results": results, "stopped_for": blocker, "all_passed": blocker is None}
