from __future__ import annotations

from pathlib import Path

from intelligence.services.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.research_contract import (
    OWNER_RETRIEVAL_STAGES,
    OWNER_WORKFLOW_SPECS,
    RESEARCH_OWNER_IDS,
    TurnIntent,
)
from intelligence.services.run_store import RunStore
from intelligence.services.turn_controller import TurnDecision
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
)
from intelligence.workbench_skills.registry import SkillRegistry
from intelligence.workbench_skills.router import route_skills


def _definition(skill_id: str, trigger: str) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        name=skill_id,
        description=f"{skill_id} fixture",
        version="1.0.0",
        triggers=(trigger,),
        input_schema={"type": "object"},
        permissions=("local_read",),
        timeout_seconds=240,
    )


def test_all_research_owners_have_consistent_inline_workflow_specs() -> None:
    assert set(OWNER_WORKFLOW_SPECS) == RESEARCH_OWNER_IDS
    for owner, spec in OWNER_WORKFLOW_SPECS.items():
        assert spec.owner == owner
        assert spec.execution_mode in {"inline", "subtask"}
        assert spec.execution_mode == "inline"
        assert spec.retrieval_stages == OWNER_RETRIEVAL_STAGES[owner]
        assert spec.required_skill_ids[-1] == owner
        assert spec.output_schema == "AnswerSpec"
        assert spec.max_wall_time_seconds == 240


def test_router_cannot_replace_controller_owner_with_workflow_spec() -> None:
    registry = {
        "stock-deep-dive": _definition("stock-deep-dive", "深挖"),
        "news-impact": _definition("news-impact", "影响"),
    }

    result = route_skills(
        "请深挖英维克并分析客户影响",
        "ask",
        "auto",
        [],
        registry=registry,
        answer_owner=OWNER_WORKFLOW_SPECS["stock-deep-dive"].owner,
        llm_complete=lambda _messages: (
            '{"skill_ids":["news-impact"],'
            '"reasons":{"news-impact":"消息影响"}}',
            object(),
            "",
        ),
    )

    assert [selection.skill_id for selection in result.selections] == [
        "stock-deep-dive"
    ]


def test_manual_skill_selection_does_not_rewrite_controller_owner() -> None:
    intent = TurnIntent(
        primary_subject="英维克",
        secondary_topics=("液冷",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
    )
    registry = {
        "stock-deep-dive": _definition("stock-deep-dive", "深挖"),
        "daily-agent": _definition("daily-agent", "今天研究什么"),
    }

    result = route_skills(
        "今天研究什么",
        "ask",
        "manual",
        ["daily-agent"],
        registry=registry,
        answer_owner=intent.answer_owner,
    )

    assert [selection.skill_id for selection in result.selections] == [
        "daily-agent"
    ]
    assert intent.answer_owner == "stock-deep-dive"


class _OwnerSkill:
    skill_id = "stock-deep-dive"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        modules = [
            {
                "type": "summary",
                "summary": "公司公告披露液冷业务进展。",
            }
        ]
        citations = [
            {
                "source": "announcement.json",
                "title": "公司公告",
                "evidence_layer": "canonical",
                "as_of": "2026-07-15",
            }
        ]
        contract = build_module_answer_contract(
            skill_id=self.skill_id,
            title="个股深挖",
            modules=modules,
            citations=citations,
            warnings=[],
            as_of="2026-07-15",
            retrieval_plan=("读取公司公告",),
            output_contract=("只输出可追溯事实",),
        )
        assert contract is not None
        return SkillOutput(
            skill_id=self.skill_id,
            modules=modules,
            citations=citations,
            warnings=[],
            as_of="2026-07-15",
            raw_result_ref=None,
            answer_contract=contract,
        )


def test_orchestrator_emits_workflow_loaded_before_owner_start(
    tmp_path: Path,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "请个股深挖英维克"
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation.conversation_id,
    )
    conversation_store.append_message(
        conversation.conversation_id,
        "user",
        query,
        run_id=run.run_id,
    )
    assistant = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    registry = SkillRegistry()
    registry.register(
        _definition("stock-deep-dive", "深挖"),
        _OwnerSkill(),
    )
    intent = TurnIntent(
        primary_subject="英维克",
        secondary_topics=(),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda _options: (_ for _ in ()).throw(
            AssertionError("owner contract must bypass generic ask")
        ),
        skill_registry=registry,
        turn_controller_fn=lambda _query, **_kwargs: TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            reason="fixture",
            turn_intent=intent,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        assistant_message_id=assistant.message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    events = run_store.load_stream_events(run.run_id)
    workflow = next(
        event for event in events if event["event_type"] == "workflow.loaded"
    )
    owner_start = next(
        event
        for event in events
        if event["event_type"] == "skill.start"
        and event["payload"]["skill_id"] == "stock-deep-dive"
    )
    spec = OWNER_WORKFLOW_SPECS["stock-deep-dive"]
    assert workflow["seq"] < owner_start["seq"]
    assert workflow["payload"] == {
        **spec.to_dict(),
        "required_skill_ids": list(spec.required_skill_ids),
        "retrieval_stages": list(spec.retrieval_stages),
        "status": "loaded",
    }
