"""The real semantic verifier and final public coverage, without a judge call."""

import json
from dataclasses import replace

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_semantic_verifier import recheck_owned_public_delivery, numeric_condition_unsupported
from intelligence.services.episode_projection import project_durable_events
from intelligence.services.episode_entry_identity import EntryIdentity
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolRunResult, ToolSpec
from intelligence.tests.owned_result_support import frame_context, source_fixture, finish_payload


def _native_parts(parts_fn):
    frame, context = frame_context(task_id="owned-public")
    source = source_fixture()

    def runner(_query, _context):
        return ToolRunResult(source.evidence, source.observation, source.trace,
                             dataset=source.dataset, query_basis=source.query_basis)

    registry = ResearchToolRegistry((ToolSpec("mainline_context", "mainline_context", "同日行情", "local", "current", runner,
                                            io_effect="local_read"),))

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, *, messages, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn("", (ModelToolCall("source", "mainline_context", {"query": "同日行情"}),))
            source_view = next(json.loads(m["content"])["owned_results"] for m in messages
                               if m["role"] == "tool" and "owned_results" in json.loads(m["content"]))
            return ModelTurn(json.dumps(finish_payload(parts_fn(source_view["parts"])), ensure_ascii=False), ())

    outcome = ContinuousAgentEpisode(Model()).run(task_frame=frame, context=context, registry=registry)
    assert outcome.stop_reason == "model_finish"
    return frame, context, outcome


def test_true_semantic_boundary_keeps_owned_rule_without_numeric_doubt(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")

    def parts(view):
        rule = next(p for p in view if p["text"].startswith("本地量价规则"))
        immune = next(p for p in view if "医药生物主题中的免疫治疗" in p["text"])
        return [{"result_ref": rule["result_ref"]}, {"result_ref": immune["result_ref"]},
                "免疫治疗同样双红确认。", "若后续成交额持续2天大于500亿元，才考虑提高判断。"]

    frame, context, outcome = _native_parts(parts)
    semantic = SemanticEpisodeVerifier().verify(frame=frame,
        structurally_verified=verify_episode_outcome(context.contract, outcome), context=context, deadline=context.deadline)
    assert "不满足严格双红" in semantic.public_answer
    assert semantic.owned_coverage["owned_faithful"] == 2
    assert semantic.owned_coverage["free_unassessed"] == 2
    assert semantic.owned_coverage["whole_answer"] == "unassessed"
    marks = [r for r in semantic.sentence_verdicts if r["decision"] == "marked"]
    assert marks and all("本地量价规则" not in r["sentence"] for r in marks)
    assert "2天" in marks[0]["sentence"] and "500" in marks[0]["sentence"]


@pytest.mark.parametrize("free_first", [False, True])
def test_owned_span_does_not_exempt_identical_free_rule_or_future_threshold(monkeypatch, free_first):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")

    def parts(view):
        rule = next(p for p in view if p["text"].startswith("本地量价规则"))
        pair = [rule["text"], {"result_ref": rule["result_ref"]}] if free_first else [{"result_ref": rule["result_ref"]}, rule["text"]]
        return [*pair, "若成交额大于500亿元并持续10天，则升级判断。"]

    frame, context, outcome = _native_parts(parts)
    semantic = SemanticEpisodeVerifier().verify(frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome),
                                                context=context, deadline=context.deadline)
    marked = [r for r in semantic.sentence_verdicts if r["decision"] == "marked"]
    assert any("本地量价规则" in r["sentence"] for r in marked)
    assert any("10天" in r["sentence"] for r in marked)
    assert semantic.owned_coverage["owned_faithful"] == 1
    assert semantic.owned_coverage["free_unassessed"] == 2
    assert numeric_condition_unsupported(semantic.verified)


