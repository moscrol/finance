"""Task-scoped guidance and native-tool projection, without changing authority."""

from dataclasses import replace
import json

import pytest

from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.judgment_delta import judgment_delta_receipt
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_research_harness import (
    _ScriptedModel,
    _context,
    _evidence,
    _finish_content,
    _frame,
    _registry,
    _tool_turn,
)
from intelligence.runtime.agent_episode import ModelTurn


class _ToolCapturingModel(_ScriptedModel):
    def __init__(self, turns):
        super().__init__(turns)
        self.seen_tools = []

    def complete(self, *, messages, tools, timeout):
        self.seen_tools.append(tools)
        return super().complete(messages=messages, tools=tools, timeout=timeout)


def test_native_runtime_keeps_full_tool_schema_without_duplicate_prompt_prose():
    frame = _frame()
    context = _context(frame)
    registry = _registry((_evidence("evidence-1"),))
    model = _ToolCapturingModel([
        _tool_turn(), ModelTurn(_finish_content(), (), "scripted", ""),
    ])
    definitions = registry.tool_definitions(context.contract.allowed_capabilities)
    full = json.loads(FinanceResearchHarness().assemble_prompt(frame, context, registry)[1])

    outcome = GLMAgentRuntime(client=model).run(
        task_frame=frame, context=context, registry=registry,
    )

    assert outcome.status == "completed"
    compact = json.loads(model.seen_messages[0][1]["content"])
    assert "market_data" in compact["available_tools"]
    assert definitions[0]["function"]["description"] not in compact["available_tools"]
    assert definitions[0]["function"]["description"] in full["available_tools"]
    assert registry.tool_definitions(context.contract.allowed_capabilities) == definitions
    assert model.seen_tools[0] == definitions
    assert {k: v for k, v in compact.items() if k != "available_tools"} == {
        k: v for k, v in full.items() if k != "available_tools"
    }


def test_research_guidance_preserves_substance_without_mandatory_headings():
    frame = _frame()
    context = replace(_context(frame), retrieval_stages=("company_master", "counterevidence"))
    _, text = FinanceResearchHarness().assemble_prompt(frame, context, _registry(()))
    payload = json.loads(text)
    rules = payload["question_type_rules"]
    for marker in ("标题逐字", "逐字写", "没有就写「无」", "每条以"):
        assert marker not in rules
    assert "反证" in rules
    assert "来源" in rules or "证据序号" in rules
    stages = payload["retrieval_stages_rule"]
    assert "可选" in stages
    assert "每个阶段都应有" not in stages
    assert "用户" in stages and "缺口" in stages


def test_untemplated_answer_is_not_scored_as_missing_research():
    receipt = judgment_delta_receipt(
        "订单是否兑现仍取决于验收；客户取消订单会削弱判断，需跟踪后续公告。",
        query="这份订单会如何影响公司利润？",
        question_type="stock_deep_dive",
    )
    assert "missing_elements" not in receipt
    assert receipt["quality_assessment"] == "not_evaluated"


@pytest.mark.parametrize("route", ["quick_fact", "concept_definition", "methodology_discussion"])
@pytest.mark.parametrize("user_goal", ["回答所请求的事实", "判断反事实条件下原结论是否成立"])
@pytest.mark.parametrize("question", [
    "请查宁德时代2026-09-24的收盘价和成交额。", "请查询宁德时代当前的收盘价和成交额。",
])
@pytest.mark.parametrize("entity_catalogue", [False, True], ids=["unanchored", "anchored"])
def test_semantic_knowledge_route_cannot_remove_fact_floor_during_episode_assembly(
    route, user_goal, question, entity_catalogue, tmp_path, monkeypatch,
):
    relations = tmp_path / "relations"
    relations.mkdir()
    entities = {"宁德时代": {"codes": ["300750.SZ"], "concepts": {}}} if entity_catalogue else {}
    (relations / "entity_exposures.json").write_text(
        json.dumps({"entities": entities}), encoding="utf-8",
    )
    monkeypatch.setenv("WORKBENCH_KNOWLEDGE_WIKI", str(tmp_path))
    monkeypatch.setenv("ENTITY_ANCHOR_SECURITIES_DB", "disabled")
    reply = json.dumps({
        "route_id": route, "confidence": 0.9, "reason": "test erroneous knowledge route",
        "user_goal": user_goal, "assumptions": [], "ambiguities": [],
    })
    control = TurnControlCore().control(
        question, llm_complete=lambda _messages: (reply, object(), ""),
    )
    assert control.needs_retrieval
    context = build_episode_context(
        control.task_frame, task_id=f"fact-floor:{entity_catalogue}:{route}:{question}:{user_goal}",
        capabilities=control.capabilities,
        today="2026-09-30", latest_data_date="2026-09-30",
    )
    assert context.contract.allowed_capabilities
    # Unanchored fact queries may retain an optional personal-memory slot. It
    # cannot replace the required factual outputs or supply their evidence.
    outputs = context.contract.required_outputs
    required = tuple(item for item in outputs if item.required)
    assert required
    assert {item.grounding_mode for item in required} == {"evidence"}
    assert {(item.output_id, item.grounding_mode) for item in outputs
            if item.grounding_mode != "evidence"} <= {("prime_memory", "user_premise")}
    for basis in ("model_reasoning", "user_premise", "evidence"):
        content = json.dumps({
            "status": "completed", "draft": "宁德时代当日收盘价123.45元，成交额10亿元。", "gaps": [],
            "bindings": [{"output_id": item.output_id, "basis": basis, "evidence_hashes": []}
                         for item in required],
        })
        admission = FinanceResearchHarness().admit_finish(
            content, context=context, evidence=(), registry=ResearchToolRegistry(()),
        )
        assert not admission.accepted

    source_date = "2026-09-24" if "2026-09-24" in question else "2026-09-30"
    draft = f"宁德时代{source_date}收盘价123.45元，成交额10亿元；仅覆盖该交易日。"
    evidence = replace(
        _evidence("fact-floor-data", title="宁德时代日行情"),
        detail=draft, source_date=source_date,
    )
    content = json.dumps({
        "status": "completed", "draft": draft, "gaps": [],
        "bindings": [{"output_id": item.output_id, "basis": "evidence",
                      "evidence_hashes": [evidence.content_hash]} for item in required],
    })
    admission = FinanceResearchHarness().admit_finish(
        content, context=context, evidence=(evidence,), registry=_registry((evidence,)),
    )
    assert admission.accepted, admission
