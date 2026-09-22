"""Market -> historical episode -> leaders -> succession, without hindsight claims."""

from copy import deepcopy
from datetime import date, timedelta
import json

import duckdb
import pytest

from intelligence.services.historical_research.features import compute_features
from intelligence.services.historical_research.intent import (
    HistoryIntent,
    infer_history_intent,
    inherit_history_followup,
)
from intelligence.services.historical_research.query import (
    HistoryQuery,
    HistoryQuerySpec,
)
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline


@pytest.fixture
def anatomy_db(tmp_path):
    path = tmp_path / "anatomy.duckdb"
    days = [date(2026, 1, 5) + timedelta(days=i) for i in range(25)]
    with duckdb.connect(str(path)) as con:
        con.execute("""CREATE TABLE fact_market_daily (
            trade_date DATE, sh_index_pct_chg DOUBLE, total_amount DOUBLE,
            advancers INT, limit_up INT, limit_down INT, market_stage TEXT,
            cycle_stage TEXT, cycle_stage_source TEXT)""")
        con.execute("""CREATE TABLE fact_sector_daily (
            trade_date DATE, sector_ts_code TEXT, sector_name TEXT,
            pct_chg DOUBLE, amount DOUBLE, diff_ratio DOUBLE, sector_universe_snapshot_id TEXT)""")
        con.execute("""CREATE TABLE fact_sector_stock_daily (
            trade_date DATE, sector_ts_code TEXT, stock_ts_code TEXT, stock_name TEXT,
            pct_chg DOUBLE, sector_universe_snapshot_id TEXT)""")
        con.execute("""CREATE TABLE fact_stock_daily (
            trade_date DATE, stock_ts_code TEXT, stock_name TEXT, pct_chg DOUBLE, amount DOUBLE)""")
        for i, day in enumerate(days):
            con.execute(
                "INSERT INTO fact_market_daily VALUES (?, ?, ?, ?, ?, ?, '供应商阶段', '供应商内层阶段', 'fixture-v1')",
                [day, i % 3 - 1, 10000 + i * 100, 1000 + i * 50, 30 + i, 10 + i % 2],
            )
            for code, launch in (("A.FP", 5), ("B.FP", 10)):
                pct = 5 if launch <= i <= launch + 2 else -4 if i > launch + 2 else 0
                con.execute(
                    "INSERT INTO fact_sector_daily VALUES (?, ?, '同名不同篮子', ?, 600, ?, 'snapshot')",
                    [day, code, pct, 11 if i == launch else 0],
                )
            for stock, pct in (
                ("S1", 10 if 5 <= i <= 7 else -5 if i > 7 else 0),
                ("S2", 2 if i >= 5 else 0),
                ("FUTURE", 50),
            ):
                con.execute(
                    "INSERT INTO fact_stock_daily VALUES (?, ?, ?, ?, ?)",
                    [day, stock, stock, pct, 200 if i == 5 else 100],
                )
            for stock in ("S1", "S2") if i <= 5 else ("S1", "S2", "FUTURE"):
                con.execute(
                    "INSERT INTO fact_sector_stock_daily VALUES (?, 'A.FP', ?, ?, 1, 'snapshot')",
                    [day, stock, stock],
                )
    return path


def run(path, **kw):
    args = dict(
        operation="trace_history",
        start="2026-01-05",
        end="2026-01-29",
        entity_codes=["A.FP", "B.FP"],
    )
    args.update(kw)
    return HistoryQuery(path).run(
        HistoryQuerySpec.from_arguments(args),
        information_cutoff=InformationCutoff(date(2026, 1, 29), "requested"),
        deadline=ResearchDeadline.from_timeout(10),
    )


def record(result, kind, code):
    return next(
        r
        for r in result["rows"]
        if r["record_kind"] == kind and r["entity_code"] == code
    )


