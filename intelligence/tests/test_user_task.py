from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from intelligence.services.task_frame import TaskFrame
from intelligence.services.user_task import ResolvedValue, UserTask


def _frame(*, subject: str | None = None) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场的主线是什么？",
        user_goal="判断当前市场主线",
        question_type="market_watch",
        subject=subject,
        subject_kind="theme" if subject else "unknown",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("用户未明确市场范围，按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_a_share_market",
        confidence=0.9,
    )


def test_user_task_preserves_raw_question_and_resolution_provenance() -> None:
    question = "  目前市场的主线是什么？  "
    task = UserTask(
        raw_question=question,
        conversation_context="  上一轮在讨论市场风格。  ",
        subjects=(),
        market_scope=ResolvedValue(" A股 ", "product_default"),
        time_window=None,
        assumptions=(" 按A股市场理解 ", "按A股市场理解"),
        ambiguities=(),
        user_premises=(),
        task_id=" task-1 ",
    )

    assert task.raw_question == question
    assert task.market_scope == ResolvedValue("A股", "product_default")
    assert task.assumptions == ("按A股市场理解",)
    assert task.to_dict()["task_id"] == "task-1"
    with pytest.raises(FrozenInstanceError):
        task.task_id = "changed"  # type: ignore[misc]


def test_from_task_frame_marks_a_share_default_without_inventing_subject() -> None:
    task = UserTask.from_task_frame(
        _frame(subject=None),
        {
            "conversation_context": "延续上一轮",
            "task_id": "turn-1",
            "time_window_source": "inferred",
        },
    )

    assert task.raw_question == "目前市场的主线是什么？"
    assert task.subjects == ()
    assert task.market_scope == ResolvedValue("A股", "product_default")
    assert task.time_window == {
        "value": "最近交易日",
        "source": "inferred",
    }


def test_task_frame_exposes_compatibility_projection() -> None:
    task = _frame(subject="液冷").to_user_task({"task_id": "compat-1"})

    assert isinstance(task, UserTask)
    assert task.task_id == "compat-1"
    assert task.subjects[0].value == "液冷"
    assert get_type_hints(TaskFrame.to_user_task)["return"] is UserTask


def test_user_task_rejects_unknown_resolution_source() -> None:
    with pytest.raises(ValueError, match="resolution source"):
        ResolvedValue("A股", "guessed")


def test_user_task_rejects_non_json_safe_time_window() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        UserTask(
            raw_question="市场怎么看",
            conversation_context="",
            subjects=(),
            market_scope=None,
            time_window={"anchor": object()},
            assumptions=(),
            ambiguities=(),
            user_premises=(),
            task_id="task-unsafe",
        )


# --- 输入理解层（2026-09-09，05 单）：材料 / 假设 / 方法 / 盘感 / 代称 -----------------

from intelligence.services.user_task import (  # noqa: E402
    METHOD_STATUS_UNVERIFIED,
    PRIOR_JUDGEMENT_PREMISE,
    extract_method_candidates,
    extract_user_premises,
    material_id_for,
    materials_in_conversation,
    references_material,
    resolve_nicknames,
    split_user_message,
    translate_market_feel,
)

REPORT = (
    "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n\n"
    "一、核心观点\n公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年，"
    "预计 2027 年一季度满产。管理层在电话会中表示下游两家电池厂已完成 A 样验证。\n\n"
    "二、关键数据\n2026 年上半年新签订单 12 亿元，同比增长 40%；毛利率 31.5%（去年同期 27.2%）。\n\n"
    "三、我们的判断\n我们认为硫化物路线将在 2027 年替代氧化物成为主流，公司 A 是最大受益者，目标价上调 30%。"
)
REPORT_QUESTION = "这篇研报的核心逻辑站得住吗？帮我分开哪些是硬事实、哪些只是推测"
TABLE = (
    "板块\t涨停家数\t成交额(亿)\t成交额环比\n固态电池\t14\t612\t+18%\n液冷\t9\t388\t-6%\n"
    "商业航天\t6\t241\t+3%\n创新药\t5\t530\t-12%\n算力租赁\t3\t177\t-21%"
)
TABLE_QUESTION = "从这张表看哪条线最强，量能跟得上吗"


def test_split_report_and_question() -> None:
    parts = split_user_message(f"{REPORT}\n\n{REPORT_QUESTION}")

    assert parts.question == REPORT_QUESTION
    assert len(parts.materials) == 1
    material = parts.materials[0]
    assert material.kind == "pasted_text"
    assert material.material_id == material_id_for(REPORT)
    assert "2026-08-28" in material.dates
    assert "2026-08" in material.dates
    assert "硫化物" in material.title
    assert material.paragraphs == 4
    assert material.char_count == len(REPORT)
    assert parts.material_texts == (REPORT,)


def test_split_table_keeps_headers_and_rows() -> None:
    parts = split_user_message(f"{TABLE}\n\n{TABLE_QUESTION}")

    assert parts.question == TABLE_QUESTION
    assert len(parts.materials) == 1
    table = parts.materials[0]
    assert table.kind == "table"
    assert table.headers == ("板块", "涨停家数", "成交额(亿)", "成交额环比")
    assert table.rows == 5
    assert table.title.startswith("表格：板块/涨停家数")


