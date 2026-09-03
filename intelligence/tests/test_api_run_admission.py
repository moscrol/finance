"""run 准入与排队（多用户内测前置）。

覆盖：每用户并发上限 429、系统队列上限 429 + Retry-After、排队不计时（期限从真正
开跑起算）、排队中取消不执行、重启恢复绕过准入、预检/复核竞态时配额退回、
env 解析 fail-fast。
"""

import threading
import time
from collections.abc import Callable

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api import app as app_module  # noqa: E402
from intelligence.api.app import RunSupervisor  # noqa: E402
from intelligence.api.quota import RunQuota  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("条件未在超时内成立")


def _status(client: TestClient, run_id: str, user: str) -> str:
    return client.get(f"/api/runs/{run_id}", params={"user": user}).json()["status"]


class _Gate:
    """假 runner：记录开跑时刻与当时的 deadline，卡住直到测试放行。"""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started_at: dict[str, float] = {}
        self.deadline_at_start: dict[str, float | None] = {}
        self._lock = threading.Lock()

    def run_ask(self, store: RunStore, run_id: str, req) -> None:
        with self._lock:
            self.started_at[run_id] = time.monotonic()
        self.release.wait(timeout=10)
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    def conversation_turn(self, **kwargs: object) -> None:
        run_id = str(kwargs["run_id"])
        signal = kwargs["cancellation_signal"]
        with self._lock:
            self.started_at[run_id] = time.monotonic()
            self.deadline_at_start[run_id] = signal.deadline_expires_at  # type: ignore[attr-defined]
        self.release.wait(timeout=10)
        kwargs["run_store"].finish_run(run_id, rs.STATUS_COMPLETED)  # type: ignore[attr-defined]


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "owner")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    monkeypatch.delenv("WORKBENCH_AUTH_MODE", raising=False)
    for name in (
        app_module.ENV_RUN_WORKERS,
        app_module.ENV_MAX_ACTIVE_RUNS_PER_USER,
        app_module.ENV_MAX_QUEUED_RUNS,
    ):
        monkeypatch.delenv(name, raising=False)

    gate = _Gate()
    monkeypatch.setattr(app_module, "_run_ask", gate.run_ask)
    monkeypatch.setattr(app_module, "_run_conversation_turn", gate.conversation_turn)
    clients: list[TestClient] = []

    def build(supervisor: RunSupervisor, quota: RunQuota | None = None) -> TestClient:
        client = TestClient(
            app_module.create_app(
                repo_root=repo_root,
                run_supervisor=supervisor,
                run_quota=quota,
            )
        )
        clients.append(client)
        return client

    class _Harness:
        pass

    h = _Harness()
    h.build = build  # type: ignore[attr-defined]
    h.gate = gate  # type: ignore[attr-defined]
    yield h
    gate.release.set()
    for client in clients:
        client.app.state.supervisor.shutdown()


def _post_run(client: TestClient, user: str, question: str = "q"):
    return client.post("/api/runs", json={"question": question, "user": user})


def test_per_user_limit_rejects_second_active_run_and_frees_after_completion(harness):
    client = harness.build(
        RunSupervisor(max_workers=4, timeout_sec=30, max_active_runs_per_user=1)
    )
    first = _post_run(client, "u1")
    assert first.status_code == 200
    run1 = first.json()["run_id"]
    _wait_for(lambda: run1 in harness.gate.started_at)

    second = _post_run(client, "u1")
    assert second.status_code == 429
    assert "在进行中" in second.json()["detail"]
    assert second.headers["retry-after"] == "15"
    # 预检拒掉的请求不留 run 记录
    assert [run.run_id for run in RunStore(user_id="u1").list_runs()] == [run1]

    # 别的用户不受 u1 的上限影响
    assert _post_run(client, "u2").status_code == 200

    harness.gate.release.set()
    _wait_for(lambda: _status(client, run1, "u1") == "completed")
    assert _post_run(client, "u1").status_code == 200