def test_market_stage_provenance_and_new_comparable_features(anatomy_db):
    from intelligence.services.historical_research.episode import _result
    from tests.test_history_model_projection import _project

    with duckdb.connect(str(anatomy_db)) as con:
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN market_stage_source TEXT")
        con.execute("ALTER TABLE fact_market_daily ADD COLUMN market_stage_confidence DOUBLE")
        con.execute("UPDATE fact_market_daily SET market_stage_source='local:stage-lr-v1', market_stage_confidence=0.961")
    args = dict(entity_kind="market", entity_codes=["000001.SH"])
    inspected = run(anatomy_db, operation="inspect_history", preview_limit=1, **args)
    assert inspected["rows"][-1]["trade_date"] == "2026-01-29"
    assert inspected["rows"][-1]["market"]["cycle_stage_source"] == "fixture-v1"
    assert "Not theme lifecycle" in inspected["rows"][-1]["stage_semantics"]
    assert inspected["rows"][-1]["market"]["market_stage_source"] == "local:stage-lr-v1"
    assert "非倍数" in inspected["rows"][-1]["market_units"]
    _, details = _project(_result(inspected, result_ref="run/history-query-example.json"))
    assert any(r.get("market", {}).get("market_stage_source") == "local:stage-lr-v1" for r in details)
    assert any(r.get("market", {}).get("market_stage_confidence") == 0.961 for r in details)
    assert all(not r.get("projection_status") for r in details)
    calculated = run(
        anatomy_db,
        operation="compute_history",
        features=[
            "return_pct",
            "max_drawdown_pct",
            "advancers_mean",
            "limit_up_mean",
            "limit_down_mean",
        ],
        **args,
    )
    assert calculated["rows"][0]["features"]["advancers_mean"] == 1600
    assert (
        calculated["feature_definitions"]["max_drawdown_pct"]["version"]
        == "history-anatomy-features-v1"
    )
    assert calculated["pit_grade"] == "hindsight_reconstruction"


def test_market_analogues_exclude_reference_and_ignore_later_facts(anatomy_db):
    args = dict(
        operation="find_analogues",
        entity_kind="market",
        entity_codes=["000001.SH"],
        start="2026-01-20",
        end="2026-01-22",
        search_start="2026-01-05",
        search_end="2026-01-19",
        window_days=3,
        step_days=1,
        features=[
            "return_pct",
            "amount_vs_prior_mean",
            "advancers_mean",
            "limit_up_mean",
        ],
        match_mode="trigger_only",
    )
    before = run(anatomy_db, **args)
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(
            "UPDATE fact_market_daily SET sh_index_pct_chg=99, advancers=9999 WHERE trade_date>'2026-01-22'"
        )
    after = run(anatomy_db, **args)
    assert before["query_id"] == after["query_id"]
    assert before["rows"] == after["rows"]
    assert len(before["rows"]) == 13
    assert all(row["overlap_cluster"] == "overlap-1" for row in before["rows"])
    assert before["promotion_eligible"] is False


def test_trace_signal_features_peak_confirmation_and_actual_launch_members(anatomy_db):
    result = run(anatomy_db, preview_limit=1)
    signal = record(result, "launch_signal", "A.FP")
    assert signal["signal_date"] == signal["signal_known_as_of"] == "2026-01-10"
    assert signal["end"] == "2026-01-10"
    assert signal["features"]["return_pct"] == pytest.approx(5)
    assert signal["features"]["amount_vs_prior_mean"] == pytest.approx(1)
    path = record(result, "price_path", "A.FP")
    assert path["peak_date"] == "2026-01-12"
    assert path["peak_gain_pct"] == pytest.approx(15.7625)
    assert path["confirmation_date"] == "2026-01-15"
    assert path["peak_status"] == "drawdown_confirmed_retrospectively"
    assert path["peak_known_as_of"] == "2026-01-29"
    assert path["confirmation_known_as_of"] == "2026-01-29"
    leaders = [r for r in result["rows"] if r["record_kind"] == "member_leader"]
    assert [r["entity_code"] for r in leaders] == ["S1", "S2"]
    assert leaders[0]["features"]["return_pct"] == pytest.approx(33.1)
    assert leaders[0]["rank"] == 1
    assert leaders[0]["path_anchor"] == "sector_signal_not_stock_launch"
    assert leaders[0]["peak_date"] == "2026-01-12"
    assert result["total_matched"] > result["returned_count"] == 1
    assert result["truncated"]
    assert "history-anatomy-v1" in result["definition_refs"][-1]
    assert all(not result[key] for key in ("decision_eligible", "promotion_eligible"))


