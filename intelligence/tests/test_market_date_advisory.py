"""日期差异只说明时点：保留真实输入，不改值、不造退出或补齐证明。"""

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services import ask_blocks, episode_tools
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import SealedFixturePolicy, build_episode_registry
from intelligence.tests.test_episode_tools import _market_forecast_frame


def _registry(tmp_path: Path, *, reference_date: str = "2026-07-27"):
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id=f"date-advisory-{tmp_path.name}",
        capabilities=("market_data", "mainline_context"),
        timeout=20.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date=reference_date,
    )
    registry = build_episode_registry(
        frame, context,
        finance_root=tmp_path,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        fixture_policy=SealedFixturePolicy(),
    )
    return registry, context


def _database(tmp_path: Path):
    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    return duckdb.connect(str(path))


@pytest.mark.parametrize("with_market", [False, True])
@pytest.mark.parametrize("reference_date", ["2026-07-21", "2026-07-27"])
def test_mainline_delivers_each_sources_actual_date(tmp_path: Path, with_market: bool, reference_date: str):
    with _database(tmp_path) as con:
        if with_market:
            con.execute("create table fact_market_daily(trade_date date)")
            con.execute("insert into fact_market_daily values ('2026-07-24')")
        con.execute(
            "create table fact_mainline_theme_daily("
            "trade_date date, theme_name varchar, sector_count integer, min_sort integer)"
        )
        con.execute(
            "insert into fact_mainline_theme_daily values "
            "('2026-07-23', '电子', 2, 1), ('2026-07-28', '未来题材', 1, 1)"
        )
        con.execute(
            "create table fact_mainline_sector_daily("
            "trade_date date, theme_name varchar, sector_name varchar)"
        )
        con.execute(
            "insert into fact_mainline_sector_daily values "
            "('2026-07-22', '电子', '半导体'), ('2026-07-28', '未来题材', '未来板块')"
        )
    registry, context = _registry(tmp_path, reference_date=reference_date)
    result = registry.execute("mainline_context", {}, context=context, step_id="mixed:1")
    assert result.trace.status == "success"
    assert result.gaps == ()
    assert result.evidence
    assert result.trace.served_date == "2026-07-23"
    assert all(item.source_date in {"2026-07-22", "2026-07-23"} for item in result.evidence)
    assert {item.source_date for item in result.evidence if "题材级主线汇总" in item.detail} == {"2026-07-23"}
    assert {item.source_date for item in result.evidence if "半导体" in item.detail} == {"2026-07-22"}
    assert "未来" not in result.observation
    assert "不因日期差异降级或拒答" in result.observation
    assert not any(item.detail.startswith("使用要求：") for item in result.evidence)


@pytest.mark.parametrize("dataset_date", ["2026-07-22", "2026-07-27"])
def test_old_filtered_rows_are_delivered_without_inventing_exit(tmp_path: Path, dataset_date: str):
    with _database(tmp_path) as con:
        con.execute(
            "create table fact_mainline_sector_daily("
            "trade_date date, theme_name varchar, sector_name varchar, today_pct double)"
        )
        con.execute("insert into fact_mainline_sector_daily values ('2026-07-22', '电子', '半导体', 1.5)")
        con.execute("insert into fact_mainline_sector_daily values (?, '医药', '创新药', 2)", [dataset_date])
    registry, context = _registry(tmp_path)
    result = registry.execute(
        "finance_query",
        {
            "dataset": "mainline_sector_daily",
            "dimensions": ["trade_date", "theme_name", "sector_name"],
            "metrics": ["return_pct"],
            "filters": [{"field": "theme_name", "op": "eq", "value": "电子"}],
        },
        context=context, step_id="filtered:1",
    )
    assert result.trace.status in {"ok", "success"}
    assert len(result.evidence) == 1
    assert result.evidence[0].source_date == "2026-07-22"
    assert "1.5" in result.evidence[0].detail
    assert result.gaps == ()
    assert result.payload_sha256
    if dataset_date == "2026-07-27":
        assert "subject_exited_universe" in result.trace.detail
        assert "其后未再出现" in result.observation
    else:
        assert "subject_exited_universe" not in result.trace.detail
        assert "其后未再出现" not in result.observation
        assert "数据时点说明" in result.observation


def test_truly_empty_query_keeps_specific_gap(tmp_path: Path):
    with _database(tmp_path) as con:
        con.execute("create table fact_market_daily(trade_date date, total_amount double)")
    registry, context = _registry(tmp_path)
    result = registry.execute(
        "finance_query",
        {"dataset": "market_daily", "dimensions": ["trade_date"], "metrics": ["total_amount"]},
        context=context, step_id="empty:1",
    )
    assert result.trace.status == "empty"
    assert result.evidence == ()
    assert result.gaps == ("market_daily 在指定条件与时点内没有结构化结果",)
    assert "数据时点说明" not in result.observation


