"""每用户每日 run 配额测试：预占语义、并发不超卖、豁免、跨天重置、429 端点行为。"""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence import userspace  # noqa: E402
from intelligence.api import app as app_module  # noqa: E402
from intelligence.api.quota import RunQuota  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402


@pytest.fixture()
def users_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "owner")
    return tmp_path


def test_zero_limit_means_unlimited(users_env):
    quota = RunQuota(daily_limit=0)
    for _ in range(5):
        assert quota.reserve("u1").allowed


def test_reserve_denies_after_limit(users_env):
    quota = RunQuota(daily_limit=2)
    assert quota.reserve("u1").allowed
    assert quota.reserve("u1").allowed
    denied = quota.reserve("u1")
    assert not denied.allowed
    assert (denied.used, denied.limit) == (2, 2)
    # 其他用户不受影响
    assert quota.reserve("u2").allowed


def test_exempt_user_bypasses(users_env):
    quota = RunQuota(daily_limit=1, exempt_users=frozenset({"owner"}))
    for _ in range(3):
        assert quota.reserve("owner").allowed
    assert quota.reserve("guest").allowed
    assert not quota.reserve("guest").allowed


def test_stale_date_resets(users_env):
    quota = RunQuota(daily_limit=1)
    state_path = userspace.user_space("u1").root / "run_quota.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"date": "2000-01-01", "used": 99}), encoding="utf-8"
    )
    assert quota.reserve("u1").allowed
    assert not quota.reserve("u1").allowed


def test_concurrent_reserve_never_oversells(users_env):
    """预占的意义所在：并发 check-then-act 不得超卖。"""
    quota = RunQuota(daily_limit=5)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: quota.reserve("u1").allowed, range(30)))
    assert sum(results) == 5


def test_release_refunds_one_slot_and_floors_at_zero(users_env):
    """release 只用于「预占后被准入拒收」的补偿；退到 0 之后再退是空操作。"""
    quota = RunQuota(daily_limit=1)
    assert quota.reserve("u1").allowed
    assert not quota.reserve("u1").allowed
    quota.release("u1")
    assert quota.reserve("u1").allowed
    quota.release("u1")
    quota.release("u1")  # 已是 0，不得变成负数
    assert quota.reserve("u1").allowed
    assert not quota.reserve("u1").allowed
    # 豁免用户与未启用配额：release 无副作用
    RunQuota(daily_limit=0).release("u1")
    RunQuota(daily_limit=1, exempt_users=frozenset({"owner"})).release("owner")


def test_corrupt_state_file_recovers(users_env):
    quota = RunQuota(daily_limit=1)
    state_path = userspace.user_space("u1").root / "run_quota.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not-json{", encoding="utf-8")
    assert quota.reserve("u1").allowed
    assert not quota.reserve("u1").allowed


def test_from_env_parses_and_fails_fast(monkeypatch):
    monkeypatch.setenv("WORKBENCH_DAILY_RUN_QUOTA", "7")
    monkeypatch.setenv("WORKBENCH_QUOTA_EXEMPT_USERS", "owner, ops ")
    quota = RunQuota.from_env()
    assert quota.daily_limit == 7
    assert quota.exempt_users == frozenset({"owner", "ops"})
    monkeypatch.setenv("WORKBENCH_DAILY_RUN_QUOTA", "abc")
    with pytest.raises(ValueError):
        RunQuota.from_env()


@pytest.fixture()
def quota_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "owner")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    monkeypatch.delenv("WORKBENCH_AUTH_MODE", raising=False)

    def fake_run_ask(store: RunStore, run_id: str, req) -> None:
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    return TestClient(
        app_module.create_app(
            repo_root=repo_root,
            run_quota=RunQuota(daily_limit=1, exempt_users=frozenset({"owner"})),
        )
    )


def test_endpoint_denies_with_429_after_limit(quota_client):
    first = quota_client.post("/api/runs", json={"question": "q1", "user": "u1"})
    assert first.status_code == 200
    second = quota_client.post("/api/runs", json={"question": "q2", "user": "u1"})
    assert second.status_code == 429
    assert "今日研究次数已用完" in second.json()["detail"]
    # 其他用户与豁免用户不受影响
    assert (
        quota_client.post(
            "/api/runs", json={"question": "q3", "user": "u2"}
        ).status_code
        == 200
    )
    for _ in range(2):
        assert (
            quota_client.post(
                "/api/runs", json={"question": "q4", "user": "owner"}
            ).status_code
            == 200
        )
