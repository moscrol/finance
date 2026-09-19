"""计划契约回归：只用临时库/假执行器，不抓上游、不写生产库。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from intelligence import cli as intelligence_cli
from intelligence.paths import ProjectPaths
from intelligence.workflows import daily_review as workflow
from market_feature_store import cli, db, quality
from market_feature_store.consumption_registry import load_registry, resolve_plan, tables_for_plan
from scripts import check_daily_review_data as gate
from scripts import render_daily_review_briefing as renderer

DAY = "2026-09-07"


@pytest.fixture(autouse=True)
def clean_plan_env(monkeypatch):
    monkeypatch.delenv("REVIEW_SYNC_PLAN", raising=False)


@pytest.fixture
def paths(tmp_path):
    return ProjectPaths(tmp_path, tmp_path / "wiki", tmp_path / "site", tmp_path / "snapshot", tmp_path / "index")


@pytest.fixture
def sync_module():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "review_sync_alignment", root / "skills/daily-full-review/scripts/run_review_sync.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("explicit,env,day,expected", [
    (None, None, DAY, "full"), (None, "", DAY, "full"),
    (None, "local", DAY, "local"), ("full", "local", DAY, "full"),
    ("local", "full", DAY, "local"), ("cheap", "local", DAY, "cheap"),
    (None, "auto", DAY, "cheap"), ("auto", "local", "2026-09-04", "full"),
])
def test_shared_resolution(explicit, env, day, expected, monkeypatch, sync_module):
    if env is not None:
        monkeypatch.setenv("REVIEW_SYNC_PLAN", env)
    assert resolve_plan(explicit, day) == expected
    assert sync_module.resolve_plan(explicit, day) == expected
    assert workflow.DailyReviewOptions(date=day, plan=explicit).plan == expected


def test_invalid_environment_fails_before_db_or_subprocess(monkeypatch):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "locla")
    opener = Mock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(quality, "_connect_ro", opener)
    monkeypatch.setattr(gate, "_connect_read_only", opener)
    for call in (lambda: quality.check_daily(DAY), lambda: gate.check_data(DAY),
                 lambda: workflow.DailyReviewOptions(date=DAY)):
        with pytest.raises(ValueError, match="unknown plan"):
            call()
    opener.assert_not_called()


@pytest.mark.parametrize("plan", ["local", "cheap", "full"])
@pytest.mark.parametrize("selection", [{}, {"from_step": "daily-review"}, {"only_step": "daily-review-html"}])
def test_workflow_pins_both_gates_and_nested_html_gate(plan, selection, monkeypatch, paths):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", plan)
    options = workflow.DailyReviewOptions(date=DAY, skip_sync=True, **selection)
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "full" if plan == "local" else "local")
    summary = workflow.dry_run_daily_review(options, paths)
    assert summary.inputs["plan"] == plan
    by_name = {step.name: step.command for step in summary.steps}
    for name in ("quality-gate", "cross-day-quality-gate", "daily-review-html"):
        assert f"--plan {plan}" in by_name[name]
    assert list(by_name)[:3] == ["quality-gate", "cross-day-quality-gate", "export-increment"]


def test_daily_cli_passes_plan_through_to_summary(monkeypatch, capsys):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "full")
    assert intelligence_cli.main(["daily", "--date", DAY, "--plan", "local", "--skip-sync", "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["inputs"]["plan"] == "local"
    assert "--plan local" in next(s["command"] for s in summary["steps"] if s["name"] == "cross-day-quality-gate")


@pytest.mark.parametrize("plan", ["local", "cheap", "auto"])
def test_nonfull_never_silently_runs_legacy_full_sync(plan, monkeypatch, paths):
    runner = Mock(side_effect=AssertionError("must not execute full sync"))
    monkeypatch.setattr(workflow, "run_command_step", runner)
    monkeypatch.setattr(workflow, "record_daily_review_metrics", Mock())
    options = workflow.DailyReviewOptions(date=DAY, plan=plan, alerts_enabled=False)
    summary = workflow.run_daily_review(options, paths)
    assert summary.status == "FAIL"
    assert "--skip-sync" in summary.errors[0]
    runner.assert_not_called()
    # 只选报告的恢复入口本来就不跑同步，仍可通过，且不能绕两道门。
    resume = workflow.DailyReviewOptions(date=DAY, plan=plan, from_step="daily-review")
    assert workflow.dry_run_daily_review(resume, paths).status == "SKIP"


@pytest.mark.parametrize("plan", ["local", "cheap", "full"])
def test_renderer_passes_plan_and_preserves_gate_failure(plan, monkeypatch):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "local" if plan != "local" else "full")
    run = Mock(return_value=SimpleNamespace(returncode=3))
    monkeypatch.setattr(renderer.subprocess, "run", run)
    assert renderer.main([DAY, "--plan", plan]) == 3
    assert run.call_args.args[0][-2:] == ["--plan", plan]


@pytest.mark.parametrize("plan", ["local", "cheap", "full"])
def test_sync_release_passes_identical_plan(plan, monkeypatch, sync_module):
    calls = []

    def fake(label, argv, timeout):
        calls.append((label, argv))
        return {"label": label, "status": "ok", "code": 0, "elapsed": 0}

    monkeypatch.setattr(sync_module, "run_step", fake)
    _, ok = sync_module.run_release_steps(DAY, 1, plan)
    assert ok
    for label, argv in calls[:2]:
        assert argv[argv.index("--plan") + 1] == plan, label


def test_local_preflight_does_not_require_fupanhui(monkeypatch, sync_module):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "local")
    monkeypatch.setattr(sync_module.sys, "argv", ["run_review_sync.py", "--date", DAY])
    preflight = Mock(return_value=[])
    monkeypatch.setattr(sync_module, "preflight", preflight)
    monkeypatch.setattr(sync_module, "narrative_freshness_warnings", lambda _: [])
    monkeypatch.setattr(sync_module, "build_plan", Mock(return_value=[]))
    monkeypatch.setattr(sync_module, "run_release_steps", Mock(return_value=([], True)))
    monkeypatch.setattr(sync_module, "write_runlog", Mock())
    assert sync_module.main() == 0
    preflight.assert_called_once_with(require_fupanhui=False)
    sync_module.build_plan.assert_called_once_with(DAY, 300, 600, "local")
    sync_module.run_release_steps.assert_called_once_with(DAY, 300, "local")


def test_registry_scope_preserves_local_requirements_and_full_theme_flow():
    local, fields = gate.plan_scope("local")
    assert "fact_theme_flow_daily" not in local
    # 连板、新高、主线、核心股已经有 local 生产者，不得误豁免。
    assert {"fact_limit_advance_daily", "fact_stock_high_daily", "fact_mainline_theme_daily",
            "fact_core_stock_daily", "fact_core_leader_daily"} <= set(local)
    assert set(fields) == set(gate.MARKET_FIELDS)
    assert "local" not in load_registry().dataset("theme_flow").steps
    for plan in ("full", "cheap"):
        tables, _ = gate.plan_scope(plan)
        assert "fact_theme_flow_daily" in tables
        assert quality.tables_in_plan(plan, quality.GAP_TABLES) == quality.GAP_TABLES
        assert quality.tables_in_plan(plan, quality.ROW_ANOMALY_TABLES) == quality.ROW_ANOMALY_TABLES


@pytest.fixture
def quality_db():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE, advancers INT, "
                "limit_up INT, limit_down INT, volume_ratio DOUBLE, sh_index_close DOUBLE, sh_index_pct_chg DOUBLE)")
    con.execute("INSERT INTO fact_market_daily VALUES (?, 12000, 3000, 60, 10, 1.0, 3500, 0.5)", [DAY])
    local = tables_for_plan(load_registry(), "local")
    for table in set(quality.GAP_TABLES + quality.ROW_ANOMALY_TABLES):
        # 当前跨日质量门还会检查成分行情全空，夹具提供该查询的真实列。
        columns = "trade_date DATE"
        if table == "fact_sector_stock_daily":
            columns += ", sector_ts_code VARCHAR, sector_name VARCHAR, price DOUBLE, pct_chg DOUBLE, amount DOUBLE"
        con.execute(f"CREATE TABLE {table} ({columns})")
        if table in local:
            if table == "fact_sector_stock_daily":
                con.execute(f"INSERT INTO {table} VALUES (?, 'sector', 'sector', 10, 1, 100)", [DAY])
            else:
                con.execute(f"INSERT INTO {table} VALUES (?)", [DAY])
    yield con
    con.close()


def test_cross_day_cli_env_local_passes_but_explicit_full_and_cheap_do_not(monkeypatch, quality_db, capsys):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "local")
    # CLI 使用真实 quality 函数，仅替换连接；cursor 允许入口关闭而不关闭夹具。
    monkeypatch.setattr(quality, "_connect_ro", quality_db.cursor)
    assert cli.main(["check-daily", "--trade-date", DAY]) == 0
    assert "plan=local" in capsys.readouterr().out
    for plan in ("full", "cheap"):
        assert cli.main(["check-daily", "--trade-date", DAY, "--plan", plan]) == 2
        assert "fact_global_index_daily" in capsys.readouterr().out


def test_local_cross_day_still_rejects_missing_required_data_and_bad_values(monkeypatch, quality_db):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "local")
    quality_db.execute("DELETE FROM fact_stock_daily")
    quality_db.execute("UPDATE fact_market_daily SET total_amount = 0")
    result = quality.check_daily(DAY, con=quality_db)
    assert not result["ok"]
    assert "fact_stock_daily" in {g["table"] for g in result["gaps"]}
    assert "total_amount" in {v["field"] for v in result["range_violations"]}


def test_local_plan_still_rejects_present_but_quoteless_sector(quality_db):
    quality_db.execute("UPDATE fact_sector_stock_daily SET price=NULL, pct_chg=NULL, amount=NULL")
    result = quality.check_daily(DAY, con=quality_db, plan="local")
    assert not result["ok"]
    assert result["quoteless_sectors"][0]["sector_ts_code"] == "sector"


def test_cross_day_auto_uses_db_latest_day_not_wall_clock(monkeypatch, quality_db):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "auto")
    assert quality.check_daily(con=quality_db)["plan"] == "cheap"
    quality_db.execute("UPDATE fact_market_daily SET trade_date='2026-09-04'")
    assert quality.check_daily(con=quality_db)["plan"] == "full"


@pytest.mark.parametrize("plan", ["local", "full", "cheap", "auto"])
def test_same_day_cli_resolves_environment(plan, monkeypatch):
    monkeypatch.setenv("REVIEW_SYNC_PLAN", plan)
    check = Mock(return_value=[])
    monkeypatch.setattr(gate, "check_data", check)
    assert gate.main([DAY, "--phase", "data"]) == 0
    check.assert_called_once_with(DAY, plan=resolve_plan(plan, DAY))


def test_same_day_local_keeps_null_field_and_required_table_checks(monkeypatch):
    con = duckdb.connect(":memory:")
    db.init_db(con)
    con.execute("INSERT INTO fact_market_daily (trade_date) VALUES (?)", [DAY])
    monkeypatch.setenv("REVIEW_SYNC_PLAN", "local")
    monkeypatch.setattr(gate, "_connect_read_only", con.cursor)
    monkeypatch.setattr(gate, "_print_staging_contrast", Mock())
    try:
        missing = gate.check_data(DAY)
        assert any("fact_stock_daily 无" in m for m in missing)
        assert any("fact_market_daily.strength_avg_pct 为空" in m for m in missing)
        assert not any("fact_theme_flow_daily" in m for m in missing)
        for plan in ("full", "cheap"):
            assert any("fact_theme_flow_daily 无" in m for m in gate.check_data(DAY, plan))
    finally:
        con.close()


def test_river_does_not_present_previous_theme_flow_as_current():
    from intelligence.services.river import Gap, _capital_track

    con = duckdb.connect(":memory:")
    db.init_db(con)
    con.execute("INSERT INTO fact_theme_flow_daily (trade_date, theme_code, theme_name, total_fund) "
                "VALUES ('2026-09-04', 'T1', '题材A', 123)")
    try:
        result = _capital_track(con, DAY, "990001.FP", "题材A")
        assert isinstance(result, Gap)
        assert result.reason == "no_data"
    finally:
        con.close()
