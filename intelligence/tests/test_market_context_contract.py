"""D4 contracts through a real DuckDB, registry and model-facing projection."""

from __future__ import annotations

from dataclasses import asdict, FrozenInstanceError, replace
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
from uuid import uuid4

import duckdb
import pytest

from intelligence.services import agent_research, ask, ask_blocks, episode_tools, llm_refine, reading_baseline
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.task_frame import TaskFrame
from market_feature_store import signals as market_signals


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("D4 contract tests must not use sockets or models")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for name in ("synthesize", "synthesize_messages", "synthesize_messages_stream"):
        monkeypatch.setattr(llm_refine, name, forbidden)
    monkeypatch.setattr(llm_refine, "complete", forbidden)
    monkeypatch.setenv("FINANCE_READING_BASELINE", "1")


def _database(
    tmp_path: Path, rows: list[tuple[str, str, str, int | None]], *, trade_date: str = "2026-10-01",
) -> Path:
    db_path = tmp_path / "fixture.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute((Path(__file__).parents[2] / "market_feature_store/schema.sql").read_text())
    con.execute("insert into fact_market_daily (trade_date) values (?)", [trade_date])
    con.executemany(
        "insert into fact_mainline_sector_daily "
        "(trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no, "
        "today_pct, limit_up_count, net_inflow_1d, amount, cycle_status, cycle_level) "
        "values (?, ?, ?, ?, ?, ?, 2, 0, 0, 5010000, '顺势', '小级别')",
        [(trade_date, theme, theme, code, name, order) for theme, code, name, order in rows],
    )
    con.executemany(
        "insert into fact_sector_daily_generation "
        "(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, "
        "sw_l1, pct_chg, diff_ratio, amount) "
        "values (?, 'legacy', ?, ?, '电子', 2, 42, 501)",
        [(trade_date, code, name) for _theme, code, name, _order in rows],
    )
    con.close()
    return db_path


def _registry(
    db_path: Path, *, query: str = "当前市场主线是什么", subject=None,
    latest_data_date: str = "2026-10-01",
):
    frame = TaskFrame(
        raw_question=query, user_goal="核对主线结构", question_type="market_forecast",
        subject=subject, subject_kind="market_pattern", market_scope="A股",
        timeframe="最近交易日", required_outputs=("current_baseline",),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="current_market_scenarios", confidence=1.0,
    )
    context = build_episode_context(
        frame, task_id=f"d4-contract:{uuid4()}", capabilities=("mainline_context",),
        timeout=30.0, latest_data_date=latest_data_date, today=latest_data_date,
    )
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=db_path.parent, knowledge_wiki=db_path.parent / "wiki",
        l3_runner=None, evidence_search_judge=None,
        fixture_policy=episode_tools.SealedFixturePolicy(market_db_path=db_path),
    )
    return registry, context


def _consume(db_path: Path, *, query: str = "当前市场主线是什么", subject=None):
    registry, context = _registry(db_path, query=query, subject=subject)
    observation = registry.execute("mainline_context", {}, context=context, step_id="d4:1")
    projection = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=observation.evidence, seen_prose=set(),
    )
    return observation, projection, json.loads(projection.model_content)


def test_real_registry_does_not_lose_last_theme_after_global_thirty(tmp_path):
    rows = [("AAA", f"A{i:02}", f"AAA板块{i:02}", i) for i in range(31)]
    rows.append(("ZZZ", "Z00", "ZZZ板块", 1))
    observation, _projection, facing = _consume(_database(tmp_path, rows))
    assert any("ZZZ板块" in item.detail for item in observation.evidence)
    assert any("ZZZ板块" in item["detail"] for item in facing["evidence"])
    basis = facing["query_basis"]
    assert basis["theme_names"] == ["AAA", "ZZZ"]
    assert basis["total_rows"] == 32
    assert basis["total_groups"] == 2
    assert basis["preview_limit_per_theme"] == 8
    assert [group["preview_rows"] for group in basis["groups"]] == [8, 1]
    assert [group["omitted_rows"] for group in basis["groups"]] == [23, 0]
    assert len(observation.evidence) == 9


