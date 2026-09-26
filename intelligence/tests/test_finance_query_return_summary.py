"""Bounded return summaries: frozen live errors and adversarial data shapes."""
from datetime import date, timedelta
import json
import math
import socket
import subprocess
from uuid import uuid4

import duckdb
import pytest

from intelligence.services import agent_research, episode_tools, finance_query as fq
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.tool_result_budget import budget_tool_observation


# Frozen daily percentages from run_20260922_002223_310816, not model totals.
DAYS = (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)
SERIES = {
    "600673.SH": (-4.77, -1.52, 3.38, -4.98, 3.7, -1.5161, 1.35, .09, -1.2, -.61, .39, 1.5715, .22, 1.2),
    "990325.FP": (-1.4, -.72, -.1579, -1.8276, 2.1897, -.3223, -.3016, -1.1143, -1.521, .7835, -.1284, 2.9846, -.3727, 2.6213),
    "990231.FP": (-1.45, -1.13, -.1228, -2.0713, 1.0243, .5671, .211, -1.6734, -2.4618, .5301, .1091, 2.2419, -.6807, 1.3716),
    "990313.FP": (-1.82, -1.73, -1.1267, .6283, .9056, 2.486, -.3656, -1.3994, -1.6633, -.3383, -2.7644, 1.687, -.1239, 1.4111),
    "801230": (-1.6391962590860731, -1.7048757469422027, .757084196286395, -1.962373193098188, 2.714520832171874, 1.8036237663949795, .7318017343492356, -.8958527975552188, -2.1982283213170306, -.8644390524171541, -1.6912661025919817, 1.6428945541358653, -.17903407878938626, 1.3282367968652453),
}
DATASETS = {
    "stock_daily": ("stock_code", "stock_ts_code", "600673.SH"),
    "sector_daily": ("sector_code", "sector_ts_code", "990325.FP"),
    "sw_l1_daily": ("sw_l1_code", "sw_l1_code", "801230"),
}
METRICS = ["return_compound_pct", "return_valid_count", "return_observed_count", "return_min_pct", "return_max_pct"]


@pytest.fixture
def return_db(tmp_path):
    path = tmp_path / "finance/db/market_feature_store.duckdb"
    path.parent.mkdir(parents=True)
    with duckdb.connect(str(path)) as con:
        for dataset, (_, column, code) in DATASETS.items():
            con.execute(f'CREATE TABLE fact_{dataset} (trade_date DATE, {column} VARCHAR, pct_chg DOUBLE)')
            codes = [c for c in SERIES if c.endswith(".FP")] if dataset == "sector_daily" else [code]
            for entity in codes:
                con.executemany(f"INSERT INTO fact_{dataset} VALUES (?, ?, ?)", [
                    (date(2026, 9, day), entity, value) for day, value in zip(DAYS, SERIES[entity])
                ] + [(date(2026, 8, 31), entity, 80), (date(2026, 9, 21), entity, 80)])
    return path


def arguments(dataset="stock_daily", **overrides):
    key, _, code = DATASETS[dataset]
    values = dict(dataset=dataset, metrics=METRICS, dimensions=[key], group_by=[key],
                  filters=[{"field": key, "op": "eq", "value": code}],
                  time_range={"start": "2026-09-01", "end": "2026-09-18"}, limit=1)
    values.update(overrides)
    return values


def run(path, dataset="stock_daily", **overrides):
    return fq.FinanceQuery(path).run(fq.FinanceQuerySpec.from_arguments(arguments(dataset, **overrides)),
                                   information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
                                   deadline=ResearchDeadline.from_timeout(5))


