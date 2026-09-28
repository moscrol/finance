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
NUMERIC_PRIOR = "若连续3日客户验证进度未达标，就应暂缓下结论"


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


def financial_controller_response():
    return json.dumps({
        "route_id": "stock_deep_dive", "confidence": 0.95,
        "reason": "研究公司", "user_goal": "判断公司研究证据",
        "assumptions": [], "ambiguities": [],
    }), object(), ""


@pytest.mark.parametrize("query", [
    "我之前纠正过的研究顺序是什么？只回顾我的记录，不做行情判断。",
    "只回顾我此前的偏好。",
    "我上次记录的检查清单是什么？",
    "关于光刻胶，我之前纠正过的研究顺序是什么？只回顾我的记录，不做行情判断。",
])
def test_default_resolver_personal_reference_reaches_bounded_classifier(tmp_path, monkeypatch, query):
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wiki"))
    calls = []

    def controller(messages, **kwargs):
        calls.append((messages, kwargs))
        if "personal_records_only" in messages[0]["content"]:
            return route_response()
        # Match the actual production prompt, never rely on its legacy schema.
        return json.dumps({"route_id": "personal_memory_recall", "confidence": 0.99,
                           "reason": "纯回顾", "user_goal": "回顾既存记录",
                           "assumptions": [], "ambiguities": []}), None, ""

    monkeypatch.setattr(llm_refine, "complete", controller)
    frame = decide_turn(query, deadline=ResearchDeadline.from_timeout(2)).task_frame
    assert frame.question_type == "personal_memory_recall"
    assert len(calls) == 1 and 0 < calls[0][1]["timeout"] <= 2
    assert frame.subject == ("光刻胶" if "光刻胶" in query else None)


def test_recent_reader_applies_cutoff_before_record_limit(tmp_path, monkeypatch):
    from datetime import date
    from intelligence.services.research_contract import InformationCutoff
    from intelligence.services import user_memory

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wiki"))
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", lambda *a, **kw: ())
    monkeypatch.setattr(llm_refine, "complete", lambda *a, **kw: route_response())
    path = tmp_path / "users" / "alice" / "corrections.jsonl"
    for day in range(1, 15):
        corrections.record_correction(path, correction=f"记录{day}：先检查客户验证", ts=f"2026-09-{day:02d}T12:00:00")
    frame = decide_turn("只回顾我此前的偏好。").task_frame
    context = replace(
        build_episode_context(frame, task_id="recent-before-cutoff", timeout=30),
        information_cutoff=InformationCutoff(date(2026, 9, 6), "requested"),
    )
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path / "finance", knowledge_wiki=tmp_path / "wiki",
        l3_runner=None, memory_user="alice",
    )
    records = tuple(item for item in registry.opening_prefetch if item.evidence_tier == "user_memory")
    assert len(records) == user_memory.DEFAULT_LIMIT
    assert [item.source_date for item in records] == [f"2026-09-{day:02d}" for day in range(6, 1, -1)]
    assert all("future_of_cutoff" not in item.detail for item in registry.opening_prefetch)


@pytest.mark.parametrize("draft", [
    f"你此前记录：{NUMERIC_PRIOR}（E1）。",
    f"你此前纠偏：{NUMERIC_PRIOR}（E1）。",
    f"你此前的纠偏是：{NUMERIC_PRIOR}（E1）。",
    f"用户自己的记录是：{NUMERIC_PRIOR}（E1）。",
    "你原来的要求是：客户验证如果连续3日没有达标，应先暂缓形成结论（E1）。",
    f"你此前纠偏：{NUMERIC_PRIOR}。",
    "- 若**连续3日客户验证进度未达标**，就应暂缓下结论。",
    "- 配套的纠偏规则：**若连续 3 日客户验证进度未达标，就应暂缓下结论**。",
])
def test_bound_personal_number_uses_contract_and_original_not_prefix(tmp_path, monkeypatch, draft):
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl",
        correction=NUMERIC_PRIOR, themes=["长电科技"],
    )
    frame, context, outcome, _ = _episode(tmp_path, monkeypatch, draft=draft)
    assert outcome.usage.invalid_actions == 0
    structural = verify_episode_outcome(context.contract, outcome)
    assert structural.verified_status == "completed"
    assert not numeric_condition_unsupported(structural)
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    semantic = SemanticEpisodeVerifier().verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(30),
    )
    assert semantic.status == "completed" and semantic.public_answer == draft