@pytest.mark.parametrize("price", ["每股价格2.5元", "每股价格2.5"])
def test_price_role_keeps_today_through_factory_registry_and_shared_model(tmp_path, price):
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.temporal_contract import compile_temporal_contract, message_digest

    db_path = _database(tmp_path, [("CURRENT_MARKET_1007", "NOW", "当前板块", 1)], trade_date="2026-10-07")
    _write(db_path, "insert into fact_market_daily (trade_date) values ('2026-02-05')")
    _write(db_path, "insert into fact_mainline_sector_daily "
           "(trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
           "values ('2026-02-05','OLD','OLD_PRICE_DATE_SENTINEL_205','OLD','旧板块')")
    query = f"今天A股的主线强弱怎么看？\r\n有一只股{price}，请据此解释盘面。资料截至今天。"
    temporal = compile_temporal_contract(query, today=date(2026, 10, 7), message_id="complete-original-user")
    assert temporal.market_target is None
    assert temporal.cutoff_source.excerpt == query
    assert temporal.cutoff_source.message_sha256 == message_digest(query.replace("\r\n", "\n"))
    frame = understand_query(query, today=date(2026, 10, 7), temporal_contract=temporal).task_frame
    assert frame.timeframe == "最新可用交易日"
    context = build_episode_context(frame, task_id=f"price-{price}", capabilities=("mainline_context",),
                                    today="2026-10-07", latest_data_date="2026-10-07")
    registry = episode_tools.build_episode_registry(frame, context, finance_root=tmp_path,
        knowledge_wiki=tmp_path / "wiki", l3_runner=None,
        fixture_policy=episode_tools.SealedFixturePolicy(market_db_path=db_path))
    observation = registry.execute("mainline_context", {}, context=context, step_id="price-date")
    public = FinanceResearchHarness().project_tool_result(observation, evidence_so_far=observation.evidence,
                                                         seen_prose=set()).model_content
    assert {item.source_date for item in observation.evidence} == {"2026-10-07"}
    assert observation.query_basis["snapshot_date"] == "2026-10-07"
    assert "CURRENT_MARKET_1007" in public and "OLD_PRICE_DATE_SENTINEL_205" not in public
    assert context.temporal_contract is temporal


def test_real_registry_all_six_themes_survive_guidance_card_budget(tmp_path):
    rows = [(f"主题{i}", f"S{i}", f"板块{i}", i) for i in range(6)]
    observation, _projection, facing = _consume(_database(tmp_path, rows))
    for _theme, _code, sector, _order in rows:
        assert any(sector in item.detail for item in observation.evidence)
        assert any(sector in item["detail"] for item in facing["evidence"])
    assert len(observation.evidence) == 6
    assert facing["query_basis"]["theme_names"] == [row[0] for row in rows]


def test_real_registry_reading_rules_are_never_fact_cards(tmp_path):
    observation, projection, facing = _consume(
        _database(tmp_path, [("主题", "S0", "板块", 1)])
    )
    assert not any("判读[" in item.detail for item in observation.evidence)
    assert not any("判读[" in item["detail"] for item in facing["evidence"])
    assert len(projection.audit_payload["evidence_ids"]) == 1
    rule = reading_baseline.block_rules("D4_mainline")[0]
    for value in (rule.id, rule.title, rule.rule, rule.source):
        assert value in facing["observation"]
    assert observation.evidence[0].source_date == "2026-10-01"
    assert observation.evidence[0].evidence_tier == "L4_structured"
    assert json.loads(observation.evidence[0].independent_key) == ["2026-10-01", "主题", "S0"]
    assert "满足严格双红" not in observation.evidence[0].detail
    assert "满足严格双红" not in facing["observation"]
    assert facing["query_basis"]["price_volume_signals"][0]["strict_double_red"] is True


def _write(db_path: Path, sql: str, params=None):
    con = duckdb.connect(str(db_path))
    try:
        con.execute(sql, params or [])
    finally:
        con.close()


def test_snapshot_single_theme_and_stable_ties_preserve_all_source_fields(tmp_path):
    rows = [("T", "Z", "同名板块", 1), ("T", "A", "同名板块", 1),
            ("T", "B", "末尾板块", None), ("U", "C", "其他板块", 1)]
    db_path = _database(tmp_path, rows)
    _write(db_path,
           "update fact_mainline_sector_daily set startup_date_small='2026-09-30', "
           "high_status_label='历史新高', near_breakout_label='接近突破' where theme_code='T'")
    snapshot = ask_blocks.mainline_context_snapshot("T题材", "T", db_path, as_of="2026-10-01")
    assert snapshot.status == "available"
    assert snapshot.target_theme == "T"
    assert snapshot.total_rows == 3
    assert [fact.sector_ts_code for fact in snapshot.facts] == ["A", "Z", "B"]
    first = snapshot.facts[0]
    assert first.theme_code == "T" and first.sort_no == 1
    assert first.today_pct == 2 and first.limit_up_count == 0
    assert first.net_inflow_1d == 0 and first.amount == 5010000
    assert first.cycle_status == "顺势" and first.cycle_level == "小级别"
    assert first.startup_date_small == "2026-09-30"
    assert first.high_status_label == "历史新高" and first.near_breakout_label == "接近突破"
    assert first.sector_pct == 2 and first.diff_ratio == 42 and first.sector_amount == 501
    assert first.sw_l1 == "电子"
    assert first.pct_source == "fact_sector_daily.pct_chg"
    assert first.amount_source == "fact_sector_daily.amount"
    assert isinstance(snapshot.facts, tuple) and isinstance(snapshot.groups, tuple)
    assert isinstance(snapshot.groups[0].non_null_counts, tuple)
    with pytest.raises(FrozenInstanceError):
        first.amount = 1
    with pytest.raises(ValueError, match="same source"):
        replace(snapshot, signals=(replace(snapshot.signals[0], theme_code="wrong"), *snapshot.signals[1:]))
    _obs, _projection, facing = _consume(db_path, query="T题材", subject="T")
    assert facing["query_basis"]["scope"] == "current_table_single_theme"
    assert facing["query_basis"]["theme_names"] == ["T"]


