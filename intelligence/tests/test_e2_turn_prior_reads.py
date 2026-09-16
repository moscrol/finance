"""P3d slice: post-controller material_only prior reads, not whole-turn purity.

Drive real run_turn with temporary stores and counted producer seams. Stop at
adapter entry so a scripted result/finalizer cannot mask pre-execution reads.
Controller history, source-aware continuation and deterministic routes remain
outside this slice; injected controllers exercise both canonical/legacy frames.
"""
from collections import Counter
from dataclasses import replace
import socket

import pytest

from intelligence.runtime import conversation_orchestrator as runtime
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import TurnIntent
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import TurnDecision


class AdapterReached(BaseException):
    """Exit the real entry before completion-side effects (not caught as failure)."""


@pytest.mark.parametrize("scope", ["material_only", "local_only", "full", "ordinary"])
@pytest.mark.parametrize("canonical_frame", [True, False])
@pytest.mark.parametrize("prior_raises", [False, True])
def test_post_controller_prior_reads_obey_material_only(
    tmp_path, monkeypatch, scope, canonical_frame, prior_raises,
):
    prefix = {
        "material_only": "只依据以下材料回答。\n\n",
        "local_only": "不要联网。\n\n",
        "full": "可以查真实数据。\n\n",
        "ordinary": "",
    }[scope]
    query = prefix + "「甲公司收入100，订单20。」\n\n1. 甲公司订单占收入多少？"
    if scope == "ordinary":
        query = "甲公司订单占收入多少？"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "absent.duckdb"))
    attempts = Counter()

    def network(*args, **kwargs):
        attempts["network"] += 1
        raise AssertionError("no network in this fixture")

    monkeypatch.setattr(socket.socket, "connect", network)
    monkeypatch.setattr(socket, "getaddrinfo", network)
    frame = understand_query(query).task_frame
    assert frame is not None
    if scope == "ordinary":
        assert frame.material_contract is None
    else:
        assert frame.material_contract.data_scope == scope
        assert not frame.material_contract.needs_clarification
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )
    store = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = store.create_conversation()
    old = store.append_message(
        conversation.conversation_id, "assistant", "旧回答仅用于测试历史坐标。",
        run_id="old-run", turn_intent=intent.to_dict(),
    )
    inherited = replace(intent, inherited_from_turn=old.message_id)
    run = runs.create_run(query, "ask", session_id=conversation.conversation_id)
    store.append_message(conversation.conversation_id, "user", query, run_id=run.run_id)
    message = store.append_message(
        conversation.conversation_id, "assistant", "", status="running", run_id=run.run_id,
    )
    captured = {}
    stance = object()

    def controller(raw, **kwargs):
        captured["controller_context"] = kwargs["context"]
        assert raw == query
        return TurnDecision(
            lane="research", needs_retrieval=True, needs_memory=True, needs_template=True,
            question_type=frame.question_type, subject=frame.subject,
            task_frame=frame if canonical_frame else None, turn_intent=inherited,
        )

    def answer_spec(_run_id):
        attempts["answer_spec"] += 1
        assert _run_id == "old-run"
        return {"research_artifacts": [{"sentinel": "old-provider-artifact"}]}

    def stance_read(*args, **kwargs):
        attempts["stance"] += 1
        return stance

    def prior_read(*args, **kwargs):
        attempts["project_prior"] += 1
        if prior_raises:
            raise RuntimeError("count this even though production catches it")
        return "PROJECT_PRIOR_SENTINEL", "current"

    def perspective_read(*args, **kwargs):
        attempts["perspective"] += 1
        return "PERSPECTIVE_SENTINEL"

    class Adapter:
        def handle(self, *, frame, control):
            captured["frame"] = frame
            captured["control"] = control
            raise AdapterReached

    # Force the normal producer conditions true, without reading any real data.
    monkeypatch.setattr(runtime, "should_run_stance_pack", lambda **kwargs: True)
    monkeypatch.setattr(runtime, "run_stance_pack", stance_read)
    monkeypatch.setattr(runtime.research_project, "prior_for_turn", prior_read)
    monkeypatch.setattr(runtime.perspective_lab, "active_runtime_prompt", perspective_read)
    monkeypatch.setattr(runtime, "deterministic_lane_answer", lambda *args: None)
    orchestrator = runtime.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=store, run_store=runs,
        turn_controller_fn=controller, continuous_turn_adapter=Adapter(),
    )
    monkeypatch.setattr(orchestrator, "_load_answer_spec", answer_spec)
    with pytest.raises(AdapterReached):
        orchestrator.run_turn(
            conversation_id=conversation.conversation_id, run_id=run.run_id,
            assistant_message_id=message.message_id, query=query,
            skill_mode="auto", selected_skill_ids=[],
        )
    assert attempts["network"] == 0
    assert captured["frame"].material_contract == frame.material_contract
    expected = 0 if scope == "material_only" else 1
    assert {name: attempts[name] for name in (
        "answer_spec", "stance", "project_prior", "perspective",
    )} == dict.fromkeys(("answer_spec", "stance", "project_prior", "perspective"), expected)
    control = captured["control"]
    assert control.stance_pack is (None if scope == "material_only" else stance)
    assert control.perspective_context == ("" if scope == "material_only" else "PERSPECTIVE_SENTINEL")
    assert ("PROJECT_PRIOR_SENTINEL" in control.conversation_context) == (
        scope != "material_only" and not prior_raises
    )
    # This test does NOT claim to filter the history already sent to controller.
    assert "旧回答仅用于测试历史坐标" in captured["controller_context"]
