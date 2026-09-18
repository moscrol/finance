"""Force late API workers to resolve runners during fixture teardown, not after it."""
from __future__ import annotations

import threading

import pytest

from intelligence.api import app as api_module
from intelligence.api.credits import CreditStore
from intelligence.tests import test_api_credits, test_api_quota, test_api_run_admission


@pytest.mark.parametrize("owner", ["quota", "credits", "admission"])
def test_api_fixture_joins_late_worker_before_restoring_runner(tmp_path, owner):
    entered = threading.Event()
    release = threading.Event()
    joined = threading.Event()
    calls = []
    fixture = None
    client = None
    with pytest.MonkeyPatch.context() as patch:
        execute = api_module.RunSupervisor._execute

        def delayed_execute(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test did not release its worker")
            return execute(*args, **kwargs)

        patch.setattr(api_module.RunSupervisor, "_execute", delayed_execute)
        factory = {
            "quota": test_api_quota.quota_client,
            "credits": test_api_credits.api,
            "admission": test_api_run_admission.harness,
        }[owner]
        try:
            fixture = factory.__wrapped__(tmp_path, patch)
            value = next(fixture)
            if owner == "quota":
                client = value
            elif owner == "credits":
                client = value(CreditStore(enabled=False))
            else:
                client = value.build(api_module.RunSupervisor(max_workers=1, timeout_sec=10))
            supervisor = client.app.state.supervisor
            fake_runner = api_module._run_ask

            def recording_fake(*args, **kwargs):
                calls.append("fixture_runner")
                return fake_runner(*args, **kwargs)

            patch.setattr(api_module, "_run_ask", recording_fake)
            shutdown = supervisor._executor.shutdown

            def controlled_shutdown(wait=True, *, cancel_futures=False):
                if wait:
                    joined.set()
                    release.set()
                return shutdown(wait=wait, cancel_futures=cancel_futures)

            patch.setattr(supervisor._executor, "shutdown", controlled_shutdown)
            response = client.post("/api/runs", json={"question": "q", "user": "owner"})
            assert response.status_code == 200
            assert entered.wait(5)
            assert calls == [], "worker must remain behind the deterministic gate"
            # Teardown must join while the fixture's runner/env patches still exist.
            with pytest.raises(StopIteration):
                next(fixture)
            assert joined.is_set(), "fixture restored dependencies without joining its worker"
            assert calls == ["fixture_runner"]
            assert supervisor.active_count() == 0
        finally:
            release.set()
            if fixture is not None:
                fixture.close()
            if client is not None:
                # Also drain deliberately broken variants before monkeypatch undo.
                client.app.state.supervisor.shutdown()
                client.app.state.supervisor._executor.shutdown(wait=True, cancel_futures=True)
                client.close()
