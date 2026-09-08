"""A model can revise a paged case without reconstructing its old provenance."""

import json

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.historical_research.episode import (
    HistorySession,
    history_tool_specs,
)
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_historical_research_episode import _registry


def model_view(observation):
    projected = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=(), seen_prose=set()
    )
    model = json.loads(projected.model_content)
    assert not model["evidence"]
    return json.loads(model["observation"])


@pytest.fixture
def saved_case(tmp_path):
    registry, context, session = _registry(tmp_path)
    query = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
            "features": ["return_pct"],
        },
        context=context,
        step_id="query",
    )
    qref = query.telemetry["result_ref"]
    qid = query.telemetry["query_id"]
    draft = {
        "question": "农业这一波如何形成并延续？",
        "purpose": "retrospective_discovery",
        "entity_ids": ["A.FP"],
        "source_refs": [qref],
        "hypotheses": [
            {
                "hypothesis_id": f"h{i}",
                "statement": f"解释{i}：" + "旧假设有反证，仍待查。" * 40,
                "source_case_refs": [qref],
                "failed_sample_refs": [qid],
                "counterevidence_refs": [qref],
                "exposed_sample_refs": [qid],
            }
            for i in range(8)
        ],
    }
    first = registry.execute(
        "save_history_research", {"draft": draft}, context=context, step_id="save"
    )
    return registry, context, session, first.telemetry["result_ref"], qref


def second_turn(tmp_path, session):
    run = session.store.create_run(
        "看到反例后修订并保存", "ask", session_id=session.conversation_id
    )
    next_session = HistorySession(session.store, run.run_id, session.conversation_id)
    frame = understand_query("找找历史失败案例并修订刚才的研究假设").task_frame
    context = build_episode_context(frame, task_id=run.run_id)
    registry = ResearchToolRegistry(
        tuple(
            history_tool_specs(
                frame,
                context,
                tmp_path / "db" / "market_feature_store.duckdb",
                next_session,
            )
        )
    )
    return registry, context, next_session


def test_case_pages_are_complete_real_model_json_and_cover_all_hypotheses(saved_case):
    registry, context, session, ref, _ = saved_case
    offset, ids = 0, []
    while offset is not None:
        result = registry.execute(
            "read_history_result",
            {"result_ref": ref, "offset": offset, "limit": 25},
            context=context,
            step_id=f"page-{offset}",
        )
        assert len(result.observation) <= 900
        page = model_view(result)
        assert page["kind"] == "research_draft"
        assert page["result_ref"] == ref
        assert page["revision"] == 1
        assert page["total_hypotheses"] == 8
        assert page["hypotheses"]
        assert all(item["statement_truncated"] for item in page["hypotheses"])
        ids.extend(item["hypothesis_id"] for item in page["hypotheses"])
        assert page["next_offset"] is None or page["next_offset"] > offset
        offset = page["next_offset"]
    assert ids == [f"h{i}" for i in range(8)]
    assert len(session.read(ref)["draft"]["hypotheses"][0]["statement"]) > 300


def test_sparse_patch_cross_turn_preserves_old_provenance_and_is_idempotent(
    saved_case, tmp_path
):
    _, _, old_session, ref, qref = saved_case
    registry, context, session = second_turn(tmp_path, old_session)
    old = old_session.read(ref)["draft"]
    read = registry.execute(
        "read_history_result", {"result_ref": ref}, context=context, step_id="read"
    )
    page = model_view(read)
    target = page["hypotheses"][0]["hypothesis_id"]
    counter = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "start": "2026-08-04",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
            "features": ["return_pct"],
        },
        context=context,
        step_id="counter-query",
    )
    new_counter_ref = counter.telemetry["result_ref"]
    arguments = {
        "previous_result_ref": ref,
        "patch": {
            "source_refs": [new_counter_ref],
            "hypotheses": [
                {
                    "hypothesis_id": target,
                    "statement": "新反证使原解释削弱",
                    "status": "weakened",
                    "counterevidence_refs": [new_counter_ref],
                }
            ],
        },
    }
    saved = registry.execute(
        "save_history_research", arguments, context=context, step_id="patch"
    )
    new_ref = saved.telemetry["result_ref"]
    current = session.read(new_ref)["draft"]
    assert current["revision"] == 2 and current["parent_revision"] == 1
    assert current["source_refs"] == [*old["source_refs"], new_counter_ref]
    assert set(old["exposed_sample_refs"]) <= set(current["exposed_sample_refs"])
    assert len(current["hypotheses"]) == 8
    first = current["hypotheses"][0]
    assert (first["version"], first["parent_version"], first["status"]) == (
        2,
        1,
        "weakened",
    )
    for field in (
        "source_case_refs",
        "failed_sample_refs",
        "counterevidence_refs",
        "exposed_sample_refs",
    ):
        assert set(old["hypotheses"][0][field]) <= set(first[field])
    assert first["counterevidence_refs"] == [qref, new_counter_ref]
    assert new_counter_ref in current["exposed_sample_refs"]
    assert current["hypotheses"][1:] == old["hypotheses"][1:]
    assert old_session.read(ref)["draft"] == old
    retry = registry.execute(
        "save_history_research", arguments, context=context, step_id="retry"
    )
    assert retry.telemetry["result_ref"] == new_ref
    same = registry.execute(
        "save_history_research",
        {**arguments, "previous_result_ref": new_ref},
        context=context,
        step_id="same-head",
    )
    assert same.telemetry["result_ref"] == new_ref
    for item in context.history_results[-3:]:
        assert item["operation"] == "save_history_research"
        assert item["revision"] == 2 and item["result_ref"] == new_ref
        assert item["execution_status"] == "success"
    assert model_view(saved)["revision"] == 2


