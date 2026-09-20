"""Same-window continuation through real controller/registry/RunStore seams.

Synthetic facts and scripted consumers are not a live-model acceptance run.
"""

from dataclasses import replace
from datetime import date
import json
from uuid import uuid4

import pytest

from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.historical_research.episode import HistorySession, history_tool_specs
from intelligence.services.historical_research.query import HistoryQuery, HistoryQuerySpec
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore
from tests.test_history_live_seams import FIRST, FOLLOWUPS, _decide
from tests.test_history_market_anatomy import anatomy_db as _anatomy_db


@pytest.fixture
def anatomy_db(tmp_path):
    return _anatomy_db.__wrapped__(tmp_path)


def _context(frame):
    return build_episode_context(
        frame, task_id=f"window-{uuid4().hex}", capabilities=("finance_query",),
        information_cutoff=InformationCutoff(date(2026, 9, 15), "requested"),
    )


def _tools(frame, context, path, session):
    return ResearchToolRegistry(tuple(history_tool_specs(frame, context, path, session)))


def _deliver(observation, context):
    # Direct registry tests explicitly emulate the successful message boundary;
    # scripted-loop tests below exercise the actual runtime acknowledgement.
    from intelligence.services.research_harness import FinanceResearchHarness

    harness = FinanceResearchHarness()
    projection = harness.project_tool_result(
        observation, evidence_so_far=observation.evidence, seen_prose=set())
    harness.acknowledge_tool_result(observation, projection, context=context)
    return observation


def _execute(registry, context, **args):
    return _deliver(registry.execute("history_query", args, context=context, step_id=uuid4().hex), context)


def _read(registry, context, ref, **page):
    return _deliver(registry.execute("read_history_result", dict(result_ref=ref, **page),
                                    context=context, step_id=uuid4().hex), context)


def _scenario(tmp_path, path):
    conversations = ConversationStore("window", root=tmp_path / "conversations")
    conversation = conversations.create_conversation()
    first = _decide(conversations, conversation, FIRST)
    runs = RunStore("window", root=tmp_path / "runs")
    run = runs.create_run(FIRST, "ask", session_id=conversation.conversation_id)
    session = HistorySession(runs, run.run_id, run.session_id)
    context = _context(first.task_frame)
    tools = _tools(first.task_frame, context, path, session)
    found = _execute(tools, context, operation="find_analogues", entity_kind="market",
                     entity_codes=["000001.SH"], start="2026-01-24", end="2026-01-29",
                     search_start="2026-01-05", search_end="2026-01-23", window_days=6,
                     step_days=6, features=["return_pct", "advancers_mean"], preview_limit=1)
    ref = found.telemetry["result_ref"]
    original = session.read(ref)
    decision = _decide(conversations, conversation, FOLLOWUPS[0], first.turn_intent, 1)
    current = runs.create_run(FOLLOWUPS[0], "ask", session_id=run.session_id)
    session2 = HistorySession(runs, current.run_id, run.session_id)
    context2 = _context(decision.task_frame)
    tools2 = _tools(decision.task_frame, context2, path, session2)
    return tools2, context2, session2, original, ref, conversations, conversation, decision


def _args(original, ref, **changes):
    row = original["rows"][0]
    return dict(dict(operation="rank_history", entity_kind="sector", entity_codes=[],
                     start=row["start"], end=row["end"], preview_limit=1,
                     window_ref={"result_ref": ref, "sample_id": row["sample_id"]}), **changes)


def test_real_controller_freezes_reference_policy_not_assistant_wording(tmp_path):
    store = ConversationStore("window", root=tmp_path)
    conv = store.create_conversation()
    previous = None
    for n, (question, source, extension) in enumerate(zip(
        (FIRST, *FOLLOWUPS), ("none", "analogue", "prior_analysis", "prior_analysis"),
        (False, False, True, False), strict=True,
    )):
        decision = _decide(store, conv, question, previous, n)
        intent = decision.task_frame.history_intent
        assert intent.analysis_window_source == source
        assert intent.allow_window_extension is extension
        assert type(intent).from_dict(intent.to_dict()) == intent
        previous = decision.turn_intent
    changed = _decide(store, conv, "继续，改用2026-02-01至2026-02-10观察窗复盘行情，范围与截止日不变。", previous, 4)
    assert changed.task_frame.history_intent.analysis_window_source == "none"
    assert not changed.task_frame.history_intent.allow_window_extension
    assert changed.task_frame.history_intent.requested_start == "2026-01-01"


