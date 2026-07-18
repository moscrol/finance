from __future__ import annotations

import plistlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_akshare_runtime_isolated_from_workbench_api_venv() -> None:
    requirements = (
        REPO_ROOT / "scripts" / "requirements-akshare-snapshot.txt"
    ).read_text(encoding="utf-8")
    bootstrap = (
        REPO_ROOT / "scripts" / "bootstrap_akshare_snapshot_runtime.sh"
    ).read_text(encoding="utf-8")
    runner = (REPO_ROOT / "scripts" / "run_akshare_snapshot.sh").read_text(
        encoding="utf-8"
    )
    chain_runner = (REPO_ROOT / "scripts" / "run_market_snapshot.sh").read_text(
        encoding="utf-8"
    )

    assert "akshare==" in requirements
    assert "akshare-venv" in bootstrap
    assert ".venv-workbench" not in bootstrap + runner
    assert "scripts.sync_akshare_market_snapshot" in runner
    assert 'AKSHARE_PROXY_MODE:-direct' in runner
    assert 'NO_PROXY="*"' in runner
    assert "scripts.sync_market_snapshot" in chain_runner
    assert "WORKBENCH_PYTHON" in chain_runner
    assert "AKSHARE_PYTHON" in chain_runner
    assert ".venv-workbench" in chain_runner
    assert "akshare-venv" in chain_runner
    assert "MARKET_DB_PATH" in chain_runner
    assert 'NO_PROXY="*"' in chain_runner


def test_launch_agent_runs_weekdays_with_explicit_direct_proxy_policy() -> None:
    plist_path = (
        REPO_ROOT
        / "intelligence"
        / "data"
        / "com.a77.finance-akshare-snapshot.plist"
    )
    with plist_path.open("rb") as handle:
        payload = plistlib.load(handle)

    assert payload["Label"] == "com.a77.finance-akshare-snapshot"
    assert payload["ProgramArguments"] == [
        "/Users/a77/finance-workspace-runtime/scripts/run_market_snapshot.sh"
    ]
    assert payload["EnvironmentVariables"]["AKSHARE_PROXY_MODE"] == "direct"
    assert payload["EnvironmentVariables"]["WORKBENCH_PYTHON"] == (
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python"
    )
    assert payload["EnvironmentVariables"]["MARKET_DB_PATH"] == (
        "/Users/a77/finance-workspace-private/db/market_feature_store.duckdb"
    )
    schedules = payload["StartCalendarInterval"]
    assert {item["Weekday"] for item in schedules} == {1, 2, 3, 4, 5}
    assert {(item["Hour"], item["Minute"]) for item in schedules} == {(16, 15)}
