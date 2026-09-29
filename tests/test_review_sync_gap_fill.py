"""夜跑接线：当晚封存报价 → 补名 → 两源补行；三步都只在 staging 上动 canonical，失败一律降为 skip。

每个测试钉一个失败形状；不联网、不读凭证、不写库（run_step 全部替换成假件）。

变异自检（scripts/mutation_check.py，2026-09-29 @7837d9b5，本文件 + test_bridge_gap_arbitration.py，8/8 KILLED）：
补行失败不降级 / 去名字闸 / 生产库判定退回仓相对路径 / 上游拒服务后继续打 / 采集不限当天 /
跳过捕获审计 / 没封存也给 --capture-dir / 收据可覆盖——各自点名的测试全红，还原后树与 HEAD 一致。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from market_feature_store.consumption_registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-09-29"
CST = ZoneInfo("Asia/Shanghai")


@pytest.fixture
def review(monkeypatch, tmp_path):
    path = ROOT / "skills/daily-full-review/scripts/run_review_sync.py"
    spec = importlib.util.spec_from_file_location("review_gap_fill_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "QUOTE_CAPTURE_ROOT", tmp_path / "tencent")
    monkeypatch.setattr(module, "BRIDGE_GAP_FILL_ROOT", tmp_path / "gap-fill")
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "staging.duckdb"))
    return module


def _fake_run(calls, status="ok", code=0):
    def run(label, argv, timeout, **kwargs):
        calls.append((label, argv, timeout))
        return {"label": label, "status": status, "code": code, "elapsed": 0.0}
    return run


def _seal(review):
    capture = review.QUOTE_CAPTURE_ROOT / DAY
    capture.mkdir(parents=True)
    (capture / "receipt.json").write_text("{}")
    return capture


def test_order_capture_after_bridge_fill_before_any_row_consumer(review):
    names = [name for name, _ in review.build_plan(DAY, 1, 1, "local")]
    order = [names.index(n) for n in ("stock-daily", "capture-dated-quotes", "attach-capture-names",
                                      "bridge-gap-fill", "stitch-sector-stocks", "limit-stats-local",
                                      "features")]
    assert order == sorted(order)
    for plan in ("full", "cheap"):
        plan_names = [n for n, _ in review.build_plan(DAY, 1, 1, plan)]
        assert "capture-dated-quotes" not in plan_names and "bridge-gap-fill" not in plan_names


def test_registry_lists_new_steps_in_the_same_position(review):
    assert list(load_registry().plans["local"]) == review.plan_step_names()["local"]


def test_new_steps_are_declared_optional_for_recovery(review):
    assert {"capture-dated-quotes", "attach-capture-names", "bridge-gap-fill"} <= set(review.OPTIONAL_SKIP_STEPS)


@pytest.mark.parametrize("now", [
    datetime(2026, 9, 30, 18, 40, tzinfo=CST),   # 回放历史日：捕获只能描述采集当天
    datetime(2026, 9, 29, 14, 59, tzinfo=CST),   # 收盘前
])
def test_capture_skips_outside_its_own_evening(review, monkeypatch, now):
    monkeypatch.setattr(review, "run_step", lambda *a, **k: pytest.fail("must not spawn"))
    result = review.capture_dated_quotes_step(DAY, 9, now=lambda: now)
    assert result["status"] == "skip" and "only describes its own day" in result["note"]


def test_capture_does_not_resample_an_existing_seal(review, monkeypatch):
    _seal(review)
    monkeypatch.setattr(review, "run_step", lambda *a, **k: pytest.fail("must not spawn"))
    result = review.capture_dated_quotes_step(DAY, 9, now=lambda: datetime(2026, 9, 29, 18, 40, tzinfo=CST))
    assert result["status"] == "skip" and "already" in result["note"]


def test_capture_reads_the_staging_db_and_writes_the_dated_dir(review, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(review, "run_step", _fake_run(calls))
    result = review.capture_dated_quotes_step(DAY, 9, now=lambda: datetime(2026, 9, 29, 18, 40, tzinfo=CST))
    assert result["status"] == "ok"
    (label, argv, timeout), = calls
    assert label == "capture-dated-quotes" and timeout == 9
    assert argv[1] == "scripts/capture_dated_quotes.py"
    assert argv[argv.index("--from-duckdb") + 1] == str(tmp_path / "staging.duckdb")
    assert argv[argv.index("--out-dir") + 1] == str(review.QUOTE_CAPTURE_ROOT / DAY)
    assert argv[argv.index("--target-date") + 1] == DAY


@pytest.mark.parametrize("status,code", [("fail", 2), ("timeout", None)])
def test_capture_failure_is_a_skip_not_a_fail(review, monkeypatch, status, code):
    monkeypatch.setattr(review, "run_step", _fake_run([], status, code))
    result = review.capture_dated_quotes_step(DAY, 9, now=lambda: datetime(2026, 9, 29, 18, 40, tzinfo=CST))
    assert result["status"] == "skip" and f"{status} code={code}" in result["note"]


def test_gap_fill_applies_on_the_staging_db_with_fresh_receipt(review, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(review, "run_step", _fake_run(calls))
    step = dict(review.build_plan(DAY, 7, 9, "local"))["bridge-gap-fill"]
    assert step()["status"] == "ok"
    assert step()["status"] == "ok"
    (label, argv, timeout), (_, argv2, _) = calls
    assert label == "bridge-gap-fill" and timeout == 9
    assert argv[1] == "scripts/backfill_bridge_gaps.py" and "--apply" in argv
    assert argv[argv.index("--db") + 1] == str(tmp_path / "staging.duckdb")
    assert argv[argv.index("--trade-date") + 1] == DAY
    receipt = Path(argv[argv.index("--receipt") + 1])
    assert receipt != Path(argv2[argv2.index("--receipt") + 1])  # 每轮新目录，旧证据不覆盖
    assert receipt.parent.is_dir() and not receipt.exists()
    fetch = Path(argv[argv.index("--eastmoney-fetch-dir") + 1])
    assert fetch.parent == receipt.parent and not fetch.exists()
    assert "--capture-dir" not in argv  # 没有封存就不给，不拿半份目录当证据


def test_gap_fill_uses_the_sealed_capture_when_present(review, monkeypatch):
    capture = _seal(review)
    calls = []
    monkeypatch.setattr(review, "run_step", _fake_run(calls))
    review.bridge_gap_fill_step(DAY, 9)
    (_, argv, _), = calls
    assert argv[argv.index("--capture-dir") + 1] == str(capture)


@pytest.mark.parametrize("status,code", [("fail", 1), ("fail", 2), ("timeout", None)])
def test_gap_fill_failure_never_reaches_the_tail_retry(review, monkeypatch, status, code):
    # 收尾重试会在下游算完之后才重跑 fail/timeout 步骤；那时再插行，派生表就与 canonical 对不上。
    monkeypatch.setattr(review, "run_step", _fake_run([], status, code))
    result = review.bridge_gap_fill_step(DAY, 9)
    assert result["status"] == "skip"
    assert "no rows filled" in result["note"]