@pytest.mark.parametrize("dataset,code,expected", [
    ("stock_daily", "600673.SH", -3.076590776511101),
    ("sector_daily", "990325.FP", .5615237044258592),
    ("sector_daily", "990231.FP", -3.597349066313904),
    ("sector_daily", "990313.FP", -4.282013992367906),
    ("sw_l1_daily", "801230", -2.3047363303856927),
])
def test_frozen_live_series_computed_before_limit(return_db, dataset, code, expected):
    key = DATASETS[dataset][0]
    result = run(return_db, dataset, filters=[{"field": key, "op": "eq", "value": code}])
    row, = result.rows
    assert row["return_compound_pct"] == pytest.approx(expected)
    assert row["return_compound_pct"] == pytest.approx((math.prod(1 + x / 100 for x in SERIES[code]) - 1) * 100)
    assert row["return_valid_count"] == row["return_observed_count"] == 14
    assert row["return_min_pct"] == min(SERIES[code])
    assert row["return_max_pct"] == max(SERIES[code])
    evidence, = result.evidence
    assert "请求=2026-09-01..2026-09-18" in evidence.detail
    assert "日期=2026-09:01,02" in evidence.detail
    assert f"代码={code}" in evidence.detail
    assert len(evidence.detail) <= 240
    assert "样本数不证明交易日齐全" in evidence.detail
    assert "逐日复利" in evidence.detail
    assert evidence.observations == ()
    assert evidence.content_hash == agent_research.evidence_content_hash(evidence)
    assert code not in result.audit.physical_sql
    assert code in result.audit.bound_parameters
    assert result.audit.row_count == result.audit.applied_limit == 1


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), -100.01])
def test_bad_row_invalidates_whole_chain_instead_of_skipping(return_db, bad):
    with duckdb.connect(str(return_db)) as con:
        con.execute("UPDATE fact_stock_daily SET pct_chg=? WHERE trade_date='2026-09-02'", [bad])
    row, = run(return_db).rows
    assert row["return_valid_count"] == 13
    assert row["return_observed_count"] == 14
    assert all(row[name] is None for name in ("return_compound_pct", "return_min_pct", "return_max_pct"))


def test_duplicate_day_fails_even_when_values_agree(return_db):
    with duckdb.connect(str(return_db)) as con:
        con.execute("INSERT INTO fact_stock_daily SELECT * FROM fact_stock_daily WHERE trade_date='2026-09-02'")
    row, = run(return_db).rows
    assert row["return_valid_count"] == row["return_observed_count"] == 15
    assert row["return_compound_pct"] is row["return_max_pct"] is None


@pytest.mark.parametrize("value,expected", [(0, 0), (-100, -100), (1e308, None)])
def test_zero_total_loss_and_overflow(return_db, value, expected):
    with duckdb.connect(str(return_db)) as con:
        con.execute("UPDATE fact_stock_daily SET pct_chg=?", [value])
    row, = run(return_db).rows
    assert row["return_compound_pct"] == expected
    assert row["return_valid_count"] == 14


def test_empty_is_not_zero_return(return_db):
    result = run(return_db, filters=[{"field": "stock_code", "op": "eq", "value": "999999.SH"}])
    assert result.rows == result.evidence == ()


def test_group_ranking_and_cap_never_limit_input_days(return_db):
    result = run(return_db, "sector_daily", filters=[], limit=2,
                 order_by=[{"field": "return_compound_pct", "direction": "desc"}])
    assert [r["sector_code"] for r in result.rows] == ["990325.FP", "990231.FP"]
    assert [r["return_valid_count"] for r in result.rows] == [14, 14]
    with duckdb.connect(str(return_db)) as con:
        con.execute("DELETE FROM fact_stock_daily")
        con.executemany("INSERT INTO fact_stock_daily VALUES (?, '600673.SH', 1)", [
            (date(2026, 8, 20) + timedelta(days=i),) for i in range(30)
        ])
    row, = run(return_db, time_range={"start": "2026-08-20", "end": "2026-09-18"}).rows
    assert row["return_compound_pct"] == pytest.approx((1.01 ** 30 - 1) * 100)
    assert row["return_observed_count"] == 30


def test_window_and_date_set_survive_evidence_identity(return_db):
    left = run(return_db, time_range={"start": "2026-09-05", "end": "2026-09-18"})
    right = run(return_db, time_range={"start": "2026-09-06", "end": "2026-09-18"})
    assert left.rows == right.rows
    assert left.evidence[0].content_hash != right.evidence[0].content_hash
    with duckdb.connect(str(return_db)) as con:
        con.execute("UPDATE fact_stock_daily SET trade_date='2026-09-05' WHERE trade_date='2026-09-07'")
    moved = run(return_db, time_range={"start": "2026-09-05", "end": "2026-09-18"})
    assert left.rows == moved.rows
    assert left.evidence[0].content_hash != moved.evidence[0].content_hash