@pytest.mark.parametrize(
    "patch",
    [
        {
            "hypotheses": [
                {"hypothesis_id": "h0", "failed_sample_refs": ["made-up-ref"]}
            ]
        },
        {"hypotheses": [{"hypothesis_id": "missing-id", "status": "unsupported"}]},
        {"remove_hypotheses": ["h0"]},
        {"hypotheses": [{"hypothesis_id": "h0", "version": 99}]},
    ],
)
def test_patch_rejects_bad_refs_deletion_unknown_id_and_manual_versions(
    saved_case, patch
):
    registry, context, session, ref, _ = saved_case
    before = len(session.refs)
    with pytest.raises(ValueError):
        registry.execute(
            "save_history_research",
            {"previous_result_ref": ref, "patch": patch},
            context=context,
            step_id="bad",
        )
    assert len(session.refs) == before


def test_patch_requires_exact_case_parent_and_exclusive_mode(saved_case):
    registry, context, _, ref, qref = saved_case
    for arguments in (
        {"patch": {}},
        {"patch": {}, "previous_result_ref": qref},
        {"patch": {}, "draft": {}, "previous_result_ref": ref},
    ):
        with pytest.raises(ValueError):
            registry.execute(
                "save_history_research",
                arguments,
                context=context,
                step_id="bad-parent",
            )


def test_full_draft_cannot_delete_prior_hypotheses_and_stale_patch_is_rejected(
    saved_case,
):
    registry, context, session, ref, _ = saved_case
    old = session.read(ref)["draft"]
    deleted = {key: value for key, value in old.items() if key != "case_id"}
    deleted.update(revision=2, parent_revision=1, hypotheses=[])
    with pytest.raises(ValueError, match="retain hypotheses"):
        registry.execute(
            "save_history_research",
            {"previous_result_ref": ref, "draft": deleted},
            context=context,
            step_id="delete",
        )
    registry.execute(
        "save_history_research",
        {
            "previous_result_ref": ref,
            "patch": {"hypotheses": [{"hypothesis_id": "h0", "status": "weakened"}]},
        },
        context=context,
        step_id="valid",
    )
    with pytest.raises(ValueError, match="stale_case_revision"):
        registry.execute(
            "save_history_research",
            {
                "previous_result_ref": ref,
                "patch": {
                    "hypotheses": [{"hypothesis_id": "h0", "status": "unsupported"}]
                },
            },
            context=context,
            step_id="stale",
        )


def test_patch_cannot_use_parent_from_another_conversation(saved_case, tmp_path):
    _, _, session, ref, _ = saved_case
    other = session.store.create_run(
        "另一个会话", "ask", session_id="other-conversation"
    )
    other_session = HistorySession(session.store, other.run_id, "other-conversation")
    frame = understand_query("找找农业历史失败案例并修订假设").task_frame
    context = build_episode_context(frame, task_id=other.run_id)
    registry = ResearchToolRegistry(
        tuple(
            history_tool_specs(
                frame,
                context,
                tmp_path / "db" / "market_feature_store.duckdb",
                other_session,
            )
        )
    )
    with pytest.raises(ValueError, match="outside this conversation"):
        registry.execute(
            "save_history_research",
            {"previous_result_ref": ref, "patch": {"stop_reason": "counterevidence"}},
            context=context,
            step_id="wrong-conversation",
        )


def test_noop_patch_helper_still_validates_authorized_references(saved_case):
    from intelligence.services.historical_research.research import (
        ResearchCase,
        prepare_research_patch,
    )

    _, _, session, ref, _ = saved_case
    previous = ResearchCase.from_dict(session.read(ref)["draft"])
    with pytest.raises(ValueError, match="unauthorized"):
        prepare_research_patch({}, previous=previous, available_result_refs=())
