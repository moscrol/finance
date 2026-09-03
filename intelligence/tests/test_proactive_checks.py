"""本轮主动检查的守门测试。

守的是设计里写死、但代码里很容易被后人改掉的事：
1. 不触发则整段为空——中立提示词不无故变长；
2. 市场阶段题（复盘/主线/怎么看）要触发，个股基本面题不触发；
3. 调用方声明了在场证据种类、却缺检查所需种类 → INSUFFICIENT；
4. 总开关能整块关掉；
5. 检查正文不得混进未回测数字阈值（与 reading_baseline 同一条红线）；
6. 注入标签必须写明「漏检闸 / 不是 KOL 观点」，防止冒充 SPT 口吻。
"""

from __future__ import annotations

import json
import os
import re
from unittest import mock

from intelligence.services import llm_refine, proactive_checks
from intelligence.services.episode_protocol import build_episode_input
from intelligence.tests.test_episode_protocol import _context, _frame
from intelligence.services.task_frame import TaskFrame


def test_generic_fact_question_is_not_triggered() -> None:
    assert proactive_checks.guidance("英维克的液冷业务是什么", question_type="theme_analysis") == ""
    assert proactive_checks.evaluate("固态电池产业链怎么分", question_type="theme_analysis").triggered is False


def test_market_stage_question_triggers_all_four_checks() -> None:
    report = proactive_checks.evaluate("目前市场怎么看", question_type="market_forecast")
    assert report.triggered
    assert [item.check.id for item in report.items] == [
        "SPT-P12",
        "SPT-P13",
        "SPT-P14",
        "SPT-P15",
    ]
    text = proactive_checks.guidance("今天主线还在不在", question_type="dated_market_review")
    assert "[SPT-P12]" in text
    assert "不是 KOL 观点" in text


def test_explicit_claim_words_trigger_without_market_question_type() -> None:
    report = proactive_checks.evaluate("这个冰点能算起始日吗", question_type="general_finance_qa")
    assert report.triggered
    assert any(item.check.id == "SPT-P12" for item in report.items)


def test_missing_required_kinds_are_insufficient() -> None:
    report = proactive_checks.evaluate(
        "医药是不是新主线",
        question_type="market_forecast",
        present_kinds=("volume_structure",),
    )
    by_id = {item.check.id: item for item in report.items}
    assert by_id["SPT-P12"].status == "insufficient"
    assert "index_breadth" in by_id["SPT-P12"].missing_kinds
    assert by_id["SPT-P13"].status == "insufficient"
    text = proactive_checks.render(report)
    assert "INSUFFICIENT" in text
    assert "index_breadth" in text


def test_present_kinds_cover_required_stay_open() -> None:
    report = proactive_checks.evaluate(
        "目前市场怎么看",
        question_type="market_forecast",
        present_kinds=(
            "index_breadth",
            "volume_structure",
            "sector_flow",
            "index_level",
            "sector_structure",
        ),
    )
    assert all(item.status == "open" for item in report.items)


def test_flag_disables_entire_block() -> None:
    off = {"FINANCE_PROACTIVE_CHECKS": "0"}
    assert proactive_checks.evaluate("目前市场怎么看", question_type="market_forecast", env=off).triggered is False
    assert proactive_checks.guidance("目前市场怎么看", question_type="market_forecast", env=off) == ""


def test_no_unbacktested_numeric_thresholds() -> None:
    numeric = re.compile(r"\d+\s*(?:%|倍|万亿|亿|分位)")
    offenders = [
        (check.id, match.group())
        for check in proactive_checks.CHECKS
        for match in [numeric.search(check.rule)]
        if match
    ]
    assert offenders == [], f"主动检查不得带未回测数字阈值：{offenders}"


def test_synthesis_prompt_keeps_old_callers_byte_identical() -> None:
    system = llm_refine.build_synthesis_messages("问题", "题材", "证据")[0]["content"]
    assert "本轮主动检查" not in system