@pytest.mark.parametrize("theme_schema", ["missing", "date_only", "names_only"])
def test_partial_theme_table_does_not_hide_sector_facts(tmp_path: Path, theme_schema: str):
    with _database(tmp_path) as con:
        if theme_schema == "date_only":
            con.execute("create table fact_mainline_theme_daily(trade_date date)")
        elif theme_schema == "names_only":
            con.execute("create table fact_mainline_theme_daily(trade_date date, theme_name varchar)")
            con.execute("insert into fact_mainline_theme_daily values ('2026-07-23', '电子')")
        con.execute(
            "create table fact_mainline_sector_daily("
            "trade_date date, theme_name varchar, sector_name varchar)"
        )
        con.execute("insert into fact_mainline_sector_daily values ('2026-07-22', '电子', '半导体')")
    registry, context = _registry(tmp_path)
    result = registry.execute("mainline_context", {}, context=context, step_id="partial:1")
    assert result.trace.status == "success"
    assert any(item.source_date == "2026-07-22" and "半导体" in item.detail for item in result.evidence)
    if theme_schema == "names_only":
        assert any(item.source_date == "2026-07-23" and "题材级主线汇总" in item.detail for item in result.evidence)


def test_direct_mainline_block_without_overview_still_uses_available_tables(tmp_path: Path, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 27)

    monkeypatch.setattr(ask_blocks, "date", FixedDate)
    with _database(tmp_path) as con:
        con.execute("create table fact_mainline_theme_daily(trade_date date, theme_name varchar)")
        con.execute(
            "insert into fact_mainline_theme_daily values "
            "('2026-07-23', '电子'), ('2026-07-28', '未来题材')"
        )
    block = ask_blocks._market_review_mainline_context_block_for_llm(
        "分析主线", None, tmp_path / "db" / "market_feature_store.duckdb"
    )
    assert "2026-07-23 题材级主线汇总：电子" in block
    assert "未来题材" not in block


@pytest.mark.parametrize("limit_up", [None, 0, 3])
def test_detailed_mainline_keeps_null_count_and_rule_lines_out_of_facts(tmp_path: Path, limit_up):
    with _database(tmp_path) as con:
        con.execute(
            "create table fact_mainline_sector_daily("
            "trade_date date, theme_name varchar, sector_name varchar, sort_no integer, "
            "cycle_status varchar, cycle_level varchar, today_pct double, limit_up_count integer, "
            "startup_date_small date, high_status_label varchar, near_breakout_label varchar, "
            "amount double, sector_ts_code varchar)"
        )
        con.execute(
            "create table fact_sector_daily("
            "trade_date date, sector_ts_code varchar, pct_chg double, diff_ratio double, "
            "amount double, sw_l1 varchar)"
        )
        con.execute(
            "insert into fact_mainline_sector_daily values "
            "('2026-07-22', '电子', '半导体', 1, '分歧', null, 1.5, ?, "
            "'2026-07-20', null, null, null, 'chip.FP')",
            [limit_up],
        )
    registry, context = _registry(tmp_path)
    result = registry.execute("mainline_context", {}, context=context, step_id="detailed:1")
    assert result.trace.status == "success"
    sector = next(item for item in result.evidence if "电子核心板块" in item.detail)
    assert sector.source_date == "2026-07-22"
    assert "涨1.50%" in sector.detail
    assert "边际量-%" in sector.detail
    assert "成交-亿" in sector.detail
    assert f"涨停{'-' if limit_up is None else limit_up}" in sector.detail
    if limit_up is None:
        assert "涨停0" not in sector.detail
    assert not any("判读[" in item.detail for item in result.evidence)
    assert "判读[" in result.observation


def test_episode_date_instruction_separates_reference_from_cutoff(tmp_path: Path):
    import json
    from intelligence.services.episode_protocol import build_episode_input

    registry, context = _registry(tmp_path)
    payload = json.loads(build_episode_input(_market_forecast_frame(), context, registry))
    assert "不可变日期上限" in payload["date_rule"]
    assert "不因日期差异降级或拒答" in payload["date_rule"]
    assert "真正缺失" in payload["date_rule"]
    assert payload["information_cutoff"]["as_of_date"] == "2026-07-27"


def test_market_block_selects_available_data_newer_than_reference(tmp_path: Path, monkeypatch):
    seen = []
    monkeypatch.setattr(
        episode_tools.ask_blocks, "_market_data_asof",
        lambda *_a, **kw: seen.append(kw["as_of"]) or "2026-07-24",
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks, "_daily_market_overview_block_for_llm",
        lambda *_a, **kw: seen.append(kw["as_of"]) or "2026-07-24 成交额10000亿元",
    )
    monkeypatch.setattr(episode_tools.ask_blocks, "_market_cause_window_block_for_llm", lambda *_a, **_k: "")
    monkeypatch.setattr(episode_tools, "_asof_prefetch_text", lambda *_a: "")
    registry, context = _registry(tmp_path, reference_date="2026-07-21")
    result = registry.execute("market_data", {}, context=context, step_id="newer:1")
    assert set(seen) == {"2026-07-27"}
    assert result.trace.status == "success"
    assert {item.source_date for item in result.evidence} == {"2026-07-24"}
    assert result.gaps == ()


@pytest.mark.parametrize("source_date", [None, "not-a-date"])
def test_unknown_date_is_not_replaced_with_reference_date(tmp_path: Path, monkeypatch, source_date):
    monkeypatch.setattr(episode_tools.ask_blocks, "_market_data_asof", lambda *_a, **_k: source_date)
    monkeypatch.setattr(
        episode_tools, "_market_block",
        lambda *_a, **_k: ("成交额10000亿元", "本地 DuckDB", "market_overview"),
    )
    registry, context = _registry(tmp_path)
    result = registry.execute("market_data", {}, context=context, step_id="unknown:1")
    assert result.trace.status == "success"
    assert result.evidence
    assert all(item.source_date != "2026-07-27" for item in result.evidence)
    assert "数据日期未确认" in result.observation
    assert result.gaps == ()