def test_canonical_published_view_replaces_legacy_and_fallback_marks_sources(tmp_path):
    db_path = _database(tmp_path, [("T", "S1", "已发布", 1), ("T", "S2", "回退", 2)])
    _write(db_path,
           "insert into ops_sector_universe_snapshot_daily "
           "values ('2026-10-01','published','fixture',2,0,'published',current_timestamp)")
    _write(db_path,
           "insert into fact_sector_daily_generation "
           "(trade_date,sector_universe_snapshot_id,sector_ts_code,sector_name,sw_l1,pct_chg,amount,diff_ratio) "
           "values ('2026-10-01','published','S1','已发布','通信',0,0,-1), "
           "('2026-10-01','published','S2','回退',NULL,NULL,NULL,10), "
           "('2026-10-01','candidate','S1','候选','伪',99,99999,99)")
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    assert snapshot.total_rows == 2
    first, second = snapshot.facts
    assert (first.sector_pct, first.sector_amount, first.diff_ratio, first.sw_l1) == (0, 0, -1, "通信")
    assert (second.sector_pct, second.sector_amount, second.diff_ratio) == (2, 501, 10)
    assert second.pct_source == "fact_mainline_sector_daily.today_pct"
    assert second.amount_source == "fact_mainline_sector_daily.amount/10000"
    assert len(snapshot.signals) == 2
    assert snapshot.signals[0].strict_double_red is False
    assert snapshot.signals[1].strict_double_red is False


def test_full_group_non_null_counts_are_before_preview_and_keep_none_and_zero(tmp_path):
    rows = [("T", f"S{i}", f"板块{i}", i) for i in range(12)]
    db_path = _database(tmp_path, rows)
    _write(db_path,
           "update fact_mainline_sector_daily set today_pct=NULL,limit_up_count=NULL, "
           "net_inflow_1d=NULL,amount=NULL,cycle_status=NULL,cycle_level=NULL where sector_ts_code='S0'")
    _write(db_path,
           "update fact_sector_daily_generation set pct_chg=NULL,diff_ratio=NULL,amount=NULL,sw_l1=NULL "
           "where sector_ts_code='S0'")
    _write(db_path,
           "update fact_mainline_sector_daily set today_pct=0,limit_up_count=0,net_inflow_1d=0,amount=0 "
           "where sector_ts_code='S1'")
    _write(db_path,
           "update fact_sector_daily_generation set pct_chg=0,diff_ratio=0,amount=0 where sector_ts_code='S1'")
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    group = snapshot.groups[0]
    assert (group.total_rows, group.preview_rows, group.omitted_rows) == (12, 8, 4)
    assert dict(group.non_null_counts) == {metric: 11 for metric in ask_blocks._MAINLINE_COVERAGE_METRICS}
    unknown, zero = snapshot.facts[:2]
    assert unknown.today_pct is None and unknown.limit_up_count is None and unknown.amount is None
    assert unknown.sector_pct is None and unknown.sector_amount is None and unknown.diff_ratio is None
    assert zero.today_pct == zero.limit_up_count == zero.net_inflow_1d == zero.amount == 0
    result = episode_tools.mainline_snapshot_tool_result(snapshot)
    assert "涨停家数=未提供" in result.evidence[0].detail
    assert "板块成交额亿元=未提供" in result.evidence[0].detail
    assert "涨停家数=0" in result.evidence[1].detail
    assert "板块成交额亿元=0" in result.evidence[1].detail