def test_synthesis_prompt_labels_proactive_as_checklist_not_persona() -> None:
    messages = llm_refine.build_synthesis_messages(
        "问题",
        "题材",
        "证据",
        baseline_guidance="- [FY-A10] 框架自身可被证伪",
        proactive_guidance=proactive_checks.guidance("目前市场怎么看", question_type="market_forecast"),
    )
    system = messages[0]["content"]
    assert "本轮主动检查" in system
    assert "不是 KOL 观点" in system
    assert system.index("判读基线") < system.index("本轮主动检查")


def test_market_review_system_appends_checks_only_when_triggered() -> None:
    from intelligence.services.ask import (
        _MARKET_REVIEW_SYSTEM_PROMPT,
        _market_review_system_content,
    )

    assert _market_review_system_content("英维克的液冷业务是什么", "theme_analysis") == (
        _MARKET_REVIEW_SYSTEM_PROMPT
    )
    review = _market_review_system_content("目前市场怎么看", "market_review")
    assert review.startswith(_MARKET_REVIEW_SYSTEM_PROMPT)
    assert "SPT-P12" in review
    assert "不是 KOL 观点" in review


def test_prompt_section_is_empty_when_not_triggered() -> None:
    assert proactive_checks.prompt_section("英维克的液冷业务是什么", question_type="theme_analysis") == ""
    assert proactive_checks.as_prompt_section("") == ""


def test_prompt_section_does_not_double_wrap() -> None:
    body = proactive_checks.guidance("目前市场怎么看", question_type="market_forecast")
    wrapped = proactive_checks.as_prompt_section(body)
    assert wrapped.count("## 本轮主动检查") == 1
    assert proactive_checks.as_prompt_section(wrapped) == wrapped


def test_daily_review_contract_carries_proactive_checks(monkeypatch, tmp_path) -> None:
    from intelligence.workbench_skills import daily_review as skill_module

    monkeypatch.setattr(
        skill_module,
        "mainline_knowledge_module",
        lambda *a, **k: {
            "module_id": "daily_knowledge_anchor",
            "title": "主线方向的知识库积累",
            "kind": "list",
            "status": "complete",
            "summary": "口径说明",
            "content": None,
            "metrics": [],
            "items": [{"title": "半导体", "summary": "概念页 1（半导体）"}],
        },
    )
    monkeypatch.setattr(
        skill_module,
        "daily_projection_modules",
        lambda *a, **k: ("2026-07-29", [{"module_id": "daily_overview", "title": "今日核心"}], []),
    )

    class _Store:
        def add_artifact(self, *a, **k):
            class _A:
                path = "daily-review-skill-result.json"

            return _A()

    class _Ctx:
        query = "今天大盘处于什么阶段？当前主线是哪几个方向？"
        repo_root = tmp_path
        run_store = _Store()
        run_id = "run_proactive"

    output = skill_module.DailyReviewSkill().execute(_Ctx())
    assert output.answer_contract is not None
    contract = "\n".join(output.answer_contract.output_contract)
    assert "SPT-P12" in contract
    assert "不是 KOL 观点" in contract


def test_episode_input_injects_only_when_triggered() -> None:
    market = json.loads(build_episode_input(_frame(), _context(_frame())))
    assert "SPT-P12" in market["proactive_checks"]
    assert "漏检" in market["proactive_checks_rule"]

    stock_frame = TaskFrame(
        raw_question="英维克的液冷业务是什么",
        user_goal="了解业务",
        question_type="theme_analysis",
        subject="英维克",
        subject_kind="company",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_answer",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )
    stock = json.loads(build_episode_input(stock_frame, _context(stock_frame)))
    assert "proactive_checks" not in stock
    assert "proactive_checks_rule" not in stock

    with mock.patch.dict(os.environ, {"FINANCE_PROACTIVE_CHECKS": "0"}):
        off = json.loads(build_episode_input(_frame(), _context(_frame())))
    assert "proactive_checks" not in off
    assert "proactive_checks_rule" not in off
