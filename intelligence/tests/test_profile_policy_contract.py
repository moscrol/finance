"""Resource settings must not select semantic policy or certify model quality."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from intelligence.services import agent_research, model_profile
from intelligence.services.turn_controller import decide_turn


@pytest.fixture
def gate_module():
    path = Path(__file__).resolve().parents[2] / "scripts/harness_tier_gate.py"
    spec = importlib.util.spec_from_file_location("profile_contract_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("FWP_MODEL_PROFILE", "FWP_RESOURCE_PROFILE", "ASK_AGENT_MAX_STEPS"):
        monkeypatch.delenv(key, raising=False)


def test_legacy_frontier_no_longer_selects_semantic_policy(monkeypatch):
    reply = json.dumps({"route_id": "chat", "subject": None, "timeframe": None,
                        "confidence": 0.42, "reason": "fixed offline response"})
    def complete(_):
        return reply, object(), ""
    baseline = decide_turn("随便聊聊未来", llm_complete=complete).to_dict()
    monkeypatch.setenv("FWP_MODEL_PROFILE", "frontier")
    assert decide_turn("随便聊聊未来", llm_complete=complete).to_dict() == baseline


def test_resource_profile_has_no_semantic_or_escalation_fields():
    assert not ({"route_authority", "escalation_eligible"} & model_profile.active_profile().to_dict().keys())


def test_explicit_resource_budget_available_without_model_tier(monkeypatch):
    monkeypatch.setenv("FWP_RESOURCE_PROFILE", "expanded")
    assert agent_research.max_steps() == 8


@pytest.mark.parametrize("raw", ["standard", "", "unknown"])
def test_explicit_resource_setting_does_not_fall_through_to_legacy_frontier(monkeypatch, raw):
    monkeypatch.setenv("FWP_MODEL_PROFILE", "frontier")
    monkeypatch.setenv("FWP_RESOURCE_PROFILE", raw)
    assert agent_research.max_steps() == 4


def test_empty_model_arm_is_input_error(gate_module):
    with pytest.raises(gate_module.GateInputError):
        gate_module.gate({"a": False}, {"a": True}, {}, {})


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None, [], {}])
def test_score_values_are_exact_booleans(gate_module, value):
    with pytest.raises(gate_module.GateInputError):
        gate_module.case_outcomes({"cases": {"a": value}})


@pytest.mark.parametrize("report", [None, [], {"cases": {}}, {"cases": {"": True}}])
def test_malformed_or_empty_reports_are_rejected(gate_module, report):
    with pytest.raises(gate_module.GateInputError):
        gate_module.case_outcomes(report)


def test_direct_api_cannot_bypass_boolean_validation(gate_module):
    with pytest.raises(gate_module.GateInputError):
        gate_module.gate({"a": "false"}, {"a": True}, {"a": True}, {"a": True})


def test_all_four_arms_need_same_case_ids(gate_module):
    with pytest.raises(gate_module.GateInputError):
        gate_module.gate({"a": False}, {"a": True}, {"b": True}, {"b": True})


def test_score_improvement_does_not_prove_generic_benefit(gate_module):
    result = gate_module.gate({"a": False}, {"a": True}, {"a": True}, {"a": True})
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["scope"] == "paired_case_score_comparison_only"
    assert result["acceptance"] == "not_established"
    assert "cost_and_latency" in result["missing_evidence"]


def test_regression_not_hidden_by_equal_net_score(gate_module):
    result = gate_module.gate({"a": True, "b": False}, {"a": False, "b": True},
                              {"a": True, "b": True}, {"a": True, "b": True})
    assert result["verdict"] == "FAIL"
    assert result["weak"]["broken"] == ["a"]


def test_summary_counters_must_agree(gate_module):
    from intelligence.eval import content_correctness as cc
    n = len(cc.load_cases())
    with pytest.raises(gate_module.GateInputError):
        gate_module.case_outcomes({"total": n, "passed": n - 1, "failures": {}})


def test_duplicate_json_case_id_rejected(gate_module, tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"cases":{"a":false,"a":true}}')
    with pytest.raises(gate_module.GateInputError):
        gate_module._load(path, "duplicate")


def test_cli_inconclusive_is_not_success(gate_module, tmp_path):
    args = ["check", "--json"]
    for name, value in [("weak-base", False), ("weak-new", True),
                        ("strong-base", True), ("strong-new", True)]:
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps({"cases": {"a": value}}))
        args += ["--" + name, str(p)]
    assert gate_module.main(args) == 3



def test_all_empty_arms_are_input_error(gate_module):
    with pytest.raises(gate_module.GateInputError):
        gate_module.gate({}, {}, {}, {})


def test_both_score_improvements_still_do_not_certify_generic_benefit(gate_module):
    result = gate_module.gate({"a": False}, {"a": True}, {"a": False}, {"a": True})
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["weak"]["net"] == result["strong"]["net"] == 1


def test_mixed_report_formats_cannot_hide_conflicting_summary(gate_module):
    with pytest.raises(gate_module.GateInputError):
        gate_module.case_outcomes({"cases": {"a": True}, "total": 1, "passed": 0, "failures": {}})
