from dataclasses import replace

import pytest

from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import TaskFrame
from intelligence.services.episode_factory import build_episode_context


@pytest.mark.parametrize(
    "question",
    [
        "这一波农业是怎么走出来的？",
        "事后复盘人形机器人，发现强势股特征",
        "之前有没有类似情况？找找失败案例",
    ],
)
def test_history_semantics_survive_frame_and_context(question):
    frame = understand_query(question).task_frame
    assert frame.history_intent is not None
    restored = TaskFrame.from_dict(frame.to_dict())
    assert restored == frame
    context = build_episode_context(frame, task_id="history-test")
    assert context.history_intent == frame.history_intent
    assert "finance_query" in context.contract.allowed_capabilities
    assert frame.question_type != "dated_market_review"


def test_normal_daily_question_does_not_authorize_history():
    frame = understand_query("今天市场怎么样").task_frame
    assert frame.history_intent is None
    assert build_episode_context(frame, task_id="daily").history_intent is None


def test_history_scope_cannot_be_supplied_as_unchecked_serialized_dict():
    frame = understand_query("这一波农业怎么走出来的").task_frame
    value = frame.to_dict()
    value["history_intent"]["scope"] = "all_files"
    assert TaskFrame.from_dict(value) is None


def test_legacy_frame_roundtrip():
    frame = understand_query("今天市场怎么样").task_frame
    value = frame.to_dict()
    value.pop("history_intent", None)
    assert TaskFrame.from_dict(value) == frame
    assert replace(frame, history_intent=None).task_frame_hash == frame.task_frame_hash


@pytest.mark.parametrize(
    "question",
    [
        "给我解释一下题材炒作的特征",
        "什么是强势股，强势股有什么特征？",
        "过去两次回答类似，重新解释一下",
    ],
)
def test_definition_and_conversation_comments_do_not_gain_history_scope(question):
    assert understand_query(question).task_frame.history_intent is None


def test_natural_named_wave_reaches_research_control_without_asking_for_subject():
    from intelligence.services.turn_controller import decide_turn
    from intelligence.runtime.turn_control_core import project_turn_decision

    decision = decide_turn(
        "这一波农业是怎么走出来的？", llm_complete=lambda _: (None, None, "offline")
    )
    control = project_turn_decision(decision, task_frame=decision.task_frame)
    assert control.terminal_kind == "research"
    assert decision.subject == "农业"
    assert "finance_query" in control.capabilities


def test_two_comparison_anchors_are_not_a_reversed_range():
    frame = understand_query(
        "回溯2026-09-07这波农业行情，与2026-08-01那波相似吗"
    ).task_frame
    assert frame.history_intent is not None
    assert frame.history_intent.requested_start is None


def _history_root(tmp_path):
    import duckdb

    path = tmp_path / "db" / "market_feature_store.duckdb"
    path.parent.mkdir()
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code TEXT, sector_name TEXT, pct_chg DOUBLE, amount DOUBLE, diff_ratio DOUBLE)"
        )
        con.execute(
            "INSERT INTO fact_sector_daily VALUES ('2026-08-03','A.FP','农业',1,100,15),('2026-08-04','A.FP','农业',2,130,30)"
        )
        con.execute(
            "CREATE TABLE fact_market_daily (trade_date DATE, sh_index_pct_chg DOUBLE)"
        )
        con.execute(
            "INSERT INTO fact_market_daily VALUES ('2026-08-03',0),('2026-08-04',0)"
        )
    return path


def _registry(tmp_path, question="这一波农业是怎么走出来的？"):
    from intelligence.services.run_store import RunStore
    from intelligence.services.historical_research.episode import (
        HistorySession,
        history_tool_specs,
    )
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.services.research_contract import InformationCutoff
    from datetime import date

    path = _history_root(tmp_path)
    store = RunStore("history-test", root=tmp_path / "runs")
    run = store.create_run(question, "ask", session_id="conversation-history")
    session = HistorySession(store, run.run_id, "conversation-history")
    frame = understand_query(question).task_frame
    context = build_episode_context(
        frame,
        task_id=run.run_id,
        capabilities=("finance_query",),
        information_cutoff=InformationCutoff(date(2026, 9, 7), "requested"),
    )
    registry = ResearchToolRegistry(
        tuple(history_tool_specs(frame, context, path, session))
    )
    return registry, context, session


