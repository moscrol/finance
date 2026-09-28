"""D6 author-side contracts; offline writer/judges, not live P7 acceptance."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import re
from uuid import uuid4

import pytest

from intelligence.tests.material_judge_helpers import material_judge_report

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, ModelTurn, OutputEvidenceBinding
from intelligence.services.conversation_materials import collect_material_turn_history
from intelligence.services.conversation_store import Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input, validate_episode_finish
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier, _judge_system_prompt, _mismatched_path_trend_indexes,
    _mismatched_weekday_indexes, _novel_numeric_condition_indexes, recheck_material_public_delivery,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.material_grounding import ClaimSourceBinding, MaterialAnchor, material_grounding_payload
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.query_ledger import query_ledger_scope
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import ResearchDeadline, ResearchTaskContract
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolRunResult, ToolSpec
from intelligence.services.turn_controller import decide_turn

QUESTION = "只依据以下材料回答。\n\n「甲收入100万元，新增订单20万元。」\n\n1. 订单占收入比例是多少？"
FACT = "订单占收入比例为20÷100=20%。"
OLD = "若订单增长达到123456万元便可升级。"
BOUNDARY = "\n\n## 证据边界\n结论仅在用户材料前提内成立。"


def setup(*, history=False):
    if history:
        records = (
            Message("user-old", "conv", "user", QUESTION, "2026-09-16", "completed"),
            Message("assistant-old", "conv", "assistant", OLD, "2026-09-16", "completed"),
        )
        frame = decide_turn("继续上一轮。\n\n1. 上轮订单占比的回答有哪些错误？", conversation_materials=collect_material_turn_history(records)).task_frame
    else:
        frame = understand_query(QUESTION).task_frame
    context = build_episode_context(frame, task_id="d6-" + uuid4().hex)
    assert context.contract.material_contract.data_scope == "material_only"
    return frame, context


def fact_claim(context, text=FACT):
    material = context.contract.material_grounding.materials[0]
    return ClaimSourceBinding(text, "material_fact", (MaterialAnchor(material.material_id, material.text),))


def outcome(context, claims=None, *, text=FACT, evidence=(), hashes=()):
    claims = claims if claims is not None else (fact_claim(context, text),)
    return AgentOutcome(
        task_frame_hash=context.contract.task_frame_hash, status="completed",
        draft="## q1\n" + text + BOUNDARY, evidence=evidence, traces=(), gaps=(),
        stop_reason="model_finish", usage=AgentUsage(), events=(EpisodeEvent(1, "task", {"task_frame_hash": context.contract.task_frame_hash}),),
        bindings=(OutputEvidenceBinding("answer_q1", hashes, claims=claims), OutputEvidenceBinding("evidence_boundary", (), basis="user_premise")),
    )


def finish(value):
    return {"status": value.status, "draft": value.draft, "gaps": list(value.gaps), "bindings": [b.to_dict() for b in value.bindings]}


def verify(frame, context, value, judge):
    return SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verify_episode_outcome(context.contract, value),
        deadline=ResearchDeadline.from_timeout(60),
    )


def passing(request):
    assert "material_grounding" in request
    assert "claims" in request["output_bindings"][0]
    assert "material_fact" in _judge_system_prompt(request)
    return material_judge_report(request)


def test_real_material_calculation_completes_without_fabricating_tool_evidence():
    frame, context = setup()
    value = outcome(context)
    parsed = validate_episode_finish(finish(value), context=context, evidence=())
    assert parsed.bindings == value.bindings
    assert verify_episode_outcome(context.contract, value).verified_status == "completed"
    result = verify(frame, context, value, passing)
    assert result.status == "completed" and result.judge_status == "passed"
    assert FACT in result.public_answer and value.evidence == ()
    assert context.contract.material_contract.authenticity == "real"


@pytest.mark.parametrize("mutation", ["unknown_material", "wrong_quote", "label_only", "unbound_second", "wrong_output", "external_binding"])
def test_material_only_rejects_unanchored_or_misbound_facts_even_with_passing_judge(mutation):
    frame, context = setup()
    value = outcome(context)
    claim = value.bindings[0].claims[0]
    if mutation == "unknown_material":
        claim = replace(claim, material_anchors=(MaterialAnchor("invented", "100"),))
    elif mutation == "wrong_quote":
        claim = replace(claim, material_anchors=(replace(claim.material_anchors[0], quote="甲利润500万元"),))
    elif mutation == "label_only":
        claim = replace(claim, material_anchors=())
    if mutation == "unbound_second":
        value = replace(value, draft=value.draft.replace(FACT, FACT + "实际市占率80%。"))
    if mutation == "external_binding":
        evidence = AgentEvidence("finance_query", "市场", "利润500", "cached-local-looking", content_hash="external", io_effect="external_or_mixed")
        value = replace(value, evidence=(evidence,), bindings=(replace(value.bindings[0], evidence_hashes=("external",)), value.bindings[1]))
    value = replace(value, bindings=(replace(value.bindings[0], claims=(claim,)), value.bindings[1]))
    if mutation == "wrong_output":
        value = replace(value, bindings=(OutputEvidenceBinding("answer_q1", (), gap="未绑定"), replace(value.bindings[1], claims=(claim,))))
    with pytest.raises(ValueError):
        validate_episode_finish(finish(value), context=context, evidence=value.evidence)
    calls = []
    result = verify(frame, context, value, lambda request: (calls.append(request), passing(request))[1])
    assert result.status != "completed" and not calls


def test_writer_judge_and_contract_restore_share_original_source_catalogue():
    frame, context = setup(history=True)
    writer = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))["material_grounding"]
    value = outcome(context)
    calls = []
    verify(frame, context, value, lambda request: (calls.append(request), passing(request))[1])
    canonical = material_grounding_payload(context.contract)
    assert calls[0]["material_grounding"] == {key: value for key, value in canonical.items() if key not in {"finish_format", "rule"}}
    assert "finish_format" in writer
    assert all(OLD not in row["text"] for row in writer["sources"] if row["ref"].startswith("M"))
    assert [row for row in writer["sources"] if row["ref"].startswith("H")] == [
        {"ref": "H1", "kind": "historical_assistant_statement", "text": OLD},
    ]
    assert calls[0]["material_grounding"]["historical_assistant_statements"][0]["source_message_id"] == "assistant-old"
    restored = ResearchTaskContract.from_dict(json.loads(json.dumps(context.contract.to_dict())))
    assert restored == context.contract
    damaged = json.loads(json.dumps(context.contract.to_dict()))
    damaged["material_grounding"]["materials"][0]["text"] = "tampered"
    with pytest.raises(ValueError):
        ResearchTaskContract.from_dict(damaged)


def historical_claim(text):
    return ClaimSourceBinding(text, "historical_assistant_statement", old_answer_coordinate="assistant-old", historical_quote=OLD, basis="assistant_judgment")


def test_historical_retraction_is_allowed_without_material_anchor_or_numeric_purity_false_positive():
    frame, context = setup(history=True)
    text = "撤回旧答的说法（若订单增长达到123456万元便可升级），它不是当前事实。"
    value = outcome(context, (historical_claim(text),), text=text)
    validate_episode_finish(finish(value), context=context, evidence=())
    result = verify(frame, context, value, passing)
    assert result.status == "completed" and text in result.public_answer
    full = replace(context.contract, material_contract=replace(context.contract.material_contract, data_scope="full"))
    verified = verify_episode_outcome(full, value)
    assert _novel_numeric_condition_indexes([{"index": 1, "text": text}], verified) == ()


def _wrong_weekday_label(day):
    return "周" + "二三四五六日一"[day.weekday()]


@pytest.mark.parametrize("scan,text,detail", [
    (_mismatched_weekday_indexes,
     f"撤回旧答关于9月14日（{_wrong_weekday_label(date(2026, 9, 14))}）的说法（若订单增长达到123456万元便可升级）。",
     "2026-09-14 收盘数据"),
    (_mismatched_path_trend_indexes,
     "撤回旧答「成交额一路下跌」的判断（若订单增长达到123456万元便可升级）。",
     "2026-09-10 成交额100亿；2026-09-11 成交额120亿；2026-09-12 成交额90亿"),
])
def test_calendar_and_path_scans_exempt_only_bound_historical_sentences(scan, text, detail):
    _, context = setup(history=True)
    full = replace(context.contract, material_contract=replace(context.contract.material_contract, data_scope="full"))
    evidence = AgentEvidence("finance_query", "行情", detail, "local", content_hash="dated", io_effect="local_read")
    value = outcome(context, (historical_claim(text),), text=text, evidence=(evidence,), hashes=("dated",))
    sentences = [{"index": 1, "text": text}]
    assert scan(sentences, verify_episode_outcome(full, value)) == ()
    unbound = replace(value, bindings=(replace(value.bindings[0], claims=()), value.bindings[1]))
    assert scan(sentences, verify_episode_outcome(full, unbound)) == (1,)
    forged = replace(value, bindings=(replace(value.bindings[0], claims=(replace(historical_claim(text), historical_quote="从未说过"),)), value.bindings[1]))
    assert scan(sentences, verify_episode_outcome(full, forged)) == (1,)


@pytest.mark.parametrize("mutation", ["wrong_coordinate", "wrong_quote", "material_laundering"])
def test_old_answer_coordinates_cannot_be_forged_or_promoted_to_material(mutation):
    _, context = setup(history=True)
    text = "撤回旧答的升级阈值。"
    claim = historical_claim(text)
    if mutation == "wrong_coordinate":
        claim = replace(claim, old_answer_coordinate="user-old")
    elif mutation == "wrong_quote":
        claim = replace(claim, historical_quote="从未说过的句子")
    else:
        claim = ClaimSourceBinding(text, "material_fact", (MaterialAnchor("assistant-old", OLD),))
    value = outcome(context, (claim,), text=text)
    with pytest.raises(ValueError):
        validate_episode_finish(finish(value), context=context, evidence=())
    assert "answer_q1" in verify_episode_outcome(context.contract, value).missing_outputs


@pytest.mark.parametrize("kind", ["historical_assistant_statement", "reasoning", "premise_declaration"])
def test_semantic_rejection_of_laundered_current_fact_reopens_question_not_meta_exemption(kind):
    frame, context = setup(history=True)
    text = "旧答说订单增长123456万元，因此目前已经满足升级条件。"
    claim = historical_claim(text) if kind == "historical_assistant_statement" else ClaimSourceBinding(text, kind)
    value = outcome(context, (claim,), text=text)
    calls = []
    def reject_mix(request):
        calls.append(request)
        assert request["output_bindings"][0]["claims"][0]["kind"] == kind
        indexes = [row["index"] for row in request["sentences"] if text == row["text"]]
        return material_judge_report(request, rejected=indexes, issues=["历史数字被挪为当前推断，混句拒绝。"])
    result = verify(frame, context, value, reject_mix)
    assert calls and result.status != "completed"
    assert text not in result.public_answer
    assert "answer_q1" in result.verified.missing_outputs


@pytest.mark.parametrize("scope,io_effect,allowed", [("local_only", "local_read", True), ("local_only", "unknown", False), ("local_only", "external_or_mixed", False), ("full", "external_or_mixed", True)])
def test_binding_purity_depends_on_actual_io_not_tool_name_or_freshness(scope, io_effect, allowed):
    frame, context = setup()
    contract = replace(context.contract, material_contract=replace(context.contract.material_contract, data_scope=scope))
    context = replace(context, contract=contract)
    evidence = AgentEvidence("finance_query", "本地缓存", "收入100万元", "local-cache", freshness="current", content_hash="observed", io_effect=io_effect)
    value = outcome(context, (), evidence=(evidence,), hashes=("observed",))
    if allowed:
        validate_episode_finish(finish(value), context=context, evidence=value.evidence)
        assert verify_episode_outcome(contract, value).verified_status == "completed"
    else:
        with pytest.raises(ValueError, match="frozen data scope"):
            validate_episode_finish(finish(value), context=context, evidence=value.evidence)
        assert verify_episode_outcome(contract, value).verified_status == "partial"


class Writer:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append((messages, tools))
        return ModelTurn(json.dumps(finish(self.value), ensure_ascii=False), (), "offline", "")


def test_real_episode_consumes_claim_binding_without_tool_calls():
    frame, context = setup()
    writer = Writer(outcome(context))
    result = ContinuousAgentEpisode(writer).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert result.status == "completed", result.stop_reason
    assert result.bindings[0].claims == writer.value.bindings[0].claims
    assert not result.evidence and len(writer.calls) == 1
    assert writer.calls[0][1] == []
    payload = json.loads(writer.calls[0][0][1]["content"])
    assert payload["material_grounding"]["data_scope"] == "material_only"
    assert verify(frame, context, result, passing).status == "completed"


@pytest.mark.parametrize("mutation", ["quote", "sentence"])
def test_real_adapter_does_not_reopen_repair_after_source_integrity_rejection(mutation):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.runtime.turn_control_core import TurnControlResult

    frame, context = setup()
    value = outcome(context)
    claim = value.bindings[0].claims[0]
    if mutation == "quote":
        claim = replace(claim, material_anchors=(replace(claim.material_anchors[0], quote="材料中不存在"),))
    else:
        claim = replace(claim, text=claim.text.replace("。", "；"))
    value = replace(value, bindings=(replace(value.bindings[0], claims=(claim,)), value.bindings[1]))
    writer = Writer(value)
    requests = []
    result = ContinuousTurnAdapter(
        runtime=GLMAgentRuntime(client=writer), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=lambda request: requests.append(request)),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(writer.calls) == 1 and not requests
    assert result.status != "completed" and FACT not in result.answer
    events = result.private_artifact["outcome"]["events"]
    assert not any(event["kind"] == "repair_reentry" for event in events)
    assert any(event["kind"] == "finish" and event["payload"].get("rejection_code") == "material_source_violation" for event in events)


def test_finalizer_recovery_receives_same_material_grounding_contract():
    frame, context = setup(history=True)
    writer = Writer(outcome(context))
    EpisodeFinalizer(writer).recover(task_frame=frame, context=context, evidence=(), gaps=(), failure_reason="model_exception")
    payload = json.loads(writer.calls[0][0][1]["content"])
    expected = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))["material_grounding"]
    assert payload["material_grounding"] == expected
    assert "material_delivery" in payload


def test_ordinary_task_keeps_material_grounding_absent():
    frame = understand_query("市盈率是什么？").task_frame
    context = build_episode_context(frame, task_id="ordinary-" + uuid4().hex)
    assert "material_grounding" not in context.contract.to_dict()
    assert "material_grounding" not in json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))


@pytest.mark.parametrize("claim", [
    None, [], "fact", {}, {"text": None, "kind": "reasoning"},
    {"text": FACT, "kind": []}, {"text": FACT, "kind": "unknown"},
    {"text": FACT, "kind": "material_fact", "material_anchors": {}},
    {"text": FACT, "kind": "material_fact", "material_anchors": [None]},
    {"text": FACT, "kind": "material_fact", "material_anchors": [{"material_id": 1, "quote": "x"}]},
    {"text": FACT, "kind": "historical_assistant_statement", "historical_quote": None},
    {"text": FACT, "kind": "reasoning", "unexpected": True},
])
def test_malformed_claims_fail_as_protocol_format_errors_not_runtime_exceptions(claim):
    _, context = setup()
    payload = finish(outcome(context))
    payload["bindings"][0]["claims"] = [claim]
    with pytest.raises(ValueError) as error:
        validate_episode_finish(payload, context=context, evidence=())
    assert error.value.code == "bad_claim_binding"
    assert error.value.kind.value == "format"


def test_claim_cannot_bind_only_a_substring_of_a_larger_current_assertion():
    _, context = setup(history=True)
    text = "撤回旧答123456万元的条件，因此当前订单已升级。"
    value = outcome(context, (historical_claim("撤回旧答123456万元的条件"),), text=text)
    # Also check a non-question binding: question-body coverage is not the only guard.
    value = replace(value, bindings=(value.bindings[0], replace(value.bindings[1], claims=value.bindings[0].claims)))
    with pytest.raises(ValueError, match="claim text"):
        validate_episode_finish(finish(value), context=context, evidence=())


@pytest.mark.parametrize("location", ["boundary", "outside", "title", "quote"])
def test_semantic_rejection_cannot_hide_current_facts_outside_question_body(location):
    frame, context = setup()
    text = "据此推理，实际订单已经爆发但尚未联网核验。"
    value = outcome(context)
    if location == "boundary":
        value = replace(value, draft=value.draft + "\n" + text,
                        bindings=(value.bindings[0], replace(value.bindings[1], claims=(ClaimSourceBinding(text, "premise_declaration"),))))
    elif location == "outside":
        value = replace(value, draft=text + "\n" + value.draft)
    elif location == "title":
        value = replace(value, draft=value.draft.replace("## q1", "## q1 " + text))
    else:
        value = replace(value, draft=value.draft.replace(FACT, FACT + "\n> " + text))
    validate_episode_finish(finish(value), context=context, evidence=())
    def reject(request):
        rejected = [row["index"] for row in request["sentences"] if text in row["text"]]
        assert rejected
        return material_judge_report(request, rejected=rejected, issues=["无当前事实来源。"])
    result = verify(frame, context, value, reject)
    assert result.status == "partial" and result.judge_status == "rejected"
    assert result.verified.missing_outputs and text not in result.public_answer


def test_judge_deletion_drops_only_the_rejected_claim_and_keeps_recheck_strict():
    frame, context = setup()
    extra = "该比例按材料口径计算。"
    value = outcome(context, (fact_claim(context), ClaimSourceBinding(extra, "reasoning")), text=FACT + extra)
    validate_episode_finish(finish(value), context=context, evidence=())
    def reject_fact(request):
        indexes = [row["index"] for row in request["sentences"] if row["text"] == FACT]
        return material_judge_report(request, rejected=indexes, issues=["计算错误。"])
    result = verify(frame, context, value, reject_fact)
    assert result.status == "partial" and "answer_q1" in result.verified.missing_outputs
    assert [claim.text for claim in result.verified.outcome.bindings[0].claims] == [extra]
    assert not any("material_source_violation" in issue for issue in result.verified.issues)
    assert FACT not in result.public_answer and extra in result.public_answer
    # Drift the verifier did not cause still fails closed.
    checked = recheck_material_public_delivery(result, projected=result.public_answer.replace(extra, ""))
    assert any("material_source_violation" in issue for issue in checked.verified.issues)
    # Rejecting every answered sentence leaves a well-formed gap binding, never a legal gap.
    def reject_all(request):
        indexes = [row["index"] for row in request["sentences"] if row["text"] in {FACT, extra}]
        return material_judge_report(request, rejected=indexes, issues=["全部拒绝。"])
    emptied = verify(frame, context, value, reject_all)
    binding = emptied.verified.outcome.bindings[0]
    assert binding.claims == () and binding.gap and emptied.verified.missing_outputs == ("answer_q1",)
    assert all(item.status != "legal_gap" for item in emptied.verified.completion.outputs)


@pytest.mark.parametrize("mutation", ["correct", "wrong_result", "missing_input", "unrelated_quote"])
def test_multiple_material_calculation_is_reviewed_for_inputs_and_derivation(mutation):
    frame = understand_query("只依据以下材料回答。\n\n「甲收入100万元。」\n\n「甲新增订单20万元。」\n\n1. 订单占收入比例是多少？").task_frame
    context = build_episode_context(frame, task_id="multi-" + uuid4().hex)
    materials = context.contract.material_grounding.materials
    # P2 keeps the numbered-question residual as one material; anchors are
    # quote-level, so a multi-input calculation lists one exact quote per input.
    material = next(item for item in materials if item.text.startswith("「"))
    quotes = ("「甲收入100万元。」", "「甲新增订单20万元。」")
    assert all(quote in material.text for quote in quotes)
    anchors = tuple(MaterialAnchor(material.material_id, quote) for quote in quotes)
    text = FACT if mutation != "wrong_result" else FACT.replace("=20%", "=50%")
    if mutation == "missing_input":
        anchors = anchors[:1]
    elif mutation == "unrelated_quote":
        anchors = tuple(replace(anchor, quote="甲") for anchor in anchors)
    value = outcome(context, (ClaimSourceBinding(text, "material_fact", anchors),), text=text)
    validate_episode_finish(finish(value), context=context, evidence=())
    calls = []
    def arithmetic_oracle(request):
        # Narrow, independent fixture oracle, not a substitute for the live semantic judge.
        calls.append(request)
        source_texts = {row["material_id"]: row["text"] for row in request["material_grounding"]["materials"]}
        claim = request["output_bindings"][0]["claims"][0]
        quotes = " ".join(a["quote"] for a in claim["material_anchors"] if a["quote"] in source_texts[a["material_id"]])
        revenue = re.search(r"收入(\d+)万元", quotes)
        orders = re.search(r"订单(\d+)万元", quotes)
        answer = re.search(r"=(\d+)%", claim["text"])
        supported = bool(revenue and orders and answer and Decimal(answer[1]) == Decimal(orders[1]) / Decimal(revenue[1]) * 100)
        indexes = [] if supported else [row["index"] for row in request["sentences"] if row["text"] == text]
        return material_judge_report(request, rejected=indexes, issues=[] if supported else ["计算输入或推导不成立。"])
    result = verify(frame, context, value, arithmetic_oracle)
    assert calls
    assert (result.status == "completed") == (mutation == "correct")
    if mutation != "correct":
        assert "answer_q1" in result.verified.missing_outputs and text not in result.public_answer


def test_unnumbered_material_question_has_sources_and_rejects_current_fact_laundering():
    query = "只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？"
    frame = understand_query(query).task_frame
    context = build_episode_context(frame, task_id="unnumbered-" + uuid4().hex)
    value = outcome(context)
    value = replace(value, draft=value.draft.replace("## q1\n", ""),
                    bindings=(replace(value.bindings[0], output_id="direct_answer"), value.bindings[1]))
    assert any("收入100万元" in row.text for row in context.contract.material_grounding.materials)
    validate_episode_finish(finish(value), context=context, evidence=())
    assert verify(frame, context, value, passing).status == "completed"
    text = "当前订单已经爆发但尚未联网核验。"
    value = replace(value, draft=value.draft.replace(FACT, text),
                    bindings=(replace(value.bindings[0], claims=(ClaimSourceBinding(text, "reasoning"),)), value.bindings[1]))
    def reject(request):
        indexes = [row["index"] for row in request["sentences"] if row["text"] == text]
        return material_judge_report(request, rejected=indexes, issues=["标签不能替当前事实背书。"])
    result = verify(frame, context, value, reject)
    assert result.status == "partial" and "direct_answer" in result.verified.missing_outputs
    assert text not in result.public_answer


@pytest.mark.parametrize("mutation", ["delete", "append", "rewrite"])
def test_public_projection_rechecks_exact_claims_after_successful_judge(mutation):
    frame, context = setup()
    result = verify(frame, context, outcome(context), passing)
    assert result.status == "completed"
    projected = result.public_answer.replace(FACT, {"delete": "", "append": FACT + "市场份额80%。", "rewrite": FACT.replace("20%", "50%")}[mutation])
    checked = recheck_material_public_delivery(result, projected=projected)
    assert checked.status == "partial" and "answer_q1" in checked.repair_output_ids
    assert "claims" not in checked.public_answer and "material_id" not in checked.public_answer


@pytest.mark.parametrize("effect,claimed", [("local_read", "unknown"), ("external_or_mixed", "local_read"), ("unknown", "local_read")])
def test_dispatch_stamps_runner_provenance_before_cache_and_serialization(effect, claimed):
    frame = understand_query("今天市场怎么样？").task_frame
    context = build_episode_context(frame, task_id="stamp-" + uuid4().hex, capabilities=("finance_query",))
    evidence = AgentEvidence("finance_query", "测试", "收入100万元", "local-looking", content_hash="stamp", io_effect=claimed)
    calls = []
    def runner(query, context):
        calls.append(query)
        return ToolRunResult((evidence,), "收入100万元", ProviderTrace("offline", "finance_query", "ok"))
    registry = ResearchToolRegistry((ToolSpec("finance_query", "finance_query", "offline", "local", "stable", runner, io_effect=effect),))
    with query_ledger_scope():
        first = registry.execute("finance_query", {"query": "x"}, context=context, step_id="1")
        second = registry.execute("finance_query", {"query": "x"}, context=context, step_id="2")
    assert len(calls) == 1 and first.evidence == second.evidence
    assert first.evidence[0].io_effect == effect and evidence.io_effect == claimed
    _, material_context = setup()
    value = outcome(material_context, evidence=first.evidence)
    raw = json.loads(json.dumps(value.to_dict()))
    restored = AgentEvidence(**raw["evidence"][0])
    assert restored.io_effect == effect
    assert tuple(ClaimSourceBinding.from_dict(row) for row in raw["bindings"][0]["claims"]) == value.bindings[0].claims


@pytest.mark.parametrize("numbered", [True, False])
@pytest.mark.parametrize("real_runtime", [False, True])
def test_rejected_material_claim_can_be_rewritten_with_fresh_binding_and_same_sources(numbered, real_runtime):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession

    frame, context = setup()
    output_id = "answer_q1" if numbered else "direct_answer"
    if not numbered:
        frame = understand_query("只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？").task_frame
        context = build_episode_context(frame, task_id="unnumbered-repair-" + uuid4().hex)
    good = outcome(context)
    text = "订单占收入比例为50%。"
    bad = outcome(context, text=text)
    if not numbered:
        def unnumber(value):
            return replace(value, draft=value.draft.replace("## q1\n", ""),
                           bindings=(replace(value.bindings[0], output_id=output_id), value.bindings[1]))
        good, bad = unnumber(good), unnumber(bad)
    resumes, requests = [], []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                assert goal.missing_answer_elements == (output_id,)
                assert goal.remaining_calls == 0 and not goal.reopen_tools
                return replace(good, events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=bad, resume_callback=resume)
    class RepairWriter(Writer):
        def complete(self, *, messages, tools, timeout):
            self.value = good if self.calls else bad
            assert tools == []
            return super().complete(messages=messages, tools=tools, timeout=timeout)
    writer = RepairWriter(bad)
    def judge(request):
        requests.append(request)
        rejected = [row["index"] for row in request["sentences"] if row["text"] == text]
        return material_judge_report(request, rejected=rejected, issues=["计算错误。"] if rejected else [])
    result = ContinuousTurnAdapter(
        runtime=GLMAgentRuntime(client=writer) if real_runtime else Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    if real_runtime:
        assert len(writer.calls) == 2
        events = result.private_artifact["outcome"]["events"]
        goals = [json.loads(event["payload"]["content"]) for event in events
                 if event["kind"] == "model_input" and event["payload"].get("source") == "repair_goal"]
        assert len(goals) == 1
        assert goals[0]["missing_answer_elements"] == [output_id]
        assert goals[0]["remaining_calls"] == 0 and not goals[0]["reopen_tools"]
        assert all(not event["payload"].get("unreachable_without_tools") for event in events if event["kind"] == "repair_goal")
    else:
        assert len(resumes) == 1
    assert len(requests) == 2, result.private_artifact
    assert requests[0]["material_grounding"] == requests[1]["material_grounding"]
    assert requests[0]["output_bindings"][0]["claims"] != requests[1]["output_bindings"][0]["claims"]
    assert result.status == "completed" and FACT in result.answer and text not in result.answer
    assert result.private_artifact["semantic_verifier"]["repair_output_ids"] == []


@pytest.mark.parametrize("case", [
    "material_only", "local_only", "full", "ordinary", "uncertain",
    "source_violation", "unknown_output", "mandatory_capability", "rejected_claim",
    "terminal_material_source_violation", "terminal_forged_hash",
])
def test_unnumbered_rewrite_permission_requires_settled_scope_and_only_delivery_gaps(case):
    from intelligence.services.episode_issues import Issue, IssueCode
    from intelligence.services.repair_coordinator import classify_repair_failure

    frame = understand_query("只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？").task_frame
    context = build_episode_context(frame, task_id="rewrite-permission-" + uuid4().hex)
    value = replace(outcome(context), draft=BOUNDARY, bindings=(
        OutputEvidenceBinding("direct_answer", (), gap="回答尚未交付"),
        OutputEvidenceBinding("evidence_boundary", (), basis="user_premise"),
    ))
    structural = verify_episode_outcome(context.contract, value)
    assert structural.missing_outputs == ("direct_answer",)
    contract = context.contract
    if case in {"local_only", "full"}:
        contract = replace(contract, material_contract=replace(contract.material_contract, data_scope=case))
    elif case == "ordinary":
        contract = replace(contract, material_contract=None)
    elif case == "uncertain":
        contract = replace(contract, material_contract=replace(contract.material_contract, classification="boundary_uncertain"))
    structural = replace(structural, contract=contract)
    if case == "source_violation":
        structural = replace(structural, issue_items=(*structural.issue_items,
            Issue(IssueCode.MATERIAL_SOURCE_VIOLATION, "direct_answer", "forged anchor")))
    elif case == "mandatory_capability":
        structural = replace(structural, mandatory_missing_capabilities=("finance_query",))
    elif case.startswith("terminal_"):
        value = replace(value, stop_reason="invalid_model_finish", events=(*value.events,
            EpisodeEvent(2, "finish", {"rejection_code": case.removeprefix("terminal_")})))
        structural = replace(structural, outcome=value)
    shape = classify_repair_failure(
        value, structural,
        missing_outputs=("invented_output",) if case == "unknown_output" else structural.missing_outputs,
        rejected_claims=("unresolved_claim",) if case == "rejected_claim" else (),
        semantic_gap_outputs=(),
    )
    assert shape.input_only_rewrite is (case == "material_only")
    assert not shape.cold_restart


def test_repair_writer_reads_the_rejected_sentence_and_reason_not_a_bare_index():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession

    frame, context = setup()
    bad = "订单增速明显高于行业平均。"
    material_id = context.contract.material_grounding.materials[0].material_id
    reason = f"该句带入材料之外的行业平均前提，{material_id} 里没有行业数据。"
    value = outcome(context, claims=(fact_claim(context), ClaimSourceBinding(bad, "reasoning")))
    value = replace(value, draft="## q1\n" + FACT + "\n" + bad + BOUNDARY)
    goals = []

    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                goals.append(goal)
                return replace(outcome(context), events=(*previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=value, resume_callback=resume)

    def judge(request):
        indexes = [row["index"] for row in request["sentences"] if row["text"] == bad]
        report = material_judge_report(request, rejected=indexes, issues=["外部前提不得写进材料结论。"])
        for row in report.get("material_claim_checks", []):
            if not row["supported"]:
                row["reason"] = reason
        return report

    result = ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(goals) == 1 and result.status == "completed"
    carried = goals[0].rejected_claim_notes
    assert len(carried) == 1 and carried[0].startswith("claim_index:")
    assert bad in carried[0] and "行业平均前提" in carried[0]
    assert material_id not in carried[0] and material_id.casefold() not in carried[0].casefold()
    assert bad not in result.answer and FACT in result.answer
    # 带给作者的话真的进了 REPAIR_GOAL 提示（文案仍由 harness 组装）。
    from intelligence.services.research_harness import FinanceResearchHarness
    prompt = json.loads(FinanceResearchHarness().repair_goal_message(goals[0], tools_open=False))
    assert prompt["rejected_claim_notes"] == list(carried)


@pytest.mark.parametrize("judge_outage", [False, True])
def test_unnumbered_final_projection_and_judge_outage_cannot_publish_completed(monkeypatch, judge_outage):
    from intelligence.runtime import continuous_turn_adapter as adapter_module
    from intelligence.runtime.turn_control_core import TurnControlResult
    from intelligence.services.episode_session import CallbackEpisodeSession

    frame = understand_query("只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？").task_frame
    context = build_episode_context(frame, task_id="unnumbered-projection-" + uuid4().hex)
    value = outcome(context)
    value = replace(value, draft=FACT + BOUNDARY,
                    bindings=(replace(value.bindings[0], output_id="direct_answer"), value.bindings[1]))
    resumes, requests = [], []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                resumes.append(goal)
                pytest.fail("projection after repair or judge outage must not start a new rewrite")
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=value, resume_callback=resume)
    def judge(request):
        requests.append(request)
        if judge_outage:
            raise ValueError("offline judge outage")
        return passing(request)
    if not judge_outage:
        # This projection runs after the repair loop's public-text recheck.
        monkeypatch.setattr(adapter_module, "_with_calendar_disclosure", lambda answer, _frame: answer.replace(FACT, ""))
    result = adapter_module.ContinuousTurnAdapter(
        runtime=Runtime(), runtime_name="continuous_glm", mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: ResearchToolRegistry(()),
        semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge),
    ).handle(frame=frame, control=TurnControlResult(
        task_frame=frame, execution_route=frame.question_type, terminal_kind="research",
        needs_retrieval=False, capabilities=(), contract_required=True,
    ))
    assert len(requests) == 1 and not resumes
    assert result.status != "completed" and FACT not in result.answer
    semantic = result.private_artifact["semantic_verifier"]
    if judge_outage:
        assert semantic["pending_rejudge"] is True and semantic["repair_output_ids"] == []
    else:
        assert "direct_answer" in semantic["repair_output_ids"]
