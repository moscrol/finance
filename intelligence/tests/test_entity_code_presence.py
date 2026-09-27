"""Exact entity identity is checked independently of interval data coverage."""

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import duckdb
import pytest

from intelligence.services.historical_research.query import (
    HistoryQuery,
    HistoryQueryError,
    HistoryQuerySpec,
)
from intelligence.services.finance_query import FinanceQuery, FinanceQueryError, FinanceQuerySpec
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline


@pytest.fixture
def entity_db(tmp_path):
    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    with duckdb.connect(str(path)) as con:
        con.execute((Path(__file__).parents[2] / "market_feature_store/schema.sql").read_text())
        con.execute("""
            INSERT INTO ops_sector_universe_snapshot_daily VALUES
              ('2026-08-03', 'old', 'test', 2, 0, 'published', '2026-08-03'),
              ('2026-09-17', 'new', 'test', 2, 0, 'published', '2026-09-17'),
              ('2026-09-17', 'candidate', 'test', 1, 0, 'candidate', '2026-09-17');
            INSERT INTO fact_sector_universe_daily VALUES
              ('2026-08-03', 'old', 'OLD.TI', '旧码', 0, 'test', '2026-08-03'),
              ('2026-08-03', 'old', 'NO_BAR.FP', '已知无行情', 0, 'test', '2026-08-03'),
              ('2026-09-17', 'new', 'NEW.FP', '新码', 0, 'test', '2026-09-17'),
              ('2026-09-17', 'new', 'NO_BAR.FP', '已知无行情', 0, 'test', '2026-09-17'),
              ('2026-09-17', 'candidate', 'CANDIDATE.BK', '未发布', 0, 'test', '2026-09-17');
            INSERT INTO fact_market_daily (trade_date, sh_index_pct_chg) VALUES
              ('2026-08-03', 0), ('2026-09-17', 0);
            INSERT INTO fact_sector_daily_generation
              (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount) VALUES
              ('2026-07-01', 'legacy', 'LEGACY.TI', '旧目录', 1, 100),
              ('2026-09-17', 'new', 'NEW.FP', '新码', 1, 100),
              ('2026-09-17', 'candidate', 'CANDIDATE.BK', '未发布', 1, 100),
              ('2026-09-17', 'legacy', 'HIDDEN_LEGACY.TI', '被已发布快照遮蔽', 1, 100);
        """)
    return path


def _history(path, codes, *, end="2026-09-18", kind="sector"):
    return HistoryQuery(path).run(
        HistoryQuerySpec.from_arguments({
            "operation": "compute_history", "start": "2026-08-01", "end": end,
            "entity_kind": kind, "entity_codes": list(codes),
        }),
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )


def test_unknown_history_code_is_not_an_all_null_research_sample(entity_db):
    with pytest.raises(HistoryQueryError, match="unknown_entity_code") as error:
        _history(entity_db, ("899050.BK",))
    assert error.value.entity_check.unknown_codes == ("899050.BK",)


def _finance_arguments(codes, *, op="in", kind="sector", end="2026-09-18"):
    return {
        "dataset": f"{kind}_daily", "dimensions": ["trade_date", f"{kind}_code"],
        "metrics": ["amount"],
        "filters": [{"field": f"{kind}_code", "op": op, "value": list(codes) if op == "in" else codes[0]}],
        "time_range": {"start": "2026-08-01", "end": end},
    }


def _finance(path, codes, **kwargs):
    return FinanceQuery(path).run(
        FinanceQuerySpec.from_arguments(_finance_arguments(codes, **kwargs)),
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )


@pytest.mark.parametrize("op", ["eq", "in"])
def test_finance_exact_unknown_is_a_typed_failure(entity_db, op):
    with pytest.raises(FinanceQueryError, match="unknown_entity_code") as error:
        _finance(entity_db, ("899050.BK",), op=op)
    assert error.value.entity_check.unknown_codes == ("899050.BK",)


