#!/usr/bin/env python3
"""Opt-in real-judge control cases for phantom material support.

Uses a scripted, validated writer finish and the normal semantic verifier.
Not a Workbench/P7 acceptance run, not an independent review, and no sampling
until green. Each fixed case is run once; normal verifier retry budgets apply.
Prints JSONL including actual judge requests/turns, never credentials.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import subprocess

from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import validate_episode_finish
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.material_grounding import material_grounding_payload
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import ResearchDeadline

QUESTION = "只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？"
NUMBERS = "本回答仅依据用户材料中的收入100万元和新增订单20万元。"
INPUTS = "甲收入100万元，新增订单20万元"
CASES = (
    ("unbound_numbers", NUMBERS, "只依据材料", False),
    ("empty_anchors", NUMBERS, "", False),
    ("bound_numbers", NUMBERS, INPUTS, True),
    ("pure_scope", "本回答仅依据用户材料，未引入外部数据。", "只依据材料", True),
)


def probe_case(case, client):
    name, declaration, quote, expected_supported = case
    frame = understand_query(QUESTION).task_frame
    context = build_episode_context(frame, task_id="controlled-claim-judge-" + name)
    source = context.contract.material_grounding.materials[0]
    payload = json.loads(material_grounding_payload(context.contract)["finish_format"]["wire_template"])
    payload["bindings"][0]["claims"] = [{
        "text": "订单占收入比例为20÷100=20%。", "kind": "material_fact",
        "material_anchors": [{"material_id": source.material_id, "quote": INPUTS}],
    }]
    payload["bindings"][1]["claims"] = [{
        "text": declaration, "kind": "premise_declaration",
        "material_anchors": [{"material_id": source.material_id, "quote": quote}] if quote else [],
    }]
    parsed = validate_episode_finish(payload, context=context, evidence=())
    draft = AgentOutcome(
        task_frame_hash=frame.task_frame_hash, status=parsed.status, draft=parsed.draft,
        evidence=(), traces=(), gaps=parsed.gaps, stop_reason="controlled_judge_probe",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=parsed.bindings, usage=AgentUsage(),
    )
    result = SemanticEpisodeVerifier(primary_judge=client).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, draft),
        deadline=ResearchDeadline.from_timeout(90),
    )
    checks = [row for row in result.material_claim_checks if row["output_id"] == "evidence_boundary"]
    matched = bool(checks) and all(row["supported"] is expected_supported for row in checks)
    matched = matched and result.judge_status == ("passed" if expected_supported else "rejected")
    return {"case": name, "entry": "controlled_verifier_only_not_workbench", "expected_supported": expected_supported,
            "expectation_matched": matched, "question": QUESTION, "finish": payload, "result": result.to_dict()}


class RecordingClient:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = []

    def complete(self, *, messages, tools, timeout):
        turn = self.delegate.complete(messages=messages, tools=tools, timeout=timeout)
        self.calls.append({"messages": messages, "tools": tools, "timeout": timeout, "turn": asdict(turn)})
        return turn


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="explicitly allow four fixed real-judge cases")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; this diagnostic makes real model calls")
    from intelligence.runtime.glm_agent_runtime import GLMModelClient

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    matched = []
    for case in CASES:
        client = RecordingClient(GLMModelClient())
        result = probe_case(case, client)
        matched.append(result["expectation_matched"])
        print(json.dumps({"revision": revision, "dirty": dirty, **result, "judge_calls": client.calls}, ensure_ascii=False), flush=True)
    return 0 if all(matched) else 1


if __name__ == "__main__":
    raise SystemExit(main())