def test_actual_adapter_backfill_verify_and_final_public_share_the_same_proof(monkeypatch):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.research_contract import InMemoryRootBudgetLedger
    from intelligence.runtime.turn_control_core import TurnControlResult

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, context, outcome = _native_parts(lambda view: [{"result_ref": p["result_ref"]} for p in view
        if p["text"].startswith("本地量价规则") or "医药生物主题中的免疫治疗" in p["text"]])
    context = replace(context, root_budget=InMemoryRootBudgetLedger(episode_id=context.contract.task_id,
        initial_calls=6, hard_calls_cap=6, initial_seconds=30, hard_seconds_cap=30))

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    result = ContinuousTurnAdapter(runtime=Runtime(), semantic_verifier=SemanticEpisodeVerifier(), mode="on",
        context_factory=lambda *_args, **_kwargs: context, registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        task_id_factory=lambda: context.contract.task_id).handle(frame=frame, control=TurnControlResult(
            task_frame=frame, execution_route="market_forecast", terminal_kind="research", needs_retrieval=True,
            capabilities=("mainline_context",), contract_required=True))
    assert "不满足严格双红" in result.answer
    assert "未在证据中找到出处" not in result.answer
    artifact = result.private_artifact
    assert artifact["backfill_turns"] == 0
    assert artifact["semantic_verifier"]["owned_coverage"]["owned_faithful"] == 2
    assert artifact["semantic_verifier"]["owned_coverage"]["whole_answer"] == "unassessed"


def test_context_none_old_bad_body_and_instance_reuse_never_grant_proof(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, context, outcome = _native_parts(lambda view: [{"result_ref": next(p["result_ref"] for p in view
                                           if "医药生物主题中的免疫治疗" in p["text"])}])
    structural = verify_episode_outcome(context.contract, outcome)
    verifier = SemanticEpisodeVerifier()
    approved = verifier.verify(frame=frame, structurally_verified=structural, context=context, deadline=context.deadline)
    assert approved.owned_coverage["owned_faithful"] == 1
    without_context = verifier.verify(frame=frame, structurally_verified=approved.verified, deadline=context.deadline)
    assert without_context.owned_coverage is None and without_context.verified._owned_answer is None
    assert "owned_coverage" not in without_context.to_dict()

    changed = replace(outcome, draft=outcome.draft.replace("不满足", "满足"))
    rejected = verifier.verify(frame=frame, structurally_verified=verify_episode_outcome(context.contract, changed),
                               context=context, deadline=context.deadline)
    assert rejected.judge_status == "rejected" and rejected.owned_coverage is None
    assert rejected.verified._owned_answer is None and "免疫治疗满足" not in rejected.public_answer
    new_owner = replace(context, entry_identity=EntryIdentity("workbench_conversation", "other-user", "chat", "run", "assistant").bind(context.contract.task_id))
    rejected = verifier.verify(frame=frame, structurally_verified=structural, context=new_owner, deadline=context.deadline)
    assert rejected.judge_status == "rejected" and rejected.verified._owned_answer is None


def test_final_public_removal_mutation_and_private_receipt_projection(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, context, outcome = _native_parts(lambda view: [{"result_ref": next(p["result_ref"] for p in view
                                           if "医药生物主题中的免疫治疗" in p["text"])}, "自由分析待验证。"])
    semantic = SemanticEpisodeVerifier().verify(frame=frame, structurally_verified=verify_episode_outcome(context.contract, outcome),
                                                context=context, deadline=context.deadline)
    removed = recheck_owned_public_delivery(semantic, context=context, projected="自由分析待验证。")
    assert removed.owned_coverage["owned_faithful"] == 0 and removed.owned_coverage["owned_removed"] == 1
    changed = recheck_owned_public_delivery(semantic, context=context, projected=outcome.draft.replace("不满足", "满足"))
    assert changed.owned_coverage["owned_changed"] == 1 and changed.owned_coverage["owned_faithful"] == 0
    assert changed.judge_status == "rejected" and "免疫治疗满足" not in changed.public_answer
    # Same text absorbed into another author's syntax loses its node certificate.
    wrapped = recheck_owned_public_delivery(semantic, context=context, projected="并非" + outcome.draft)
    assert wrapped.owned_coverage["owned_faithful"] == 0
    projected = project_durable_events(outcome.events)
    finish = next(e["payload"] for e in reversed(projected.events) if e["kind"] == "finish")
    assert "owned_answer" not in finish and "owned_answer_sha256" in finish
    private = project_durable_events(outcome.events, include_model_visible_text=True)
    assert next(e["payload"] for e in reversed(private.events) if e["kind"] == "finish")["owned_answer"]