def test_exempt_user_skips_per_user_cap_but_not_queue_bound(harness):
    client = harness.build(
        RunSupervisor(
            max_workers=2,
            timeout_sec=30,
            max_active_runs_per_user=1,
            max_queued_runs=0,
            exempt_users=frozenset({"owner"}),
        )
    )
    first = _post_run(client, "owner").json()["run_id"]
    _wait_for(lambda: first in harness.gate.started_at)
    # owner 不受每用户上限约束：第二个照收
    assert _post_run(client, "owner").status_code == 200
    # 但两个 worker 都被 owner 占满、队列为 0 → 系统上限对 owner 同样生效
    third = _post_run(client, "owner")
    assert third.status_code == 429
    assert "系统繁忙" in third.json()["detail"]
    harness.gate.release.set()


def test_full_queue_rejects_with_retry_after_and_recovers(harness):
    client = harness.build(
        RunSupervisor(max_workers=1, timeout_sec=30, max_queued_runs=0)
    )
    run1 = _post_run(client, "u1").json()["run_id"]
    _wait_for(lambda: run1 in harness.gate.started_at)

    busy = _post_run(client, "u2")
    assert busy.status_code == 429
    assert "系统繁忙" in busy.json()["detail"]
    assert busy.headers["retry-after"] == "30"

    readiness = client.get("/api/readiness").json()["workers"]
    assert (readiness["active"], readiness["queued"], readiness["capacity"]) == (
        1,
        0,
        1,
    )
    assert readiness["max_queued"] == 0

    harness.gate.release.set()
    _wait_for(lambda: _status(client, run1, "u1") == "completed")
    assert _post_run(client, "u2").status_code == 200


def test_queued_run_deadline_starts_when_it_actually_runs(harness):
    timeout_sec = 20.0
    client = harness.build(
        RunSupervisor(max_workers=1, timeout_sec=timeout_sec, max_queued_runs=1)
    )
    conversation = client.post(
        "/api/conversations", json={"title": "排队", "user": "u1"}
    ).json()["conversation_id"]

    def send(content: str):
        return client.post(
            f"/api/conversations/{conversation}/messages",
            json={"content": content, "skill_mode": "auto", "user": "u1"},
        )

    run1 = send("第一问").json()["run_id"]
    _wait_for(lambda: run1 in harness.gate.started_at)

    submitted_at = time.monotonic()
    queued = send("第二问")
    assert queued.status_code == 202
    run2 = queued.json()["run_id"]
    assert _status(client, run2, "u1") == "queued"
    registry = client.app.state.cancellation_registry
    assert registry[("u1", run2)].deadline_expires_at is None, "排队中不得计时"

    time.sleep(0.4)
    harness.gate.release.set()
    _wait_for(lambda: run2 in harness.gate.started_at)
    started_at = harness.gate.started_at[run2]
    deadline = harness.gate.deadline_at_start[run2]
    assert deadline is not None
    # 期限锚在开跑时刻，而不是提交时刻：排队那 0.4s 没有被吃掉
    assert abs((deadline - started_at) - timeout_sec) < 0.5
    assert deadline > submitted_at + timeout_sec + 0.3
    _wait_for(lambda: _status(client, run2, "u1") == "completed")


def test_cancel_queued_run_never_executes(harness):
    client = harness.build(
        RunSupervisor(max_workers=1, timeout_sec=30, max_queued_runs=2)
    )
    run1 = _post_run(client, "u1").json()["run_id"]
    _wait_for(lambda: run1 in harness.gate.started_at)
    run2 = _post_run(client, "u2").json()["run_id"]
    assert _status(client, run2, "u2") == "queued"

    cancelled = client.post(f"/api/runs/{run2}/cancel", params={"user": "u2"})
    assert cancelled.json()["status"] == "cancelled"

    harness.gate.release.set()
    _wait_for(lambda: _status(client, run1, "u1") == "completed")
    time.sleep(0.1)
    assert run2 not in harness.gate.started_at
    assert _status(client, run2, "u2") == "cancelled"


