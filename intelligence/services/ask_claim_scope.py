"""Attach private advisory review to both immediate and deferred ask delivery."""

from __future__ import annotations

from intelligence.services.ask_render import render_conversation_answer
from intelligence.services.ask_types import AskResult
from intelligence.services.claim_scope_review import claim_scope_requested, review_runtime_claims
from intelligence.services.output_review import OutputReviewGate, ReviewCheck


def review_ask_claim_scope(result: AskResult, *, delivered_answer: str | None = None) -> AskResult:
    if not claim_scope_requested():
        return result
    # Only source records are evidence. AnswerSpec claims and synthesis are model
    # output and must never be used to certify their own fund-flow assertions.
    evidence = (
        [source.to_dict() for source in result.answer_spec.sources]
        if result.answer_spec is not None else
        [{"source": item.source, "detail": item.detail} for item in result.citations]
    )
    evidence.extend(
        {"source_date": trace.source_trade_date}
        for trace in result.provider_traces
        if trace.status == "ok" and trace.source_trade_date
    )
    receipt = review_runtime_claims(
        answer=render_conversation_answer(result) if delivered_answer is None else delivered_answer,
        question=result.query,
        episode={"outcome": {"events": [], "evidence": evidence}},
        mapping_limits=("engine_b_tool_requests_unavailable",),
    )
    gate = result.review_gate
    if gate is None:
        gate = result.review_gate = OutputReviewGate()
    gate.claim_scope = receipt
    gate.checks = [check for check in gate.checks if not check.name.startswith("口径越界·")]
    if receipt is not None:
        gate.checks.extend(ReviewCheck(**check) for check in receipt.get("checks", []))
    return result
