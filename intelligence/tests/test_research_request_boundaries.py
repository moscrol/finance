"""Research instructions are not pasted evidence or company-ranking requests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.query_understanding import understand_query
from intelligence.services.ranking_contract import parse_ranking_intent
from intelligence.services.user_task import split_user_message

FIXTURES = Path(__file__).parent / "fixtures/research_requests_0921"


@pytest.mark.parametrize("name", ("q1", "q2", "q3"))
def test_frozen_request_keeps_every_requirement_and_its_context(name):
    question = (FIXTURES / f"{name}.txt").read_text().rstrip("\n")
    parts = split_user_message(question)
    assert parts.materials == ()
    assert parts.question == question
    assert parts.question_ids == tuple(f"q{i}" for i in range(1, 8))
    frame = understand_query(question).task_frame
    assert frame is not None
    assert frame.question_type != "kol_review"
    assert frame.material_contract is not None
    assert len(frame.material_contract.questions) == 7
    assert "材料 " not in " ".join(frame.assumptions)
    assert not parse_ranking_intent(question)


@pytest.mark.parametrize("heading", ("请完成以下任务：", "要求：", "研究要求："))
def test_checklist_keeps_nested_details_and_non_question_items(heading):
    question = (
        f"请研究电池产业链盈利传导。\n\n{heading}\n\n"
        "1. 按共同驱动重新分组。\n"
        "2. 对每一组分别列出：\n   - 已确认事实；\n   - 替代解释。\n"
        "3. 不给买卖建议，关键事实注明来源。"
    )
    parts = split_user_message(question)
    assert parts.question == question
    assert parts.materials == ()
    assert parts.question_ids == ("q1", "q2", "q3")
    assert "替代解释" in parts.sub_questions[1]


@pytest.mark.parametrize(
    "wrapper", ("> {}", "```\n{}\n```", "「{}」", "材料如下：\n{}")
)
def test_protected_or_pasted_checklist_is_not_promoted(wrapper):
    brief = "请研究电池需求。\n\n要求：\n1. 列出事实。\n2. 不要联网。"
    wrapped = (
        wrapper.format(brief.replace("\n", "\n> "))
        if wrapper.startswith(">")
        else wrapper.format(brief)
    )
    parts = split_user_message(wrapped)
    assert not getattr(parts.regions, "request_checklist", False)
    assert not any(
        s.scope == "message" and s.kind == "constraint_b"
        for s in parts.regions.instructions
    )


def test_real_document_after_request_remains_material():
    text = (
        "请分析以下报告：\n\n来源：某公司公告\n公司订单增加，预计明年确认收入。\n\n"
        "要求：\n1. 哪些已经确认？\n2. 哪些还需核实？"
    )
    parts = split_user_message(text)
    assert parts.materials
    assert not getattr(parts.regions, "request_checklist", False)


@pytest.mark.parametrize(
    "query",
    (
        "英维克、申菱环境、高澜股份，请把需要核实的资料按信息增益排序。",
        "液冷、储能、光伏，选出最值得优先跟踪的三个方向。",
        "比较订单、收入、利润，给出最强的替代解释。",
        "请按证据强度对三项资料排个序。",
    ),
)
def test_non_company_ranking_does_not_require_company_matrix(query):
    assert not parse_ranking_intent(query)


@pytest.mark.parametrize("suffix", ("", "\n\n不要联网。"))
def test_compact_checklist_retains_independent_scope_instruction(suffix):
    question = "请研究电池需求。\n要求：\n1. 列出事实。\n2. 对照替代解释。" + suffix
    parts = split_user_message(question)
    assert parts.question == question
    assert parts.question_ids == ("q1", "q2")
    assert parts.materials == ()
    frame = understand_query(question).task_frame
    assert frame.material_contract.classification != "boundary_uncertain"
    if suffix:
        assert any(
            s.kind == "constraint_b" and s.scope == "message"
            for s in parts.regions.instructions
        )
        assert "不要联网" not in parts.sub_questions[-1]
        assert frame.material_contract.data_scope != "full"


def test_quoted_document_before_heading_is_not_promoted_to_a_request():
    text = "请分析。\n\n> 请研究电池。\n> 不要联网。\n\n要求：\n1. 列出事实。\n2. 对照证据。"
    assert not split_user_message(text).regions.request_checklist


def test_checklist_does_not_drop_explicit_url_material():
    text = "请研究电池需求。\n\n要求：\n1. 核验 https://example.test/report 。\n2. 对照证据。"
    parts = split_user_message(text)
    assert parts.question == text
    assert any(ref.kind == "url" for ref in parts.materials)


@pytest.mark.parametrize(
    "query",
    (
        "英维克、申菱环境、高澜股份。\n请排个序。",
        "请按证据强度给这三家公司排序。",
        "液冷板块里英维克和申菱环境，谁更值得优先研究？",
        "液冷板块里英维克和申菱环境按证据强度排序。",
        "请给三家公司排序；另外把资料按信息增益排序。",
        "请给三家公司排序，并把资料按信息增益排序。",
    ),
)
def test_real_company_ranking_still_routes(query):
    assert parse_ranking_intent(query)


def test_checklist_is_delivered_to_writer_and_reviewer():
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_protocol import build_episode_input
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.tests.test_episode_protocol import _registry
    from intelligence.tests.test_episode_semantic_verifier import _structural

    question = (FIXTURES / "q3.txt").read_text().rstrip("\n")
    frame = understand_query(question).task_frame
    context = build_episode_context(
        frame,
        task_id="request-test",
        tier="quick",
        today="2026-09-21",
        latest_data_date="2026-09-18",
    )
    writer = json.loads(build_episode_input(frame, context, _registry()))
    # The judge is exercised without calling a model or retrieving data.
    _, verified = _structural("暂不能确认景气改善。")
    reviewer = SemanticEpisodeVerifier()._judge_request(frame, verified, [])
    expected = [
        {"question_id": q.question_id, "text": q.text}
        for q in frame.material_contract.questions
    ]
    assert writer["explicit_requirements"] == expected
    assert reviewer["explicit_requirements"] == expected
    assert "至少3个" in expected[1]["text"]
    assert "第三种解释" in expected[2]["text"]

    from intelligence.services.episode_semantic_verifier import _call_flexible

    assert (
        _call_flexible(lambda **kwargs: kwargs["explicit_requirements"], reviewer, 1)
        == expected
    )
    assert (
        _call_flexible(lambda explicit_requirements: explicit_requirements, reviewer, 1)
        == expected
    )