def test_full_group_price_volume_counts_include_rows_outside_preview(tmp_path):
    db_path = _database(tmp_path, [("T", f"S{i:02}", f"板块{i:02}", i) for i in range(12)])
    _write(db_path, "update fact_sector_daily_generation set pct_chg=-2,diff_ratio=3 where sector_ts_code='S08'")
    _write(db_path, "update fact_sector_daily_generation set pct_chg=-1,diff_ratio=-2 where sector_ts_code='S09'")
    _write(db_path, "update fact_sector_daily_generation set pct_chg=0,diff_ratio=0 where sector_ts_code='S10'")
    _write(db_path, "update fact_sector_daily_generation set pct_chg=NULL,diff_ratio=NULL,amount=NULL where sector_ts_code='S11'")
    _write(db_path, "update fact_mainline_sector_daily set today_pct=NULL,amount=NULL where sector_ts_code='S11'")
    observation, _projection, facing = _consume(db_path)
    group = facing["query_basis"]["groups"][0]
    assert len(observation.evidence) == 8
    assert group["full_group_counts"] == {
        "distinct_sector_codes": 12,
        "price_up": 8, "price_down": 2, "price_flat": 1, "price_unknown": 1,
        "turnover_up": 9, "turnover_down": 1, "turnover_flat": 1, "turnover_unknown": 1,
        "double_red": 8, "not_double_red": 3, "double_red_unknown": 1,
    }
    assert "全量计数" in facing["observation"]
    assert group["omitted_rows"] == 4


def test_omitted_double_red_cannot_be_reported_as_zero(tmp_path):
    db_path = _database(tmp_path, [("T", f"S{i:02}", f"板块{i:02}", i) for i in range(9)])
    _write(db_path, "update fact_sector_daily_generation set pct_chg=-1 where sector_ts_code<>'S08'")
    observation, _projection, facing = _consume(db_path)
    assert all(not row["strict_double_red"] for row in observation.query_basis["price_volume_signals"])
    counts = facing["query_basis"]["groups"][0]["full_group_counts"]
    assert counts["double_red"] == 1 and counts["price_up"] == 1
    assert counts["price_down"] == 8 and counts["distinct_sector_codes"] == 9


def test_nonfinite_omitted_values_are_unknown_in_full_counts(tmp_path):
    db_path = _database(tmp_path, [("T", f"S{i:02}", f"板块{i:02}", i) for i in range(9)])
    _write(db_path, "update fact_sector_daily_generation set pct_chg=?,diff_ratio=?,amount=? where sector_ts_code='S08'",
           [float('nan'), float('inf'), float('inf')])
    _observation, _projection, facing = _consume(db_path)
    counts = facing["query_basis"]["groups"][0]["full_group_counts"]
    assert counts["price_unknown"] == counts["turnover_unknown"] == counts["double_red_unknown"] == 1
    assert counts["double_red"] == 8


def test_full_counts_follow_canonical_double_red_thresholds(tmp_path, monkeypatch):
    db_path = _database(tmp_path, [("T", "S", "板块", 1)])
    monkeypatch.setattr(market_signals, "DOUBLE_RED_DIFF", 50.0)
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    assert snapshot.signals[0].strict_double_red is False
    assert dict(snapshot.groups[0].full_group_counts)["double_red"] == 0


def test_fact_projection_does_not_round_large_or_precise_source_values(tmp_path):
    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    _write(db_path,
           "update fact_mainline_sector_daily set net_inflow_1d=24046907555, amount=70055125.75, today_pct=5.176587")
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    detail = episode_tools.mainline_snapshot_tool_result(snapshot).evidence[0].detail
    assert "24046907555.0" in detail
    assert "70055125.75" in detail
    assert "5.176587" in detail


def test_preview_exact_ties_use_theme_code_and_sector_code_for_stability(tmp_path):
    db_path = _database(tmp_path, [("T", code, "同名", 1) for code in ("A00", "Z01", "Z00")])
    _write(db_path,
           "update fact_mainline_sector_daily set theme_code=case "
           "when sector_ts_code like 'Z%' then 'A' else 'B' end")
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    assert [(fact.theme_code, fact.sector_ts_code) for fact in snapshot.facts] == [
        ("A", "Z00"), ("A", "Z01"), ("B", "A00"),
    ]


