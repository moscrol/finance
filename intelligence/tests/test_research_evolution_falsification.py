"""反向证伪：把接线打断，对应验收场景**必须**变红（spec 06 §7 末段）。

一个绿色的验收套件只说明「当前实现下断言成立」，不说明「断言咬得住」。这里逐个植入
spec 点名的三种偷懒实现，断言对应场景失败——失败本身就是这些测试的通过条件。

第四条是本轨自己发现的接缝：04 的结果身份不可解析时，揭示路径必须 fail closed。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from intelligence.tests import research_evolution_fixtures as fx  # noqa: E402
from intelligence.tests.test_research_evolution_api import (  # noqa: E402
    CONDITION_DOWNGRADE,
    World,
    test_i03_triggered_condition_ranks_first_and_rejudge_carries_scope_into_a_real_turn as i03,
    test_i06_unauthenticated_mode_refuses_arbitrary_user_switch as i06,
    test_i08_failed_run_cannot_be_laundered_into_a_closed_item as i08,
)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    return fx.install_env(monkeypatch, tmp_path)


def test_faking_the_maintenance_report_breaks_i03(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """偷懒实现①：不调 01，直接回一份固定的空报告。I03 必须失败。"""
    from intelligence.services.judgment_maintenance import MaintenanceReport

    def fixed_report(**kwargs: object) -> MaintenanceReport:
        return MaintenanceReport(
            id="jm-fixed",
            owner_user_id=str(kwargs["owner_user_id"]),
            as_of=str(kwargs["as_of"]),
            knowledge_cutoff=str(kwargs["knowledge_cutoff"]),
            input_digest="0" * 64,
            generated_at=str(kwargs.get("generated_at") or ""),
            pit_grade="unverifiable",
            hindsight=False,
            gaps=(),
            items=(),
            counts={"items_open": 0},
        )

    monkeypatch.setattr("intelligence.services.judgment_maintenance.assess", fixed_report)
    world = World(env)
    with pytest.raises(AssertionError):
        i03(world)


def test_dropping_the_owner_scope_check_breaks_i06(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """偷懒实现②：去掉归属校验，请求里的 ``user`` 直接当 owner。I06 必须失败。"""
    from intelligence.services.research_evolution.access import AccessPolicy

    monkeypatch.setattr(
        AccessPolicy,
        "resolve_owner",
        lambda self, requested_user: str(requested_user or self.configured_user),
    )
    world = World(env)
    with pytest.raises(AssertionError):
        i06(world)


def test_filtering_out_failed_runs_breaks_i08(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """偷懒实现③：把失败 run 当成没发生（只认 completed）。I08 必须失败。"""
    from intelligence.services.run_store import RunStore

    original = RunStore.load_run

    def only_successful(self: RunStore, run_id: str):
        run = original(self, run_id)
        if getattr(run, "status", "") == "failed":
            raise FileNotFoundError(run_id)
        return run

    monkeypatch.setattr(RunStore, "load_run", only_successful)
    world = World(env)
    with pytest.raises(AssertionError):
        i08(world)


def test_reveal_is_refused_when_the_outcome_identity_cannot_be_parsed(env: Path) -> None:
    """不透明结果身份 → 不揭示。凭空编一个实体与区间去登记曝光，比不登记更糟。"""
    world = World(env)
    world.register("diagnostics_policy", {"policy": fx.diagnostics_policy(), "provenance": "synthetic"})
    pack = fx.exercise_pack()
    for case in pack["cases"]:
        case["outcome_identity"] = "oc-opaque-001"
    world.register("exercise_pack", {"pack": pack, "provenance": "synthetic"})
    world.record_receipt(fx.coverage_receipt())

    exercise = world.view()["diagnostics"]["exercise"]
    assert exercise is not None, "本场景应当仍然出题（出题不依赖结果身份可解析）"
    response = world.act(action="reveal_exercise", idempotency_key="k-opaque", exercise_id=exercise["id"])
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "dependency_missing"

    from intelligence.services.research_validation import Repository

    repo = Repository(world.user_root / "research_validation", owner_user_id=fx.OWNER)
    assert repo.list_exposures() == [], "拒绝揭示时不得留下任何曝光记录"


def test_condition_wiring_is_live_not_a_constant(env: Path) -> None:
    """把盘面读数换掉，条件判定必须跟着变——否则说明它根本没读观测。"""
    triggered = World(env, market_stage="反弹")
    triggered.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    hit = [i for i in triggered.view()["maintenance"]["items"] if i["condition_result"] == "true"]
    assert hit and hit[0]["action"] == "rejudge"

    other = World(env, market_stage="主升")
    other.track_judgment(conditions=CONDITION_DOWNGRADE).raise_for_status()
    miss = [i for i in other.view()["maintenance"]["items"] if i["change_type"] == "condition_evaluated"]
    assert miss and miss[0]["condition_result"] == "false"
    assert miss[0]["action"] == "none"
