from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path

import duckdb
import pytest

from intelligence.eval.ceiling_pit_fixture import (
    TemporalSchemaError,
    TemporalValueError,
    audit_filtered_duckdb,
    build_filtered_duckdb,
)


AS_OF = "2026-07-24"


def _source_db(path: Path) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE prices (trade_date DATE, value INTEGER)"
        )
        connection.execute(
            "INSERT INTO prices VALUES "
            "('2026-07-24', 1), ('2026-07-25', 2), (NULL, 3)"
        )
    finally:
        connection.close()


def test_filtered_duckdb_rejects_unclassified_temporal_column(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _source_db(source)
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE mystery (id INTEGER, mystery_effective_when VARCHAR)"
        )
    finally:
        connection.close()

    with pytest.raises(
        TemporalSchemaError,
        match="unclassified_temporal_column.*mystery_effective_when",
    ):
        build_filtered_duckdb(source, target, as_of=AS_OF)

    assert not target.exists()


def test_filtered_duckdb_physically_excludes_future_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _source_db(source)

    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT trade_date, value FROM prices ORDER BY value"
        ).fetchall() == [
            (date(2026, 7, 24), 1),
            (None, 3),
        ]
    finally:
        connection.close()
    table = next(item for item in receipt.tables if item.name == "main.prices")
    assert table.source_rows == 3
    assert table.target_rows == 2
    assert table.maxima["trade_date"] == "2026-07-24T00:00:00+08:00"
    assert target.stat().st_mode & 0o777 == 0o444
    assert len(receipt.target_sha256) == 64
    assert receipt.target_sha256 != hashlib.sha256(source.read_bytes()).hexdigest()


def test_filtered_duckdb_handles_compact_dates_timestamps_empty_tables_and_views(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE compact (report_period VARCHAR, value INTEGER)"
        )
        connection.execute(
            "INSERT INTO compact VALUES "
            "('20260724', 1), ('20260725', 2), (NULL, 3)"
        )
        connection.execute(
            "CREATE TABLE events (published_at TIMESTAMPTZ, value INTEGER)"
        )
        connection.execute(
            "INSERT INTO events VALUES "
            "('2026-07-24T15:59:59Z', 1), "
            "('2026-07-24T16:00:00Z', 2), (NULL, 3)"
        )
        connection.execute("CREATE TABLE empty_dates (end_date DATE)")
        connection.execute("CREATE TABLE base_rows (date DATE, value INTEGER)")
        connection.execute(
            "INSERT INTO base_rows VALUES ('2026-07-24', 1), ('2026-07-25', 2)"
        )
        connection.execute("CREATE VIEW base_view AS SELECT * FROM base_rows")
    finally:
        connection.close()

    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT value FROM compact ORDER BY value"
        ).fetchall() == [(1,), (3,)]
        assert connection.execute(
            "SELECT value FROM events ORDER BY value"
        ).fetchall() == [(1,), (3,)]
        assert connection.execute("SELECT COUNT(*) FROM empty_dates").fetchone() == (
            0,
        )
        assert connection.execute("SELECT value FROM base_view").fetchall() == [(1,)]
        assert connection.execute(
            "SELECT table_type FROM information_schema.tables "
            "WHERE table_name = 'base_view'"
        ).fetchone() == ("BASE TABLE",)
    finally:
        connection.close()
    view_receipt = next(item for item in receipt.tables if item.name == "main.base_view")
    assert view_receipt.source_kind == "VIEW"
    assert view_receipt.source_rows == 2
    assert view_receipt.target_rows == 1


def test_filtered_duckdb_rejects_malformed_temporal_values(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE reports (report_date VARCHAR, value INTEGER)"
        )
        connection.execute("INSERT INTO reports VALUES ('not-a-date', 1)")
    finally:
        connection.close()

    with pytest.raises(
        TemporalValueError,
        match="malformed_temporal_value:main.reports:report_date:1",
    ):
        build_filtered_duckdb(source, target, as_of=AS_OF)

    assert not target.exists()


def test_filtered_duckdb_audit_detects_target_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _source_db(source)
    receipt = build_filtered_duckdb(source, target, as_of=AS_OF)
    target.chmod(0o644)

    audit = audit_filtered_duckdb(receipt)

    assert audit.status == "invalid"
    assert "target_mode" in audit.issues


def test_temporal_classifier_distinguishes_cutoffs_labels_and_intraday_times(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            """
            CREATE TABLE signals (
                trade_date DATE,
                start_date DATE,
                limit_times INTEGER,
                period_type VARCHAR,
                is_realtime BOOLEAN,
                first_limit_time VARCHAR,
                value INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO signals VALUES "
            "('2026-07-24', '2026-07-24', 2, '20d', TRUE, '93312', 1), "
            "('2026-07-24', '2026-07-25', 3, '20d', TRUE, '101739', 2), "
            "('2026-07-24', '2026-07-24', 4, '20d', FALSE, '09:25:00', 3), "
            "('2026-07-24', '2026-07-24', 5, '20d', FALSE, '0', 4)"
        )
    finally:
        connection.close()

    build_filtered_duckdb(source, target, as_of=AS_OF)

    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT limit_times, period_type, is_realtime, first_limit_time, value "
            "FROM signals"
        ).fetchall() == [
            (2, "20d", True, "93312", 1),
            (4, "20d", False, "09:25:00", 3),
            (5, "20d", False, "0", 4),
        ]
    finally:
        connection.close()


def test_intraday_time_requires_date_anchor_and_valid_clock(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    connection = duckdb.connect(str(source))
    try:
        connection.execute(
            "CREATE TABLE signals (trade_date DATE, first_limit_time VARCHAR)"
        )
        connection.execute("INSERT INTO signals VALUES ('2026-07-24', '259999')")
    finally:
        connection.close()

    with pytest.raises(
        TemporalValueError,
        match="malformed_intraday_time:main.signals:first_limit_time:1",
    ):
        build_filtered_duckdb(source, target, as_of=AS_OF)
