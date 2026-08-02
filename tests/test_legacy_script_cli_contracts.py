"""legacy CLI 的参数解析、canonical 数据和退役边界测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OLD_DB = ROOT / "db" / "market.duckdb"


def _make_canonical_fixture(path: Path) -> list[str]:
    dates = [f"2026-01-{day:02d}" for day in range(1, 7)]
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE fact_market_daily (
            trade_date DATE,
            total_amount DOUBLE,
            amount_vs_yesterday_pct DOUBLE,
            limit_up INTEGER,
            limit_down INTEGER,
            sh_week_ma DOUBLE,
            sh_deviation_pct DOUBLE,
            advancers INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_sector_daily (
            trade_date DATE,
            sector_ts_code TEXT,
            sector_name TEXT,
            diff_ratio DOUBLE,
            pct_chg DOUBLE,
            amount DOUBLE
        )
        """
    )
    con.executemany(
        "INSERT INTO fact_market_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (date, 120.0 if date == dates[1] else 100.0, None, 10, 1, 3000.0, 0.0, 1000)
            for date in dates
        ],
    )
    con.executemany(
        "INSERT INTO fact_sector_daily VALUES (?, ?, ?, ?, ?, ?)",
        [(date, "S1", "测试板块", 20.0, 1.0, 600.0) for date in dates],
    )
    con.close()
    return dates


def _run(script: str, *args: str, env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, script, *args],
        cwd=ROOT,
        env=merged_env,
        capture_output=True,
        text=True,
    )


def test_backtest_help_is_side_effect_free(tmp_path):
    before = OLD_DB.exists()
    result = _run(
        "scripts/backtest_sector.py",
        "--help",
        env={"MARKET_FEATURE_STORE_DB": str(tmp_path / "unused.duckdb")},
    )
    assert result.returncode == 0
    assert "--db-path" in result.stdout
    assert OLD_DB.exists() is before


def test_backtest_runs_against_canonical_fixture(tmp_path):
    db_path = tmp_path / "market_feature_store.duckdb"
    dates = _make_canonical_fixture(db_path)
    result = _run(
        "scripts/backtest_sector.py",
        "--from",
        dates[0],
        "--to",
        dates[-1],
        "--db-path",
        str(db_path),
        "--top",
        "1",
        "--hold",
        "3",
    )
    assert result.returncode == 0, result.stderr
    assert "板块回测结果" in result.stdout
    assert not OLD_DB.exists()


def test_backtest_missing_database_fails_without_creating_path(tmp_path):
    missing = tmp_path / "missing.duckdb"
    result = _run("scripts/backtest_sector.py", "--db-path", str(missing))
    assert result.returncode == 2
    assert "canonical DuckDB" in result.stderr
    assert not missing.exists()


def test_turning_point_help_is_side_effect_free(tmp_path):
    before = OLD_DB.exists()
    result = _run(
        "scripts/detect_turning_points.py",
        "--help",
        env={"MARKET_FEATURE_STORE_DB": str(tmp_path / "unused.duckdb")},
    )
    assert result.returncode == 0
    assert "--db-path" in result.stdout
    assert OLD_DB.exists() is before


def test_turning_point_cli_runs_against_canonical_fixture(tmp_path):
    db_path = tmp_path / "market_feature_store.duckdb"
    dates = _make_canonical_fixture(db_path)
    result = _run(
        "scripts/detect_turning_points.py",
        "--from",
        dates[0],
        "--to",
        dates[-1],
        "--db-path",
        str(db_path),
    )
    assert result.returncode == 0, result.stderr
    assert "信号" in result.stdout
    assert "放量" in result.stdout
    assert not OLD_DB.exists()


def test_turning_point_missing_database_fails_without_creating_path(tmp_path):
    missing = tmp_path / "missing.duckdb"
    result = _run("scripts/detect_turning_points.py", "--db-path", str(missing))
    assert result.returncode == 2
    assert "canonical DuckDB" in result.stderr
    assert not missing.exists()


def test_sync_help_is_side_effect_free(tmp_path):
    before = OLD_DB.exists()
    result = _run(
        "scripts/sync_to_local.py",
        "--help",
        env={"HOME": str(tmp_path)},
    )
    assert result.returncode == 0
    assert "已退役" in result.stdout
    assert OLD_DB.exists() is before


def test_sync_invocation_is_retired_without_database_or_network(tmp_path):
    before = OLD_DB.exists()
    result = _run(
        "scripts/sync_to_local.py",
        "--incremental",
        env={"HOME": str(tmp_path)},
    )
    assert result.returncode == 2
    assert "daily-full" in result.stderr
    assert OLD_DB.exists() is before


def test_renderer_help_is_side_effect_free(tmp_path):
    before = OLD_DB.exists()
    result = _run(
        "scripts/render_daily_review_template.py",
        "--help",
        env={"HOME": str(tmp_path)},
    )
    assert result.returncode == 0
    assert "--trade-date" in result.stdout
    assert "--output-dir" in result.stdout
    assert OLD_DB.exists() is before


def test_renderer_passes_requested_paths_to_report_builder(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "render_daily_review_template",
        ROOT / "scripts" / "render_daily_review_template.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    calls = {}

    def fake_build_daily_review(**kwargs):
        calls.update(kwargs)
        return {
            "trade_date": kwargs["trade_date"],
            "output_path": kwargs["output_path"],
            "chart_path": kwargs["chart_path"],
        }

    monkeypatch.setattr(module, "build_daily_review", fake_build_daily_review)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "render_daily_review_template.py",
            "--trade-date",
            "2026-01-05",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert module.main() == 0
    assert calls == {
        "trade_date": "2026-01-05",
        "output_path": str(tmp_path / "2026-01-05-daily-review.md"),
        "chart_path": str(tmp_path / "2026-01-05-advancers-ma5.png"),
    }