def test_analogue_followup_cannot_silently_rank_the_recent_window(tmp_path, anatomy_db, monkeypatch):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    calls = []
    original_run = HistoryQuery.run

    def tracked(*args, **kwargs):
        calls.append(True)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(HistoryQuery, "run", tracked)
    with pytest.raises(ValueError, match="history_window_reference_required"):
        _execute(tools, context, operation="rank_history", entity_kind="stock",
                 start="2026-01-24", end="2026-01-29")
    assert calls == []
    assert context.history_results == []
    assert not [r for r in session.refs if r.startswith(session.run_id + "/")]


def test_source_must_be_consumed_and_sample_must_be_from_saved_candidates(tmp_path, anatomy_db):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    with pytest.raises(ValueError, match="history_window_source_not_read"):
        _execute(tools, context, **_args(original, ref))
    _read(tools, context, ref, limit=1)
    blocks = [json.loads(e.detail) for e in _read(tools, context, ref, limit=1).evidence]
    assert any(b.get("sample_id") == original["rows"][0]["sample_id"] for b in blocks)
    with pytest.raises(ValueError, match="history_window_sample_not_found"):
        _execute(tools, context, **_args(original, ref, window_ref={
            "result_ref": ref, "sample_id": original["reference"]["sample_id"]}))
    # A candidate outside the consumed page must first be explicitly paged in.
    with pytest.raises(ValueError, match="history_window_sample_not_read"):
        _execute(tools, context, **_args(original, ref, window_ref={
            "result_ref": ref, "sample_id": original["rows"][1]["sample_id"]}))
    assert not [r for r in session.refs if r.startswith(session.run_id + "/")]


def test_same_reference_window_binds_sector_stock_and_trace_without_changing_population(tmp_path, anatomy_db):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    before = anatomy_db.read_bytes()
    source_bytes = session.store.read_history_artifact(*session.refs[ref])
    _read(tools, context, ref, limit=1)
    results = []
    for kind in ("sector", "stock"):
        result = _execute(tools, context, **_args(original, ref, entity_kind=kind))
        saved = session.read(result.telemetry["result_ref"])
        assert saved["spec"]["window_ref"] == _args(original, ref)["window_ref"]
        assert saved["window_binding"]["start"] == original["rows"][0]["start"]
        assert saved["window_binding"]["end"] == original["rows"][0]["end"]
        assert saved["window_binding"]["relation"] == "same_window"
        assert saved["total_matched"] == (2 if kind == "sector" else 3)
        assert saved["returned_count"] == 1
        results.append(saved)
    traced = _execute(tools, context, **_args(original, ref, operation="trace_history", entity_codes=["A.FP", "B.FP"]))
    saved = session.read(traced.telemetry["result_ref"])
    assert saved["window_binding"]["root_query_id"] == original["query_id"]
    assert saved["window_binding"]["root_sample_id"] == original["rows"][0]["sample_id"]
    assert saved["spec"]["start"] == results[0]["spec"]["start"]
    assert saved["spec"]["end"] == results[1]["spec"]["end"]
    assert anatomy_db.read_bytes() == before
    assert session.store.read_history_artifact(*session.refs[ref]) == source_bytes


@pytest.mark.parametrize("change", [{"end": "2026-01-29"}, {"start": "2026-01-06"}])
def test_changed_window_is_rejected_before_db_and_not_silently_rewritten(tmp_path, anatomy_db, monkeypatch, change):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    # Deliberately derive mismatch from source so this does not depend on analogue ordering.
    args = _args(original, ref, operation="trace_history", entity_codes=["A.FP"], **change)
    if args["start"] == original["rows"][0]["start"] and "start" in change:
        args["start"] = original["rows"][0]["end"]
    calls = []
    original_run = HistoryQuery.run

    def tracked(*args, **kwargs):
        calls.append(True)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(HistoryQuery, "run", tracked)
    with pytest.raises(ValueError, match="history_window_mismatch"):
        _execute(tools, context, **args)
    assert calls == []
    assert len(context.history_results) == 1  # Only the successful source read.


