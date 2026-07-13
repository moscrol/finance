from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services.runtime_inputs import (
    RuntimeResearchInputs,
    probe_market_inputs,
)


def _runtime_inputs(tmp_path: Path) -> RuntimeResearchInputs:
    return RuntimeResearchInputs.from_roots(
        code_root=tmp_path / "code",
        data_root=tmp_path / "data",
        users_root=tmp_path / "users",
        knowledge_wiki=tmp_path / "knowledge" / "wiki",
        vector_index_dir=tmp_path / "knowledge" / ".rag_index",
    )


def _write_market_db(
    path: Path,
    trade_date: str,
    *,
    column_type: str = "date",
) -> None:
    path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            f"create table fact_market_daily(trade_date {column_type})"
        )
        connection.execute("insert into fact_market_daily values (?)", [trade_date])
    finally:
        connection.close()


def _complete_market_payload() -> dict[str, object]:
    return {
        "stage": "修复",
        "total_amount": 1,
        "amount_ratio": 1.0,
        "advancers": 1,
        "decliners": 1,
        "limit_up": 1,
        "limit_down": 0,
        "capacity_top3": [],
    }


def _write_warn_snapshot(
    inputs: RuntimeResearchInputs,
    trade_date: str,
    *,
    market: dict[str, object],
) -> None:
    inputs.market_snapshot_dir.mkdir(parents=True)
    (inputs.market_snapshot_dir / "meta.json").write_text(
        json.dumps({"latest_trade_date": trade_date}), encoding="utf-8"
    )
    (inputs.market_snapshot_dir / f"{trade_date}.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "trade_date": trade_date,
                "market": market,
                "themes": [],
                "strong_stocks": [],
            }
        ),
        encoding="utf-8",
    )


def test_runtime_inputs_keep_code_and_canonical_data_roots_separate(
    tmp_path: Path,
) -> None:
    code_root = tmp_path / "code-worktree"
    data_root = tmp_path / "canonical-data"
    users_root = tmp_path / "users"
    wiki_root = tmp_path / "knowledge" / "wiki"
    vector_root = tmp_path / "knowledge" / ".rag_index"
    snapshot_override = tmp_path / "snapshots"

    inputs = RuntimeResearchInputs.from_roots(
        code_root=code_root,
        data_root=data_root,
        users_root=users_root,
        knowledge_wiki=wiki_root,
        vector_index_dir=vector_root,
    )
    overridden = RuntimeResearchInputs.from_roots(
        code_root=code_root,
        data_root=data_root,
        users_root=users_root,
        knowledge_wiki=wiki_root,
        vector_index_dir=vector_root,
        market_snapshot_dir=snapshot_override,
    )

    assert inputs.code_root == code_root.resolve()
    assert inputs.data_root == data_root.resolve()
    assert inputs.market_db_path == data_root.resolve() / "db/market_feature_store.duckdb"
    assert inputs.exports_dir == data_root.resolve() / "market_feature_store/exports"
    assert inputs.market_snapshot_dir == data_root.resolve() / "market_snapshot"
    assert inputs.users_root == users_root.resolve()
    assert inputs.knowledge_wiki == wiki_root.resolve()
    assert inputs.vector_index_dir == vector_root.resolve()
    assert overridden.market_snapshot_dir == snapshot_override.resolve()


