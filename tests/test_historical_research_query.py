"""Public historical-query contract on small, independent canonical fixtures."""

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from intelligence.services.historical_research.query import (
    HistoryQuery,
    HistoryQueryCancelled,
    HistoryQuerySpec,
    HistoryQueryTimedOut,
    history_query_parameters,
)
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "history.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("""CREATE TABLE fact_sector_daily (
            trade_date DATE, sector_ts_code TEXT, sector_name TEXT, pct_chg DOUBLE,
            amount DOUBLE, diff_ratio DOUBLE, source TEXT, updated_at TIMESTAMP,
            sector_universe_snapshot_id TEXT)""")
        con.execute("""CREATE TABLE fact_market_daily (
            trade_date DATE, total_amount DOUBLE, advancers INTEGER, limit_up INTEGER,
            sh_index_pct_chg DOUBLE, market_stage TEXT, source TEXT)""")
        con.execute("""CREATE TABLE fact_sector_stock_daily (
            trade_date DATE,sector_ts_code TEXT,stock_ts_code TEXT,stock_name TEXT,
            price DOUBLE,pct_chg DOUBLE,amount DOUBLE,source TEXT,
            sector_universe_snapshot_id TEXT)""")
        con.execute("""CREATE TABLE fact_stock_daily (
            trade_date DATE,stock_ts_code TEXT,stock_name TEXT,close DOUBLE,
            pct_chg DOUBLE,amount DOUBLE,source TEXT)""")
        con.execute("""CREATE TABLE fact_theme_limit_heat_daily (
            trade_date DATE,sector_ts_code TEXT,dimension TEXT,scope TEXT,
            limit_up_count INTEGER,total_count INTEGER,source TEXT)""")
        con.execute("""CREATE TABLE fact_event_daily (
            event_date DATE,event_id TEXT,title TEXT,content TEXT,sectors TEXT,
            source TEXT,updated_at TIMESTAMP)""")
        days = [date(2026, 1, 5) + timedelta(days=i) for i in range(40)]
        con.executemany(
            "INSERT INTO fact_market_daily VALUES (?,20000,3000,60,0,'test','fixture')",
            [(day,) for day in days],
        )
        con.executemany(
            "INSERT INTO fact_sector_daily VALUES (?,?,?,1,600,11,'fixture',NULL,'snap-a')",
            [(day, code, "同名板块") for code in ("A.FP", "A.TI") for day in days],
        )
    return path


def run(db: Path, **arguments):
    defaults = {
        "operation": "inspect_history",
        "start": "2026-01-05",
        "end": "2026-02-13",
    }
    defaults.update(arguments)
    return HistoryQuery(db).run(
        HistoryQuerySpec.from_arguments(defaults),
        information_cutoff=InformationCutoff(date(2026, 2, 13), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )


@pytest.fixture
def stock_db(db):
    with duckdb.connect(str(db)) as con:
        con.execute("""INSERT INTO fact_stock_daily
            SELECT trade_date, replace(sector_ts_code, 'A.', 'S.'), '同名股票',
                   10, pct_chg, amount, 'stock-fixture'
            FROM fact_sector_daily""")
    return db


def test_stock_catalog_and_inspect_keep_stock_identity_and_membership_version(stock_db):
    catalog = run(stock_db, entity_kind="stock", query="同名", preview_limit=1)
    assert {row["entity_code"] for row in catalog["rows"]} == {"S.FP", "S.TI"}
    assert catalog["total_matched"] == 2
    assert all(row["entity_kind"] == "stock" for row in catalog["rows"])
    with duckdb.connect(str(stock_db)) as con:
        con.execute("""INSERT INTO fact_sector_stock_daily VALUES
            ('2026-01-05','A.FP','S.FP','同名股票',10,1,600,'member','snap-member')""")
    result = run(stock_db, entity_kind="stock", entity_codes=["S.FP"], end="2026-01-05")
    row = result["rows"][0]
    assert row["stock"]["stock_ts_code"] == "S.FP"
    assert row["sector_memberships"][0]["sector_universe_snapshot_id"] == "snap-member"
    assert "sector" not in row
    assert "fact_sector_daily" not in result["inputs"]
    assert row["events"] == []
    assert result["event_time_status"] == "stock_event_link_not_available"


def test_stock_compute_uses_stock_values_and_versioned_definitions(stock_db):
    with duckdb.connect(str(stock_db)) as con:
        con.execute(
            "UPDATE fact_stock_daily SET pct_chg=10,amount=1200 WHERE trade_date='2026-01-06'"
        )
    result = run(
        stock_db,
        operation="compute_history",
        entity_kind="stock",
        entity_codes=["S.FP"],
        end="2026-01-06",
        features=["return_pct", "amount_ratio", "market_relative_return_pct"],
    )
    assert result["rows"][0]["features"] == pytest.approx(
        {"return_pct": 11.1, "amount_ratio": 2, "market_relative_return_pct": 11.1}
    )
    assert "return_pct@history-features-v1" in result["definition_refs"]
    assert (
        result["feature_definitions"]["market_relative_return_pct"]["entity_kind"]
        == "stock"
    )


def test_stock_rejects_sector_only_features_and_conditions():
    base = dict(
        operation="compute_history",
        entity_kind="stock",
        entity_codes=["S.FP"],
        start="2026-01-05",
        end="2026-01-06",
    )
    for feature in (
        "double_red_days",
        "max_double_red_streak",
        "advancer_share",
        "limit_up_share",
        "first_surge_lag",
    ):
        with pytest.raises(ValueError, match="unsupported_definition"):
            HistoryQuerySpec.from_arguments({**base, "features": [feature]})
        with pytest.raises(ValueError, match="unsupported_definition"):
            HistoryQuerySpec.from_arguments(
                {**base, "condition": {"feature": feature, "op": "gte", "value": 1}}
            )


def test_stock_trigger_matching_ignores_future_returns(stock_db):
    args = dict(
        operation="find_analogues",
        entity_kind="stock",
        entity_codes=["S.FP", "S.TI"],
        reference_code="S.FP",
        start="2026-01-20",
        end="2026-01-22",
        search_start="2026-01-05",
        search_end="2026-01-19",
        window_days=3,
        step_days=3,
        match_mode="trigger_only",
        features=["return_pct", "amount_ratio"],
    )
    before = run(stock_db, **args)
    assert before["total_matched"] == 10
    with duckdb.connect(str(stock_db)) as con:
        con.execute(
            "UPDATE fact_stock_daily SET pct_chg=99 WHERE trade_date>'2026-01-22'"
        )
    after = run(stock_db, **args)
    assert after["query_id"] == before["query_id"]
    assert after["rows"] == before["rows"]
    assert after["universe"]["entity_kind"] == "stock"


def test_stock_case_comparison_keeps_success_failure_denominator(stock_db):
    with duckdb.connect(str(stock_db)) as con:
        con.executemany(
            "UPDATE fact_stock_daily SET amount=?,pct_chg=? WHERE stock_ts_code='S.FP' AND trade_date=?",
            [
                (100, 0, "2026-01-05"),
                (200, 0, "2026-01-06"),
                (100, 10, "2026-01-07"),
                (200, 0, "2026-01-08"),
                (200, -10, "2026-01-09"),
                (100, 0, "2026-01-10"),
                (200, 10, "2026-01-11"),
                (100, 0, "2026-01-12"),
                (100, -10, "2026-01-13"),
            ],
        )
    result = run(
        stock_db,
        operation="compare_cases",
        entity_kind="stock",
        entity_codes=["S.FP"],
        start="2026-01-05",
        end="2026-01-12",
        search_start="2026-01-05",
        search_end="2026-01-12",
        features=["amount_ratio"],
        window_days=2,
        step_days=2,
        preview_limit=1,
        condition={"feature": "amount_ratio", "op": "gte", "value": 1},
        outcome={"horizon_days": 1, "threshold_pct": 0},
    )
    assert result["total_matched"] == 4
    assert result["returned_count"] == 1
    assert result["comparison"]["four_cells"] == {
        "x_true_y_true": 1,
        "x_true_y_false": 1,
        "x_false_y_true": 1,
        "x_false_y_false": 1,
    }
    assert result["outcome_definition"]["metric"] == "compounded_stock_daily_pct"
    assert "return_pct@history-features-v1" in result["definition_refs"]


def test_catalog_keeps_same_name_codes_separate_and_displays_only_preview(db):
    result = run(db, query="同名", preview_limit=1)
    assert {row["entity_code"] for row in result["rows"]} == {"A.FP", "A.TI"}
    assert result["total_matched"] == 2
    assert result["returned_count"] == 1
    assert result["truncated"] is True
    assert result["decision_eligible"] is False
    assert result["promotion_eligible"] is False


def test_compute_uses_full_range_and_never_turns_null_into_zero(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=0 WHERE sector_ts_code='A.FP'"
        )
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=10 WHERE sector_ts_code='A.FP' AND trade_date='2026-02-13'"
        )
        con.execute(
            "UPDATE fact_sector_daily SET amount=NULL WHERE sector_ts_code='A.FP' AND trade_date='2026-01-06'"
        )
    result = run(
        db,
        operation="compute_history",
        entity_codes=["A.FP"],
        features=["return_pct", "amount_ratio"],
        preview_limit=1,
    )
    row = result["rows"][0]
    assert row["features"]["return_pct"] == pytest.approx(10)
    assert row["features"]["amount_ratio"] is None
    assert row["feature_coverage"]["return_pct"]["expected_dates"] == 40
    assert row["feature_coverage"]["amount_ratio"]["nonnull_dates"] == 39
    assert row["entity_code"] == "A.FP"
    assert "feature:amount_ratio:missing" in result["gaps"]


def test_inspect_keeps_missing_stock_join_and_event_time_unknown(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "INSERT INTO fact_sector_stock_daily VALUES ('2026-01-05','A.FP','S1','stock',10,NULL,100,'member','snap-a')"
        )
        con.execute(
            "INSERT INTO fact_event_daily VALUES ('2026-01-05','e1','event','text','[{\"ts_code\":\"A.FP\"}]','editor','2026-02-01')"
        )
    result = run(db, entity_codes=["A.FP"], end="2026-01-05")
    row = result["rows"][0]
    assert row["members"][0]["pct_chg"] is None
    assert row["members"][0]["stock_daily"] is None
    assert row["events"][0]["publication_time_status"] == "unknown"
    assert row["events"][0]["updated_at"].startswith("2026-02-01")
    assert (
        result["coverage"]["fact_sector_stock_daily"]["fields"]["pct_chg"]["nonnull"]
        == 0
    )
    assert result["coverage"]["member_stock_join"]["missing"] == 1


def test_streak_diffusion_and_lead_use_declared_day_and_member_denominators(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET amount=100 WHERE sector_ts_code='A.FP' AND trade_date='2026-01-05'"
        )
        con.executemany(
            "INSERT INTO fact_sector_stock_daily VALUES (?,'A.FP',?,'stock',10,?,100,'member','snap-a')",
            [
                ("2026-01-05", "S1", 8),
                ("2026-01-05", "S2", -1),
                ("2026-01-06", "S1", 1),
                ("2026-01-06", "S2", 1),
            ],
        )
        con.executemany(
            "INSERT INTO fact_theme_limit_heat_daily VALUES (?,'A.FP','theme','all',?,2,'fixture')",
            [
                ("2026-01-05", 0),
                ("2026-01-06", 1),
            ],
        )
    row = run(
        db,
        operation="compute_history",
        entity_codes=["A.FP"],
        end="2026-01-06",
        features=[
            "double_red_days",
            "max_double_red_streak",
            "advancer_share",
            "limit_up_share",
            "first_surge_lag",
            "market_relative_return_pct",
        ],
    )["rows"][0]
    assert row["features"] == pytest.approx(
        {
            "double_red_days": 1,
            "max_double_red_streak": 1,
            "advancer_share": 0.75,
            "limit_up_share": 0.25,
            "first_surge_lag": -1,
            "market_relative_return_pct": 2.01,
        }
    )


def test_unknown_feature_and_untyped_extra_parameters_fail_closed():
    base = {
        "operation": "compute_history",
        "entity_codes": ["A.FP"],
        "start": "2026-01-05",
        "end": "2026-01-06",
    }
    with pytest.raises(ValueError, match="unsupported_definition"):
        HistoryQuerySpec.from_arguments(
            {**base, "features": ["invented_catalyst_score"]}
        )
    with pytest.raises(ValueError, match="unknown"):
        HistoryQuerySpec.from_arguments({**base, "sql": "SELECT 1"})


def test_trigger_only_analogue_ranking_ignores_future_values_and_full_path_is_labelled(
    db,
):
    args = dict(
        operation="find_analogues",
        entity_codes=["A.FP", "A.TI"],
        reference_code="A.FP",
        start="2026-01-20",
        end="2026-01-22",
        search_start="2026-01-05",
        search_end="2026-01-19",
        window_days=3,
        step_days=3,
        match_mode="trigger_only",
        preview_limit=1,
    )
    before = run(db, **args)
    assert before["total_matched"] > 1
    assert before["returned_count"] == 1
    assert all(row["feature_cutoff"] == row["end"] for row in before["rows"])
    assert all("forward_return_pct" not in row for row in before["rows"])
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=99,amount=999999 WHERE trade_date>'2026-01-22'"
        )
    after = run(db, **args)
    assert after["rows"] == before["rows"]
    assert after["query_id"] == before["query_id"]
    full = run(db, **{**args, "match_mode": "full_path"})
    assert full["matching_use"] == "retrospective_full_path_discovery"
    assert full["decision_eligible"] is False


def test_compare_freezes_full_universe_before_outcomes_and_counts_all_four_cells(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=0 WHERE sector_ts_code='A.FP'"
        )
        con.executemany(
            "UPDATE fact_sector_daily SET amount=? WHERE sector_ts_code='A.FP' AND trade_date=?",
            [
                (100, "2026-01-05"),
                (200, "2026-01-06"),
                (100, "2026-01-07"),
                (200, "2026-01-08"),
                (200, "2026-01-09"),
                (100, "2026-01-10"),
                (200, "2026-01-11"),
                (100, "2026-01-12"),
            ],
        )
        con.executemany(
            "UPDATE fact_sector_daily SET pct_chg=? WHERE sector_ts_code='A.FP' AND trade_date=?",
            [
                (10, "2026-01-07"),
                (-10, "2026-01-09"),
                (10, "2026-01-11"),
                (-10, "2026-01-13"),
            ],
        )
    args = dict(
        operation="compare_cases",
        entity_codes=["A.FP"],
        start="2026-01-05",
        end="2026-01-12",
        search_start="2026-01-05",
        search_end="2026-01-12",
        features=["amount_ratio"],
        window_days=2,
        step_days=2,
        condition={"feature": "amount_ratio", "op": "gte", "value": 1},
        outcome={"horizon_days": 1, "threshold_pct": 0},
        preview_limit=1,
    )
    before = run(db, **args)
    assert before["total_matched"] == 4
    assert before["returned_count"] == 1
    assert before["comparison"]["four_cells"] == {
        "x_true_y_true": 1,
        "x_true_y_false": 1,
        "x_false_y_true": 1,
        "x_false_y_false": 1,
    }
    assert before["execution_phases"] == [
        "features_read",
        "selection_frozen",
        "outcomes_read",
    ]
    assert all("overlap_cluster" in row for row in before["rows"])
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=10 WHERE sector_ts_code='A.FP' AND trade_date='2026-01-13'"
        )
    after = run(db, **args)
    assert after["selection_fingerprint"] == before["selection_fingerprint"]
    assert after["query_id"] != before["query_id"]
    assert after["comparison"]["four_cells"]["x_false_y_true"] == 2


def test_compare_reports_missing_inputs_and_immature_outcomes_separately(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET amount=NULL WHERE sector_ts_code='A.FP' AND trade_date='2026-02-08'"
        )
    result = run(
        db,
        operation="compare_cases",
        entity_codes=["A.FP"],
        start="2026-02-08",
        end="2026-02-13",
        search_start="2026-02-08",
        search_end="2026-02-13",
        features=["amount_ratio"],
        window_days=2,
        step_days=2,
        condition={"feature": "amount_ratio", "op": "gte", "value": 1},
        outcome={"horizon_days": 1, "threshold_pct": 0},
    )
    assert result["total_matched"] == 3
    assert result["comparison"]["missing"] == 1
    assert result["comparison"]["immature"] == 1
    assert sum(result["comparison"]["four_cells"].values()) == 1


def test_missing_market_day_does_not_shorten_outcome_horizon(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "INSERT INTO fact_stock_daily VALUES ('2026-01-07','S1','stock',10,0,100,'fixture')"
        )
        con.execute("DELETE FROM fact_market_daily WHERE trade_date='2026-01-07'")
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=NULL WHERE trade_date='2026-01-07' AND sector_ts_code='A.FP'"
        )
    result = run(
        db,
        operation="compare_cases",
        entity_codes=["A.FP"],
        start="2026-01-05",
        end="2026-01-06",
        search_start="2026-01-05",
        search_end="2026-01-06",
        features=["amount_ratio"],
        window_days=2,
        step_days=2,
        condition={"feature": "amount_ratio", "op": "gte", "value": 1},
        outcome={"horizon_days": 1, "threshold_pct": 0},
    )
    assert result["rows"][0]["outcome_end"] == "2026-01-07"
    assert result["rows"][0]["comparison_state"] == "missing_outcome"


def test_ambiguous_stock_keys_do_not_silently_pick_one_price(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "INSERT INTO fact_sector_stock_daily VALUES ('2026-01-05','A.FP','S1','stock',10,1,100,'member','snap-a')"
        )
        con.execute(
            "INSERT INTO fact_stock_daily VALUES ('2026-01-05','S1','stock',10,1,100,'one'), ('2026-01-05','S1','stock',50,1,100,'two')"
        )
    result = run(db, entity_codes=["A.FP"], end="2026-01-05")
    assert result["rows"][0]["members"][0]["stock_daily"] is None
    assert result["coverage"]["member_stock_join"]["ambiguous"] == 1


def test_cancelled_or_expired_request_never_creates_database(tmp_path):
    db = tmp_path / "does-not-exist.duckdb"
    spec = HistoryQuerySpec.from_arguments(
        {"operation": "inspect_history", "start": "2026-01-05", "end": "2026-01-06"}
    )
    cutoff = InformationCutoff(date(2026, 2, 13), "requested")
    with pytest.raises(HistoryQueryCancelled):
        HistoryQuery(db).run(
            spec,
            information_cutoff=cutoff,
            deadline=ResearchDeadline.from_timeout(5),
            is_cancelled=lambda: True,
        )
    with pytest.raises(HistoryQueryTimedOut):
        HistoryQuery(db).run(
            spec, information_cutoff=cutoff, deadline=ResearchDeadline.from_timeout(0)
        )
    assert not db.exists()


def test_schema_parser_reject_nonfinite_thresholds_and_unadvertised_shapes():
    assert history_query_parameters()["additionalProperties"] is False
    base = {
        "operation": "compare_cases",
        "entity_codes": ["A.FP"],
        "start": "2026-01-05",
        "end": "2026-01-06",
        "search_start": "2026-01-05",
        "search_end": "2026-01-06",
        "condition": {"feature": "return_pct", "op": "gte", "value": float("nan")},
        "outcome": {"horizon_days": 1, "threshold_pct": 0},
    }
    with pytest.raises(ValueError, match="unsupported_definition"):
        HistoryQuerySpec.from_arguments(base)


def test_simple_aggregate_does_not_scan_unneeded_member_universe(db):
    with duckdb.connect(str(db)) as con:
        con.execute("""INSERT INTO fact_sector_stock_daily
            SELECT DATE '2026-01-05','A.FP','S'||i,'stock',10,1,100,'member','snapshot'
            FROM range(100001) t(i)""")
    result = run(
        db, operation="compute_history", entity_codes=["A.FP"], features=["return_pct"]
    )
    assert result["rows"][0]["features"]["return_pct"] == pytest.approx(
        48.886373, abs=0.000001
    )
    with pytest.raises(ValueError, match="row limit"):
        run(db, entity_codes=["A.FP"], end="2026-01-05")


def test_content_and_membership_versions_change_artifact_identity(db):
    before = run(db, entity_codes=["A.FP"], end="2026-01-05")
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET sector_universe_snapshot_id='snap-b' WHERE sector_ts_code='A.FP'"
        )
    after = run(db, entity_codes=["A.FP"], end="2026-01-05")
    assert before["query_id"] != after["query_id"]
    assert after["source_refs"][0]["snapshot_ids"] == ["snap-b"]


def test_cutoff_and_duplicate_sector_rows_never_silently_change_feature(db):
    with pytest.raises(ValueError, match="cutoff"):
        run(db, entity_codes=["A.FP"], end="2026-02-14")
    with duckdb.connect(str(db)) as con:
        con.execute(
            "INSERT INTO fact_sector_daily SELECT * FROM fact_sector_daily WHERE trade_date='2026-01-05' AND sector_ts_code='A.FP'"
        )
    row = run(db, operation="compute_history", entity_codes=["A.FP"], end="2026-01-06")[
        "rows"
    ][0]
    assert row["features"]["return_pct"] is None


def test_calendar_missing_known_entity_date_cannot_silently_drop_return(db):
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=10 WHERE trade_date='2026-01-06'"
        )
        con.execute("DELETE FROM fact_market_daily WHERE trade_date='2026-01-06'")
    base = dict(entity_codes=["A.FP"], start="2026-01-05", end="2026-01-07")
    with pytest.raises(ValueError, match="calendar_gap"):
        run(db, operation="compute_history", **base)
    with pytest.raises(ValueError, match="calendar_gap"):
        run(
            db,
            operation="find_analogues",
            search_start="2026-01-05",
            search_end="2026-01-07",
            window_days=2,
            **base,
        )
    result = run(db, **base)
    assert result["total_matched"] == 3
    assert any(gap.startswith("calendar_gap") for gap in result["gaps"])


def test_null_heat_denominator_is_missing_instead_of_type_error(db):
    with duckdb.connect(str(db)) as con:
        con.execute("""INSERT INTO fact_theme_limit_heat_daily VALUES
            ('2026-01-05','A.FP','theme','all',1,NULL,'fixture')""")
    result = run(
        db,
        operation="compute_history",
        entity_codes=["A.FP"],
        end="2026-01-05",
        features=["limit_up_share"],
    )
    assert result["rows"][0]["features"]["limit_up_share"] is None
    assert "feature:limit_up_share:missing" in result["gaps"]