def test_succession_retains_rejected_pairs_not_causal(anatomy_db):
    result = run(anatomy_db)
    link = record(result, "sector_succession", "B.FP")
    assert link["source_sector"] == "A.FP"
    assert link["lag_trading_days"] == 3
    assert link["succession_status"] == "candidate_not_causal"
    assert link["causal_status"] == "not_established"
    assert (
        link["evidence"]["source_return_pct"]
        < 0
        < link["evidence"]["target_return_pct"]
    )
    rejected = record(result, "sector_succession", "A.FP")
    assert rejected["succession_status"] == "outside_succession_window"
    assert result["universe"]["record_counts"]["sector_succession"] == 2


def test_signal_unchanged_by_future_but_peak_needs_confirmation(anatomy_db):
    early = run(anatomy_db, end="2026-01-12")
    late = run(anatomy_db)
    assert record(early, "launch_signal", "A.FP") == record(
        late, "launch_signal", "A.FP"
    )
    p = record(early, "price_path", "A.FP")
    assert p["peak_status"] == "window_peak_unconfirmed"
    assert p["confirmation_date"] is None
    assert record(early, "sector_succession", "B.FP")["succession_status"] == "immature"


def test_missing_price_fails_closed_and_missing_member_is_not_zero(anatomy_db):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(
            "DELETE FROM fact_sector_daily WHERE sector_ts_code='B.FP' AND trade_date='2026-01-16'"
        )
        con.execute(
            "UPDATE fact_stock_daily SET pct_chg=NULL WHERE stock_ts_code='S1' AND trade_date='2026-01-11'"
        )
    result = run(anatomy_db)
    assert record(result, "price_path", "B.FP")["peak_status"] == "unverifiable"
    missing = record(result, "member_leader", "S1")
    assert missing["features"]["return_pct"] is None and missing["rank"] is None
    assert missing["path_status"] == "missing"
    assert "feature:return_pct:missing" in result["gaps"]


def test_duplicate_membership_cannot_choose_a_winner(anatomy_db):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(
            "INSERT INTO fact_sector_stock_daily SELECT * FROM fact_sector_stock_daily WHERE trade_date='2026-01-10' AND stock_ts_code='S1'"
        )
    leader = record(run(anatomy_db), "member_leader", "S1")
    assert leader["membership_status"] == "ambiguous"
    assert leader["rank"] is None
    assert leader["peak_date"] is None


def test_signal_gap_not_observed_and_insufficient_history_distinct(anatomy_db):
    short = run(anatomy_db, end="2026-01-09")
    assert (
        record(short, "launch_signal", "A.FP")["signal_status"]
        == "insufficient_history"
    )
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET diff_ratio=0 WHERE sector_ts_code='A.FP'"
        )
        con.execute(
            "UPDATE fact_sector_daily SET diff_ratio=NULL WHERE sector_ts_code='B.FP' AND trade_date='2026-01-11'"
        )
    result = run(anatomy_db)
    assert record(result, "launch_signal", "A.FP")["signal_status"] == "not_observed"
    assert (
        record(result, "launch_signal", "B.FP")["signal_status"]
        == "observed_with_earlier_gaps"
    )


def test_stock_signal_uses_own_prior_volume_not_future_winner(anatomy_db):
    result = run(anatomy_db, entity_kind="stock", entity_codes=["S1", "S2"])
    assert record(result, "launch_signal", "S1")["signal_date"] == "2026-01-10"
    assert record(result, "launch_signal", "S2")["signal_status"] == "not_observed"
    assert {r["record_kind"] for r in result["rows"]} == {"launch_signal", "price_path"}


def test_new_formulas_are_hand_calculable():
    days = [1, 2, 3]
    rows = [
        dict(trade_date=d, pct_chg=p, amount=a)
        for d, p, a in ((1, 10, 100), (2, -20, 200), (3, 5, 450))
    ]
    values, _ = compute_features(
        (
            "return_pct",
            "max_drawdown_pct",
            "up_day_share",
            "amount_vs_prior_mean",
            "amount_share_change_pp",
        ),
        days,
        rows,
        market=[dict(trade_date=d, total_amount=1000) for d in days],
    )
    assert values == pytest.approx(
        dict(
            return_pct=-7.6,
            max_drawdown_pct=20,
            up_day_share=2 / 3,
            amount_vs_prior_mean=3,
            amount_share_change_pp=35,
        )
    )