def test_registered_query_persists_complete_result_and_reads_by_controlled_ref(
    tmp_path,
):
    registry, context, session = _registry(tmp_path)
    result = registry.execute(
        "history_query",
        {
            "operation": "inspect_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
            "preview_limit": 1,
        },
        context=context,
        step_id="query",
    )
    assert result.trace.status == "success"
    ref = result.telemetry["result_ref"]
    payload = session.read(ref)
    assert len(payload["rows"]) == 2
    assert payload["returned_count"] == 1
    assert payload["pending_sources"][0]["status"] == "pending_sync"
    second = registry.execute(
        "read_history_result",
        {"result_ref": ref, "offset": 1, "limit": 1},
        context=context,
        step_id="read",
    )
    assert "2026-08-04" in second.evidence[-1].detail
    with pytest.raises(ValueError, match="outside this conversation"):
        session.read("another-run/history-query-any.json")


def test_user_exclusive_window_stops_execution_before_reading_database(
    tmp_path, monkeypatch
):
    registry, context, session = _registry(
        tmp_path, "只研究2026-08-01到2026-08-31这波农业行情怎么走出来的"
    )
    from intelligence.services.historical_research.query import HistoryQuery

    def forbidden(*args, **kwargs):
        pytest.fail("outside-scope query reached the engine")

    monkeypatch.setattr(HistoryQuery, "run", forbidden)
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        registry.execute(
            "history_query",
            {
                "operation": "inspect_history",
                "start": "2024-01-01",
                "end": "2024-01-10",
            },
            context=context,
            step_id="rejected",
        )
    assert context.history_results == []


def test_registry_requires_both_history_intent_and_finance_capability(tmp_path):
    from intelligence.services.historical_research.episode import history_tool_specs

    frame = understand_query("这一波农业怎么走出来的").task_frame
    context = build_episode_context(
        frame, task_id="blocked", capabilities=("kb_search",)
    )
    context = replace(
        context, contract=replace(context.contract, allowed_capabilities=("kb_search",))
    )
    assert history_tool_specs(frame, context, tmp_path / "absent.duckdb", None) == []


def test_real_app_factory_injects_same_run_writer_only_for_history(
    tmp_path, monkeypatch
):
    from intelligence.api import app as api
    from intelligence.services.historical_research.episode import history_tool_specs
    from intelligence.services.research_tool_registry import ResearchToolRegistry

    registry, context, session = _registry(tmp_path)
    received = []

    def compose(frame, ctx, **kwargs):
        received.append(kwargs)
        return ResearchToolRegistry(
            tuple(
                history_tool_specs(
                    frame,
                    ctx,
                    tmp_path / "db" / "market_feature_store.duckdb",
                    kwargs.get("history_session"),
                )
            )
        )

    monkeypatch.setattr(api, "build_episode_registry", compose)
    factory = api._memory_bound_registry_factory(
        None,
        history_session=api._history_session_for_run(
            session.store, session.run_id, session.conversation_id
        ),
    )
    assembled = factory(understand_query("这一波农业怎么走出来的").task_frame, context)
    assert {"history_query", "read_history_result", "save_history_research"} <= set(
        assembled.names()
    )
    assert received[-1]["history_session"].run_id == session.run_id
    frame = understand_query("今天市场怎么样").task_frame
    factory(frame, build_episode_context(frame, task_id="normal"))
    assert "history_session" not in received[-1]


def test_elliptical_history_followup_inherits_and_can_change_window():
    from intelligence.services.turn_controller import decide_turn

    def offline(_):
        return None, None, "offline"

    first = decide_turn("这一波农业怎么走出来的", llm_complete=offline)
    previous = first.turn_intent
    for query in ("以前有没有类似？", "那以前呢？"):
        followup = decide_turn(
            query, previous_intent=previous, previous_turn_id="t1", llm_complete=offline
        )
        assert followup.task_frame.history_intent.purpose == "historical_comparison"
        assert followup.subject == "农业"
    narrowed = decide_turn(
        "只看2025-01-01到2025-03-31",
        previous_intent=previous,
        previous_turn_id="t1",
        llm_complete=offline,
    )
    assert narrowed.task_frame.history_intent.requested_start == "2025-01-01"
    assert narrowed.task_frame.history_intent.strict_window is True
    unrelated = decide_turn(
        "解释一下市盈率",
        previous_intent=previous,
        previous_turn_id="t1",
        llm_complete=offline,
    )
    assert unrelated.task_frame.history_intent is None