def test_restart_recovery_resubmits_runs_beyond_per_user_limit(harness):
    # 崩溃前同一用户有两个在途 run；恢复时不得因每用户上限=1 丢掉其一
    store = RunStore(user_id="u1")
    stale = [store.create_run(f"q{i}", "ask").run_id for i in range(2)]

    client = harness.build(
        RunSupervisor(max_workers=2, timeout_sec=30, max_active_runs_per_user=1)
    )
    assert sorted(client.app.state.recovered_runs) == sorted(stale)
    _wait_for(lambda: all(run_id in harness.gate.started_at for run_id in stale))
    harness.gate.release.set()
    for run_id in stale:
        _wait_for(lambda run_id=run_id: _status(client, run_id, "u1") == "completed")


def test_lost_admission_race_refunds_quota_and_terminalizes_run(harness, monkeypatch):
    """预检放行、_submit 原子复核拒收：run 记终态，配额退回，用户没白扣一次。"""
    supervisor = RunSupervisor(
        max_workers=4, timeout_sec=30, max_active_runs_per_user=1
    )
    client = harness.build(supervisor, quota=RunQuota(daily_limit=2))
    run1 = _post_run(client, "u1").json()["run_id"]
    _wait_for(lambda: run1 in harness.gate.started_at)

    monkeypatch.setattr(supervisor, "check_admission", lambda user_id: None)
    lost = _post_run(client, "u1")
    assert lost.status_code == 429
    runs = {run.run_id: run for run in RunStore(user_id="u1").list_runs()}
    rejected = next(run for run_id, run in runs.items() if run_id != run1)
    assert (rejected.status, rejected.error) == ("failed", "admission_rejected")

    harness.gate.release.set()
    _wait_for(lambda: _status(client, run1, "u1") == "completed")
    # 配额 2 次：run1 用 1 次，被拒那次已退回 → 还能再来 1 次，第 3 次才 429
    assert _post_run(client, "u1").status_code == 200
    denied = _post_run(client, "u1")
    assert denied.status_code == 429
    assert "今日研究次数已用完" in denied.json()["detail"]


def test_conversation_path_rejection_terminalizes_pending_assistant_message(harness):
    client = harness.build(
        RunSupervisor(max_workers=4, timeout_sec=30, max_active_runs_per_user=1)
    )
    conversation = client.post(
        "/api/conversations", json={"title": "并发", "user": "u1"}
    ).json()["conversation_id"]

    def send(content: str):
        return client.post(
            f"/api/conversations/{conversation}/messages",
            json={"content": content, "skill_mode": "auto", "user": "u1"},
        )

    run1 = send("第一问").json()["run_id"]
    _wait_for(lambda: run1 in harness.gate.started_at)
    rejected = send("第二问")
    assert rejected.status_code == 429
    messages = client.get(
        f"/api/conversations/{conversation}/messages", params={"user": "u1"}
    ).json()
    # 预检拒掉：不写用户消息、不留 pending 助手气泡
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[-1]["run_id"] == run1
    harness.gate.release.set()


def test_from_env_parses_and_fails_fast():
    configured = RunSupervisor.from_env(
        timeout_sec=5,
        env={
            app_module.ENV_RUN_WORKERS: "3",
            app_module.ENV_MAX_ACTIVE_RUNS_PER_USER: "1",
            app_module.ENV_MAX_QUEUED_RUNS: "0",
            app_module.ENV_EXEMPT_USERS: "owner, ops ",
        },
    )
    try:
        assert configured.max_workers == 3
        assert configured.max_active_runs_per_user == 1
        assert configured.max_queued_runs == 0
        assert configured.exempt_users == frozenset({"owner", "ops"})
    finally:
        configured.shutdown()

    defaults = RunSupervisor.from_env(timeout_sec=5, env={})
    try:
        assert defaults.max_workers == app_module._WORKER_COUNT
        assert defaults.max_active_runs_per_user == 0
        assert defaults.max_queued_runs is None
    finally:
        defaults.shutdown()

    with pytest.raises(ValueError):
        RunSupervisor.from_env(env={app_module.ENV_RUN_WORKERS: "0"})
    with pytest.raises(ValueError):
        RunSupervisor.from_env(env={app_module.ENV_MAX_QUEUED_RUNS: "many"})
