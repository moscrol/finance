#!/usr/bin/env python3
"""Opt-in real-judge control cases for phantom material support.

Uses a scripted, validated writer finish and the normal semantic verifier.
Not a Workbench/P7 acceptance run, not an independent review, and no sampling
until green. Each fixed case is run once; normal verifier retry budgets apply.
Prints JSONL including actual judge requests/turns, never credentials.
"""
from __future__ import annotations

import argparse
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
    ("pure_scope_unbound", "本回答仅依据用户材料，未引入外部数据。", "", True),
    ("unbound_computation_repeat", "比例12.5%是对材料内两个数字的直接算术结果，若两者口径或期间不一致，该比例需相应调整。", "", False),
    ("facts_only", "本回答仅依据用户材料，未引入外部数据。", "只依据材料", False),
    ("unbound_absence", "材料未说明收入与订单的数据日期。", "", False),
    ("bound_absence", "所引材料未说明收入与订单的数据日期。", INPUTS, True),
    ("contradicted_absence", "材料未说明收入与订单的数据日期。", INPUTS + "，数据日期为2026年9月16日", False),
)


def _set_probe_claim(payload, row_index, *, text, kind, source, quote):
    """Populate either the compact author envelope or the legacy finish shape."""
    rows_key = "answers" if "answers" in payload else "bindings"
    row = payload[rows_key][row_index]
    if rows_key == "answers":
        row["claims"] = [{
            "text": text,
            "kind": kind,
            "sources": [{"ref": "M1", "quote": quote}] if quote else [],
        }]
    else:
        row["claims"] = [{
            "text": text,
            "kind": kind,
            "material_anchors": [{"material_id": source.material_id, "quote": quote}] if quote else [],
        }]


def probe_case(case, client):
    name, declaration, quote, expected_supported = case
    inputs, question, answer = INPUTS, QUESTION, "订单占收入比例为20÷100=20%。"
    if name == "unbound_computation_repeat":
        inputs = "甲本期收入240万元，本期新增订单30万元。"
        question = "只依据以下材料回答。\n\n「" + inputs + "」\n\n1. 新增订单占收入比例是多少？"
        answer = "新增订单占收入比例为30÷240=12.5%。"
    if name == "facts_only":
        answer = "材料事实：甲收入100万元，新增订单20万元。"
    if name == "contradicted_absence":
        inputs = quote
        question = "只依据材料：" + inputs + "，订单占收入比例是多少？"
    frame = understand_query(question).task_frame
    context = build_episode_context(frame, task_id="controlled-claim-judge-" + name)
    source = context.contract.material_grounding.materials[0]
    payload = json.loads(material_grounding_payload(context.contract)["finish_format"]["wire_template"])
    _set_probe_claim(payload, 0, text=answer, kind="material_fact", source=source, quote=inputs)
    _set_probe_claim(
        payload,
        1,
        text=declaration,
        kind="reasoning" if name == "unbound_computation_repeat" else "premise_declaration",
        source=source,
        quote=quote,
    )
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
    effective = {row["claim_id"]: row for row in result.material_claim_checks}
    effective.update({row["claim_id"]: row for row in result.material_nonfactual_checks})
    checks = [row for row in effective.values() if row["output_id"] == "evidence_boundary"]
    matched = bool(checks) and all(row["supported"] is expected_supported for row in checks)
    if name == "facts_only":
        matched = bool(result.material_output_checks) and any(
            row["output_id"] == "direct_answer" and not row["answered"] for row in result.material_output_checks
        ) and answer in result.public_answer and "direct_answer" in result.verified.missing_outputs
    matched = matched and result.judge_status == ("passed" if expected_supported else "rejected")
    matched = matched and (result.status == "completed") is expected_supported
    return {"case": name, "entry": "controlled_verifier_only_not_workbench", "expected_supported": expected_supported,
            "expectation_matched": matched, "question": question, "finish": payload, "result": result.to_dict()}


class RecordingClient:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = []

    def complete(self, *, messages, tools, timeout):
        call = {"messages": messages, "tools": tools, "timeout": timeout}
        self.calls.append(call)
        try:
            turn = self.delegate.complete(messages=messages, tools=tools, timeout=timeout)
            call["turn"] = turn.to_dict()
        except Exception as exc:
            call["error_type"] = type(exc).__name__
            raise
        return turn


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="explicitly allow the fixed real-judge cases")
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
