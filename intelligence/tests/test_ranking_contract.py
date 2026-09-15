"""排序与情景表达契约（10 号单）：意图门、契约文本、解析、机械再排序、缺件核对、登记。

反向验证（合同第 5 条）：改一个关键成本/订单/需求条件，排序应在合理场景改变；
只换文案和公司行序不能改变推导。
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from intelligence.services import ranking_contract as rc
from intelligence.services.episode_protocol import (
    EpisodeFinishRejection,
    RejectionKind,
    build_episode_input,
    build_episode_instructions,
    validate_episode_finish,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.track_contract import is_contract_rewrite_only
from intelligence.tests.test_episode_protocol import _context, _frame, _registry
from intelligence.tests.test_track_slot_repair_binding import (
    _binding,
    _context as _track_context,
    _evidence,
    _finish,
)

FROZEN = (
    "液冷板块里英维克、申菱环境、高澜股份、同飞股份谁更值得优先研究？排个序，并说明什么变化会改排序",
    "高速覆铜板涨价，生益科技、南亚新材、华正新材谁的利润传导最强？排序并给出兑现节奏",
    "英维克、申菱环境、高澜股份这三家液冷公司，谁的客户集中风险最大？这怎么影响研究优先级",
    "PCB里世运电路、兴森科技、东山精密、光华科技，哪家已经被市场定价、哪家还没兑现？按预期差排序",
    "这轮液冷和2023年光模块行情在机制上有哪些相似和不同？对英维克、申菱环境、高澜股份的排序有什么影响",
    "如果铜价回落20%且高速CCL涨价落空，生益科技、南亚新材、华正新材的排序会怎么变？观察点怎么改",
)

ANSWER = """英维克优先，因其液冷收入占比最高且客户已放量；最大不确定变量是 CDU 交付节奏。

## 公司矩阵
| 公司 | 优先级 | 需求暴露 | 收入/利润传导 | 兑现时间 | 已定价程度 | 关键分歧 |
|---|---|---|---|---|---|---|
| 英维克（002837） | 1 | 液冷收入占比 30%（E1） | 毛利率 +2pct（E2） | 2026Q3（E1） | 较高（E4） | 客户集中 |
| 申菱环境 | 2 | 缺数：液冷收入拆分 | 缺数：单季毛利率 | 2026Q4（E3） | 中等（E4） | 订单真实性 |
| 高澜股份 | 3 | 送样阶段（E5） | 缺数：需要订单金额 | 未知 | 低（E4） | 是否进入供应链 |

## 财务传导
- 英维克：需求↑ → 收入 +（E1） → 2026Q3 → 预期差小。

## 竞争解释
1. 解释 A：排序由液冷收入兑现度决定。区分变量：英维克 2026Q3 液冷收入；若 ≥ 30% 则本解释成立。
2. 解释 B：排序由客户资本开支节奏决定。区分变量：CSP 资本开支指引；若上调则本解释成立。

## 改判条件表
| 变量 | 变化 | 受影响公司 | 方向 | 观察指标×时间窗 |
|---|---|---|---|---|
| 铜价 | 回落 20% | 申菱环境、英维克 | 申菱环境↑ 英维克↓ | 铜价周度均价，30 天内 |
| 高澜股份订单 | 获得公告级订单 | 高澜股份 | ↑↑ | 公告，2026-10-31 前 |

