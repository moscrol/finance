"""真实分步入口的同花顺接线；不联网、不读凭证、不写生产库。"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_feature_store import hithink_client
from market_feature_store.consumption_registry import load_registry
from market_feature_store.sync import sync_daily_full

ROOT = Path(__file__).resolve().parents[1]
STEPS = (
    "hithink-stock-daily", "hithink-sector-kline",
    "hithink-limit-pools", "hithink-dragon-auction", "hithink-research",
)
TARGET = "2026-09-02"


@pytest.fixture
def review(monkeypatch):
    path = ROOT / "skills/daily-full-review/scripts/run_review_sync.py"
    spec = importlib.util.spec_from_file_location("review_hithink_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(hithink_client, "has_api_key", lambda: True)
    return module


def _result(label, status="ok"):
    return {"label": label, "status": status, "code": 0 if status == "ok" else 1, "elapsed": 0.0}


def test_local_plan_invokes_five_real_cli_commands_in_order(review, monkeypatch):
    recorded = []

    def fake_run(label, argv, timeout):
        recorded.append((label, argv, timeout))
        return _result(label)

    monkeypatch.setattr(review, "run_step", fake_run)
    plan = dict(review.build_plan(TARGET, 11, 99, "local"))
    names = list(plan)
    positions = [names.index(step) for step in STEPS]
    assert positions == sorted(positions)
    assert names.index("stock-daily") < positions[0]
    assert positions[-1] < names.index("stitch-sector-stocks")
    for step in STEPS:
        assert plan[step]()["status"] == "ok"
    for (label, argv, timeout), step in zip(recorded, STEPS):
        assert label == step
        assert argv[:4] == review.CLI + ["sync-" + step]
        if step == "hithink-research":
            assert "--incremental" not in argv and "--history-only" not in argv
            assert names.index(step) > names.index("hithink-dragon-auction")
        else:
            assert "--incremental" in argv and "--full" not in argv
        assert timeout == 99
        # 不显式传 db_path：子进程继承 MARKET_FEATURE_STORE_DB 的 staging，
        # 不启用独立 sidecar 写入兜底。
        assert "--db" not in argv
        if step != "hithink-stock-daily":
            assert argv[argv.index("--end-date") + 1] == TARGET
    assert "--skip-constituents" in recorded[1][1]  # 当前快照不冒充历史成员


def test_no_key_is_visible_skip_and_never_starts_child(review, monkeypatch):
    monkeypatch.setattr(hithink_client, "has_api_key", lambda: False)

    def forbidden(*args, **kwargs):
        pytest.fail("缺 key 不应启动外呼子进程")

    monkeypatch.setattr(review, "run_step", forbidden)
    plan = dict(review.build_plan(TARGET, 11, 99, "local"))
    for step in STEPS:
        result = plan[step]()
        assert result["status"] == "skip"
        assert result["code"] is None
        assert "no-key" in result["note"]


def test_run_step_preserves_staging_environment(review, monkeypatch):
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", "/tmp/test-only-staging.duckdb")
    captured = []

    def fake_child(argv, **kwargs):
        captured.append((argv, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(review.subprocess, "run", fake_child)
    dict(review.build_plan(TARGET, 11, 99, "local"))[STEPS[0]]()
    assert len(captured) == 1
    assert "env" not in captured[0][1]  # subprocess 默认继承父进程环境
    assert captured[0][1]["cwd"] == str(ROOT)


def _main_fakes(review, monkeypatch, statuses, retries):
    calls = []
    releases = []
    logs = []

    def step():
        index = min(len(calls), len(statuses) - 1)
        calls.append(STEPS[0])
        return _result(STEPS[0], statuses[index])

    monkeypatch.setattr(review, "build_plan", lambda *a: [(STEPS[0], step)])
    monkeypatch.setattr(review, "_notify", lambda *a: None)
    monkeypatch.setattr(review, "write_runlog", lambda *a, **k: logs.append((a, k)))
    monkeypatch.setattr(review, "run_release_steps", lambda *a: (releases.append(a) or [], True))
    monkeypatch.setattr(review.sys, "argv", [
        "review", "--date", TARGET, "--plan", "local", "--skip-preflight",
        "--retry-rounds", str(retries),
    ])
    return calls, releases, logs


@pytest.mark.parametrize("status", ["fail", "timeout", "partial"])
def test_failed_hithink_cannot_be_hidden_by_old_table_gates(review, monkeypatch, status):
    _, releases, logs = _main_fakes(review, monkeypatch, [status], retries=0)
    assert review.main() == 1
    assert releases == []  # 旧表门即使绿，也不准导出/换名
    assert logs[0][0][2] is False


def test_successful_retry_can_release(review, monkeypatch):
    calls, releases, logs = _main_fakes(review, monkeypatch, ["fail", "ok"], retries=1)
    assert review.main() == 0
    assert len(calls) == 2 and len(releases) == 1
    assert "retry r1" in logs[0][0][1][0]["note"]


def test_retry_finishes_before_calendar_consumers_run(review, monkeypatch):
    calls, releases, _ = _main_fakes(review, monkeypatch, ["fail", "ok"], retries=1)
    original = review.build_plan(TARGET, 11, 99, "local")[0]

    def consumer():
        calls.append("hithink-limit-pools")
        return _result("hithink-limit-pools")

    monkeypatch.setattr(review, "build_plan", lambda *a: [original, ("hithink-limit-pools", consumer)])
    assert review.main() == 0
    assert calls == [STEPS[0], STEPS[0], "hithink-limit-pools"]
    assert len(releases) == 1


def test_unrecovered_dump_does_not_run_calendar_consumers(review, monkeypatch):
    _, releases, _ = _main_fakes(review, monkeypatch, ["fail"], retries=1)
    original = review.build_plan(TARGET, 11, 99, "local")[0]

    def forbidden():
        pytest.fail("dump 未恢复，不应拿旧日历跑下游")

    monkeypatch.setattr(review, "build_plan", lambda *a: [original, ("hithink-limit-pools", forbidden)])
    assert review.main() == 1
    assert releases == []


def test_losing_key_on_retry_cannot_hide_attempted_failure(review, monkeypatch):
    _, releases, _ = _main_fakes(review, monkeypatch, ["fail", "skip"], retries=1)
    assert review.main() == 1
    assert releases == []


def test_registry_owns_parallel_tables_without_claiming_old_facts():
    registry = load_registry()
    for step in STEPS:
        datasets = registry.datasets_for_step(step, "local")
        assert datasets
        tables = {table for ds in datasets for table in ds.tables}
        assert not tables & {"fact_stock_daily", "fact_sector_daily", "fact_sector_stock_daily"}
    assert "fact_sector_constituent_hithink" not in {
        table for ds in registry.datasets_for_step("hithink-sector-kline", "local") for table in ds.tables
    }


def test_research_monolith_forwards_date(monkeypatch):
    from market_feature_store.sync import sync_hithink_research as module

    calls = []
    monkeypatch.setattr(module, "sync_hithink_research", lambda **kw: calls.append(kw) or {"status": "ok"})
    sync_daily_full.run_hithink_research_step(TARGET)
    assert calls == [{"end_date": date(2026, 9, 2)}]


@pytest.mark.parametrize("kind", ["sector_kline", "limit_pools", "dragon_auction"])
def test_monolith_wrappers_forward_target_day_too(monkeypatch, kind):
    module = __import__(f"market_feature_store.sync.sync_hithink_{kind}", fromlist=["x"])
    calls = []
    monkeypatch.setattr(module, "skip_reason_if_no_key", lambda: None)
    monkeypatch.setattr(module, f"sync_hithink_{kind}", lambda **kw: calls.append(kw) or {})
    getattr(sync_daily_full, f"run_hithink_{kind}_step")(TARGET)
    assert calls[0]["end_date"] == date(2026, 9, 2)