@pytest.mark.parametrize("override,match", [
    ({"metrics": ["return_compound_pct"]}, "together"),
    ({"metrics": ["return_max_pct"]}, "together"),
    ({"group_by": []}, "dimensions and group_by"),
    ({"dimensions": ["stock_name"], "group_by": ["stock_name"]}, "dimensions and group_by"),
    ({"dimensions": ["stock_code", "trade_date"], "group_by": ["stock_code", "trade_date"]}, "dimensions and group_by"),
    ({"time_range": None}, "explicit time_range"),
    ({"time_range": {"end": "2026-09-18"}}, "explicit time_range"),
    ({"metrics": METRICS + ["return_pct"]}, "only return summary metrics"),
    ({"filters": [{"field": "return_pct", "op": "gt", "value": 0}]}, "only stock_code"),
    ({"filters": [{"field": "stock_name", "op": "eq", "value": "sample"}]}, "only stock_code"),
    ({"time_range": {"start": "2026-09-01", "end": "2026-09-21"}}, "cutoff"),
])
def test_invalid_summary_fails_before_io(tmp_path, override, match):
    with pytest.raises(fq.FinanceQueryValidationError, match=match):
        run(tmp_path / "missing.duckdb", **override)


@pytest.mark.parametrize("metric", METRICS)
def test_summary_alias_never_acts_as_daily_row_filter(tmp_path, metric):
    with pytest.raises(fq.FinanceQueryValidationError, match="cannot be used as row filters"):
        run(tmp_path / "missing.duckdb", metrics=["return_pct"], dimensions=["trade_date"], group_by=[],
            filters=[{"field": metric, "op": "gt", "value": 0}])


def test_existing_grouped_daily_average_is_not_labelled_cumulative(return_db):
    result = run(return_db, metrics=["return_pct"])
    assert result.rows[0]["return_pct"] == pytest.approx(sum(SERIES["600673.SH"]) / 14)
    assert "平均日涨跌幅" in result.evidence[0].detail
    assert "不是累计收益" in result.evidence[0].detail


@pytest.mark.parametrize("dataset", DATASETS)
def test_local_registry_delivers_summary_without_external_io(return_db, tmp_path, monkeypatch, dataset):
    frame = understand_query("只用本地已有资料，不联网：东阳光600673.SH从2026-09-01至2026-09-18与板块相比强弱如何？").task_frame
    context = build_episode_context(frame, task_id=f"return-{uuid4().hex}", capabilities=tuple(sorted(LOCAL_READ_CAPABILITIES)),
                                    today="2026-09-18", latest_data_date="2026-09-18", timeout=15, synthesis_reserve=0)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unexpected network/subprocess/calculator")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(episode_tools, "_calc_loader_for", forbidden)
    registry = episode_tools.build_episode_registry(frame, context, finance_root=return_db.parent.parent,
                knowledge_wiki=tmp_path / "wiki", memory_users_root=tmp_path / "users", derived_calculation_runner=forbidden)
    assert set(registry.names()) == LOCAL_READ_CAPABILITIES
    definition = next(x["function"] for x in registry.tool_definitions(context.contract.allowed_capabilities) if x["function"]["name"] == "finance_query")
    assert "return_compound_pct" in definition["parameters"]["properties"]["dataset"]["description"]
    result = registry.execute("finance_query", arguments(dataset), context=context, step_id="return-summary")
    assert result.trace.status == "success"
    assert result.evidence[0].io_effect == "local_read"
    assert calls == []
    delivered = budget_tool_observation({"observation": result.observation, "evidence": [{"detail": e.detail} for e in result.evidence]})
    assert "逐日复利" in delivered["evidence"][0]["detail"]
    assert "2026-09-01..2026-09-18" in delivered["observation"]
    assert delivered["evidence"][0]["detail"] == result.evidence[0].detail
    assert "日期=2026-09:01,02,03,04,07,08,09,10,11,14,15,16,17,18" in delivered["evidence"][0]["detail"]
    projection = FinanceResearchHarness().project_tool_result(result, evidence_so_far=result.evidence, seen_prose=set())
    payload = json.loads(projection.model_content)
    assert payload["evidence"][0]["detail"] == result.evidence[0].detail
    again = FinanceResearchHarness().project_tool_result(result, evidence_so_far=result.evidence, seen_prose=projection.seen_prose)
    assert result.evidence[0].detail in again.model_content


