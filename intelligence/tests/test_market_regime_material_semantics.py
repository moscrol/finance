"""D10 materials must describe why a dimension is unusable, not invent absence.

Synthetic DuckDB → actual loader/artifact/renderer/transport; no provider calls.
The historical two-value loader API remains compatible for other consumers.
"""
from __future__ import annotations

import hashlib
import yaml
import socket

import duckdb
import pytest

from intelligence.history_context_cli import history_payload
from intelligence.services import market_regime_analogs as regime
from intelligence.tests.test_river_history_consumption import CUTOFF, _make_db
from market_feature_store import market_regime_vectors as vectors


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("D10 semantic regression attempted network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "synthetic.duckdb"
    _make_db(path)
    return path


def artifact(db):
    return regime.load_market_regime_artifact(db, as_of=CUTOFF)


def block(db):
    return regime.regime_block_for_llm(db, as_of=CUTOFF)


def model(db):
    return yaml.safe_load(block(db).split("```yaml\n")[1].split("\n```")[0])


def model_observations(db):
    payload = model(db)
    table = payload["feature_observations"]
    return {payload["feature_keys"][label]: {
                **table["defaults"], **dict(zip(table["columns"], row, strict=True)),
                **{k: overrides[label] for k, overrides in table["overrides"].items() if label in overrides},
            } for label, row in table["features"].items()}


def test_constants_are_not_claimed_as_empty_tables(db):
    result = artifact(db)
    assert result.available
    assert "对应表无数据" not in block(db)  # existing wrong behavior, independent of new fields
    assert result.constant_features == ("double_red_theme_count", "new_high_count")
    assert result.empty_features == result.query_failed_features == ()
    assert result.current_summary["double_red_theme_count"] == 1
    text = block(db)
    assert "常量退出" in text
    observations = model_observations(db)
    assert {f for f, o in observations.items() if o["comparison_status"] == "constant"} == set(result.constant_features)
    assert observations["double_red_theme_count"]["non_null_days"] == 48
    assert "对应表无数据" not in text
    assert "已按覆盖率降权" not in text  # globally dropped != pairwise coverage penalty
    assert "首题材涨停份额" in text
    assert "绝对占比高低" in text


@pytest.mark.parametrize("mode", ["missing_table", "empty", "future_only", "null_values"])
def test_query_failure_is_distinct_from_no_observations_in_fit_range(db, mode):
    with duckdb.connect(str(db)) as con:
        if mode == "missing_table":
            con.execute("DROP TABLE fact_theme_limit_heat_daily")
        elif mode == "empty":
            con.execute("DELETE FROM fact_theme_limit_heat_daily")
        elif mode == "future_only":
            con.execute("DELETE FROM fact_theme_limit_heat_daily WHERE trade_date <= ?", [CUTOFF])
        else:
            con.execute("UPDATE fact_theme_limit_heat_daily SET market_share = NULL")
    result = artifact(db)
    assert result.available
    if mode == "missing_table":
        assert result.query_failed_features == ("top1_theme_share",)
        assert result.empty_features == ()
        assert "查询失败" in block(db)
    else:
        assert result.query_failed_features == ()
        assert result.empty_features == ("top1_theme_share",)
        assert "范围无非空" in block(db)
    observation = model_observations(db)["top1_theme_share"]
    assert observation["comparison_status"] == ("query_failed" if mode == "missing_table" else "empty")
    assert observation["read_status"] == ("query_failed" if mode == "missing_table" else "queried")
    assert "top1_theme_share" not in result.constant_features
    assert "对应表无数据" not in block(db)


@pytest.mark.parametrize("mode", ["empty", "missing_table", "missing_column"])
def test_base_query_failure_does_not_report_no_rows(db, mode):
    with duckdb.connect(str(db)) as con:
        if mode == "empty":
            con.execute("DELETE FROM fact_market_daily")
        elif mode == "missing_table":
            con.execute("DROP TABLE fact_market_daily")
        else:
            con.execute("ALTER TABLE fact_market_daily DROP COLUMN advancers")
    result = artifact(db)
    assert not result.available
    if mode == "empty":
        assert "截止范围内无行" in result.degrade_reason
        assert "查询失败" not in result.degrade_reason
    else:
        assert "查询失败" in result.degrade_reason
        assert "无数据" not in result.degrade_reason
    assert str(db) not in result.degrade_reason
    assert block(db) == ""  # existing unavailable-block contract stays intact


@pytest.mark.parametrize("mode, count", [("empty", 0), ("missing_head", 14)])
def test_current_signature_loss_is_not_hidden_by_global_variance(db, mode, count):
    with duckdb.connect(str(db)) as con:
        end = "2025-04-10" if mode == "empty" else "2025-03-21"
        con.execute("UPDATE fact_market_daily SET advancers=NULL WHERE trade_date BETWEEN ? AND ?",
                    ["2025-03-14", end])
    result = artifact(db)
    assert result.available
    assert "advancers" in result.active_features
    assert result.current_missing_features == ("advancers",)
    assert result.current_feature_counts["advancers"] == count
    assert "advancers" not in result.current_signature_features
    assert "advancers" not in result.empty_features
    for candidate in result.analogs:
        assert "advancers" not in candidate["shared_features"]
        assert candidate["active_dims"] == len(result.active_features)
        assert candidate["shared_dims"] == len(candidate["shared_features"])
    text = block(db)
    payload = model(db)
    assert payload["current_gap_days"]["涨家数"] == count
    assert payload["selection"]["window_days"] == 20
    assert "首尾段覆盖" in text
    assert "共有维覆盖" in text


@pytest.mark.parametrize("stamp", ["2025-06-01", None, "not-a-timestamp"])
def test_trade_date_only_is_not_proof_of_a_rewrite(db, stamp):
    with duckdb.connect(str(db)) as con:
        con.execute("ALTER TABLE fact_market_daily ALTER COLUMN updated_at TYPE VARCHAR")
        con.execute("UPDATE fact_market_daily SET updated_at=?", [stamp])
    result = artifact(db)
    assert result.pit_grade == "trade_date_only"
    text = block(db)
    assert "之后被重写过" not in text
    assert "晚于截止、缺失或不可解析" in text
    assert "不能区分首次迟入库与覆盖修订" in text
    assert "不等于逐日历史可知" in text
    assert "辅表" in text


def test_strict_base_timestamp_does_not_certify_auxiliary_history(db):
    with duckdb.connect(str(db)) as con:
        con.execute("UPDATE fact_market_daily SET updated_at='2025-04-01'")
    result = artifact(db)
    assert result.pit_grade == "strict"  # marker algorithm unchanged
    text = block(db)
    assert model(db)["pit_grade"] == "strict"
    assert "fact_market_daily.updated_at" in text
    assert "不等于逐日历史可知" in text
    assert "辅表" in text


def test_detailed_loader_preserves_legacy_vector_values_and_missing_return(db):
    with duckdb.connect(str(db), read_only=True) as con:
        detailed = vectors.load_market_regime_vector_result(con, as_of=CUTOFF, knowledge_cutoff=CUTOFF)
        legacy_rows, legacy_missing = vectors.load_market_regime_vectors(
            con, as_of=CUTOFF, knowledge_cutoff=CUTOFF,
        )
    assert detailed.status == "available"
    assert detailed.vectors == legacy_rows
    assert list(detailed.query_failed_features) == legacy_missing
    # No source-day coverage contract yet: nonmatching double-red days stay None, not 0.
    assert any(row["double_red_theme_count"] is None for row in legacy_rows)
    assert any(row["double_red_theme_count"] == 1 for row in legacy_rows)
    assert all(row["trade_date"] <= CUTOFF.isoformat() for row in legacy_rows)


def test_real_transport_receives_corrected_material_without_database_writes(db):
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    payload = history_payload(db, as_of=CUTOFF.isoformat())
    detail = payload["blocks"][0]["detail"]
    assert "常量退出" in detail and "不能区分首次迟入库与覆盖修订" in detail
    assert payload["blocks"][0]["sha256"] == hashlib.sha256(detail.encode()).hexdigest()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert payload["evidence_grade"] == "INFERRED"


def test_endpoint_sample_frequency_and_path_questions_are_separate(db):
    text = block(db)
    assert "终点收益大于0" in text
    assert "样本频率" in text
    assert "终点收益不描述区间内的涨跌路径" in text
    assert "不是概率预测" in text


@pytest.mark.parametrize("mode", ["missing_table", "empty", "future_only"])
def test_base_loader_diagnostics_keep_legacy_two_value_contract(db, mode):
    with duckdb.connect(str(db)) as con:
        if mode == "missing_table":
            con.execute("DROP TABLE fact_market_daily")
        elif mode == "empty":
            con.execute("DELETE FROM fact_market_daily")
        else:
            con.execute("DELETE FROM fact_market_daily WHERE trade_date <= ?", [CUTOFF])
    with duckdb.connect(str(db), read_only=True) as con:
        result = vectors.load_market_regime_vector_result(con, as_of=CUTOFF)
        legacy = vectors.load_market_regime_vectors(con, as_of=CUTOFF)
    assert result.status == ("query_failed" if mode == "missing_table" else "empty")
    assert result.vectors == []
    assert result.query_failed_features == ()  # aux queries never ran
    assert legacy == ([], list(vectors.FEATURES))


def test_loader_query_exception_is_not_mislabeled_empty_and_does_not_leak_sql(db, monkeypatch):
    monkeypatch.setitem(vectors._AUX_QUERIES, "top1_theme_share", "select PRIVATE_SQL_SENTINEL from missing_source")
    result = artifact(db)
    assert result.query_failed_features == ("top1_theme_share",)
    assert result.empty_features == ()
    assert "PRIVATE_SQL_SENTINEL" not in block(db)
    assert "查询失败" in block(db)


def test_zero_is_observed_constant_and_old_api_keeps_dropped_order():
    rows = [{"zero": 0.0, "empty": None, "moving": value} for value in (1, 2, 3)]
    features = ("zero", "empty", "moving")
    z_rows, reasons = regime._standardize_vectors_with_reasons(rows, features)
    legacy_rows, dropped = regime.standardize_vectors(rows, features)
    assert reasons == {"zero": "constant", "empty": "empty"}
    assert legacy_rows == z_rows and dropped == ["zero", "empty"]
    assert set(z_rows[0]) == {"moving"}


def test_candidate_signature_gap_is_disclosed_without_changing_rank(db):
    with duckdb.connect(str(db)) as con:
        con.execute("UPDATE fact_market_daily SET advancers=NULL WHERE trade_date < '2025-03-14'")
    result = artifact(db)
    assert result.available and result.current_missing_features == ()
    for candidate in result.analogs:
        assert "advancers" in candidate["missing_features"]
        assert "advancers" not in candidate["shared_features"]
        assert candidate["shared_dims"] == candidate["active_dims"] - 1
        payload = model(db)
        ref = next(k for k, dates in payload["windows"].items()
                   if dates == [candidate["start_date"], candidate["end_date"]])
        table = payload["candidates"]
        rendered = dict(zip(table["columns"], table["windows"][ref], strict=True))
        assert (rendered["shared_dims"], rendered["active_dims"]) == (candidate["shared_dims"], candidate["active_dims"])
        assert "涨家数" in rendered["missing_features"]