@pytest.mark.parametrize(
    "overrides",
    [
        dict(entity_kind="market", entity_codes=["000002.SH"]),
        dict(entity_kind="market"),
        dict(entity_kind="stock", features=["advancers_mean"]),
        dict(features=["limit_down_mean"]),
    ],
)
def test_unsupported_entity_feature_or_trace_combinations_rejected(overrides):
    args = dict(
        operation="trace_history",
        start="2026-01-05",
        end="2026-01-29",
        entity_codes=["A.FP"],
    )
    with pytest.raises(ValueError):
        HistoryQuerySpec.from_arguments(dict(args, **overrides))


def test_no_automatic_scope_expansion_or_future_read(anatomy_db):
    result = run(anatomy_db, start="2026-01-10", end="2026-01-20")
    assert record(result, "launch_signal", "A.FP")["signal_status"] == "not_observed"
    assert all(
        "2026-01-10" <= r["trade_date"] <= "2026-01-20"
        for rows in result["inputs"].values()
        for r in rows
    )
    with pytest.raises(ValueError, match="cutoff"):
        run(anatomy_db, end="2026-01-30")


@pytest.mark.parametrize(
    "question",
    [
        "当前市场处于什么阶段，与哪些历史阶段相似？",
        "当时哪些个股走强，启动到见顶的形态如何？",
        "板块见顶后哪些板块接力、有什么证据？",
        "不同板块如何启动，有哪些共同且可计算的特征？",
    ],
)
def test_user_questions_reach_real_frame_and_authorized_history_tool(
    tmp_path, question
):
    from intelligence.tests.test_historical_research_episode import _registry

    registry, context, _ = _registry(tmp_path, question)
    assert context.history_intent is not None
    result = registry.execute(
        "history_query",
        dict(
            operation="inspect_history",
            start="2026-08-03",
            end="2026-08-04",
            entity_kind="market",
            entity_codes=["000001.SH"],
        ),
        context=context,
        step_id="market",
    )
    assert result.trace.status == "success"


def test_anatomy_followup_preserves_exclusive_dates_and_cancel():
    previous = HistoryIntent(
        "retrospective_discovery", "2026-01-05", "2026-01-29", strict_window=True
    )
    assert inherit_history_followup("那它们见顶后谁接力？", previous) == previous
    assert inherit_history_followup("不要历史研究", previous) is None
    assert infer_history_intent("什么是启动信号？") is None


def test_registry_projection_and_finish_recognize_trace_as_evidence(tmp_path):
    from intelligence.tests.test_historical_research_episode import _registry
    from intelligence.services.historical_research.research import assess_history_finish
    from tests.test_history_model_projection import _project

    registry, context, session = _registry(tmp_path)
    observed = registry.execute(
        "history_query",
        dict(
            operation="trace_history",
            start="2026-08-03",
            end="2026-08-04",
            entity_codes=["A.FP"],
        ),
        context=context,
        step_id="trace",
    )
    assert observed.trace.status == "success"
    ref = observed.telemetry["result_ref"]
    artifact = session.read(ref)
    assert artifact["rows"][0]["signal_status"] == "insufficient_history"
    _, details = _project(observed)
    assert any(r.get("signal_status") == "insufficient_history" for r in details)
    result = assess_history_finish(
        {
            "history_research": dict(
                purpose=context.history_intent.purpose,
                result_refs=[ref],
                claim_level="single_case",
                research_only=True,
                decision_eligible=False,
                promotion_eligible=False,
            )
        },
        context=context,
    )
    assert result.claim_level == "single_case"


def test_full_trace_survives_actual_model_detail_budget(anatomy_db):
    from intelligence.services.historical_research.episode import _result
    from tests.test_history_model_projection import _project

    payload = run(anatomy_db)
    frozen = deepcopy(payload)
    _, details = _project(_result(payload, result_ref="run/history-query-example.json"))
    assert any(
        r.get("peak_status") == "drawdown_confirmed_retrospectively" for r in details
    )
    assert any(r.get("succession_status") == "candidate_not_causal" for r in details)
    assert any(r.get("path_sample") for r in details)
    assert any(r.get("membership_date") == "2026-01-10" for r in details)
    assert all(not r.get("projection_status") for r in details)
    assert payload == frozen


