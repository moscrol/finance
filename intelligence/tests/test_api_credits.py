"""积分账本（赠送 + 月度充值，按真实用量结算）测试：定价公式、用量读取、预占/绑定/释放、
结算与欠账、消费顺序、过期、自动赠送、豁免、并发与跨进程不超卖、坏文件 fail closed、
429/余额端点、准入/日配额补偿、执行器终态结算、CLI。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
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
    POINTS_PER_YUAN,
    CreditPricing,
    CreditStore,
    RunUsage,
    read_run_usage,
)
from intelligence.api.quota import RunQuota  # noqa: E402
from intelligence.services import run_store as rs  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "workbench_credits.py"

T0 = datetime(2026, 9, 3, 6, 0, tzinfo=timezone.utc)

# 测试价目：markup 1、无底价、无最低消费、预占 100 分；default 档 1 元/M in、2 元/M out。
# 数字取整齐是为了让断言能手算；生产价目见 credits.py 默认值与 WORKBENCH_CREDITS_PRICING。
TEST_PRICING = CreditPricing.from_mapping(
    {
        "markup": "1",
        "base_fee_yuan": "0",
        "min_charge_yuan": "0",
        "hold_yuan": "1.00",
        "models": {
            "default": {"input_yuan_per_1m": "1", "output_yuan_per_1m": "2"},
            "glm-5.3": {"input_yuan_per_1m": "10", "output_yuan_per_1m": "20"},
        },
    },
    source="test",
)


class _Clock:
    def __init__(self, now: datetime = T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _store(**kwargs) -> CreditStore:
    kwargs.setdefault("enabled", True)
    kwargs.setdefault("pricing", TEST_PRICING)
    return CreditStore(**kwargs)


def _usage(inp: int, out: int, model: str = "glm-5.3", tool_calls: int = 0) -> RunUsage:
    return RunUsage({model: (inp, out)}, llm_calls=1, tool_calls=tool_calls)


@pytest.fixture()
def users_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "owner")
    return tmp_path


# ── 定价 ────────────────────────────────────────────────────────────────────


def test_points_per_yuan_is_fixed_at_100():
    assert POINTS_PER_YUAN == 100


def test_cost_formula_base_markup_tokens_tools_and_ceiling():
    pricing = CreditPricing.from_mapping(
        {
            "markup": "2",
            "base_fee_yuan": "0.10",
            "min_charge_yuan": "0.05",
            "tool_call_fee_yuan": "0.01",
            "models": {
                "default": {"input_yuan_per_1m": "3", "output_yuan_per_1m": "12"}
            },
        },
        source="t",
    )
    # 37256 in × 3 + 792 out × 12 = 0.1117680 + 0.0095040 = 0.121272 元 × 2 = 0.242544
    # + base 0.10 + 3 tool × 0.01 = 0.372544 元 → ceil(37.2544) = 38 分
    breakdown = pricing.cost(
        _usage(37256, 792, model="unknown-model", tool_calls=3), completed=True
    )
    assert breakdown.points == 38
    assert breakdown.rule == "metered"
    assert breakdown.by_model == {
        "unknown-model": {"input_tokens": 37256, "output_tokens": 792}
    }
    # 未知模型走 default 档：换成已登记的模型名才会变
    assert pricing.rate_for("unknown-model") is pricing.models["default"]


def test_cost_uses_model_specific_rate_and_sums_across_models():
    # glm-5.3: 100k in × 10 + 10k out × 20 = 1.0 + 0.2 = 1.2 元；default: 100k × 1 + 0 = 0.1 元
    usage = RunUsage({"glm-5.3": (100_000, 10_000), "gpt-x": (100_000, 0)}, llm_calls=2)
    breakdown = TEST_PRICING.cost(usage, completed=True)
    assert breakdown.points == 130
    assert breakdown.cost_yuan.startswith("1.3")


def test_min_charge_floors_metered_cost():
    pricing = CreditPricing.from_mapping(
        {
            "min_charge_yuan": "0.20",
            "models": {
                "default": {"input_yuan_per_1m": "1", "output_yuan_per_1m": "1"}
            },
        },
        source="t",
    )
    assert pricing.cost(_usage(10, 0), completed=True).points == 20


def test_free_when_no_usage_and_not_completed_but_base_fee_when_completed():
    pricing = CreditPricing.from_mapping(
        {
            "base_fee_yuan": "0.10",
            "models": {
                "default": {"input_yuan_per_1m": "1", "output_yuan_per_1m": "1"}
            },
        },
        source="t",
    )
    free = pricing.cost(None, completed=False)
    assert (free.points, free.rule) == (0, "free")
    base = pricing.cost(None, completed=True)
    assert (base.points, base.rule) == (10, "base_only")
    # 有 llm_calls 但没 token（provider 没回用量）：按无模型用量处理
    assert pricing.cost(RunUsage({}, llm_calls=2), completed=False).points == 0


def test_pricing_validation_and_env_loading(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        CreditPricing.from_mapping({"models": {}}, source="t")
    with pytest.raises(ValueError):
        CreditPricing.from_mapping(
            {
                "models": {
                    "default": {"input_yuan_per_1m": "-1", "output_yuan_per_1m": "1"}
                }
            },
            source="t",
        )
    with pytest.raises(ValueError):
        CreditPricing.from_mapping(
            {
                "markup": "two",
                "models": {
                    "default": {"input_yuan_per_1m": "1", "output_yuan_per_1m": "1"}
                },
            },
            source="t",
        )
    path = tmp_path / "pricing.json"
    path.write_text(
        json.dumps(
            {
                "hold_yuan": "0.5",
                "models": {
                    "default": {"input_yuan_per_1m": "1", "output_yuan_per_1m": "1"}
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WORKBENCH_CREDITS_PRICING", str(path))
    pricing = CreditPricing.from_env()
    assert (pricing.hold_points, pricing.source) == (50, str(path))
    monkeypatch.setenv("WORKBENCH_CREDITS_PRICING", str(tmp_path / "missing.json"))
    with pytest.raises(ValueError):
        CreditPricing.from_env()
    monkeypatch.delenv("WORKBENCH_CREDITS_PRICING")
    assert CreditPricing.from_env().source == "builtin-default"


def test_default_pricing_is_loadable_and_sane():
    pricing = CreditPricing.default()
    assert pricing.hold_points == 100  # 1 元
    observed = pricing.cost(
        _usage(37256, 792, model="glm-5.3", tool_calls=3), completed=True
    )
    assert (
        20 <= observed.points <= 60
    )  # 生产实测一次 run 的量级：几十分，不是几分也不是几百分


# ── 用量读取 ────────────────────────────────────────────────────────────────


def _write_episode(run_dir: Path, events: list[dict], usage: dict | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "continuous-episode.json").write_text(
        json.dumps({"events": events, "outcome": {"usage": usage}}), encoding="utf-8"
    )


def test_read_run_usage_groups_tokens_by_served_model(tmp_path):
    run_dir = tmp_path / "run_x"
    _write_episode(
        run_dir,
        [
            {
                "kind": "model_turn",
                "payload": {
                    "served_model": "glm-5.3",
                    "input_tokens": 100,
                    "output_tokens": 5,
                },
            },
            {
                "kind": "tool_request",
                "payload": {"input_tokens": 999},
            },  # 非模型事件不计
            {
                "kind": "model_turn",
                "payload": {
                    "served_model": "glm-5.3",
                    "input_tokens": 50,
                    "output_tokens": 5,
                },
            },
            {
                "kind": "branch_completed",
                "payload": {
                    "served_model": "gpt-x",
                    "input_tokens": 7,
                    "output_tokens": 1,
                },
            },
            {
                "kind": "model_turn",
                "payload": {"served_model": "glm-5.3"},
            },  # 没回用量：不编造
        ],
        {"llm_calls": 4, "tool_calls": 2, "input_tokens": 157, "output_tokens": 11},
    )
    usage = read_run_usage(run_dir)
    assert usage is not None
    assert dict(usage.tokens_by_model) == {"glm-5.3": (150, 10), "gpt-x": (7, 1)}
    assert (usage.llm_calls, usage.tool_calls) == (4, 2)
    assert (usage.input_tokens, usage.output_tokens) == (157, 11)


def test_read_run_usage_falls_back_to_outcome_totals_and_absence(tmp_path):
    run_dir = tmp_path / "run_y"
    _write_episode(
        run_dir,
        [],
        {"llm_calls": 1, "tool_calls": 0, "input_tokens": 300, "output_tokens": 20},
    )
    usage = read_run_usage(run_dir)
    assert usage is not None and dict(usage.tokens_by_model) == {"": (300, 20)}
    # 罐头答案：既没事件也没总量
    _write_episode(tmp_path / "run_z", [], {"llm_calls": 0, "tool_calls": 0})
    assert read_run_usage(tmp_path / "run_z") is None
    # 没有 episode 文件（legacy 路径）
    assert read_run_usage(tmp_path / "run_none") is None
    (tmp_path / "run_bad").mkdir()
    (tmp_path / "run_bad" / "continuous-episode.json").write_text("{", encoding="utf-8")
    assert read_run_usage(tmp_path / "run_bad") is None


# ── 预占 / 结算 / 欠账 ─────────────────────────────────────────────────────


def test_disabled_store_allows_everything_and_touches_nothing(users_env):
    store = CreditStore(enabled=False)
    for _ in range(3):
        assert store.reserve("u1").reason == "disabled"
    assert store.settle("u1", "run_1", _usage(1, 1), completed=True) is None
    assert not (userspace.user_space("u1").root / "credits.json").exists()


def test_no_grant_and_no_signup_gift_denies(users_env):
    denied = _store(signup_gift=0).reserve("u1")
    assert (denied.allowed, denied.reason, denied.available) == (False, "exhausted", 0)


def test_signup_gift_is_granted_once_on_first_contact(users_env):
    store = _store(signup_gift=2000, clock=_Clock())
    decision = store.reserve("u1")
    assert (
        decision.allowed and decision.hold_points == 100 and decision.available == 1900
    )
    balance = store.balance("u1")
    assert (balance.remaining, balance.holds) == (1900, 100)
    assert [g.kind for g in balance.grants] == [KIND_GIFT] and balance.grants[
        0
    ].amount == 2000
    # 结算释放预占并按用量扣：1.9 + 0.1 = 2.0 元 = 200 分
    store.bind_hold("u1", decision.hold_id, "run_1")
    store.settle("u1", "run_1", _usage(190_000, 5_000), completed=True)
    assert store.balance("u1").remaining == 1800
    # 用完之后不会因为「余额为 0」再送一次
    store.revoke("u1", balance.grants[0].id)
    assert not store.reserve("u1").allowed
    assert len(store.balance("u1").grants) == 1


def test_hold_reduces_available_until_settled_or_released(users_env):
    store = _store()
    store.grant("u1", KIND_GIFT, 150)
    first = store.reserve("u1")
    assert first.allowed and first.available == 50
    second = store.reserve("u1")  # 余额 50 > 0：还能占
    assert second.allowed and second.available == -50
    third = store.reserve("u1")  # 可用 ≤ 0：拒
    assert not third.allowed and third.reason == "exhausted"
    assert store.release_hold("u1", hold_id=second.hold_id) == 100
    assert store.balance("u1").remaining == 50
    store.bind_hold("u1", first.hold_id, "run_1")
    settlement = store.settle(
        "u1", "run_1", _usage(1_000, 0), completed=True
    )  # 0.01 元 = 1 分
    assert settlement is not None and (
        settlement.charged,
        settlement.hold_released,
    ) == (1, 100)
    assert store.balance("u1").remaining == 149
    assert store.balance("u1").holds == 0


def test_settle_consumes_soonest_expiring_grant_first_and_spans_grants(users_env):
    clock = _Clock()
    store = _store(clock=clock)
    gift = store.grant("u1", KIND_GIFT, 500, note="赠送")
    month = store.grant(
        "u1", KIND_MONTHLY, 30, expires_at=T0 + timedelta(days=30), note="9 月"
    )
    stale = store.grant("u1", KIND_MONTHLY, 900, expires_at=T0 - timedelta(seconds=1))
    assert store.balance("u1").remaining == 530  # 过期的 900 不算
    # 5 万 in + 0 out @ glm-5.3 = 0.5 元 = 50 分：先吃完月度 30，再动赠送 20
    settlement = store.settle("u1", "run_1", _usage(50_000, 0), completed=True)
    assert settlement is not None and settlement.charged == 50
    remaining = {g.id: g.remaining for g in store.balance("u1").grants}
    assert remaining == {gift.id: 480, month.id: 0, stale.id: 900}
    row = store.history("u1")[-1]
    assert row["reason"] == "run" and row["delta"] == -50
    assert row["allocations"] == [
        {"grant_id": month.id, "points": 30},
        {"grant_id": gift.id, "points": 20},
    ]
    assert row["usage"]["input_tokens"] == 50_000 and row["cost"]["rule"] == "metered"
    clock.now = T0 + timedelta(days=31)
    store.grant(
        "u1", KIND_MONTHLY, 300, expires_at=T0 + timedelta(days=30)
    )  # 到手即过期
    assert store.balance("u1").remaining == 480


def test_same_expiry_consumes_earlier_grant_first(users_env):
    clock = _Clock()
    store = _store(clock=clock)
    older = store.grant("u1", KIND_GIFT, 10)
    clock.now = T0 + timedelta(minutes=1)
    newer = store.grant("u1", KIND_GIFT, 10)
    store.settle("u1", "run_1", _usage(1_000, 0), completed=True)  # 1 分
    remaining = {g.id: g.remaining for g in store.balance("u1").grants}
    assert remaining == {older.id: 9, newer.id: 10}


def test_overrun_becomes_debt_blocks_admission_and_is_repaid_by_next_grant(users_env):
    store = _store()
    store.grant("u1", KIND_GIFT, 20)
    decision = store.reserve("u1")  # 余额 20 > 0，允许最后一问
    assert decision.allowed
    store.bind_hold("u1", decision.hold_id, "run_1")
    settlement = store.settle(
        "u1", "run_1", _usage(50_000, 0), completed=True
    )  # 0.5 元 = 50 分，余额只有 20
    assert settlement is not None and (settlement.charged, settlement.debt_after) == (
        50,
        30,
    )
    balance = store.balance("u1")
    assert (balance.remaining, balance.debt) == (-30, 30)
    denied = store.reserve("u1")
    assert not denied.allowed and denied.available == -30
    grant = store.grant("u1", KIND_MONTHLY, 100, expires_at=T0 + timedelta(days=30))
    assert grant.remaining == 70  # 先抵欠账
    after = store.balance("u1")
    assert (after.remaining, after.debt) == (70, 0)
    reasons = [row["reason"] for row in store.history("u1")]
    assert reasons[-2:] == ["grant", "debt_repaid"]
    assert store.reserve("u1").allowed


def test_settle_without_hold_still_charges_and_free_when_never_ran(users_env):
    store = _store()
    store.grant("u1", KIND_GIFT, 100)
    # 重启恢复的 run：没有预占记录也照实扣
    settlement = store.settle("u1", "run_recovered", _usage(2_000, 0), completed=True)
    assert settlement is not None and (
        settlement.charged,
        settlement.hold_released,
    ) == (2, 0)
    # 排队中被取消：没跑、没用量 → 0 分，不留 run 流水
    decision = store.reserve("u1")
    store.bind_hold("u1", decision.hold_id, "run_q")
    assert store.release_hold("u1", run_id="run_q") == 100
    settlement = store.settle("u1", "run_q", None, completed=False)
    assert settlement is not None and settlement.charged == 0
    assert [row["reason"] for row in store.history("u1")] == ["grant", "run"]
    assert store.balance("u1").remaining == 98


def test_stale_hold_expires_and_stops_blocking(users_env):
    clock = _Clock()
    store = _store(clock=clock)
    store.grant("u1", KIND_GIFT, 100)
    orphan = store.reserve("u1")  # 进程崩在 reserve 与 bind 之间
    assert orphan.allowed and store.balance("u1").remaining == 0
    clock.now = T0 + timedelta(hours=7)
    assert store.balance("u1").remaining == 100
    assert store.reserve("u1").allowed


def test_exempt_user_bypasses_and_records_nothing(users_env):
    store = _store(exempt_users=frozenset({"owner"}))
    for _ in range(3):
        assert store.reserve("owner").reason == "exempt"
    assert store.settle("owner", "run_1", _usage(1, 1), completed=True) is None
    assert store.balance("owner").exempt
    assert not (userspace.user_space("owner").root / "credits.json").exists()


def test_revoke_zeroes_a_grant(users_env):
    store = _store()
    grant = store.grant("u1", KIND_MONTHLY, 10, expires_at=T0 + timedelta(days=30))
    store.grant("u1", KIND_GIFT, 3)
    assert store.revoke("u1", grant.id, note="退款").remaining == 0
    assert store.balance("u1").remaining == 3
    with pytest.raises(KeyError):
        store.revoke("u1", "g-not-there")


def test_grant_validates_inputs(users_env):
    store = _store()
    with pytest.raises(ValueError):
        store.grant("u1", "coupon", 1)
    with pytest.raises(ValueError):
        store.grant("u1", KIND_GIFT, 0)
    with pytest.raises(ValueError):
        store.grant("u1", KIND_GIFT, 1, expires_at=datetime(2026, 1, 1))  # naive


def test_corrupt_file_fails_closed_and_is_preserved(users_env):
    store = _store(signup_gift=5)
    path = userspace.user_space("u1").root / "credits.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json{", encoding="utf-8")
    denied = store.reserve("u1")
    assert not denied.allowed and denied.reason == "corrupt"
    assert store.settle("u1", "run_1", _usage(1, 1), completed=True) is None
    # 钱的账本坏了不能当成空账本重建（那等于把别人的余额清零再送一次赠送）
    assert path.read_text(encoding="utf-8") == "not-json{"
    assert store.balance("u1").corrupt


def test_concurrent_reserve_never_oversells(users_env):
    store = _store()
    store.grant(
        "u1", KIND_GIFT, 500
    )  # 预占 100/次 → 恰好 5 次能占到（第 5 次占完可用变 0）
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.reserve("u1").allowed, range(30)))
    assert sum(results) == 5


def _slow_load(original):
    """把读-判-写窗口撑到毫秒级：没有锁时并发必然互相覆盖，有锁时只是慢一点。"""

    def load(path):
        state = original(path)
        time.sleep(0.002)
        return state

    return staticmethod(load)


def test_two_store_instances_share_the_file_lock(users_env, monkeypatch):
    """两个实例各有自己的线程锁，能护住账本的只剩文件锁——这就是 CLI 与服务进程同写一份账本的形状。"""
    monkeypatch.setattr(CreditStore, "_load", _slow_load(CreditStore._load))
    a = _store()
    b = _store()
    a.grant("u1", KIND_GIFT, 1000)
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
import sys, time
from intelligence.api.credits import CreditStore
_orig = CreditStore._load
def _slow(path):
    state = _orig(path)
    time.sleep(0.002)
    return state
CreditStore._load = staticmethod(_slow)
store = CreditStore(enabled=True)
print(sum(1 for _ in range(int(sys.argv[1])) if store.reserve("u1").allowed))
"""