@pytest.mark.parametrize("tool", ["history_query", "finance_query"])
def test_episode_preserves_fabricated_gap_without_minting_evidence(entity_db, tmp_path, monkeypatch, tool):
    _, context, registry, arguments = _tool_setup(entity_db, tmp_path, monkeypatch, tool)
    result = registry.execute(tool, arguments, context=context, step_id="entities")
    assert not result.evidence
    assert "unknown_entity_code" in result.observation
    assert result.gaps == ("fabricated_entity:sector:899050.BK",)
    assert result.telemetry["entity_check"]["known_codes"] == ["OLD.TI"]


def _tool_setup(entity_db, tmp_path, monkeypatch, tool):
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_tools import build_episode_registry
    from intelligence.services.historical_research.episode import HistorySession, history_tool_specs
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.services.run_store import RunStore

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    frame = understand_query("这一波农业是怎么走出来的？").task_frame
    if tool == "finance_query":
        frame = replace(frame, history_intent=None, raw_question="查询2026-08-01至2026-09-18农业板块成交额")
    context = build_episode_context(
        frame, task_id=uuid4().hex, capabilities=("finance_query",),
        information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
    )
    if tool == "history_query":
        store = RunStore("entity-test", root=tmp_path / "runs")
        run = store.create_run(frame.raw_question, "ask", session_id="entity-history")
        session = HistorySession(store, run.run_id, "entity-history")
        registry = ResearchToolRegistry(tuple(history_tool_specs(frame, context, entity_db, session)))
        arguments = {"operation": "compute_history", "start": "2026-08-01", "end": "2026-09-18",
                     "entity_codes": ["OLD.TI", "899050.BK"]}
    else:
        registry = build_episode_registry(
            frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki",
        )
        registry = ResearchToolRegistry((registry.resolve("finance_query"),))
        arguments = _finance_arguments(("OLD.TI", "899050.BK"))
    return frame, context, registry, arguments


@pytest.mark.parametrize("code", ["NO_BAR.FP", "OLD.TI", "LEGACY.TI"])
def test_known_codes_do_not_require_interval_quotes_or_latest_membership(entity_db, code):
    before = entity_db.read_bytes()
    history = _history(entity_db, (code,))
    finance = _finance(entity_db, (code,))
    assert history["status"] == "research_only"
    assert history["rows"][0]["features"]["return_pct"] is None
    assert finance.rows == ()
    assert not any("fabricated_entity" in gap for gap in history["gaps"])
    assert entity_db.read_bytes() == before


@pytest.mark.parametrize("runner,error_type", [(_history, HistoryQueryError), (_finance, FinanceQueryError)])
@pytest.mark.parametrize("code", ["CANDIDATE.BK", "HIDDEN_LEGACY.TI"])
def test_candidate_and_shadowed_legacy_rows_are_not_published_identity(entity_db, runner, error_type, code):
    with pytest.raises(error_type, match="unknown_entity_code"):
        runner(entity_db, (code,))


@pytest.mark.parametrize("runner,error_type", [(_history, HistoryQueryError), (_finance, FinanceQueryError)])
def test_catalog_uses_requested_historical_end_not_today(entity_db, runner, error_type):
    runner(entity_db, ("OLD.TI",), end="2026-08-03")
    with pytest.raises(error_type, match="unknown_entity_code"):
        runner(entity_db, ("NEW.FP",), end="2026-08-03")


@pytest.mark.parametrize("fault", ["missing", "incomplete", "undated_dimension"])
@pytest.mark.parametrize("runner,error_type", [(_history, HistoryQueryError), (_finance, FinanceQueryError)])
def test_unverifiable_directory_is_distinct_from_unknown(entity_db, runner, error_type, fault):
    with duckdb.connect(str(entity_db)) as con:
        if fault == "missing":
            con.execute("DROP TABLE fact_sector_universe_daily")
        elif fault == "incomplete":
            con.execute("UPDATE ops_sector_universe_snapshot_daily SET sector_count=9 WHERE status='published'")
        else:
            con.execute("INSERT INTO dim_sector (sector_ts_code, sector_name) VALUES ('899050.BK', '无时点身份')")
    with pytest.raises(error_type, match="entity_catalog_unavailable") as error:
        runner(entity_db, ("899050.BK",))
    assert error.value.entity_check.unknown_codes == ()
    assert not any("fabricated_entity" in gap for gap in error.value.entity_check.gaps)


