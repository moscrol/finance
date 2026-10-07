"""Market statistics must keep their denominators in the model-visible tool result.

Synthetic rows reproduce live measurement shapes, not frozen answers: different
ratio denominators, a full ladder with incomplete cohort success, unverified
money units, and ambiguous foreign dates. Aggregate fixtures do not prove actual
membership overlap. No model call or production DB write.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services import episode_tools, finance_query as fq
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.task_frame import TaskFrame


@pytest.fixture
def market_root(tmp_path: Path) -> Path:
    (tmp_path / "db").mkdir()
    with duckdb.connect(str(tmp_path / "db/market_feature_store.duckdb")) as con:
        con.execute("""CREATE TABLE fact_theme_limit_heat_daily (
            trade_date DATE, sector_name VARCHAR, limit_up_count INTEGER,
            market_limit_up_count INTEGER, total_count INTEGER,
            limit_up_ratio DOUBLE, market_share DOUBLE, rank INTEGER)""")
        con.execute("""INSERT INTO fact_theme_limit_heat_daily VALUES
            ('2026-07-22', '甲方向', 6, 30, 120, 5, 20, 1),
            ('2026-07-22', '乙方向', 6, 30, 60, 10, 20, 2)""")
        con.execute("""CREATE TABLE fact_limit_advance_daily (
            trade_date DATE, stock_name VARCHAR, boards INTEGER,
            promotion_rate VARCHAR)""")
        con.execute("""INSERT INTO fact_limit_advance_daily VALUES
            ('2026-07-22', '甲股', 4, '1/1=100%'),
            ('2026-07-22', '乙股', 3, '1/4=25%'),
            ('2026-07-22', '丙股', 2, '2/20=10%'),
            ('2026-07-22', '丁股', 2, '2/20=10%')""")
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE, limit_up INTEGER)")
        con.execute("INSERT INTO fact_market_daily VALUES ('2026-07-22', 30)")
        con.execute("CREATE TABLE fact_mainline_theme_daily (trade_date DATE, sector_count INTEGER)")
        con.execute("INSERT INTO fact_mainline_theme_daily VALUES ('2026-07-22', 2)")
        con.execute("""CREATE TABLE fact_mainline_sector_daily (
            trade_date DATE, sector_name VARCHAR, amount DOUBLE, net_inflow_1d DOUBLE)""")
        con.execute("INSERT INTO fact_mainline_sector_daily VALUES ('2026-07-22', '甲板块', 7022875.4, 4473476293)")
        con.execute("""CREATE TABLE fact_leader_height_daily (
            trade_date DATE, leader_name VARCHAR, height INTEGER, fd_amount DOUBLE)""")
        con.execute("INSERT INTO fact_leader_height_daily VALUES ('2026-07-22', '甲股', 5, 23686.2996)")
        con.execute("""CREATE TABLE fact_global_index_daily (
            trade_date DATE, source_trade_date DATE, code VARCHAR, close DOUBLE, pct_chg DOUBLE)""")
        con.execute("INSERT INTO fact_global_index_daily VALUES ('2026-07-22', '2026-07-22', 'IXIC', 100, 0.6214)")
    return tmp_path


def spec(dataset: str) -> fq.FinanceQuerySpec:
    fields = {
        "theme_limit_heat_daily": (
            ("limit_up_count", "market_limit_up_count", "total_count", "limit_up_ratio", "market_share"),
            ("trade_date", "sector_name"),
        ),
        "limit_advance_daily": (("boards",), ("trade_date", "stock_name", "promotion_rate")),
        "market_daily": (("limit_up",), ("trade_date",)),
        "mainline_theme_daily": (("sector_count",), ("trade_date",)),
        "mainline_sector_daily": (("amount", "net_inflow_1d"), ("trade_date", "sector_name")),
        "leader_height_daily": (("height", "seal_amount"), ("trade_date", "leader_name")),
        "global_index_daily": (("return_pct",), ("trade_date", "session_date", "index_code")),
    }
    metrics, dimensions = fields[dataset]
    return fq.FinanceQuerySpec(dataset=dataset, metrics=metrics, dimensions=dimensions,
        time_range=fq.TimeRange(date(2026, 7, 22), date(2026, 7, 22)))


def query(root: Path, query_spec: fq.FinanceQuerySpec):
    return fq.FinanceQuery(root / "db/market_feature_store.duckdb").run(
        query_spec, information_cutoff=InformationCutoff(date(2026, 7, 22), "requested"),
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_heat_evidence_names_both_denominators_without_changing_values(market_root):
    result = query(market_root, spec("theme_limit_heat_daily"))
    first = next(item.detail for item in result.evidence if "板块名称=甲方向" in item.detail)
    row = next(row for row in result.rows if row["sector_name"] == "甲方向")
    assert "板块内涨停占比%=5" in first
    assert "占全市场涨停家数比例%=20" in first
    assert "板块成分股家数=120" in first
    assert row["limit_up_ratio"] == 5
    assert row["market_share"] == 20
    assert not result.quality_gaps
    assert "limit_up_ratio=limit_up_count/total_count" in result.observation
    assert "market_share=limit_up_count/market_limit_up_count" in result.observation
    assert "不能相加" in result.observation
    assert "stock_code" in result.observation
    assert "资金迁移" in result.observation


def test_ladder_evidence_distinguishes_survivors_from_cohort_success(market_root):
    result = query(market_root, spec("limit_advance_daily"))
    assert len(result.evidence) == 4
    middle = next(item.detail for item in result.evidence if "股票名称=乙股" in item.detail)
    assert "同板位晋级率（非个股概率）=1/4=25%" in middle
    assert "N-1→N" in result.observation
    assert "同日同板位" in result.observation
    assert "无板位空档不等于全部晋级" in result.observation
    assert "失败" in result.observation
    assert "不能相加" in result.observation
    assert not result.quality_gaps


def test_notes_are_schema_semantics_not_minted_evidence(market_root):
    query_spec = spec("theme_limit_heat_daily")
    result = query(market_root, query_spec)
    assert len(result.rows) == len(result.evidence) == 2
    assert all("资金迁移" not in item.detail for item in result.evidence)
    empty = query(market_root, replace(query_spec, filters=(fq.QueryFilter("sector_name", "eq", "未命中"),)))
    assert not empty.evidence
    assert "未命中" in empty.observation
    ordinary = query(market_root, spec("mainline_theme_daily"))
    assert ordinary.observation == ordinary.evidence[0].detail
    assert "无板位空档" not in ordinary.observation


@pytest.mark.parametrize("dataset", [
    "theme_limit_heat_daily", "limit_advance_daily", "market_daily",
    "mainline_sector_daily", "leader_height_daily", "global_index_daily",
])
def test_catalog_and_executed_basis_share_the_measurement_note(market_root, dataset):
    query_spec = spec(dataset)
    result = query(market_root, query_spec)
    basis = episode_tools._finance_query_basis(query_spec, result)
    note = basis["interpretation_note"]
    assert note in fq.FINANCE_QUERY_PARAMETERS["properties"]["dataset"]["description"]
    assert note in result.observation
    assert basis["candidate_pool_size"] is None
    assert "SELECT" not in note
    assert "/Users/" not in note


@pytest.mark.parametrize("lean", ["off", "on"])
@pytest.mark.parametrize("dataset", [
    "theme_limit_heat_daily", "limit_advance_daily", "market_daily",
    "mainline_sector_daily", "leader_height_daily", "global_index_daily",
])
def test_measurement_note_reaches_actual_model_view_after_pruning(market_root, monkeypatch, lean, dataset):
    monkeypatch.setenv("ASK_EPISODE_LEAN_OBSERVATION", lean)
    frame = TaskFrame(raw_question="2026-07-22 核查涨停分布与晋级情况", user_goal="核查盘面",
        question_type="dated_market_review", subject="A股市场", subject_kind="market_pattern",
        market_scope="A股", timeframe="2026-07-22", required_outputs=("direct_assessment",),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="structured_market_data", confidence=1.0)
    context = build_episode_context(frame, task_id=f"measurement-note-{market_root.name}", capabilities=("finance_query",),
        timeout=10, synthesis_reserve=0, today="2026-07-22", latest_data_date="2026-07-22")
    registry = episode_tools.build_episode_registry(frame, context, finance_root=market_root,
        knowledge_wiki=market_root / "wiki", l3_runner=None)
    query_spec = spec(dataset)
    observation = registry.execute("finance_query", {
        "dataset": dataset, "metrics": list(query_spec.metrics), "dimensions": list(query_spec.dimensions),
        "filters": [], "time_range": {"start": "2026-07-22", "end": "2026-07-22"},
        "group_by": [], "order_by": [], "limit": 50,
    }, context=context, step_id="measurement:1")
    assert observation.trace.status == "success"
    harness = FinanceResearchHarness()
    first = harness.project_tool_result(observation, evidence_so_far=observation.evidence,
        seen_prose=frozenset())
    # Make the prose too long; both compaction and repeat pruning must preserve
    # the executed contract rather than relying on an appended warning.
    long_observation = replace(observation, observation=observation.observation + "长正文" * 2000)
    clipped = harness.project_tool_result(long_observation, evidence_so_far=observation.evidence,
        seen_prose=frozenset())
    repeated = harness.project_tool_result(observation, evidence_so_far=observation.evidence,
        seen_prose=first.seen_prose)
    for projection in (first, clipped, repeated):
        model_view = json.loads(projection.model_content)
        note = model_view["query_basis"]["interpretation_note"]
        assert note == observation.query_basis["interpretation_note"]
        assert note == projection.audit_payload["query_basis"]["interpretation_note"]
        assert model_view["query_basis"]["returned_row_count"] == len(observation.evidence)
        assert len(model_view["evidence"]) == len(observation.evidence)
        assert model_view["ok"] is True
    assert json.loads(clipped.model_content)["context_budget"]["truncated"]
    assert json.loads(repeated.model_content)["noise_prune"]["collapsed_prose"]


def test_grouped_heat_discloses_aggregation_not_a_recomputed_union_ratio(market_root):
    grouped = replace(spec("theme_limit_heat_daily"),
        dimensions=("trade_date",), group_by=("trade_date",))
    result = query(market_root, grouped)
    # SQL still does the requested registered aggregation. It must not be
    # mistaken for 12 distinct stocks or 12/120 recomputed as a group ratio.
    assert result.rows[0]["limit_up_count"] == 12
    assert result.rows[0]["limit_up_ratio"] == 7.5
    note = episode_tools._finance_query_basis(grouped, result)["interpretation_note"]
    assert "limit_up_count=sum" in note
    assert "limit_up_ratio=avg" in note
    assert "比例均值不是合并群体的比例" in note
    assert "求和不自动去重" in note
    assert note in result.observation


def test_grouped_ladder_does_not_turn_maximum_into_each_stock_height(market_root):
    grouped = replace(spec("limit_advance_daily"),
        dimensions=("trade_date",), group_by=("trade_date",))
    result = query(market_root, grouped)
    assert result.rows[0]["boards"] == 4
    note = episode_tools._finance_query_basis(grouped, result)["interpretation_note"]
    assert "boards=max" in note
    assert "最大板位不是该组每只股票的板位" in note
    assert "当日成功连板" in note


def test_selected_ratio_keeps_denominator_meaning_but_does_not_invent_denominator(market_root):
    selected = replace(spec("theme_limit_heat_daily"), metrics=("market_share",))
    result = query(market_root, selected)
    assert set(result.rows[0]) == {"trade_date", "sector_name", "market_share"}
    assert "占全市场涨停家数比例%=20" in result.evidence[0].detail
    assert "全市场涨停家数=30" not in result.evidence[0].detail
    assert "market_limit_up_count" in result.observation
    assert "原始行口径" in result.observation


def test_missing_promotion_is_unknown_not_success_or_a_synthetic_failure(market_root):
    with duckdb.connect(str(market_root / "db/market_feature_store.duckdb")) as con:
        con.execute("UPDATE fact_limit_advance_daily SET promotion_rate = NULL")
    result = query(market_root, spec("limit_advance_daily"))
    assert len(result.evidence) == 4
    assert "同板位晋级率（非个股概率）=未知" in result.evidence[0].detail
    assert "缺失晋级率不表示零或全部成功" in result.observation
    assert "0%" not in result.observation and "100%" not in result.observation


def test_empty_query_keeps_interpretation_separate_from_no_rows(market_root):
    empty = replace(spec("limit_advance_daily"), filters=(fq.QueryFilter("boards", "gte", 99),))
    result = query(market_root, empty)
    basis = episode_tools._finance_query_basis(empty, result)
    assert not result.evidence and not result.rows
    assert "不证明事件未发生" in result.observation
    assert basis["returned_row_count"] == 0
    assert basis["candidate_pool_size"] is None
    assert "缺失晋级率" in basis["interpretation_note"]


def test_market_totals_describe_activity_not_fund_origin_or_completed_liquidation(market_root):
    result = query(market_root, spec("market_daily"))
    assert "成交额不是成交股数" in result.observation
    assert "不能单独证明增量资金入场" in result.observation
    assert "不能据此确认风险已经出清" in result.observation
    assert "指数贡献" in result.observation
    assert result.evidence[0].detail == "交易日=2026-07-22；涨停家数=30"
    assert not result.quality_gaps


@pytest.mark.parametrize("dataset,metric,label,raw", [
    ("mainline_sector_daily", "amount", "成交额（源值，单位未核验）", 7022875.4),
    ("mainline_sector_daily", "net_inflow_1d", "1日净流入（源值，单位未核验）", 4473476293),
    ("leader_height_daily", "seal_amount", "封单额（源值，单位未核验）", 23686.2996),
], ids=["mainline-amount", "mainline-flow", "leader-seal"])
def test_unverified_money_units_are_not_invented_from_magnitude(market_root, dataset, metric, label, raw):
    result = query(market_root, spec(dataset))
    assert result.rows[0][metric] == raw
    assert f"{label}=" in result.evidence[0].detail
    assert "单位未核验" in episode_tools._finance_query_basis(spec(dataset), result)["interpretation_note"]
    assert "成交额亿=" not in result.evidence[0].detail
    assert "万元=" not in result.evidence[0].detail
    assert len(result.evidence) == 1


def test_mainline_grouping_does_not_claim_unique_fund_flow(market_root):
    grouped = replace(spec("mainline_sector_daily"), dimensions=("trade_date",), group_by=("trade_date",))
    result = query(market_root, grouped)
    note = episode_tools._finance_query_basis(grouped, result)["interpretation_note"]
    assert "同一板块可在多个题材下重复" in note
    assert "成分股也可能重叠" in note
    assert "净流入不能直接相加" in note
    assert "amount=sum" in note
    assert "net_inflow_1d=sum" in note
    assert result.rows[0]["amount"] == 7022875.4


def test_foreign_calendar_label_does_not_prove_publication_before_cutoff(market_root):
    result = query(market_root, spec("global_index_daily"))
    assert "外盘会话日=2026-07-22" in result.evidence[0].detail
    note = episode_tools._finance_query_basis(spec("global_index_daily"), result)["interpretation_note"]
    assert "可知时点" in note
    assert "交易时区" in note
    assert "不能仅凭日期标签" in note


def test_unknown_dataset_has_no_measurement_claim():
    assert fq.interpretation_note(replace(spec("market_daily"), dataset="not_registered")) == ""


def test_promotion_sync_repeats_level_statistic_only_on_successful_stocks(tmp_path, monkeypatch):
    from market_feature_store.sync import sync_fupanhui_limit_advance_daily as sync

    class Connection:
        def __init__(self):
            self.daily = []

        def execute(self, *_args):
            return self

        def executemany(self, sql, rows):
            if "INSERT INTO fact_limit_advance_daily" in sql:
                self.daily.extend(rows)

        def fetchone(self):
            return (2, 1, 2, date(2026, 7, 22), date(2026, 7, 22))

        def close(self):
            pass

    con = Connection()
    monkeypatch.setattr(sync, "connect", lambda: con)
    monkeypatch.setattr(sync, "init_db", lambda: None)
    monkeypatch.setattr(sync.fs, "api_get", lambda *_a, **_kw: {
        "trade_date": "2026-07-22", "trade_dates": ["2026-07-22", "2026-07-21"],
        "levels": [{"level": 2, "promoted_count": 2, "total_count": 6, "promotion_rate": 33.333,
            "stocks": [
                {"ts_code": "000001.SZ", "name": "甲股", "status_type": "U"},
                {"ts_code": "000002.SZ", "name": "乙股", "status_type": "U"},
                {"ts_code": "000003.SZ", "name": "失败股", "status_type": "D"},
            ]}],
    })
    stats = sync.sync_fupanhui_limit_advance("2026-07-22")
    assert stats["skipped_status"] == 1
    assert len(con.daily) == 2
    assert {row[3] for row in con.daily} == {2}
    assert {row[7] for row in con.daily} == {"2/6=33%"}


def test_unrelated_query_does_not_advertise_market_interpretation(market_root):
    query_spec = spec("mainline_theme_daily")
    basis = episode_tools._finance_query_basis(query_spec, query(market_root, query_spec))
    assert "interpretation_note" not in basis
