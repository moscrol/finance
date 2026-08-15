"""ResearchProfile 接缝：吸收 GroundedBudgetProfile + effective-config 收据。

对应 spec §7.5。本轮验的是信封本身的不变量，以及 conversation 入口
改走 ``profile_named("deep-research").execution_policy()`` 这一处接线。
ask 入口仍直接持有 ``grounded_deep``，不在本文件范围。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.runtime.agent_runtime_factory import (
    DEFAULT_RUNTIME_BACKEND as FACTORY_DEFAULT_BACKEND,
    RUNTIME_BACKEND_NAMES as FACTORY_BACKEND_NAMES,
)
from intelligence.services.repair_coordinator import max_repair_cycles_for_tier
from intelligence.services.research_policy import (
    GroundedBudgetProfile,
    ResearchExecutionPolicy,
    grounded_deep,
)
from intelligence.services.research_profile import (
    CONTINUOUS_VERIFIER_CHAIN,
    DEFAULT_RUNTIME_BACKEND,
    PROFILE_NAMES,
    RESEARCH_PROFILES,
    RUNTIME_BACKEND_NAMES,
    ResearchProfileError,
    profile_field_names,
    profile_named,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_PY = REPO_ROOT / "intelligence" / "api" / "app.py"


def test_catalog_has_exactly_the_spec_names() -> None:
    assert set(RESEARCH_PROFILES) == PROFILE_NAMES
    assert PROFILE_NAMES == {
        "quick-research",
        "deep-research",
        "daily-review",
        "read-only",
        "benchmark",
        "headless",
    }


def test_profile_named_returns_catalog_identity() -> None:
    first = profile_named("deep-research")
    assert first is RESEARCH_PROFILES["deep-research"]
    assert profile_named("deep-research") is first


def test_unknown_profile_name_raises() -> None:
    with pytest.raises(ResearchProfileError, match="unknown research profile"):
        profile_named("mystery-research")


def test_deep_research_holds_the_existing_grounded_deep_object() -> None:
    profile = profile_named("deep-research")
    assert profile.budget is grounded_deep
    policy = profile.execution_policy()
    assert policy.grounded_budget_profile is grounded_deep
    assert policy.max_elapsed_seconds == grounded_deep.root_seconds
    assert policy.synthesis_reserve_seconds == grounded_deep.synthesis_reserve_seconds


def test_profiles_without_budget_use_execution_policy_defaults() -> None:
    policy = profile_named("quick-research").execution_policy()
    default = ResearchExecutionPolicy()
    assert policy == default
    assert policy.grounded_budget_profile is None


def test_profile_does_not_grow_its_own_budget_numbers() -> None:
    """第二配置源的形状：把别人的秒数抄成自己的字段。"""

    stolen = {
        "root_seconds",
        "synthesis_reserve_seconds",
        "child_seconds",
        "composer_grant_seconds",
        "judge_reserve_seconds",
        "minimum_two_phase_entry_seconds",
        "target_seconds",
        "total_seconds",
        "max_repair_cycles",
        "max_elapsed_seconds",
    }
    assert stolen.isdisjoint(profile_field_names())


def test_repair_cycles_are_derived_from_the_existing_tier_function() -> None:
    deep = profile_named("deep-research").dump_effective_config()
    quick = profile_named("quick-research").dump_effective_config()
    assert deep["repair_max_cycles"] == max_repair_cycles_for_tier("deep")
    assert quick["repair_max_cycles"] == max_repair_cycles_for_tier("quick")
    assert deep["repair_max_cycles_source"] == "max_repair_cycles_for_tier"


def test_dump_exposes_grounded_deep_provenance() -> None:
    dump = profile_named("deep-research").dump_effective_config()
    budget = dump["grounded_budget_profile"]
    assert isinstance(budget, dict)
    assert budget["name"] == "grounded_deep"
    assert budget["measurement_basis"] == grounded_deep.measurement_basis
    assert dump["execution_policy"]["grounded_budget_profile_name"] == "grounded_deep"
    assert dump["provider_source"] == "ambient"
    assert dump["allowed_tools_source"] == "contract"
    assert dump["output_contract_source"] == "owner"
    assert dump["verifier_chain"] == list(CONTINUOUS_VERIFIER_CHAIN)
    assert dump["declared_overrides"] == []


def test_override_keeps_unmentioned_budget() -> None:
    """dsh 替换整行会让没写的字段消失；typed merge 必须留下 budget。"""

    base = profile_named("deep-research")
    changed = base.override(runtime_backend="sdk_glm")
    assert changed is not base
    assert changed.runtime_backend == "sdk_glm"
    assert changed.budget is grounded_deep
    assert changed.declared_overrides == ("runtime_backend",)
    dump = changed.dump_effective_config()
    assert dump["grounded_budget_profile"]["name"] == "grounded_deep"
    assert dump["declared_overrides"] == ["runtime_backend"]


def test_override_rejects_undeclared_fields() -> None:
    with pytest.raises(ResearchProfileError, match="undeclared override fields"):
        profile_named("deep-research").override(root_seconds=30)


def test_explicit_none_budget_is_a_declared_clear() -> None:
    changed = profile_named("deep-research").override(budget=None)
    assert changed.budget is None
    assert changed.execution_policy().grounded_budget_profile is None
    assert changed.declared_overrides == ("budget",)


def test_override_rejects_a_dict_budget() -> None:
    with pytest.raises(ResearchProfileError, match="GroundedBudgetProfile"):
        profile_named("deep-research").override(budget={"name": "fake", "root_seconds": 1})


def test_switching_to_headless_requires_explicit_benchmark_only() -> None:
    base = profile_named("deep-research")
    with pytest.raises(ResearchProfileError, match="benchmark-only"):
        base.override(runtime_backend="codex_headless")
    changed = base.override(
        runtime_backend="codex_headless",
        benchmark_only=True,
    )
    assert changed.benchmark_only is True
    assert changed.declared_overrides == ("runtime_backend", "benchmark_only")


def test_headless_catalog_entry_is_benchmark_only() -> None:
    profile = profile_named("headless")
    assert profile.runtime_backend == "codex_headless"
    assert profile.benchmark_only is True
    assert profile.budget is None


def test_read_only_catalog_entry_does_not_invent_a_tool_list() -> None:
    profile = profile_named("read-only")
    assert profile.read_only is True
    assert profile.allowed_tools is None
    assert profile.dump_effective_config()["allowed_tools_source"] == "contract"


def test_factory_backend_names_are_the_profile_set() -> None:
    assert FACTORY_BACKEND_NAMES is RUNTIME_BACKEND_NAMES
    assert FACTORY_DEFAULT_BACKEND == DEFAULT_RUNTIME_BACKEND
    assert RUNTIME_BACKEND_NAMES == {
        "continuous_glm",
        "sdk_glm",
        "sdk_gpt",
        "codex_headless",
    }


def test_conversation_entry_constructs_policy_from_deep_research_profile() -> None:
    source = APP_PY.read_text(encoding="utf-8")
    assert 'profile_named("deep-research").execution_policy()' in source
    assert "grounded_budget_profile=grounded_deep" not in source


def test_ad_hoc_budget_must_still_be_the_existing_type() -> None:
    other = GroundedBudgetProfile(
        name="other_measured",
        root_seconds=grounded_deep.root_seconds,
        synthesis_reserve_seconds=grounded_deep.synthesis_reserve_seconds,
        child_seconds=grounded_deep.child_seconds,
        composer_grant_seconds=grounded_deep.composer_grant_seconds,
        judge_reserve_seconds=grounded_deep.judge_reserve_seconds,
        minimum_two_phase_entry_seconds=grounded_deep.minimum_two_phase_entry_seconds,
        measurement_basis="test double; not a second production source",
    )
    changed = profile_named("deep-research").override(budget=other)
    assert changed.budget is other
    assert changed.budget is not grounded_deep
    assert changed.execution_policy().grounded_budget_profile is other
