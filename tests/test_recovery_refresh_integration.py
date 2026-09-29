"""Recovery consumes refresh failure and only permits the plan's optional skips.

Real child control flow, input validation, snapshot parser and history writer;
other data leaves are deterministic stubs. This is not a full production replay.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db, hithink_client
from market_feature_store.cli import build_parser, cmd_stitch_sector_stocks
from market_feature_store.sync import sync_local_sector_members as stitch
from scripts import recover_local_review as recovery
from tests import test_stitch_refresh_completion as refresh_tests


@pytest.fixture
def completed(monkeypatch):
    yield from refresh_tests.completed.__wrapped__(monkeypatch)


@pytest.fixture
def child_runner(tmp_path, monkeypatch):
    target = tmp_path / "sample.duckdb.staging"
    with duckdb.connect(str(target)) as con:
        db.init_db(con)
        con.execute(
            "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, close, pre_close, "
            "amount, turnover, source) VALUES ('2026-09-15','000001.SZ','样本',10,9,.01,1,'sina:stock_zh_a_daily')"
        )
    row = dict(trade_date="2026-09-16", stock_ts_code="000001.SZ", stock_name="样本",
               source="sina:stock_zh_a_daily", close=11.0, pre_close=10.0, pct_chg=10.0,
               amount=.011, turnover=1.0, open=10.0, high=11.0, low=10.0, volume=1000.0)
    raw = [dict(f297=20260917, f12="000001", f14="样本", f2=12.0, f18=11.0,
                f3=9.09, f6=1200000, f8=1.0, f17=11.0, f15=12.0, f16=11.0, f5=1000.0)]
    history, snapshot = tmp_path / "history.jsonl", tmp_path / "snapshot.json"
    history.write_text(json.dumps(row) + "\n")
    snapshot.write_text(json.dumps(raw))
    args = argparse.Namespace(history_day="2026-09-16", snapshot_day="2026-09-17",
                              history=history, snapshot=snapshot, receipt=tmp_path / "receipt.json")
    monkeypatch.setenv("FINANCE_WS", str(tmp_path))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(target))
    monkeypatch.setenv("MARKET_FEATURE_STORE_RUN_ID", "refresh-current-run")
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "local")
    monkeypatch.setattr(db, "DB_PATH", target)
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    sync = recovery.load_script("skills/daily-full-review/scripts/run_review_sync.py")
    history_module = recovery.load_script("skills/duckdb-backfill/scripts/backfill_stock_daily_sina.py")
    monkeypatch.setattr(recovery, "load_script", lambda path:
                        history_module if "backfill_stock_daily_sina.py" in path else sync)
    calls = []

    def run(*, key=True, leaf="", status="fail", stitch_cli=None):
        monkeypatch.setattr(hithink_client, "has_api_key", lambda: key)

        def run_step(label, argv, timeout):
            calls.append((label, argv))
            if label == "stitch-sector-stocks" and stitch_cli:
                rc = stitch_cli(argv)
                result_status = "ok" if rc == 0 else "fail"
            else:
                result_status = status if label == leaf else "ok"
                rc = 0 if result_status == "ok" else 2
            return dict(label=label, status=result_status, code=rc, elapsed=0)

        monkeypatch.setattr(sync, "run_step", run_step)
        return recovery.child(args)

    return run, target, sync, calls


def test_real_refresh_cli_failure_prevents_child_success(child_runner, completed, monkeypatch):
    run, target, _, calls = child_runner
    original = stitch.stitch_sector_members

    def expired_baseline(*args, **kwargs):
        # Isolate the exact R1 fixture; other child leaves use a separate tiny DB.
        kwargs["fetch_caps"] = False
        return original("2026-09-17", con=completed, **kwargs)

    monkeypatch.setattr(stitch, "stitch_sector_members", expired_baseline)
    with pytest.raises(RuntimeError, match="stitch-sector-stocks failed; no publish"):
        run(stitch_cli=lambda argv: cmd_stitch_sector_stocks(build_parser().parse_args(argv[3:])))
    assert not Path(str(target) + ".status.json").exists()
    assert not any(label in {"sector-daily-local", "same-day-gate"} for label, _ in calls)


def test_plan_declared_hithink_no_key_skips_do_not_claim_updates(child_runner):
    run, target, sync, calls = child_runner
    assert run(key=False) == 0
    status = json.loads(Path(str(target) + ".status.json").read_text())
    assert status["ok"] is True and status["run_id"] == "refresh-current-run"
    # 可选步骤在回放里各自显式 skip，与同花顺 no-key skip 分开核：
    # 采集只能描述采集当天；补名与两源补行都要当日封存，回放历史日没有。
    optional = [r for r in status["steps"] if r["label"] in sync.OPTIONAL_SKIP_STEPS]
    assert [(r["label"], r["status"]) for r in optional] == [
        (label, "skip") for label in ("capture-dated-quotes", "attach-capture-names", "bridge-gap-fill")] * 2
    assert all("only describes its own day" in r["note"] for r in optional if r["label"] == "capture-dated-quotes")
    assert all("no sealed capture" in r["note"] for r in optional if r["label"] != "capture-dated-quotes")
    assert not any(label in sync.OPTIONAL_SKIP_STEPS for label, _ in calls)  # 回放里不起子进程、不联网
    skipped = [r for r in status["steps"]
               if r["status"] == "skip" and r["label"] not in sync.OPTIONAL_SKIP_STEPS]
    assert len(skipped) == 2 * len(sync.HITHINK_STEPS)
    assert {r["label"] for r in skipped} == set(sync.HITHINK_STEPS)
    assert all(r["code"] is None and "未更新" in r["note"] for r in skipped)
    assert not any(label in sync.HITHINK_STEPS for label, _ in calls)
    for label, argv in calls:
        if label == "index-daily":
            assert "--no-fupanhui-fallback" in argv


def test_successful_leaves_write_current_run_only(child_runner):
    run, target, sync, calls = child_runner
    assert run() == 0
    status = json.loads(Path(str(target) + ".status.json").read_text())
    assert status["ok"] is True and status["run_id"] == "refresh-current-run"
    historical_steps = set(sync.HITHINK_STEPS) - {"hithink-research"}
    assert all(r["status"] == "ok" for r in status["steps"]
               if r["label"] not in {"hithink-research", *sync.OPTIONAL_SKIP_STEPS})
    assert all(r["status"] == "skip" for r in status["steps"] if r["label"] in sync.OPTIONAL_SKIP_STEPS)
    assert Counter(label for label, _ in calls if label in sync.HITHINK_STEPS) == {
        label: 2 for label in historical_steps
    }


@pytest.mark.parametrize("key", [True, False])
def test_recovery_never_invokes_latest_only_research(child_runner, monkeypatch, key):
    run, target, sync, calls = child_runner
    original = sync.sync_hithink_step

    def dated_step(label, day, timeout):
        assert label != "hithink-research", "historical recovery must not invoke latest-only research"
        return original(label, day, timeout)

    monkeypatch.setattr(sync, "sync_hithink_step", dated_step)
    assert run(key=key) == 0
    status = json.loads(Path(str(target) + ".status.json").read_text())
    excluded = [r for r in status["steps"] if r["label"] == "hithink-research"]
    assert [r["date"] for r in excluded] == ["2026-09-16", "2026-09-17"]
    assert all(r["status"] == "skip" and r["code"] is None for r in excluded)
    assert all("latest-only" in r["note"] and "未更新" in r["note"] for r in excluded)
    assert not any(label == "hithink-research" for label, _ in calls)


@pytest.mark.parametrize("leaf,status", [
    ("index-daily", "skip"), ("index-daily", "fail"), ("stitch-sector-stocks", "skip"),
    ("stitch-sector-stocks", "fail"), ("hithink-stock-daily", "fail"),
    ("hithink-sector-kline", "timeout"), ("same-day-gate", "fail"),
    ("cross-day-gate", "fail"), ("backfill-alignment", "fail"),
])
def test_required_failures_and_nonoptional_skips_still_block(child_runner, leaf, status):
    run, target, _, _ = child_runner
    with pytest.raises(RuntimeError, match="no publish"):
        run(leaf=leaf, status=status)
    assert not Path(str(target) + ".status.json").exists()