def test_saved_case_cannot_restart_v1_to_erase_failure_and_revises_across_turns(
    tmp_path,
):
    from intelligence.services.historical_research.episode import (
        HistorySession,
        history_tool_specs,
    )
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from copy import deepcopy

    registry, context, session = _registry(tmp_path)
    result = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
        },
        context=context,
        step_id="query",
    )
    query_ref = result.telemetry["result_ref"]
    query_id = result.telemetry["query_id"]
    draft = {
        "question": "农业如何形成",
        "purpose": "retrospective_discovery",
        "entity_ids": ["A.FP"],
        "source_refs": [query_id],
        "hypotheses": [
            {
                "hypothesis_id": "h1",
                "statement": "双红可能先行",
                "source_case_refs": [query_ref],
                "failed_sample_refs": [query_id],
            }
        ],
    }
    first = registry.execute(
        "save_history_research", {"draft": draft}, context=context, step_id="save"
    )
    ref = first.telemetry["result_ref"]
    retry = registry.execute(
        "save_history_research", {"draft": draft}, context=context, step_id="retry"
    )
    assert retry.telemetry["result_ref"] == ref
    erased = dict(draft, hypotheses=[])
    with pytest.raises(ValueError, match="requires_previous"):
        registry.execute(
            "save_history_research", {"draft": erased}, context=context, step_id="erase"
        )
    run2 = session.store.create_run(
        "再看反例", "ask", session_id=session.conversation_id
    )
    session2 = HistorySession(session.store, run2.run_id, session.conversation_id)
    frame = understand_query("找找历史失败案例").task_frame
    context2 = build_episode_context(frame, task_id=run2.run_id)
    reg2 = ResearchToolRegistry(
        tuple(
            history_tool_specs(
                frame,
                context2,
                tmp_path / "db" / "market_feature_store.duckdb",
                session2,
            )
        )
    )
    revised = deepcopy(session.read(ref)["draft"])
    revised.pop("case_id")
    revised.update(revision=2, parent_revision=1)
    revised["hypotheses"][0].update(
        version=2,
        parent_version=1,
        statement="双红先行假设被反例削弱",
        status="weakened",
    )
    saved = reg2.execute(
        "save_history_research",
        {"draft": revised, "previous_result_ref": ref},
        context=context2,
        step_id="revise",
    )
    stored = session2.read(saved.telemetry["result_ref"])["draft"]
    assert stored["hypotheses"][0]["failed_sample_refs"] == [query_id]
    assert session.read(ref)["draft"]["revision"] == 1


def test_old_and_latest_same_conversation_refs_remain_readable_after_20_runs(tmp_path):
    from intelligence.services.historical_research.episode import HistorySession

    registry, context, session = _registry(tmp_path)
    refs = []
    for i in range(22):
        run = session.store.create_run(
            str(i), "ask", session_id=session.conversation_id
        )
        s = HistorySession(session.store, run.run_id, session.conversation_id)
        refs.append(s.save("query", {"query_id": str(i), "rows": []}))
    newest = HistorySession(session.store, run.run_id, session.conversation_id)
    assert newest.read(refs[0])["query_id"] == "0"
    assert newest.read(refs[-1])["query_id"] == "21"


@pytest.mark.parametrize(
    "question",
    [
        "只研究2026-08-31到2026-08-01这一波农业怎么走出来的",
        "只研究2026-02-31到2026-03-03这一波农业怎么走出来的",
    ],
)
def test_invalid_explicit_windows_clarify_instead_of_expanding_scope(question):
    from intelligence.services.turn_controller import decide_turn

    decision = decide_turn(question, llm_complete=lambda _: (None, None, "offline"))
    assert decision.lane == "clarify"
    assert decision.task_frame.history_intent.window_error


def test_reading_later_artifact_under_earlier_cutoff_does_not_project_any_evidence(
    tmp_path,
):
    from datetime import date
    from intelligence.services.research_contract import InformationCutoff
    from intelligence.services.historical_research.episode import history_tool_specs
    from intelligence.services.research_tool_registry import ResearchToolRegistry

    registry, context, session = _registry(tmp_path)
    observed = registry.execute(
        "history_query",
        {
            "operation": "inspect_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
        },
        context=context,
        step_id="query",
    )
    earlier = replace(
        context,
        information_cutoff=InformationCutoff(date(2026, 8, 1), "requested"),
        history_results=[],
    )
    frame = understand_query("站在2026-08-01收盘，这一波农业怎么走出来的").task_frame
    reader = ResearchToolRegistry(
        tuple(
            history_tool_specs(
                frame, earlier, tmp_path / "db" / "market_feature_store.duckdb", session
            )
        )
    )
    with pytest.raises(ValueError, match="after_information_cutoff"):
        reader.execute(
            "read_history_result",
            {"result_ref": observed.telemetry["result_ref"]},
            context=earlier,
            step_id="old",
        )
    assert earlier.history_results == []


