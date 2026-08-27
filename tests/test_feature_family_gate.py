"""同日门：有 fact 无 feature 是半成品；INCOMPLETE 时对照 staging。"""
from __future__ import annotations

import duckdb

from scripts import check_daily_review_data as gate


def test_feature_family_gap_names_the_unrun_layer():
    counts = {
        "fact_market_daily": 1,
        "fact_sector_period_rank_daily": 0,
        "feature_market_window": 0,
        "feature_sector_window": 0,
        "feature_stock_window": 0,
        "feature_stock_technical_daily": 0,
    }
    missing = gate._feature_family_gap(counts, "2026-08-20")
    assert len(missing) == 1
    assert "派生层未跑" in missing[0]
    assert "compute_features" in missing[0]
    assert "feature_sector_window" in missing[0]


def test_feature_family_gap_silent_when_facts_also_missing():
    assert gate._feature_family_gap({"fact_market_daily": 0}, "2026-08-20") == []


def test_feature_family_gap_silent_when_complete():
    counts = {
        "fact_market_daily": 1,
        "fact_sector_period_rank_daily": 40,
        "feature_market_window": 4,
        "feature_sector_window": 10,
        "feature_stock_window": 10,
        "feature_stock_technical_daily": 10,
    }
    assert gate._feature_family_gap(counts, "2026-08-20") == []


def test_staging_contrast_prints_not_promoted(tmp_path, monkeypatch, capsys):
    prod = tmp_path / "market_feature_store.duckdb"
    staging = tmp_path / "market_feature_store.duckdb.staging"
    for path, rows in ((prod, 0), (staging, 31)):
        con = duckdb.connect(str(path))
        con.execute("CREATE TABLE fact_sw_l1_daily (trade_date DATE)")
        if rows:
            con.execute(
                "INSERT INTO fact_sw_l1_daily VALUES ('2026-08-20')"
            )
        con.close()
    monkeypatch.setattr(gate, "DB_PATH", prod)
    monkeypatch.setattr(gate, "TABLES", ["fact_sw_l1_daily"])
    gate._print_staging_contrast("2026-08-20", {"fact_sw_l1_daily": 0})
    out = capsys.readouterr().out
    assert "STAGING CONTRAST" in out
    assert "未晋升" in out
    assert "生产=0" in out
    assert "staging=1" in out