def test_another_candidate_cannot_replace_the_selected_reference_mid_turn(tmp_path, anatomy_db):
    tools, context, _, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    _execute(tools, context, **_args(original, ref))
    second = original["rows"][1]
    with pytest.raises(ValueError, match="history_window_selection_conflict"):
        _execute(tools, context, **_args(original, ref, entity_kind="stock", start=second["start"], end=second["end"],
            window_ref={"result_ref": ref, "sample_id": second["sample_id"]}))


def test_old_intent_is_compatible_and_standalone_engine_cannot_skip_ref_resolution(tmp_path, anatomy_db):
    from intelligence.services.historical_research.intent import HistoryIntent
    from intelligence.services.research_contract import ResearchDeadline

    intent = HistoryIntent.from_dict({"purpose": "retrospective_discovery"})
    assert intent.analysis_window_source == "none"
    assert intent.allow_window_extension is False
    tools, context, _, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    spec = HistoryQuerySpec.from_arguments(_args(original, ref))
    with pytest.raises(ValueError, match="history_window_unresolved"):
        HistoryQuery(anatomy_db).run(spec, information_cutoff=context.information_cutoff,
                                    deadline=ResearchDeadline.from_timeout(10))


def test_explicit_extension_is_not_implied_by_authorized_end_or_cutoff(tmp_path, anatomy_db):
    tools, context, session, original, ref, store, conv, decision = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref))
    rank_ref = ranked.telemetry["result_ref"]
    follow = _decide(store, conv, FOLLOWUPS[1], decision.turn_intent, 2)
    run = session.store.create_run(FOLLOWUPS[1], "ask", session_id=session.conversation_id)
    next_session = HistorySession(session.store, run.run_id, session.conversation_id)
    next_context = _context(follow.task_frame)
    next_tools = _tools(follow.task_frame, next_context, anatomy_db, next_session)
    _read(next_tools, next_context, rank_ref)
    args = _args(original, ref, operation="trace_history", entity_codes=["A.FP", "B.FP"],
                 window_ref={"result_ref": rank_ref}, end="2026-01-29")
    extended = _execute(next_tools, next_context, **args)
    trace_ref = extended.telemetry["result_ref"]
    binding = next_session.read(trace_ref)["window_binding"]
    assert binding["relation"] == "extended_observation"
    assert binding["source_end"] == original["rows"][0]["end"]
    assert binding["end"] == "2026-01-29"
    # The delivered extended trace is a valid direct parent for another analysis
    # on the same root ranking window. Its source window is wider than the rank
    # original, but that direct-edge detail must not look like a root-window swap.
    # Read the saved trace original as the next direct parent, matching the
    # cross-turn workflow even though this direct test also delivered its query.
    _read(next_tools, next_context, trace_ref)
    continued = _execute(next_tools, next_context, **dict(
        args, entity_kind="stock", window_ref={"result_ref": trace_ref}))
    continued_binding = next_session.read(continued.telemetry["result_ref"])["window_binding"]
    assert continued_binding["root_query_id"] == binding["root_query_id"]
    assert continued_binding["root_sample_id"] == binding["root_sample_id"]
    assert (continued_binding["ranking_start"], continued_binding["ranking_end"]) == (
        binding["ranking_start"], binding["ranking_end"])
    assert continued_binding["source_query_id"] == next_session.read(trace_ref)["query_id"]
    assert (continued_binding["source_start"], continued_binding["source_end"]) == (
        binding["start"], binding["end"])
    with pytest.raises(ValueError, match="history_window_observation_conflict"):
        _execute(next_tools, next_context, **dict(args, end="2026-01-28"))
    # Observation extension leaves the original ranking interval available.
    same_rank = _execute(next_tools, next_context, **dict(
        args, operation="rank_history", end=original["rows"][0]["end"]))
    assert same_rank.trace.status == "success"
    # A later cutoff alone does not authorize extending a same-window comparison.
    strict_frame = replace(follow.task_frame, history_intent=replace(
        follow.task_frame.history_intent, allow_window_extension=False))
    strict_context = _context(strict_frame)
    strict_tools = _tools(strict_frame, strict_context, anatomy_db, next_session)
    _read(strict_tools, strict_context, rank_ref)
    with pytest.raises(ValueError, match="history_window_mismatch"):
        _execute(strict_tools, strict_context, **args)
    # Extension is for observation, not for silently reranking on a different period.
    with pytest.raises(ValueError, match="history_window_mismatch"):
        _execute(next_tools, next_context, **dict(args, operation="rank_history"))


