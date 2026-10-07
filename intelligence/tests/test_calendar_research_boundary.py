"""Calendar truth can disclose a gap without completing unrelated research."""
from dataclasses import fields, replace
import json
from pathlib import Path

import pytest

from intelligence.services.honesty_gates import calendar_disclosure, with_calendar_disclosure
from intelligence.services.lane_generation import deterministic_lane_answer
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision, decide_turn
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.run_store import RunStore
from intelligence.services.research_contract import TurnIntent


def frozen_stock_decision() -> TurnDecision:
    payload = json.loads((Path(__file__).parent / "fixtures/calendar-stock-research-frame.json").read_text())
    frame = TaskFrame.from_dict(payload["task_frame"])
    original = payload["decision"]
    kwargs = {field.name: original[field.name] for field in fields(TurnDecision)
              if field.name in original and field.name not in {"task_frame", "turn_intent"}}
    return TurnDecision(**kwargs, task_frame=frame)


def test_frozen_company_research_keeps_its_owner_after_calendar_disclosure() -> None:
    decision = frozen_stock_decision()
    frame = decision.task_frame
    assert decision.lane == "research" and decision.needs_retrieval
    assert frame.question_type == "stock_deep_dive"
    assert calendar_disclosure(frame)
    assert deterministic_lane_answer(frame.raw_question, decision) is None


def test_workbench_dispatches_the_frozen_company_task_to_its_research_owner(tmp_path) -> None:
    decision = frozen_stock_decision()
    frozen = decision.task_frame
    intent = TurnIntent(primary_subject=frozen.subject, secondary_topics=(),
        question_type=frozen.question_type, answer_owner="stock-deep-dive",
        comparison_entities=(), inherited_from_turn=None,
        timeframe=frozen.timeframe, required_outputs=frozen.required_outputs,
        task_frame_hash=frozen.task_frame_hash)
    decision = replace(decision, turn_intent=intent)
    conversations = ConversationStore("calendar-boundary-probe", root=tmp_path / "conversations")
    runs = RunStore("calendar-boundary-probe", root=tmp_path / "runs")
    conversation = conversations.create_conversation()
    run = runs.create_run(frozen.raw_question, "ask", session_id=conversation.conversation_id)
    conversations.append_message(conversation.conversation_id, "user", frozen.raw_question, run_id=run.run_id)
    assistant = conversations.append_message(conversation.conversation_id, "assistant", "", status="pending", run_id=run.run_id)
    called = []

    class Owner:
        def handle(self, *, frame, control):
            assert frame is control.task_frame
            assert frame.evidence_policy == "company_multi_layer_evidence"
            assert calendar_disclosure(frame)
            called.append(frame)
            return ContinuousTurnResult(handled=True, status="completed",
                answer=with_calendar_disclosure("公司证据与客户线索由原研究所有者继续核对。", frame),
                as_of="2026-10-07", citations=(), warnings=(), private_artifact={}, events=())

    def forbidden(*args, **kwargs):
        raise AssertionError("calendar must not dispatch company research to a fallback author")

    TurnOrchestrator(repo_root=tmp_path, conversation_store=conversations, run_store=runs,
        turn_controller_fn=lambda *_args, **_kwargs: decision,
        continuous_turn_adapter=Owner(), answer_query_fn=forbidden,
        route_skills_fn=forbidden, lane_answer_fn=forbidden).run_turn(
            conversation_id=conversation.conversation_id, run_id=run.run_id,
            assistant_message_id=assistant.message_id, query=frozen.raw_question,
            skill_mode="manual", selected_skill_ids=[])
    assert len(called) == 1
    answer = (runs.run_dir(run.run_id) / "answer.md").read_text()
    assert "原研究所有者继续核对" in answer
    assert "休市" in answer


@pytest.mark.parametrize("query", [
    "截至2026年10月7日，存储涨价如何传导到公司利润？",
    "截至2026年10月7日，长电科技今年利润同比多少？",
    "截至2026年10月7日，长电科技估值贵不贵？",
    "截至2026年10月7日，长电科技近期公告对产业链有什么影响？",
])
def test_nonmarket_evidence_duties_continue_when_the_exchange_is_closed(query: str) -> None:
    decision = decide_turn(query)
    assert calendar_disclosure(decision.task_frame)
    assert deterministic_lane_answer(query, decision) is None


@pytest.mark.parametrize("policy", [
    "personal_memory_recall", "stable_knowledge", "model_reasoning",
    "source_critique_evidence", "comparable_multi_source_evidence",
    "official_disclosure_scan", "event_scenario_evidence", "claim_verification_evidence",
    "future_unrecognized_evidence_policy",
])
def test_calendar_does_not_gain_terminal_authority_over_other_evidence_policies(policy: str) -> None:
    decision = frozen_stock_decision()
    frame = replace(decision.task_frame, evidence_policy=policy)
    decision = replace(decision, task_frame=frame)
    assert calendar_disclosure(frame)
    assert deterministic_lane_answer(frame.raw_question, decision) is None


def test_calendar_boundary_remains_in_the_research_delivery() -> None:
    frame = frozen_stock_decision().task_frame
    original = "公司公告与行业线索分开核对；已有材料不能证明具体客户订单。"
    delivered = with_calendar_disclosure(original, frame)
    assert delivered.startswith(calendar_disclosure(frame))
    assert delivered.endswith(original)
    assert "回答须先说明" not in delivered


@pytest.mark.parametrize("query", [
    "2026-02-17 涨停家数多少", "2026-07-25 市场怎么样",
])
def test_existing_closed_day_market_shortcuts_remain(query: str) -> None:
    decision = decide_turn(query)
    answer = deterministic_lane_answer(query, decision)
    assert answer and "休市" in answer and "前一交易日" in answer
