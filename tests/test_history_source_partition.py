"""H-03: material ownership and incomplete quotations cannot grant history controls."""
from dataclasses import asdict

import pytest

from intelligence.services.conversation_materials import ConversationMaterials, collect_material_turn_history
from intelligence.services.historical_research.intent import (
    explicit_information_cutoff, history_research_cancelled, infer_history_intent,
    inherit_history_followup, named_wave_subject,
)
from intelligence.services.honesty_gates import requested_information_cutoff
from intelligence.services.user_task import classify_top_level_regions, split_user_message, top_level_message_text
from tests.test_history_control_boundary import (
    BASE, _decide, _project, no_external_io, trusted_history,
)
from tests.test_history_permission_inheritance import FOLLOWUPS, assert_local, message, no_model_calls

__all__ = ["no_external_io", "no_model_calls", "trusted_history"]
MATERIAL_CONTAINERS = ("材料如下：\n{}", "报告原文：\n{}", "  {}")
UNCLOSED_QUOTES = ("「", "『", "“", "‘", '"', "'")


@pytest.mark.parametrize("query", [
    "材料如下：\n那它们见顶后谁接力？", "「那它们见顶后谁接力？",
])
def test_original_adjacent_counterexamples_cannot_restore_history(query, trusted_history, tmp_path):
    previous, history = trusted_history
    decision = _decide(query, previous, history)
    _, context, names = _project(decision, tmp_path)
    assert context.history_intent is None and names == ()
    assert decision.task_frame.raw_question == query
    assert decision.turn_intent.inherited_from_turn is None


@pytest.mark.parametrize("container", MATERIAL_CONTAINERS)
@pytest.mark.parametrize("text", [*FOLLOWUPS, BASE, "那它呢？"])
@pytest.mark.parametrize("has_previous", [False, True])
def test_material_owned_text_is_not_live_history_control(container, text, has_previous, trusted_history, tmp_path):
    previous, history = trusted_history if has_previous else (None, None)
    query = container.format(text)
    decision = _decide(query, previous, history)
    _, context, names = _project(decision, tmp_path)
    assert decision.task_frame.history_intent is None
    assert decision.turn_intent.history_intent is None
    assert decision.turn_intent.inherited_from_turn is None
    assert context.history_intent is None and names == ()
    assert decision.task_frame.raw_question == query.strip()


@pytest.mark.parametrize("opener", UNCLOSED_QUOTES)
@pytest.mark.parametrize("text", [*FOLLOWUPS, "市盈率是什么？"])
def test_incomplete_quote_clarifies_without_capabilities(opener, text, trusted_history, tmp_path):
    previous, history = trusted_history
    query = opener + text
    visible, uncertain = top_level_message_text(query)
    assert not visible and uncertain
    assert classify_top_level_regions(query).classification == "boundary_uncertain"
    decision = _decide(query, previous, history)
    control, context, names = _project(decision, tmp_path)
    assert control.terminal_kind == "clarification"
    assert not context.contract.allowed_capabilities
    assert context.history_intent is None and names == ()


@pytest.mark.parametrize("container", [*MATERIAL_CONTAINERS, "「{}"])
def test_all_permission_readers_use_material_ownership(container, trusted_history):
    previous, _ = trusted_history
    assert infer_history_intent(container.format(BASE)) is None
    assert named_wave_subject(container.format(BASE)) is None
    assert explicit_information_cutoff(container.format(BASE)) is None
    assert inherit_history_followup(container.format(FOLLOWUPS[0]), previous.history_intent) is None
    assert not history_research_cancelled(container.format("不要历史研究。"))
    assert requested_information_cutoff(container.format("站在2026年9月1日收盘。")) is None