## 下一步
- 补关键缺口：申菱环境液冷收入拆分。
- 检验条件：2026Q3 英维克液冷收入占比。
（非投资建议）
"""


# —— 意图门 ——
@pytest.mark.parametrize("question", FROZEN)
def test_frozen_questions_route_to_ranking_contract(question: str) -> None:
    assert rc.parse_ranking_intent(question)


@pytest.mark.parametrize(
    "question",
    (
        "涨幅排行前10",
        "今天液冷板块怎么样",
        "液冷和风冷的优势分别是什么",
        "需求和成本哪个更重要",
        "今天哪个板块最强",
        "英维克和申菱环境哪个市值最大",
        "光伏自上次之后有什么新变化",
        "比较瑞华泰和中际旭创",
        "",
    ),
)
def test_non_ranking_questions_do_not_route(question: str) -> None:
    assert not rc.parse_ranking_intent(question)


def test_two_companies_need_a_strong_cue_and_self_contained_asks_route() -> None:
    assert rc.parse_ranking_intent("英维克和申菱环境哪个更值得研究")
    assert not rc.parse_ranking_intent("英维克和申菱环境哪个更大")
    assert rc.parse_ranking_intent("液冷涨价谁最受益")


def test_scenario_update_intent_only_on_rerank_followups() -> None:
    assert rc.parse_scenario_update_intent(FROZEN[5])
    assert rc.parse_scenario_update_intent("上面这几家再排序一下")
    assert not rc.parse_scenario_update_intent(FROZEN[0])
    assert not rc.parse_scenario_update_intent("如果铜价回落对英维克利润有什么影响")
    # 追问不点名公司也算排序题：对象在上一轮
    assert rc.parse_ranking_intent("如果铜价回落20%，排序会怎么变")


PRIOR_CONTEXT = (
    "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n"
    "## 最近消息原文\n"
    "user: 液冷板块里英维克、申菱环境、高澜股份谁更值得优先研究？排个序\n"
    "assistant: 旧版本排序：高澜股份第一。\n"
    "| 公司 | 优先级 | 需求暴露 | 收入/利润传导 | 兑现时间 | 已定价程度 | 关键分歧 |\n"
    "|---|---|---|---|---|---|---|\n"
    "| 高澜股份 | 1 | a | b | c | d | e |\n"
    "| 英维克 | 2 | a | b | c | d | e |\n"
    "user: 再仔细看一遍\n"
    f"assistant: {ANSWER}\n"
)


def test_latest_prior_artifact_picks_the_most_recent_complete_matrix() -> None:
    prior = rc.latest_prior_artifact(PRIOR_CONTEXT)
    assert prior is not None
    assert prior.order == ("英维克", "申菱环境", "高澜股份")
    assert rc.latest_prior_artifact("") is None
    assert rc.latest_prior_artifact("user: 今天怎么样\nassistant: 还行。") is None


def test_episode_rule_embeds_mechanical_rerank_baseline_for_followups() -> None:
    followup = "如果铜价回落20%，英维克、申菱环境、高澜股份的排序会怎么变？观察点怎么改"
    rule = rc.episode_ranking_rule(followup, "theme_analysis", conversation_context=PRIOR_CONTEXT)
    assert "【再排序基线】" in rule
    assert "上一轮排序：英维克 > 申菱环境 > 高澜股份" in rule
    assert "机械再排序结果：申菱环境 > 英维克 > 高澜股份" in rule
    assert "观察点更新：铜价周度均价，30 天内" in rule
    uncovered = rc.episode_ranking_rule(
        "如果树脂价格暴涨，排序会怎么变", "theme_analysis", conversation_context=PRIOR_CONTEXT
    )
    assert "没有覆盖该变量" in uncovered and "机械再排序结果" not in uncovered
    # 没有上一轮矩阵：只有契约，没有基线段；首问也没有基线段
    assert "【再排序基线】" not in rc.episode_ranking_rule(followup, "theme_analysis")
    assert "【再排序基线】" not in rc.episode_ranking_rule(FROZEN[0], "theme_analysis", conversation_context=PRIOR_CONTEXT)


def test_receipt_checks_model_rerank_table_against_mechanical_result() -> None:
    followup = "如果铜价回落20%，英维克、申菱环境、高澜股份的排序会怎么变？"
    consistent = ANSWER + (
        "\n## 新旧排序对照\n| 公司 | 原优先级 | 新优先级 | 变动原因 |\n|---|---|---|---|\n"
        "| 申菱环境 | 2 | 1 | 铜价回落改善成本（E3） |\n| 英维克 | 1 | 2 | 相对失去成本优势 |\n| 高澜股份 | 3 | 3 | 无变化 |\n"
    )
    receipt = rc.ranking_receipt(consistent, query=followup, conversation_context=PRIOR_CONTEXT)
    assert receipt["scenario_update_intent"] is True
    assert receipt["prior_rerank"]["after"] == ["申菱环境", "英维克", "高澜股份"]
    assert receipt["rerank_consistent"] is True
    assert "ranking_rerank_table" not in receipt["missing_outputs"]
    inconsistent = consistent.replace("| 申菱环境 | 2 | 1 |", "| 申菱环境 | 2 | 3 |").replace(
        "| 高澜股份 | 3 | 3 |", "| 高澜股份 | 3 | 1 |"
    )
    assert rc.ranking_receipt(inconsistent, query=followup, conversation_context=PRIOR_CONTEXT)["rerank_consistent"] is False
    no_table = rc.ranking_receipt(ANSWER, query=followup, conversation_context=PRIOR_CONTEXT)
    assert no_table["rerank_consistent"] is None and "ranking_rerank_table" in no_table["missing_outputs"]
    first_ask = rc.ranking_receipt(ANSWER, query=FROZEN[0], conversation_context=PRIOR_CONTEXT)
    assert first_ask["prior_rerank"] is None and first_ask["rerank_consistent"] is None


# —— 契约文本 ——
def test_guidance_carries_fixed_headers_and_discipline() -> None:
    legacy = rc.build_ranking_guidance()
    episode = rc.build_ranking_guidance_for_episode()
    for text in (legacy, episode):
        assert "| " + " | ".join(rc.MATRIX_HEADERS) + " |" in text
        assert "| " + " | ".join(rc.FLIP_HEADERS) + " |" in text
        assert "| " + " | ".join(rc.RERANK_HEADERS) + " |" in text
        assert "竞争解释" in text and "区分变量" in text
        for label in rc.NEXT_ACTION_LABELS:
            assert label in text
        assert "禁止编造具体弹性、权重、胜率、概率" in text
        assert "排序不变，需补该变量的敏感性" in text
    assert "[D6]" in legacy and "[M]" in legacy
    assert "E1、E2" in episode
    for legacy_marker in ("[M]", "[V]", "[D6]", "[W7]"):
        assert legacy_marker not in episode


def test_for_query_returns_empty_when_not_routed() -> None:
    assert rc.ranking_guidance_for_query("深信服毛利率多少", "valuation") == ""
    assert rc.episode_ranking_rule("今天液冷板块怎么样", "theme_analysis") == ""
    assert "排序与情景表达契约" in rc.ranking_guidance_for_query(FROZEN[0], "theme_analysis")
    assert "排序与情景表达契约" in rc.episode_ranking_rule(FROZEN[0], "theme_analysis")


# —— 解析 ——
def test_parse_artifact_reads_matrix_flips_explanations_and_next_actions() -> None:
    artifact = rc.parse_ranking_artifact(ANSWER)
    assert artifact.order == ("英维克", "申菱环境", "高澜股份")
    assert artifact.priority_complete
    first = artifact.matrix[0]
    assert first.code == "002837" and first.gap_count == 0
    assert set(first.evidence_ids) == {"E1", "E2", "E4"}
    assert artifact.matrix[1].gap_count == 2
    assert [item.variable for item in artifact.flip_conditions] == ["铜价", "高澜股份订单"]
    assert artifact.flip_conditions[0].moves == {"申菱环境": 1, "英维克": -1}
    assert artifact.flip_conditions[1].moves == {"高澜股份": 2}
    assert [item.distinguishing_variable for item in artifact.explanations] == [
        "英维克 2026Q3 液冷收入",
        "CSP 资本开支指引",
    ]
    assert len(artifact.next_actions) == 2
    assert artifact.next_actions[0].startswith("补关键缺口：")
    assert artifact.main_judgment.startswith("英维克优先")
    payload = artifact.to_payload()
    json.dumps(payload, ensure_ascii=False)
    assert payload["numeric_probabilities_allowed"] is False


def test_missing_elements_on_prose_only_answer() -> None:
    prose = "英维克最好，申菱环境其次，高澜股份最后。（非投资建议）"
    assert rc.missing_contract_elements(prose) == (
        "matrix",
        "flip_conditions",
        "competing_explanations",
        "next_actions",
    )
    assert rc.missing_contract_elements(prose, scenario_update=True)[-1] == "rerank_table"
    assert rc.missing_contract_elements(ANSWER) == ()


def test_matrix_without_priority_or_single_row_counts_as_missing() -> None:
    no_priority = ANSWER.replace("| 1 |", "|  |")
    assert "matrix" in rc.missing_contract_elements(no_priority)
    duplicate_priority = ANSWER.replace("| 申菱环境 | 2 |", "| 申菱环境 | 1 |")
    assert "matrix" in rc.missing_contract_elements(duplicate_priority)


def test_contract_missing_outputs_only_for_ranking_questions() -> None:
    prose = "英维克最好。"
    assert rc.contract_missing_outputs(prose, query="今天液冷板块怎么样") == ()
    ids = rc.contract_missing_outputs(prose, query=FROZEN[0])
    assert ids == (
        "ranking_matrix",
        "ranking_flip_conditions",
        "ranking_competing_explanations",
        "ranking_next_actions",
    )
    assert "ranking_rerank_table" in rc.contract_missing_outputs(prose, query=FROZEN[5])
    merged = rc.merge_ranking_missing_outputs(
        ("direct_assessment", "ranking_matrix"), prose, query=FROZEN[0]
    )
    assert merged == ("direct_assessment", *ids)
    assert rc.merge_ranking_missing_outputs(("direct_assessment",), prose, query="今天液冷板块怎么样") == (
        "direct_assessment",
    )


def test_expression_slots_count_as_contract_rewrite_only() -> None:
    assert is_contract_rewrite_only(("ranking_matrix", "ranking_flip_conditions"))
    assert is_contract_rewrite_only(("track_ttl", "ranking_next_actions"))
    assert not is_contract_rewrite_only(("ranking_matrix", "direct_assessment"))
    assert not is_contract_rewrite_only(("ranking_matrix",), rejected_claims=("c1",))


# —— 机械再排序（反向验证） ——
def test_cost_condition_changes_the_order_and_updates_watchpoints() -> None:
    artifact = rc.parse_ranking_artifact(ANSWER)
    update = rc.apply_scenario(artifact, scenario_text=FROZEN[5])
    assert update.before == ("英维克", "申菱环境", "高澜股份")
    assert update.after == ("申菱环境", "英维克", "高澜股份")
    assert update.moved == {"英维克": (1, 2), "申菱环境": (2, 1)}
    assert not update.unchanged
    assert update.watchpoints == ("铜价周度均价，30 天内",)
    json.dumps(update.to_payload(), ensure_ascii=False)


def test_opposite_direction_does_not_fire_the_condition() -> None:
    artifact = rc.parse_ranking_artifact(ANSWER)
    update = rc.apply_scenario(artifact, scenario_text="如果铜价上涨 10%，排序会怎么变")
    assert update.unchanged and update.after == update.before
    assert "反向变化" in update.reason


def test_uncovered_variable_keeps_order_and_asks_for_sensitivity() -> None:
    artifact = rc.parse_ranking_artifact(ANSWER)
    update = rc.apply_scenario(artifact, scenario_text="如果树脂价格暴涨")
    assert update.unchanged
    assert "需补充该变量的敏感性" in update.reason


def test_company_specific_order_condition_lifts_two_positions() -> None:
    artifact = rc.parse_ranking_artifact(ANSWER)
    update = rc.apply_scenario(artifact, scenario_text="高澜股份拿到公告级订单后怎么排")
    assert update.after == ("高澜股份", "英维克", "申菱环境")
    assert update.moved["高澜股份"] == (3, 1)


def test_row_shuffle_and_wording_changes_do_not_change_the_derivation() -> None:
    lines = ANSWER.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith("| 英维克"))
    third = next(i for i, line in enumerate(lines) if line.startswith("| 高澜股份 | 3"))
    lines[first], lines[third] = lines[third], lines[first]
    shuffled = "\n".join(lines).replace("客户集中", "客户集中度偏高").replace("送样阶段", "仍在送样")
    original = rc.parse_ranking_artifact(ANSWER)
    variant = rc.parse_ranking_artifact(shuffled)
    assert variant.order == original.order
    assert rc.apply_scenario(variant, scenario_text="铜价回落").after == rc.apply_scenario(
        original, scenario_text="铜价回落"
    ).after


def test_apply_scenario_refuses_without_complete_priorities() -> None:
    artifact = rc.parse_ranking_artifact(ANSWER.replace("| 申菱环境 | 2 |", "| 申菱环境 |  |"))
    update = rc.apply_scenario(artifact, scenario_text="铜价回落")
    assert update.unchanged and "缺优先级列" in update.reason


# —— 收据 ——
def test_receipt_shape_and_non_ranking_shortcut() -> None:
    receipt = rc.ranking_receipt(ANSWER, query=FROZEN[0], question_type="theme_analysis", as_of="2026-09-09")
    assert receipt["check"] == "ranking_contract"
    assert receipt["ranking_intent"] is True and receipt["scenario_update_intent"] is False
    assert receipt["missing_outputs"] == [] and receipt["matrix_rows"] == 3 and receipt["flip_rows"] == 2
    assert receipt["artifact"]["order"] == ["英维克", "申菱环境", "高澜股份"]
    json.dumps(receipt, ensure_ascii=False)
    plain = rc.ranking_receipt("今天液冷放量。", query="今天液冷板块怎么样", question_type="theme_analysis")
    assert plain["ranking_intent"] is False and plain["artifact"] is None
    assert plain["missing_outputs"] == []


# —— 改判条件 → checkpoints ——
def test_ingest_flip_conditions_registers_once_and_renders_for_prompt(tmp_path) -> None:
    path = tmp_path / "checkpoints.jsonl"
    written = rc.ingest_flip_conditions(
        path, ANSWER, query=FROZEN[0], as_of="2026-09-09", theme="液冷", session_id="s1"
    )
    assert len(written) == 2
    assert written[0]["source"] == rc.FLIP_SOURCE and written[0]["category"] == rc.FLIP_CATEGORY
    assert written[0]["stocks"] == ["申菱环境", "英维克"] and written[0]["due"] == "2026-10-09"
    assert written[1]["due"] == "2026-10-31" and written[1]["themes"] == ["液冷"]
    assert "改判条件｜若铜价回落 20%" in written[0]["claim"]
    # 重复登记空操作；非排序题空操作
    assert rc.ingest_flip_conditions(path, ANSWER, query=FROZEN[0], as_of="2026-09-09") == []
    assert rc.ingest_flip_conditions(path, ANSWER, query="今天液冷板块怎么样") == []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    open_rows = rc.open_flip_condition_records(rows, [])
    rendered = rc.render_flip_conditions_for_prompt(open_rows)
    assert rendered.count("- [due=") == 2 and "（申菱环境、英维克）" in rendered
    scored = [{"id": rows[0]["id"], "verdict": "hit"}]  # checkpoints.TERMINAL_VERDICTS 之一
    assert len(rc.open_flip_condition_records(rows, scored)) == 1


# —— episode 接缝 ——
def test_ranking_questions_get_episode_ranking_contract_in_rules_only() -> None:
    frame = dataclasses.replace(_frame(), raw_question=FROZEN[0], question_type="theme_analysis")
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    rules = payload["question_type_rules"]
    instructions = build_episode_instructions(frame, _context(frame), _registry())
    assert "排序与情景表达契约" in rules
    assert "| " + " | ".join(rc.MATRIX_HEADERS) + " |" in rules
    assert "排序与情景表达契约" not in instructions
    for legacy_marker in ("[M]", "[V]", "[D6]", "[W7]"):
        assert legacy_marker not in rules


def test_non_ranking_questions_keep_rules_unchanged() -> None:
    frame = _frame()
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    assert "排序与情景表达契约" not in payload["question_type_rules"]


@pytest.mark.parametrize("slot", sorted(rc.RANKING_CONTRACT_OUTPUT_ID_SET))
def test_binding_a_ranking_slot_is_a_recoverable_format_rejection(slot: str) -> None:
    with pytest.raises(EpisodeFinishRejection) as excinfo:
        validate_episode_finish(
            _finish([_binding("change_summary"), _binding(slot)]),
            context=_track_context(),
            evidence=_evidence(),
        )
    assert excinfo.value.code == "expression_slot_binding"
    assert excinfo.value.kind is RejectionKind.FORMAT
    message = str(excinfo.value)
    assert slot in message and "写进 draft" in message and "公司矩阵表" in message


def test_repair_goal_message_explains_ranking_slots_and_keeps_track_text() -> None:
    harness = FinanceResearchHarness()

    def goal(*elements: str) -> RepairGoal:
        return RepairGoal(
            episode_id="ranking-slot-repair",
            repair_goal_id="repair-ranking-slot-1",
            cycle=1,
            missing_answer_elements=tuple(elements),
            unsupported_claims=(),
            missing_evidence_modes=(),
            attempted_actions=("kb_search:液冷",),
            evidence_progress=CoverageDelta(1, 0, 1),
            remaining_calls=2,
            remaining_seconds=30.0,
        )

    with_ranking = json.loads(
        harness.repair_goal_message(goal("ranking_matrix", "ranking_flip_conditions", "direct_assessment"), tools_open=False)
    )
    note = with_ranking["expression_elements_note"]
    assert "ranking_matrix" in note and "公司矩阵表" in note and "direct_assessment" not in note
    assert "改判条件表" in note and "不要作为 bindings 的 output_id" in note
    track_only = json.loads(harness.repair_goal_message(goal("track_ttl", "change_summary"), tools_open=False))
    assert track_only["expression_elements_note"].endswith("四态对照或「无上期基线」声明）")
    assert "公司矩阵" not in track_only["expression_elements_note"]
    without = json.loads(harness.repair_goal_message(goal("direct_assessment"), tools_open=False))
    assert "expression_elements_note" not in without
