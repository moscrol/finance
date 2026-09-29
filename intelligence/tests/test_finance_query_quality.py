"""Availability gates do not certify truth, fill NULLs, or switch providers."""
from dataclasses import replace
from datetime import date
import hashlib
from pathlib import Path

import duckdb
import pytest

from intelligence.services import finance_query as fq
from intelligence.services import episode_tools
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.task_frame import TaskFrame


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "db").mkdir()
    with duckdb.connect(str(tmp_path / "db/market_feature_store.duckdb")) as con:
        con.execute("""create table fact_mainline_sector_daily (
            trade_date date, sector_ts_code varchar, sector_name varchar,
            theme_name varchar, high_status varchar, amount double, strength double)""")
        con.execute("""insert into fact_mainline_sector_daily values
            ('2026-09-24','A','甲板块','测试',NULL,NULL,NULL),
            ('2026-09-24','B','乙板块','测试','20d',NULL,NULL)""")
        con.execute("""create table fact_sector_daily (
            trade_date date, sector_ts_code varchar, sector_name varchar, sw_l1 varchar, amount double,
            pct_chg double, strength double)""")
        con.execute("""insert into fact_sector_daily values
            ('2026-09-24','A.FP','甲板块','电子',5,0,NULL),
            ('2026-09-24','A.FP','甲板块','电子',0,0,NULL),
            ('2026-09-24','A.FP','甲板块','电子',NULL,0,NULL)""")
        con.execute("""create table fact_sector_stock_daily (
            trade_date date, sector_ts_code varchar, stock_ts_code varchar,
            stock_name varchar, high_status varchar, amount double)""")
        con.execute("""insert into fact_sector_stock_daily values
            ('2026-09-24','A','000001.SZ','缺标记',NULL,5),
            ('2026-09-24','B','000002.SZ','显式否定','非新高',0),
            ('2026-09-24','A','000003.SZ','显式新高','20d',3),
            ('2026-09-24','A','000004.SZ','空串','',2)""")
        con.execute("""create table fact_stock_high_daily (
            trade_date date, stock_ts_code varchar, stock_name varchar,
            primary_high_period varchar, primary_high_label varchar,
            limit_status varchar, price double)""")
        con.execute("""insert into fact_stock_high_daily values
            ('2026-09-24','000001.SZ','缺标记','120d','120日新高',NULL,12),
            ('2026-09-23','000004.SZ','空串','20d','20日新高',NULL,10)""")
        con.execute("""create table fact_stock_daily (
            trade_date date, stock_ts_code varchar, amount double, turnover double)""")
        con.execute("""insert into fact_stock_daily values
            ('2026-09-24','000001.SZ',12,NULL)""")
        con.execute("""create table fact_stock_daily_hithink (
            trade_date date, stock_ts_code varchar, turnover double)""")
        con.execute("""insert into fact_stock_daily_hithink values
            ('2026-09-24','000001.SZ',1200000000)""")
    return tmp_path