def test_cross_process_reserve_never_oversells(users_env):
    """四个真实进程同抢一份账本：文件锁在，总放行数恰等于余额能容的预占数。"""
    store = CreditStore(enabled=True)  # 默认价目：预占 100 分
    store.grant("u1", KIND_GIFT, 700)
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
    monkeypatch.setenv("WORKBENCH_CREDITS_SIGNUP_GIFT", "2000")
    monkeypatch.setenv("WORKBENCH_QUOTA_EXEMPT_USERS", "owner, ops ")
    monkeypatch.delenv("WORKBENCH_CREDITS_PRICING", raising=False)
    store = CreditStore.from_env()
    assert store.enabled and store.signup_gift == 2000
    assert store.exempt_users == frozenset({"owner", "ops"})
    assert store.pricing.source == "builtin-default"
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


def _wait_for(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("条件未在超时内成立")


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

    # 假 runner：往 run 目录写一份带用量的 episode，再完成 run——结算读的就是这份文件。
    usage_per_run: dict[str, tuple[int, int] | None] = {}

    def fake_run_ask(store: RunStore, run_id: str, req) -> None:
        tokens = usage_per_run.get("*", (20_000, 1_000))
        if tokens is not None:
            _write_episode(
                store.run_dir(run_id),
                [
                    {
                        "kind": "model_turn",
                        "payload": {
                            "served_model": "glm-5.3",
                            "input_tokens": tokens[0],
                            "output_tokens": tokens[1],
                        },
                    }
                ],
                {
                    "llm_calls": 1,
                    "tool_calls": 0,
                    "input_tokens": tokens[0],
                    "output_tokens": tokens[1],
                },
            )
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    def fake_conversation_turn(**kwargs: object) -> None:
        run_store = kwargs["run_store"]
        run_id = str(kwargs["run_id"])
        _write_episode(
            run_store.run_dir(run_id),  # type: ignore[attr-defined]
            [
                {
                    "kind": "model_turn",
                    "payload": {
                        "served_model": "glm-5.3",
                        "input_tokens": 10_000,
                        "output_tokens": 0,
                    },
                }
            ],
            {
                "llm_calls": 1,
                "tool_calls": 0,
                "input_tokens": 10_000,
                "output_tokens": 0,
            },
        )
        run_store.finish_run(run_id, rs.STATUS_COMPLETED)  # type: ignore[attr-defined]

    monkeypatch.setattr(app_module, "_run_ask", fake_run_ask)
    monkeypatch.setattr(app_module, "_run_conversation_turn", fake_conversation_turn)
    clients: list[TestClient] = []

    def build(
        credits: CreditStore, quota: RunQuota | None = None, supervisor=None
    ) -> TestClient:
        client = TestClient(
            app_module.create_app(
                repo_root=repo_root,
                run_credits=credits,
                run_quota=quota,
                run_supervisor=supervisor,
            )
        )
        clients.append(client)
        return client

    build.usage_per_run = usage_per_run  # type: ignore[attr-defined]
    yield build
    for client in clients:
        client.app.state.supervisor.shutdown()


def _post_run(client: TestClient, user: str):
    return client.post("/api/runs", json={"question": "q", "user": user})


def _run_status(client: TestClient, run_id: str, user: str) -> str:
    return client.get(f"/api/runs/{run_id}", params={"user": user}).json()["status"]


def test_endpoint_gifts_holds_settles_actual_usage_then_denies(api):
    credits = _store(signup_gift=250, exempt_users=frozenset({"owner"}))
    client = api(credits)
    # 20000 in × 10 + 1000 out × 20 = 0.20 + 0.02 = 0.22 元 = 22 分/次
    first = _post_run(client, "u1")
    assert first.status_code == 200
    run_id = first.json()["run_id"]
    _wait_for(lambda: _run_status(client, run_id, "u1") == "completed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    assert credits.balance("u1").remaining == 228
    body = client.get("/api/credits", params={"user": "u1"}).json()
    assert (
        body["remaining"],
        body["holds"],
        body["debt"],
        body["points_per_yuan"],
    ) == (228, 0, 0, 100)
    row = credits.history("u1")[-1]
    assert (row["reason"], row["delta"], row["run_id"]) == ("run", -22, run_id)
    assert row["cost"]["by_model"] == {
        "glm-5.3": {"input_tokens": 20_000, "output_tokens": 1_000}
    }

    # 花到余额 ≤ 0 为止：228 → 206 → … 每次 22；第 11 次后 -14 → 被拒
    for _ in range(10):
        response = _post_run(client, "u1")
        assert response.status_code == 200
        rid = response.json()["run_id"]
        _wait_for(lambda rid=rid: _run_status(client, rid, "u1") == "completed")
        _wait_for(lambda: credits.balance("u1").holds == 0)
    assert credits.balance("u1").remaining == 228 - 22 * 10
    ok = _post_run(client, "u1")  # 余 8 > 0：最后一问放行
    assert ok.status_code == 200
    rid = ok.json()["run_id"]
    _wait_for(lambda: _run_status(client, rid, "u1") == "completed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    assert (credits.balance("u1").remaining, credits.balance("u1").debt) == (-14, 14)
    denied = _post_run(client, "u1")
    assert denied.status_code == 429
    assert "透支 14 分" in denied.json()["detail"]
    assert "Retry-After" not in denied.headers
    for _ in range(3):
        assert _post_run(client, "owner").status_code == 200
    # 被拒的请求不留 run
    assert len(RunStore(user_id="u1").list_runs()) == 12


def test_balance_endpoint_and_bootstrap_summary(api):
    credits = _store(signup_gift=0, exempt_users=frozenset({"owner"}))
    client = api(credits)
    credits.grant(
        "u1", KIND_MONTHLY, 300, expires_at=T0 + timedelta(days=30), note="9 月"
    )
    credits.grant("u1", KIND_GIFT, 200)

    body = client.get("/api/credits", params={"user": "u1"}).json()
    assert body["user"] == "u1"
    assert (body["enabled"], body["exempt"], body["remaining"]) == (True, False, 500)
    assert [(g["kind"], g["remaining"], g["amount"]) for g in body["grants"]] == [
        (KIND_MONTHLY, 300, 300),
        (KIND_GIFT, 200, 200),
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
        "remaining": 500,
        "points_per_yuan": 100,
        "next_expiry": (T0 + timedelta(days=30)).isoformat(),
    }
    health = client.get("/api/health").json()["runtime"]["credits"]
    assert (health["enabled"], health["pricing_source"], health["hold_points"]) == (
        True,
        "test",
        100,
    )


def test_disabled_store_reports_disabled_and_never_blocks(api):
    client = api(CreditStore(enabled=False))
    for _ in range(3):
        assert _post_run(client, "u1").status_code == 200
    body = client.get("/api/credits", params={"user": "u1"}).json()
    assert body["enabled"] is False and body["remaining"] is None


def test_daily_quota_denial_releases_the_hold(api):
    credits = _store()
    credits.grant("u1", KIND_GIFT, 500)
    client = api(credits, quota=RunQuota(daily_limit=1))
    first = _post_run(client, "u1")
    assert first.status_code == 200
    rid = first.json()["run_id"]
    _wait_for(lambda: _run_status(client, rid, "u1") == "completed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    denied = _post_run(client, "u1")
    assert denied.status_code == 429
    assert "今日研究次数已用完" in denied.json()["detail"]
    # 被日配额拦下的请求没得到服务：不留预占、不扣账
    balance = credits.balance("u1")
    assert (balance.remaining, balance.holds) == (500 - 22, 0)


def test_lost_admission_race_releases_the_hold(api, monkeypatch):
    credits = _store()
    credits.grant("u1", KIND_GIFT, 200)
    client = api(credits)

    def reject(*args, **kwargs):
        raise app_module.RunAdmissionError("系统繁忙", retry_after_sec=30)

    monkeypatch.setattr(client.app.state.supervisor, "submit", reject)
    rejected = _post_run(client, "u1")
    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "30"
    balance = credits.balance("u1")
    assert (balance.remaining, balance.holds) == (200, 0)
    run = RunStore(user_id="u1").list_runs()[0]
    assert (run.status, run.error) == ("failed", "admission_rejected")


def test_cancel_while_queued_releases_hold_without_charge(api, monkeypatch):
    credits = _store()
    credits.grant("u1", KIND_GIFT, 200)
    gate = threading.Event()

    def blocking_run_ask(store: RunStore, run_id: str, req) -> None:
        gate.wait(timeout=10)
        store.finish_run(run_id, rs.STATUS_COMPLETED)

    monkeypatch.setattr(app_module, "_run_ask", blocking_run_ask)
    supervisor = app_module.RunSupervisor(max_workers=1, timeout_sec=30)
    client = api(credits, supervisor=supervisor)
    blocker = _post_run(client, "u1").json()["run_id"]
    queued = _post_run(client, "u1").json()["run_id"]
    _wait_for(lambda: _run_status(client, queued, "u1") == "queued")
    assert credits.balance("u1").holds == 200
    client.post(f"/api/runs/{queued}/cancel", params={"user": "u1"})
    _wait_for(
        lambda: credits.balance("u1").holds == 100
    )  # 排队中取消：预占释放、零扣账
    gate.set()
    _wait_for(lambda: _run_status(client, blocker, "u1") == "completed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    # 排队中取消的那条零扣账；跑完的那条没写用量文件、测试价目无基础费 → 也是 0，账本只剩 grant
    assert [row["reason"] for row in credits.history("u1")] == ["grant"]
    assert credits.balance("u1").remaining == 200


def test_failed_run_without_usage_is_free_but_with_usage_is_charged(api, monkeypatch):
    credits = _store()
    credits.grant("u1", KIND_GIFT, 200)
    client = api(credits)

    def crash_before_llm(store: RunStore, run_id: str, req) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "_run_ask", crash_before_llm)
    rid = _post_run(client, "u1").json()["run_id"]
    _wait_for(lambda: _run_status(client, rid, "u1") == "failed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    assert credits.balance("u1").remaining == 200
    assert credits.history("u1")[-1]["reason"] == "grant"  # 零用量失败不留 run 流水

    def fail_after_tokens(store: RunStore, run_id: str, req) -> None:
        _write_episode(
            store.run_dir(run_id),
            [
                {
                    "kind": "model_turn",
                    "payload": {
                        "served_model": "glm-5.3",
                        "input_tokens": 10_000,
                        "output_tokens": 0,
                    },
                }
            ],
            {
                "llm_calls": 1,
                "tool_calls": 0,
                "input_tokens": 10_000,
                "output_tokens": 0,
            },
        )
        store.finish_run(run_id, rs.STATUS_FAILED, error="model_unavailable")

    monkeypatch.setattr(app_module, "_run_ask", fail_after_tokens)
    rid = _post_run(client, "u1").json()["run_id"]
    _wait_for(lambda: _run_status(client, rid, "u1") == "failed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    assert credits.balance("u1").remaining == 190  # 烧掉的 token 照收，不看结局


def test_conversation_path_is_metered_too(api):
    credits = _store(signup_gift=100)
    client = api(credits)
    conversation = client.post(
        "/api/conversations", json={"title": "积分", "user": "u1"}
    ).json()["conversation_id"]

    def send(content: str):
        return client.post(
            f"/api/conversations/{conversation}/messages",
            json={"content": content, "skill_mode": "auto", "user": "u1"},
        )

    accepted = send("q1")
    assert accepted.status_code == 202
    rid = accepted.json()["run_id"]
    _wait_for(lambda: _run_status(client, rid, "u1") == "completed")
    _wait_for(lambda: credits.balance("u1").holds == 0)
    assert credits.balance("u1").remaining == 90  # 10000 in × 10 元/M = 0.10 元 = 10 分
    credits.settle("u1", "run_drain", _usage(90_000, 0), completed=True)  # 再扣 90 → 0
    denied = send("q2")
    assert denied.status_code == 429
    assert "积分已用完" in denied.json()["detail"]
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
        "--points",
        "2000",
        "--note",
        "内测赠送",
        "--json",
        env=env,
    )
    assert granted.returncode == 0, granted.stderr
    gift = json.loads(granted.stdout)
    assert (gift["kind"], gift["amount"], gift["expires_at"]) == ("gift", 2000, None)

    monthly = _cli(
        "grant", "--user", "u1", "--kind", "monthly", "--yuan", "20", "--json", env=env
    )
    assert monthly.returncode == 0, monthly.stderr
    month = json.loads(monthly.stdout)
    assert (month["kind"], month["amount"]) == ("monthly", 2000)  # 20 元 = 2000 积分
    expires = datetime.fromisoformat(month["expires_at"])
    assert (
        timedelta(days=29) < expires - datetime.now(timezone.utc) <= timedelta(days=30)
    )

    # 服务端账本读到 CLI 写的 grant，并按「先到期先用」先扣月度
    store = CreditStore(enabled=True)
    settlement = store.settle(
        "u1", "run_1", RunUsage({"glm-5.3": (10_000, 0)}), completed=True
    )
    assert settlement is not None and settlement.charged > 0
    row = store.history("u1")[-1]
    assert row["allocations"][0]["grant_id"] == month["id"]

    balance = _cli("balance", "--user", "u1", "--json", env=env)
    assert balance.returncode == 0, balance.stderr
    body = json.loads(balance.stdout)
    assert body["remaining"] == 4000 - settlement.charged

    listed = _cli("list", "--json", env=env)
    assert listed.returncode == 0, listed.stderr
    rows = json.loads(listed.stdout)
    assert [(r["user"], r["remaining"]) for r in rows] == [
        ("u1", 4000 - settlement.charged)
    ]

    revoked = _cli(
        "revoke", "--user", "u1", "--grant-id", month["id"], "--note", "退款", env=env
    )
    assert revoked.returncode == 0, revoked.stderr
    assert (
        json.loads(_cli("balance", "--user", "u1", "--json", env=env).stdout)[
            "remaining"
        ]
        == 2000
    )

    history = _cli("history", "--user", "u1", "--json", env=env)
    assert history.returncode == 0, history.stderr
    assert [row["reason"] for row in json.loads(history.stdout)] == [
        "grant",
        "grant",
        "run",
        "revoke",
    ]

    assert (
        _cli(
            "grant", "--user", "u1", "--kind", "gift", "--points", "0", env=env
        ).returncode
        == 2
    )
    assert (
        _cli(
            "grant",
            "--user",
            "u1",
            "--kind",
            "gift",
            "--points",
            "1",
            "--yuan",
            "1",
            env=env,
        ).returncode
        == 2
    )
    human = _cli("balance", "--user", "u1", env=env)
    assert human.returncode == 0 and "2000" in human.stdout and "¥20.00" in human.stdout


def test_cli_pricing_and_estimate(users_env):
    env = {"FORESIGHT_USERS_DIR": os.environ["FORESIGHT_USERS_DIR"]}
    pricing = _cli("pricing", "--json", env=env)
    assert pricing.returncode == 0, pricing.stderr
    table = json.loads(pricing.stdout)
    assert table["points_per_yuan"] == 100 and "default" in table["models"]
    estimate = _cli(
        "estimate",
        "--input-tokens",
        "37256",
        "--output-tokens",
        "792",
        "--model",
        "glm-5.3",
        "--tool-calls",
        "3",
        "--json",
        env=env,
    )
    assert estimate.returncode == 0, estimate.stderr
    cost = json.loads(estimate.stdout)
    assert cost["rule"] == "metered" and 20 <= cost["points"] <= 60
    human = _cli(
        "estimate", "--input-tokens", "37256", "--output-tokens", "792", env=env
    )
    assert human.returncode == 0 and "积分" in human.stdout


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
        "--points",
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