@pytest.mark.parametrize("runner,error_type", [(_history, HistoryQueryError), (_finance, FinanceQueryError)])
def test_stock_identity_is_positive_only_without_complete_list(entity_db, runner, error_type):
    with duckdb.connect(str(entity_db)) as con:
        con.execute("INSERT INTO fact_stock_daily (trade_date, stock_ts_code) VALUES ('2026-07-01', '600001.SH')")
    runner(entity_db, ("600001.SH",), kind="stock")
    with pytest.raises(error_type, match="entity_catalog_unavailable") as error:
        runner(entity_db, ("600001.SH", "999999.SH"), kind="stock")
    assert error.value.entity_check.known_codes == ("600001.SH",)
    assert error.value.entity_check.unverifiable_codes == ("999999.SH",)
    assert error.value.entity_check.unknown_codes == ()


def test_contains_and_exclusion_are_searches_not_exact_identity_claims(entity_db):
    assert _finance(entity_db, ("NEW",), op="contains").rows
    assert _finance(entity_db, ("899050",), op="contains").rows == ()
    assert _finance(entity_db, ("899050.BK",), op="ne").rows


def test_dated_dimension_can_prove_identity_without_a_price_record(entity_db):
    with duckdb.connect(str(entity_db)) as con:
        con.execute("INSERT INTO dim_sector (sector_ts_code, sector_name, first_seen_date) VALUES ('DIM.TI', '维表已知', '2026-07-01')")
    assert _finance(entity_db, ("DIM.TI",)).rows == ()
    assert _history(entity_db, ("DIM.TI",))["rows"][0]["features"]["return_pct"] is None


def test_frozen_live_history_request_is_rejected_before_calculation(entity_db):
    fixture = Path(__file__).parent / "fixtures/live_products/run_20260922_191550_067475"
    episode_bytes = (fixture / "continuous-episode.json").read_bytes()
    manifest = json.loads((fixture / "MANIFEST.json").read_text())
    assert hashlib.sha256(episode_bytes).hexdigest() == manifest["frozen"]["continuous-episode.json"]["sha256"]
    arguments = json.loads(episode_bytes)["events"][24]["payload"]["arguments"]
    with pytest.raises(HistoryQueryError, match="unknown_entity_code") as error:
        HistoryQuery(entity_db).run(
            HistoryQuerySpec.from_arguments(arguments),
            information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
            deadline=ResearchDeadline.from_timeout(10),
        )
    assert error.value.entity_check.unknown_codes == ("899050.BK",)


