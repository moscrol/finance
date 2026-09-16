from pathlib import Path

import duckdb
import pytest

from scripts.audit_methodology_label_drift import audit


def _database(path: Path, *, changed: bool = False) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE history_calendar(trade_date DATE)")
        con.execute("INSERT INTO history_calendar VALUES ('2026-09-10')")
        con.execute("""CREATE TABLE history_labels(
            entity_type VARCHAR, entity_id VARCHAR, trade_date DATE,
            label VARCHAR, value_num DOUBLE, value_text VARCHAR)
        """)
        con.execute("INSERT INTO history_labels VALUES ('theme','a','2026-09-10','x',?,NULL)", [2 if changed else 1])
        con.execute('CREATE TABLE "other table"(value INTEGER)')
        con.execute('INSERT INTO "other table" VALUES (1), (1)')


def test_audit_splits_changes_new_dates_and_preserves_other_tables(tmp_path: Path) -> None:
    old, new = tmp_path / "old.duckdb", tmp_path / "new.duckdb"
    _database(old)
    _database(new, changed=True)
    with duckdb.connect(str(new)) as con:
        con.execute("INSERT INTO history_labels VALUES ('theme','b','2026-09-09','x',1,NULL), ('theme','a','2026-09-11','x',1,NULL)")
    report = audit(old, new)
    assert report["labels"] == [{"label": "x", "old_rows": 1, "new_rows": 3, "matched": 1,
                                  "removed": 0, "added_historical": 1, "added_new_dates": 1,
                                  "changed_values": 1}]
    assert report["other_tables_preserved"] is True


@pytest.mark.parametrize("drop", [False, True])
def test_audit_detects_removed_tables_and_duplicate_rows(tmp_path: Path, drop: bool) -> None:
    old, new = tmp_path / "old.duckdb", tmp_path / "new.duckdb"
    _database(old)
    _database(new)
    with duckdb.connect(str(new)) as con:
        if drop:
            con.execute('DROP TABLE "other table"')
        else:
            con.execute('DELETE FROM "other table"')
            con.execute('INSERT INTO "other table" VALUES (1)')
    report = audit(old, new)
    assert report["other_tables_preserved"] is False
    row = report["other_tables"]["other table"]
    assert row == ({"missing": True} if drop else {"lost_rows": 1, "added_rows": 0})


def test_missing_database_fails_without_creating_it(tmp_path: Path) -> None:
    missing = tmp_path / "missing.duckdb"
    with pytest.raises(FileNotFoundError):
        audit(missing, missing)
    assert not missing.exists()
