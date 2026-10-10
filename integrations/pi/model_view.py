"""Model-facing tool data; private receipts never widen the research cutoff.

Follow ResearchHarness.project_tool_result's public/audit boundary without importing
its finish contract or owned-result authoring instructions into the native Pi arm.
"""
from __future__ import annotations

from intelligence.services.agent_runtime import public_agent_evidence
from intelligence.services.research_tool_registry import ToolObservation


def model_observation(observation: ToolObservation) -> dict[str, object]:
    return {
        **observation.result_status_fields(),
        "tool": observation.tool,
        "query": observation.query,
        "dataset": observation.dataset,
        "caliber": observation.caliber,
        "query_basis": dict(observation.query_basis),
        "source_context": dict(observation.source_context),
        "gaps": list(observation.gaps),
        "observation": observation.observation,
        "evidence": [public_agent_evidence(item) for item in observation.evidence],
        "evidence_hashes": list(observation.evidence_hashes),
    }
