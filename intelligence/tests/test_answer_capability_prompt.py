"""Task-scoped guidance and native-tool projection, without changing authority."""

from dataclasses import replace
import json

from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.judgment_delta import judgment_delta_receipt
from intelligence.services.research_harness import FinanceResearchHarness
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
