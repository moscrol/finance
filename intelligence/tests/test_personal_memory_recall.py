"""Pure recall is a retrieval task, not a current-world financial claim.

Temporary identities and a deterministic provider exercise the real controller,
contract compiler and Episode finish boundary. No live models or data roots.
"""
from __future__ import annotations

from dataclasses import replace
import json
import time
from uuid import uuid4

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services import corrections, episode_tools, llm_refine
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.episode_protocol import validate_episode_finish
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, numeric_condition_unsupported
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.memory_status import record_status
from intelligence.services.personal_memory_recall import memory_gap_public_notice
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.query_resolution import QueryResolution
from intelligence.services.query_understanding import understand_query
from intelligence.services.turn_controller import decide_turn
from intelligence.tests.test_episode_semantic_verifier import _judge


RECALL = "关于长电科技，我之前纠正过的研究顺序是什么？只回顾我的记录，不做行情判断。"


class SubjectResolver:
    """The live entry already resolved the company before selecting an intent."""

    def __init__(self, subject="长电科技"):
        self.subject = subject

    def resolve(self, query):
        return QueryResolution(
            envelope=replace(
                understand_query(query), subject=self.subject, subject_kind="company",
                matched_by="entity", question_type="stock_deep_dive",
            ),
            anchor=None,
        )


def route_response(route="personal_memory_recall"):
    return json.dumps({"personal_records_only": route == "personal_memory_recall"}), object(), ""


@pytest.mark.parametrize(("query", "subject"), [
    (RECALL, "长电科技"),
    ("关于宁德时代，提醒我之前设定的 3 项检查顺序。", "宁德时代"),
])
def test_pure_recall_compiles_required_personal_output(query, subject):
    calls = []

    def complete(messages):
        calls.append(messages)
        return route_response()

    decision = decide_turn(query, resolver=SubjectResolver(subject), llm_complete=complete)

    assert decision.task_frame is not None
    assert decision.task_frame.question_type == "personal_memory_recall"
    assert calls, "the company identity must not silently decide a financial task"
    assert decision.task_frame.subject == subject
    assert decision.task_frame.raw_question == query
    context = build_episode_context(decision.task_frame, task_id="recall", timeout=30)
    assert context.contract.allowed_capabilities == ("memory_lookup",)
    assert len(context.contract.required_outputs) == 1
    output = context.contract.required_outputs[0]
    assert output.output_id == "prior_recall" and output.required
    assert output.grounding_mode == "user_premise"
    assert output.evidence_types == ("memory_lookup",)


@pytest.mark.parametrize("query", ["长电科技现在怎么看", "长电科技的收入是多少", "长电科技的上涨空间如何"])
def test_ordinary_finance_adds_no_arbitration(query):
    def forbidden(_messages):
        pytest.fail("ordinary finance must not acquire a new model call")

    decision = decide_turn(query, resolver=SubjectResolver(), llm_complete=forbidden)
    assert decision.task_frame.question_type != "personal_memory_recall"
    context = build_episode_context(decision.task_frame, task_id="normal")
    assert any(output.required and output.grounding_mode == "evidence" for output in context.contract.required_outputs)


@pytest.mark.parametrize("response", [
    (None, None, "timeout"), ("not-json", None, ""),
    (json.dumps({"route_id": "invented"}), None, ""),
    (json.dumps({"personal_records_only": "true"}), None, ""),
    (json.dumps({"personal_records_only": 1}), None, ""),
    (json.dumps({"personal_records_only": True, "new_capabilities": ["finance_query"]}), None, ""),
    ("[true]", None, ""),
    route_response("stock_deep_dive"),
])
def test_failed_or_mixed_arbitration_keeps_financial_contract(response):
    calls = []

    def complete(messages):
        calls.append(messages)
        return response

    decision = decide_turn(
        "长电科技，结合我之前的判断，评估现在的上涨空间。",
        resolver=SubjectResolver(), llm_complete=complete,
    )
    assert len(calls) == 1
    assert decision.task_frame.question_type == "stock_deep_dive"
    context = build_episode_context(decision.task_frame, task_id="mixed")
    assert any(item.required and item.grounding_mode == "evidence" for item in context.contract.required_outputs)
    assert not next(item for item in context.contract.required_outputs if item.output_id == "prior_recall").required