@pytest.mark.parametrize("identity", [None, "", " "])
def test_missing_subject_never_certifies_return(return_db, identity):
    with duckdb.connect(str(return_db)) as con:
        con.execute("UPDATE fact_stock_daily SET stock_ts_code=?", [identity])
    row, = run(return_db, filters=[]).rows
    assert row["return_observed_count"] == 14
    assert row["return_compound_pct"] is row["return_max_pct"] is None


def test_same_count_different_dates_are_not_presented_as_aligned(return_db):
    original = run(return_db)
    with duckdb.connect(str(return_db)) as con:
        con.execute("UPDATE fact_stock_daily SET trade_date='2026-09-05' WHERE trade_date='2026-09-07'")
    changed = run(return_db)
    assert original.rows == changed.rows
    assert "日期=2026-09:01,02,03,04,05,08" in changed.evidence[0].detail
    assert original.evidence[0].content_hash != changed.evidence[0].content_hash


def test_sector_code_universes_survive_projection_without_name_merging(return_db):
    with duckdb.connect(str(return_db)) as con:
        con.execute("INSERT INTO fact_sector_daily SELECT trade_date, '990325.TI', pct_chg FROM fact_sector_daily WHERE sector_ts_code='990325.FP'")
    result = run(return_db, "sector_daily", filters=[], limit=10)
    assert len(result.rows) == 4
    cards = {r["sector_code"]: e.detail for r, e in zip(result.rows, result.evidence)}
    assert "复盘会板块清单（.FP）" in cards["990325.FP"]
    assert "同花顺板块清单（.TI）" in cards["990325.TI"]
    assert all(len(detail) <= 240 for detail in cards.values())


def test_long_date_set_refuses_instead_of_delivering_truncated_card(return_db):
    with duckdb.connect(str(return_db)) as con:
        con.execute("DELETE FROM fact_stock_daily")
        con.executemany("INSERT INTO fact_stock_daily VALUES (?, '600673.SH', 1)", [
            (date(2026, 6, 1) + timedelta(days=i),) for i in range(90)
        ])
    with pytest.raises(fq.FinanceQueryLimitExceeded, match="缩短 time_range"):
        run(return_db, time_range={"start": "2026-06-01", "end": "2026-09-18"})


def test_sample_day_extrema_exposes_the_live_counterexample(return_db):
    row, = run(return_db, time_range={"start": "2026-09-05", "end": "2026-09-18"}).rows
    assert row["return_max_pct"] == 3.7
    assert row["return_min_pct"] == -1.5161


def test_relative_direction_from_same_observed_dates(return_db):
    stock = run(return_db)
    fluorine = run(return_db, "sector_daily", filters=[{"field": "sector_code", "op": "eq", "value": "990231.FP"}])
    assert stock.rows[0]["return_compound_pct"] - fluorine.rows[0]["return_compound_pct"] == pytest.approx(.520758289802803)


def test_connection_is_read_only_and_summary_hint_describes_contract(return_db):
    calls = []

    def connect(path, *, read_only):
        calls.append(read_only)
        return duckdb.connect(path, read_only=read_only)

    spec = fq.FinanceQuerySpec.from_arguments(arguments())
    fq.FinanceQuery(return_db, connect=connect).run(spec, information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
                                                deadline=ResearchDeadline.from_timeout(5))
    assert calls == [True]
    hint = fq.validation_retry_hint(spec, fq.FinanceQueryValidationError("return summary requires grouping"))
    assert all(name in hint for name in ("return_compound_pct", "return_valid_count", "return_observed_count", "stock_code", "time_range"))
