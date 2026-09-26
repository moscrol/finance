"""Saved live market-analogue failure: repair must preserve explicit entity semantics."""

from copy import deepcopy
from datetime import date, timedelta
import json
from uuid import uuid4

import duckdb
import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_tool_batch import EpisodeToolBatchSession
from intelligence.services import episode_tools
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.historical_research.episode import HistorySession
from intelligence.services.historical_research.query import HistoryQuerySpec, HistoryQueryError
from intelligence.services.query_understanding import understand_query
from intelligence.services.run_store import RunStore


def _arguments():
    # This is the live failure shape: index code + market features, omitted kind.
    return dict(
        operation="find_analogues", start="2026-08-11", end="2026-08-12",
        entity_codes=["000001.SH"], features=["return_pct", "advancers_mean"],
        search_start="2026-08-03", search_end="2026-08-07", window_days=2,
    )


def test_omitted_kind_is_not_silently_inferred_from_code_or_features():
    args = _arguments()
    before = deepcopy(args)
    with pytest.raises(HistoryQueryError, match="entity_kind/code mismatch") as exc:
        HistoryQuerySpec.from_arguments(args)
    assert "entity_kind='market'" in str(exc.value)
    assert "Omitted entity_kind defaults to sector" in str(exc.value)
    assert args == before
    repaired = HistoryQuerySpec.from_arguments(dict(args, entity_kind="market"))
    assert repaired.entity_kind == "market"
    assert repaired.start.isoformat() == args["start"]
    assert repaired.search_end.isoformat() == args["search_end"]


@pytest.mark.parametrize("kind", ["sector", "stock"])
def test_explicit_wrong_kind_is_rejected_even_without_market_only_features(kind):
    with pytest.raises(HistoryQueryError, match="entity_kind/code mismatch"):
        HistoryQuerySpec.from_arguments(dict(_arguments(), entity_kind=kind, features=["return_pct"]))


def test_missing_codes_diagnostic_mentions_explicit_market_kind_without_choosing_it():
    args = _arguments()
    args.pop("entity_codes")
    with pytest.raises(HistoryQueryError, match="exact entity_codes required") as exc:
        HistoryQuerySpec.from_arguments(args)
    assert "entity_kind='market'" in str(exc.value)
    assert "for sector/stock inspect exact codes first" in str(exc.value)


def test_feature_mismatch_explains_selected_kind_not_global_lack_of_capability():
    args = dict(_arguments(), entity_codes=["A.FP"])
    with pytest.raises(HistoryQueryError, match="features do not apply") as exc:
        HistoryQuerySpec.from_arguments(args)
    assert "entity_kind=sector" in str(exc.value)
    assert "incompatible=advancers_mean" in str(exc.value)
    assert "advancers_mean/limit_up_mean/limit_down_mean require entity_kind='market'" in str(exc.value)
    compatible = HistoryQuerySpec.from_arguments(dict(args, features=["return_pct"]))
    assert compatible.entity_kind == "sector"  # Preserve legacy compatible defaults.


def _registry(tmp_path):
    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE fact_market_daily(trade_date DATE, sh_index_pct_chg DOUBLE, total_amount DOUBLE, advancers INTEGER)")
        for index in range(10):
            day = date(2026, 8, 3) + timedelta(days=index)
            con.execute("INSERT INTO fact_market_daily VALUES (?, ?, ?, ?)", [day, index % 3 - 1, 1000 + index, 2000 + index])
    question = "不要联网。以2026-08-12为信息截止日，只研究2026-08-03至2026-08-12。当前市场处于什么阶段，与哪些历史阶段相似？"
    frame = understand_query(question).task_frame
    assert frame.history_intent is not None
    store = RunStore("test-market-repair", root=tmp_path / "runs")
    run = store.create_run(question, "ask", session_id=f"repair-{uuid4().hex}")
    session = HistorySession(store, run.run_id, run.session_id)
    context = build_episode_context(
        frame, task_id=run.run_id, today="2026-08-12", latest_data_date="2026-08-12",
        capabilities=("finance_query",),
    )
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path, knowledge_wiki=tmp_path / "wiki", history_session=session,
    )
    return registry, context, frame, session, path


def test_batch_rejects_then_corrected_arguments_execute_without_expanding_scope(tmp_path):
    registry, context, _, session, path = _registry(tmp_path)
    before = path.read_bytes()
    batch = EpisodeToolBatchSession()
    failed = batch.execute(
        (ModelToolCall("missing-kind", "history_query", _arguments()),),
        registry=registry, context=context, remaining_slots=3,
    )
    assert failed.executed_count == 0
    assert failed.items[0].status == "rejected"
    assert "entity_kind='market'" in failed.items[0].detail
    assert not session.refs
    repaired = batch.execute(
        (ModelToolCall("explicit-kind", "history_query", dict(_arguments(), entity_kind="market")),),
        registry=registry, context=context, remaining_slots=3,
    )
    assert repaired.executed_count == 1
    item = repaired.items[0]
    assert item.status == "success"
    ref = item.observation.telemetry["result_ref"]
    original = session.read(ref)
    assert original["spec"]["entity_kind"] == "market"
    assert original["spec"]["features"] == _arguments()["features"]
    assert original["authorized_scope"]["requested_start"] == "2026-08-03"
    assert original["knowledge_cutoff"] == "2026-08-12"
    assert path.read_bytes() == before


class _MarketRepairModel:
    """Scripted wire-level repair test; not evidence of real-model research ability."""

    def __init__(self, context):
        self.context = context
        self.result_ref = None
        self.received_diagnostic = False

    def complete(self, *, messages, tools, timeout):
        observed = [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]
        assert len(observed) <= 2
        if not observed:
            args = _arguments()
        elif len(observed) == 1:
            assert observed[-1]["ok"] is False
            assert "entity_kind='market'" in observed[-1]["detail"]
            self.received_diagnostic = True
            args = dict(_arguments(), entity_kind="market")
        else:
            assert observed[-1]["ok"] is True
            assert observed[-1]["evidence"]
            observation = observed[-1]["observation"]
            meta, _ = json.JSONDecoder().raw_decode(observation[observation.index("{"):])
            self.result_ref = meta["result_ref"]
            gap = "脚本只验证类型诊断可恢复；相似窗口不是规律，完整条件比较未完成。"
            return ModelTurn(json.dumps({
                "status": "partial", "draft": gap, "gaps": [gap],
                # basis 跟随合同的 grounding_mode：假设槽不得伪装成证据。
                "bindings": [{"output_id": item.output_id, "evidence_hashes": [],
                              "basis": item.grounding_mode, "gap": gap}
                             for item in self.context.contract.required_outputs],
                "history_research": {
                    "purpose": self.context.history_intent.purpose, "result_refs": [self.result_ref],
                    "claim_level": "single_case", "research_only": True,
                    "decision_eligible": False, "promotion_eligible": False,
                },
            }, ensure_ascii=False), (), "scripted-market-repair", "")
        return ModelTurn("", (ModelToolCall(f"history-repair-{len(observed)}", "history_query", args),), "scripted-market-repair", "")


def test_real_episode_returns_market_kind_hint_and_saves_corrected_analogue_original(tmp_path):
    registry, context, frame, session, path = _registry(tmp_path)
    before = path.read_bytes()
    model = _MarketRepairModel(context)
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert outcome.stop_reason == "model_finish"
    assert model.received_diagnostic and model.result_ref
    assert session.read(model.result_ref)["spec"]["entity_kind"] == "market"
    assert len(session.refs) == 1
    assert path.read_bytes() == before
