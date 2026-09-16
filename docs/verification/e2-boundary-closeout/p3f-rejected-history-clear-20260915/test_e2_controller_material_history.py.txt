"""Positive controls for P3f: material-only must not erase legitimate user input.

Drive run_turn -> real decide_turn with synthetic ConversationStore/RunStore.
Stop immediately after controller evaluation, before any execution/finalization.
These are compatibility probes, NOT proof of source filtering or D7 inheritance.
"""

import pytest

from intelligence.runtime import conversation_orchestrator as runtime
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import decide_turn
from intelligence.services.user_task import split_user_message


REPORT = (
    "【合成材料】甲公司经营数据说明\n\n"
    "一、订单\n甲公司本期新增订单二十万元，本期收入一百万元，"
    "两项均采用本期人民币万元口径。这里只列示材料内的数字，未提供任何市场行情。\n\n"
    "二、口径\n订单不等于已确认收入，不应把订单与收入直接相加，"
    "比例仅用于说明题面数字之间的关系。\n\n"
    "三、限制\n本材料没有预测下一期收入，也没有介绍同业公司；"
    "不能据此推断市场份额、股价或估值。"
)
QUERY = "只依据以上材料回答。\n\n1. 这篇里提到的订单与收入口径有何不同？"


class ControllerReached(BaseException):
    """Stop before adapter/finalizer; not swallowed by the runtime's fallback."""


@pytest.mark.parametrize("has_user_material", [True, False])
def test_material_only_retains_user_material_or_known_absence(
    tmp_path, monkeypatch, has_user_material,
):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "absent.duckdb"))
    store = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = store.create_conversation()
    if has_user_material:
        store.append_message(conversation.conversation_id, "user", REPORT, run_id="prior")
        store.append_message(
            conversation.conversation_id, "assistant", "已收到用户材料。", run_id="prior",
        )
    run = runs.create_run(QUERY, "ask", session_id=conversation.conversation_id)
    store.append_message(conversation.conversation_id, "user", QUERY, run_id=run.run_id)
    message = store.append_message(
        conversation.conversation_id, "assistant", "", status="running", run_id=run.run_id,
    )
    captured = []
    model_calls = []

    def no_external_model(messages):
        model_calls.append(messages)
        return None, None, "offline author probe"

    def controller(raw, **kwargs):
        decision = decide_turn(raw, **kwargs, llm_complete=no_external_model)
        captured.append(decision)
        raise ControllerReached

    orchestrator = runtime.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=store, run_store=runs,
        turn_controller_fn=controller,
    )
    with pytest.raises(ControllerReached):
        orchestrator.run_turn(
            conversation_id=conversation.conversation_id, run_id=run.run_id,
            assistant_message_id=message.message_id, query=QUERY,
            skill_mode="auto", selected_skill_ids=[],
        )
    assert len(captured) == 1
    decision = captured[0]
    assert decision.task_frame.material_contract.data_scope == "material_only"
    if has_user_material:
        refs = split_user_message(REPORT).materials
        assert refs, "fixture must actually contain a recognized material"
        assert decision.task_frame.referenced_material_ids == tuple(
            ref.material_id for ref in reversed(refs)
        )
        assert decision.lane != "clarify"
    else:
        from intelligence.services.task_frame import MISSING_MATERIAL_CLARIFICATION

        assert decision.lane == "clarify"
        assert MISSING_MATERIAL_CLARIFICATION in decision.clarification_questions
        assert not model_calls, "known missing material must clarify before model input"
