#!/usr/bin/env python3
"""Verify correction-ledger consumption and per-user isolation offline.

This uses a temporary users root and the existing correction writer and
``memory_lookup`` registry. It does not exercise Workbench's missing automatic
correction-ingest path, call a model, or touch real user state. Output contains
counts and hashes only, never correction text or private paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence import userspace  # noqa: E402
from intelligence.services import corrections, memory_status, user_memory  # noqa: E402
from intelligence.services.episode_factory import build_episode_context  # noqa: E402
from intelligence.services.episode_tools import build_episode_registry  # noqa: E402
from intelligence.services.task_frame import TaskFrame  # noqa: E402


class VerificationError(RuntimeError):
    """A required offline contract did not hold."""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def frame() -> TaskFrame:
    return TaskFrame(
        raw_question="光刻胶，现在怎么看",
        user_goal="检查用户纠偏是否作为历史先验进入研究工具",
        question_type="stock_deep_dive",
        subject="光刻胶",
        subject_kind="concept",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_official_evidence",
        confidence=0.9,
    )


def write_correction(root: Path, user: str, *, ts: str) -> dict[str, Any]:
    path = userspace.user_space(user).corrections_path
    # user_space resolves the configured FORESIGHT_USERS_DIR; assert it points
    # into this temporary root before using the canonical writer.
    require(path.resolve().is_relative_to(root.resolve()), "Correction path escaped temporary users root")
    _, record = corrections.record_correction(
        path,
        correction="先看客户验证再谈弹性",
        original="只凭产能公告判断弹性",
        principle="验证进度优先于产能规划",
        themes=["光刻胶"],
        ts=ts,
    )
    return record


def lookup(root: Path, user: str, query: str = "光刻胶，现在怎么看") -> dict[str, Any]:
    recalled = user_memory.relevant_memory_records(
        query,
        user=user,
        limit=5,
    )
    registry_context = build_episode_context(
        frame(),
        task_id=f"memory-audit-{user}-{hashlib.sha256(user.encode()).hexdigest()[:8]}",
        capabilities=("memory_lookup",),
        timeout=30.0,
    )
    registry = build_episode_registry(
        frame(),
        registry_context,
        finance_root=root / "finance",
        knowledge_wiki=root / "wiki",
        l3_runner=None,
        memory_user=user,
    )
    require("memory_lookup" in registry.names(), f"memory_lookup missing for {user}")
    result = registry.execute(
        "memory_lookup",
        query,
        context=registry_context,
        step_id=f"memory-audit-{user}:1",
    )
    return {
        "recalled_corrections": len(recalled.corrections),
        "registered": "memory_lookup" in registry.names(),
        "trace_status": result.trace.status,
        "evidence_count": len(result.evidence),
        "evidence_detail_sha256": sorted(digest(item.detail) for item in result.evidence),
        "evidence_tiers": sorted({item.evidence_tier for item in result.evidence}),
        "source_labels": sorted({item.source for item in result.evidence}),
        "gaps": list(result.gaps),
    }


def verify() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="memory-consumption-") as tmp:
        root = Path(tmp) / "users"
        root.mkdir()
        old_root = os.environ.get(userspace.ENV_USERS_DIR)
        os.environ[userspace.ENV_USERS_DIR] = str(root)
        try:
            alice = write_correction(root, "alice", ts="2026-09-25T02:00:00")
            alice_before = lookup(root, "alice")
            bob_before = lookup(root, "bob")
            require(alice_before["recalled_corrections"] == 1, "Alice ledger was not recalled")
            require(alice_before["evidence_count"] == 1, "Alice tool did not return her correction")
            require(bob_before["recalled_corrections"] == 0, "Bob recalled Alice's correction")
            require(bob_before["evidence_count"] == 0, "Bob tool returned Alice's correction")
            require(bob_before["trace_status"] == "empty", "Bob empty recall was not explicit")
            require(alice_before["evidence_tiers"] == ["user_memory"], "Memory tier was not prior-only")
            require(all("非市场事实" in source for source in alice_before["source_labels"]), "Memory source boundary missing")

            alice_path = userspace.user_space("alice").corrections_path
            memory_status.record_status(
                alice_path,
                target_ts=alice["id"],
                status="rejected",
                reason="offline withdrawal check",
                ts="2026-09-25T02:01:00",
            )
            alice_after = lookup(root, "alice")
            require(alice_after["recalled_corrections"] == 0, "Rejected correction remained in direct recall")
            require(alice_after["evidence_count"] == 0, "Rejected correction remained in tool evidence")
            require(alice_after["trace_status"] == "empty", "Post-withdrawal empty recall was not explicit")

            no_identity_context = build_episode_context(
                frame(),
                task_id="memory-audit-no-identity",
                capabilities=("memory_lookup",),
                timeout=30.0,
            )
            no_identity_registry = build_episode_registry(
                frame(),
                no_identity_context,
                finance_root=root / "finance-no-identity",
                knowledge_wiki=root / "wiki-no-identity",
                l3_runner=None,
            )
            require("memory_lookup" not in no_identity_registry.names(), "Missing identity exposed memory tool")

            return {
                "status": "PASS",
                "scope": "temporary_ledger_writer_to_memory_lookup; no_workbench_ingest_no_model_no_real_user_state",
                "write_path": "canonical_corrections_record_correction_in_temporary_users_root",
                "alice_record_id": alice["id"],
                "alice_correction_sha256": digest(alice["correction"]),
                "alice_before_withdrawal": alice_before,
                "bob_cross_user_control": bob_before,
                "alice_after_withdrawal": alice_after,
                "missing_identity": {"memory_lookup_registered": False},
                "inputs_unchanged": True,
            }
        finally:
            if old_root is None:
                os.environ.pop(userspace.ENV_USERS_DIR, None)
            else:
                os.environ[userspace.ENV_USERS_DIR] = old_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args()
    try:
        report = verify()
    except Exception as exc:  # keep the audit result machine-readable
        report = {"status": "FAIL", "scope": "temporary_ledger_writer_to_memory_lookup", "error": type(exc).__name__}
        if not args.json:
            print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["status"])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