def test_window_selection_uses_root_ranking_identity_and_observation_endpoint():
    from intelligence.services.historical_research.window_binding import WindowSelection

    base = {
        "root_query_id": "root-a", "root_sample_id": "sample-a",
        "ranking_start": "2026-01-17", "ranking_end": "2026-01-22",
        "source_start": "2026-01-17", "source_end": "2026-01-22",
        "start": "2026-01-17", "end": "2026-01-29",
    }
    mixed_parent = dict(base, source_start="2026-01-17", source_end="2026-01-29")
    selection = WindowSelection()
    with selection.reserve(base, observation=True):
        with selection.reserve(mixed_parent, observation=True):
            pass
    for changed in (
        dict(mixed_parent, root_query_id="root-b"),
        dict(mixed_parent, root_sample_id="sample-b"),
        dict(mixed_parent, ranking_start="2026-01-18"),
        dict(mixed_parent, ranking_end="2026-01-23"),
    ):
        with pytest.raises(ValueError, match="history_window_selection_conflict"):
            with selection.reserve(changed, observation=True):
                pass
    with pytest.raises(ValueError, match="history_window_observation_conflict"):
        with selection.reserve(dict(mixed_parent, end="2026-01-30"), observation=True):
            pass


def test_window_selection_allows_parallel_same_root_mixed_parent_siblings():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from intelligence.services.historical_research.window_binding import WindowSelection

    base = {
        "root_query_id": "root-a", "root_sample_id": "sample-a",
        "ranking_start": "2026-01-17", "ranking_end": "2026-01-22",
        "source_start": "2026-01-17", "source_end": "2026-01-22",
        "start": "2026-01-17", "end": "2026-01-29",
    }
    sibling = dict(base, source_end="2026-01-29")
    entered, release = Event(), Event()
    selection = WindowSelection()

    def hold_first():
        with selection.reserve(base, observation=True):
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(hold_first)
        try:
            assert entered.wait(3)
            with selection.reserve(sibling, observation=True):
                pass
        finally:
            release.set()
        first.result(5)


def test_source_identity_scope_and_cutoff_are_checked_before_query(tmp_path, anatomy_db, monkeypatch):
    tools, context, session, original, ref, _, _, decision = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    calls = []
    original_run = HistoryQuery.run

    def tracked(*args, **kwargs):
        calls.append(True)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(HistoryQuery, "run", tracked)
    other = session.store.create_run("other", "ask", session_id="other-conversation")
    foreign = HistorySession(session.store, other.run_id, other.session_id)
    foreign_ref = foreign.save("query", original)
    with pytest.raises(ValueError, match="outside this conversation"):
        _execute(tools, context, **_args(original, foreign_ref))
    # Source reference window is later than candidate; narrow shell cannot hide it.
    narrowed = replace(decision.task_frame, history_intent=replace(
        decision.task_frame.history_intent, requested_end=original["rows"][0]["end"]))
    narrow_context = _context(narrowed)
    narrowed_tools = _tools(narrowed, narrow_context, anatomy_db, session)
    with pytest.raises(ValueError, match="outside_authorized_scope|after_information_cutoff"):
        _execute(narrowed_tools, narrow_context, **_args(original, ref))
    late_ref = session.save("query", dict(original, knowledge_cutoff="2026-09-16"))
    with pytest.raises(ValueError, match="after_information_cutoff"):
        _execute(tools, context, **_args(original, late_ref))
    assert calls == []
    assert narrow_context.history_results == []


