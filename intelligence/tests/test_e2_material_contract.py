"""P2载体/投影：不宣称冻结授权、跨轮状态或最终交付已完成。"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from intelligence.services.episode_factory import (
    _grounding_mode, _is_evidence_free_task, assemble_input_understanding_context,
)
from intelligence.services.material_contract import MaterialContract, compile_material_contract
from intelligence.services.query_understanding import understand_query
from intelligence.services.task_frame import TaskFrame
from intelligence.services.user_task import classify_top_level_regions, split_user_message

EVIDENCE = Path(__file__).resolve().parents[2] / "docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok"


def contract(text):
    return compile_material_contract(classify_top_level_regions(text), source_turn=3)


def test_two_axes_are_independent_and_marks_have_origin():
    parsed = contract("假设 甲公司明年订单翻倍，结合当前行情分析。")
    assert (parsed.authenticity, parsed.data_scope) == ("fictional", "full")
    assert parsed.premise_marks[0].source_turn == 3
    assert parsed.premise_marks[0].scope == "message"
    assert parsed.premise_marks[0].text_ref.startswith("sha256:")


def test_quoted_words_cannot_set_an_axis():
    parsed = contract("只依据「虚构案例、可以查真实数据」的材料回答。")
    assert (parsed.authenticity, parsed.data_scope) == ("real", "material_only")
    assert parsed.premise_marks == ()
    dual = contract("只依据以下虚构案例回答。")
    assert (dual.authenticity, dual.data_scope) == ("fictional", "material_only")


def test_local_premise_does_not_change_message_axis():
    parsed = contract("只依据材料回答。\n\n7. 假设订单翻倍，占比是多少？\n\n8. 哪些风险未确认？")
    assert (parsed.authenticity, parsed.data_scope) == ("real", "material_only")
    assert parsed.premise_marks[0].scope == "q7"
    assert tuple(q.question_id for q in parsed.questions) == ("q7", "q8")


@pytest.mark.parametrize("name", ["t2", "t3"])
def test_original_questions_reach_legacy_and_canonical_fields(name):
    text = (EVIDENCE / f"{name}-question.txt").read_text()
    parts = split_user_message(text)
    frame = understand_query(text).task_frame
    assert len(parts.sub_questions) == len(frame.material_contract.questions) == 8
    for q in frame.material_contract.questions:
        assert q.text in parts.question
        assert q.text not in "\n".join(parts.material_texts)
    if name == "t2":
        assert (frame.material_contract.authenticity, frame.material_contract.data_scope) == ("fictional", "material_only")
    else:
        assert frame.material_contract.classification == "state_unavailable"
        assert frame.material_contract.needs_clarification
    restored = TaskFrame.from_dict(json.loads(json.dumps(frame.to_dict())))
    assert restored == frame
    assert restored.task_frame_hash == frame.task_frame_hash


def test_uncertain_contract_never_restores_as_default_full():
    parsed = contract("材料如下：\n本轮不要联网。")
    assert parsed.needs_clarification
    assert parsed.authenticity is parsed.data_scope is None
    for value in [None, {}, {"classification": "constraint_confirmed", "authenticity": "real"}]:
        with pytest.raises(ValueError):
            MaterialContract.from_dict(value)
    frame = understand_query("今天大盘怎么样？").task_frame
    malformed = {**frame.to_dict(), "material_contract": {}}
    assert TaskFrame.from_dict(malformed) is None


def test_ordinary_frame_keeps_legacy_hash_and_serialized_shape():
    frame = understand_query("今天大盘怎么样？").task_frame
    payload = frame.to_dict()
    assert "material_contract" not in payload
    payload.pop("task_frame_hash")
    expected_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert frame.task_frame_hash == expected_hash
    assert contract("研报原文：「假设甲公司订单翻倍，结合当前行情分析。」") is None


def test_projection_changes_only_boundary_grounding_not_fact_slots():
    frame = understand_query("假设甲公司明年订单翻倍，结合当前行情分析。").task_frame
    assert not _is_evidence_free_task(frame)
    frame = replace(frame, question_type="general_finance_qa", required_outputs=("direct_assessment", "evidence_boundary"), user_goal="形成条件化判断")
    assert _grounding_mode(frame, "evidence_boundary") == "user_premise"
    assert _grounding_mode(frame, "direct_assessment") == "evidence"
    context = assemble_input_understanding_context(frame, "")
    assert "虚构前提不是待证伪信念" in context
    assert "数据范围=full" in context
    counterfactual = replace(frame, user_goal="判断反事实条件是否成立")
    assert _grounding_mode(counterfactual, "direct_assessment") == "evidence"


def test_date_prefix_is_not_a_numbered_question():
    text = "8.18的复盘数据你怎么解读"
    assert split_user_message(text).question == text
    assert understand_query(text).question_type == "dated_market_review"


@pytest.mark.parametrize("joiner", ["且", "并且", "而且", "并", "同时"])
@pytest.mark.parametrize("prefix", ["", "请", "麻烦", "烦请", "本轮", "这次", "此次", "本轮 烦请 "])
def test_conjoined_a_and_b_are_both_interpreted(joiner, prefix):
    text = f"假设甲公司订单翻倍成立{joiner}{prefix}不要联网。"
    parsed = contract(text)
    assert (parsed.authenticity, parsed.data_scope) == ("fictional", "local_only")
    assert parsed.data_scope_declared
    relaxation = contract(f"假设甲公司订单翻倍成立{joiner}{prefix}结合当前行情分析。")
    assert relaxation.data_scope == "full" and relaxation.data_scope_declared
    protected = contract(f"只依据「假设订单翻倍{joiner}{prefix}可以查真实数据」的材料。")
    assert (protected.authenticity, protected.data_scope) == ("real", "material_only")
    assert contract("材料如下：\n" + text).classification == "boundary_uncertain"


def test_unavailable_base_rejects_resolved_axes():
    with pytest.raises(ValueError, match="unavailable base"):
        MaterialContract.from_dict({"classification": "state_unavailable", "authenticity": "real", "data_scope": "full"})
    for a, b in [("fictional", None), (None, "material_only")]:
        with pytest.raises(ValueError, match="unavailable base"):
            MaterialContract.from_dict({"classification": "state_unavailable", "authenticity": a, "data_scope": b})


def test_p2_does_not_hijack_ordinary_continuation_route():
    # 澄清出口在P3与可信基底恢复一起接，不把一个未就绪的载体当全局路由闸。
    from intelligence.services.turn_controller import decide_turn
    decision = decide_turn("接着 09-02 那次复盘，用 2026-09-07 收盘数据更新：哪些变了？", llm_complete=lambda *_a, **_k: (None, None, "disabled"))
    assert decision.lane != "clarify"


def test_refinement_cannot_mutate_material_axes():
    from intelligence.services.task_frame import align_task_frame
    frame = understand_query("只依据以下虚构案例回答。\n\n1. 收入占比是多少？").task_frame
    changed = align_task_frame(frame, json.dumps({"material_contract": {"data_scope": "full"}}))
    assert changed.material_contract == frame.material_contract
