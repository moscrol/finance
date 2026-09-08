"""Stored research keeps the scope of its underlying queries across turns."""

from dataclasses import replace

import pytest

from intelligence.services.historical_research.episode import (
    HistorySession,
    history_tool_specs,
)
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_historical_research_episode import _registry


def _query(registry, context, day="2026-08-03"):
    return registry.execute(
        "history_query",
        {
            "operation": "inspect_history",
            "start": day,
            "end": day,
            "entity_codes": ["A.FP"],
        },
        context=context,
        step_id="query",
    )


def _draft(*refs):
    return {
        "question": "农业如何形成",
        "purpose": "retrospective_discovery",
        "entity_ids": ["A.FP"],
        "source_refs": list(refs),
        "window_start": "2026-08-04",
        "window_end": "2026-09-07",
    }


def _next_turn(tmp_path, session, context, question=None):
    question = question or "只研究2026-08-04到2026-09-07这波农业行情怎么走出来的"
    run = session.store.create_run(question, "ask", session_id=session.conversation_id)
    next_session = HistorySession(session.store, run.run_id, session.conversation_id)
    frame = understand_query(question).task_frame
    next_context = replace(context, history_results=[], history_artifact_index=[])
    specs = history_tool_specs(
        frame,
        next_context,
        tmp_path / "db" / "market_feature_store.duckdb",
        next_session,
    )
    return ResearchToolRegistry(tuple(specs)), next_context, next_session


@pytest.mark.parametrize("reference_key", ["query_id", "result_ref"])
def test_case_cannot_hide_an_out_of_scope_query_and_failed_read_is_pure(
    tmp_path, reference_key
):
    registry, context, session = _registry(tmp_path)
    query = _query(registry, context)
    draft = _draft(query.telemetry[reference_key])
    draft["hypotheses"] = [
        {
            "hypothesis_id": "h1",
            "statement": "8月3日的表现提示量价关系",
            "source_case_refs": [query.telemetry[reference_key]],
        }
    ]
    saved = registry.execute(
        "save_history_research", {"draft": draft}, context=context, step_id="save"
    )
    reader, read_context, next_session = _next_turn(tmp_path, session, context)
    for ref in (query.telemetry["result_ref"], saved.telemetry["result_ref"]):
        with pytest.raises(ValueError, match="outside_authorized_scope"):
            reader.execute(
                "read_history_result",
                {"result_ref": ref},
                context=read_context,
                step_id="read",
            )
        assert next_session.query_aliases == {}
        assert next_session.definition_refs == set()
        assert read_context.history_results == []


def test_saved_aliases_are_checked_even_when_not_cited_in_this_draft(tmp_path):
    registry, context, session = _registry(tmp_path)
    _query(registry, context)
    # A previous query alias remains in the complete case envelope, even when
    # the model leaves source_refs empty. Reading must not hydrate that alias.
    context.history_results.clear()
    saved = registry.execute(
        "save_history_research", {"draft": _draft()}, context=context, step_id="save"
    )
    reader, read_context, next_session = _next_turn(tmp_path, session, context)
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        reader.execute(
            "read_history_result",
            {"result_ref": saved.telemetry["result_ref"]},
            context=read_context,
            step_id="read",
        )
    assert next_session.query_aliases == {}


def test_nested_case_scope_is_checked_by_both_read_and_save(tmp_path):
    registry, context, session = _registry(tmp_path)
    query = _query(registry, context)
    first = registry.execute(
        "save_history_research",
        {"draft": _draft(query.telemetry["query_id"])},
        context=context,
        step_id="first",
    )
    broad, broad_context, broad_session = _next_turn(
        tmp_path, session, context, "继续找农业的历史失败案例"
    )
    second = broad.execute(
        "save_history_research",
        {"draft": _draft(first.telemetry["result_ref"])},
        context=broad_context,
        step_id="second",
    )
    reader, read_context, next_session = _next_turn(
        tmp_path, broad_session, broad_context
    )
    ref = second.telemetry["result_ref"]
    for tool, arguments in (
        ("read_history_result", {"result_ref": ref}),
        ("save_history_research", {"draft": _draft(ref)}),
    ):
        with pytest.raises(ValueError, match="outside_authorized_scope"):
            reader.execute(tool, arguments, context=read_context, step_id=tool)
    assert next_session.store.load_run(next_session.run_id).artifacts == []
    assert next_session.query_aliases == {}
    assert read_context.history_results == []


def test_in_scope_case_retains_query_aliases_for_the_next_revision(tmp_path):
    registry, context, session = _registry(tmp_path)
    query = _query(registry, context, "2026-08-04")
    saved = registry.execute(
        "save_history_research",
        {"draft": _draft(query.telemetry["query_id"])},
        context=context,
        step_id="save",
    )
    reader, read_context, next_session = _next_turn(tmp_path, session, context)
    result = reader.execute(
        "read_history_result",
        {"result_ref": saved.telemetry["result_ref"]},
        context=read_context,
        step_id="read",
    )
    assert "研究草稿" in result.observation
    assert next_session.query_aliases[query.telemetry["query_id"]] == query.telemetry[
        "result_ref"
    ]
    draft = next_session.read(saved.telemetry["result_ref"])["draft"]
    draft.pop("case_id")
    draft.update(revision=2, parent_revision=1, open_questions=["还需寻找反例"])
    revised = reader.execute(
        "save_history_research",
        {"draft": draft, "previous_result_ref": saved.telemetry["result_ref"]},
        context=read_context,
        step_id="revise",
    )
    assert next_session.read(revised.telemetry["result_ref"])["draft"]["revision"] == 2


def test_dependency_cycle_does_not_skip_an_out_of_scope_sibling(tmp_path, monkeypatch):
    registry, context, session = _registry(tmp_path)
    query = _query(registry, context)
    reader, read_context, next_session = _next_turn(tmp_path, session, context)
    original_read = next_session.read
    calls = []
    # The file writer creates an immutable DAG. This deliberately injected cycle
    # verifies the reader remains bounded if a future artifact format adds links.
    first, second = "run/history-case-first.json", "run/history-case-second.json"
    payloads = {
        first: {
            "draft": dict(_draft(second), case_id="case-first"),
            "knowledge_cutoff": "2026-09-07",
        },
        second: {
            "draft": dict(
                _draft(first, query.telemetry["result_ref"]), case_id="case-second"
            ),
            "knowledge_cutoff": "2026-09-07",
        },
    }

    def read(ref):
        calls.append(ref)
        return payloads[ref] if ref in payloads else original_read(ref)

    monkeypatch.setattr(next_session, "read", read)
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        reader.execute(
            "read_history_result",
            {"result_ref": first},
            context=read_context,
            step_id="cycle",
        )
    assert len(calls) <= 4
    assert next_session.query_aliases == {}


def test_history_tool_preview_schema_and_parser_share_25_row_limit(tmp_path):
    registry, context, session = _registry(tmp_path)
    frame = understand_query("这一波农业怎么走出来的").task_frame
    spec = history_tool_specs(frame, context, tmp_path / "missing.duckdb", session)[0]
    assert spec.parameters["properties"]["preview_limit"]["maximum"] == 25
    arguments = {
        "operation": "inspect_history",
        "start": "2026-08-03",
        "end": "2026-08-04",
        "entity_codes": ["A.FP"],
        "preview_limit": 26,
    }
    with pytest.raises(ValueError, match="preview limit must be 1..25"):
        spec.parse_arguments(arguments)
    parsed, _ = spec.parse_arguments(dict(arguments, preview_limit=25))
    assert parsed.preview_limit == 25
    assert not session.store.load_run(session.run_id).artifacts
