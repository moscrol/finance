#!/usr/bin/env python3
"""Replay the frozen 2026-09-18 turn-6/7 loss without a model, DB, or service.

Reads the original private continuous-episode.json; nothing is copied into git.
Checks the original bytes via SHA-256 and original rejection codes, then runs
those exact turns through the new loop with frozen evidence. Two deterministic
paths exercise continued research and bounded no-tools recovery. They are NOT
new live submissions, finance certification, or permission to change the old
not_passed acceptance. --output creates a new receipt exclusively (no overwrite).
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def replay(path: Path) -> dict[str, object]:
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_research import AgentEvidence, StructuredObservation
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.finish_candidate import CANDIDATE_REVIEW_NOTICE
    from intelligence.services.historical_research.intent import HistoryIntent
    from intelligence.services.research_contract import (
        InformationCutoff, ResearchDeadline, ResearchPolicy, ResearchRunContext, ResearchTaskContract,
    )
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
    from intelligence.services.task_frame import TaskFrame
    from scripts.smoke_workbench_self_use import SecretScanner

    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "2ec9617b42c551ac42b882a9c5b339d0894a0037904de263465bfec539aad4f0", "not the frozen source artifact"
    artifact = json.loads(raw)
    scanner = SecretScanner()
    scanner.scan(artifact, "original_episode")
    assert not scanner.hits, "source secret scan failed; never copy secrets into a receipt"
    contract = ResearchTaskContract.from_dict(artifact["contract"])
    frame = TaskFrame.from_dict(artifact["task_frame"])
    assert frame is not None and frame.task_frame_hash == contract.task_frame_hash
    meta = artifact["research_context"]
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy("max", 8, 60, 0), trace_parent_id=contract.task_id,
        today=meta["today"], latest_data_date=meta["latest_data_date"],
        information_cutoff=InformationCutoff(date.fromisoformat(meta["information_cutoff"]["as_of_date"]), meta["information_cutoff"]["source"]),
        history_intent=HistoryIntent.from_dict(meta["history_intent"]),
        history_results=deepcopy(meta["history_results"]),
    )
    cards = []
    for source in artifact["outcome"]["evidence"]:
        value = dict(source)
        for key in ("supports", "contradicts", "derived_from"):
            value[key] = tuple(value.get(key, ()))
        value["observations"] = tuple(StructuredObservation(**row) for row in value.get("observations", ()))
        cards.append(AgentEvidence(**value))
    evidence = tuple(cards)
    turns = [row["payload"] for row in artifact["events"] if row["kind"] == "model_turn"]
    first = next(row["content"] for row in turns if row.get("turn_id") == "turn-6")
    second = next(row["content"] for row in turns if row.get("turn_id") == "turn-7")
    recovery = next(row["content"] for row in turns if row.get("phase") == "finalization_recovery")
    # Envelope boundary fixed by the frozen original, not a production parser.
    prose, envelope = first.rsplit('\n\n{"status":', 1)
    summary = json.loads('{"status":' + envelope)["draft"]
    old_parts = (prose, summary, json.loads(second)["draft"], json.loads(recovery)["draft"])
    assert (len(first), len(second), len(recovery)) == (2610, 1871, 1535)
    assert _hash(old_parts[-1]) == "403db7ec72a5d9737058f556f17123dccc3d3dcdab222df59a365681d7ac6571"

    def no_io(*_args):
        raise AssertionError("replay must not run a tool")

    # Authoritative observations are seeded at the retained-turn boundary.
    # Menu definitions are inert; earlier eight tool calls are not re-executed.
    registry = ResearchToolRegistry(tuple(ToolSpec(
        name=name, capability=name, description="frozen replay, no IO",
        cost="local", freshness="current", runner=no_io,
    ) for name in dict.fromkeys((*contract.allowed_capabilities, *(card.tool for card in evidence)))), opening_prefetch=evidence)
    harness = FinanceResearchHarness()
    admitted = [harness.admit_finish(text, context=context, evidence=evidence, registry=registry) for text in (first, second)]
    assert [value.rejection["rejection_code"] for value in admitted] == ["not_json_object", "history_missing_comparison"]
    assert all(not value.accepted and value.candidate is not None for value in admitted)
    assert prose in admitted[0].candidate.draft and summary in admitted[0].candidate.draft
    assert old_parts[2] == admitted[1].candidate.draft
    results = {}
    for mode in ("continued", "recovery"):
        calls = []
        scripted = iter((first, second, recovery))

        class Model:
            def complete(self, **kwargs):
                calls.append(deepcopy(kwargs))
                return ModelTurn(next(scripted), (), "offline-replay", "")

        run_context = replace(
            context, deadline=ResearchDeadline.from_timeout(60),
            policy=replace(context.policy, max_steps=8 if mode == "continued" else 1),
        )
        outcome = ContinuousAgentEpisode(Model()).run(task_frame=frame, context=run_context, registry=registry)
        assert all(part in outcome.draft for part in old_parts)
        positions = [outcome.draft.index(part) for part in old_parts]
        assert positions == sorted(positions)
        assert outcome.status == "partial" and CANDIDATE_REVIEW_NOTICE in outcome.gaps
        assert len(calls) == outcome.usage.llm_calls == 3 and outcome.usage.tool_calls == 0
        assert [event.payload["code"] for event in outcome.events if event.kind == "invalid_action"] == ["not_json_object", "history_missing_comparison"]
        if mode == "continued":
            assert calls[2]["tools"] and outcome.stop_reason == "model_finish"
        else:
            assert not calls[2]["tools"] and outcome.stop_reason == "finalization_recovered"
            payload = json.loads(calls[2]["messages"][1]["content"])
            assert all(part in payload["candidate_drafts"][0] for part in old_parts[:3])
            assert len(payload["evidence"]) > 12

        def unavailable(_request):
            raise TimeoutError("offline replay: judge deliberately unavailable")

        reviewed = SemanticEpisodeVerifier(judge_fn=unavailable).verify(
            frame=frame, structurally_verified=verify_episode_outcome(contract, outcome),
            deadline=run_context.deadline,
        )
        # Independent financial review is NOT simulated as a pass.
        assert all(part in reviewed.public_answer for part in old_parts)
        assert reviewed.status == "partial" and reviewed.judge_status == "unavailable"
        scanner.scan(reviewed.public_answer, f"{mode}.public_answer")
        assert not scanner.hits
        results[mode] = {
            "draft_chars": len(outcome.draft), "draft_sha256": _hash(outcome.draft),
            "public_chars": len(reviewed.public_answer), "public_sha256": _hash(reviewed.public_answer),
            "exact_parts_preserved": len(old_parts), "order_preserved": True,
            "llm_stub_calls": len(calls), "real_model_calls": 0, "tool_calls": 0,
            "status": outcome.status, "stop_reason": outcome.stop_reason,
            "judge_status": reviewed.judge_status,
        }
    return {
        "schema": "finish-candidate-replay/v1", "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw), "source_task_frame_hash": frame.task_frame_hash,
        "turns": {name: {"chars": len(text), "sha256": _hash(text)} for name, text in zip(("turn-6", "turn-7", "recovery"), (first, second, recovery), strict=True)},
        "rejection_codes": [value.rejection["rejection_code"] for value in admitted],
        "frozen_evidence_count": len(evidence), "results": results,
        "source_acceptance": "not_passed", "new_product_submissions": 0,
        "financial_certification": False, "checks": "passed", "secret_scan_hits": len(scanner.hits),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty_paths": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = replay(args.episode)
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
