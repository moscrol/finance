"""Model-free stdin bridge for the opt-in Pi history review adapter.

No database, credential, network, or user-ledger access. The host owns the
already-delivered source packets and the reviewer response.
"""
from __future__ import annotations

import argparse
import json
import sys

from intelligence.services.history_answer_review import (
    build_history_review, build_nonfactual_audit, combine_history_reviews,
    review_messages, validate_history_review, history_review_batches,
    accept_history_batches, build_completeness_review, accept_completeness_review,
)

MAX_BYTES = 512 * 1024


def handle(action: str, value: dict) -> dict:
    if action == "prepare":
        request = build_history_review(value["question"], value["draft"], value["sources"])
        return {"request": request, "messages": review_messages(request),
                "batch_count": len(history_review_batches(request))}
    if action == "batch":
        index = value["index"]
        batches = history_review_batches(value["request"])
        if type(index) is not int or not 0 <= index < len(batches):
            raise ValueError("invalid history batch index")
        batch = batches[index]
        return {"request": batch, "messages": review_messages(batch)}
    if action == "accept_batches":
        verdict = accept_history_batches(value["request"], value["responses"])
        completion = build_completeness_review(value["request"]) if verdict["status"] == "pending_completeness" else None
        return {"verdict": verdict, "completion": {"request": completion, "messages": review_messages(completion)} if completion else None}
    if action == "complete":
        verdict = accept_completeness_review(value["request"], value["first"], value["response"])
        audit = build_nonfactual_audit(value["request"], verdict) if verdict["status"] == "reviewed" else None
        return {"verdict": verdict, "audit": {"request": audit, "messages": review_messages(audit)} if audit else None}
    if action == "accept":
        verdict = validate_history_review(value["request"], value["response"])
        audit = build_nonfactual_audit(value["request"], verdict) if verdict["status"] == "reviewed" else None
        return {"verdict": verdict, "audit": {"request": audit, "messages": review_messages(audit)} if audit else None}
    if action == "audit":
        second = validate_history_review(value["audit_request"], value["response"])
        return {"verdict": combine_history_reviews(value["first"], value["audit_request"], second)}
    raise ValueError("unknown history review action")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "accept", "audit", "accept_batches", "complete", "batch"))
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("history review input too large")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("history review input must be an object")
        output = json.dumps(handle(args.action, value), ensure_ascii=False, allow_nan=False)
        if len(output.encode()) > MAX_BYTES:
            raise ValueError("history review response too large")
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        print('{"error":"history_review_unavailable"}')
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