def test_probe_market_inputs_reports_stale_export_and_missing_optional_snapshot(
    tmp_path: Path,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    _write_market_db(inputs.market_db_path, "2026-07-13")
    inputs.exports_dir.mkdir(parents=True)
    (inputs.exports_dir / "2026-07-10-theme-candidates.json").write_text(
        "{}", encoding="utf-8"
    )

    status = probe_market_inputs(inputs)

    assert status.duckdb_available is True
    assert status.duckdb_cutoff == "2026-07-13"
    assert status.latest_export_date == "2026-07-10"
    assert status.export_freshness == "stale"
    assert status.market_snapshot_available is False
    assert status.market_snapshot_date is None
    assert status.market_data_available is True
    assert status.warning is None


@pytest.mark.parametrize(
    ("export_name", "expected_date", "expected_freshness"),
    [
        ("2026-07-13-theme-candidates.json", "2026-07-13", "fresh"),
        ("2026-07-14-theme-candidates.json", "2026-07-14", "conflict"),
        ("20260713-theme-candidates.json", None, "missing"),
        ("2026-99-99-theme-candidates.json", None, "missing"),
    ],
)
def test_probe_market_inputs_classifies_only_canonical_exports(
    tmp_path: Path,
    export_name: str,
    expected_date: str | None,
    expected_freshness: str,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    _write_market_db(inputs.market_db_path, "2026-07-13")
    inputs.exports_dir.mkdir(parents=True)
    (inputs.exports_dir / export_name).write_text("{}", encoding="utf-8")

    status = probe_market_inputs(inputs)

    assert status.latest_export_date == expected_date
    assert status.export_freshness == expected_freshness


def test_probe_market_inputs_does_not_accept_an_empty_snapshot_directory(
    tmp_path: Path,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    inputs.market_snapshot_dir.mkdir(parents=True)

    status = probe_market_inputs(inputs)

    assert status.duckdb_available is False
    assert status.duckdb_cutoff is None
    assert status.market_snapshot_available is False
    assert status.market_snapshot_date is None
    assert status.market_data_available is False
    assert status.warning == "duckdb_missing"


def test_probe_market_inputs_accepts_a_warn_snapshot_with_a_real_daily_file(
    tmp_path: Path,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    _write_warn_snapshot(
        inputs,
        "2026-07-13",
        market=_complete_market_payload(),
    )

    status = probe_market_inputs(inputs)

    assert status.market_snapshot_available is True
    assert status.market_snapshot_date == "2026-07-13"
    assert status.market_data_available is True


def test_probe_market_inputs_rejects_a_warn_snapshot_without_core_market_payload(
    tmp_path: Path,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    _write_warn_snapshot(inputs, "2026-07-13", market={})

    status = probe_market_inputs(inputs)

    assert status.market_snapshot_available is False
    assert status.market_snapshot_date is None
    assert status.market_data_available is False


def test_probe_market_inputs_rejects_an_invalid_snapshot_date(tmp_path: Path) -> None:
    inputs = _runtime_inputs(tmp_path)
    _write_warn_snapshot(
        inputs,
        "2026-99-99",
        market=_complete_market_payload(),
    )

    status = probe_market_inputs(inputs)

    assert status.market_snapshot_available is False
    assert status.market_snapshot_date is None
    assert status.market_data_available is False


def test_probe_market_inputs_rejects_an_invalid_varchar_duckdb_cutoff(
    tmp_path: Path,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    _write_market_db(
        inputs.market_db_path,
        "2026-99-99",
        column_type="varchar",
    )

    status = probe_market_inputs(inputs)

    assert status.duckdb_available is False
    assert status.duckdb_cutoff is None
    assert status.market_data_available is False
    assert status.warning == "duckdb_invalid_cutoff"


def test_probe_market_inputs_bounds_export_directory_io_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    inputs.exports_dir.mkdir(parents=True)
    original_iterdir = Path.iterdir

    def fail_exports(directory: Path):
        if directory == inputs.exports_dir:
            raise OSError(f"private failure at {directory}")
        return original_iterdir(directory)

    monkeypatch.setattr(Path, "iterdir", fail_exports)

    status = probe_market_inputs(inputs)

    assert status.latest_export_date is None
    assert status.export_freshness == "missing"
    assert status.export_warning == "exports_unavailable"
    assert str(tmp_path) not in status.export_warning


def test_probe_market_inputs_returns_a_bounded_warning_for_invalid_duckdb(
    tmp_path: Path,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    inputs.market_db_path.parent.mkdir(parents=True)
    inputs.market_db_path.write_text("not a database", encoding="utf-8")

    status = probe_market_inputs(inputs)

    assert status.duckdb_available is False
    assert status.duckdb_cutoff is None
    assert status.warning == "duckdb_unavailable"
    assert str(tmp_path) not in status.warning


def test_probe_market_inputs_bounds_snapshot_validator_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _runtime_inputs(tmp_path)
    private_error = f"snapshot exploded at {tmp_path}"

    def fail_snapshot(_root: Path):
        raise RuntimeError(private_error)

    monkeypatch.setattr(
        "intelligence.services.runtime_inputs.validate_market_snapshot_root",
        fail_snapshot,
    )

    status = probe_market_inputs(inputs)

    assert status.market_snapshot_available is False
    assert status.market_snapshot_date is None
    assert status.market_data_available is False
    assert status.snapshot_warning == "snapshot_unavailable"
    assert str(tmp_path) not in status.snapshot_warning
    assert private_error not in repr(status)
