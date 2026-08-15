from __future__ import annotations

from intelligence.runtime.episode_tool_batch import tool_batch_timeout_seconds
from intelligence.services.episode_semantic_verifier import semantic_judge_window_seconds
from intelligence.services.research_contract import (
    ResearchPolicy,
    apply_env_ceiling,
    derive_stage_caps,
)


def test_derive_stage_caps_pins_current_tier_table() -> None:
    table = {
        "quick": derive_stage_caps(ResearchPolicy.for_tier("quick")),
        "standard": derive_stage_caps(ResearchPolicy.for_tier("standard")),
        "deep": derive_stage_caps(ResearchPolicy.for_tier("deep")),
    }
    assert table["quick"].tool_batch_seconds == 10.0
    assert table["standard"].tool_batch_seconds == 70.0
    assert table["deep"].tool_batch_seconds == 192.0
    assert table["deep"].judge_window_seconds == 50.0
    for tier, caps in table.items():
        policy = ResearchPolicy.for_tier(tier)
        assert caps.tool_batch_seconds + policy.synthesis_reserve == policy.total_seconds


def test_deep_caps_reproduce_arm_c_floors() -> None:
    caps = derive_stage_caps(ResearchPolicy.for_tier("deep"))
    assert caps.judge_window_seconds >= 25.0
    assert caps.tool_batch_seconds >= 60.0
    assert min(30.0, caps.judge_window_seconds * 0.5) >= 25.0


def test_standard_caps_stay_inside_total_and_protect_reserve() -> None:
    policy = ResearchPolicy.for_tier("standard")
    caps = derive_stage_caps(policy)
    assert policy.synthesis_reserve == 20.0
    assert caps.tool_batch_seconds + policy.synthesis_reserve == policy.total_seconds


def test_env_ceiling_can_only_lower_derived_cap(monkeypatch) -> None:
    monkeypatch.delenv("ASK_TOOL_BATCH_TIMEOUT", raising=False)
    derived = derive_stage_caps(ResearchPolicy.for_tier("standard")).tool_batch_seconds
    assert derived != 30.0
    assert apply_env_ceiling(derived, "ASK_TOOL_BATCH_TIMEOUT") == derived
    monkeypatch.setenv("ASK_TOOL_BATCH_TIMEOUT", "5")
    assert apply_env_ceiling(derived, "ASK_TOOL_BATCH_TIMEOUT") == 5.0
    monkeypatch.setenv("ASK_TOOL_BATCH_TIMEOUT", "999")
    assert apply_env_ceiling(derived, "ASK_TOOL_BATCH_TIMEOUT") == derived


def test_timeout_helpers_use_derived_caps_not_literals(monkeypatch) -> None:
    monkeypatch.delenv("ASK_TOOL_BATCH_TIMEOUT", raising=False)
    monkeypatch.delenv("ASK_SEMANTIC_JUDGE_WINDOW", raising=False)
    deep = ResearchPolicy.for_tier("deep")
    assert tool_batch_timeout_seconds(deep) == 192.0
    assert semantic_judge_window_seconds(deep) == 50.0
    monkeypatch.setenv("ASK_TOOL_BATCH_TIMEOUT", "60")
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE_WINDOW", "40")
    assert tool_batch_timeout_seconds(deep) == 60.0
    assert semantic_judge_window_seconds(deep) == 40.0
