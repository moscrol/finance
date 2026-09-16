"""Review I11 through real API and writers with an isolated synthetic user."""
from __future__ import annotations

import pytest

import intelligence.tests.research_evolution_fixtures as fx
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_research_evolution_rework import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    fx.install_env(monkeypatch, tmp_path)
    return World(tmp_path / "users", monkeypatch)


def test_i11_withdraw_logging_then_research_stops_product_measurement(world):
    for action in ("grant", "withdraw"):
        response = world.events([{
            "event_id": f"review-consent-{action}",
            "event_type": "consent_changed",
            "payload": {
                "consent_version": "review-consent-v1",
                "scopes": ["logging"],
                "effective_at": world.clock().isoformat(),
                "action": action,
                "terms_hash": "sha256:" + "f" * 64,
                "initiator": "user",
                "assistance_source": "workbench",
            },
        }])
        response.raise_for_status()
        assert response.json()["accepted"] == [f"review-consent-{action}"], response.text
        world.clock.advance(seconds=1)

    launched = world.client.post(
        f"/api/conversations/{world.conversation_id}/messages",
        json={"user": fx.OWNER, "content": "Continue research after logging withdrawal", "skill_mode": "hybrid"},
    )
    assert launched.status_code == 202, launched.text
    run_id = launched.json()["run_id"]
    assert world.wait_terminal(run_id)["status"] == "completed"
    events = EvolutionStore(world.user_root / "research_evolution", fx.OWNER).list_product_value_events()
    run_measurements = [e for e in events if run_id in e.get("run_ids", [])]
    print("I11", "consent_events", [e["payload"]["action"] for e in events if e["event_type"] == "consent_changed"],
          "research_status", "completed", "post_withdraw_measurements", [e["event_type"] for e in run_measurements])
    assert not run_measurements, "Withdrawing logging must stop optional product measurement while research remains usable"