def test_no_successful_analogue_cannot_be_replaced_with_inspect_or_case(tmp_path, anatomy_db):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    inspected = _execute(tools, context, operation="inspect_history", entity_kind="market",
                         entity_codes=["000001.SH"], start="2026-01-24", end="2026-01-29")
    wrong_ref = inspected.telemetry["result_ref"]
    with pytest.raises(ValueError, match="history_window_analogue_required"):
        _execute(tools, context, **_args(original, wrong_ref))
    empty = dict(original, rows=[], preview=[], total_matched=0, returned_count=0)
    empty_ref = session.save("query", empty)
    _read(tools, context, empty_ref)
    with pytest.raises(ValueError, match="history_window_sample_not_found"):
        _execute(tools, context, **_args(original, empty_ref))


def test_immutable_original_recovery_checks_dependencies_and_lineage_without_live_db(tmp_path, anatomy_db, monkeypatch):
    import duckdb

    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref))
    rank_ref = ranked.telemetry["result_ref"]
    before = session.read(rank_ref)
    calls = []
    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: calls.append(True))
    _read(tools, context, rank_ref)
    assert calls == []
    assert session.read(rank_ref) == before
    forged = dict(before, window_binding=dict(before["window_binding"], source_end="2026-01-01"))
    forged_ref = session.save("query", forged)
    count = len(context.history_results)
    with pytest.raises(ValueError, match="history_window_binding_invalid"):
        _read(tools, context, forged_ref)
    assert len(context.history_results) == count
    assert calls == []


def test_overflow_does_not_shrink_window_or_population_and_failed_reservation_releases(tmp_path, anatomy_db, monkeypatch):
    from intelligence.services.historical_research import query

    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    original_limit = query.MAX_INPUT_ROWS
    monkeypatch.setattr(query, "MAX_INPUT_ROWS", 2)
    before = anatomy_db.read_bytes()
    with pytest.raises(ValueError, match="input row limit exceeded"):
        _execute(tools, context, **_args(original, ref, entity_kind="stock"))
    assert not [r for r in session.refs if r.startswith(session.run_id + "/")]
    assert len(context.history_results) == 1
    monkeypatch.setattr(query, "MAX_INPUT_ROWS", original_limit)
    second = original["rows"][1]
    result = _execute(tools, context, **_args(original, ref, entity_kind="stock", start=second["start"], end=second["end"],
        window_ref={"result_ref": ref, "sample_id": second["sample_id"]}))
    saved = session.read(result.telemetry["result_ref"])
    assert saved["total_matched"] == 3
    assert saved["spec"]["start"] == second["start"] and saved["spec"]["end"] == second["end"]
    assert anatomy_db.read_bytes() == before