@pytest.mark.parametrize("draft", [
    "此前的要求是连续5日客户验证未达标就暂缓结论（E1）。",
    "此前的要求是连续3周客户验证未达标就暂缓结论（E1）。",
    "此前的要求是股价达到3元就暂缓结论（E1）。",
    "此前的要求是连续3日客户验证未达标就暂缓结论（E2）。",
    "此前的要求是连续5日客户验证未达标就暂缓结论。",
    "此前的要求是连续3周客户验证未达标就暂缓结论。",
    "此前的要求是股价达到3元就暂缓结论。",
])
def test_personal_number_requires_matching_unit_and_bound_original(tmp_path, monkeypatch, draft):
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl", correction=NUMERIC_PRIOR, themes=["长电科技"],
    )
    _, context, outcome, _ = _episode(tmp_path, monkeypatch)
    structural = verify_episode_outcome(context.contract, replace(outcome, draft=draft))
    assert numeric_condition_unsupported(structural)


@pytest.mark.parametrize("binding_state", ["unbound", "gap", "wrong-hash"])
def test_no_inline_citation_does_not_support_unqualified_binding(tmp_path, monkeypatch, binding_state):
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl", correction=NUMERIC_PRIOR, themes=["长电科技"],
    )
    _, context, outcome, _ = _episode(tmp_path, monkeypatch, draft=f"你曾纠偏：{NUMERIC_PRIOR}。")
    binding = outcome.bindings[0]
    binding = (replace(binding, gap="缺少可用记录") if binding_state == "gap" else
               replace(binding, evidence_hashes=() if binding_state == "unbound" else ("wrong-hash",)))
    structural = verify_episode_outcome(context.contract, replace(outcome, bindings=(binding,)))
    assert structural.verified_status != "completed"
    assert numeric_condition_unsupported(structural)


@pytest.mark.parametrize(("citation", "unsupported"), [("", False), ("（E1）", True), ("（E2）", False), ("（E3）", True)])
def test_explicit_citation_narrows_unique_recall_slot_binding(tmp_path, monkeypatch, citation, unsupported):
    from intelligence.services.agent_research import evidence_content_hash

    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl", correction=NUMERIC_PRIOR, themes=["长电科技"],
    )
    _, context, outcome, _ = _episode(tmp_path, monkeypatch)
    second = replace(outcome.evidence[0], detail="若连续7日客户验证进度未达标，就应暂缓下结论")
    second = replace(second, content_hash=evidence_content_hash(second))
    outcome = replace(
        outcome, evidence=(*outcome.evidence, second),
        bindings=(replace(outcome.bindings[0], evidence_hashes=(outcome.evidence[0].content_hash, second.content_hash)),),
        draft=f"若连续7日客户验证进度未达标，就应暂缓下结论{citation}。",
    )
    assert numeric_condition_unsupported(verify_episode_outcome(context.contract, outcome)) is unsupported


def test_personal_number_rejects_invalid_original_hash(tmp_path, monkeypatch):
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl", correction=NUMERIC_PRIOR, themes=["长电科技"],
    )
    _, context, outcome, _ = _episode(tmp_path, monkeypatch, draft=f"你曾纠偏：{NUMERIC_PRIOR}（E1）。")
    tampered = replace(outcome.evidence[0], content_hash="forged-original-hash")
    outcome = replace(
        outcome, evidence=(tampered,),
        bindings=(replace(outcome.bindings[0], evidence_hashes=(tampered.content_hash,)),),
    )
    structural = verify_episode_outcome(context.contract, outcome)
    assert structural.verified_status != "completed"
    assert numeric_condition_unsupported(structural)


def test_same_number_reversed_condition_still_reaches_existing_semantic_judge(tmp_path, monkeypatch):
    corrections.record_correction(
        tmp_path / "users" / "alice" / "corrections.jsonl", correction=NUMERIC_PRIOR, themes=["长电科技"],
    )
    draft = "你的旧要求是连续3日客户验证未达标就应立即下结论（E1）。"
    frame, context, outcome, _ = _episode(tmp_path, monkeypatch, draft=draft)
    structural = verify_episode_outcome(context.contract, outcome)
    assert not numeric_condition_unsupported(structural), "numeric identity alone cannot establish meaning"
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    judge = _judge(False, rejected=(1,))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(30),
    )
    assert judge.calls and NUMERIC_PRIOR in json.dumps(judge.calls, ensure_ascii=False)
    assert "立即下结论" not in result.public_answer
    assert result.status != "completed"


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
    calls = []

    def controller(messages):
        calls.append(messages)
        return financial_controller_response()

    decision = decide_turn(query, resolver=SubjectResolver(), llm_complete=controller)
    assert len(calls) == 1
    assert "route_id,confidence,reason,user_goal,assumptions,ambiguities" in calls[0][0]["content"]
    assert "personal_records_only" not in calls[0][0]["content"]
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
        return response if len(calls) == 1 else financial_controller_response()

    decision = decide_turn(
        "长电科技，结合我之前的判断，评估现在的上涨空间。",
        resolver=SubjectResolver(), llm_complete=complete,
    )
    mixed = response[0] == json.dumps({"personal_records_only": False})
    assert len(calls) == (2 if mixed else 1)
    if mixed:
        assert "route_id,confidence,reason,user_goal,assumptions,ambiguities" in calls[1][0]["content"]
    assert decision.task_frame.question_type == "stock_deep_dive"
    context = build_episode_context(decision.task_frame, task_id="mixed")
    assert any(item.required and item.grounding_mode == "evidence" for item in context.contract.required_outputs)
    assert not next(item for item in context.contract.required_outputs if item.output_id == "prior_recall").required


