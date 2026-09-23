"""Read-only derived breadth and sector classification provenance."""
from datetime import date

import duckdb
import pytest

from intelligence.services.finance_query import FinanceQuery, FinanceQuerySpec, FinanceQueryValidationError
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "breadth.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR, pct_chg DOUBLE, source VARCHAR)")
        con.executemany("INSERT INTO fact_stock_daily VALUES (?, ?, ?, ?)", [
            ("2026-09-18", "a", 2, "eastmoney:snapshot"),
            ("2026-09-18", "b", -1, "eastmoney:snapshot"),
            ("2026-09-18", "c", -2, "eastmoney:snapshot"),
            ("2026-09-18", "d", 0, "eastmoney:snapshot"),
            ("2026-09-17", "a", None, "test"),
            ("2026-09-17", "b", 0, "test"),
            ("2026-09-16", "a", float("nan"), "test"),
            ("2026-09-15", "a", -1, "test"),
            ("2026-09-15", "a", -1, "test"),
            ("2026-09-21", "a", -9, "future"),
        ])
        con.execute("CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code VARCHAR, sector_name VARCHAR, pct_chg DOUBLE, source VARCHAR)")
        con.executemany("INSERT INTO fact_sector_daily VALUES (?, ?, ?, ?, ?)", [
            ("2026-09-18", "1.FP", "板块甲", 4, "local:agg/pct=eqw"),
            ("2026-09-18", "2.TI", "板块乙", 3, "ifind:test"),
            ("2026-09-18", "other", "板块丙", 2, None),
        ])
    return path


def run(db, dataset="market_breadth_daily", **overrides):
    spec = dict(dataset=dataset, dimensions=["trade_date", "source"],
                metrics=["advancers", "decliners", "unchanged", "observed_stocks", "valid_returns", "missing_returns"],
                time_range={"start": "2026-09-18", "end": "2026-09-18"})
    spec.update(overrides)
    return FinanceQuery(db).run(FinanceQuerySpec.from_arguments(spec),
                               information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
                               deadline=ResearchDeadline.from_timeout(2))


def test_breadth_aggregates_full_day_before_return_limit(db):
    result = run(db, limit=1)
    assert result.rows == ({"trade_date": "2026-09-18", "source": "eastmoney:snapshot",
                            "advancers": 1, "decliners": 2, "unchanged": 1,
                            "observed_stocks": 4, "valid_returns": 4, "missing_returns": 0},)
    assert "下跌家数=2" in result.observation
    assert "eastmoney:snapshot" in result.observation
    assert "future" not in result.observation
    assert result.evidence[0].source_date == "2026-09-18"
    assert "fact_stock_daily" in result.audit.physical_sql


@pytest.mark.parametrize("day, missing", [("2026-09-17", 1), ("2026-09-16", 1), ("2026-09-15", 0)])
def test_missing_nonfinite_and_duplicate_quotes_do_not_become_valid_counts(db, day, missing):
    result = run(db, time_range={"start": day, "end": day})
    assert result.rows[0]["missing_returns"] == missing
    assert all(result.rows[0][metric] is None for metric in ("advancers", "decliners", "unchanged"))
    assert "下跌家数=未知" in result.observation


def test_absent_day_is_empty_not_zero_or_previous_day(db):
    result = run(db, time_range={"start": "2026-09-14", "end": "2026-09-14"})
    assert result.rows == ()
    assert result.evidence == ()


def test_future_window_still_rejected(db):
    with pytest.raises(FinanceQueryValidationError, match="cutoff"):
        run(db, time_range={"start": "2026-09-21", "end": "2026-09-21"})


def test_sector_provenance_survives_omitted_code_and_source(db):
    result = run(db, "sector_daily", dimensions=["sector_name"], metrics=["return_pct"],
                 order_by=[{"field": "return_pct", "direction": "desc"}])
    assert list(result.rows[0]) == ["sector_name", "return_pct"]
    assert "复盘会板块清单（.FP）" in result.evidence[0].detail
    assert "同花顺板块清单（.TI）" in result.evidence[1].detail
    assert "未识别板块码系" in result.evidence[2].detail
    assert "复盘会" not in result.evidence[1].detail


def test_grouped_sector_evidence_discloses_mixed_universes(db):
    result = run(db, "sector_daily", dimensions=["trade_date"], metrics=["return_pct"],
                 group_by=["trade_date"])
    assert len(result.rows) == 1
    assert "复盘会" in result.observation and "同花顺" in result.observation


def test_sector_numeric_source_is_separate_from_classification(db):
    result = run(db, "sector_daily", dimensions=["sector_name", "source"], metrics=["return_pct"],
                 order_by=[{"field": "return_pct", "direction": "desc"}])
    assert "local:agg/pct=eqw" in result.evidence[0].detail
    assert "复盘会" in result.evidence[0].detail
