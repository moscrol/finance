"""QC I11：撤回 ``logging`` 同意后研究照常可用，自用产品测量（run_started / run_finished / cost_recorded）不再落账。

三条一起才承重：撤回必需范围 → 不写；必需范围都在 → 照写；撤回无关范围 → 照写。
只测第一条会让「干脆永远不写」也变绿。
"""
from __future__ import annotations

import time

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def _consent(world: World, action: str, scopes: list[str], tag: str) -> None:
    event_id = f"i11-consent-{tag}-{action}"
    response = world.events([{
        "event_id": event_id,
        "event_type": "consent_changed",
        "payload": {
            "consent_version": "i11-consent-v1",
            "scopes": scopes,
            "effective_at": world.clock().isoformat(),
            "action": action,
            "terms_hash": "sha256:" + "f" * 64,
            "initiator": "user",
            "assistance_source": "workbench",
        },
    }])
    response.raise_for_status()
    assert response.json()["accepted"] == [event_id], response.text
    world.clock.advance(seconds=1)


def _run_once(world: World, text: str) -> str:
    launched = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": text, "skill_mode": "hybrid"},
    )
    assert launched.status_code == 202, launched.text
    run_id = launched.json()["run_id"]
    assert world.wait_terminal(run_id)["status"] == "completed"
    return run_id


def _measurements_for(world: World, run_id: str) -> list[str]:
    events = EvolutionStore(world.user_root / "research_evolution", fx.OWNER).list_product_value_events()
    return sorted(e["event_type"] for e in events if run_id in (e.get("run_ids") or []))


def _wait_measurements(world: World, run_id: str, expected: set[str], timeout: float = 10.0) -> list[str]:
    """终态 claim 与事件追加之间有毫秒级窗口——轮询到期望的事件类型都出现为止。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        seen = _measurements_for(world, run_id)
        if expected <= set(seen):
            return seen
        time.sleep(0.02)
    raise AssertionError(f"{sorted(expected)} 未在超时内落账，只见 {_measurements_for(world, run_id)}")


def test_withdraw_logging_stops_self_use_measurement_but_research_completes(world):
    _consent(world, "grant", ["research", "logging"], "a")
    _consent(world, "withdraw", ["logging"], "a")
    run_id = _run_once(world, "Continue research after logging withdrawal")
    # run_started 在 create_run 内同步写、早于 202 返回——它不在，说明门在 create 点就关了；
    # 终态事件在 claim 之后追加，给它一个窗口再断言，避免「还没来得及写」的假绿。
    time.sleep(0.5)
    assert _measurements_for(world, run_id) == []


def test_granted_required_scopes_keep_measurement_flowing(world):
    _consent(world, "grant", ["research", "logging"], "b")
    run_id = _run_once(world, "Research with consent in force")
    # cost_recorded 必须一起等：它在终态事件之后才追加，只等 run_finished 会在机器
    # 繁忙时抢在它前面返回（实测 load 44 的全量回归里偷发红，单跑则稳绿）。
    seen = _wait_measurements(world, run_id, {"run_started", "run_finished", "cost_recorded"})
    assert "cost_recorded" in seen  # 假 turn 记了 120 tokens → 终态多写一条 certainty=unknown 的成本


def test_withdrawing_an_unrelated_scope_does_not_stop_measurement(world):
    _consent(world, "grant", ["research", "logging", "blind_review"], "c")
    _consent(world, "withdraw", ["blind_review"], "c")
    run_id = _run_once(world, "Research after withdrawing an unrelated scope")
    _wait_measurements(world, run_id, {"run_started", "run_finished"})


def test_no_consent_record_keeps_self_use_default(world):
    run_id = _run_once(world, "Owner observing themselves without any consent record")
    _wait_measurements(world, run_id, {"run_started", "run_finished"})


def _timer(world: World, action: str, version: str) -> None:
    event_id = f"timer-{version}-{action}"
    response = world.events([{
        "event_id": event_id,
        "event_type": "consent_changed",
        "participant_id": fx.OWNER,
        "payload": {
            "consent_version": version,
            "scopes": ["research", "logging"] if version == "workbench-activity-v1" else ["activity-timer"],
            "effective_at": world.clock().isoformat(),
            "action": action,
            "terms_hash": "sha256:" + "a" * 64,
            "initiator": "user",
            "assistance_source": "workbench",
        },
    }])
    response.raise_for_status()
    assert response.json()["accepted"] == [event_id], response.text
    world.clock.advance(seconds=1)


@pytest.mark.parametrize("version", ["workbench-activity-v1", "workbench-activity-v2"])
@pytest.mark.parametrize("explicit_grant", [False, True])
def test_timer_stop_preserves_all_three_measurement_events(world, version, explicit_grant):
    if explicit_grant:
        _consent(world, "grant", ["research", "logging"], "measure")
    _timer(world, "grant", version)
    _timer(world, "withdraw", version)
    run_id = _run_once(world, "Research after stopping independent timer")
    assert _wait_measurements(world, run_id, {"run_started", "run_finished", "cost_recorded"}) == [
        "cost_recorded", "run_finished", "run_started",
    ]


@pytest.mark.parametrize("version", ["workbench-activity-v1", "workbench-activity-v2"])
def test_timer_start_does_not_reauthorize_withdrawn_measurement(world, version):
    _consent(world, "grant", ["research", "logging"], "measure")
    _consent(world, "withdraw", ["logging"], "revoke")
    _timer(world, "grant", version)
    run_id = _run_once(world, "Research still works without measurement consent")
    time.sleep(0.5)
    assert _measurements_for(world, run_id) == []