@pytest.mark.parametrize("amount", [None, 0, 500, 501])
@pytest.mark.parametrize("diff", [42, 10, -1])
def test_volume_qualification_uses_canonical_rule_and_never_infers_funding(tmp_path, amount, diff):
    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    _write(db_path, "update fact_mainline_sector_daily set amount=?", [None if amount is None else amount * 10000])
    _write(db_path, "update fact_sector_daily_generation set amount=?, diff_ratio=?", [amount, diff])
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    signal = snapshot.signals[0]
    expected = None if amount is None else market_signals.is_double_red(2, diff, amount)
    assert signal.strict_double_red is expected
    assert ask_blocks._classify_mainline_volume_state(2, diff, amount) == signal.state
    text = ask_blocks.render_mainline_context_snapshot(snapshot)
    for forbidden in ("真正双红", "增量启动", "存量抱团", "唯一资金主线"):
        assert forbidden not in signal.state and forbidden not in text


@pytest.mark.parametrize("missing", ["pct_chg", "diff_ratio", "amount"])
def test_any_missing_volume_input_means_unknown_even_if_other_inputs_pass(tmp_path, missing):
    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    _write(db_path, f"update fact_sector_daily_generation set {missing}=NULL")
    if missing == "pct_chg":
        _write(db_path, "update fact_mainline_sector_daily set today_pct=NULL")
    if missing == "amount":
        _write(db_path, "update fact_mainline_sector_daily set amount=NULL")
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    assert snapshot.signals[0].strict_double_red is None
    assert snapshot.signals[0].inputs_complete is False
    assert snapshot.signals[0].missing_inputs == ({
        "pct_chg": "sector_pct", "diff_ratio": "diff_ratio", "amount": "sector_amount",
    }[missing],)
    assert "不足待确认" in snapshot.signals[0].state


def test_legacy_volume_logic_calls_the_canonical_qualifier(monkeypatch):
    calls = []
    def qualify(*values):
        calls.append(values)
        return False
    monkeypatch.setattr(market_signals, "is_double_red", qualify)
    assert "未确认严格双红" in ask_blocks._classify_mainline_volume_state(2, 42, 501)
    assert calls == [(2, 42, 501)]
    ask_blocks._classify_mainline_volume_state(2, 42, None)
    assert len(calls) == 1


def test_inclusive_history_calendar_boundaries_and_all_historical_themes(tmp_path):
    db_path = _database(tmp_path, [("当前主题", "CURRENT", "板块", 1)])
    _write(db_path,
           "insert into fact_mainline_sector_daily (trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
           "values ('2026-09-09','OUT','窗外','OUT','窗外板块'), "
           "('2026-09-10','IN','边界','IN','边界板块'), "
           "('2026-09-30','IN','边界','IN','边界板块')")
    for i in range(12):
        _write(db_path,
               "insert into fact_mainline_sector_daily (trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
               "values ('2026-09-10',?,?,?,?)", [f"H{i}", f"历史{i:02}", f"H{i}", "历史板块"])
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path, as_of="2026-09-30")
    assert snapshot.snapshot_date == "2026-09-30"
    assert snapshot.market_date is None
    assert snapshot.history_start == "2026-09-10" and snapshot.history_end == "2026-09-30"
    assert len(snapshot.history) == 13
    history = {row.theme_name: row for row in snapshot.history}
    assert "窗外" not in history and "当前主题" not in history
    assert history["边界"].day_count == 2 and history["边界"].sector_rows == 2
    assert history["边界"].first_date == "2026-09-10" and history["边界"].last_date == "2026-09-30"
    assert history["边界"].has_snapshot_day is True
    assert history["历史00"].has_snapshot_day is False
    basis = episode_tools.mainline_snapshot_tool_result(snapshot).query_basis
    assert basis["history_window"] == {
        "start": "2026-09-10", "end": "2026-09-30", "lookback_days": 20,
        "unit": "calendar_days", "inclusive_start": True, "inclusive_end": True,
    }
    assert len(basis["history"]) == 13
    assert "非截止日主线排名" in ask_blocks.render_mainline_context_snapshot(snapshot)


