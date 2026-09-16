"""D1 A1: 题组终点及原编号，不以末尾指令或第一题编号偷换题目集合。"""
from intelligence.services.user_task import classify_top_level_regions


def test_message_instruction_after_group_does_not_drop_last_question():
    regions = classify_top_level_regions(
        "1. 甲订单占比多少？\n\n2. 乙是否有正式订单？\n\n只依据上述材料回答。"
    )
    assert regions.sub_questions == ("甲订单占比多少？", "乙是否有正式订单？")
    assert [(s.kind, s.scope) for s in regions.instructions] == [("constraint_b", "message")]


def test_original_question_numbers_need_not_start_at_one():
    regions = classify_top_level_regions(
        "继续上一轮。\n\n7. 假设订单翻倍，占比是多少？\n\n8. 哪些风险未确认？"
    )
    assert regions.sub_questions == ("假设订单翻倍，占比是多少？", "哪些风险未确认？")
    assert [(s.kind, s.scope) for s in regions.instructions] == [
        ("continuation", "message"), ("premise_declaration", "q7"),
    ]
    assert regions.question_ids == ("q7", "q8")