def test_plain_finance_query_cannot_bypass_exclusive_history_window(tmp_path):
    from intelligence.services.episode_tools import build_episode_registry

    registry, context, session = _registry(
        tmp_path, "只研究2026-08-04到2026-08-04这波农业行情怎么走出来的"
    )
    frame = understand_query(
        "只研究2026-08-04到2026-08-04这波农业行情怎么走出来的"
    ).task_frame
    full = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path,
        knowledge_wiki=tmp_path / "missing-wiki",
        history_session=session,
    )
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        full.execute(
            "finance_query",
            {
                "dataset": "sector_daily",
                "dimensions": ["trade_date", "sector_ts_code"],
                "metrics": ["pct_chg"],
                "time_range": {"start": "2026-08-03", "end": "2026-08-03"},
            },
            context=context,
            step_id="outside",
        )


def test_precreated_second_session_cannot_reset_case_lineage(tmp_path):
    from intelligence.services.historical_research.episode import (
        HistorySession,
        history_tool_specs,
    )
    from intelligence.services.research_tool_registry import ResearchToolRegistry

    registry, context, session = _registry(tmp_path)
    run2 = session.store.create_run(
        "这一波农业是怎么走出来的？", "ask", session_id=session.conversation_id
    )
    second = HistorySession(session.store, run2.run_id, session.conversation_id)
    frame = understand_query("这一波农业是怎么走出来的？").task_frame
    context2 = build_episode_context(frame, task_id=run2.run_id)
    reg2 = ResearchToolRegistry(
        tuple(
            history_tool_specs(
                frame, context2, tmp_path / "db" / "market_feature_store.duckdb", second
            )
        )
    )
    draft = {
        "question": "农业研究",
        "purpose": "retrospective_discovery",
        "entity_ids": ["A.FP"],
        "source_refs": [],
        "open_questions": ["量价信号是否重复出现"],
    }
    registry.execute(
        "save_history_research", {"draft": draft}, context=context, step_id="one"
    )
    with pytest.raises(ValueError, match="requires_previous"):
        reg2.execute(
            "save_history_research",
            {"draft": dict(draft, open_questions=[])},
            context=context2,
            step_id="two",
        )


@pytest.mark.parametrize(
    "question", ["不要再找反例，给我解释市盈率", "不做历史行情复盘，只解释涨跌幅怎么算"]
)
def test_explicit_stop_does_not_reauthorize_historical_research(question):
    from intelligence.services.turn_controller import decide_turn

    def offline(_):
        return None, None, "offline"

    previous = decide_turn("这一波农业怎么走出来的", llm_complete=offline).turn_intent
    result = decide_turn(
        question, previous_intent=previous, previous_turn_id="old", llm_complete=offline
    )
    assert result.task_frame.history_intent is None
    assert result.subject != "农业"


def test_clarification_repairs_date_error_without_changing_subject():
    from intelligence.services.task_frame import resolve_task_frame_clarification

    frame = understand_query(
        "只研究2026-08-31到2026-08-01这一波农业怎么走出来的"
    ).task_frame
    repaired = resolve_task_frame_clarification(frame, "2026-08-01到2026-08-31")
    assert repaired.history_intent.window_error is None
    assert repaired.history_intent.requested_start == "2026-08-01"
    assert repaired.subject == frame.subject


@pytest.mark.parametrize("question", ["不用L2继续复盘", "不用L2，继续复盘"])
def test_source_restriction_preserves_explicit_history_continuation(question):
    from intelligence.services.turn_controller import decide_turn

    def offline(_):
        return None, None, "offline"

    previous = decide_turn("这一波农业怎么走出来的", llm_complete=offline).turn_intent
    result = decide_turn(
        question, previous_intent=previous, previous_turn_id="old", llm_complete=offline
    )
    assert result.task_frame.history_intent == previous.history_intent
    assert result.subject == "农业"