def test_concurrent_incompatible_selection_is_rejected_before_second_db_read(tmp_path, anatomy_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    entered, release = Event(), Event()
    original_run = HistoryQuery.run
    calls = []

    def gated(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test failed to release query")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(HistoryQuery, "run", gated)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(_execute, tools, context, **_args(original, ref))
        try:
            assert entered.wait(3)
            second = original["rows"][1]
            with pytest.raises(ValueError, match="history_window_selection_conflict"):
                _execute(tools, context, **_args(original, ref, entity_kind="stock", start=second["start"], end=second["end"],
                    window_ref={"result_ref": ref, "sample_id": second["sample_id"]}))
        finally:
            release.set()
        result = first.result(5)
    assert calls == [True]
    assert session.read(result.telemetry["result_ref"])["total_matched"] == 2


def test_actual_projection_keeps_candidate_identity_and_window_relation_whole(tmp_path, anatomy_db):
    from tests.test_history_model_projection import _project

    tools, context, _, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _, candidates = _project(_read(tools, context, ref))
    assert any(r.get("sample_id") == original["rows"][0]["sample_id"] for r in candidates)
    _, details = _project(_execute(tools, context, **_args(original, ref)))
    relation = next(r for r in details if r.get("relation") == "same_window")
    assert (relation["start"], relation["end"]) == (original["rows"][0]["start"], original["rows"][0]["end"])
    assert (relation["source_start"], relation["source_end"]) == (relation["start"], relation["end"])
    assert any(r.get("result_ref") == ref for r in details)
    assert not any("source_reference" in r.get("fields", []) for r in details)


@pytest.mark.parametrize("loop_name", ["episode", "reference"])
def test_scripted_episode_reads_original_and_repairs_mismatched_window(tmp_path, anatomy_db, loop_name):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn

    tools, context, session, original, ref, _, _, decision = _scenario(tmp_path, anatomy_db)
    received = []

    class Consumer:
        def complete(self, *, messages, tools, timeout):
            observed = [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]
            received[:] = observed
            n = len(observed)
            if n < 3:
                name = "read_history_result" if n == 0 else "history_query"
                args = {"result_ref": ref} if n == 0 else _args(original, ref, **({"end": "2026-01-29"} if n == 1 else {}))
                return ModelTurn("", (ModelToolCall(f"window-{n}", name, args),), "scripted-window", "")
            gap = "脚本仅验证原件读取与同窗纠错；不是实际模型验收，条件全集未完成。"
            return ModelTurn(json.dumps({
                "status": "partial", "draft": gap, "gaps": [gap],
                "bindings": [{"output_id": o.output_id, "evidence_hashes": [], "gap": gap}
                             for o in context.contract.required_outputs],
            }, ensure_ascii=False), (), "scripted-window", "")

    loop = ContinuousAgentEpisode if loop_name == "episode" else HarnessReferenceLoop
    result = loop(Consumer()).run(task_frame=decision.task_frame, context=context, registry=tools)
    assert result.stop_reason == "model_finish"
    assert len(received) == 3
    assert received[0]["ok"] is True
    assert received[1]["ok"] is False and received[1]["error"] == "tool_exception"
    assert "history_window_mismatch" in received[1]["detail"]
    assert received[2]["ok"] is True
    saved_refs = [r for r in session.refs if r.startswith(session.run_id + "/")]
    assert len(saved_refs) == 1
    saved = session.read(saved_refs[0])
    assert saved["window_binding"]["source_query_id"] == original["query_id"]
    assert saved["spec"]["end"] == original["rows"][0]["end"]


@pytest.mark.parametrize("quote", [
    "「如果窗口太短，可以延长观察」",
    "\"如果窗口太短，可以延长观察\"",
    "```text\n如果窗口太短，可以延长观察\n```",
])
def test_quoted_or_negated_extension_never_grants_permission(quote):
    from intelligence.services.historical_research.intent import HistoryIntent, with_analysis_window_policy

    previous = HistoryIntent("historical_comparison", "2026-01-01", "2026-09-30", strict_window=True)
    result = with_analysis_window_policy(previous, "继续，用同一时间窗验证接力。解释材料：\n" + quote, continuing=True)
    assert result.analysis_window_source == "prior_analysis"
    assert result.allow_window_extension is False
    denied = with_analysis_window_policy(previous, "用同一时间窗验证；不允许延长观察。", continuing=True)
    assert denied.allow_window_extension is False
    fresh = with_analysis_window_policy(previous, "比较不同板块启动时的特征，用同一时间窗。")
    assert fresh.analysis_window_source == "none"  # No nonexistent prior analysis prerequisite.


def test_same_window_policy_and_source_selection_are_in_actual_prompt(tmp_path, anatomy_db):
    from intelligence.services.research_harness import FinanceResearchHarness

    tools, context, session, original, ref, _, _, decision = _scenario(tmp_path, anatomy_db)
    system, user = FinanceResearchHarness().assemble_prompt(decision.task_frame, context, tools)
    assert "本轮必须绑定历史参照窗" in system
    assert "超行数限则缩窄" not in system
    assert "window_ref" in system
    assert ref in user
    definitions = tools.tool_definitions(context.contract.allowed_capabilities)
    query = next(d["function"] for d in definitions if d["function"]["name"] == "history_query")
    assert "window_ref" in query["parameters"]["properties"]


def test_bound_rank_remains_recomputable_by_independent_arithmetic(tmp_path, anatomy_db):
    from scripts.audit_historical_research_artifacts import audit_artifact

    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref, entity_kind="stock"))
    run_id, filename = session.refs[ranked.telemetry["result_ref"]]
    # This audits arithmetic and fingerprints, not the semantic binding itself.
    report = audit_artifact(session.store.run_dir(run_id) / filename)
    assert report["errors"] == []
    assert report["result"] == "checked"


