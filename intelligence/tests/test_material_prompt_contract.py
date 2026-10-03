"""Prompt ownership, not semantic acceptance of any generated answer."""
from dataclasses import replace
import json
from uuid import uuid4

import pytest

from intelligence.eval.knevo_regression import load_suite
from intelligence.services.conversation_materials import ConversationMaterials
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import _question_type_rules, build_episode_input
from intelligence.services.material_answer_authoring import material_author_payload
from intelligence.services.research_reasoning import guidance as reasoning_guidance
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.research_workflow_guidance import workflow_guidance
from intelligence.services.turn_controller import decide_turn

PACKS = tuple(case for case in load_suite() if case.case_id.startswith("K260917-pack"))
TYPE_GUIDANCE_HEADINGS = ("跟踪方法建议（可选）", "情景树表达契约", "排序方法建议（可选）")
RETIRED_HEADINGS = ("跟踪表达契约", "排序与情景表达契约")


def context_for(case):
    frame = decide_turn(case.question, conversation_materials=ConversationMaterials()).task_frame
    return frame, build_episode_context(frame, task_id=f"material-prompt-{uuid4().hex}")


@pytest.mark.parametrize("case", PACKS, ids=lambda case: case.case_id)
def test_numbered_material_contract_owns_prompt_without_dropping_questions(case, monkeypatch):
    monkeypatch.setenv("FINANCE_RESEARCH_REASONING", "off")
    frame, context = context_for(case)
    original_contract = context.contract.to_dict()
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    rules = payload["question_type_rules"]
    assert all(heading not in rules for heading in (*TYPE_GUIDANCE_HEADINGS, *RETIRED_HEADINGS))
    assert "financial_data" not in rules
    assert "memory_lookup" not in rules
    assert "E1、E2" not in rules
    assert rules == workflow_guidance(frame.question_type)
    assert context.contract.to_dict() == original_contract
    assert payload["task_frame"]["raw_question"] == frame.raw_question == case.question.strip()
    assert payload["research_contract"] == json.loads(json.dumps({
        key: value for key, value in original_contract.items() if key not in {"task_id", "material_grounding"}
    }))
    assert payload["material_grounding"] == json.loads(json.dumps(material_author_payload(context.contract)))
    assert payload["material_grounding"]["finish_format"]["format"] == "material_claims_v1"
    assert [(q["question_id"], q["text"]) for q in payload["material_delivery"]["questions"]] == [
        (q.question_id, q.text) for q in context.contract.material_contract.questions
    ]
    assert len(payload["material_delivery"]["questions"]) == 8
    assert payload["available_tools"] == ""
    assert context.contract.allowed_capabilities == ()


@pytest.mark.parametrize("case", PACKS, ids=lambda case: case.case_id)
def test_writer_gets_sentence_construction_checks_in_compact_template(case):
    frame, context = context_for(case)
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    format_payload = payload["material_grounding"]["finish_format"]
    rule = format_payload["rule"]
    for instruction in (
        "先找齐本句使用的原始输入",
        "即使输入来自同一材料或已在前句引用",
        "数字、计算、事实比较或事实前提",
        "同一主体、指标、单位及各自期间",
        "厂商出货、渠道库存、终端消耗不能互换",
        "缺少成本口径时不能把收入方向等同于利润方向",
        "未给正常库存基准时不把库存增减直接定性为过剩或安全",
    ):
        assert instruction in rule
    template = json.loads(format_payload["wire_template"])
    assert template == {
        "format": "material_claims_v1", "status": "completed",
        "answers": [
            {"output_id": spec.output_id, "claims": []}
            for spec in context.contract.required_outputs if spec.required
        ],
    }


@pytest.mark.parametrize("scope,clarify", [
    ("full", False), (None, True), ("material_only", True),
])
def test_unsettled_or_non_material_scope_keeps_type_guidance(scope, clarify):
    frame, context = context_for(PACKS[0])
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    expected = _question_type_rules(frame, ordinary)
    assert all(heading in expected for heading in TYPE_GUIDANCE_HEADINGS)
    assert all(heading not in expected for heading in RETIRED_HEADINGS)
    changed = replace(context, contract=replace(context.contract, material_contract=replace(
        context.contract.material_contract, data_scope=scope,
        classification="boundary_uncertain" if clarify else "constraint_confirmed",
    )))
    assert _question_type_rules(frame, changed) == expected


def test_settled_local_only_numbered_questions_follow_numbered_delivery():
    """main 8fd6882ea（09-22，经 #942 合入）：local_only 也按原题号逐题交付，编号交付合同
    决定答案形状，旧版题型关键词模板不再叠加——与 material_only 编号题同一条路。
    本分支原测试把 local_only 归入「保留旧提示词」，前向合并后按后定的产品决定改钉。"""
    frame, context = context_for(PACKS[0])
    changed = replace(context, contract=replace(context.contract, material_contract=replace(
        context.contract.material_contract, data_scope="local_only",
        classification="constraint_confirmed",
    )))
    assert _question_type_rules(frame, changed) == (
        workflow_guidance(frame.question_type) + reasoning_guidance(frame.question_type)
    )


