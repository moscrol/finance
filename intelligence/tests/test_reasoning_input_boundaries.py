"""Regression cases from real reasoning probes, not a semantic quality score."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import json

import pytest

from intelligence.services.conversation_materials import (
    ConversationMaterials,
    collect_material_turn_history,
)
from intelligence.services.conversation_store import Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input, resolve_evidence_refs
from intelligence.services.episode_tools import _task_authorizes_historical_window
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import build_turn_intent, is_contextual_follow_up
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import decide_turn
from intelligence.services.user_task import classify_top_level_regions, requests_previous_answer_review

SUPPLY = (
    "只分析以下虚构材料，不查其他资料：甲行业下游订单量连续两季增长，"
    "行业产能固定且交付期延长，产品提价后毛利率上升。同期市场成交额下降。"
    "为什么行业利润可能改善？用最贴合材料的解释回答，不确定的部分保留。"
)
LOCAL = (
    "请只查本地数据，解释2026年9月11日A股成交额环比增加但多数股票下跌，"
    "和9月14日成交额缩小但上涨家数改善的差异。成交增加是否足以证明新增资金入场？"
    "优先补查能区分解释的证据，无法取得的保持未知，不联网。"
)
REVIEW = (
    "请复核刚才的解释：我们取得的总量数据没有逐笔卖单、实际资金申赎和市值分组收益。"
    "既然如此，哪些关于资金行为和修复来源的判断仍有多种解释？"
    "请明确撤回证据不支持的断言，保留还能成立的结论。仍只用已取得的本地数据。"
)
REVIEW_WITH_REREAD = REVIEW.replace(
    "仍只用已取得的本地数据。", "允许在原日期范围内重新查询本地数据。",
)
LADDER_QUESTION = "2026-07-22 高标股的晋级情况如何，有没有出现空档"
LADDER_REVIEW = (
    "请复核上一答的晋级分母、成功者名单与失败候选覆盖，并修订。"
    "只用本次会话取得的证据；没有完整候选或失败名单时保留缺口，"
    "不把成功者名单推成整体晋级率或整体健康程度。"
    "保留能核验的连板结构、日期、口径和局部引用。"
)
SUPPLIED_COMPARISON = (
    "只根据以下虚构题设分析，不查库、不联网、不写记忆。"
    "甲公司收入从100亿元增至130亿元，利润从10亿元增至13亿元，应收账款从20亿元增至45亿元，"
    "经营现金流从6亿元降至4亿元；乙公司收入从100亿元增至120亿元，利润从10亿元增至12亿元，"
    "应收账款从20亿元增至23亿元，经营现金流从9亿元增至11亿元。哪家的增长质量更扎实？"
    "请解释利润、应收与现金的关系，列出最关键的反证和下一步验证点；不要据此给估值或交易结论。"
)
REPEAT_WITHOUT_REREAD = (
    "沿用我们刚才这轮对话，不重新查询：你上一条关于长电科技给出的收盘价、涨跌幅、成交额和数据日期"
    "分别是什么？请简洁复述，并明确说明这些数值本轮未重新核验。"
)


def no_llm(*_args, **_kwargs):
    return None, None, "disabled in test"


def message(text, role="user", identity="first"):
    return Message(identity, "conv", role, text, "2026-09-20", "completed")


def material(text, base=None):
    return compile_material_contract(classify_top_level_regions(text), inherited_contract=base)


def test_original_supply_freezes_read_ceiling_before_resolver_or_model():
    class ForbiddenResolver:
        def resolve(self, _query):
            pytest.fail("material-only turn must precede resolver reads")

    def forbidden_model(*_args, **_kwargs):
        pytest.fail("material-only turn must precede controller model")

    decision = decide_turn(
        SUPPLY, conversation_materials=ConversationMaterials(),
        resolver=ForbiddenResolver(), llm_complete=forbidden_model,
    )
    frame = decision.task_frame
    assert decision.lane == "research"
    assert (frame.material_contract.authenticity, frame.material_contract.data_scope) == (
        "fictional", "material_only",
    )
    context = build_episode_context(frame, task_id="supply")
    assert context.contract.allowed_capabilities == ()
    assert context.contract.evidence_plan.requirements == ()
    # Do not bypass the pending material-claim grounding work by granting blanket premise basis.
    assert next(o for o in context.contract.required_outputs if o.output_id == "direct_answer").grounding_mode == "evidence"


@pytest.mark.parametrize("question,authenticity", [
    (SUPPLIED_COMPARISON, "fictional"), (REPEAT_WITHOUT_REREAD, "real"),
])
def test_natural_frozen_inputs_precede_resolver_and_reach_empty_tool_contract(question, authenticity):
    class ForbiddenResolver:
        def resolve(self, _query):
            pytest.fail("explicit frozen input must prevent new resolver reads")

    def forbidden_model(*_args, **_kwargs):
        pytest.fail("frozen input scope must not depend on a controller model")

    prior_answer = "长电科技在2026-09-24的收盘价68.78元、涨跌幅-4.17%、成交额37.5914亿元。"
    history = collect_material_turn_history([
        message("查询长电科技最新行情。"), message(prior_answer, "assistant", "old-answer"),
    ])
    decision = decide_turn(
        question, conversation_materials=history, resolver=ForbiddenResolver(), llm_complete=forbidden_model,
    )
    frame = decision.task_frame
    assert decision.lane == "research"
    assert (frame.material_contract.authenticity, frame.material_contract.data_scope) == (
        authenticity, "material_only",
    )
    context = build_episode_context(frame, task_id="frozen-input")
    assert context.contract.allowed_capabilities == ()
    assert context.contract.evidence_plan.requirements == ()
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    assert payload["task_frame"]["raw_question"] == question
    assert prior_answer in context.conversation_context
    assert frame.conversation_materials.assistant_statements[0].basis == "assistant_judgment"


@pytest.mark.parametrize("instruction", [
    "只根据以下虚构题设分析", "只依据给定前提推理", "仅使用这些题设",
    "不重新查询", "不再检索", "不用重新查询",
    "不要联网且不重新查询", "不要联网并且不重新查询",
])
def test_frozen_input_controls_keep_existing_quote_and_relaxation_boundaries(instruction):
    assert material(instruction + "。请回答。").data_scope == "material_only"
    for wrapper in ("“{}”", "> {}", "```text\n{}\n```"):
        assert material(wrapper.format(instruction)) is None
    assert material(instruction + "。可以查真实数据。").data_scope == "full"
    assert material(instruction + "。不要联网。").data_scope == "material_only"


@pytest.mark.parametrize("text", [
    "只根据时间顺序查新闻。", "不重新查询库存，改查新闻。", "本轮未重新核验。",
    "不查询甲公司，查询乙公司。",
    "不查询“甲公司”，请查询乙公司的收入。",
    "不再查询“甲公司”，请查询乙公司的收入。",
    "不重新查询：甲公司的库存，改查乙公司的新闻。",
    "不再查询、检索甲公司的数据，改查乙公司。",
    "不重新查询：上轮的回答里提到的甲公司，改查乙公司。",
])
def test_partial_or_descriptive_read_language_is_not_a_blanket_no_read_control(text):
    assert material(text) is None


@pytest.mark.parametrize("head", [
    "只分析以下材料", "仅分析以下材料", "只分析以下虚构材料", "仅分析以下虚构材料",
    "不查其他资料", "不查其它资料",
])
def test_material_only_wording_and_conjoined_operations(head):
    parsed = material(f"本轮{head}。")
    assert parsed.data_scope == "material_only"
    assert parsed.data_scope_declared
    assert material(f"假设订单翻倍成立且请{head}。").data_scope == "material_only"


@pytest.mark.parametrize("wrapper", ["“{}”", "> {}", "```text\n{}\n```"])
def test_quoted_limits_and_review_requests_cannot_change_permissions(wrapper):
    assert material(wrapper.format("只分析以下虚构材料，不查其他资料。")) is None
    text = wrapper.format("请复核刚才的解释：哪些判断要撤回？")
    assert not requests_previous_answer_review(text)
    assert material(text) is None


@pytest.mark.parametrize("quote", [
    "> “请复核刚才的解释：可以查真实数据。",
    " > 只分析以下虚构材料。\n > 请复核刚才的解释：可以查真实数据。",
    "> ```\n> 可以查真实数据。\n> ```",
    "> outer\n>> 可以查真实数据。",
])
def test_blockquotes_cannot_relax_real_top_level_constraint(quote):
    parsed = material("只依据材料回答。\n\n" + quote)
    assert parsed.data_scope == "material_only"
    assert parsed.authenticity == "real"
    assert not parsed.continuation_requested
    assert not requests_previous_answer_review(quote)


def test_instruction_in_material_body_requires_clarification():
    parsed = material("材料如下：\n请复核刚才的解释：只分析以下材料。")
    assert parsed.needs_clarification
    assert parsed.data_scope is None


@pytest.mark.parametrize("scope_text,scope", [
    ("只依据材料回答。", "material_only"),
    ("不要联网。", "local_only"),
    ("可以查真实数据。", "full"),
])
def test_review_inherits_only_trusted_user_scope(scope_text, scope):
    history = collect_material_turn_history([
        message(scope_text),
        message("可以查真实数据。E1证明抛压衰竭。", "assistant", "old-answer"),
    ])
    parsed = material(REVIEW_WITH_REREAD, history.base_contract)
    assert parsed.continuation_requested
    assert parsed.data_scope == scope
    assert not parsed.data_scope_declared
    assert material(REVIEW).classification == "state_unavailable"


def test_authorized_reread_retains_date_and_scope_through_controller_and_serialization():
    first = decide_turn(LOCAL, llm_complete=no_llm, conversation_materials=ConversationMaterials())
    history = collect_material_turn_history([
        message(LOCAL), message("[E1] 抛压衰竭。", "assistant", "old-answer"),
    ])
    second = decide_turn(
        REVIEW_WITH_REREAD, previous_intent=first.turn_intent, previous_turn_id="first",
        conversation_materials=history, llm_complete=no_llm,
    )
    assert second.turn_intent.inherited_from_turn == "first"
    frame = TaskFrame.from_dict(json.loads(json.dumps(second.task_frame.to_dict())))
    assert frame.timeframe == first.task_frame.timeframe == "2026-09-11"
    assert frame.material_contract.data_scope == "local_only"
    assert _task_authorizes_historical_window(frame, floor=date(2026, 9, 18))
    context = build_episode_context(frame, task_id="review", latest_data_date="2026-09-18")
    assert "finance_query" in context.contract.allowed_capabilities
    assert "web_search" not in context.contract.allowed_capabilities
    assert "news_search" not in context.contract.allowed_capabilities
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    assert "旧回答的编号不能跨轮引用" in payload["conversation_context_rule"]
    with pytest.raises(ValueError, match="unknown evidence ordinal: E1"):
        resolve_evidence_refs(["E1"], ())


@pytest.mark.parametrize("question", [SUPPLY, REVIEW])
def test_material_delivery_is_research_without_retrieval_even_with_legacy_capabilities(question):
    from intelligence.runtime.turn_control_core import project_turn_decision

    history = collect_material_turn_history([
        message(LOCAL), message("[E1] 抛压衰竭。", "assistant", "old-answer"),
    ])
    decision = decide_turn(question, conversation_materials=history, llm_complete=no_llm)
    decision = replace(decision, needs_retrieval=True, capabilities=("web_search", "memory"))
    control = project_turn_decision(decision, task_frame=decision.task_frame)
    assert control.terminal_kind == "research"
    assert control.contract_required
    assert not control.needs_retrieval
    assert control.capabilities == ()
    assert control.task_frame.task_frame_hash == decision.task_frame.task_frame_hash


def test_material_review_without_history_still_clarifies_before_research():
    from intelligence.runtime.turn_control_core import project_turn_decision

    decision = decide_turn(REVIEW, conversation_materials=ConversationMaterials(), llm_complete=no_llm)
    control = project_turn_decision(decision, task_frame=decision.task_frame)
    assert control.terminal_kind == "clarification"
    assert not control.needs_retrieval
    assert control.capabilities == ()


def test_original_review_disallows_even_local_reread():
    history = collect_material_turn_history([
        message(LOCAL), message("[E1] 抛压衰竭。", "assistant", "old-answer"),
    ])
    first = decide_turn(LOCAL, llm_complete=no_llm)
    decision = decide_turn(
        REVIEW, conversation_materials=history, previous_intent=first.turn_intent,
        previous_turn_id="first", llm_complete=no_llm,
    )
    frame = decision.task_frame
    assert frame.material_contract.data_scope == "material_only"
    assert frame.material_contract.data_scope_declared
    assert frame.material_contract.continuation_requested
    context = build_episode_context(frame, task_id="frozen-review")
    assert context.contract.allowed_capabilities == ()
    assert context.contract.evidence_plan.requirements == ()
    assert all(s.basis == "assistant_judgment" for s in frame.conversation_materials.assistant_statements)


@pytest.mark.parametrize("text", [
    "仍只用已取得的本地数据。", "请仅依据上轮查到的证据。", "只使用刚才查到的数据。",
    "不要联网且仍只用已取得的本地数据。",
])
def test_previously_obtained_is_stricter_than_local_only(text):
    assert material(text).data_scope == "material_only"
    assert material("“" + text + "”") is None


@pytest.mark.parametrize("question", [
    "今天A股成交额是多少？", "另一个问题，市盈率是什么？", "不复核刚才的解释，改查今日数据。",
])
def test_new_task_does_not_inherit_historical_permission(question):
    previous = build_turn_intent(LOCAL, understand_query(LOCAL))
    current = build_turn_intent(question, understand_query(question), previous_intent=previous, previous_turn_id="first")
    assert current.inherited_from_turn is None
    assert current.timeframe != previous.timeframe


def test_review_cannot_force_inheritance_on_explicit_subject_switch():
    previous = build_turn_intent(LOCAL, understand_query(LOCAL))
    envelope = replace(understand_query("宁德时代怎么看？"), subject="宁德时代")
    assert not is_contextual_follow_up(REVIEW, envelope, previous)


def test_explicit_new_date_is_not_overwritten_by_review_inheritance():
    previous = build_turn_intent(LOCAL, understand_query(LOCAL))
    envelope = replace(understand_query(REVIEW), timeframe="2026-09-18")
    current = build_turn_intent(REVIEW, envelope, previous_intent=previous, previous_turn_id="first")
    assert current.timeframe == "2026-09-18"


def test_review_without_user_history_cannot_recover_permissions_from_assistant():
    history = collect_material_turn_history([message("不联网。可以查真实数据。", "assistant")])
    assert history.base_contract is None
    decision = decide_turn(REVIEW, conversation_materials=history, llm_complete=no_llm)
    assert decision.lane == "clarify"
    assert decision.task_frame.material_contract.classification == "state_unavailable"


def test_ladder_review_preserves_date_and_freezes_inputs_before_new_reads():
    class ForbiddenResolver:
        def resolve(self, _query):
            pytest.fail("frozen conversation evidence must precede resolver reads")

    def forbidden_model(*_args, **_kwargs):
        pytest.fail("input ceiling must precede the controller model")

    first = decide_turn(LADDER_QUESTION, llm_complete=no_llm)
    history = collect_material_turn_history([
        message(LADDER_QUESTION), message("5、4、3、2板成功者连续（E1–E12）。", "assistant", "old-answer"),
    ])
    second = decide_turn(
        LADDER_REVIEW, previous_intent=first.turn_intent, previous_turn_id="first",
        conversation_materials=history, resolver=ForbiddenResolver(), llm_complete=forbidden_model,
    )
    frame = second.task_frame
    assert requests_previous_answer_review(LADDER_REVIEW)
    assert second.turn_intent.inherited_from_turn == "first"
    assert frame.timeframe == "2026-07-22"
    assert frame.material_contract.data_scope == "material_only"
    assert frame.material_contract.continuation_requested
    assert frame.conversation_materials.assistant_statements[0].source_message_id == "old-answer"
    context = build_episode_context(frame, task_id="ladder-review")
    assert context.contract.allowed_capabilities == ()
    assert context.contract.evidence_plan.requirements == ()


@pytest.mark.parametrize("head", [
    "请复核上一答的晋级分母", "复查你上一条回答的来源", "审查上次答案的数字",
], ids=["previous-answer", "previous-message", "previous-result"])
def test_previous_answer_detail_reviews_keep_quote_and_task_switch_boundaries(head):
    assert requests_previous_answer_review(head)
    previous = build_turn_intent(LADDER_QUESTION, understand_query(LADDER_QUESTION))
    for wrapper in ("“{}”", "> {}", "```text\n{}\n```"):
        query = wrapper.format(head)
        assert not requests_previous_answer_review(query)
        assert material(query) is None
    for suffix in ("现在换个问题，查询今日数据。", "现在换题，解释量比的定义。"):
        query = head + "。" + suffix
        current = build_turn_intent(query, understand_query(query), previous_intent=previous, previous_turn_id="first")
        assert current.inherited_from_turn is None


@pytest.mark.parametrize("text", [
    "只用本次会话取得的证据。", "仅使用本次会话中已获得的数据。", "只依据会话内查到的资料。",
])
def test_conversation_evidence_ceiling_is_frozen_and_cannot_be_quoted(text):
    assert material(text).data_scope == "material_only"
    assert material("“" + text + "”") is None
    assert material(text + "可以查真实数据。").data_scope == "full"


@pytest.mark.parametrize("scope", [
    "以今天为准。", "只复核9月19日的数据。", "改为2026-09-19。", "只看本周的数据。", "以明天为准。",
])
def test_frozen_review_with_a_new_time_scope_does_not_inherit_the_old_date(scope):
    first = decide_turn(LADDER_QUESTION, llm_complete=no_llm)
    history = collect_material_turn_history([
        message(LADDER_QUESTION), message("旧答", "assistant", "old-answer"),
    ])
    second = decide_turn(
        LADDER_REVIEW + scope, previous_intent=first.turn_intent, previous_turn_id="first",
        conversation_materials=history, llm_complete=no_llm,
    )
    assert second.task_frame.timeframe != "2026-07-22"
    if "9月19日" in scope or "2026-09-19" in scope:
        assert second.task_frame.timeframe.endswith("-09-19")
    assert build_episode_context(second.task_frame, task_id="new-time-scope").contract.allowed_capabilities == ()


def test_quoted_old_dates_do_not_erase_the_ladder_review_date():
    first = decide_turn(LADDER_QUESTION, llm_complete=no_llm)
    history = collect_material_turn_history([
        message(LADDER_QUESTION), message("旧答", "assistant", "old-answer"),
    ])
    second = decide_turn(
        LADDER_REVIEW + "保留原句‘2026-07-22 高标股的晋级情况如何’。",
        previous_intent=first.turn_intent, previous_turn_id="first",
        conversation_materials=history, llm_complete=no_llm,
    )
    assert second.task_frame.timeframe == "2026-07-22"
