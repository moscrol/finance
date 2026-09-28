"""Revealed inputs: parser/entry delivery only, never semantic acceptance."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from intelligence.eval.knevo_regression import load_suite
from intelligence.services.conversation_materials import ConversationMaterials
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.query_understanding import material_request_question_type, understand_query
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.turn_controller import decide_turn
from intelligence.services.user_task import classify_top_level_regions, split_user_message

CASES = load_suite()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_original_case_scope_and_question_delivery(case):
    parts = split_user_message(case.question)
    contract = compile_material_contract(parts.regions)
    assert contract is not None
    assert (contract.classification, contract.authenticity, contract.data_scope) == (
        "constraint_confirmed", "fictional", "material_only",
    )
    if case.case_id.startswith("K260917-pack"):
        assert parts.question_ids == tuple(f"q{i}" for i in range(1, 9))
        for question in parts.sub_questions:
            assert question in parts.question
            assert question not in "\n".join(parts.material_texts)


@pytest.mark.parametrize("instruction", [
    "只分析虚构材料", "仅分析虚构材料", "仅使用材料", "仅使用以下材料",
    "仅使用下列材料", "只用给定材料", "仅根据这些材料", "只使用上述材料",
])
def test_material_scope_variants_and_protected_forms(instruction):
    parsed = compile_material_contract(classify_top_level_regions(instruction + "，不联网。"))
    assert parsed.data_scope == "material_only"
    for text in (f"「{instruction}，可以查真实数据」", f"```\n{instruction}\n```"):
        assert compile_material_contract(classify_top_level_regions(text)) is None
    ambiguous = compile_material_contract(classify_top_level_regions("材料如下：\n" + instruction))
    assert ambiguous.needs_clarification
    assert ambiguous.data_scope is None


@pytest.mark.parametrize("verb", ["计算", "评价", "核算", "解释", "给出", "列出", "归纳"])
def test_imperative_numbered_question_is_not_lost(verb):
    text = f"只依据材料回答。\n\n1. {verb}同比增速。\n2. 请写结论。"
    parts = split_user_message(text)
    assert parts.question_ids == ("q1", "q2")
    assert f"{verb}同比增速。" in parts.question


def test_message_material_ceiling_allows_question_local_restriction():
    parsed = compile_material_contract(classify_top_level_regions(
        "仅使用下列材料。\n\n1. 不要联网，计算比例。\n2. 请写结论。"
    ))
    assert not parsed.needs_clarification
    assert parsed.data_scope == "material_only"


def test_enumerated_network_restriction_is_not_silently_lost():
    parsed = compile_material_contract(classify_top_level_regions("不查库、不联网、不写记忆。"))
    assert parsed.data_scope == "local_only"  # This does not claim a separate no-DB policy.


def test_q14_typed_controller_delivers_news_guidance_without_permissions(monkeypatch):
    monkeypatch.setenv("FINANCE_RESEARCH_WORKFLOW_GUIDANCE", "1")
    case = next(case for case in CASES if case.case_id == "Q14-news-layers")
    decision = decide_turn(case.question, conversation_materials=ConversationMaterials())
    assert decision.lane == "research"
    frame = decision.task_frame
    assert frame.question_type == "news_impact"
    context = build_episode_context(frame, task_id="revealed-news")
    assert context.contract.allowed_capabilities == ()
    assert context.contract.evidence_plan.requirements == ()
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    assert payload["task_frame"]["raw_question"] == case.question
    assert "消息逐项拆为事实、解读与情绪表达" in payload["question_type_rules"]
    assert "量化情绪溢价" in payload["question_type_rules"]
    assert understand_query(case.question).question_type == frame.question_type


def test_finance_material_method_reaches_episode_author_without_changing_contract(monkeypatch):
    case = next(case for case in CASES if case.case_id == "K260917-pack2")
    frame = decide_turn(case.question, conversation_materials=ConversationMaterials()).task_frame
    assert frame.question_type == "general_finance_qa"
    context = build_episode_context(frame, task_id="finance-method")
    registry = ResearchToolRegistry(())
    on = json.loads(build_episode_input(frame, context, registry))

    assert "[FA-01]" in on["reading_baseline"]
    assert "现金资本开支影响投资后现金" in on["reading_baseline"]
    assert "融资需要还取决于其他现金收付" in on["reading_baseline"]
    assert on["research_contract"]["allowed_capabilities"] == []
    assert on["research_contract"]["evidence_plan"]["requirements"] == []
    assert on["available_tools"] == ""
    assert [item["output_id"] for item in on["research_contract"]["required_outputs"]] == [
        *(f"answer_q{i}" for i in range(1, 9)), "evidence_boundary",
    ]

    monkeypatch.setenv("FINANCE_READING_BASELINE", "0")
    off = json.loads(build_episode_input(frame, context, registry))
    assert "reading_baseline" not in off
    assert "reading_baseline_rule" not in off
    assert on["research_contract"] == off["research_contract"]
    assert on["available_tools"] == off["available_tools"]
    monkeypatch.delenv("FINANCE_READING_BASELINE")

    market = json.loads(build_episode_input(replace(frame, question_type="market_watch"), context, registry))
    assert "reading_baseline" not in market
    assert "reading_baseline_rule" not in market

    ordinary = decide_turn("请计算今天上证指数收盘点位。", conversation_materials=ConversationMaterials()).task_frame
    ordinary_context = build_episode_context(ordinary, task_id="ordinary-fact")
    ordinary_payload = json.loads(build_episode_input(ordinary, ordinary_context, registry))
    assert "FA-01" not in json.dumps(ordinary_payload["research_contract"], ensure_ascii=False)
    assert "FA-01" not in ordinary_payload["available_tools"]


@pytest.mark.parametrize("question", [
    "这个消息能支持什么结论？", "这条公告意味着什么？", "该新闻有什么影响？",
])
def test_supplied_news_route_uses_user_request_not_material_prose(question):
    request = "仅使用材料。\n\n" + question
    assert material_request_question_type(split_user_message(request)) == "news_impact"
    for body in (f"「{question}」", f"```\n{question}\n```", "材料如下：\n" + question):
        assert material_request_question_type(split_user_message(body)) == "general_finance_qa"
    pack = "仅使用材料。\n\n1. " + question + "\n2. 请计算增速。"
    assert material_request_question_type(split_user_message(pack)) == "general_finance_qa"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_real_turn_entry_reaches_empty_registry_without_fact_reads(tmp_path, monkeypatch, case):
    import socket

    from intelligence.runtime import conversation_orchestrator as runtime
    from intelligence.services import episode_tools, turn_controller
    from intelligence.services.conversation_store import ConversationStore
    from intelligence.services.run_store import RunStore

    class Reached(BaseException):
        pass

    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        pytest.fail("material-only attempted a resolver, prior, network or prefetch read")

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "absent.duckdb"))
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(turn_controller.QueryResolver, "resolve", forbidden)
    monkeypatch.setattr(runtime, "should_run_stance_pack", lambda **kwargs: True)
    monkeypatch.setattr(runtime, "run_stance_pack", forbidden)
    monkeypatch.setattr(runtime.research_project, "prior_for_turn", forbidden)
    monkeypatch.setattr(runtime.perspective_lab, "active_runtime_prompt", forbidden)
    for name in ("_roots", "_market_db_path", "_opening_prefetch_evidence"):
        monkeypatch.setattr(episode_tools, name, forbidden)
    monkeypatch.setattr(episode_tools.ask_blocks, "_market_data_asof", forbidden)
    monkeypatch.setattr(episode_tools.entity_anchor, "resolve_entity_anchor", forbidden)
    captured = []

    class Adapter:
        def handle(self, *, frame, control):
            context = build_episode_context(frame, task_id="entry-regression")
            registry = episode_tools.build_episode_registry(frame, context, finance_root=tmp_path)
            captured.append(json.loads(build_episode_input(frame, context, registry)))
            assert frame.material_contract.data_scope == "material_only"
            assert not frame.material_contract.needs_clarification
            assert context.contract.allowed_capabilities == ()
            assert context.contract.evidence_plan.requirements == ()
            assert registry.names() == () and registry.opening_prefetch == ()
            assert control.perspective_context == "" and control.stance_pack is None
            raise Reached

    store = ConversationStore("probe-material", root=tmp_path / "conversations")
    runs = RunStore("probe-material", root=tmp_path / "runs")
    conv = store.create_conversation()
    run = runs.create_run(case.question, "ask", session_id=conv.conversation_id)
    store.append_message(conv.conversation_id, "user", case.question, run_id=run.run_id)
    assistant = store.append_message(conv.conversation_id, "assistant", "", status="running", run_id=run.run_id)
    orchestrator = runtime.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=store, run_store=runs,
        continuous_turn_adapter=Adapter(),
    )
    with pytest.raises(Reached):
        orchestrator.run_turn(
            conversation_id=conv.conversation_id, run_id=run.run_id,
            assistant_message_id=assistant.message_id, query=case.question,
            skill_mode="auto", selected_skill_ids=[],
        )
    assert attempts == []
    assert len(captured) == 1
    assert captured[0]["task_frame"]["raw_question"] == case.question.strip()
    if case.case_id.startswith("K260917-pack"):
        assert [item["output_id"] for item in captured[0]["research_contract"]["required_outputs"]] == [
            *(f"answer_q{i}" for i in range(1, 9)), "evidence_boundary",
        ]
