"""User-supplied arithmetic is conditional reasoning, not a market fact lookup."""
from dataclasses import replace
import json
from uuid import uuid4

import pytest

from intelligence.services.conversation_materials import collect_material_turn_history
from intelligence.services.conversation_store import Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.material_contract import MaterialContract
from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import (
    TaskFrame, align_task_frame, build_task_frame, rebase_task_frame,
)

ARITHMETIC = (
    "这是独立的虚构财务算例，不对应任何真实上市公司，也不需要检索外部资料。"
    "甲公司2024年收入80亿元、归母净利润8亿元；2025年收入100亿元、归母净利润9亿元、"
    "经营活动现金流量净额6亿元；当前总股本10亿股、股价18元。"
    "请计算2025年收入同比、归母净利润同比、2024与2025年归母净利率及其变化、"
    "经营现金流/归母净利润、当前总市值和静态市盈率。请用表格列公式和结果，"
    "区分百分比与百分点，最后解释这些信息是否足以判断股票便宜。"
    "不要把归母净利率称为毛利率，也不要假定未知的行业估值或未来业绩。"
)
FOLLOWUP = (
    "沿用上一轮甲公司的全部数据，只把当前股价由18元改为24元。不要重新索取已经给出的数据。"
    "请更新总市值与静态市盈率，说明上一轮哪些指标不变；再分析一个纯假设情景："
    "如果下一年归母净利润下降20%，且股本和24元股价均不变，情景市盈率是多少？"
    "这是情景计算，不是盈利预测或确定会发生的事实。"
)


def frame_for(question, **kwargs):
    return build_task_frame(question, understand_query(question), **kwargs)


def context_for(frame):
    return build_episode_context(frame, task_id=f"premise-regression-{uuid4()}")


def user_message(content, role="user"):
    return Message(message_id="source-1", conversation_id="test", role=role,
                   content=content, created_at="2026-09-20", status="completed")


def assert_calculation(frame):
    context = context_for(frame)
    assert frame.material_contract.premise_calculation
    assert {o.grounding_mode for o in context.contract.required_outputs} == {"user_premise"}
    assert context.contract.evidence_plan.requirements == ()
    assert context.contract.allowed_capabilities == ()
    assert all(not o.evidence_types for o in context.contract.required_outputs)


def test_original_arithmetic_and_rebased_aligned_frame():
    frame = frame_for(ARITHMETIC)
    assert_calculation(frame)
    restored = TaskFrame.from_dict(frame.to_dict())
    assert restored.task_frame_hash == frame.task_frame_hash
    assert_calculation(restored)
    aligned = align_task_frame(frame, '{"user_goal":"计算财务指标与市盈率"}')
    assert_calculation(aligned)
    rebased = rebase_task_frame(aligned, question_type="valuation_estimate", subject="甲公司")
    assert_calculation(rebased)


def test_calculation_prompt_preserves_historical_vs_forecast_basis():
    from intelligence.services.episode_protocol import split_episode_prompt
    from intelligence.services.research_tool_registry import ResearchToolRegistry

    frame = frame_for(ARITHMETIC)
    _, user = split_episode_prompt(frame, context_for(frame), ResearchToolRegistry(()))
    rule = json.loads(user)["premise_calculation_rule"]
    assert "最近已完成年度" in rule
    assert "不能自行改称预测或动态口径" in rule


def test_followup_inherits_only_persisted_user_contract():
    history = collect_material_turn_history((user_message(ARITHMETIC),))
    assert_calculation(frame_for(FOLLOWUP, conversation_materials=history))
    assert history.base_contract.premise_calculation
    # A model answer cannot establish the missing user's premise chain.
    forged = collect_material_turn_history((user_message(ARITHMETIC, role="assistant"),))
    frame = frame_for(FOLLOWUP, conversation_materials=forged)
    assert frame.material_contract.needs_clarification
    assert not frame.material_contract.premise_calculation