def test_bound_original_cannot_hide_wider_ancestor_scope(tmp_path, anatomy_db):
    tools, context, session, original, ref, _, _, decision = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref))
    # The chosen candidate starts after the source's search_start. Its shell is
    # allowed, but the historical search used to select it is outside this scope.
    start = original["rows"][0]["start"]
    assert start > original["spec"]["search_start"]
    frame = replace(decision.task_frame, history_intent=replace(
        decision.task_frame.history_intent, requested_start=start))
    next_context = _context(frame)
    next_tools = _tools(frame, next_context, anatomy_db, session)
    before = dict(session.query_aliases)
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        _read(next_tools, next_context, ranked.telemetry["result_ref"])
    assert next_context.history_results == []
    assert session.query_aliases == before


def test_reading_only_analogue_does_not_complete_a_same_window_request(tmp_path, anatomy_db):
    from intelligence.services.historical_research.research import assess_history_finish

    tools, context, _, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    # Even if the normal condition-comparison obligation is irrelevant here,
    # the specifically requested analysis is still missing.
    context = replace(context, history_intent=replace(context.history_intent, purpose="retrospective_discovery"))
    missing = assess_history_finish({}, context=context)
    assert missing.force_partial
    assert "绑定原件参照窗" in missing.gap


def test_cancel_and_deadline_leave_no_binding_or_saved_calculation(tmp_path, anatomy_db):
    from intelligence.services.research_contract import ResearchDeadline

    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    before = len(context.history_results)
    with pytest.raises(Exception, match="cancelled"):
        tools.execute("history_query", _args(original, ref), context=context, step_id=uuid4().hex,
                      is_cancelled=lambda: True)
    expired = replace(context, deadline=ResearchDeadline.from_timeout(0))
    with pytest.raises((TimeoutError, ValueError), match="deadline|time|budget"):
        tools.execute("history_query", _args(original, ref), context=expired, step_id=uuid4().hex)
    assert len(context.history_results) == before
    assert not [r for r in session.refs if r.startswith(session.run_id + "/")]
    # A failed reservation does not block a corrected valid request.
    assert _execute(tools, context, **_args(original, ref)).trace.status == "success"


def test_case_can_reference_both_bound_calculation_and_its_shared_ancestor(tmp_path, anatomy_db):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref))
    rank_ref = ranked.telemetry["result_ref"]
    # A diamond dependency is not a cycle: both query aliases and source_refs
    # may name the common analogue source already visited via the bound rank.
    case = session.save("case", {
        "draft": {"case_id": "case-window", "revision": 1, "question": "同窗排名",
                  "window_start": "2026-01-05", "window_end": "2026-01-29",
                  "source_refs": [ref, rank_ref], "hypotheses": []},
        "knowledge_cutoff": "2026-09-15", "query_aliases": {
            original["query_id"]: ref, ranked.telemetry["query_id"]: rank_ref,
        },
    })
    assert _read(tools, context, case).trace.status == "success"


def test_unbound_request_preserves_old_query_id_shape():
    spec = HistoryQuerySpec.from_arguments(dict(operation="rank_history", start="2026-01-05", end="2026-01-29"))
    assert "window_ref" not in spec.to_dict()


def test_worker_completion_or_projection_without_message_does_not_attest_consumption(tmp_path, anatomy_db):
    from intelligence.services.research_harness import FinanceResearchHarness

    tools, context, _, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    observed = tools.execute("read_history_result", {"result_ref": ref}, context=context, step_id=uuid4().hex)
    harness = FinanceResearchHarness()
    projection = harness.project_tool_result(observed, evidence_so_far=observed.evidence, seen_prose=set())
    # A completed worker (including one waiting in a concurrent batch) or a
    # projected-but-unappended message cannot authorize a dependent calculation.
    with pytest.raises(ValueError, match="history_window_source_not_read"):
        _execute(tools, context, **_args(original, ref))
    body = json.loads(projection.model_content)
    body["evidence"] = [e for e in body["evidence"] if "sample_id" not in json.loads(e["detail"])]
    hidden = replace(projection, model_content=json.dumps(body))
    harness.acknowledge_tool_result(observed, hidden, context=context)
    with pytest.raises(ValueError, match="history_window_sample_not_read"):
        _execute(tools, context, **_args(original, ref))
    harness.acknowledge_tool_result(observed, projection, context=context)
    assert _execute(tools, context, **_args(original, ref)).trace.status == "success"


