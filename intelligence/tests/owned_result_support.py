"""Public D4 source fixture and boundary drivers for ownership tests."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff, RequiredOutput, ResearchDeadline, ResearchPolicy,
    ResearchRunContext, ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ToolObservation
from intelligence.services.task_frame import TaskFrame

IMMUNE_KEY = ("2026-09-30", "LM002.LOCAL", "990080.FP")


def source_fixture() -> ToolObservation:
    data = json.loads((Path(__file__).parent / "fixtures/owned_d4_source.json").read_text())
    evidence = tuple(AgentEvidence(**{**card, "supports": tuple(card["supports"]),
                                    "contradicts": tuple(card["contradicts"])})
                     for card in data.pop("evidence"))
    return ToolObservation(
        **{**data, "payload_field_names": tuple(data["payload_field_names"]),
           "evidence_hashes": tuple(data["evidence_hashes"])},
        evidence=evidence,
        trace=ProviderTrace(provider="agent:mainline_context", capability="mainline_context",
                            status="success", source_trade_date="2026-09-30", result_count=24),
    )


def frame_context(*, task_id: str = "owned-results-test", max_steps: int = 4):
    frame = TaskFrame(
        raw_question="截至2026年9月30日的主线结构怎样？", user_goal="核对同日量价资格",
        question_type="market_forecast", subject="A股市场", subject_kind="market_pattern",
        market_scope="A股", timeframe="2026-09-30", required_outputs=("direct_assessment",),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="current_market_scenarios", confidence=1.0,
    )
    contract = ResearchTaskContract(
        task_id=task_id, question=frame.raw_question, subject=frame.subject,
        subject_kind=frame.subject_kind, question_type=frame.question_type,
        required_outputs=(RequiredOutput("direct_assessment", "同日行情研判", ("mainline_context",), True),),
        allowed_capabilities=("mainline_context",), research_tier="quick", freshness="current",
        task_frame_hash=frame.task_frame_hash, evidence_plan=EvidencePlan(),
    )
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy(tier="quick", total_seconds=60, synthesis_reserve=5,
                              max_steps=max_steps), trace_parent_id=task_id,
        today="2026-09-30", latest_data_date="2026-09-30",
        information_cutoff=InformationCutoff(date(2026, 9, 30), "requested"),
    )
    return frame, context


def finish_payload(parts=None, *, draft="", source=None):
    source = source or source_fixture()
    result = {"status": "completed", "draft": draft, "gaps": [], "bindings": [{
        "output_id": "direct_assessment", "evidence_hashes": [source.evidence[0].content_hash],
        "basis": "evidence", "gap": "",
    }]}
    if parts is not None:
        result["answer_parts"] = parts
    return result