@pytest.mark.parametrize("query", [
    "材料如下：\n那它们见顶后谁接力？",
    "材料如下：\n" + "甲公司发布研究观点，行业竞争和客户需求值得关注。" * 3 + "\n那它们见顶后谁接力？",
    "材料如下：\n历史类似，失败案例也看看。",
    "材料如下：\n" + "甲公司发布研究观点，行业竞争和客户需求值得关注。" * 3 + "\n历史类似，失败案例也看看。",
    "「那它们见顶后谁接力？",
])
def test_replay_does_not_promote_material_into_trusted_history(query, trusted_history, tmp_path):
    previous, _ = trusted_history
    history = collect_material_turn_history([message(BASE), message(query, identity="u2")])
    history = ConversationMaterials.from_dict(asdict(history))
    assert history.history_intent is None
    decision = _decide(FOLLOWUPS[0], previous, history)
    control, context, names = _project(decision, tmp_path)
    assert control.terminal_kind == "clarification"
    assert not context.contract.allowed_capabilities and names == ()


@pytest.mark.parametrize("query", [
    *FOLLOWUPS,
    "材料如下：\n甲公司收入增长。\n\n那它们见顶后谁接力？",
    "材料如下：\n甲公司收入增长。\n\n1. 那它们见顶后谁接力？",
    "那它们见顶后谁接力？\n\n材料如下：\n甲公司收入增长。",
    "那它们见顶后谁接力？\n\n报告原文：\n不要历史研究。",
])
def test_independent_live_followup_keeps_local_ceiling(query, trusted_history, tmp_path):
    previous, history = trusted_history
    if query.endswith("不要历史研究。"):
        visible, uncertain = top_level_message_text(query)
        assert not uncertain and "不要历史研究" not in visible
    assert_local(_decide(query, previous, history), tmp_path)


@pytest.mark.parametrize("query", [
    "Apple's revenue rose. What's next?",
    "Don't change the scope.",
    "请分析‘公司的业务’。",
    "请分析\\\"公司的业务\\\"。",
])
def test_apostrophes_and_closed_or_escaped_quotes_are_not_uncertain(query):
    visible, uncertain = top_level_message_text(query)
    assert not uncertain
    assert classify_top_level_regions(query).classification != "boundary_uncertain"
    if "Apple's" in query or "Don't" in query:
        assert visible == query


def test_partition_does_not_hide_numbered_question_case_text():
    text = "只依据以下材料回答。\n\n1. 材料如下：\n甲公司收入增长。\n这说明什么？\n\n2. 请写结论。"
    parts = split_user_message(text)
    visible, uncertain = top_level_message_text(text)
    assert not uncertain
    assert parts.question_ids == ("q1", "q2")
    assert "甲公司收入增长" in visible and "这说明什么" in visible


@pytest.mark.parametrize("query", [
    "材料如下：\n那它们见顶后谁接力？", "「那它们见顶后谁接力？",
    "  那它们见顶后谁接力？",
])
def test_real_entry_does_not_recover_history_from_material(query, trusted_history, tmp_path, monkeypatch):
    from intelligence.runtime import conversation_orchestrator as runtime
    from intelligence.services.conversation_store import ConversationStore
    from intelligence.services.run_store import RunStore

    class Reached(BaseException):
        pass

    previous, _ = trusted_history
    captured = []

    def controller(raw, **kwargs):
        captured.append(_decide(raw, kwargs.get("previous_intent"), kwargs.get("conversation_materials")))
        raise Reached

    monkeypatch.setattr(runtime, "decide_turn", controller)
    store = ConversationStore("history", root=tmp_path / "conversations")
    runs = RunStore("history", root=tmp_path / "runs")
    conv = store.create_conversation()
    store.append_message(conv.conversation_id, "user", BASE, run_id="prior")
    store.append_message(conv.conversation_id, "assistant", "继续研究。", run_id="prior", turn_intent=previous.to_dict())
    run = runs.create_run(query, "ask", session_id=conv.conversation_id)
    store.append_message(conv.conversation_id, "user", query, run_id=run.run_id)
    pending = store.append_message(conv.conversation_id, "assistant", "", status="running", run_id=run.run_id)
    orchestrator = runtime.TurnOrchestrator(repo_root=tmp_path, conversation_store=store, run_store=runs)
    with pytest.raises(Reached):
        orchestrator.run_turn(conversation_id=conv.conversation_id, run_id=run.run_id,
                              assistant_message_id=pending.message_id, query=query,
                              skill_mode="auto", selected_skill_ids=[])
    assert len(captured) == 1
    _, context, names = _project(captured[0], tmp_path)
    assert context.history_intent is None and names == ()