@pytest.mark.parametrize("strict", [False, True])
def test_real_history_window_limits_mainline_aggregates_without_losing_current_coverage(tmp_path, strict):
    from intelligence.services.query_understanding import understand_query

    rows = [("合法主线", f"S{i}", f"板块{i}", i) for i in range(9)]
    db_path = _database(tmp_path, rows, trade_date="2026-09-30")
    _write(db_path, "insert into fact_mainline_sector_daily "
           "(trade_date,theme_code,theme_name,sector_ts_code,sector_name) values "
           "('2026-09-10','OUT','OUT_OF_WINDOW_THEME_43210','OUT1','旧板块'), "
           "('2026-09-29','合法主线','合法主线','EARLY1','合法边界')")
    query = ("只看2026-09-29至2026-09-30窗口内的A股主线，做事后复盘；资料截至区间结束日"
             if strict else "复盘2026年9月30日A股，资料截至2026年10月7日")
    frame = understand_query(query, today=date(2026, 10, 8)).task_frame
    context = build_episode_context(frame, task_id=f"strict-d4-{strict}", capabilities=("mainline_context",),
                                    today="2026-10-08", latest_data_date="2026-10-07")
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki", l3_runner=None,
        fixture_policy=episode_tools.SealedFixturePolicy(market_db_path=db_path),
    )
    observation = registry.execute("mainline_context", {}, context=context, step_id="strict-d4")
    model = FinanceResearchHarness().project_tool_result(observation, evidence_so_far=observation.evidence,
                                                        seen_prose=set()).model_content
    basis = json.loads(model)["query_basis"]
    assert basis["snapshot_date"] == "2026-09-30"
    assert basis["total_rows"] == 9 and basis["total_groups"] == 1
    assert (basis["groups"][0]["preview_rows"], basis["groups"][0]["omitted_rows"]) == (8, 1)
    assert len(observation.evidence) == 8
    histories = {row["theme_name"]: row for row in basis["history"]}
    assert histories["合法主线"]["day_count"] == 2
    assert histories["合法主线"]["first_date"] == "2026-09-29"
    assert histories["合法主线"]["sector_rows"] == 10
    assert ("OUT_OF_WINDOW_THEME_43210" in model) is (not strict)
    assert basis["history_window"] == {
        "start": "2026-09-29" if strict else "2026-09-10", "end": "2026-09-30",
        "lookback_days": 1 if strict else 20, "unit": "calendar_days", "inclusive_start": True, "inclusive_end": True,
    }


def test_future_upper_bound_and_market_review_staleness_do_not_deliver_old_facts(tmp_path):
    db_path = _database(tmp_path, [("未来主题", "FUTURE", "未来板块", 1)])
    _write(db_path,
           "insert into fact_market_daily (trade_date) values ('2026-09-30')")
    _write(db_path,
           "insert into fact_mainline_sector_daily (trade_date,theme_code,theme_name,sector_ts_code,sector_name) "
           "values ('2026-09-29','OLD','旧主题','OLD','旧板块')")
    direct = ask_blocks.mainline_context_snapshot("市场主线", None, db_path, as_of="2026-09-30")
    assert direct.status == "available" and direct.snapshot_date == "2026-09-29"
    assert direct.facts[0].sector_name == "旧板块"
    review = ask_blocks.market_review_mainline_context_snapshot("市场主线", None, db_path, as_of="2026-09-30")
    assert review.status == "stale" and review.market_date == "2026-09-30"
    assert review.snapshot_date == "2026-09-29" and not review.facts and not review.signals
    result = episode_tools.mainline_snapshot_tool_result(review)
    assert not result.evidence
    assert "旧主题" not in result.observation and "未来主题" not in result.observation
    assert "仅截至 2026-09-29" in result.observation
    assert result.query_basis["status"] == "stale"


@pytest.mark.parametrize("case, expected", [
    ("missing", "unavailable"), ("missing_table", "unavailable"),
    ("broken_query", "unavailable"), ("bad_file", "unavailable"),
    ("no_rows", "empty"), ("future_only", "empty"),
])
def test_unavailable_empty_and_future_only_are_explicit_non_evidence(tmp_path, case, expected):
    db_path = tmp_path / "fixture.duckdb"
    if case in {"no_rows", "future_only", "broken_query"}:
        db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
        if case == "no_rows":
            _write(db_path, "delete from fact_mainline_sector_daily")
        if case == "broken_query":
            _write(db_path, "drop view fact_sector_daily")
    elif case == "missing_table":
        _write(db_path, "create table dummy(x integer)")
    elif case == "bad_file":
        db_path.write_text("invalid database")
    snapshot = ask_blocks.mainline_context_snapshot(
        "市场主线", None, db_path, as_of="2026-09-30" if case == "future_only" else None,
    )
    assert snapshot.status == expected
    assert not snapshot.facts and not snapshot.signals
    result = episode_tools.mainline_snapshot_tool_result(snapshot)
    assert not result.evidence and result.trace.result_count == 0
    assert result.trace.status == ("request_error" if expected == "unavailable" else "empty")
    assert result.query_basis["status"] == expected
    assert snapshot.gap_messages
    assert str(db_path) not in json.dumps(result.query_basis, ensure_ascii=False)


