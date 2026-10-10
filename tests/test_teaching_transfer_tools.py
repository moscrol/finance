"""Disclosure, cutoff and recovery guards for the transferred offline tools."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services.methodology_backtest.store import open_labels_db
from intelligence.services.teaching_framework.receipts import make_receipt, write_receipt
from scripts.export_teaching_river import export, rehydrate


@pytest.fixture
def sidecar(tmp_path):
    path = tmp_path / "source.duckdb"
    con = open_labels_db(path, read_only=False)
    for entity, day, known in [
        ("market", "2026-03-01", "2026-03-01 07:00:00"),
        ("market", "2026-03-02", "2026-04-01 07:00:00"),
        ("market", "2026-04-01", "2026-03-01 07:00:00"),
        ("sector", "2026-03-01", "2026-03-01 07:00:00"),
        ("stock", "2026-03-01", "2026-03-01 07:00:00"),
    ]:
        con.execute("""INSERT INTO history_teaching_labels
            (entity_type, entity_id, trade_date, label, value_num, label_version,
             framework_version, computed_at, first_known_at)
            VALUES (?, ?, ?, 'tf.above_week_ma', 1, 'v1', 'fw1', '2026-04-02', ?)""",
                    [entity, entity, day, known])
    con.execute("""INSERT INTO history_range_leaders
        (window_days, trade_date, rank, stock_ts_code, computed_at)
        VALUES (5, '2026-03-01', 1, 'PRIVATE-STOCK', '2026-04-02')""")
    write_receipt(con, make_receipt(build_kind="teaching_labels", framework_version="fw1",
        label_version="v1", source_db="private-source", source_max_trade_date="2026-04-01",
        source_row_counts={}, parameter_hash="p", canonical_hash="h"))
    con.close()
    return path


def _rows(path: Path, table: str):
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute(f'SELECT * FROM "{table}"').fetchall()
    finally:
        con.close()


def test_market_export_does_not_include_stock_tables(sidecar, tmp_path):
    out = tmp_path / "export"
    assert export(sidecar, out, scope="market", cutoff=None) == 0
    leaders = out / "history_range_leaders.parquet"
    if leaders.exists():
        con = duckdb.connect()
        try:
            assert con.execute("SELECT count(*) FROM read_parquet(?)", [str(leaders)]).fetchone()[0] == 0
        finally:
            con.close()


def test_cutoff_filters_event_date_and_omits_unverifiable_tables(sidecar, tmp_path):
    out = tmp_path / "export"
    assert export(sidecar, out, scope="all", cutoff="2026-03-31") == 0
    target = tmp_path / "restored.duckdb"
    assert rehydrate(out, target) == 0
    rows = _rows(target, "history_teaching_labels")
    assert len(rows) == 3
    assert all(str(row[2]) <= "2026-03-31" for row in rows)
    assert _rows(target, "history_range_leaders") == []


def test_rehydrate_never_overwrites_existing_file(sidecar, tmp_path):
    out = tmp_path / "export"
    export(sidecar, out, scope="all", cutoff=None)
    target = tmp_path / "important.duckdb"
    target.write_bytes(b"must survive")
    with pytest.raises(FileExistsError):
        rehydrate(out, target)
    assert target.read_bytes() == b"must survive"


def test_rehydrate_checks_manifest_hash_before_writing(sidecar, tmp_path):
    out = tmp_path / "export"
    export(sidecar, out, scope="all", cutoff=None)
    manifest = out / "MANIFEST.json"
    doc = json.loads(manifest.read_text())
    doc["tables"]["history_teaching_labels"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(doc))
    target = tmp_path / "restored.duckdb"
    with pytest.raises(ValueError, match="SHA256"):
        rehydrate(out, target)
    assert not target.exists()


def test_export_handles_apostrophe_in_path(sidecar, tmp_path):
    out = tmp_path / "user's export"
    assert export(sidecar, out, scope="market", cutoff=None) == 0
    assert (out / "MANIFEST.json").exists()


def test_export_refuses_to_mix_with_existing_bundle(sidecar, tmp_path):
    out = tmp_path / "export"
    export(sidecar, out, scope="all", cutoff=None)
    original = (out / "MANIFEST.json").read_bytes()
    with pytest.raises(FileExistsError):
        export(sidecar, out, scope="market", cutoff=None)
    assert (out / "MANIFEST.json").read_bytes() == original


def test_diagnosis_reads_teaching_receipts_not_legacy_meta(sidecar, monkeypatch, capsys):
    from scripts import diagnose_empty_teaching_tables as tool

    monkeypatch.setattr("sys.argv", ["diagnose", "--labels-db", str(sidecar)])
    assert tool.main() == 0
    text = capsys.readouterr().out
    assert "teaching_labels" in text
    assert "从未对这个库跑完过" not in text
    assert "跑过之后被清空" not in text
    assert "has_rows" in text