@pytest.mark.parametrize("remaining", [0.0, 2.0, 100.0])
def test_arbitration_uses_root_remaining_budget_once(monkeypatch, remaining):
    calls = []

    def complete(_messages, **kwargs):
        calls.append(kwargs)
        return route_response()

    monkeypatch.setattr(llm_refine, "complete", complete)
    decision = decide_turn(
        RECALL, resolver=SubjectResolver(), deadline=ResearchDeadline.from_timeout(remaining),
    )
    if remaining == 0:
        assert calls == [] and decision.task_frame.question_type == "stock_deep_dive"
    else:
        assert len(calls) == 1 and 0 < calls[0]["timeout"] <= min(8, remaining)
        assert decision.task_frame.question_type == "personal_memory_recall"


def test_late_arbitration_cannot_change_financial_contract():
    def complete(_messages):
        time.sleep(0.025)
        return route_response()

    decision = decide_turn(
        RECALL, resolver=SubjectResolver(), llm_complete=complete,
        deadline=ResearchDeadline.from_timeout(0.01),
    )
    assert decision.task_frame.question_type == "stock_deep_dive"


@pytest.mark.parametrize("header_delay", [0.0, 0.8])
def test_controller_real_http_deadline_returns_and_reaps_worker(monkeypatch, header_delay):
    from intelligence.services import llm_http_transport
    from intelligence.tests.test_llm_tool_response_deadline import local_provider

    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    events = []
    opener = llm_http_transport.urlopen

    def observed(request, timeout, **kwargs):
        return opener(
            request, timeout, **kwargs, loopback_only=True,
            observer=lambda event, **details: events.append({"event": event, **details}),
        )

    monkeypatch.setattr(llm_http_transport, "urlopen", observed)
    with local_provider(header_delay=header_delay, body_seconds=1.5) as provider:
        monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (provider,))
        with llm_refine.call_ledger_scope() as ledger:
            started = time.monotonic()
            decision = decide_turn(
                RECALL, resolver=SubjectResolver(), deadline=ResearchDeadline.from_timeout(0.35),
            )
            elapsed = time.monotonic() - started
        assert elapsed < 0.85, f"0.35s controller window lasted {elapsed:.3f}s"
    assert decision.task_frame.question_type == "stock_deep_dive"
    records = ledger.summary()["records"]
    assert len(records) == 1 and records[0]["status"] == "failed"
    assert records[0]["reason"] == "timeout"
    assert events[-1]["event"] == "closed" and events[-1]["returncode"] is not None


def test_pure_recall_contract_does_not_gain_financial_or_forward_permissions(monkeypatch):
    from intelligence.services.task_frame import derive_required_outputs

    monkeypatch.setenv("WORKBENCH_TOOL_AUTHORIZATION", "all")
    query = "关于长电科技，复述我之前记录的明天上涨判断，不评价是否成立。"
    frame = decide_turn(query, resolver=SubjectResolver(), llm_complete=lambda _: route_response()).task_frame
    context = build_episode_context(frame, task_id="no-financial-permissions")
    assert context.contract.allowed_capabilities == ("memory_lookup",)
    assert tuple(item.output_id for item in context.contract.required_outputs) == ("prior_recall",)
    assert derive_required_outputs("personal_memory_recall", query, extra=("verification_conditions",)) == ("prior_recall",)


def test_existing_candidate_grammar_does_not_claim_english_coverage():
    decision = decide_turn(
        "For ACME, recall my earlier research checklist; only my saved notes.",
        resolver=SubjectResolver("ACME"), llm_complete=lambda _: pytest.fail("new lexical route"),
    )
    assert decision.task_frame.question_type == "stock_deep_dive"