def test_rank_history_discovers_population_without_prefilter_and_keeps_missing(
    anatomy_db,
):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(
            "UPDATE fact_stock_daily SET pct_chg=NULL WHERE stock_ts_code='S1' AND trade_date='2026-01-10'"
        )
    ranked = run(
        anatomy_db,
        operation="rank_history",
        entity_kind="stock",
        entity_codes=[],
        end="2026-01-12",
        preview_limit=1,
    )
    assert ranked["total_matched"] == 3
    assert ranked["preview"][0]["entity_code"] == "FUTURE"
    assert ranked["rows"][-1]["entity_code"] == "S1"
    assert ranked["rows"][-1]["rank"] is None
    assert ranked["universe"]["missing_unranked"] == 1
    assert ranked["rows"][0]["selection_mode"] == "posthoc_ranked_observed_universe"
    assert ranked["returned_count"] == 1


def test_rank_and_trace_obey_same_row_budget_cancellation_and_read_only(
    anatomy_db, monkeypatch
):
    import intelligence.services.historical_research.query as module

    before = anatomy_db.read_bytes()
    monkeypatch.setattr(module, "MAX_INPUT_ROWS", 3)
    for operation in ("trace_history", "rank_history"):
        with pytest.raises(ValueError, match="row limit"):
            run(anatomy_db, operation=operation)
    assert anatomy_db.read_bytes() == before
    spec = HistoryQuerySpec.from_arguments(
        dict(
            operation="trace_history",
            start="2026-01-05",
            end="2026-01-29",
            entity_codes=["A.FP"],
        )
    )
    with pytest.raises(module.HistoryQueryCancelled):
        HistoryQuery(anatomy_db).run(
            spec,
            information_cutoff=InformationCutoff(date(2026, 1, 29), "requested"),
            deadline=ResearchDeadline.from_timeout(10),
            is_cancelled=lambda: True,
        )


def test_full_registry_restores_pages_and_enforces_scope(tmp_path):
    from intelligence.tests.test_historical_research_episode import _registry
    from intelligence.services.query_understanding import understand_query
    from intelligence.services.episode_tools import build_episode_registry

    question = "只研究2026-08-03到2026-08-04这一波农业怎么走出来的"
    _, context, session = _registry(tmp_path, question)
    registry = build_episode_registry(
        understand_query(question).task_frame,
        context,
        finance_root=tmp_path,
        knowledge_wiki=tmp_path / "missing-wiki",
        history_session=session,
    )
    args = dict(
        operation="trace_history",
        start="2026-08-03",
        end="2026-08-04",
        entity_codes=["A.FP"],
    )
    result = registry.execute("history_query", args, context=context, step_id="trace")
    assert result.trace.status == "success"
    ref = result.telemetry["result_ref"]
    reread = registry.execute(
        "read_history_result",
        dict(result_ref=ref, offset=0, limit=1),
        context=context,
        step_id="page",
    )
    assert reread.trace.status == "success"
    assert reread.telemetry["operation"] == "trace_history"
    for op in ("trace_history", "rank_history"):
        with pytest.raises(ValueError, match="outside_authorized_scope"):
            registry.execute(
                "history_query",
                dict(args, operation=op, start="2026-08-02"),
                context=context,
                step_id=op,
            )


