from pathlib import Path
import hashlib
import duckdb
import pytest
from scripts.audit_agent_data_consumption import audit_consumption


def database(tmp_path: Path, sql: str) -> Path:
    path = tmp_path / "facts.duckdb"
    con = duckdb.connect(str(path))
    con.execute(sql)
    con.close()
    return path


def spec(table="fact_daily", time="trade_date", metric="value"):
    return {"daily": {"table": table, "time_column": time, "fields": {"date": time, "value": metric}, "metrics": {"value": metric}}}


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing.duckdb"
    with pytest.raises(FileNotFoundError):
        audit_consumption(path, {}, {}, set())
    assert not path.exists()


def test_physical_objects_outside_schema_are_not_invisible(tmp_path):
    path = database(tmp_path, "CREATE TABLE fact_native(trade_date DATE, value DOUBLE); INSERT INTO fact_native VALUES ('2026-09-24', 8)")
    result = audit_consumption(path, {}, {}, set())
    assert result["unaccounted_facts"] == ["fact_native"]
    assert result["summary"]["nonempty_unaccounted_relations"] == 1
    assert result["requires_attention"]


def test_view_is_a_distinct_public_read_surface(tmp_path):
    path = database(tmp_path, "CREATE TABLE fact_generation(trade_date DATE, value DOUBLE); INSERT INTO fact_generation VALUES ('2026-09-24', 8); CREATE VIEW fact_daily AS SELECT * FROM fact_generation")
    result = audit_consumption(path, spec(), {"fact_generation": "internal: version store"}, {"fact_daily", "fact_generation"})
    assert result["summary"]["semantic_relations"] == 1
    assert result["summary"]["exempt_relations"] == 1
    assert not result["requires_attention"]


def test_latest_all_null_metrics_differ_from_real_zero(tmp_path):
    path = database(tmp_path, "CREATE TABLE fact_daily(trade_date DATE, value DOUBLE); INSERT INTO fact_daily VALUES ('2026-09-23', 0), ('2026-09-24', NULL)")
    row = audit_consumption(path, spec(), {}, {"fact_daily"})["relations"][0]
    assert row["profile_rows"] == 1
    assert row["all_null_exposed_metrics"] == ["value"]
    assert row["metric_surface_empty"]
    zero_dir = tmp_path / "zero"
    zero_dir.mkdir()
    path2 = database(zero_dir, "CREATE TABLE fact_daily(trade_date DATE, value DOUBLE); INSERT INTO fact_daily VALUES ('2026-09-24', 0)")
    assert not audit_consumption(path2, spec(), {}, {"fact_daily"})["relations"][0]["metric_surface_empty"]


def test_semantic_date_precedes_future_end_date(tmp_path):
    path = database(tmp_path, "CREATE TABLE fact_daily(end_date DATE, effective_date DATE, value DOUBLE); INSERT INTO fact_daily VALUES ('2027-01-01','2026-09-02',1),('2027-06-01','2026-09-03',2)")
    row = audit_consumption(path, spec(time="effective_date"), {}, {"fact_daily"})["relations"][0]
    assert row["last_date"] == "2026-09-03"
    assert row["time_basis"] == "semantic_registry"


def test_missing_registered_relation_and_field_are_reported(tmp_path):
    path = database(tmp_path, "CREATE TABLE fact_daily(trade_date DATE, value DOUBLE)")
    definitions = {**spec(metric="missing"), "another": {"table": "fact_absent", "fields": {}, "metrics": {}}}
    result = audit_consumption(path, definitions, {}, {"fact_daily"})
    assert result["registered_missing_relations"] == ["fact_absent"]
    assert result["relations"][0]["missing_registered_columns"] == ["missing"]


def test_audit_does_not_change_database_or_promote_exemptions(tmp_path):
    path = database(tmp_path, "CREATE TABLE feature_l2(trade_date DATE, value DOUBLE); INSERT INTO feature_l2 VALUES ('2026-09-24', 8)")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = audit_consumption(path, {}, {"feature_l2": "stale_since: old declaration"}, {"feature_l2"})
    assert result["relations"][0]["last_date"] == "2026-09-24"
    assert result["relations"][0]["disposition"] == "explicit_exemption"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_intentional_empty_is_not_called_a_populated_surface(tmp_path):
    path = database(tmp_path, "CREATE TABLE fact_daily(trade_date DATE, value DOUBLE)")
    row = audit_consumption(path, spec(), {}, {"fact_daily"}, {"fact_daily"})["relations"][0]
    assert row["intentional_empty"] and row["rows"] == 0
    assert not row["metric_surface_empty"]


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink", "existing_report"])
def test_cli_refuses_existing_output_without_changing_database(tmp_path, monkeypatch, alias):
    from scripts.audit_agent_data_consumption import main

    path = database(tmp_path, "CREATE TABLE fact_daily(value DOUBLE); INSERT INTO fact_daily VALUES (7)")
    output = path if alias == "same" else tmp_path / "report.json"
    if alias == "symlink":
        output.symlink_to(path)
    elif alias == "hardlink":
        output.hardlink_to(path)
    elif alias == "existing_report":
        output.write_text("previous report")
    before = path.read_bytes()
    prior_output = output.read_bytes()
    monkeypatch.setattr("sys.argv", ["audit", "--db", str(path), "--output", str(output)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert path.read_bytes() == before
    assert output.read_bytes() == prior_output