def test_extended_trace_cannot_launder_new_rank_interval_in_later_turn(tmp_path, anatomy_db):
    tools, context, session, original, ref, store, conv, decision = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref))
    follow = _decide(store, conv, FOLLOWUPS[1], decision.turn_intent, 2)
    ctx = _context(follow.task_frame)
    registry = _tools(follow.task_frame, ctx, anatomy_db, session)
    rank_ref = ranked.telemetry["result_ref"]
    _read(registry, ctx, rank_ref)
    extended = _execute(registry, ctx, **_args(original, ref, operation="trace_history",
        entity_codes=["A.FP"], end="2026-01-29", window_ref={"result_ref": rank_ref}))
    trace_ref = extended.telemetry["result_ref"]
    last = _decide(store, conv, FOLLOWUPS[2], follow.turn_intent, 3)
    last_ctx = _context(last.task_frame)
    last_tools = _tools(last.task_frame, last_ctx, anatomy_db, session)
    _read(last_tools, last_ctx, trace_ref)
    with pytest.raises(ValueError, match="extended observation is not a new ranking interval"):
        _execute(last_tools, last_ctx, **_args(original, ref, end="2026-01-29",
            window_ref={"result_ref": trace_ref}))
    # Continuing the explicitly extended observation is not a further extension.
    observed = _execute(last_tools, last_ctx, **_args(original, ref, operation="trace_history",
        entity_codes=["A.FP"], end="2026-01-29", window_ref={"result_ref": trace_ref}))
    assert observed.trace.status == "success"
    assert observed.telemetry["window_binding"]["ranking_end"] == original["rows"][0]["end"]


@pytest.mark.parametrize("reference", [
    {}, {"result_ref": 3}, {"result_ref": "r", "sample_id": "1"},
    {"result_ref": "r", "sample_id": "A" * 64},
    {"result_ref": "r", "allow_window_extension": True},
])
def test_tool_arguments_cannot_grant_permissions_or_use_preview_ordinals(reference):
    with pytest.raises(ValueError, match="invalid window_ref"):
        HistoryQuerySpec.from_arguments(dict(operation="rank_history", start="2026-01-05",
                                             end="2026-01-29", window_ref=reference))


def test_cycle_and_cancellation_during_dependency_read_do_not_publish(tmp_path, anatomy_db, monkeypatch):
    tools, context, session, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    ranked = _execute(tools, context, **_args(original, ref))
    rank_ref = ranked.telemetry["result_ref"]
    saved = session.read(rank_ref)
    count = len(context.history_results)
    original_read = session.read
    cyclic = dict(saved, spec=dict(saved["spec"], window_ref={"result_ref": rank_ref}))
    monkeypatch.setattr(session, "read", lambda value: cyclic if value == rank_ref else original_read(value))
    with pytest.raises(ValueError, match="history_window_dependency_cycle_or_depth_limit"):
        _read(tools, context, rank_ref)
    assert len(context.history_results) == count
    cancelled = []

    def read_then_cancel(value):
        result = original_read(value)
        if value == ref:
            cancelled.append(True)
        return result

    monkeypatch.setattr(session, "read", read_then_cancel)
    with pytest.raises(RuntimeError, match="cancelled"):
        tools.execute("read_history_result", {"result_ref": rank_ref}, context=context,
                      step_id=uuid4().hex, is_cancelled=lambda: bool(cancelled))
    assert cancelled == [True]
    assert len(context.history_results) == count


def test_undelivered_bound_calculation_cannot_clear_completion_gap(tmp_path, anatomy_db):
    from intelligence.services.historical_research.research import assess_history_finish

    tools, context, _, original, ref, *_ = _scenario(tmp_path, anatomy_db)
    _read(tools, context, ref)
    result = tools.execute("history_query", _args(original, ref), context=context, step_id=uuid4().hex)
    context = replace(context, history_intent=replace(context.history_intent, purpose="retrospective_discovery"))
    assert assess_history_finish({}, context=context).force_partial
    _deliver(result, context)
    assert not assess_history_finish({}, context=context).force_partial
