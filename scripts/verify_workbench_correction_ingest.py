#!/usr/bin/env python3
"""Offline probe for the Workbench correction write side.

The probe uses only temporary user state and deterministic services. It does not
call a model, run research, or touch the real Workbench user root. Output keeps
case IDs, reasons, statuses, and field names only; correction prose is omitted.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence import userspace  # noqa: E402
from intelligence.runtime.conversation_orchestrator import (  # noqa: E402
    ConversationContext,
    TurnOrchestrator,
    workbench_correction_guard_reason,
)
from intelligence.services import workbench_correction_ingest  # noqa: E402
from intelligence.services.conversation_store import ConversationStore, Message  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402


def previous_answer() -> dict[str, str]:
    return {
        "message_id": "msg-answer-1",
        "role": "assistant",
        "status": "completed",
        "content": "双红后可以直接上车，但仍需结合量能和容量确认。",
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def direct_case(path: Path, text: str, previous: dict[str, str] | None, *, ts: str) -> dict[str, Any]:
    result = workbench_correction_ingest.maybe_record_workbench_correction(
        path,
        user_text=text,
        previous_assistant=previous,
        conversation_id="conv-probe",
        corrected_message_id="msg-answer-1",
        ts=ts,
    )
    return {"status": result.status, "reason": result.reason}


def verify() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="workbench-correction-") as tmp:
        root = Path(tmp)
        users_root = root / "users"
        old_users_root = os.environ.get(userspace.ENV_USERS_DIR)
        old_pytest = os.environ.pop("PYTEST_CURRENT_TEST", None)
        os.environ[userspace.ENV_USERS_DIR] = str(users_root)
        try:
            path = root / "direct" / "corrections.jsonl"
            cases = {
                "W-corr-1": direct_case(
                    path,
                    "不对，应该先看板块容量再下结论",
                    previous_answer(),
                    ts="2026-09-25T02:00:00+00:00",
                ),
                "W-corr-2": direct_case(
                    path,
                    "不对，应该先看板块容量再下结论",
                    None,
                    ts="2026-09-25T02:01:00+00:00",
                ),
                "W-corr-3": direct_case(
                    path,
                    "这波不对，应该是情绪退潮",
                    previous_answer(),
                    ts="2026-09-25T02:02:00+00:00",
                ),
                "W-corr-5": {
                    "status": "skipped",
                    "reason": workbench_correction_guard_reason("tester"),
                },
            }
            require(cases["W-corr-1"]["status"] == "recorded", "positive fixture was not recorded")
            require(cases["W-corr-2"]["reason"] == "no_prior_answer", "missing prior answer was not rejected")
            require(cases["W-corr-3"]["reason"] == "market_commentary", "market commentary was recorded")
            require(cases["W-corr-5"]["reason"] == "identity_skipped", "tester guard was not enforced")

            store = ConversationStore("default", root=root / "conversations")
            run_store = RunStore("default", root=root / "runs")
            conversation = store.create_conversation()
            run = run_store.create_run(
                "瑞华泰怎么看",
                "ask",
                session_id=conversation.conversation_id,
            )
            trace_steps: list[str] = []
            original_trace = TurnOrchestrator._trace

            def capture_trace(self, run_id, message_id, conversation_id, step_id, name, output, **kwargs):
                del self, run_id, message_id, conversation_id, name, output, kwargs
                trace_steps.append(step_id)

            TurnOrchestrator._trace = capture_trace
            try:
                orchestrator = TurnOrchestrator(
                    repo_root=root,
                    conversation_store=store,
                    run_store=run_store,
                )
                orchestrator._maybe_ingest_workbench_correction(
                    context=ConversationContext(
                        summary="",
                        recent_messages=(
                            Message(
                                message_id="msg-answer-default",
                                conversation_id=conversation.conversation_id,
                                role="assistant",
                                content="上一轮完成稿",
                                created_at="2026-09-25T01:00:00+00:00",
                                status="completed",
                            ),
                        ),
                    ),
                    query="不对，应该先看板块容量再下结论",
                    conversation_id=conversation.conversation_id,
                    run_id=run.run_id,
                    assistant_message_id="msg-new-answer",
                    warnings=[],
                )
            finally:
                TurnOrchestrator._trace = original_trace

            runtime_path = users_root / "default" / "corrections.jsonl"
            require(runtime_path.exists(), "default runtime path did not receive correction")
            runtime_record = json.loads(runtime_path.read_text(encoding="utf-8").splitlines()[0])
            required_fields = {
                "source",
                "conversation_id",
                "corrected_message_id",
                "plane",
            }
            require(required_fields <= runtime_record.keys(), "runtime provenance fields are incomplete")
            require(trace_steps == ["user_correction_recorded"], "recorded trace receipt is missing")

            return {
                "status": "PASS",
                "scope": "temporary_workbench_write_side; no_model_no_real_user_state",
                "cases": cases,
                "runtime_default": {
                    "recorded": True,
                    "trace_steps": trace_steps,
                    "provenance_fields": sorted(required_fields),
                },
                "identity_guards": {
                    "default": workbench_correction_guard_reason("default"),
                    "tester": workbench_correction_guard_reason("tester"),
                    "probe": workbench_correction_guard_reason("probe-alice"),
                },
            }
        finally:
            if old_users_root is None:
                os.environ.pop(userspace.ENV_USERS_DIR, None)
            else:
                os.environ[userspace.ENV_USERS_DIR] = old_users_root
            if old_pytest is not None:
                os.environ["PYTEST_CURRENT_TEST"] = old_pytest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args()
    try:
        report = verify()
    except Exception as exc:  # keep failures bounded and machine-readable
        report = {"status": "FAIL", "scope": "temporary_workbench_write_side", "error": type(exc).__name__}
        if not args.json:
            print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["status"])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
