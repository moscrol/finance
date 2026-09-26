from __future__ import annotations

from datetime import date
import plistlib

import duckdb
import pytest

from scripts import audit_hithink_runtime as audit

DAY = date(2026, 9, 18)


@pytest.fixture
def rig(tmp_path):
    expected, runtime = tmp_path / "expected", tmp_path / "runtime"
    for root in (expected, runtime):
        (root / audit.PIPELINE).parent.mkdir(parents=True)
    (expected / audit.PIPELINE).write_text(
        "HITHINK_STEPS = ('hithink-stock-daily', 'hithink-research')\n"
    )
    (runtime / audit.PIPELINE).write_text("def build_local_plan():\n    return []\n")
    plist = tmp_path / "job.plist"
    with plist.open("wb") as handle:
        plistlib.dump(
            {
                "EnvironmentVariables": {
                    "FINANCE_SYNC_CODE_ROOT": str(runtime),
                    "REVIEW_SYNC_PLAN": "local",
                    "SECRET": "do-not-print",
                }
            },
            handle,
        )
    path = tmp_path / "sample.duckdb"
    with duckdb.connect(str(path)) as con:
        for table in audit.TABLES:
            con.execute(f"CREATE TABLE {table} (trade_date DATE)")
            con.execute(f"INSERT INTO {table} VALUES ('2026-09-08')")
    return dict(launchd_plist=plist, db_path=path, expected_root=expected, target=DAY)


def test_detects_old_deployed_steps_and_stale_data_without_write(rig):
    before = rig["db_path"].read_bytes()
    report = audit.audit(**rig)
    assert report["status"] == "gaps"
    assert report["missing_declared_steps"] == [
        "hithink-research",
        "hithink-stock-daily",
    ]
    assert report["tables"]["fact_stock_daily_hithink"]["latest_date"] == "2026-09-08"
    assert "do-not-print" not in str(report)
    assert rig["db_path"].read_bytes() == before


def test_missing_db_is_not_created(rig):
    path = rig["db_path"].with_name("missing.duckdb")
    rig["db_path"] = path
    with pytest.raises(FileNotFoundError):
        audit.audit(**rig)
    assert not path.exists()


def test_event_table_empty_does_not_claim_supplier_failure(rig):
    runtime = rig["expected_root"].parent / "runtime"
    (runtime / audit.PIPELINE).write_text(
        (rig["expected_root"] / audit.PIPELINE).read_text()
    )
    with duckdb.connect(str(rig["db_path"])) as con:
        for table in audit.DAILY_TABLES:
            con.execute(f"INSERT INTO {table} VALUES (?)", [DAY])
    report = audit.audit(**rig)
    assert report["status"] == "checks_passed"
    assert "not field completeness" in report["boundary"]


def test_non_local_plan_is_reported_even_when_steps_are_declared(rig):
    with rig["launchd_plist"].open("rb") as handle:
        config = plistlib.load(handle)
    config["EnvironmentVariables"]["REVIEW_SYNC_PLAN"] = "cheap"
    with rig["launchd_plist"].open("wb") as handle:
        plistlib.dump(config, handle)
    assert "configured_plan_is_not_local" in audit.audit(**rig)["gaps"]


def test_cli_nonzero_and_structured_diagnostic_on_gaps(rig, capsys):
    result = audit.main(
        [
            "--launchd-plist",
            str(rig["launchd_plist"]),
            "--db",
            str(rig["db_path"]),
            "--expected-code-root",
            str(rig["expected_root"]),
            "--date",
            DAY.isoformat(),
        ]
    )
    assert result == 2
    assert "configured_code_missing_hithink_steps" in capsys.readouterr().out
