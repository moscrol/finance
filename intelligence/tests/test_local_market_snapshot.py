from datetime import date
import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import SealedFixturePolicy, build_episode_registry
from intelligence.services.market_snapshot_contract import load_market_snapshot_as_of
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import default_registry
from intelligence.services.turn_controller import decide_turn

CURRENT = "只用本地已有数据，不联网：截至2026年9月21日，A股市场处于什么状态、当前有哪些主要题材？请结合真实数据分析，注明各项数据截至日期，缺少的部分单独说明。"
HISTORICAL = "只用本地已有数据，不联网：把信息截止严格限定为2026年9月11日，分析当时A股市场的成交额、市场阶段和主要题材。请给出实际数值与来源日期，不使用9月11日之后的数据，缺失的部分单独说明。"


def _snapshot(root, day="2026-09-21", **overrides):
    root.mkdir(exist_ok=True)
    doc = {
        "schema_version": "1.1-akshare", "trade_date": day, "source_data_date": day,
        "source": "AkShare", "freshness": "fresh", "quality": "complete",
        "market": {"stage": "上涨阶段", "total_amount": 20479.03, "amount_ratio": None,
                   "advancers": 4535, "decliners": 936, "limit_up": 103, "limit_down": 0,
                   "capacity_top3": []},
        "themes": [{"concept": "化学制药", "priority_score": 90, "trigger_types": ["akshare_limit_up_pool"],
                    "limit_up_count": 9, "new_high_count": None}],
        "strong_stocks": [],
        **overrides,
    }
    (root / f"{day}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def _registry(tmp_path, question=CURRENT):
    frame = decide_turn(question).task_frame
    context = build_episode_context(frame, task_id=tmp_path.name, today="2026-09-21", latest_data_date="2026-09-21", timeout=30, synthesis_reserve=0)
    registry = build_episode_registry(frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki", fixture_policy=SealedFixturePolicy())
    return context, registry


def test_local_only_reads_snapshot_without_mixed_tools_or_network(tmp_path, monkeypatch):
    import socket

    def forbidden(*_a, **_kw):
        pytest.fail("snapshot must not connect or use mixed market runner")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr("intelligence.services.episode_tools._market_block", forbidden)
    _snapshot(tmp_path / "market_snapshot")
    context, registry = _registry(tmp_path)
    assert context.contract.material_contract.data_scope == "local_only"
    names = registry.names()
    assert "local_market_snapshot" in names
    assert not {"market_data", "financial_data", "web_search"}.intersection(names)
    assert all(spec.io_effect == "local_read" for spec in registry.authorized_specs())
    result = registry.execute("local_market_snapshot", {}, context=context, step_id="snapshot")
    assert result.trace.status == "success"
    assert {item.source_date for item in result.evidence} == {"2026-09-21"}
    assert any("20479.03亿元" in item.detail for item in result.evidence)
    assert any("跌停家数 0家" in item.detail for item in result.evidence)
    assert "null" in next(item.detail for item in result.evidence if "化学制药" in item.title)
    assert not any("快照成交量比 0" in item.detail for item in result.evidence)
    assert "不等同于复盘周期阶段" in result.observation
    assert "不是全市场题材或主线全集" in result.observation
    assert all(item.content_hash and item.internal_locator for item in result.evidence)


def test_snapshot_theme_locator_preserves_original_array_index(tmp_path):
    from intelligence.services.local_market_snapshot import read_snapshot_evidence

    root = tmp_path / "snapshots"
    doc = _snapshot(root)
    _snapshot(root, themes=[None, *doc["themes"]])
    evidence, _, _ = read_snapshot_evidence(root, as_of=date(2026, 9, 21))
    theme = next(item for item in evidence if "化学制药" in item.title)
    assert theme.internal_locator.endswith("#themes.1")
    assert [(item.metric, item.value) for item in theme.observations] == [("snapshot_priority_score", 90.0), ("snapshot_limit_up_count", 9.0)]


def test_historical_cutoff_reaches_query_and_snapshot_runners(tmp_path):
    root = tmp_path / "market_snapshot"
    _snapshot(root)
    _snapshot(root, "2026-09-11")
    (tmp_path / "db").mkdir()
    with duckdb.connect(str(tmp_path / "db/market_feature_store.duckdb")) as con:
        con.execute("create table fact_market_daily(trade_date date, total_amount double)")
        con.execute("insert into fact_market_daily values ('2026-09-11', 19710.64), ('2026-09-18', 99999)")
    context, registry = _registry(tmp_path, HISTORICAL)
    assert context.information_cutoff.as_of_date == date(2026, 9, 11)
    args = {"dataset": "market_daily", "dimensions": ["trade_date"], "metrics": ["total_amount"]}
    result = registry.execute("finance_query", args, context=context, step_id="omitted")
    assert result.evidence and {item.source_date for item in result.evidence} == {"2026-09-11"}
    assert "19710.64" in result.observation and "99999" not in result.observation
    result = registry.execute("finance_query", {**args, "time_range": {"start": "2026-09-18", "end": "2026-09-18"}}, context=context, step_id="beyond")
    assert not result.evidence and result.trace.status == "parse_error"
    assert "information cutoff" in result.observation
    result = registry.execute("local_market_snapshot", {}, context=context, step_id="history-snapshot")
    assert {item.source_date for item in result.evidence} == {"2026-09-11"}


@pytest.mark.parametrize("shape", ("future_only", "mixed", "observation_only", "past_with_future_observation"))
def test_explicit_cutoff_does_not_redeliver_all_future_tool_evidence(tmp_path, shape):
    context, _ = _registry(tmp_path, HISTORICAL)

    def runner(*_args):
        future = AgentEvidence(tool="mainline_context", title="SECRET-FUTURE", detail="99999 future", source="fixture", source_date="2026-09-18")
        past = AgentEvidence(tool="mainline_context", title="past", detail="past value", source="fixture", source_date="2026-09-11")
        evidence = {
            "observation_only": [], "mixed": [past, future],
            "past_with_future_observation": [past], "future_only": [future],
        }[shape]
        return evidence, "99999 future", ProviderTrace(provider="fixture", capability="mainline_context", status="success", detail="99999 future", source_trade_date="2026-09-18"), ("99999 future gap",)

    registry = default_registry({"mainline_context": runner})
    # Verify the shared cutoff guard, independent of the local-only authorization guard.
    from dataclasses import replace
    context = replace(context, contract=replace(context.contract, material_contract=None, allowed_capabilities=("mainline_context",)))
    result = registry.execute("mainline_context", {}, context=context, step_id="hostile")
    has_past = shape in {"mixed", "past_with_future_observation"}
    assert len(result.evidence) == (1 if has_past else 0)
    assert result.trace.status == ("success" if has_past else "future_of_cutoff")
    assert "99999" not in repr(result) and "SECRET-FUTURE" not in repr(result)
    assert "已隔离" in str(result.gaps)


def test_strict_cutoff_does_not_reuse_non_strict_cached_delivery(tmp_path):
    from dataclasses import replace
    from intelligence.services.query_ledger import query_ledger_scope
    from intelligence.services.research_contract import InformationCutoff

    context, _ = _registry(tmp_path, HISTORICAL)
    context = replace(context, contract=replace(context.contract, material_contract=None, allowed_capabilities=("mainline_context",)))
    loose = replace(context, information_cutoff=InformationCutoff(date(2026, 9, 11), "runtime_default"))

    def runner(*_args):
        return [AgentEvidence(tool="mainline_context", title="future", detail="99999", source="fixture", source_date="2026-09-18")], "99999", ProviderTrace(provider="fixture", capability="mainline_context", status="success")

    registry = default_registry({"mainline_context": runner})
    with query_ledger_scope():
        first = registry.execute("mainline_context", {}, context=loose, step_id="loose")
        second = registry.execute("mainline_context", {}, context=context, step_id="strict")
    assert first.evidence
    assert not second.evidence and "99999" not in repr(second)


@pytest.mark.parametrize("overrides", [
    {"trade_date": "2026-09-22"}, {"served_trade_date": "2026-09-22"},
    {"source_data_date": "2026-09-22"}, {"source_data_date": "bad"},
    {"quality": "failed"}, {"market": []},
])
def test_bad_or_contradictory_newer_snapshot_does_not_erase_valid_older(tmp_path: Path, overrides):
    root = tmp_path / "snapshots"
    _snapshot(root, "2026-09-11")
    _snapshot(root, **overrides)
    loaded = load_market_snapshot_as_of(root, date(2026, 9, 21))
    assert loaded["found"] and loaded["doc"]["trade_date"] == "2026-09-11"
    assert loaded["warnings"]


def test_history_never_reads_latest_meta_or_future_daily(tmp_path, monkeypatch):
    root = tmp_path / "snapshots"
    _snapshot(root, "2026-09-11", quality="partial", freshness="historical")
    _snapshot(root)
    original = Path.read_text
    reads = []

    def read(path, *args, **kwargs):
        reads.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    loaded = load_market_snapshot_as_of(root, date(2026, 9, 11))
    assert reads == ["2026-09-11.json"]
    assert loaded["doc"]["quality"] == "partial"
    assert loaded["doc"]["freshness"] == "historical"


def test_material_only_never_loads_snapshot(tmp_path, monkeypatch):
    from dataclasses import replace
    from intelligence.services.material_contract import MaterialContract

    def forbidden(*_a, **_k):
        pytest.fail("material_only must not read a snapshot")

    monkeypatch.setattr("intelligence.services.episode_tools._roots", forbidden)
    frame = replace(decide_turn(CURRENT).task_frame, material_contract=MaterialContract("constraint_confirmed", "real", "material_only"))
    context = build_episode_context(frame, task_id=tmp_path.name, today="2026-09-21")
    assert "local_market_snapshot" not in context.contract.allowed_capabilities
    registry = build_episode_registry(frame, context)
    assert registry.names() == ()


def test_sealed_snapshot_does_not_escape_to_environment(tmp_path, monkeypatch):
    production = tmp_path / "production"
    _snapshot(production)
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(production))
    context, registry = _registry(tmp_path)
    result = registry.execute("local_market_snapshot", {}, context=context, step_id="sealed")
    assert not result.evidence


def test_sealed_snapshot_without_explicit_root_never_probes_default(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("sealed snapshot without a root must not probe daily files")

    monkeypatch.setattr("intelligence.services.local_market_snapshot.load_market_snapshot_as_of", forbidden)
    frame = decide_turn(CURRENT).task_frame
    context = build_episode_context(frame, task_id=tmp_path.name, today="2026-09-21")
    registry = build_episode_registry(frame, context, fixture_policy=SealedFixturePolicy(market_db_path=tmp_path / "missing.duckdb"))
    result = registry.execute("local_market_snapshot", {}, context=context, step_id="no-root")
    assert not result.evidence and "未读取默认目录" in result.observation


@pytest.mark.parametrize("question", ("今天A股市场怎么样", "只用本地已有数据，不联网：什么是市盈率"))
def test_snapshot_not_added_to_unrestricted_or_non_market_menu(question):
    frame = decide_turn(question).task_frame
    context = build_episode_context(frame, task_id="menu-scope", today="2026-09-21")
    assert "local_market_snapshot" not in context.contract.allowed_capabilities


def test_snapshot_parameters_cannot_relax_cutoff(tmp_path):
    from intelligence.services.research_tool_registry import InvalidResearchToolArguments

    context, registry = _registry(tmp_path, HISTORICAL)
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare("local_market_snapshot", {"date": "2026-09-21"})
    assert context.information_cutoff.as_of_date == date(2026, 9, 11)


def test_no_snapshot_reports_scoped_gap(tmp_path):
    context, registry = _registry(tmp_path)
    result = registry.execute("local_market_snapshot", {}, context=context, step_id="empty")
    assert not result.evidence and result.trace.status == "empty"
    assert "不代表整个本地没有该日数据" in result.observation
