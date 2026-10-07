"""User time authority through the production control and evidence seams."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import socket
from uuid import uuid4

import duckdb
import pytest

from intelligence.runtime.turn_control_core import project_turn_decision
from intelligence.services import llm_refine
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.query_resolution import QueryResolution
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.task_frame import TaskFrame
from intelligence.services.temporal_contract import TemporalContract, TemporalSource, compile_temporal_contract, message_digest
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolRunResult, ToolSpec
from intelligence.services.turn_controller import decide_turn


QUESTION = "请复盘2026年9月30日的A股：今天的上涨更像普涨修复，还是少数主线集中带动？用关键数据说明主线强弱，并给出足以推翻你判断的反证。只使用截至当日可见的信息，缺数就明确说缺。"
TODAY = date(2026, 10, 7)
SENTINEL = "十月一日越界哨兵987654"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch, tmp_path):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("temporal tests must not use sockets or live models")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for name in ("synthesize", "synthesize_messages", "synthesize_messages_stream", "complete"):
        monkeypatch.setattr(llm_refine, name, forbidden)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))


class LocalResolver:
    def resolve(self, query):
        return QueryResolution(understand_query(query), None)


def _control(query=QUESTION):
    decision = decide_turn(
        query, resolver=LocalResolver(),
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
        today=TODAY,
    )
    assert decision.task_frame is not None
    return project_turn_decision(decision, task_frame=decision.task_frame)


def _context(query=QUESTION):
    control = _control(query)
    return build_episode_context(
        control.task_frame, task_id=f"temporal-offline:{uuid4()}", capabilities=("news_search",),
        today=TODAY.isoformat(), latest_data_date=TODAY.isoformat(), timeout=30,
    )


def _sentinel_registry(tmp_path):
    db_path = tmp_path / "canonical.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute((Path(__file__).parents[2] / "market_feature_store/schema.sql").read_text())
    con.execute("insert into fact_market_daily (trade_date, amount_ma20) values ('2026-10-01', 987654)")
    con.close()

    def runner(_query, context):
        with duckdb.connect(str(db_path), read_only=True) as con:
            row = con.execute("select trade_date, amount_ma20 from fact_market_daily").fetchone()
        item = AgentEvidence(
            tool="news_search", title=SENTINEL, detail=f"未来数值={row[1]}",
            source="offline-fixture", source_date=str(row[0]), evidence_tier="news",
        )
        return ToolRunResult(
            (item,), SENTINEL + "原始正文", ProviderTrace("fixture", "sentinel", "success", result_count=1),
            query_basis={"preview": SENTINEL},
        )

    return ResearchToolRegistry((ToolSpec("news_search", "news_search", "fixture", "local", "current", runner),))


def _consume(registry, context):
    observation = registry.execute("news_search", {"query": "离线核验"}, context=context, step_id="sentinel:1")
    projection = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=observation.evidence, seen_prose=set(),
    )
    return observation, json.loads(projection.model_content)


@pytest.mark.parametrize(("query", "expected"), [
    (QUESTION, "2026-09-30"),
    ("复盘2026年8月12日的A股，只使用截至当日可见的信息。", "2026-08-12"),
    ("复盘2026年9月28日至2026年9月30日的A股，只使用截至该区间结束日可见的信息。", "2026-09-30"),
])
def test_controller_factory_binds_relative_cutoff(query, expected):
    assert _context(query).information_cutoff.as_of_date.isoformat() == expected


def test_relative_cutoff_prevents_future_content_at_real_model_projection(tmp_path):
    observation, model = _consume(_sentinel_registry(tmp_path), _context())
    assert not observation.evidence
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)


def test_explicit_cutoff_withholds_all_future_in_general_research(tmp_path):
    context = replace(_context(), information_cutoff=InformationCutoff(date(2026, 9, 30), "requested"))
    observation, model = _consume(_sentinel_registry(tmp_path), context)
    assert not observation.evidence
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)
    assert "不是源里没有" in model["observation"]


@pytest.mark.parametrize(("query", "target", "cutoff", "origin"), [
    (QUESTION, ("2026-09-30", "2026-09-30"), "2026-09-30", "relative_target"),
    ("复盘9/30的A股，只使用截至当日的信息", ("2026-09-30", "2026-09-30"), "2026-09-30", "relative_target"),
    ("复盘2026年9月28日至30日的A股，只用截至区间结束日的信息", ("2026-09-28", "2026-09-30"), "2026-09-30", "relative_target"),
    ("复盘9/28至9/30的A股，只用截至区间结束日的信息", ("2026-09-28", "2026-09-30"), "2026-09-30", "relative_target"),
    ("复盘2026年9月30日的A股，结合截至今天的信息", ("2026-09-30", "2026-09-30"), "2026-10-07", "runtime_relative"),
    ("复盘2026年9月30日的A股，只用截至2026年9月29日的信息", ("2026-09-30", "2026-09-30"), "2026-09-29", "explicit_user"),
    ("复盘2026年9月30日的A股，只用截至2026年10月7日的信息", ("2026-09-30", "2026-09-30"), "2026-10-07", "explicit_user"),
    ("站在2026-09-30收盘，分析A股", ("2026-09-30", "2026-09-30"), "2026-09-30", "explicit_user"),
    ("分析瑞华泰截至今天的信息", None, "2026-10-07", "runtime_relative"),
    ('解释这句话：「截至2026年9月30日的信息才可使用」。', None, None, "none"),
    ("不要把资料范围截止到2026年9月30日，请分析A股", None, None, "none"),
    ("涨幅7.16%说明什么", None, None, "none"),
    ("复盘2026年9月30日A股", ("2026-09-30", "2026-09-30"), None, "none"),
])
def test_compiler_separates_target_from_information_permission(query, target, cutoff, origin):
    from intelligence.services.temporal_contract import compile_temporal_contract

    contract = compile_temporal_contract(query, today=TODAY, message_id="real-user")
    actual = (contract.market_target.start, contract.market_target.end) if contract.market_target else None
    assert actual == target
    assert (contract.information_cutoff, contract.cutoff_origin, contract.errors) == (cutoff, origin, ())


@pytest.mark.parametrize("query", [
    "比较2026年8月12日和2026年9月30日A股，只用截至当日的信息",
    "复盘2026年9月31日A股，只用截至当日的信息",
    "复盘2026年9月30日至28日A股，只用截至区间结束日的信息",
    "复盘2026年9月30日A股，只用截至当日的信息；资料截至2026年9月29日",
    "复盘2026年9月30日A股，只用截至2026年9月31日的信息",
    '复盘A股\n```\n只用截至2026年9月30日的信息',
])
def test_invalid_time_authority_clarifies_before_resolver_or_model(query):
    class ForbiddenResolver:
        def resolve(self, *_args):
            raise AssertionError("invalid authority must stop before resolution")

    decision = decide_turn(query, resolver=ForbiddenResolver())
    assert decision.lane == "clarify"
    assert decision.capabilities == ()
    assert decision.task_frame.temporal_contract.errors


def test_factory_injected_cutoff_can_only_narrow_and_errors_refuse_context():
    frame = _control().task_frame
    for injected, expected in [(date(2026, 10, 7), "2026-09-30"), (date(2026, 9, 29), "2026-09-29")]:
        context = build_episode_context(
            frame, task_id=str(uuid4()), today=TODAY.isoformat(),
            information_cutoff=InformationCutoff(injected, "requested"),
        )
        assert context.information_cutoff.as_of_date.isoformat() == expected
        assert context.temporal_contract is frame.temporal_contract
    from intelligence.services.temporal_contract import TemporalContract

    invalid = replace(frame, temporal_contract=TemporalContract(errors=("权限不明",)))
    with pytest.raises(ValueError, match="temporal clarification"):
        build_episode_context(invalid, task_id=str(uuid4()))


@pytest.mark.parametrize("injected_factory", [False, True])
def test_real_continuous_adapter_clamps_factory_before_shared_model_projection(tmp_path, injected_factory):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter

    captured = []
    registry = _sentinel_registry(tmp_path)

    class ProbeRuntime:
        def run(self, *, task_frame, context, registry):
            observation, model = _consume(registry, context)
            captured.append((task_frame, context, observation, model))
            raise RuntimeError("offline model boundary probe completed")

    class ForbiddenVerifier:
        def verify(self, **_kwargs):
            raise AssertionError("probe must stop before verification/models")

    def late_factory(frame, **kwargs):
        context = build_episode_context(frame, **kwargs)
        return replace(context, information_cutoff=InformationCutoff(TODAY, "runtime_default"),
                       contract=replace(context.contract, timeframe=TODAY.isoformat()))

    control = _control()
    result = ContinuousTurnAdapter(
        runtime=ProbeRuntime(), semantic_verifier=ForbiddenVerifier(), mode="on",
        context_factory=late_factory if injected_factory else build_episode_context,
        registry_factory=lambda *_args, **_kwargs: registry,
        today=TODAY.isoformat(), latest_data_date=TODAY.isoformat(),
    ).handle(frame=control.task_frame, control=control)
    assert result.status == "failed"  # Probe stop is not a published answer.
    assert len(captured) == 1
    frame, context, observation, model = captured[0]
    assert context.temporal_contract is frame.temporal_contract
    assert context.information_cutoff == InformationCutoff(date(2026, 9, 30), "requested")
    assert context.contract.timeframe == "2026-09-30"
    assert not observation.evidence
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)


def _prepare_turn(conversations, runs, conversation_id, query):
    conversation = conversations.load_conversation(conversation_id)
    run = runs.create_run(query, "ask", session_id=conversation_id, parent_run_id=conversation.last_run_id)
    user = conversations.append_message(conversation_id, "user", query, run_id=run.run_id)
    assistant = conversations.append_message(conversation_id, "assistant", "", status="pending", run_id=run.run_id)
    conversations.update_summary(conversation_id, conversation.summary, last_run_id=run.run_id)
    return run.run_id, user.message_id, assistant.message_id


def _run_orchestrator(tmp_path, monkeypatch, *, prior="none", new_query=QUESTION, damage=None):
    from intelligence.runtime import conversation_orchestrator as service
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
    from intelligence.services.conversation_store import ConversationStore
    from intelligence.services.run_store import RunStore
    from intelligence.services.temporal_contract import compile_temporal_contract
    from intelligence.workbench_skills.registry import SkillRegistry

    conversations = ConversationStore("temporal", root=tmp_path / "conversations")
    runs = RunStore("temporal", root=tmp_path / "runs")
    conversation = conversations.create_conversation()
    prior_source = None
    if prior != "none":
        if damage == "unrelated_source_run":
            _prepare_turn(conversations, runs, conversation.conversation_id, QUESTION)
        old_run, old_user, old_assistant = _prepare_turn(conversations, runs, conversation.conversation_id, QUESTION)
        temporal = compile_temporal_contract(QUESTION, today=TODAY, message_id=old_user)
        if damage == "unrelated_source_run":
            unrelated_user = next(m for m in conversations.load_messages(conversation.conversation_id)
                                  if m.role == "user" and m.run_id != old_run)
            temporal = compile_temporal_contract(QUESTION, today=TODAY, message_id=unrelated_user.message_id)
        prior_source = temporal.cutoff_source
        intent = replace(_control().turn_intent, temporal_contract=temporal).to_dict()
        if prior.startswith("legacy"):
            intent.pop("temporal_contract")
        if damage == "digest":
            intent["temporal_contract"]["cutoff_source"]["message_sha256"] = "0" * 64
        if damage == "expanded_persisted_permission":
            intent["temporal_contract"]["cutoff_origin"] = "inherited_user"
            intent["temporal_contract"]["information_cutoff"] = "2026-10-07"
        conversations.revise_message(conversation.conversation_id, old_assistant, content="旧答仅是提示上下文", status="completed", turn_intent=intent)
        if damage == "missing_user":
            conversations.revise_message(conversation.conversation_id, old_user, content="", status="failed")
        if damage == "replaced_user":
            conversations.revise_message(conversation.conversation_id, old_user, content="助手摘要里说截至10/7", status="completed")
        if prior.endswith("_chain"):
            bridge_query = "那这个判断有哪些反证？"
            _bridge_run, bridge_user, bridge_assistant = _prepare_turn(conversations, runs, conversation.conversation_id, bridge_query)
            bridge = decide_turn(
                bridge_query, previous_intent=replace(_control().turn_intent, temporal_contract=temporal),
                previous_turn_id=old_assistant, resolver=LocalResolver(), today=TODAY,
                temporal_contract=compile_temporal_contract(bridge_query, today=TODAY, message_id=bridge_user),
                llm_complete=lambda *_args: (None, None, "offline bridge"),
            ).turn_intent.to_dict()
            if prior.startswith("legacy"):
                bridge.pop("temporal_contract")
            if damage == "dropped_persisted_permission":
                bridge["temporal_contract"] = TemporalContract(market_target=temporal.market_target).to_dict()
            conversations.revise_message(conversation.conversation_id, bridge_assistant,
                                         content="第二轮上下文", status="completed", turn_intent=bridge)

    if damage == "run_parent_mismatch":
        conversations.update_summary(conversation.conversation_id, "", last_run_id=None)
    run_id, user_id, assistant_id = _prepare_turn(conversations, runs, conversation.conversation_id, new_query)
    if damage == "current_mismatch":
        conversations.revise_message(conversation.conversation_id, user_id, content="被替换的原消息", status="completed")
    registry = _sentinel_registry(tmp_path)
    captured = []
    controller_calls = []

    def adversarial_controller(query, **kwargs):
        controller_calls.append(query)
        reply = json.dumps({"route_id": "dated_market_review", "confidence": 0.9,
                            "reason": "offline controller fixture", "user_goal": "核验反证",
                            "assumptions": [], "ambiguities": []})
        decision = decide_turn(
            query, resolver=LocalResolver(), llm_complete=lambda *_args: (reply, None, ""),
            today=kwargs["today"], temporal_contract=kwargs["temporal_contract"],
            previous_intent=kwargs["previous_intent"], previous_turn_id=kwargs["previous_turn_id"],
        )
        # A valid-looking later permit invented by the model is not user authority.
        forged = compile_temporal_contract("资料截至2026年10月7日", today=TODAY, message_id="model-forgery")
        frame = replace(decision.task_frame, timeframe="2026-10-07", user_goal="结合10/7的资料",
                        temporal_contract=forged)
        if damage == "dropped_continuation":
            decision = replace(decision, turn_intent=replace(decision.turn_intent, inherited_from_turn=None))
        return replace(decision, task_frame=frame, timeframe="2026-10-07")

    class CaptureAdapter:
        def handle(self, *, frame, control):
            if control.terminal_kind == "clarification":
                captured.append((frame, control, None, None))
            else:
                context = build_episode_context(frame, task_id=str(uuid4()), capabilities=("news_search",),
                                                today=TODAY.isoformat(), latest_data_date=TODAY.isoformat())
                observation, model = _consume(registry, context)
                captured.append((frame, control, context, (observation, model)))
            return ContinuousTurnResult(True, "failed", "", None, (), (), None, ())

    monkeypatch.setattr(service, "run_stance_pack", lambda *_args, **_kwargs: None)
    result = service.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=conversations, run_store=runs,
        skill_registry=SkillRegistry(), turn_controller_fn=adversarial_controller,
        continuous_turn_adapter=CaptureAdapter(),
        answer_query_fn=lambda *_args: pytest.fail("Episode probe must not enter legacy Ask"),
    ).run_turn(conversation_id=conversation.conversation_id, run_id=run_id, assistant_message_id=assistant_id,
               query=new_query, skill_mode="auto", selected_skill_ids=[])
    decision_trace = next(t for t in runs.load_trace(run_id) if t["name"] == "turn_controller")
    result = (result, json.loads(decision_trace["output_summary"]))
    return captured, controller_calls, conversations, runs, result, prior_source, user_id


def test_real_entry_pins_current_user_identity_against_controller_rewrites(tmp_path, monkeypatch):
    captured, _calls, _conversations, _runs, _result, _prior, user_id = _run_orchestrator(tmp_path, monkeypatch)
    frame, control, context, (observation, model) = captured[0]
    temporal = frame.temporal_contract
    assert temporal is control.turn_intent.temporal_contract is context.temporal_contract
    assert (temporal.cutoff_source.message_id, temporal.cutoff_source.excerpt) == (user_id, QUESTION)
    assert temporal.information_cutoff == frame.timeframe == "2026-09-30"
    assert not observation.evidence
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)


@pytest.mark.parametrize("prior", ["frozen", "legacy", "frozen_chain", "legacy_chain"])
def test_real_message_chain_recovers_user_bound_on_continuation(tmp_path, monkeypatch, prior):
    captured, _calls, _conversations, _runs, _result, prior_source, _id = _run_orchestrator(
        tmp_path, monkeypatch, prior=prior, new_query="那这个判断有哪些反证？",
    )
    frame, control, context, (observation, model) = captured[0]
    temporal = frame.temporal_contract
    assert temporal.cutoff_origin == "inherited_user"
    assert temporal.cutoff_source == prior_source
    assert temporal is control.turn_intent.temporal_contract is context.temporal_contract
    assert context.information_cutoff.as_of_date == date(2026, 9, 30)
    assert not observation.evidence
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)


@pytest.mark.parametrize("damage", ["missing_user", "replaced_user", "digest", "unrelated_source_run", "expanded_persisted_permission", "run_parent_mismatch"])
def test_missing_or_unverified_prior_user_permission_clarifies_with_zero_tools(tmp_path, monkeypatch, damage):
    captured, _calls, _conversations, _runs, result, _prior, _id = _run_orchestrator(
        tmp_path, monkeypatch, prior="frozen", damage=damage, new_query="那这个判断有哪些反证？",
    )
    assert captured == []  # The deterministic clarification ends before Episode.
    _result, trace = result
    assert trace["task_frame"]["temporal_contract"]["errors"]
    assert trace["decision"]["lane"] == "clarify"
    assert trace["decision"]["capabilities"] == []


def test_current_explicit_user_permission_survives_missing_legacy_prior(tmp_path, monkeypatch):
    captured, _calls, _conversations, _runs, _result, _prior, user_id = _run_orchestrator(
        tmp_path, monkeypatch, prior="legacy", damage="missing_user",
        new_query="请复盘2026年9月30日的A股，资料截至2026年10月7日",
    )
    frame, _control, context, (observation, model) = captured[0]
    assert frame.temporal_contract.cutoff_origin == "explicit_user"
    assert frame.temporal_contract.cutoff_source.message_id == user_id
    assert context.information_cutoff.as_of_date == TODAY
    assert observation.evidence
    assert SENTINEL in json.dumps(model, ensure_ascii=False)


def test_current_message_identity_mismatch_stops_injected_controller(tmp_path, monkeypatch):
    captured, calls, _conversations, _runs, _result, _prior, _id = _run_orchestrator(
        tmp_path, monkeypatch, damage="current_mismatch",
    )
    assert calls == []
    assert captured == []
    assert _result[1]["task_frame"]["temporal_contract"]["errors"]


@pytest.mark.parametrize("cutoff_text", ["9/29", "9月29日", "2026/9/29", "2026.9.29", "2026-9-29"])
def test_permission_dates_share_existing_date_lexicon(cutoff_text):
    temporal = compile_temporal_contract(f"复盘9/30的A股，只用截至{cutoff_text}的信息", today=TODAY)
    assert temporal.information_cutoff == "2026-09-29"
    assert temporal.market_target.end == "2026-09-30"
    assert temporal.errors == ()


def test_legacy_payload_and_hash_are_byte_identical_to_exact_base():
    # Captured from b91000b7237868cedf965ebd3fdf060b175ce39b, not generated
    # from the implementation under test.
    frame = TaskFrame("旧原题", "旧目标", "general_finance_qa", None, "unknown", "未限定", None,
                      ("direct_answer", "evidence_boundary"), (), (), None, "general_finance_evidence", 0.4)
    expected = '{"ambiguities":[],"assumptions":[],"clarification_question":null,"confidence":0.4,"evidence_policy":"general_finance_evidence","market_scope":"未限定","question_type":"general_finance_qa","raw_question":"旧原题","required_outputs":["direct_answer","evidence_boundary"],"subject":null,"subject_kind":"unknown","task_frame_hash":"86aa2d60d04943e21381fbc60b40f48ef7ca485b3341dd5df08d3b3a199c8965","timeframe":null,"user_goal":"旧目标"}'
    assert json.dumps(frame.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) == expected
    assert frame.task_frame_hash == "86aa2d60d04943e21381fbc60b40f48ef7ca485b3341dd5df08d3b3a199c8965"
    assert TaskFrame.from_dict(json.loads(expected)) == frame
    from intelligence.services.query_understanding import QueryEnvelope
    from intelligence.services.research_contract import TurnIntent

    envelope = QueryEnvelope("general_finance_qa", "unknown", None, "旧目标", None, "none", 0.4)
    intent = TurnIntent(None, (), "general_finance_qa", None, (), None)
    assert "temporal_contract" not in envelope.to_dict()
    assert "temporal_contract" not in intent.to_dict()
    assert QueryEnvelope.from_dict(envelope.to_dict()) == envelope
    assert TurnIntent.from_dict(intent.to_dict()) == intent


def test_full_source_roundtrip_normalized_digest_frozen_and_hash_binding():
    from dataclasses import FrozenInstanceError
    from intelligence.services.query_understanding import QueryEnvelope
    from intelligence.services.research_contract import TurnIntent

    original = QUESTION + "\r\n完整原文\r尾部"
    temporal = compile_temporal_contract(original, today=TODAY, message_id="user-origin")
    assert temporal.cutoff_source.excerpt == original
    assert message_digest(original) == message_digest(original.replace("\r\n", "\n").replace("\r", "\n"))
    assert TemporalContract.from_dict(json.loads(json.dumps(temporal.to_dict()))) == temporal
    assert TemporalSource.from_dict(temporal.cutoff_source.to_dict()) == temporal.cutoff_source
    with pytest.raises(FrozenInstanceError):
        temporal.information_cutoff = "2026-10-07"
    frame = replace(_control().task_frame, temporal_contract=temporal)
    assert TaskFrame.from_dict(frame.to_dict()) == frame
    changed_source = replace(temporal.cutoff_source, message_id="different-real-user")
    changed = replace(temporal, cutoff_source=changed_source, market_target=replace(temporal.market_target, source=changed_source))
    assert replace(frame, temporal_contract=changed).task_frame_hash != frame.task_frame_hash
    changed_text = compile_temporal_contract(original + "。", today=TODAY, message_id="user-origin")
    assert replace(frame, temporal_contract=changed_text).task_frame_hash != frame.task_frame_hash
    envelope = replace(understand_query(QUESTION), task_frame=frame, temporal_contract=temporal)
    intent = replace(_control().turn_intent, temporal_contract=temporal)
    assert QueryEnvelope.from_dict(envelope.to_dict()) == envelope
    assert TurnIntent.from_dict(intent.to_dict()) == intent


@pytest.mark.parametrize(("path", "bad"), [
    (("extra",), True), (("cutoff_origin",), "model"), (("information_cutoff",), "2026-9-30"),
    (("cutoff_origin",), "explicit_user"), (("cutoff_origin",), "runtime_relative"),
    (("information_cutoff",), "2026-09-31"), (("information_cutoff",), None),
    (("cutoff_source",), None), (("relative_anchor_sha256",), "0" * 64),
    (("errors",), "error"), (("errors",), [None]),
    (("market_target", "start"), "2026-10-01"), (("market_target", "end"), True),
    (("market_target", "extra"), True), (("cutoff_source", "message_id"), 7),
    (("cutoff_source", "message_sha256"), 7), (("cutoff_source", "message_sha256"), "A" * 64),
    (("cutoff_source", "excerpt"), "助手摘要"), (("cutoff_source", "extra"), True),
])
def test_present_malformed_schema_is_rejected_by_every_contract_projection(path, bad):
    from intelligence.services.query_understanding import QueryEnvelope
    from intelligence.services.research_contract import TurnIntent

    payload = _control().task_frame.temporal_contract.to_dict()
    node = payload
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = bad
    with pytest.raises(ValueError):
        TemporalContract.from_dict(payload)
    for value, reader in [(_control().task_frame.to_dict(), TaskFrame.from_dict),
                          (_control().turn_intent.to_dict(), TurnIntent.from_dict),
                          (understand_query(QUESTION).to_dict(), QueryEnvelope.from_dict)]:
        value["temporal_contract"] = payload
        with pytest.raises(ValueError):
            reader(value)


def test_none_field_present_is_not_an_absent_legacy_contract():
    for value, reader in [(_control().task_frame.to_dict(), TaskFrame.from_dict),
                          (_control().turn_intent.to_dict(), type(_control().turn_intent).from_dict)]:
        value["temporal_contract"] = None
        with pytest.raises(ValueError):
            reader(value)


def test_controller_model_projection_keeps_public_semantics_without_private_source():
    original = QUESTION + "私有源审计标记"
    prior = replace(_control(original).turn_intent, temporal_contract=compile_temporal_contract(
        original, today=TODAY, message_id="private-user-id",
    ))
    captured = []

    def complete(messages):
        captured.append(json.loads(messages[1]["content"])["task_frame"])
        return None, None, "fixture unavailable"

    decision = decide_turn("那这个判断有哪些反证？", previous_intent=prior, previous_turn_id="previous-answer",
                           today=TODAY, resolver=LocalResolver(), llm_complete=complete)
    assert captured == [json.loads(json.dumps(decision.task_frame.to_model_dict()))]
    public = captured[0]["temporal_contract"]
    assert public["information_cutoff"] == "2026-09-30"
    assert public["cutoff_origin"] == "inherited_user"
    rendered = json.dumps(public, ensure_ascii=False)
    assert all(private not in rendered for private in ("private-user-id", "私有源审计标记", prior.temporal_contract.cutoff_source.message_sha256))
    assert decision.task_frame.temporal_contract.cutoff_source.excerpt == original


@pytest.mark.parametrize(("new_query", "expected"), [
    ("那这个判断有哪些反证？资料截至2026年9月29日", "2026-09-29"),
    ("那这个判断有哪些反证？资料截至2026年10月7日", "2026-10-07"),
])
def test_real_continuation_current_user_can_tighten_or_relax(tmp_path, monkeypatch, new_query, expected):
    captured, _calls, _conversations, _runs, _result, prior_source, user_id = _run_orchestrator(
        tmp_path, monkeypatch, prior="frozen", new_query=new_query,
    )
    frame, _control_, context, (observation, model) = captured[0]
    temporal = frame.temporal_contract
    assert temporal.cutoff_origin == "explicit_user"
    assert temporal.cutoff_source.message_id == user_id
    assert temporal.market_target.source == prior_source
    assert context.information_cutoff.as_of_date.isoformat() == expected
    assert bool(observation.evidence) == (expected == "2026-10-07")
    assert (SENTINEL in json.dumps(model, ensure_ascii=False)) == bool(observation.evidence)


def test_injected_controller_cannot_expand_bound_by_dropping_real_continuation(tmp_path, monkeypatch):
    captured, _calls, _conversations, _runs, _result, prior_source, _id = _run_orchestrator(
        tmp_path, monkeypatch, prior="frozen", damage="dropped_continuation", new_query="那这个判断有哪些反证？",
    )
    frame, _control_, context, (observation, model) = captured[0]
    assert frame.temporal_contract.cutoff_source == prior_source
    assert context.information_cutoff.as_of_date.isoformat() == "2026-09-30"
    assert not observation.evidence
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)


def test_persisted_none_cannot_erase_ancestor_user_permission(tmp_path, monkeypatch):
    captured, _calls, _conversations, _runs, result, _prior_source, _id = _run_orchestrator(
        tmp_path, monkeypatch, prior="frozen_chain", damage="dropped_persisted_permission",
        new_query="那这个判断有哪些反证？",
    )
    assert captured == []
    assert result[1]["task_frame"]["temporal_contract"]["errors"]
    assert result[1]["decision"]["capabilities"] == []


@pytest.mark.parametrize("history_mode", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_real_registry_rebuilds_only_eligible_cards_and_clears_preview(tmp_path, history_mode, mixed):
    from intelligence.services.historical_research.intent import HistoryIntent

    context = _context()
    if history_mode:
        context = replace(context, history_intent=HistoryIntent(
            purpose="retrospective_discovery", strict_window=True,
            requested_start="2026-09-01", requested_end="2026-09-30",
        ))
    registry = _sentinel_registry(tmp_path)
    original_runner = registry.resolve("news_search").runner
    eligible = AgentEvidence(tool="news_search", title="已知的未来日程标题10/9", detail="合法内容123456",
                             source="fixture", source_date="2026-09-30", evidence_tier="news")

    def runner(query, ctx):
        result = original_runner(query, ctx)
        return replace(result, evidence=(eligible, *result.evidence) if mixed else result.evidence)

    registry = ResearchToolRegistry((replace(registry.resolve("news_search"), runner=runner),))
    observation, model = _consume(registry, context)
    delivered = json.dumps(model, ensure_ascii=False)
    assert SENTINEL not in delivered
    assert "未来数值=" not in delivered
    assert observation.query_basis == {}
    assert bool(observation.evidence) == mixed
    assert ("合法内容123456" in delivered) == mixed
    assert ("已知的未来日程标题10/9" in delivered) == mixed
    assert observation.telemetry["temporal_withheld"]["evidence"][0]["title"] == SENTINEL
    if not mixed:
        assert observation.trace.status == "future_of_cutoff"
        assert "不是源里没有" in model["observation"]


@pytest.mark.parametrize(("with_card", "mixed"), [(False, False), (True, False), (True, True)])
def test_known_future_provider_date_withholds_undated_prose_before_model(with_card, mixed):
    card = AgentEvidence(tool="news_search", title=SENTINEL, detail=SENTINEL, source="fixture", source_date=None, evidence_tier="news")
    eligible = replace(card, title="合法原资料", detail="合法原资料", source_date="2026-09-30")
    cards = (card, eligible) if mixed else (card,) if with_card else ()
    registry = ResearchToolRegistry((ToolSpec("news_search", "news_search", "fixture", "local", "current",
        lambda *_args: ToolRunResult(cards, SENTINEL,
                                    ProviderTrace("fixture", "sentinel", "success", source_trade_date="2026-10-01", result_count=1),
                                    query_basis={"preview": SENTINEL})),))
    observation, model = _consume(registry, _context())
    assert observation.trace.status == ("success" if mixed else "future_of_cutoff")
    assert observation.query_basis == {}
    assert bool(observation.evidence) == mixed
    assert SENTINEL not in json.dumps(model, ensure_ascii=False)


def test_unknown_date_keeps_existing_typed_scope_without_claiming_strict_availability():
    card = AgentEvidence(tool="news_search", title="日期未知的原资料", detail="待核对可得日", source="fixture",
                         source_date=None, evidence_tier="news")
    registry = ResearchToolRegistry((ToolSpec("news_search", "news_search", "fixture", "local", "current",
        lambda *_args: ToolRunResult((card,), "日期未知的原资料", ProviderTrace("fixture", "news", "success", result_count=1))),))
    observation, model = _consume(registry, _context())
    assert observation.evidence[0].source_date is None
    assert "日期未知" in json.dumps(model, ensure_ascii=False)


def test_overnight_news_never_uses_after_cutoff_cards_as_fallback(monkeypatch):
    from types import SimpleNamespace
    from intelligence.services import episode_tools

    future = SimpleNamespace(title=SENTINEL, date="2026-10-01", source="fixture", url="fixture://future")
    monkeypatch.setattr(episode_tools.market_news, "fetch_eastmoney_news_result", lambda *_args, **_kwargs:
                        SimpleNamespace(items=(), after_cutoff_items=(future,)))
    evidence, observation = episode_tools._overnight_news_evidence(as_of=date(2026, 9, 30), timeout=1)
    assert evidence == []
    assert SENTINEL not in observation
    assert "不是源里没有" in observation


def _canonical_episode_db(tmp_path):
    root = tmp_path / "finance"
    db_path = root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute((Path(__file__).parents[2] / "market_feature_store/schema.sql").read_text())
    return root, db_path


@pytest.mark.parametrize("permission", ["2026-10-07", "2026-09-29"])
def test_real_d4_consumes_target_without_making_it_all_materials_permission(tmp_path, permission):
    from intelligence.services.episode_tools import build_episode_registry

    root, db_path = _canonical_episode_db(tmp_path)
    with duckdb.connect(str(db_path)) as con:
        for day, theme, value in [("2026-09-30", "合法9月主线", 501), ("2026-10-07", SENTINEL, 987654)]:
            con.execute("insert into fact_market_daily (trade_date, total_amount) values (?, ?)", [day, value])
            con.execute("insert into fact_mainline_sector_daily (trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no, today_pct, amount) values (?, ?, ?, 'S1', ?, 1, 2, ?)",
                        [day, theme, theme, theme, value * 10000])
            con.execute("insert into fact_sector_daily_generation (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount) values (?, 'legacy', 'S1', ?, 2, ?)", [day, theme, value])
    query = f"复盘2026年9月30日A股，资料截至{permission}"
    frame = _control(query).task_frame
    context = build_episode_context(frame, task_id=str(uuid4()), capabilities=("mainline_context", "finance_query"),
                                    today=TODAY.isoformat(), latest_data_date="2026-10-07")
    registry = build_episode_registry(frame, context, finance_root=root, knowledge_wiki=tmp_path / "wiki", l3_runner=None)
    observation = registry.execute("mainline_context", {}, context=context, step_id="d4:1")
    projection = FinanceResearchHarness().project_tool_result(observation, evidence_so_far=observation.evidence, seen_prose=set())
    assert context.information_cutoff.as_of_date.isoformat() == permission
    assert SENTINEL not in projection.model_content
    assert "987654" not in projection.model_content
    if permission == "2026-10-07":
        assert observation.trace.status == "success"
        assert {card.source_date for card in observation.evidence} == {"2026-09-30"}
        assert "合法9月主线" in projection.model_content
        assert observation.query_basis["market_date"] == "2026-09-30"
    else:
        assert not observation.evidence
        assert "合法9月主线" not in projection.model_content


def test_future_event_schedule_known_by_cutoff_survives_real_episode_registry_and_model(tmp_path):
    from intelligence.services.episode_tools import build_episode_registry

    root, db_path = _canonical_episode_db(tmp_path)
    with duckdb.connect(str(db_path)) as con:
        for day, event_id, title, known in [
            ("2026-08-26", "nvda", "英伟达2026Q2财报", "2026-08-21 15:43:00"),
            ("2026-08-27", "jh", "杰克逊霍尔全球央行年会", "2026-08-21 15:43:00"),
            ("2026-08-28", "late", SENTINEL, "2026-08-24 10:00:00"),
        ]:
            con.execute("insert into fact_event_daily (event_date, event_id, title, importance, is_future, source, updated_at) values (?, ?, ?, 5, true, 'fixture', ?)", [day, event_id, title, known])
    query = "只使用截至2026年8月21日已知的信息，下周2026年8月24日至2026年8月28日有哪些大事？"
    frame = _control(query).task_frame
    context = build_episode_context(frame, task_id=str(uuid4()), capabilities=("finance_query",),
                                    today="2026-08-23", latest_data_date="2026-08-21")
    registry = build_episode_registry(frame, context, finance_root=root, knowledge_wiki=tmp_path / "wiki", l3_runner=None)
    observation = registry.execute("finance_query", {
        "dataset": "event_daily", "metrics": ["importance"], "dimensions": ["event_date", "title", "is_future"],
        "time_range": {"start": "2026-08-24", "end": "2026-08-28"},
        "order_by": [{"field": "event_date", "direction": "asc"}], "limit": 20,
    }, context=context, step_id="calendar:1")
    projection = FinanceResearchHarness().project_tool_result(observation, evidence_so_far=observation.evidence, seen_prose=set())
    assert observation.trace.status == "success"
    assert {card.source_date for card in observation.evidence} == {"2026-08-21"}
    assert "英伟达2026Q2财报" in projection.model_content
    assert "杰克逊霍尔全球央行年会" in projection.model_content
    assert "2026-08-26" in projection.model_content and "2026-08-27" in projection.model_content
    assert SENTINEL not in projection.model_content
    assert context.temporal_contract.information_cutoff == "2026-08-21"


def test_direct_legacy_factory_recovers_raw_user_only_and_pins_target():
    frame = replace(_control().task_frame, temporal_contract=None, timeframe="2026-10-07", user_goal="资料截至10/7")
    context = build_episode_context(frame, task_id=str(uuid4()), today=TODAY.isoformat(), latest_data_date=TODAY.isoformat())
    assert context.temporal_contract.cutoff_origin == "legacy_user"
    assert context.information_cutoff == InformationCutoff(date(2026, 9, 30), "requested")
    assert context.contract.timeframe == "2026-09-30"
    no_authority = replace(frame, raw_question="分析这家公司", user_goal="资料截至2026年9月30日", timeframe="2026-09-30")
    context = build_episode_context(no_authority, task_id=str(uuid4()), today=TODAY.isoformat())
    assert context.temporal_contract.cutoff_origin == "none"
    assert context.information_cutoff == InformationCutoff(TODAY, "runtime_default")


def test_relative_target_cannot_authorize_information_not_yet_available():
    query = "复盘2026年10月12日A股，只使用截至当日的信息"
    contract = compile_temporal_contract(query, today=TODAY)
    assert contract.errors
    decision = decide_turn(query, today=TODAY, resolver=type("Forbidden", (), {"resolve": lambda *_args: pytest.fail("must clarify before resolver")})())
    assert decision.lane == "clarify" and decision.capabilities == ()