def test_reading_methods_on_off_leave_actual_facts_and_full_coverage_identical(tmp_path, monkeypatch):
    db_path = _database(tmp_path, [(f"主题{i}", f"S{i}", f"板块{i}", i) for i in range(6)])
    on, _on_projection, on_facing = _consume(db_path)
    monkeypatch.setenv("FINANCE_READING_BASELINE", "off")
    off, _off_projection, off_facing = _consume(db_path)
    assert on.evidence == off.evidence
    assert on.query_basis == off.query_basis
    assert on_facing["evidence"] == off_facing["evidence"]
    assert on_facing["query_basis"] == off_facing["query_basis"]
    assert "判读[" in on_facing["observation"] and "判读[" not in off_facing["observation"]


def test_real_shared_projection_preserves_all_coverage_under_original_prose_limits(tmp_path):
    rows = [(f"主题{i}", f"S{i}", f"板块{i}" + "x" * 1200, i) for i in range(6)]
    observation, _projection, _facing = _consume(_database(tmp_path, rows))
    long = replace(observation, observation=observation.observation + "x" * 5000)
    projection = FinanceResearchHarness().project_tool_result(
        long, evidence_so_far=long.evidence, seen_prose=set(),
    )
    facing = json.loads(projection.model_content)
    assert len(facing["observation"]) == 4000
    assert all(len(item["detail"]) == 800 for item in facing["evidence"])
    assert projection.audit_payload["query_basis"] == facing["query_basis"] == observation.query_basis
    assert facing["query_basis"]["theme_names"] == [row[0] for row in rows]
    assert facing["context_budget"]["omitted_chars"] > 0
    assert len(facing["evidence_ids"]) == 6


def test_snapshot_readonly_transaction_does_not_change_database_and_signals_match(tmp_path, monkeypatch):
    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    calls = []
    connect = ask_blocks.retrieval_cache.try_connect_readonly
    statements = []
    class TrackedConnection:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, sql, *args):
            statements.append(sql)
            return self.connection.execute(sql, *args)
        def close(self):
            return self.connection.close()
    def tracked(path):
        result = connect(path)
        calls.append(result)
        return replace(result, connection=TrackedConnection(result.connection))
    monkeypatch.setattr(ask_blocks.retrieval_cache, "try_connect_readonly", tracked)
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    assert snapshot.status == "available" and len(calls) == 1
    assert statements[0] == "BEGIN TRANSACTION" and statements[-1] == "COMMIT"
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == digest
    fact, signal = snapshot.facts[0], snapshot.signals[0]
    assert (signal.trade_date, signal.theme_code, signal.sector_ts_code) == (
        fact.trade_date, fact.theme_code, fact.sector_ts_code,
    )
    assert signal.sector_pct == fact.sector_pct
    assert signal.diff_ratio == fact.diff_ratio
    assert signal.sector_amount == fact.sector_amount
    assert all(not isinstance(value, dict) for value in snapshot.__dict__.values())


@pytest.mark.parametrize("failure", ["query", "commit"])
def test_query_or_commit_failure_rolls_back_closes_and_delivers_no_facts(tmp_path, monkeypatch, failure):
    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    if failure == "query":
        _write(db_path, "drop view fact_sector_daily")
    connect = ask_blocks.retrieval_cache.try_connect_readonly
    statements = []
    closed = []
    class FailingConnection:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, sql, *args):
            statements.append(sql)
            if failure == "commit" and sql == "COMMIT":
                raise RuntimeError("injected commit failure")
            return self.connection.execute(sql, *args)
        def close(self):
            closed.append(True)
            return self.connection.close()
    def tracked(path):
        result = connect(path)
        return replace(result, connection=FailingConnection(result.connection))
    monkeypatch.setattr(ask_blocks.retrieval_cache, "try_connect_readonly", tracked)
    snapshot = ask_blocks.mainline_context_snapshot("市场主线", None, db_path)
    assert snapshot.status == "unavailable"
    assert not snapshot.facts and not snapshot.signals
    assert statements[0] == "BEGIN TRANSACTION" and statements[-1] == "ROLLBACK"
    assert closed == [True]
    assert not episode_tools.mainline_snapshot_tool_result(snapshot).evidence


def test_non_d4_block_conversion_behavior_is_unchanged():
    evidence, observation = agent_research.block_lines_to_evidence(
        "market_data", "## 总览\n- 当日成交额：0\n- 使用要求：逐项核对", "fixture",
    )
    assert [item.detail for item in evidence] == ["当日成交额：0", "使用要求：逐项核对"]
    assert observation.startswith("使用要求：逐项核对")