def query(root, dataset="mainline_sector_daily", metrics=("amount", "strength"),
          dimensions=("trade_date", "sector_name"), **kwargs):
    return fq.FinanceQuery(root / "db/market_feature_store.duckdb").run(
        fq.FinanceQuerySpec(dataset=dataset, metrics=metrics, dimensions=dimensions, **kwargs),
        information_cutoff=InformationCutoff(date(2026, 9, 24), "requested"),
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_fresh_all_null_metrics_are_flagged_without_erasing_membership(root):
    db = root / "db/market_feature_store.duckdb"
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    result = query(root)
    assert result.served_date == "2026-09-24"
    assert len(result.rows) == len(result.evidence) == 2
    assert len(result.quality_gaps) == 2
    assert result.observation.startswith("字段可用性降级")
    assert all(row["amount"] is None for row in result.rows)
    assert all("字段可用性降级" in e.detail for e in result.evidence)
    assert all(not e.observations for e in result.evidence)
    assert before == hashlib.sha256(db.read_bytes()).hexdigest()


def test_names_only_and_unrequested_fields_do_not_require_numeric_completeness(root):
    result = query(root, metrics=())
    assert not result.quality_gaps
    assert len(result.evidence) == 2
    result = query(root, dataset="sector_daily", metrics=("return_pct",))
    assert not result.quality_gaps  # strength=NULL was not requested; zero is valid.
    assert any(o.value == 0 for e in result.evidence for o in e.observations)


def test_aggregate_partial_input_is_flagged_and_not_minted_as_complete_observation(root):
    result = query(root, dataset="sector_daily", metrics=("amount", "return_pct"),
                   dimensions=("trade_date", "sector_name"), group_by=("trade_date", "sector_name"))
    assert result.rows[0]["amount"] == 5
    assert "2/3" in result.evidence[0].detail
    assert len(result.quality_gaps) == 1
    assert "COUNT(*) AS __quality_rows" in result.audit.physical_sql
    assert not any(k.startswith("__quality") for row in result.rows for k in row)
    assert not any(o.metric == "amount" for e in result.evidence for o in e.observations)
    assert any(o.metric == "pct_chg" for e in result.evidence for o in e.observations)


def test_all_null_aggregate_does_not_become_zero(root):
    result = query(root, dimensions=("trade_date",), group_by=("trade_date",))
    assert result.rows[0]["amount"] is None
    assert result.quality_gaps


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_number_is_unavailable_and_never_structured_evidence(root, value):
    with duckdb.connect(str(root / "db/market_feature_store.duckdb")) as con:
        con.execute("update fact_sector_daily set amount=?", [value])
    result = query(root, dataset="sector_daily", metrics=("amount",))
    assert result.quality_gaps
    assert "不可用（非有限值）" in result.observation
    assert all(not e.observations for e in result.evidence)


def test_unknown_high_marker_does_not_override_explicit_labels_or_mint_false_negative(root):
    result = query(root, dataset="sector_stock_daily", metrics=("amount",),
                   dimensions=("trade_date", "stock_code", "stock_name", "high_status"))
    by_code = {r["stock_code"]: e for r, e in zip(result.rows, result.evidence)}
    for code in ["000001.SZ", "000004.SZ"]:
        assert "新高状态=未知（新高标记未核验）" in by_code[code].detail
        assert "新高状态=非新高" not in by_code[code].detail
    assert "新高状态=非新高" in by_code["000002.SZ"].detail
    assert "新高状态=20d" in by_code["000003.SZ"].detail
    assert "stock_high_daily" in result.quality_gaps[0]


def test_positive_high_lookup_requires_same_day_and_code_and_no_inferred_negative(root):
    result = query(root, dataset="stock_high_daily", metrics=("price",),
                   dimensions=("trade_date", "stock_code", "high_period", "high_label", "limit_status"),
                   filters=(fq.QueryFilter("stock_code", "eq", "000001.SZ"),),
                   time_range=fq.TimeRange(date(2026, 9, 24), date(2026, 9, 24)))
    assert result.rows[0]["high_period"] == "120d"
    assert not result.quality_gaps  # limit_status retains its explicit domain NULL contract.
    assert "涨停状态=非涨停" in result.observation
    missed = query(root, dataset="stock_high_daily", metrics=("price",),
                   dimensions=("trade_date", "stock_code"),
                   filters=(fq.QueryFilter("stock_code", "eq", "000004.SZ"),),
                   time_range=fq.TimeRange(date(2026, 9, 24), date(2026, 9, 24)))
    assert not missed.rows
    assert "非新高" not in missed.observation


def test_sector_marker_does_not_suggest_stock_list_as_sector_proof(root):
    result = query(root, metrics=(), dimensions=("trade_date", "sector_name", "high_status"))
    assert "不能用个股新高名单替代板块状态" in result.quality_gaps[0]


def test_native_turnover_is_not_promoted_into_canonical_turnover(root):
    result = query(root, dataset="stock_daily", metrics=("amount", "turnover"),
                   dimensions=("trade_date", "stock_code"))
    assert result.rows[0]["amount"] == 12
    assert result.rows[0]["turnover"] is None
    assert "stock_daily.turnover" in result.quality_gaps[0]
    assert "1200000000" not in result.observation


def test_latest_nulls_are_not_masked_by_old_or_future_values(root):
    with duckdb.connect(str(root / "db/market_feature_store.duckdb")) as con:
        con.execute("""insert into fact_mainline_sector_daily values
            ('2026-09-23','C','过去','测试','20d',10,1),
            ('2026-09-25','D','未来','测试','20d',20,2)""")
    result = query(root, limit=10, order_by=(fq.Order("trade_date", "desc"),))
    assert result.served_date == "2026-09-24"
    assert len(result.rows) == 3
    assert "2/3" in result.quality_gaps[0]
    assert "未来" not in result.observation


def episode(root, arguments, latest="2026-09-24"):
    frame = TaskFrame(raw_question="核查当前盘面与缺口", user_goal="只读核查", question_type="quick_fact",
        subject="A股市场", subject_kind="market_pattern", market_scope="A股", timeframe="当前",
        required_outputs=("direct_assessment", "evidence_boundary"), assumptions=(), ambiguities=(),
        clarification_question=None, evidence_policy="structured_market_data", confidence=1.0)
    context = build_episode_context(frame, task_id="quality-regression", capabilities=("finance_query",),
        timeout=10, synthesis_reserve=0, today="2026-09-29", latest_data_date=latest)
    registry = episode_tools.build_episode_registry(frame, context, finance_root=root,
        l3_runner=None, evidence_search_judge=None)
    return registry.execute("finance_query", arguments, context=context, step_id="quality")


def test_episode_partial_with_row_bound_warnings_and_machine_gaps(root):
    result = episode(root, {"dataset":"mainline_sector_daily", "metrics":["amount","strength"],
        "dimensions":["trade_date","sector_name"], "limit":3})
    assert result.trace.status == "partial"
    assert len(result.gaps) == 2
    assert len(result.evidence) == 2
    assert result.observation.index("字段可用性降级") < result.observation.index("交易日=")
    assert all("字段可用性降级" in e.detail for e in result.evidence)
    assert result.dataset == "mainline_sector_daily"
    assert result.payload_sha256
    assert result.query_basis["field_quality"]["status"] == "partial"


def test_episode_names_only_stays_success_and_zero_stays_success(root):
    names = episode(root, {"dataset":"mainline_sector_daily", "metrics":[],
        "dimensions":["trade_date","sector_name"]})
    assert names.trace.status == "success"
    assert not names.gaps
    zero = episode(root, {"dataset":"sector_daily", "metrics":["return_pct"],
        "dimensions":["trade_date","sector_name"]})
    assert zero.trace.status == "success"
    assert not zero.gaps


def test_stale_gate_still_precedes_availability_gate(root):
    result = episode(root, {"dataset":"mainline_sector_daily", "metrics":["amount"],
        "dimensions":["trade_date","sector_name"]}, latest="2026-09-28")
    assert result.trace.status == "stale"
    assert not result.evidence


def test_exited_universe_early_return_preserves_quality(root):
    result = query(root)
    output = episode_tools._exited_universe_result(
        replace(result, served_date="2026-09-23"), capability="finance_query",
        provider="duckdb_semantic_query", dataset_label="主线板块", dataset_max_date="2026-09-24",
        detail="test", spec=fq.FinanceQuerySpec(dataset="mainline_sector_daily",
            metrics=("amount",), dimensions=("trade_date","sector_name")))
    assert output.trace.status == "partial"
    assert set(result.quality_gaps).issubset(output.gaps)
    assert "历史" in output.observation


def test_aggregate_reverse_order_keeps_quality_attached_to_correct_date(root):
    with duckdb.connect(str(root / "db/market_feature_store.duckdb")) as con:
        con.execute("""insert into fact_sector_daily values
            ('2026-09-23','A.FP','甲板块','电子',7,1,1)""")
    result = query(root, dataset="sector_daily", metrics=("amount",),
        dimensions=("trade_date",), group_by=("trade_date",),
        order_by=(fq.Order("trade_date", "asc"),),
        time_range=fq.TimeRange(date(2026, 9, 23), date(2026, 9, 24)))
    assert result.rows[0]["trade_date"] == "2026-09-23"
    assert "字段可用性降级" not in result.evidence[0].detail
    assert "字段可用性降级" in result.evidence[1].detail


def test_explicit_finite_sample_mean_contract_is_not_a_full_window_total(root):
    with duckdb.connect(str(root / "db/market_feature_store.duckdb")) as con:
        con.execute("insert into fact_stock_daily values ('2026-09-23','000001.SZ',NULL,NULL)")
        con.execute("insert into fact_stock_daily values ('2026-09-22','000001.SZ',?,NULL)", [float("nan")])
    result = query(root, dataset="stock_daily", metrics=("amount_mean", "amount_valid_count"),
        dimensions=("stock_code",), group_by=("stock_code",),
        time_range=fq.TimeRange(date(2026, 9, 22), date(2026, 9, 24)))
    assert result.rows[0]["amount_mean"] == 12
    assert result.rows[0]["amount_valid_count"] == 1
    assert not result.quality_gaps
    assert "样本数不证明交易日齐全" in result.observation
