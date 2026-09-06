from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb
import pytest

from intelligence.services.methodology_backtest.store import (
    TEACHING_TABLES,
    ensure_schema,
    reset_teaching_tables,
)
from intelligence.services.teaching_framework.params import (
    canonical_json,
    framework_version,
    load_params,
    parameter_hash,
)
from intelligence.services.teaching_framework.receipts import (
    canonical_rows_hash,
    make_receipt,
    write_receipt,
)


def test_teaching_schema_and_reset_do_not_touch_legacy_tables() -> None:
    con = duckdb.connect(":memory:")
    ensure_schema(con)
    con.execute(
        "INSERT INTO history_labels VALUES ('market', 'market', DATE '2026-01-01', 'x', 1, NULL, 'v2', TIMESTAMP '2026-01-02')"
    )
    con.execute(
        "INSERT INTO history_teaching_labels VALUES ('market', 'market', DATE '2026-01-01', 'tf.x', 1, NULL, 'supplier-v1', 'tf-v0.1', 'ok', NULL, TIMESTAMP '2026-01-02')"
    )
    reset_teaching_tables(con)
    assert con.execute("SELECT count(*) FROM history_labels").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM history_teaching_labels").fetchone()[0] == 0
    assert set(TEACHING_TABLES).issubset(
        {str(row[0]) for row in con.execute("SHOW TABLES").fetchall()}
    )


def test_parameter_hash_ignores_json_formatting(tmp_path) -> None:
    params = load_params()
    p1 = tmp_path / "one.json"
    p2 = tmp_path / "two.json"
    p1.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    p2.write_text(canonical_json(params) + "\n", encoding="utf-8")
    assert parameter_hash(p1) == parameter_hash(p2)
    assert framework_version(p1).startswith("tf-v0.1+")


def test_parameter_loader_rejects_invalid_time(tmp_path) -> None:
    params = load_params()
    params["instant_seal_time"] = "9:35"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(params), encoding="utf-8")
    with pytest.raises(ValueError, match="HH:MM"):
        load_params(p)


def test_canonical_hash_excludes_computed_at_and_sorts_primary_key() -> None:
    columns = ("trade_date", "label", "value_num", "computed_at")
    rows1 = [
        ("2026-01-02", "tf.b", 2, "2026-01-03T01:00:00"),
        ("2026-01-01", "tf.a", 1, "2026-01-03T01:00:00"),
    ]
    rows2 = [
        ("2026-01-01", "tf.a", 1, "2027-01-03T01:00:00"),
        ("2026-01-02", "tf.b", 2, "2027-01-03T01:00:00"),
    ]
    assert canonical_rows_hash(rows1, columns=columns, primary_key=("trade_date", "label")) == canonical_rows_hash(
        rows2, columns=columns, primary_key=("trade_date", "label")
    )


def test_old_receipts_remain_queryable_and_become_incomparable() -> None:
    con = duckdb.connect(":memory:")
    ensure_schema(con)
    common = dict(
        build_kind="teaching_labels",
        label_version="tf-v0.1+old",
        source_db="source.duckdb",
        source_max_trade_date="2026-01-02",
        source_row_counts={"fact_market_daily": 2},
        parameter_hash="old-hash",
        canonical_hash="rows-old",
    )
    old = make_receipt(framework_version="tf-v0.1+old", computed_at=datetime(2026, 1, 2, tzinfo=timezone.utc), **common)
    new = make_receipt(
        framework_version="tf-v0.1+new",
        label_version="tf-v0.1+new",
        parameter_hash="new-hash",
        canonical_hash="rows-new",
        computed_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        **{k: v for k, v in common.items() if k not in {"label_version", "parameter_hash", "canonical_hash"}},
    )
    write_receipt(con, old)
    write_receipt(con, new)
    rows = con.execute(
        "SELECT build_id, status, status_reason FROM history_teaching_receipts ORDER BY computed_at"
    ).fetchall()
    assert rows[0][1:] == ("incomparable", "framework_version_or_parameter_hash_changed")
    assert rows[1][1] == "ok"
    assert len(rows) == 2
