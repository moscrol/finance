from __future__ import annotations

import copy
import json

import pytest

from intelligence import userspace
from intelligence.services import perspective_exam as exam
from intelligence.services import perspective_lab as lab


@pytest.fixture
def profile():
    return {
        "id": "teacher", "display_name": "Teacher",
        "opportunity_preferences": ["容量机会"], "risk_triggers": ["库存风险"],
        "honest_boundaries": ["财务审计"],
    }


@pytest.mark.parametrize("value", [[], None, {}, False, "approved", [{"field": "opportunity_preferences"}]])
@pytest.mark.parametrize("entrypoint", ["evaluate", "exam", "debate"])
def test_rejected_contract_never_enters_judgment(profile, value, entrypoint):
    profile["signal_match_rules"] = value
    before = copy.deepcopy(profile)
    with pytest.raises(ValueError, match="audit-only"):
        if entrypoint == "evaluate":
            lab.evaluate_role(profile, question="财务审计", facts="容量机会")
        elif entrypoint == "exam":
            exam.score_case(profile, {
                "kind": "known_answer", "question": "观察什么", "facts": "容量机会",
                "expected_direction": "opportunity", "expected_field": "opportunity_preferences",
                "expected_terms": ["容量"],
            })
        else:
            lab._role_section(profile, facts="容量机会")
    assert profile == before


@pytest.mark.parametrize("allow_regression", [False, True])
def test_save_rejects_experiment_before_any_write(profile, tmp_path, monkeypatch, allow_regression):
    monkeypatch.setenv(userspace.ENV_USERS_DIR, str(tmp_path / "users"))
    us = userspace.user_space("alice")
    lab.init_perspective(us, "teacher")
    lab._save_profile(us, profile)
    before = {p: p.read_bytes() for p in us.root.rglob("*") if p.is_file()}
    profile["signal_match_rules"] = []
    incoming = copy.deepcopy(profile)
    with pytest.raises(ValueError, match="audit-only"):
        lab._save_profile(us, profile, allow_regression=allow_regression)
    assert profile == incoming
    assert {p: p.read_bytes() for p in us.root.rglob("*") if p.is_file()} == before


def test_accidental_manual_copy_cannot_pass_real_exam(profile, tmp_path, monkeypatch):
    monkeypatch.setenv(userspace.ENV_USERS_DIR, str(tmp_path / "users"))
    us = userspace.user_space("alice")
    lab.init_perspective(us, "teacher")
    profile["signal_match_rules"] = []
    lab.profile_path(us, "teacher").write_text(json.dumps(profile))
    exam.add_case(us, "teacher", kind="edge_case", question="财务审计")
    with pytest.raises(ValueError, match="audit-only"):
        exam.run_exam(us, "teacher")


@pytest.mark.parametrize("facts,direction", [("容量机会", "opportunity"), ("库存风险", "risk"),
    ("容量机会和库存风险", "mixed"), ("无可用事实", "none")])
def test_unconfigured_profile_keeps_existing_behavior(profile, facts, direction):
    result = lab.evaluate_role(profile, question="看法", facts=facts)
    assert result["direction"] == direction
    assert result["opportunity_hits"] == lab._hit_terms(profile["opportunity_preferences"], facts)
    assert result["risk_hits"] == lab._hit_terms(profile["risk_triggers"], facts)


def test_real_boundary_still_abstains(profile):
    result = lab.evaluate_role(profile, question="财务审计", facts="容量机会和库存风险")
    assert result["abstain"] and result["direction"] == "abstain"
    assert not result["opportunity_hits"] and not result["risk_hits"]