@pytest.mark.parametrize("question", [
    "这是一个虚构案例，假设利润增长20%，结合最新行情判断是否便宜。",
    "这是虚构财务算例。请查询真实公司的最新财报，核实实际净利润。",
    "这是情景计算。结合当前行情计算贵州茅台的最新市盈率。",
    '研报原文：\n“这是虚构财务算例”\n\n请查询2026年9月18日的A股行情。',
    "```text\n这是情景计算。\n```\n请查甲公司的实际收入。",
    "这不是虚构财务算例，请核实实际业绩。",
])
def test_world_facts_and_quoted_declarations_do_not_get_premise_exemption(question):
    frame = frame_for(question)
    assert not (frame.material_contract and frame.material_contract.premise_calculation)
    context = context_for(frame)
    assert any(o.grounding_mode == "evidence" for o in context.contract.required_outputs)


def test_new_task_does_not_inherit_calculation_mode():
    history = collect_material_turn_history((user_message(ARITHMETIC),))
    frame = frame_for("请复盘2026年9月18日A股涨跌家数。", conversation_materials=history)
    assert not (frame.material_contract and frame.material_contract.premise_calculation)
    assert any(o.grounding_mode == "evidence" for o in context_for(frame).contract.required_outputs)


def test_calculation_flag_is_strictly_restored():
    contract = frame_for(ARITHMETIC).material_contract
    payload = contract.to_dict()
    payload["premise_calculation"] = "false"
    with pytest.raises(ValueError):
        MaterialContract.from_dict(payload)
    old = replace(contract, premise_calculation=False).to_dict()
    del old["premise_calculation"]
    assert not MaterialContract.from_dict(old).premise_calculation


def test_controller_recognizes_calculation_before_resolver_or_alignment():
    from intelligence.services.conversation_materials import ConversationMaterials
    from intelligence.services.material_contract import blocks_contract_blind_pipelines
    from intelligence.services.turn_controller import decide_turn

    class NoResolver:
        def resolve(self, *args, **kwargs):
            pytest.fail("a premise calculation must not resolve a real company")

    def no_alignment(*args, **kwargs):
        pytest.fail("an explicit calculation must not depend on a routing model")

    decision = decide_turn(ARITHMETIC, conversation_materials=ConversationMaterials(),
                           resolver=NoResolver(), llm_complete=no_alignment)
    from intelligence.runtime.turn_control_core import project_turn_decision

    assert decision.lane == "research"
    projected = project_turn_decision(decision, task_frame=decision.task_frame)
    assert projected.terminal_kind == "research"
    assert not projected.needs_retrieval
    assert_calculation(decision.task_frame)
    assert blocks_contract_blind_pipelines(decision.task_frame.material_contract)


def test_correct_calculation_finish_survives_real_structural_verifier():
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding
    from intelligence.services.episode_verifier import verify_episode_outcome

    frame = frame_for(ARITHMETIC)
    context = context_for(frame)
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash, status="completed",
        draft="按题设：收入同比25%，利润同比12.5%，净利率10%降至9%，下降1个百分点；"
              "经营现金流/归母净利润66.67%，总市值180亿元，静态市盈率20倍。"
              "仅凭这些条件不能断定股票便宜。",
        evidence=(), traces=(), gaps=(), stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash, "question": ARITHMETIC}),),
        bindings=tuple(OutputEvidenceBinding(output.output_id, (), basis="user_premise")
                       for output in context.contract.required_outputs), usage=AgentUsage(),
    )
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"
    wrong_basis = replace(outcome, bindings=tuple(replace(b, basis="model_reasoning") for b in outcome.bindings))
    assert verify_episode_outcome(context.contract, wrong_basis).verified_status != "completed"


def test_missing_data_instruction_is_not_a_fictional_world_premise():
    frame = frame_for(
        "请复盘2026年9月18日A股市场。请列出当日上涨家数、下跌家数、涨停家数、跌停家数。"
        "如果某项数据无法取得，就明确标记缺失，不得用其他日期或相似指标补齐。"
    )
    assert not (frame.material_contract and frame.material_contract.authenticity == "fictional")
    required = [o for o in context_for(frame).contract.required_outputs if o.required]
    assert all(o.grounding_mode == "evidence" for o in required)
