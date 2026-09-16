"""consumption_registry.yaml 是分档同步的单一事实源；这里把它和管线钉在一起。

三条断言各拦一种漂移：
1. registry 自身合法（档位/表名在 schema/计划步骤有归属）——改 YAML 手滑当场红；
2. registry 的 plans 与 run_review_sync.build_plan 逐项同序——改了管线没改 YAML（或反过来）当场红；
3. public-assets 的 cheap 覆盖表与 registry 里 steps.cheap 为空的数据族一致——「停抓」两处说法必须同一份。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from market_feature_store.consumption_registry import (
    PLANS,
    TIERS,
    check_plan_against_pipeline,
    load_registry,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]
RUN_REVIEW_SYNC = ROOT / "skills" / "daily-full-review" / "scripts" / "run_review_sync.py"


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.fixture(scope="module")
def review_sync_module():
    spec = importlib.util.spec_from_file_location("run_review_sync_under_test", RUN_REVIEW_SYNC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_validates_against_schema(registry):
    assert validate_registry(registry) == []


def test_every_tier_has_members_and_every_dataset_has_a_tier(registry):
    by_tier = {tier: [d.key for d in registry.datasets if d.tier == tier] for tier in TIERS}
    assert all(by_tier.values()), by_tier
    assert {d.tier for d in registry.datasets} <= set(TIERS)


def test_plans_match_pipeline_step_names_in_order(registry, review_sync_module):
    problems = check_plan_against_pipeline(registry, review_sync_module.plan_step_names())
    assert problems == []


def test_cheap_plan_orders_value_sources_before_stitch(registry):
    cheap = list(registry.steps_for("cheap"))
    stitch = cheap.index("stitch-sector-stocks")
    for dependency in ("stock-daily", "stock-high", "limit-heat"):
        assert cheap.index(dependency) < stitch, f"{dependency} 必须先于 stitch（拼接行从它 join 值）"
    assert cheap.index("sector-stocks-delta") == stitch + 1
    assert cheap.index("sector-daily-local") > cheap.index("sector-stocks-delta")


def test_full_plan_unchanged_from_legacy_order(registry):
    assert registry.steps_for("full") == (
        "db-lock", "sectors", "market-overview", "index-daily", "sw-l1-daily", "market-deviation",
        "sector-daily", "sector-stocks", "limit-heat", "stock-high", "limit-advance", "stock-daily",
        "mainline-daily", "mainline-sector-daily", "theme-flow-daily", "public-assets", "features",
    )


def test_auto_plan_is_full_on_friday_only(review_sync_module):
    assert review_sync_module.resolve_plan("auto", "2026-09-04") == "full"  # 周五
    assert review_sync_module.resolve_plan("auto", "2026-09-07") == "cheap"  # 周一
    assert review_sync_module.resolve_plan("cheap", "2026-09-04") == "cheap"
    with pytest.raises(ValueError):
        review_sync_module.resolve_plan("weekly", "2026-09-04")


def test_public_assets_cheap_overrides_agree_with_registry(registry):
    from market_feature_store.sync import sync_fupanhui_public_assets as pa

    stopped_in_registry = {
        d.key for d in registry.datasets
        if "public-assets" in d.steps.get("full", ()) and not d.steps.get("cheap")
    }
    stopped_in_code = {name for name, override in pa.CHEAP_PLAN_OVERRIDES.items() if override is None}
    assert stopped_in_registry == stopped_in_code == {"auction"}
    cheap_names = [name for name, _ in pa.asset_syncs_for("cheap")]
    assert "auction" not in cheap_names
    assert dict(pa.asset_syncs_for("cheap"))["dragon_seats"] is pa.sync_dragon_seats_cheap
    assert [name for name, _ in pa.asset_syncs_for("full")] == [name for name, _ in pa.ASSET_SYNCS]


def test_known_plans_are_declared(registry):
    assert set(PLANS) <= set(registry.plans)


_RECIPE_PLACEHOLDERS = ("待编译", "待定义")


def test_recipe_status_matches_placeholder_state(registry):
    """status 与占位标记必须一致：没编译完不许改 status，编译完了不许留占位。

    原先只断言「至少有一条 pending-grilling」，三条 knowhow 全部编译（2026-09-04）后那条
    断言就变成永久红，且它守不住真正的漂法——把 status 改成 note 却把「待编译」留在 joins 里。
    这里按每条 recipe 的文本判：pending-grilling ⇔ 含占位。"""
    for r in registry.recipes:
        text = " ".join((*r.joins, r.proactive))
        has_placeholder = any(p in text for p in _RECIPE_PLACEHOLDERS)
        if r.status == "pending-grilling":
            assert has_placeholder, (
                f"recipe {r.key}: pending-grilling 却没有占位标记——编译进来了就改 status"
            )
        else:
            assert not has_placeholder, (
                f"recipe {r.key}: status={r.status} 但 joins/proactive 仍含「待编译/待定义」——"
                "没编译完不要改 status"
            )
        assert r.proactive.strip(), f"recipe {r.key}: proactive 不能为空（不主动就写 '-'）"
