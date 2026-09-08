"""History-to-methodology handoff keeps provenance without fabricating evidence."""

import json
from pathlib import Path

import pytest

from intelligence.services.historical_research.methodology import (
    prepare_methodology_candidate,
)
from intelligence.services.historical_research.research import (
    HypothesisDraft,
    ResearchCase,
)
from intelligence.services.methodology_backtest.rules import parse_rule


@pytest.fixture
def case():
    return ResearchCase(
        case_id="case-agriculture",
        question="农业这一波的双红能否迁移？",
        purpose="retrospective_discovery",
        entity_ids=("990302.FP",),
        source_refs=("query-1",),
        window_start="2026-08-05",
        window_end="2026-09-01",
        selection_mode="posthoc_winner",
        exposed_sample_refs=("query-1", "query-failure"),
        hypotheses=(
            HypothesisDraft(
                hypothesis_id="h-1",
                statement="连续双红可能有后续上涨，但成交额也可能只是结果。",
                source_case_refs=("case-agriculture",),
                feature_definitions=("max_double_red_streak@history-features-v1",),
                alternatives=("整体市场反弹",),
                counterevidence_refs=("query-failure",),
                failed_sample_refs=("query-failure",),
                exposed_sample_refs=("query-1", "query-failure"),
            ),
        ),
    )


@pytest.fixture
def seed():
    path = (
        Path(__file__).resolve().parents[1]
        / "methodology/rules/dual_red_streak3_continuation.v1.json"
    )
    return json.loads(path.read_text())


def prepare(case, **kwargs):
    return prepare_methodology_candidate(
        case,
        "h-1",
        owner="researcher",
        rule_id="agriculture_dual_red_candidate",
        entity_type="sector",
        **kwargs,
    )


def test_no_explicit_rule_returns_unsupported_and_preserves_complete_case(case):
    result = prepare(case)
    assert result["status"] == "unsupported_definition"
    assert result["rule_doc"] is None
    assert result["source_context"]["case"] == case.to_dict()
    assert result["source_context"]["hypothesis"] == case.hypotheses[0].to_dict()
    assert any(
        issue["code"] == "window_max_is_not_endpoint_streak"
        for issue in result["issues"]
    )
    assert result["formalization_requires_review"] is True
    assert result["decision_eligible"] is False
    assert result["promotion_eligible"] is False
    json.dumps(result, allow_nan=False)


def test_existing_rule_syntax_builds_private_candidate_without_evaluation(
    case, seed, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("candidate preparation may not write a rule or run an evaluation")

    monkeypatch.setattr(
        "intelligence.services.methodology_backtest.propose.write_rule_file", forbidden
    )
    monkeypatch.setattr(
        "intelligence.services.methodology_backtest.runner.run_rule", forbidden
    )
    result = prepare(
        case, predicates=seed["condition"]["all"], success=seed["outcome"]["success"]
    )
    assert result["status"] == "candidate_prepared"
    rule = parse_rule(result["rule_doc"])
    assert rule.sharing == "private"
    assert rule.owner == "researcher"
    assert rule.predicates == parse_rule(seed).predicates
    assert result["lifecycle"]["state"] == "candidate"
    assert result["lifecycle"]["evidence"] == []
    assert result["formalization_requires_review"] is True
    assert result["automatic_equivalence"] is False
    assert result["compiled_summary"]["window"] == {
        "start": "2026-08-05",
        "end": "2026-09-01",
    }
    assert result["compiled_summary"]["predicate_count"] == 3
    assert result["source_context"]["case"]["exposed_sample_refs"] == [
        "query-1",
        "query-failure",
    ]
    assert json.loads(rule.raw["notes"])["hypothesis"]["failed_sample_refs"] == [
        "query-failure"
    ]
    assert (
        result["next_action"]["writer"]
        == "intelligence.services.methodology_backtest.propose.write_rule_file"
    )
    assert (
        result["next_action"]["evaluator"]
        == "intelligence.services.methodology_backtest.runner.run_rule"
    )
    assert "history_labels" in result["required_inputs"]


def test_window_feature_is_not_silently_renamed_to_existing_label(case, seed):
    result = prepare(
        case,
        predicates=[
            {"label": "max_double_red_streak", "op": ">=", "value": 3, "lag": 0}
        ],
        success=seed["outcome"]["success"],
    )
    assert result["status"] == "unsupported_definition"
    assert result["rule_doc"] is None
    assert any(issue["path"].startswith("condition.all") for issue in result["issues"])


def test_unresolved_operator_blocks_candidate_even_with_other_legal_predicates(
    case, seed
):
    raw = case.to_dict()
    raw["hypotheses"][0]["unresolved_definitions"] = ["个股弱转强跨日序列"]
    changed = ResearchCase.from_dict(raw)
    result = prepare(
        changed, predicates=seed["condition"]["all"], success=seed["outcome"]["success"]
    )
    assert result["status"] == "unsupported_definition"
    assert result["rule_doc"] is None
    assert result["source_context"]["hypothesis"]["unresolved_definitions"] == [
        "个股弱转强跨日序列"
    ]


def test_missing_window_is_needs_data_and_rule_id_is_not_allocated(case, seed):
    raw = case.to_dict()
    raw["window_start"] = raw["window_end"] = None
    result = prepare(
        ResearchCase.from_dict(raw),
        predicates=seed["condition"]["all"],
        success=seed["outcome"]["success"],
    )
    assert result["status"] == "needs_data"
    assert result["compiled_summary"] is None
    assert result["rule_doc"]["rule_id"] == "agriculture_dual_red_candidate"
    assert "resolved_research_window" in result["required_inputs"]
    with pytest.raises(ValueError, match="rule_id"):
        prepare_methodology_candidate(
            case, "h-1", owner="researcher", rule_id="R-123", entity_type="sector"
        )
