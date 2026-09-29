"""Correction inheritance, not an accounting-answer or semantic-quality oracle."""
from __future__ import annotations

import json
import pytest

from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_materials import collect_material_turn_history
from intelligence.services.conversation_store import ConversationStore, Message
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore
from intelligence.services.user_task import classify_top_level_regions, material_id_for
from scripts.perspective_request_capture import RequestCapture, RequestCaptured

PRIOR = (
    "只根据以下虚构题设分析，不查库、不联网。所有公司均为虚构企业。金额单位均为亿元。\n\n"
    "1. 甲公司经营现金流为6，已经完成非现金折旧2的调节，现金资本开支为4。如何区分口径？\n\n"
    "2. 传统业务股权价值70，新业务净利润3，采用12倍利润估值。如何理解条件估值和买入边界？"
)
OLD = "旧答：净利润应先扣现金资本开支；条件价值106即代表值得买。"
CORRECTION = "请只基于原题重写第2问的判断，保留条件估值与买入边界。不要查询外部数据。"


def message(text, role="user", identity="u1", status="completed"):
    return Message(identity, "conv", role, text, "2026-09-29", status)


@pytest.mark.parametrize("query", [
    CORRECTION,
    "仅依据原材料纠正结论。",
    "请根据上一题重新回答。",
    "基于原题修正判断。",
])
def test_explicit_correction_requests_trusted_continuation(query):
    history = collect_material_turn_history([message(PRIOR), message(OLD, "assistant", "a1")])
    contract = history.compile_contract(classify_top_level_regions(query))
    assert contract is not None and contract.continuation_requested
    assert contract.data_scope == "material_only"
    assert contract.authenticity == "fictional"
    assert contract.questions == (), "old questions are sources, not new output slots"


@pytest.mark.parametrize("wrapped", [
    '请解释“只基于原题重写第2问”这句话。',
    '> 只基于原题重写第2问。',
    '```text\n只基于原题重写第2问。\n```',
    '1. 只基于原题重写第2问。',
    '不要只基于原题重写第2问。',
    '原题研究报告指出企业应重写规划。',
])
def test_non_message_or_non_instruction_cannot_recover_permissions(wrapped):
    contract = compile_material_contract(classify_top_level_regions(wrapped))
    assert contract is None or not contract.continuation_requested


def test_embedded_previous_question_sources_retain_body_identity_and_user_coordinate():
    history = collect_material_turn_history([message(PRIOR), message(OLD, "assistant", "a1")])
    questions = history.base_contract.questions
    assert len(questions) == 2
    for question in questions:
        source = next((item for item in history.question_sources if item.ref.material_id == material_id_for(question.text)), None)
        assert source is not None, "numbered premises must not disappear after their first turn"
        assert source.text == question.text
        assert source.source_message_id == "u1"
    assert not any(OLD in item.text for item in (*history.items, *history.question_sources))
    assert history.assistant_statements[0].basis == "assistant_judgment"


@pytest.mark.parametrize("records", [
    [],
    [message(PRIOR, "assistant", "a1")],
    [message(PRIOR, status="failed")],
])
def test_missing_trusted_base_requires_clarification(records):
    history = collect_material_turn_history(records, unavailable=True)
    contract = history.compile_contract(classify_top_level_regions(CORRECTION))
    assert contract is not None and contract.needs_clarification
    assert contract.data_scope is None


def test_new_topic_does_not_recover_previous_question_sources():
    history = collect_material_turn_history([
        message(PRIOR), message(OLD, "assistant", "a1"),
        message("介绍另一家乙公司的业务。", identity="u2"),
    ])
    assert not any("甲公司" in item.text or "传统业务" in item.text for item in (*history.items, *history.question_sources))
    assert not history.assistant_statements


def test_correction_can_explicitly_release_reads_without_reclassifying_premises():
    history = collect_material_turn_history([message(PRIOR)])
    contract = history.compile_contract(classify_top_level_regions("基于原题修正判断。可以查真实数据。"))
    assert contract.continuation_requested
    assert contract.data_scope == "full" and contract.authenticity == "fictional"


def test_only_correction_narrows_full_base_but_plain_correction_does_not():
    history = collect_material_turn_history([message("查询甲公司最新财报。")])
    for prefix, expected in (("只", "material_only"), ("", "full")):
        contract = history.compile_contract(classify_top_level_regions(prefix + "基于原题修正判断。"))
        assert contract is not None and contract.data_scope == expected
        assert contract.continuation_requested


