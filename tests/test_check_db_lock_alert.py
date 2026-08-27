"""生产库占锁要飞书告警；staging 占锁是夜跑常态，不告。"""
from __future__ import annotations

from unittest.mock import Mock, patch

from scripts import check_db_lock


def test_alert_skips_non_production(tmp_path):
    staging = tmp_path / "market_feature_store.duckdb.staging"
    alerter = Mock()
    with (
        patch.object(check_db_lock, "DB_PATH", staging),
        patch("market_feature_store.write_path.is_canonical_production", return_value=False),
    ):
        check_db_lock._alert_production_blocked("pid 1", alerter=alerter)
    alerter.assert_not_called()


def test_alert_fires_on_canonical_production(tmp_path):
    alerter = Mock()
    prod = tmp_path / "market_feature_store.duckdb"
    with (
        patch("market_feature_store.write_path.is_canonical_production", return_value=True),
        patch.object(check_db_lock, "DB_PATH", prod),
    ):
        check_db_lock._alert_production_blocked(
            "python -m market_feature_store.cli daily-full",
            alerter=alerter,
        )
    alerter.assert_called_once()
    text = alerter.call_args[0][0]
    assert "held exclusive DuckDB lock" in text
    assert "daily-full" in text
