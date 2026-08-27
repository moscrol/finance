"""fact slot 三处登记一致性：新 slot 漏登记会让契约装配 fail closed 炸整题。

2026-08-25 生产回归现场：P1-b 给 compile_research_program 加了
substitute_observation FactSlot，而 episode_factory._required_output_ids
会把 program.required_fact_slots 并进契约 output_ids——该 id 没进
_OUTPUT_DESCRIPTIONS，build_episode_context 直接 ValueError，命中三词族的
题（SPT 周一题/有色题）整题炸掉。全量测试没抓到，因为没有用例同时走
「三词族题 → build_episode_context」。本文件把「三处登记」变成机器可判。
"""

from __future__ import annotations

from intelligence.services.episode_factory import (
    _ADVISORY_OUTPUT_IDS,
    _OUTPUT_DESCRIPTIONS,
    _required_output_evidence_types,
    build_episode_context,
)
from intelligence.services.research_contract import _SLOT_BY_OPERATOR
from intelligence.services.turn_controller import decide_turn

Q_MONDAY = "站在spt视角下，你认为周一科技和医药板块的走势会怎么样，需要观察哪些个股的反馈"
Q_YSJS = "用spt的视角，分析下有色金属板块后续的走势，以及板块内有机会的个股有哪些"

FULL_CAPS = ("market_data", "finance_query", "kb_search", "news_search")


def test_every_program_fact_slot_is_registered_in_contract_layer() -> None:
    """结构不变量：research program 的每个 fact slot 必须三处登记齐。

    变异：从 _OUTPUT_DESCRIPTIONS / _ADVISORY_OUTPUT_IDS 删任一 fact slot
    条目，或新增 FactSlot 不登记 → 本测试红。
    """

    for slot in _SLOT_BY_OPERATOR.values():
        slot_id = slot.slot_id
        assert slot_id in _OUTPUT_DESCRIPTIONS, f"{slot_id} 缺契约描述（装配会炸）"
        assert slot_id in _ADVISORY_OUTPUT_IDS, (
            f"{slot_id} 不在 advisory 集合（可选取数收据会被当必选格判失败）"
        )
        evidence_types = _required_output_evidence_types(slot_id, FULL_CAPS)
        assert set(evidence_types) <= {"market_data", "finance_query"}, (
            f"{slot_id} 的 evidence_types 回退成了全量能力列表"
            "（模型读不出哪个工具填这格）"
        )


def test_theme_stock_observation_questions_build_contract() -> None:
    """回归锁：三词族题必须能建契约（2026-08-25 生产炸点原样复现）。"""

    for index, query in enumerate((Q_MONDAY, Q_YSJS)):
        decision = decide_turn(query)
        context = build_episode_context(
            decision.task_frame,
            task_id=f"substitute-slot-regression-{index}",
            today="2026-08-25",
            latest_data_date="2026-08-24",
        )
        output_ids = tuple(
            item.output_id for item in context.contract.required_outputs
        )
        assert "substitute_observation" in output_ids
        for item in context.contract.required_outputs:
            if item.output_id == "substitute_observation":
                assert set(item.evidence_types) <= {
                    "market_data",
                    "finance_query",
                }