def test_real_workbench_correction_reaches_author_with_original_premises(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "absent.duckdb"))

    def forbidden(*_args, **_kwargs):
        pytest.fail("material correction must bypass resolver/controller models and external reads")

    monkeypatch.setattr("intelligence.services.query_resolution.QueryResolver.resolve", forbidden)
    monkeypatch.setattr("intelligence.services.turn_controller.llm_refine.complete", forbidden)
    store = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conv = store.create_conversation()
    original = store.append_message(conv.conversation_id, "user", PRIOR, run_id="prior")
    old = store.append_message(conv.conversation_id, "assistant", OLD, run_id="prior")
    run = runs.create_run(CORRECTION, "ask", session_id=conv.conversation_id)
    store.append_message(conv.conversation_id, "user", CORRECTION, run_id=run.run_id)
    answer = store.append_message(conv.conversation_id, "assistant", "", status="running", run_id=run.run_id)
    capture = RequestCapture(today="2026-09-29")
    adapter = capture.adapter()
    seen = []

    def registry(frame, context):
        seen.append((frame, context.contract))
        return ResearchToolRegistry(())

    adapter._registry_factory = registry
    runner = TurnOrchestrator(repo_root=tmp_path, conversation_store=store, run_store=runs,
                              continuous_turn_adapter=adapter)
    with pytest.raises(RequestCaptured):
        runner.run_turn(conversation_id=conv.conversation_id, run_id=run.run_id,
                        assistant_message_id=answer.message_id, query=CORRECTION,
                        skill_mode="auto", selected_skill_ids=[])
    payload = capture.payload()
    frame, contract = seen[0]
    assert capture.calls == 1 and capture.tool_count == 0
    assert contract.allowed_capabilities == ()
    assert frame.material_contract.data_scope == "material_only"
    assert frame.material_contract.continuation_requested
    sources = payload["material_grounding"]["sources"]
    assert any("经营现金流为6" in row["text"] and row["ref"].startswith("M") for row in sources)
    assert any("股权价值70" in row["text"] and row["ref"].startswith("M") for row in sources)
    assert not any(OLD in row["text"] and row["ref"].startswith("M") for row in sources)
    assert any(row["text"] == OLD and row["ref"].startswith("H") for row in sources)
    assert any(item.source_message_id == original.message_id for item in frame.conversation_materials.items)
    assert contract.material_grounding.historical_assistant_statements[0].source_message_id == old.message_id
    assert not any(output.output_id in {"q1", "q2"} for output in contract.required_outputs)
    restored = type(frame).from_dict(json.loads(json.dumps(frame.to_dict())))
    assert restored.conversation_materials == frame.conversation_materials


@pytest.mark.parametrize("field", ["text", "source_message_id", "ref"])
def test_historical_question_deserialization_validates_sources(field):
    from dataclasses import asdict
    from intelligence.services.conversation_materials import ConversationMaterials

    history = collect_material_turn_history([message(PRIOR)])
    payload = asdict(history)
    assert len(payload["question_sources"]) == 2
    row = payload["question_sources"][0]
    row[field] = "changed body" if field == "text" else ({} if field == "ref" else "")
    with pytest.raises(ValueError):
        ConversationMaterials.from_dict(payload)


def test_reused_question_numbers_do_not_overwrite_source_or_current_output_slots():
    history = collect_material_turn_history([
        message(PRIOR), message(OLD, "assistant", "a1"),
        message("继续上一轮。\n\n1. 新情景经营现金流改为9，资本开支仍为4，差额是多少？", identity="u2"),
    ])
    assert any(row.source_message_id == "u1" and "经营现金流为6" in row.text
               for row in history.question_sources)
    assert any(row.source_message_id == "u2" and "现金流改为9" in row.text
               for row in history.question_sources)
    assert len({row.ref.material_id for row in history.question_sources}) == 3
    contract = history.compile_contract(classify_top_level_regions(CORRECTION))
    assert contract.questions == ()


def test_correction_after_conjunction_is_still_a_top_level_control():
    history = collect_material_turn_history([message(PRIOR)])
    contract = history.compile_contract(classify_top_level_regions("保持简短并只基于原题重写判断。"))
    assert contract and contract.continuation_requested
    assert contract.data_scope == "material_only"


def test_original_failed_feedback_shape_is_recognized_without_financial_keyword_rules():
    query = (
        "校审反馈：你上一答第8问把会计净利润说成应检查‘是否已扣除现金资本开支’，"
        "这是损益口径与投资现金流口径的混用。请只基于原题重写第8问的资本开支/增长再投资判断，"
        "保留原估值情景与买入边界；明确为什么不能机械从净利润或已给股权价值扣现金投资，"
        "并说明应核对哪些增长、回报、融资和倍数假设。不要查询外部数据，"
        "也不要修改其他小题已经成立的计算或填入题外数字。"
    )
    history = collect_material_turn_history([message(PRIOR)])
    contract = history.compile_contract(classify_top_level_regions(query))
    assert contract and contract.continuation_requested and contract.data_scope == "material_only"