@pytest.mark.parametrize(("response", "reason"), [
    (("", None, ""), "personal_recall_empty_response"),
    (("  ", None, ""), "personal_recall_empty_response"),
    (("{", None, ""), "personal_recall_unparsable_response"),
    ((json.dumps({"personal_records_only": 1}), None, ""), "personal_recall_invalid_schema"),
    # Existing provider normalization intentionally keeps this detail outside
    # the judge's transient-failure allowlist; preserve it without broadening.
    ((None, None, "LLM 调用失败（LLMDeadlineExceeded）"), "personal_recall_provider_unavailable"),
])
def test_arbitration_failure_is_visible_without_second_controller_call(tmp_path, monkeypatch, response, reason):
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wiki"))
    calls = []

    def controller(messages, **kwargs):
        calls.append((messages, kwargs))
        return response

    monkeypatch.setattr(llm_refine, "complete", controller)
    decision = decide_turn("只回顾我此前的偏好。")
    assert len(calls) == 1
    assert decision.task_frame.question_type != "personal_memory_recall"
    assert decision.to_dict()["llm_failure_reason"] == reason
    assert decision.llm_failure_detail


def test_successful_false_unanchored_arbitration_continues_original_full_controller(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wiki"))
    calls = []

    def controller(messages, **kwargs):
        calls.append(messages)
        if "personal_records_only" in messages[0]["content"]:
            return route_response("mixed")
        # Deliberately use the production prompt's current six-key schema. Its
        # existing parser/repair behavior must be identical with or without the
        # optional recall classification, even where that behavior is imperfect.
        return json.dumps({"route_id": "general_finance", "confidence": 0.9,
                           "reason": "混合诉求", "user_goal": "应用过往偏好",
                           "assumptions": [], "ambiguities": []}), None, ""

    query = "只回顾我此前的偏好，并告诉我如何应用。"
    monkeypatch.setattr(llm_refine, "complete", controller)
    actual = decide_turn(query)
    actual_calls = list(calls)
    calls.clear()
    monkeypatch.setattr("intelligence.services.turn_controller.references_personal_prior", lambda _: False)
    baseline = decide_turn(query)
    assert len(actual_calls) == len(calls) + 1
    assert actual_calls[1:] == calls
    assert actual.to_dict() == baseline.to_dict()


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
    assert decision.llm_failure_reason == "personal_recall_timeout"


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


@pytest.mark.parametrize("content", ["", '{"personal_records_only":true}'])
def test_controller_real_http_payload_preserves_thinking_budget_and_empty_response_trace(monkeypatch, content):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    payloads = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payloads.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"choices": [{"message": {"content": content},
                                            "finish_reason": "stop" if content else "length"}],
                               "usage": {"prompt_tokens": 173, "completion_tokens": 64}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("LLM_REASONING_EFFORT_BY_MODEL", "glm-5.3-flash:low")
    monkeypatch.delenv("LLM_COMPAT_PAYLOAD", raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        provider = llm_refine.LLMProvider(
            name="test", model="glm-5.3-flash", base_url=f"http://127.0.0.1:{server.server_port}", api_key="test",
        )
        monkeypatch.setattr(llm_refine, "detect_providers", lambda *_: (provider,))
        with llm_refine.call_ledger_scope() as ledger:
            decision = decide_turn(RECALL, resolver=SubjectResolver(), deadline=ResearchDeadline.from_timeout(2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert len(payloads) == 1
    assert payloads[0]["max_tokens"] == 512
    assert payloads[0]["thinking"] == {"type": "enabled"}
    assert payloads[0]["reasoning_effort"] == "low"
    assert len(ledger.summary()["records"]) == 1
    if content:
        assert decision.task_frame.question_type == "personal_memory_recall"
        assert not decision.llm_failure_reason
    else:
        assert decision.task_frame.question_type == "stock_deep_dive"
        assert decision.llm_failure_reason == "personal_recall_empty_response"


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
    calls = []

    def unavailable(messages):
        calls.append(messages)
        return None, None, "fixture unavailable"

    decision = decide_turn(
        "For ACME, recall my earlier research checklist; only my saved notes.",
        resolver=SubjectResolver("ACME"), llm_complete=unavailable,
    )
    assert len(calls) == 1
    assert "personal_records_only" not in calls[0][0]["content"]
    assert decision.llm_failure_reason
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