def test_episode_model_observes_launch_before_selecting_next_query(tmp_path):
    """Scripted model, real Episode/tool/artifact path; not LLM quality evaluation."""
    from intelligence.tests.test_historical_research_episode import _registry
    from intelligence.services.query_understanding import understand_query
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelTurn, ModelToolCall

    registry, context, session = _registry(tmp_path)
    question = session.store.load_run(session.run_id).question
    outputs = [item.output_id for item in context.contract.required_outputs]

    class Model:
        calls = 0
        seen = False

        def complete(self, *, messages, tools, timeout):
            self.calls += 1
            assert self.calls <= 4
            observed = [m for m in messages if m.get("role") == "tool"]
            if not observed:
                return ModelTurn("", (ModelToolCall("trace", "history_query", dict(operation="trace_history", start="2026-08-03", end="2026-08-04", entity_codes=["A.FP"])),), "scripted", "")
            if len(observed) == 1:
                observation = json.loads(observed[-1]["content"])
                details = [json.loads(item["detail"].replace('\\"', '"')) for item in observation["evidence"]]
                self.seen = any(r.get("signal_status") == "insufficient_history" for r in details)
                assert self.seen
                return ModelTurn("", (ModelToolCall("fallback-rank", "history_query", dict(operation="rank_history", start="2026-08-03", end="2026-08-04", entity_codes=[])),), "scripted", "")
            gap = "窗口不足5日预热，不能认定启动；仅保留事后排名，尚无完整历史验证。"
            return ModelTurn(json.dumps(dict(status="partial", draft=gap, gaps=[gap], bindings=[dict(output_id=output, evidence_hashes=[], gap=gap) for output in outputs]), ensure_ascii=False), (), "scripted", "")

    model = Model()
    outcome = ContinuousAgentEpisode(model).run(task_frame=understand_query(question).task_frame, context=context, registry=registry)
    assert model.seen
    assert outcome.status == "partial"
    assert outcome.stop_reason == "model_finish"
    assert [session.read(ref)["spec"]["operation"] for ref in session.refs] == ["trace_history", "rank_history"]


def test_workbench_turn_controller_routes_question_to_history(tmp_path, monkeypatch):
    """Real Workbench run_turn -> controller; stop before model/adapter side effects."""
    from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
    from intelligence.services.conversation_store import ConversationStore
    from intelligence.services.run_store import RunStore
    from intelligence.services.turn_controller import decide_turn

    class Reached(BaseException):
        pass

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    question = "当前市场处于什么阶段，与哪些历史阶段相似？"
    store = ConversationStore("history-test", root=tmp_path / "conversations")
    runs = RunStore("history-test", root=tmp_path / "runs")
    conversation = store.create_conversation()
    run = runs.create_run(question, "ask", session_id=conversation.conversation_id)
    store.append_message(
        conversation.conversation_id, "user", question, run_id=run.run_id
    )
    assistant = store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="running",
        run_id=run.run_id,
    )
    decisions = []

    def controller(raw, **kwargs):
        decision = decide_turn(
            raw, **kwargs, llm_complete=lambda _: (None, None, "offline probe")
        )
        decisions.append(decision)
        raise Reached

    runtime = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=store,
        run_store=runs,
        turn_controller_fn=controller,
    )
    with pytest.raises(Reached):
        runtime.run_turn(
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            assistant_message_id=assistant.message_id,
            query=question,
            skill_mode="auto",
            selected_skill_ids=[],
        )
    assert decisions[0].task_frame.history_intent.purpose == "historical_comparison"
    assert decisions[0].lane != "clarify"


def test_probe_script_preserves_original_and_labels_projection_limit(anatomy_db, tmp_path):
    from scripts.probe_history_queries import main

    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps({"information_cutoff": "2026-01-29", "queries": {
        "trace": {"operation": "trace_history", "start": "2026-01-05", "end": "2026-01-29", "entity_codes": ["A.FP", "B.FP"]}
    }}))
    output = tmp_path / "output"
    assert main(["--db", str(anatomy_db), "--recipe", str(recipe), "--output", str(output)]) == 0
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["results"]["trace"]["model_omissions"] == []
    assert receipt["code_sha256"]
    assert (output / "trace.json").is_file()
    with pytest.raises(FileExistsError):
        main(["--db", str(anatomy_db), "--recipe", str(recipe), "--output", str(output)])


def test_new_artifacts_have_independent_arithmetic(
    anatomy_db, tmp_path
):
    from scripts.audit_historical_research_artifacts import audit_artifact

    for kind in ("market", "sector"):
        payload = run(
            anatomy_db,
            entity_kind=kind,
            entity_codes=["000001.SH"] if kind == "market" else ["A.FP"],
            operation="compute_history" if kind == "market" else "trace_history",
        )
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        receipt = audit_artifact(path)
        assert receipt["errors"] == []
        assert receipt["result"] in {"checked", "partial"}
        assert receipt["calculation_checks"]
