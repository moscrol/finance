"""生产库写入守卫：无 --direct 必须 fail closed；有旗标必须留收据。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from market_feature_store import write_path
from market_feature_store.cli import cmd_daily_full_exec, cmd_daily_update


def test_staging_and_tmp_are_not_canonical_production(tmp_path):
    staging = tmp_path / "market_feature_store.duckdb.staging"
    other = tmp_path / "market_feature_store.duckdb"
    assert write_path.is_canonical_production(staging) is False
    assert write_path.is_canonical_production(other) is False
    assert write_path.production_write_blocked(direct=False, path=other) is None


def test_canonical_production_refuses_without_direct():
    reason = write_path.production_write_blocked(
        direct=False, path=write_path.canonical_production_path()
    )
    assert reason is not None
    assert "--direct" in reason
    assert "run_review_sync.py" in reason
    assert write_path.production_write_blocked(
        direct=True, path=write_path.canonical_production_path()
    ) is None


def test_daily_update_refuses_canonical_production_without_direct():
    args = SimpleNamespace(
        trade_date="2026-08-20",
        chart_table=None,
        skip_long=False,
        no_chart=True,
        stock_source="snapshot",
        status_json=None,
        direct=False,
    )
    with (
        patch(
            "market_feature_store.sync.sync_daily_full.preflight_daily_update",
            return_value={"ok": True, "problems": []},
        ),
        patch(
            "market_feature_store.write_path.is_canonical_production",
            return_value=True,
        ),
        patch("market_feature_store.sync.sync_daily_full.run_daily_update") as update,
    ):
        rc = cmd_daily_update(args)
    assert rc == 2
    update.assert_not_called()


def test_daily_update_direct_writes_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(write_path, "DIRECT_RECEIPT_DIR", tmp_path)
    args = SimpleNamespace(
        trade_date="2026-08-20",
        chart_table=None,
        skip_long=False,
        no_chart=True,
        stock_source="snapshot",
        status_json=None,
        direct=True,
    )
    with (
        patch(
            "market_feature_store.sync.sync_daily_full.preflight_daily_update",
            return_value={"ok": True, "problems": []},
        ),
        patch(
            "market_feature_store.write_path.is_canonical_production",
            return_value=True,
        ),
        patch(
            "market_feature_store.sync.sync_daily_full.run_daily_update",
            return_value={
                "trade_date": "2026-08-20",
                "ok": True,
                "steps": [],
                "validation": {"ok": True, "missing_fields": [], "tables": []},
            },
        ),
        patch.object(write_path, "connect", side_effect=RuntimeError("no db")),
    ):
        rc = cmd_daily_update(args)
    assert rc == 0
    receipts = list(tmp_path.glob("direct-write-2026-08-20-*.json"))
    assert len(receipts) == 1
    assert "direct-prod" in receipts[0].read_text(encoding="utf-8")


def test_run_daily_update_schedules_features():
    from market_feature_store.sync import sync_daily_full

    assert "_run_compute_features" in sync_daily_full.run_daily_update.__code__.co_names


def test_daily_full_exec_refuses_canonical_production_without_direct():
    args = SimpleNamespace(
        trade_date="2026-08-20",
        chart_table=None,
        skip_long=False,
        stock_source="snapshot",
        status_json=None,
        direct=False,
    )
    with (
        patch(
            "market_feature_store.write_path.is_canonical_production",
            return_value=True,
        ),
        patch("market_feature_store.sync.sync_daily_full.run_daily_full") as full,
    ):
        rc = cmd_daily_full_exec(args)
    assert rc == 2
    full.assert_not_called()