@pytest.mark.parametrize("tool", ["history_query", "finance_query"])
@pytest.mark.parametrize("finish_mode", ["normal", "recovery"])
def test_entity_failure_reaches_episode_outcome_gaps(entity_db, tmp_path, monkeypatch, tool, finish_mode):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.tests.test_agent_episode import _finish_turn

    frame, context, registry, arguments = _tool_setup(entity_db, tmp_path, monkeypatch, tool)

    class ScriptedConsumer:
        calls = 0

        def complete(self, *, messages, tools, timeout):
            self.calls += 1
            delivered = [message for message in messages if message.get("role") == "tool"]
            if finish_mode == "recovery" and self.calls == 1:
                known = dict(arguments)
                if tool == "history_query":
                    known["entity_codes"] = ["NEW.FP"]
                else:
                    known["filters"] = [{"field": "sector_code", "op": "eq", "value": "NEW.FP"}]
                return ModelTurn("", (ModelToolCall("known", tool, known),))
            if self.calls == (1 if finish_mode == "normal" else 2):
                return ModelTurn("", (ModelToolCall("unknown", tool, arguments),))
            if finish_mode == "recovery" and self.calls in (3, 4):
                return ModelTurn("malformed finish", (), "scripted", "")
            if finish_mode == "normal":
                assert any("unknown_entity_code" in message["content"] for message in delivered)
            return _finish_turn(status="partial", hashes=(), gap="需先核实实体代码", draft="实体代码未核实，不能据此推断市场行情缺失。")

    outcome = ContinuousAgentEpisode(ScriptedConsumer()).run(task_frame=frame, context=context, registry=registry)
    assert outcome.stop_reason == ("model_finish" if finish_mode == "normal" else "finalization_recovered")
    assert "fabricated_entity:sector:899050.BK" in outcome.gaps
    if finish_mode == "normal":
        assert not outcome.evidence
    else:
        assert outcome.evidence
        assert all("899050.BK" not in item.detail for item in outcome.evidence)


@pytest.mark.parametrize("tool", ["history_query", "finance_query"])
def test_entity_failure_during_repair_reaches_outcome(entity_db, tmp_path, monkeypatch, tool):
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
    from intelligence.tests.test_agent_episode import ScriptedModel, _finish_turn

    frame, context, registry, arguments = _tool_setup(entity_db, tmp_path, monkeypatch, tool)
    finish = _finish_turn(status="partial", hashes=(), gap="需先核实实体代码", draft="实体代码未核实，不能据此推断市场行情缺失。")
    session = GLMAgentRuntime(client=ScriptedModel([
        finish, ModelTurn("", (ModelToolCall("unknown", tool, arguments),)), finish,
    ])).start(frame, context=context, registry=registry)
    outcome = session.resume(RepairGoal(
        episode_id=context.contract.task_id, repair_goal_id=uuid4().hex, cycle=1,
        missing_answer_elements=("direct_assessment",), unsupported_claims=(),
        missing_evidence_modes=("finance_query",), attempted_actions=(),
        evidence_progress=CoverageDelta(1, 0, 1), remaining_calls=1, remaining_seconds=10,
    ))
    assert outcome.stop_reason == "repair_model_finish"
    assert "fabricated_entity:sector:899050.BK" in outcome.gaps
    assert not outcome.evidence


@pytest.mark.parametrize("interruption", ["deadline", "cancelled"])
def test_finance_catalog_reads_share_the_existing_deadline_and_cancellation(entity_db, monkeypatch, interruption):
    from intelligence.services import finance_query as fq
    from intelligence.services import research_contract as rc

    state = SimpleNamespace(now=100.0, cancelled=False, catalog_read=False, closed=False)
    monkeypatch.setattr(fq, "time", SimpleNamespace(monotonic=lambda: state.now))
    monkeypatch.setattr(rc, "time", SimpleNamespace(monotonic=lambda: state.now))

    class Connection:
        def __init__(self, path, *, read_only):
            assert read_only
            self.inner = duckdb.connect(path, read_only=True)

        def execute(self, sql, parameters=None):
            result = self.inner.execute(sql, parameters)
            if "information_schema.columns" in sql:
                state.catalog_read = True
                if interruption == "deadline":
                    state.now += 30
                else:
                    state.cancelled = True
            return result

        def interrupt(self):
            self.inner.interrupt()

        def close(self):
            self.inner.close()
            state.closed = True

    expected = fq.FinanceQueryTimedOut if interruption == "deadline" else fq.FinanceQueryCancelled
    with pytest.raises(expected):
        FinanceQuery(entity_db, connect=Connection).run(
            FinanceQuerySpec.from_arguments(_finance_arguments(("OLD.TI",))),
            information_cutoff=InformationCutoff(date(2026, 9, 18), "requested"),
            deadline=ResearchDeadline.from_timeout(10), is_cancelled=lambda: state.cancelled,
        )
    assert state.catalog_read and state.closed