def _finish(draft, *, hashes=("E1",), gap="", status="completed"):
    return {"status": status, "draft": draft, "gaps": [gap] if gap else [], "bindings": [
        {"output_id": "prior_recall", "basis": "user_premise", "evidence_hashes": list(hashes), "gap": gap},
    ]}


def _episode(tmp_path, monkeypatch, *, user="alice", draft="你此前纠偏：先看客户验证进度再下结论（E1）。"):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", lambda *a, **kw: ())
    frame = decide_turn(RECALL, resolver=SubjectResolver(), llm_complete=lambda _: route_response()).task_frame
    context = build_episode_context(frame, task_id=f"pure-recall-{uuid4().hex}", timeout=30)
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path / "finance", knowledge_wiki=tmp_path / "wiki",
        l3_runner=None, memory_user=user,
    )

    class Model:
        calls = []

        def complete(self, *, messages, tools, timeout):
            self.calls.append(messages)
            return ModelTurn(json.dumps(_finish(draft), ensure_ascii=False), (), "offline")

    model = Model()
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    return frame, context, outcome, model


@pytest.mark.parametrize("state", ["active", "rejected", "other_user", "unavailable"])
def test_real_episode_recall_and_controlled_gap_are_deliverable(tmp_path, monkeypatch, state):
    root = tmp_path / "users" / "alice"
    path, row = corrections.record_correction(
        root / "corrections.jsonl", correction="先看客户验证进度再下结论", themes=["长电科技"],
    )
    if state == "rejected":
        record_status(path, target_ts=row["id"], status="rejected")
    if state == "unavailable":
        path.write_text("{broken", encoding="utf-8")
    before = {file: file.read_bytes() for file in root.glob("*.jsonl")}
    frame, context, outcome, model = _episode(
        tmp_path, monkeypatch, user="bob" if state == "other_user" else "alice",
    )
    assert len(model.calls) == 1
    assert outcome.usage.invalid_actions == 0 and outcome.usage.tool_calls == 0
    assert outcome.bindings[0].basis == "user_premise"
    structural = verify_episode_outcome(context.contract, outcome)
    judge = _judge(True)
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(60),
    )
    assert judge.calls, "a legal recall gap must still pass the semantic boundary"
    assert result.judge_status == "passed"
    if state == "active":
        assert result.status == "completed"
        assert "先看客户验证进度再下结论" in result.public_answer
        assert structural.completion.outputs[0].status == "fulfilled"
        assert outcome.bindings[0].evidence_hashes
    else:
        notice = memory_gap_public_notice(context.contract, outcome.evidence)
        assert notice and result.public_answer == notice
        assert result.status == "partial"
        assert structural.completion.outputs[0].status == "legal_gap"
        assert outcome.bindings[0].evidence_hashes == ()
        assert "先看客户验证进度再下结论" not in result.public_answer
        assert ("未能读取" if state == "unavailable" else "未找到") in result.public_answer
    assert {file: file.read_bytes() for file in before} == before


def test_personal_recall_does_not_authorize_market_numbers(tmp_path, monkeypatch):
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl",
        correction="先观察连续3日客户验证进度再下结论", themes=["长电科技"],
    )
    frame, context, outcome, _ = _episode(
        tmp_path, monkeypatch,
        draft="你此前纠偏：先观察连续3日客户验证进度再下结论（E1）。若股价达到500元则可以买入。",
    )
    structural = verify_episode_outcome(context.contract, outcome)
    assert numeric_condition_unsupported(structural)
    with pytest.raises(ValueError, match="required output lacks evidence"):
        validate_episode_finish(_finish("编造的旧规则", hashes=()), context=context, evidence=outcome.evidence)
    with pytest.raises(ValueError, match="grounding basis mismatch"):
        validate_episode_finish(
            {**_finish("把纠偏当事实"), "bindings": [{"output_id": "prior_recall", "basis": "evidence", "evidence_hashes": ["E1"], "gap": ""}]},
            context=context, evidence=outcome.evidence,
        )
    clean = replace(outcome, draft="你此前纠偏：先观察连续3日客户验证进度再下结论（E1）。")
    assert not numeric_condition_unsupported(verify_episode_outcome(context.contract, clean))