def test_material_prompt_preserves_typed_discipline_and_opt_in_reasoning(monkeypatch):
    monkeypatch.setenv("FINANCE_RESEARCH_WORKFLOW_GUIDANCE", "1")
    monkeypatch.setenv("FINANCE_RESEARCH_REASONING", "on")
    frame, context = context_for(PACKS[0])
    frame = replace(frame, question_type="news_impact")
    context = replace(context, contract=replace(context.contract, question_type=frame.question_type))
    rules = _question_type_rules(frame, context)
    assert "消息逐项拆为事实、解读与情绪表达" in rules
    assert "研究求证意识" in rules
    assert rules == workflow_guidance(frame.question_type) + reasoning_guidance(frame.question_type)
    monkeypatch.setenv("FINANCE_RESEARCH_REASONING", "off")
    assert _question_type_rules(frame, context) == workflow_guidance(frame.question_type)


def test_unnumbered_material_prompt_keeps_ordinary_type_guidance():
    frame, context = context_for(PACKS[0])
    context = replace(context, contract=replace(context.contract, material_contract=replace(
        context.contract.material_contract, questions=(),
    )))
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    rules = _question_type_rules(frame, context)
    assert all(heading in rules for heading in TYPE_GUIDANCE_HEADINGS)
    assert all(heading not in rules for heading in RETIRED_HEADINGS)
    assert rules == _question_type_rules(frame, ordinary)


# ---------------------------------------------------------------- 编号材料题包的调用上限（2026-09-27）


def test_numbered_material_pack_gets_the_pack_turn_floor_others_do_not():
    from intelligence.services.material_delivery import material_pack_turn_seconds
    from intelligence.services.provider_latency import MATERIAL_PACK_TURN_SECONDS

    frame, context = context_for(PACKS[0])
    assert material_pack_turn_seconds(context.contract) == MATERIAL_PACK_TURN_SECONDS == 150.0
    unnumbered = replace(context, contract=replace(context.contract, material_contract=replace(
        context.contract.material_contract, questions=(),
    )))
    assert material_pack_turn_seconds(unnumbered.contract) == 0.0
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    assert material_pack_turn_seconds(ordinary.contract) == 0.0


def test_episode_turn_ceiling_is_lifted_only_for_material_packs():
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode

    frame, context = context_for(PACKS[0])
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    episode = ContinuousAgentEpisode(object(), llm_timeout=75.0)
    assert episode._turn_ceiling(context) == 150.0
    assert episode._turn_ceiling(ordinary) == 75.0
    # provider 标定更高时不被压低
    assert ContinuousAgentEpisode(object(), llm_timeout=300.0)._turn_ceiling(context) == 300.0


def test_material_pack_floor_joins_the_repair_cap_but_env_override_still_wins():
    from intelligence.services.provider_latency import with_rewrite_floor

    assert with_rewrite_floor(40.0, 0, floor_seconds=150.0, env={}) == 150.0
    assert with_rewrite_floor(40.0, 0, floor_seconds=0.0, env={}) == 40.0
    assert with_rewrite_floor(40.0, 0, floor_seconds=150.0, env={"ASK_REPAIR_SECONDS_CAP": "40"}) == 40.0


def test_material_pack_writer_is_glm53_only_on_glm53_deployments(monkeypatch):
    from intelligence.services.material_delivery import material_pack_writer_model

    frame, context = context_for(PACKS[0])
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    monkeypatch.delenv("MATERIAL_PACK_WRITER_MODEL", raising=False)
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_MODEL", "glm-5.3-flash")
    assert material_pack_writer_model(context.contract) == "glm-5.3"
    assert material_pack_writer_model(ordinary.contract) is None
    # 别家 provider 不被硬塞 GLM 模型名
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_MODEL", "gpt-5.6-sol")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert material_pack_writer_model(context.contract) is None
    # 显式配置优先：指定模型 / 关掉
    monkeypatch.setenv("MATERIAL_PACK_WRITER_MODEL", "glm-5.2")
    assert material_pack_writer_model(context.contract) == "glm-5.2"
    monkeypatch.setenv("MATERIAL_PACK_WRITER_MODEL", "off")
    assert material_pack_writer_model(context.contract) is None


def test_episode_run_scopes_the_material_pack_writer(monkeypatch):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services import llm_refine

    monkeypatch.delenv("MATERIAL_PACK_WRITER_MODEL", raising=False)
    monkeypatch.setenv("FORESIGHT_BUILTIN_LLM_MODEL", "glm-5.3-flash")
    frame, context = context_for(PACKS[0])
    ordinary = replace(context, contract=replace(context.contract, material_contract=None))
    seen: list[object] = []

    class Drive:
        def run_to_end(self):
            seen.append(llm_refine.writer_model_override())
            return "outcome"

    episode = ContinuousAgentEpisode(object(), llm_timeout=75.0)
    monkeypatch.setattr(episode, "manual_drive", lambda **_kwargs: Drive())
    assert episode.run(task_frame=frame, context=context, registry=None) == "outcome"
    assert episode.run(task_frame=frame, context=ordinary, registry=None) == "outcome"
    assert seen == ["glm-5.3", None]
    assert llm_refine.writer_model_override() is None