def test_mainline_runner_keeps_cancellation_deadline_and_freshness_before_reads(tmp_path, monkeypatch):
    from intelligence.services.research_contract import ResearchDeadline

    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    registry, context = _registry(db_path)
    stale_registry, stale_context = _registry(db_path, latest_data_date="2026-10-02")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("D4 producer must not run after cancellation/deadline/stale floor")
    monkeypatch.setattr(ask_blocks, "market_review_mainline_context_snapshot", forbidden)
    runner = registry.resolve("mainline_context").runner
    with pytest.raises(RuntimeError, match="cancelled"):
        runner("", agent_research.AgentToolContext(context.deadline, is_cancelled=lambda: True))
    with pytest.raises(TimeoutError, match="deadline"):
        runner("", agent_research.AgentToolContext(ResearchDeadline.from_timeout(0)))
    stale = stale_registry.execute("mainline_context", {}, context=stale_context, step_id="stale:1")
    assert not stale.evidence and stale.trace.status == "stale"


def test_mainline_runner_checks_cancellation_after_the_structured_read(tmp_path, monkeypatch):
    db_path = _database(tmp_path, [("T", "S1", "板块", 1)])
    registry, context = _registry(db_path)
    produce = ask_blocks.market_review_mainline_context_snapshot
    cancelled = False
    def read_then_cancel(*args, **kwargs):
        nonlocal cancelled
        result = produce(*args, **kwargs)
        cancelled = True
        return result
    monkeypatch.setattr(ask_blocks, "market_review_mainline_context_snapshot", read_then_cancel)
    with pytest.raises(RuntimeError, match="cancelled"):
        registry.resolve("mainline_context").runner(
            "", agent_research.AgentToolContext(context.deadline, is_cancelled=lambda: cancelled),
        )


def test_generic_adapter_uses_the_same_snapshot_projection_and_isolates_double_red(tmp_path, monkeypatch):
    from intelligence.runtime import conversation_orchestrator
    from intelligence.services.research_contract import InformationCutoff, ResearchDeadline

    db_path = _database(tmp_path, [(f"主题{i}", f"S{i}", f"板块{i}", i) for i in range(6)])
    contract = conversation_orchestrator._build_generic_research_contract(
        "什么是双红，现在哪些板块双红", task_id="d4-generic-contract",
        turn_intent=conversation_orchestrator.TurnIntent(
            primary_subject="双红", secondary_topics=(), question_type="concept_definition",
            answer_owner=None, comparison_entities=(), inherited_from_turn=None,
        ),
    )
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(llm_refine, "detect_provider", lambda _model=None: None)
    factory = ask.research_tool_registry.default_registry
    captured = []
    class Captured(Exception):
        pass
    def capture(tools):
        registry = factory(tools)
        result = registry.resolve("mainline_context").runner(
            "", agent_research.AgentToolContext(
                ResearchDeadline.from_timeout(30),
                information_cutoff=InformationCutoff(as_of_date=date(2026, 10, 1), source="requested"),
            ),
        )
        captured.append(result)
        raise Captured
    monkeypatch.setattr(ask.research_tool_registry, "default_registry", capture)
    with pytest.raises(Captured):
        ask._answer_generic_owner(ask.AskOptions(
            query=contract.question, kb_wiki=tmp_path / "wiki", market_db_path=db_path,
            research_task_contract=contract, use_llm=False, compose=False,
        ))
    result = captured[0]
    same = episode_tools.mainline_snapshot_tool_result(
        ask_blocks.market_review_mainline_context_snapshot(contract.question, "双红", db_path, as_of="2026-10-01"),
        capability="agent_loop",
    )
    assert result.query_basis == same.query_basis
    assert result.evidence[:6] == same.evidence
    assert len(result.evidence) == result.trace.result_count == 7
    assert result.evidence[-1].detail.startswith("当前双红板块：")
    assert result.evidence[-1].source_date == "2026-10-01"
    for rule in reading_baseline.block_rules("D4_mainline"):
        assert rule.source in result.observation
        assert all(rule.rule not in item.detail for item in result.evidence)
    assert "双红定义" in result.observation
    assert all("双红定义" not in item.detail for item in result.evidence)


def test_mixed_double_red_fallback_accepts_definition_without_creating_a_fact_card():
    evidence = [agent_research.AgentEvidence(
        tool="mainline_context", title="名单", detail="当前双红板块：板块（涨幅2%，成交额501亿元）。",
        source="fact_sector_daily", source_date="2026-10-01", evidence_tier="L4_structured",
    )]
    before = asdict(evidence[0])
    text = ask._current_market_fact_fallback_assessment(evidence, definition=market_signals.DOUBLE_RED_DESCRIPTION)
    assert market_signals.DOUBLE_RED_DESCRIPTION.rstrip("。") in text
    assert "双红数据截至：2026-10-01" in text
    assert len(evidence) == 1 and asdict(evidence[0]) == before
