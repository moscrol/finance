"""Public tool views preserve research facts without disclosing private receipts."""
from __future__ import annotations

from dataclasses import asdict
import importlib.util
import json
from pathlib import Path

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import public_agent_evidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ToolObservation

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pi_public_model_view", ROOT / "integrations/pi/model_view.py")
view = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(view)


def test_withheld_future_prose_and_private_trace_never_reach_model():
    accepted = AgentEvidence(tool="news_search", title="Admitted title", detail="Known by cutoff",
                             source="fixture", source_date="2026-09-24", content_hash="accepted-hash",
                             internal_locator="PRIVATE_LOCATOR")
    observation = ToolObservation(
        tool="news_search", query="fixture", evidence=(accepted,),
        observation="One admitted item; later content was withheld.",
        trace=ProviderTrace(provider="fixture", capability="directional_news", status="partial",
                            detail="PRIVATE_TRACE_WITH_FUTURE_TEXT"),
        gaps=("Later material was withheld.",), evidence_hashes=("accepted-hash",),
        telemetry={"temporal_withheld": {
            "evidence": [{"title": "FUTURE_TITLE", "detail": "FUTURE_DETAIL", "source_date": "2099-01-01"}],
            "observation": "FUTURE_PROSE", "query_basis": {"value": "FUTURE_BASIS"},
        }, "new_private_field": "PRIVATE_DEBUG"},
        query_basis={"total_rows": 36, "preview_rows": 8, "omitted_rows": 28},
    )
    before = asdict(observation)
    public = view.model_observation(observation)
    encoded = json.dumps(public)
    assert "FUTURE_" not in encoded and "PRIVATE_" not in encoded
    assert "telemetry" not in public and "trace" not in public
    assert public["evidence"] == [public_agent_evidence(accepted)]
    assert public["evidence_hashes"] == ["accepted-hash"]
    assert public["query_basis"] == observation.query_basis
    assert public["source_context"] == observation.source_context
    assert public["gaps"] == list(observation.gaps)
    assert public["ok"] is True and public["status"] == "partial"
    assert asdict(observation) == before, "audit must keep the original withheld record"


@pytest.mark.parametrize("status,ok,public_status", [
    ("success", True, "success"),
    ("empty", True, "empty"),
    ("stale", True, "stale"),
    ("future_of_cutoff", True, "future_of_cutoff"),
    ("parse_error", False, "parse_error"),
    ("timeout", False, "timeout"),
    ("PRIVATE_UNRECOGNIZED_STATUS", False, "unknown_provider_status"),
])
def test_domain_status_is_not_replaced_by_http_success(status, ok, public_status):
    observation = ToolObservation(
        tool="finance_query", query="fixture", evidence=(), observation="Diagnostic only.",
        trace=ProviderTrace(provider="fixture", capability="finance_query", status=status),
        gaps=("No market conclusion from this status.",),
        telemetry={"temporal_withheld": {"observation": "FUTURE_PROSE"}},
    )
    public = view.model_observation(observation)
    assert public["ok"] is ok and public["status"] == public_status
    assert "PRIVATE_" not in json.dumps(public) and "FUTURE_" not in json.dumps(public)
    assert public["evidence"] == [] and public["gaps"]
