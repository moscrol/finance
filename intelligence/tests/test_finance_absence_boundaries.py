"""Local nonmatches are process observations, not proof of absent events."""
from datetime import date
import json
import socket
import subprocess
from uuid import uuid4

import duckdb
import pytest

from intelligence.services import agent_research, episode_tools, finance_query
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_harness import FinanceResearchHarness


@pytest.fixture
def local_db(tmp_path):
    path = tmp_path / "finance" / "db" / "market_feature_store.duckdb"
    path.parent.mkdir(parents=True)
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE fact_stock_high_daily (trade_date DATE, stock_ts_code VARCHAR, price DOUBLE)")
        con.executemany("INSERT INTO fact_stock_high_daily VALUES (?, ?, ?)", [
            ("2026-08-18", "600673.SH", 36.7),
            ("2026-09-18", "600001.SH", 10.0),
        ])
        # A known stock with no high event is distinct from an unverifiable code.
        con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code VARCHAR)")
        con.execute("INSERT INTO fact_stock_daily VALUES ('2026-09-18', '600519.SH')")
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE, limit_up INTEGER)")
        con.execute("INSERT INTO fact_market_daily VALUES ('2026-09-18', 0)")
    return path


def arguments(code="600519.SH"):
    return dict(dataset="stock_high_daily", metrics=["price"], dimensions=["stock_code", "trade_date"],
                filters=[{"field": "stock_code", "op": "eq", "value": code}],
                time_range={"start": "2026-09-01", "end": "2026-09-18"}, limit=25)


def test_successful_empty_query_only_describes_local_match(local_db):
    result = finance_query.FinanceQuery(local_db).run(
        finance_query.FinanceQuerySpec.from_arguments(arguments()),
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(3),
    )
    assert result.rows == result.evidence == ()
    assert result.served_date is None
    assert result.audit.row_count == 0
    assert result.audit.requested_time_range == ("2026-09-01", "2026-09-18")
    assert "本次条件与截止时点内未命中本地记录" in result.observation
    assert "不证明事件未发生" in result.observation
    assert "不证明数据覆盖完整" in result.observation


def test_unverifiable_identity_is_not_a_successful_empty_query(local_db):
    with pytest.raises(finance_query.FinanceQueryEntityError) as raised:
        finance_query.FinanceQuery(local_db).run(
            finance_query.FinanceQuerySpec.from_arguments(arguments("999999.SH")),
            information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
            deadline=ResearchDeadline.from_timeout(3),
        )
    assert "entity_catalog_unavailable" in str(raised.value)
    assert "不能据此判定实体不存在" in str(raised.value)


def test_recorded_zero_remains_evidence_not_an_empty_query(local_db):
    result = finance_query.FinanceQuery(local_db).run(
        finance_query.FinanceQuerySpec.from_arguments(dict(
            dataset="market_daily", metrics=["limit_up"], dimensions=["trade_date"],
            time_range={"start": "2026-09-18", "end": "2026-09-18"},
        )), information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(3),
    )
    assert result.rows == ({"trade_date": "2026-09-18", "limit_up": 0},)
    assert len(result.evidence) == 1
    assert "未命中" not in result.observation


@pytest.mark.parametrize("mode", ["empty", "historical_match", "failure", "stale"])
@pytest.mark.parametrize("lean", ["off", "on"])
def test_local_registry_preserves_absence_boundary_through_model_projection(local_db, tmp_path, monkeypatch, mode, lean):
    frame = understand_query("只用本地已有资料，不联网：东阳光(600673.SH)2026-09-01至2026-09-18的新高记录？").task_frame
    context = build_episode_context(
        frame, task_id=f"absence-{uuid4().hex}", capabilities=tuple(sorted(LOCAL_READ_CAPABILITIES)),
        today="2026-09-18", latest_data_date="2026-09-18", timeout=10, synthesis_reserve=0,
    )
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("unexpected external IO")

    monkeypatch.setenv("ASK_EPISODE_LEAN_OBSERVATION", lean)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(agent_research, "build_default_tools", forbidden)
    monkeypatch.setattr(episode_tools, "_calc_loader_for", forbidden)
    if mode in {"failure", "stale"}:
        with duckdb.connect(str(local_db)) as con:
            con.execute("DROP TABLE fact_stock_high_daily" if mode == "failure" else
                        "DELETE FROM fact_stock_high_daily WHERE trade_date = '2026-09-18'")
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=local_db.parent.parent, knowledge_wiki=tmp_path / "wiki",
        memory_users_root=tmp_path / "users", derived_calculation_runner=forbidden,
    )
    assert registry.read_scope == "local_only"
    assert set(registry.names()) == set(context.contract.allowed_capabilities) == LOCAL_READ_CAPABILITIES
    result = registry.execute("finance_query", arguments("600673.SH" if mode != "empty" else "600519.SH"),
                              context=context, step_id="absence")
    assert attempted == []
    projection = FinanceResearchHarness().project_tool_result(result, evidence_so_far=result.evidence, seen_prose=set())
    model = json.loads(projection.model_content)
    assert model["gaps"] == list(result.gaps)
    again = FinanceResearchHarness().project_tool_result(
        result, evidence_so_far=result.evidence, seen_prose=projection.seen_prose,
    )
    assert json.loads(again.model_content)["gaps"] == list(result.gaps)
    if mode == "historical_match":
        assert len(result.evidence) == 1
        assert result.evidence[0].source_date == "2026-08-18"
        assert result.evidence[0].io_effect == "local_read"
        assert "36.7" in model["evidence"][0]["detail"]
        assert "本次交付的历史匹配记录日期截至" in model["observation"]
        assert "2026-08-18" in model["observation"]
        assert "2026-09-18" in model["observation"]
        assert "不证明事件未发生" in model["observation"]
        assert "不证明逐日覆盖完整" in model["observation"]
        assert "构成要素退出，非数据陈旧" not in model["observation"]
        assert result.gaps
        assert "历史记录不代替请求窗口内缺失的事实" in result.gaps[0]
    elif mode == "failure":
        assert result.trace.status == "request_error"
        assert result.evidence == ()
        assert "未命中本地记录" not in model["observation"]
        assert "事件未发生" not in model["observation"]
    else:
        assert result.trace.status == "empty"
        assert result.evidence == ()  # A stale dataset must not release the historical row.
        assert "不证明事件未发生" in model["observation"]
        assert "不证明数据覆盖完整" in model["observation"]
        assert "未命中本地记录" in model["observation"]
        assert "不证明事件未发生" in result.gaps[0]
