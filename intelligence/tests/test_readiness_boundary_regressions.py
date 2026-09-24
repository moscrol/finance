"""8792 独立 QC 的三类反例进入正式 pytest；不调用模型/生产写口。

覆盖同义改写与仅排版变化，并保留阳性对照，防止用「不再写入 / 删掉日期门 /
不再识别材料」冒充修复。原审查探针见 docs/qc-8792-readiness-0917 分支。
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.services import episode_semantic_verifier as verifier, llm_refine
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.query_understanding import understand_query
from intelligence.services.ranking_contract import ingest_flip_conditions
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.track_contract import (
    ingest_next_watch,
    parse_track_intent,
    persistence_opt_out,
)
from intelligence.services.user_task import split_user_message
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural
from intelligence.tests.test_ranking_contract import ANSWER as RANKING_ANSWER
from intelligence.tests.test_research_intent_boundaries import _R05_BODY, _TRACK_ANSWER
from intelligence.tests.test_user_task import REPORT, REPORT_QUESTION

OPT_OUTS = (
    "不需要登记这只股票为长期跟踪",
    "不要把这只股票登记为长期跟踪",
    "不要登记这两只股票为长期跟踪",
    "不要登记3只股票为长期跟踪",
    "不要将这次关于经营质量的研究登记为长期跟踪",
    "请勿将这次关于经营质量和现金流量的研究写入长期跟踪清单",
    "这次长期跟踪观察项不用登记",
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("boundary regression must not make network calls")

    monkeypatch.setattr("socket.socket.connect", denied)
    monkeypatch.setattr("socket.create_connection", denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


@pytest.mark.parametrize("query", OPT_OUTS)
def test_explicit_opt_out_preserves_research_but_not_persistence(query):
    assert persistence_opt_out(query)
    assert not parse_track_intent(query)
    assert parse_track_intent("跟踪一下中际旭创，但" + query)
    assert parse_track_intent("跟踪一下中际旭创但" + query)


@pytest.mark.parametrize("query", OPT_OUTS)
@pytest.mark.parametrize("writer", ["next_watch", "flip", "orchestrator"])
def test_explicit_opt_out_blocks_real_writers(tmp_path, monkeypatch, query, writer):
    path = tmp_path / "checkpoints.jsonl"
    if writer == "orchestrator":
        from intelligence.runtime import conversation_orchestrator as co

        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setattr(co.userspace, "user_space", lambda _: SimpleNamespace(checkpoints_path=path))
        co.TurnOrchestrator._ingest_track_next_watch(
            SimpleNamespace(run_store=SimpleNamespace(user_id="qc-isolated")),
            query=query, answer=_TRACK_ANSWER, question_type="theme_track",
            as_of="2026-09-16", theme=None, session_id="qc-boundary",
        )
    else:
        ingest, answer = (
            (ingest_next_watch, _TRACK_ANSWER) if writer == "next_watch"
            else (ingest_flip_conditions, RANKING_ANSWER)
        )
        query = "英维克、申菱环境、高澜股份谁更值得优先研究？排个序；" + query
        assert ingest(path, answer, query=query, as_of="2026-09-16", session_id="qc-boundary") == []
    assert not path.exists()


@pytest.mark.parametrize("query", [
    "不要只登记这只股票为长期跟踪，还要给到期日",
    "不要仅仅登记为长期跟踪，还要给到期日",
    "别忘了将这次关于经营质量的研究登记为长期跟踪",
    "请勿遗漏登记这只股票为长期跟踪",
    "需不需要将这次关于经营质量的研究登记为长期跟踪？",
    "不要预测，登记为长期跟踪",
    "不要预测\n登记为长期跟踪",
])
def test_qualifiers_questions_and_clause_boundaries_are_not_opt_outs(query):
    assert not persistence_opt_out(query)
    assert parse_track_intent(query)


@pytest.mark.parametrize("writer", [ingest_next_watch, ingest_flip_conditions])
def test_positive_registration_still_writes(tmp_path: Path, writer):
    answer = _TRACK_ANSWER if writer is ingest_next_watch else RANKING_ANSWER
    path = tmp_path / "checkpoints.jsonl"
    assert writer(
        path, answer,
        query="英维克、申菱环境、高澜股份谁更值得优先研究？排个序；请登记为长期跟踪",
        as_of="2026-09-16",
    )
    assert path.exists()


PLANS = (
    "后续观察：计划在2026-10-21复查 E1 所述需求是否改善。",
    "后续观察：到2026年10月21日再看 E1 中的需求能否兑现。",
    "计划于2026-10-21发布 E1 的复查结论。",
    "待补查：该公告是否发布于2026-10-21，见 E1？",
    "E1 中的项目预计在2026-10-21投产。",
)


@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("plan", PLANS)
def test_date_gate_preserves_plans_and_non_source_dates(monkeypatch, mode, plan):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, structural = _structural(
        plan + "我的基准判断是反弹仍有数日窗口。",
        detail="需求改善仍需后续观察。", title="需求跟踪公告", source="公司公告",
    )
    result = verifier.SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert plan in result.public_answer
    assert not any("evidence_date_mismatch" in issue for issue in result.issues)


@pytest.mark.parametrize("text", [
    "E1 显示该公告发布于2026-08-21。",
    "该公告的发布日期为2026年8月21日，见 E1。",
    "E1 的来源日期为2026-08-21。",
    "E1 显示该公告于2026-08-21发布。",
    "E1 显示该公告发布于2026-08-21，计划在2026-07-22复查。",
])
def test_source_date_assertions_remain_mechanically_rejected(text):
    _, structural = _structural("占位。", detail="计划在2026-08-21复查需求。")
    # detail 中另有同日计划，不能为错误的「发布日期」背书。
    assert verifier._mismatched_evidence_date_indexes(verifier._numbered_sentences(text), structural) == (1,)


@pytest.mark.parametrize("text", [
    "E1 显示该公告发布于2026-07-22，计划在2026-10-21复查。",
    "E1 显示该公告并非发布于2026-08-21。",
    "如果该公告发布于2026-08-21，E1 的时效应重查。",
    "E1 的项目投产日期是2026-10-21。",
    "E1 的来源日期是否为2026-08-21？",
    # 全链另有 E1 被数值门误读的缺陷（独立 citation-numeric 分支在修）。
    # 此处只断言日期门不误删，不用替换数值门制造全链已绿的假结论。
    "若到2026-10-21需求仍未改善，应重新评估 E1。",
    "E1 的来源日期为2026-13-21。",  # 非日历日期不由错配门猜测
])
def test_non_assertions_and_matching_publication_dates_are_left_alone(text):
    _, structural = _structural("占位。")
    assert verifier._mismatched_evidence_date_indexes(verifier._numbered_sentences(text), structural) == ()


def test_date_gate_requires_source_date_not_unrelated_corpus_dates():
    _, structural = _structural("占位。", detail="需求于2026-07-22改善。")
    evidence = replace(structural.outcome.evidence[0], source_date="")
    structural = verify_episode_outcome(
        structural.contract, replace(structural.outcome, evidence=(evidence,)),
    )
    assert verifier._mismatched_evidence_date_indexes(
        verifier._numbered_sentences("E1 显示该公告发布于2026-08-21。"), structural,
    ) == ()


FORMAT_TAILS = (
    "请按事实条目逐条整理。",
    "【输出要求】请按事实条目逐条整理。",
    "【输出要求】\n请按事实条目逐条整理。",
    "【输出要求】\n来源：逐项注明。",
    "1. 请按事实条目逐条整理。\n2. 请给出后续研究问题。",
    "一、请按事实条目逐条整理。\n二、请给出后续研究问题。",
)


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
@pytest.mark.parametrize("tail", FORMAT_TAILS)
def test_formatting_does_not_demote_question_or_change_route(separator, tail):
    text = _R05_BODY + separator + tail
    parts = split_user_message(text)
    assert parts.materials == ()
    assert parts.question == text
    actual = understand_query(text)
    assert (actual.question_type, actual.subject) == ("financial_analysis", "中际旭创")


@pytest.mark.parametrize("separator", ["", "\n", "\n\n"])
def test_explicit_research_request_has_no_length_based_material_cutoff(separator):
    body = _R05_BODY + "请分别说明比较口径、缺失项以及不能由现有证据推断的结论。" * 8
    text = body + separator + "请给出支持证据和关键反证。"
    parts = split_user_message(text)
    assert parts.materials == ()
    assert parts.question == text


@pytest.mark.parametrize("prefix", ["【研究问题】\n", "## 研究任务\n"])
def test_request_heading_does_not_demote_its_body(prefix):
    text = prefix + _R05_BODY + "\n请按事实条目逐条整理。"
    parts = split_user_message(text)
    assert parts.materials == ()
    assert parts.question == text


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
@pytest.mark.parametrize("question", [REPORT_QUESTION, _R05_BODY])
def test_request_followed_by_actual_document_preserves_both_roles(separator, question):
    parts = split_user_message(question + separator + REPORT)
    assert parts.question == question
    assert parts.material_texts == (REPORT,)


@pytest.mark.parametrize("order", ["first", "last"])
def test_actual_document_and_question_still_split(order):
    pieces = [REPORT_QUESTION, REPORT] if order == "first" else [REPORT, REPORT_QUESTION]
    parts = split_user_message("\n\n".join(pieces))
    assert parts.material_texts == (REPORT,)
    assert parts.question == REPORT_QUESTION


def test_directives_inside_a_report_do_not_turn_it_into_a_user_request():
    doc = REPORT + "\n【输出要求】请按事实条目逐条整理。"
    parts = split_user_message(doc + "\n\n" + REPORT_QUESTION)
    assert parts.material_texts == (doc,)
    assert parts.question == REPORT_QUESTION
