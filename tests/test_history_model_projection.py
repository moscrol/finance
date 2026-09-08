"""Historical values must survive the actual model-facing observation budget."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from intelligence.services.agent_research import evidence_content_hash
from intelligence.services.historical_research.episode import _result, history_tool_specs
from intelligence.services.historical_research.features import FEATURES, FEATURE_VERSION
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ToolObservation
from intelligence.services.tool_result_budget import MAX_EVIDENCE_DETAIL_CHARS
from intelligence.tests.test_historical_research_episode import _registry


REF = "run-history-review/history-query-" + "a" * 64 + ".json"


def _project(observation):
    if not isinstance(observation, ToolObservation):
        evidence = tuple(
            replace(item, content_hash=evidence_content_hash(item))
            for item in observation.evidence
        )
        observation = ToolObservation(
            tool="history_query",
            query="projection contract",
            evidence=evidence,
            evidence_hashes=tuple(item.content_hash for item in evidence),
            observation=observation.observation,
            trace=observation.trace,
            gaps=observation.gaps,
            telemetry=observation.telemetry,
        )
    projected = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=observation.evidence, seen_prose=set()
    )
    model = json.loads(projected.model_content)
    details = []
    for item in model["evidence"]:
        assert len(item["detail"]) <= MAX_EVIDENCE_DETAIL_CHARS
        assert not item["detail"].endswith("…")
        details.append(json.loads(item["detail"]))
    assert len(model["evidence"]) == len(observation.evidence)
    return model, details


def _payload(rows, *, operation="compute_history"):
    return {
        "query_id": "q-projection",
        "operation": operation,
        "status": "research_only",
        "total_matched": len(rows),
        "returned_count": len(rows),
        "truncated": False,
        "preview": rows,
        "rows": deepcopy(rows),
        "coverage": {"large": {"missing_dates": ["2024-01-01"] * 300}},
        "feature_definitions": {
            name: dict(value, version=FEATURE_VERSION) for name, value in FEATURES.items()
        },
    }


def test_real_query_projection_keeps_values_status_definition_ref_and_original(tmp_path):
    registry, context, session = _registry(tmp_path)
    observed = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
            "features": ["return_pct", "amount_ratio", "double_red_days"],
        },
        context=context,
        step_id="query",
    )
    ref = observed.telemetry["result_ref"]
    original = session.read(ref)
    frozen = deepcopy(original)
    model, details = _project(observed)
    samples = [row for row in details if row.get("entity_code") == "A.FP"]
    for feature, expected in (("return_pct", 3.02), ("amount_ratio", 1.3), ("double_red_days", 0)):
        sample = next(row for row in samples if feature in row.get("features", {}))
        assert sample["features"][feature] == pytest.approx(expected)
        assert sample["status"][feature] == "complete"
        assert sample["start"] == "2026-08-03"
        assert sample["end"] == "2026-08-04"
    definition = next(row for row in details if row.get("feature") == "double_red_days")
    assert definition["rule"] == FEATURES["double_red_days"]["rule"]
    assert "500" in definition["rule"]
    assert definition["unit"] == "trading_days"
    assert definition["version"] == FEATURE_VERSION
    assert any(row.get("entity_name") == "农业" for row in samples)
    assert any(row.get("result_ref") == ref for row in details)
    assert ref in model["observation"]
    assert any(row.get("returned_count") == 1 for row in details)
    assert len(details) > original["returned_count"]
    assert session.read(ref) == frozen
    assert "feature_coverage" in original["rows"][0]
    assert original["inputs"]


@pytest.mark.parametrize("kind", ["sector", "stock"])
def test_inspect_projects_entity_values_before_large_members_and_market(kind):
    row = {
        "entity_code": "A.FP" if kind == "sector" else "000001.SZ",
        "trade_date": "2026-08-04",
        kind: {"pct_chg": -2.5, "amount": 732.1, "diff_ratio": None, "close": 17.25},
        "market": {"debug": "large market detail" * 100},
        "members": [{"stock_ts_code": "large" + str(i)} for i in range(200)],
        "events": [{"title": "unverified" * 100}],
    }
    payload = _payload([row], operation="inspect_history")
    frozen = deepcopy(payload)
    _, details = _project(_result(payload, result_ref=REF))
    fields = {}
    for detail in details:
        if detail.get("entity_code") == row["entity_code"]:
            assert detail["trade_date"] == "2026-08-04"
            fields.update(detail.get(kind, {}))
    assert fields == row[kind]
    assert any(detail.get("members_count") == 200 for detail in details)
    assert payload == frozen


@pytest.mark.parametrize(
    ("state", "x", "y", "value"),
    [("observed", False, False, -8.25), ("missing_feature", None, None, None), ("missing_outcome", True, None, None), ("immature", True, None, None)],
)
def test_comparison_projects_exact_x_y_definitions_denominator_and_states(state, x, y, value):
    payload = _payload([{
        "entity_code": "A.FP", "start": "2026-08-03", "end": "2026-08-04",
        "x": x, "y": y, "forward_return_pct": value, "comparison_state": state,
        "outcome_end": "2026-08-11",
        "features": {"return_pct": None if x is None else 18.75},
        "feature_coverage": {"return_pct": {"status": "missing" if x is None else "complete"}},
    }], operation="compare_cases")
    condition = {"feature": "return_pct", "op": "gte", "value": 15}
    outcome = {"metric": "compounded_sector_daily_pct", "horizon_days": 5, "threshold_pct": 3, "cutoff": "2026-09-07"}
    payload.update(
        spec={"condition": condition},
        outcome_definition=outcome,
        universe={"entity_kind": "sector", "entity_codes": ["A.FP"], "start": "2024-01-02", "end": "2026-08-04", "window_days": 20, "step_days": 5},
        comparison={"four_cells": {"x_true_y_true": 2, "x_true_y_false": 3, "x_false_y_true": 5, "x_false_y_false": 7}, "missing": 11, "immature": 13, "enumerated": 41, "independence_status": "not_established"},
    )
    _, details = _project(_result(payload, result_ref=REF))
    assert next(row["condition"] for row in details if "condition" in row) == condition
    assert next(row["outcome_definition"] for row in details if "outcome_definition" in row) == outcome
    assert next(row["four_cells"] for row in details if "four_cells" in row) == payload["comparison"]["four_cells"]
    assert any(row.get("window_days") == 20 for row in details)
    for key in ("missing", "immature", "enumerated"):
        assert next(row[key] for row in details if key in row) == payload["comparison"][key]
    sample = {}
    for row in details:
        if row.get("entity_code") == "A.FP":
            sample.update(row)
    assert sample["comparison_state"] == state
    assert sample["x"] is x and sample["y"] is y
    assert sample["forward_return_pct"] == value


def test_all_preview_samples_survive_without_equating_cards_to_returned_rows():
    payload = _payload([{
        "entity_code": "A.FP", "start": "2026-08-01", "end": "2026-08-04",
        "features": {"return_pct": i}, "feature_coverage": {"return_pct": {"status": "complete"}},
    } for i in range(25)])
    payload.update(total_matched=40, truncated=True)
    model, details = _project(_result(payload, result_ref=REF))
    assert {row["sample"] for row in details if "features" in row} == set(range(25))
    assert len(model["evidence"]) > 25
    assert any(row.get("returned_count") == 25 and row.get("total_matched") == 40 for row in details)
    assert "projected_evidence_count" in model["observation"]
    assert "read_history_result" in model["observation"]
    assert "缩窄" in model["observation"]


def test_oversized_field_is_explicitly_omitted_without_clipping_json():
    payload = _payload([{"entity_code": "A.FP", "entity_name": "超长源名称" * 100, "trade_date": "2026-08-04", "sector": {"pct_chg": 1.25}}])
    _, details = _project(_result(payload, result_ref=REF))
    assert any(row.get("projection_status") == "oversized_field_omitted" for row in details)
    assert any(row.get("sector", {}).get("pct_chg") == 1.25 for row in details)
    assert len(payload["rows"][0]["entity_name"]) > 240


def test_tool_schema_exposes_feature_rules_from_the_same_definition_source(tmp_path):
    _, context, session = _registry(tmp_path)
    frame = understand_query("这一波农业怎么走出来的").task_frame
    tool = history_tool_specs(frame, context, tmp_path / "missing.duckdb", session)[0]
    description = tool.parameters["properties"]["features"]["description"]
    assert FEATURES["double_red_days"]["rule"] in description
    assert FEATURE_VERSION in description
    assert "null" in description and "500" in description


def test_public_citations_keep_distinct_query_blocks_and_sample_pages():
    from intelligence.runtime.continuous_turn_adapter import _public_citation_projection
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding

    first = _payload([{"entity_code": "A.FP", "trade_date": "2026-08-04", "sector": {"pct_chg": 1}}])
    second = dict(deepcopy(first), query_id="another-query")
    later_page = dict(deepcopy(first), preview=[{"entity_code": "B.FP", "trade_date": "2026-08-04", "sector": {"pct_chg": 2}}])
    evidence = tuple(
        replace(item, content_hash=evidence_content_hash(item))
        for payload in (first, second, later_page)
        for item in _result(payload, result_ref=REF).evidence
    )
    outcome = AgentOutcome(
        task_frame_hash="history-citations", status="partial", draft="描述性研究",
        evidence=evidence, traces=(), gaps=(), stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "history-citations"}),),
        bindings=(OutputEvidenceBinding("direct_assessment", tuple(item.content_hash for item in evidence)),),
        usage=AgentUsage(),
    )
    citations = _public_citation_projection(outcome, frozenset(), allowed_output_ids=frozenset({"direct_assessment"}))
    # Repeated metadata of the same query may collapse; distinct queries, every
    # block, and different sample pages must remain independently visible.
    expected = {(item.title, item.source, item.source_date or "") for item in evidence}
    assert len(citations) == len(expected)
    assert len([item for item in citations if item["title"].startswith("历史观察样本")]) == 3
    assert {item.independent_key for item in evidence} == {"q-projection", "another-query"}


@pytest.mark.parametrize("parent_kind", ["query", "missing_draft", "invalid_draft"])
def test_wrong_save_parent_has_a_repairable_value_error(tmp_path, parent_kind):
    registry, context, session = _registry(tmp_path)
    if parent_kind == "query":
        observed = registry.execute(
            "history_query", {"operation": "compute_history", "start": "2026-08-03", "end": "2026-08-04", "entity_codes": ["A.FP"]},
            context=context, step_id="query",
        )
        ref = observed.telemetry["result_ref"]
    else:
        ref = session.save("case", {} if parent_kind == "missing_draft" else {"draft": {"case_id": "broken"}})
    draft = {"question": "农业复盘", "purpose": "retrospective_discovery", "entity_ids": ["A.FP"], "source_refs": []}
    before = session.store.load_run(session.run_id).artifacts
    with pytest.raises(ValueError, match="previous_result_ref must reference a saved history case; omit for initial draft"):
        registry.execute("save_history_research", {"draft": draft, "previous_result_ref": ref}, context=context, step_id="wrong-parent")
    assert session.store.load_run(session.run_id).artifacts == before


def test_analogue_projection_exposes_reference_vector_candidate_delta_and_cutoff():
    candidate = {
        "entity_code": "A.FP", "start": "2025-08-05", "end": "2025-09-01",
        "feature_cutoff": "2025-09-01", "features": {"return_pct": 4.7396},
        "feature_coverage": {"return_pct": {"status": "complete"}},
        "feature_differences": {"return_pct": -22.836965264525766}, "distance": 0.83,
    }
    payload = _payload([candidate], operation="find_analogues")
    payload.update(
        reference={
            "entity_code": "990302.FP", "start": "2026-08-05", "end": "2026-09-01",
            "feature_cutoff": "2026-09-01", "features": {"return_pct": 27.576565264525765},
            "feature_coverage": {"return_pct": {"status": "complete"}},
        },
        matching_use="trigger_time_features_only_research",
    )
    _, details = _project(_result(payload, result_ref=REF))
    reference = next(row for row in details if row.get("role") == "reference" and "features" in row)
    assert reference["entity_code"] == "990302.FP"
    assert reference["features"] == payload["reference"]["features"]
    assert reference["status"]["return_pct"] == "complete"
    delta = next(row for row in details if "feature_differences" in row)
    assert delta["role"] == "candidate"
    assert delta["feature_differences"] == candidate["feature_differences"]
    assert any(row.get("feature_cutoff") == "2026-09-01" for row in details)
    assert any(row.get("matching_use") == payload["matching_use"] for row in details)
    assert any(row.get("returned_count") == 1 for row in details)