def test_plain_question_is_not_split() -> None:
    parts = split_user_message("明天你怎么看")
    assert parts.question == "明天你怎么看"
    assert parts.materials == ()


def test_material_only_message_has_empty_question() -> None:
    parts = split_user_message(REPORT)
    assert parts.question == ""
    assert len(parts.materials) == 1
    assert parts.materials[0].material_id == material_id_for(REPORT)


def test_report_last_paragraph_is_not_mistaken_for_the_question() -> None:
    # 「三、我们的判断」里有「判断」二字，不能被当成问句把材料切残。
    parts = split_user_message(REPORT)
    assert parts.materials[0].paragraphs == 4


def test_url_becomes_material_and_placeholder_in_question() -> None:
    parts = split_user_message("帮我看看这篇 https://example.com/report/123 说得对不对")
    assert len(parts.materials) == 1
    assert parts.materials[0].kind == "url"
    assert "该链接" in parts.question
    assert "https://" not in parts.question


def test_material_id_is_content_derived_and_whitespace_insensitive() -> None:
    assert material_id_for("a  b\n c") == material_id_for("a b c")
    assert material_id_for(REPORT) != material_id_for(TABLE)
    assert material_id_for(REPORT).startswith("m-")


def test_materials_in_conversation_recovers_the_same_identity() -> None:
    block = (
        "## 较早消息（原文，超预算时从最早处截断）\n（无较早消息）\n\n## 最近消息原文\n"
        f"user: {REPORT}\n\n{REPORT_QUESTION}\n"
        "assistant: 这篇研报的硬事实有三条……\n"
        "user: 这篇里提到的产能数字有官方来源吗"
    )
    found = materials_in_conversation(block)
    assert [ref.material_id for ref, _text in found] == [material_id_for(REPORT)]
    assert found[0][1] == REPORT
    assert materials_in_conversation("") == ()
    assert materials_in_conversation("## 最近消息原文\n（无历史消息）") == ()


def test_references_material_detects_pronoun_forms() -> None:
    assert references_material("这篇里提到的产能数字有官方来源吗")
    assert references_material("2026-07-23 把这份卖方材料提纯一下")
    assert references_material("从这张表看哪条线最强")
    assert not references_material("明天你怎么看")
    assert not references_material("那它的风险点呢")


def test_extract_user_premises_belief_observation_and_prior_reference() -> None:
    assert extract_user_premises(
        "我的经验是龙头连板断了以后板块一般还有一次回流，这次固态电池也会这样吗"
    ) == ("龙头连板断了以后板块一般还有一次回流",)
    assert extract_user_premises("龙头不涨了，是不是这条线要退潮了") == ("龙头不涨了（用户观察）",)
    assert PRIOR_JUDGEMENT_PREMISE in extract_user_premises("液冷题材现在怎么看？我之前的判断还成立吗")
    assert extract_user_premises("明天你怎么看") == ()


def test_extract_method_candidates_shapes_condition_expectation() -> None:
    candidates = extract_method_candidates(
        "我的经验是龙头连板断了以后板块一般还有一次回流，这次固态电池也会这样吗"
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.condition == "龙头连板断了"
    assert "回流" in candidate.expectation
    assert "这次" not in candidate.expectation
    assert candidate.status == METHOD_STATUS_UNVERIFIED
    assert candidate.applicability.startswith("未说明")
    assert candidate.counterexamples == ()


def test_extract_method_candidates_reads_applicability_and_counterexample() -> None:
    candidates = extract_method_candidates(
        "只要主升期里龙头分歧后成交额放大，次日一般会回流，除非大盘同时缩量"
    )
    assert candidates
    assert "主升" in candidates[0].applicability
    assert any("缩量" in item for item in candidates[0].counterexamples)
    assert extract_method_candidates("明天你怎么看") == ()


def test_translate_market_feel_gives_competing_explanations() -> None:
    labels = [item.label for item in translate_market_feel("龙头不涨了，是不是这条线要退潮了")]
    assert "主线退潮" in labels
    assert any("高低切" in label for label in labels)
    assert all(item.observables for item in translate_market_feel("龙头不涨了，是不是这条线要退潮了"))
    assert [item.label for item in translate_market_feel("固态电池主线最近有没有走弱")][0] == "退潮"
    assert translate_market_feel("宁王和迪王现在谁的估值更贵") == ()


def test_resolve_nicknames_pairs_and_guards() -> None:
    assert resolve_nicknames("宁王和迪王现在谁的估值更贵") == (
        ("宁王", "宁德时代"),
        ("迪王", "比亚迪"),
    )
    assert resolve_nicknames("隆基绿能怎么看") == (("隆基绿能", "隆基绿能"),)
    assert resolve_nicknames("上海光明乳业怎么看") == ()
    assert resolve_nicknames("明天你怎么看") == ()


def test_from_task_frame_defaults_user_premises_to_frame() -> None:
    from dataclasses import replace

    frame = replace(_frame(subject="液冷"), user_premises=("龙头不涨了（用户观察）",))

    assert UserTask.from_task_frame(frame).user_premises == ("龙头不涨了（用户观察）",)
    assert UserTask.from_task_frame(frame, {"user_premises": ("外部给的",)}).user_premises == ("外部给的",)
