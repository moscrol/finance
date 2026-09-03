"""额度账本（赠送 + 月度充值）测试：消费顺序、过期、自动赠送、豁免、退款、
并发与跨进程不超卖、坏文件 fail closed、429 端点、余额端点、准入/日配额补偿、CLI。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence import userspace  # noqa: E402
from intelligence.api import app as app_module  # noqa: E402
from intelligence.api.credits import (  # noqa: E402
    KIND_GIFT,
    KIND_MONTHLY,
    CreditStore,
)
from intelligence.api.quota import RunQuota  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "workbench_credits.py"

T0 = datetime(2026, 9, 3, 6, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self, now: datetime = T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture()
def users_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "owner")
    return tmp_path


# ── 账本语义 ────────────────────────────────────────────────────────────────


def test_disabled_store_allows_everything_and_touches_nothing(users_env):
    store = CreditStore(enabled=False)
    for _ in range(3):
        decision = store.reserve("u1")
        assert decision.allowed and decision.reason == "disabled"
    assert not (userspace.user_space("u1").root / "credits.json").exists()


def test_no_grant_and_no_signup_gift_denies(users_env):
    store = CreditStore(enabled=True, signup_gift=0)
    denied = store.reserve("u1")
    assert not denied.allowed
    assert (denied.reason, denied.remaining) == ("exhausted", 0)


def test_signup_gift_is_granted_once_on_first_contact(users_env):
    store = CreditStore(enabled=True, signup_gift=2, clock=_Clock())
    assert store.reserve("u1").allowed
    assert store.reserve("u1").allowed
    assert not store.reserve("u1").allowed
    balance = store.balance("u1")
    assert balance.remaining == 0
    assert [g.kind for g in balance.grants] == [KIND_GIFT]
    assert balance.grants[0].expires_at is None
    # 用完之后不会因为「余额为 0」再送一次
    assert not store.reserve("u1").allowed
    assert len(store.balance("u1").grants) == 1


def test_consumes_soonest_expiring_grant_first_and_skips_expired(users_env):
    clock = _Clock()
    store = CreditStore(enabled=True, clock=clock)
    gift = store.grant("u1", KIND_GIFT, 5, note="赠送")
    month = store.grant(
        "u1", KIND_MONTHLY, 2, expires_at=T0 + timedelta(days=30), note="9 月"
    )
    stale = store.grant(
        "u1", KIND_MONTHLY, 9, expires_at=T0 - timedelta(seconds=1), note="已过期"
    )
    assert store.balance("u1").remaining == 7  # 过期的 9 不算

    first = store.reserve("u1")
    second = store.reserve("u1")
    assert (first.grant_id, second.grant_id) == (month.id, month.id)
    third = store.reserve("u1")
    assert third.grant_id == gift.id  # 月度用完才动不过期的赠送
    remaining = {g.id: g.remaining for g in store.balance("u1").grants}
    assert remaining == {gift.id: 4, month.id: 0, stale.id: 9}

    clock.now = T0 + timedelta(days=31)
    # 月度到期后即便有余量也不可用；赠送继续可用
    store.grant("u1", KIND_MONTHLY, 3, expires_at=T0 + timedelta(days=30))
    assert store.balance("u1").remaining == 4
    assert store.reserve("u1").grant_id == gift.id


def test_same_expiry_consumes_earlier_grant_first(users_env):
    clock = _Clock()
    store = CreditStore(enabled=True, clock=clock)
    older = store.grant("u1", KIND_GIFT, 1)
    clock.now = T0 + timedelta(minutes=1)
    newer = store.grant("u1", KIND_GIFT, 1)
    assert store.reserve("u1").grant_id == older.id
    assert store.reserve("u1").grant_id == newer.id


def test_exempt_user_bypasses_and_records_nothing(users_env):
    store = CreditStore(enabled=True, exempt_users=frozenset({"owner"}))
    for _ in range(3):
        decision = store.reserve("owner")
        assert decision.allowed and decision.reason == "exempt"
    assert store.balance("owner").exempt
    assert not (userspace.user_space("owner").root / "credits.json").exists()


def test_release_refunds_last_debit_to_its_grant_and_never_exceeds_amount(users_env):
    store = CreditStore(enabled=True)
    grant = store.grant("u1", KIND_GIFT, 1)
    assert store.reserve("u1").allowed
    assert not store.reserve("u1").allowed
    store.release("u1")
    assert store.balance("u1").remaining == 1
    store.release("u1")  # 没有可退的扣账：空操作，不得超过 amount
    assert store.balance("u1").grants[0].remaining == grant.amount == 1
    # 关闭 / 豁免：release 无副作用
    CreditStore(enabled=False).release("u1")
    CreditStore(enabled=True, exempt_users=frozenset({"u1"})).release("u1")
    assert store.balance("u1").remaining == 1


def test_revoke_zeroes_a_grant(users_env):
    store = CreditStore(enabled=True)
    grant = store.grant("u1", KIND_MONTHLY, 10, expires_at=T0 + timedelta(days=30))
    store.grant("u1", KIND_GIFT, 3)
    revoked = store.revoke("u1", grant.id, note="退款")
    assert revoked.remaining == 0
    assert store.balance("u1").remaining == 3
    with pytest.raises(KeyError):
        store.revoke("u1", "g-not-there")


def test_grant_validates_inputs(users_env):
    store = CreditStore(enabled=True)
    with pytest.raises(ValueError):
        store.grant("u1", "coupon", 1)
    with pytest.raises(ValueError):
        store.grant("u1", KIND_GIFT, 0)
    with pytest.raises(ValueError):
        store.grant("u1", KIND_GIFT, 1, expires_at=datetime(2026, 1, 1))  # naive


def test_corrupt_file_fails_closed_and_is_preserved(users_env):
    store = CreditStore(enabled=True, signup_gift=5)
    path = userspace.user_space("u1").root / "credits.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json{", encoding="utf-8")
    denied = store.reserve("u1")
    assert not denied.allowed
    assert denied.reason == "corrupt"
    # 钱的账本坏了不能当成空账本重建（那等于把别人的余额清零再送一次赠送）
    assert path.read_text(encoding="utf-8") == "not-json{"
    assert store.balance("u1").corrupt


def test_concurrent_reserve_never_oversells(users_env):
    store = CreditStore(enabled=True)
    store.grant("u1", KIND_GIFT, 5)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.reserve("u1").allowed, range(30)))
    assert sum(results) == 5


def test_two_store_instances_share_the_file_lock(users_env):
    """两个实例各有自己的线程锁，能护住账本的只剩文件锁——这就是 CLI 与服务进程同写一份账本的形状。"""
    a = CreditStore(enabled=True)
    b = CreditStore(enabled=True)
    a.grant("u1", KIND_GIFT, 10)
    hits: list[bool] = []
    lock = threading.Lock()

    def worker(store: CreditStore) -> None:
        for _ in range(20):
            ok = store.reserve("u1").allowed
            with lock:
                hits.append(ok)

    threads = [threading.Thread(target=worker, args=(s,)) for s in (a, b, a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(hits) == 10
    assert a.balance("u1").remaining == 0


_RESERVE_MANY = """
import sys
from intelligence.api.credits import CreditStore
store = CreditStore(enabled=True)
print(sum(1 for _ in range(int(sys.argv[1])) if store.reserve("u1").allowed))
"""


def test_cross_process_reserve_never_oversells(users_env):
    """四个真实进程同抢一份账本：文件锁在，总放行数恰等于余额。"""
    store = CreditStore(enabled=True)
    store.grant("u1", KIND_GIFT, 7)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _RESERVE_MANY, "6"],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    outputs = [p.communicate(timeout=60) for p in procs]
    assert all(p.returncode == 0 for p in procs), [err for _, err in outputs]
    assert sum(int(out.strip()) for out, _ in outputs) == 7
    assert store.balance("u1").remaining == 0


def test_from_env_parses_and_fails_fast(monkeypatch):
    monkeypatch.setenv("WORKBENCH_CREDITS", "1")
    monkeypatch.setenv("WORKBENCH_CREDITS_SIGNUP_GIFT", "30")
    monkeypatch.setenv("WORKBENCH_QUOTA_EXEMPT_USERS", "owner, ops ")
    store = CreditStore.from_env()
    assert store.enabled and store.signup_gift == 30
    assert store.exempt_users == frozenset({"owner", "ops"})
    monkeypatch.delenv("WORKBENCH_CREDITS")
    assert not CreditStore.from_env().enabled
    monkeypatch.setenv("WORKBENCH_CREDITS", "1")
    monkeypatch.setenv("WORKBENCH_CREDITS_SIGNUP_GIFT", "many")
    with pytest.raises(ValueError):
        CreditStore.from_env()
    monkeypatch.setenv("WORKBENCH_CREDITS_SIGNUP_GIFT", "1")
    monkeypatch.setenv("WORKBENCH_CREDITS", "maybe")
    with pytest.raises(ValueError):
        CreditStore.from_env()


# ── API ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def api(tmp_path, monkeypatch):
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

    def fake_conversation_turn(**kwargs: object) -> None:
        kwargs["run_store"].finish_run(str(kwargs["run_id"]), rs.STATUS_COMPLETED)  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    monkeypatch.setattr(app_module, "_run_conversation_turn", fake_conversation_turn)
    clients: list[TestClient] = []

    def build(credits: CreditStore, quota: RunQuota | None = None) -> TestClient:
        client = TestClient(
            app_module.create_app(
                repo_root=repo_root, run_credits=credits, run_quota=quota
            )
        )
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.app.state.supervisor.shutdown()


def _post_run(client: TestClient, user: str):
    return client.post("/api/runs", json={"question": "q", "user": user})


def test_endpoint_gifts_then_denies_with_429(api):
    client = api(
        CreditStore(enabled=True, signup_gift=2, exempt_users=frozenset({"owner"}))
    )
    assert _post_run(client, "u1").status_code == 200
    assert _post_run(client, "u1").status_code == 200
    denied = _post_run(client, "u1")
    assert denied.status_code == 429
    assert "额度已用完" in denied.json()["detail"]
    assert "Retry-After" not in denied.headers  # 不是等一会就有，别让客户端自动重试
    for _ in range(3):
        assert _post_run(client, "owner").status_code == 200
    # 被拒的请求不留 run
    assert len(RunStore(user_id="u1").list_runs()) == 2


def test_balance_endpoint_and_bootstrap_summary(api):
    credits = CreditStore(
        enabled=True, signup_gift=0, exempt_users=frozenset({"owner"})
    )
    client = api(credits)
    credits.grant(
        "u1", KIND_MONTHLY, 3, expires_at=T0 + timedelta(days=30), note="9 月"
    )
    credits.grant("u1", KIND_GIFT, 2)
    assert _post_run(client, "u1").status_code == 200

    body = client.get("/api/credits", params={"user": "u1"}).json()
    assert body["user"] == "u1"
    assert (body["enabled"], body["exempt"], body["remaining"]) == (True, False, 4)
    assert [(g["kind"], g["remaining"], g["amount"]) for g in body["grants"]] == [
        (KIND_MONTHLY, 2, 3),
        (KIND_GIFT, 2, 2),
    ]
    assert body["next_expiry"] == (T0 + timedelta(days=30)).isoformat()
    assert body["grants"][0]["note"] == "9 月"
    assert "ledger" not in body  # 明细走 CLI，不给前端整本账

    owner = client.get("/api/credits", params={"user": "owner"}).json()
    assert owner["exempt"] and owner["remaining"] is None

    bootstrap = client.get("/api/workbench/bootstrap", params={"user": "u1"}).json()
    assert bootstrap["credits"] == {
        "enabled": True,
        "exempt": False,
        "remaining": 4,
        "next_expiry": (T0 + timedelta(days=30)).isoformat(),
    }


def test_disabled_store_reports_disabled_and_never_blocks(api):
    client = api(CreditStore(enabled=False))
    for _ in range(3):
        assert _post_run(client, "u1").status_code == 200
    body = client.get("/api/credits", params={"user": "u1"}).json()
    assert body["enabled"] is False and body["remaining"] is None


def test_daily_quota_denial_refunds_the_credit(api):
    credits = CreditStore(enabled=True)
    credits.grant("u1", KIND_GIFT, 5)
    client = api(credits, quota=RunQuota(daily_limit=1))
    assert _post_run(client, "u1").status_code == 200
    denied = _post_run(client, "u1")
    assert denied.status_code == 429
    assert "今日研究次数已用完" in denied.json()["detail"]
    # 被日配额拦下的请求没得到服务：额度只扣了第一次那 1 个
    assert credits.balance("u1").remaining == 4


def test_lost_admission_race_refunds_the_credit(api, monkeypatch):
    credits = CreditStore(enabled=True)
    credits.grant("u1", KIND_GIFT, 2)
    client = api(credits)

    def reject(*args, **kwargs):
        raise app_module.RunAdmissionError("系统繁忙", retry_after_sec=30)

    monkeypatch.setattr(client.app.state.supervisor, "submit", reject)
    rejected = _post_run(client, "u1")
    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "30"
    assert credits.balance("u1").remaining == 2
    run = RunStore(user_id="u1").list_runs()[0]
    assert (run.status, run.error) == ("failed", "admission_rejected")


def test_conversation_path_is_metered_too(api):
    credits = CreditStore(enabled=True, signup_gift=1)
    client = api(credits)
    conversation = client.post(
        "/api/conversations", json={"title": "额度", "user": "u1"}
    ).json()["conversation_id"]

    def send(content: str):
        return client.post(
            f"/api/conversations/{conversation}/messages",
            json={"content": content, "skill_mode": "auto", "user": "u1"},
        )

    assert send("q1").status_code == 202
    denied = send("q2")
    assert denied.status_code == 429
    assert "额度已用完" in denied.json()["detail"]
    # 被拒的那一问没有留下 pending 的助手气泡
    messages = client.get(
        f"/api/conversations/{conversation}/messages", params={"user": "u1"}
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]


# ── CLI ─────────────────────────────────────────────────────────────────────


def _cli(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        check=False,
    )


def test_cli_grant_balance_list_revoke_history(users_env):
    env = {"FORESIGHT_USERS_DIR": os.environ["FORESIGHT_USERS_DIR"]}
    granted = _cli(
        "grant",
        "--user",
        "u1",
        "--kind",
        "gift",
        "--runs",
        "30",
        "--note",
        "内测赠送",
        "--json",
        env=env,
    )
    assert granted.returncode == 0, granted.stderr
    gift = json.loads(granted.stdout)
    assert (gift["kind"], gift["amount"], gift["expires_at"]) == ("gift", 30, None)

    monthly = _cli(
        "grant", "--user", "u1", "--kind", "monthly", "--runs", "200", "--json", env=env
    )
    assert monthly.returncode == 0, monthly.stderr
    month = json.loads(monthly.stdout)
    assert month["kind"] == "monthly"
    expires = datetime.fromisoformat(month["expires_at"])
    assert (
        timedelta(days=29) < expires - datetime.now(timezone.utc) <= timedelta(days=30)
    )

    # 服务端账本读到 CLI 写的 grant，并按「先到期先用」扣月度
    store = CreditStore(enabled=True)
    assert store.reserve("u1").grant_id == month["id"]

    balance = _cli("balance", "--user", "u1", "--json", env=env)
    assert balance.returncode == 0, balance.stderr
    body = json.loads(balance.stdout)
    assert body["remaining"] == 229

    listed = _cli("list", "--json", env=env)
    assert listed.returncode == 0, listed.stderr
    rows = json.loads(listed.stdout)
    assert [(r["user"], r["remaining"]) for r in rows] == [("u1", 229)]

    revoked = _cli(
        "revoke", "--user", "u1", "--grant-id", month["id"], "--note", "退款", env=env
    )
    assert revoked.returncode == 0, revoked.stderr
    assert (
        json.loads(_cli("balance", "--user", "u1", "--json", env=env).stdout)[
            "remaining"
        ]
        == 30
    )

    history = _cli("history", "--user", "u1", "--json", env=env)
    assert history.returncode == 0, history.stderr
    reasons = [row["reason"] for row in json.loads(history.stdout)]
    assert reasons == ["grant", "grant", "run", "revoke"]

    bad = _cli("grant", "--user", "u1", "--kind", "gift", "--runs", "0", env=env)
    assert bad.returncode == 2
    human = _cli("balance", "--user", "u1", env=env)
    assert human.returncode == 0 and "30" in human.stdout


def test_cli_expires_flag_accepts_date(users_env):
    env = {
        "FORESIGHT_USERS_DIR": os.environ["FORESIGHT_USERS_DIR"],
        "TZ": "Asia/Shanghai",
    }
    out = _cli(
        "grant",
        "--user",
        "u2",
        "--kind",
        "monthly",
        "--runs",
        "5",
        "--expires",
        "2099-10-01",
        "--json",
        env=env,
    )
    assert out.returncode == 0, out.stderr
    expires = datetime.fromisoformat(json.loads(out.stdout)["expires_at"])
    assert expires.tzinfo is not None
    # 2099-10-01 00:00 上海 == 2099-09-30 16:00 UTC
    assert expires.astimezone(timezone.utc) == datetime(
        2099, 9, 30, 16, 0, tzinfo=timezone.utc
    )
