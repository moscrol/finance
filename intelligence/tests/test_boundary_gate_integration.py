"""Composition regressions for readiness/date boundaries and citation quantities.

Use the real verifier/write paths with offline fixtures. Passing here says the
mechanical gates compose; it does not certify financial reasoning or live LLMs.
"""
from __future__ import annotations

import pytest

from intelligence.services import llm_refine
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.query_understanding import understand_query
from intelligence.services.ranking_contract import ingest_flip_conditions
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.track_contract import ingest_next_watch
from intelligence.services.user_task import split_user_message
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural
from intelligence.tests.test_ranking_contract import ANSWER as RANKING_ANSWER
from intelligence.tests.test_research_intent_boundaries import _R05_BODY, _TRACK_ANSWER


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("integration regression must not connect to any service")

    monkeypatch.setattr("socket.socket.connect", denied)
    monkeypatch.setattr("socket.create_connection", denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


def _verify(text, *, detail="需求改善仍需后续观察。"):
    frame, structural = _structural(
        text, detail=detail, title="需求跟踪公告", source="公司公告",
    )
    return SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("plan", [
    "若到2026-10-21需求仍未改善，应重新评估 E1。",
    "若到2026-10-21需求仍未改善，应重新评估（E1）。",
    "若到2026年10月21日需求仍未改善，应重新评估 [E1]。",
    "计划于2026-10-21复查 E1 的公告。",
])
def test_future_review_with_citation_survives_both_gates(monkeypatch, mode, plan):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    draft = plan + "市场需求仍需观察。"
    result = _verify(draft)

    assert result.public_answer == draft
    assert result.verified.outcome.draft == draft
    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert not any("numeric_condition" in issue or "evidence_date_mismatch" in issue for issue in result.issues)


@pytest.mark.usefixtures("numeric_delete_mode")
@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("bad,reason", [
    ("E1 显示该公告发布于2026-08-21。", "evidence_date_mismatch"),
    ("若到2026-10-21评分仍低于27，应重新评估 E1。", "numeric_condition"),
    ("若到2026-10-21需求仍未改善，应重新评估 E99。", "unresolved_evidence_ordinal"),
    ("E1 显示该公告发布于2026-08-21，计划在2026-07-22复查。", "evidence_date_mismatch"),
])
def test_invalid_claim_is_removed_without_losing_the_neighboring_plan(monkeypatch, mode, bad, reason):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    plan = "若到2026-10-21需求仍未改善，应重新评估 E1。"
    result = _verify(plan + bad)

    assert result.public_answer == plan
    assert result.verified.outcome.draft == plan
    assert result.judge_status == "repaired"
    assert any(reason in issue for issue in result.issues)


@pytest.mark.usefixtures("numeric_delete_mode")
@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("supported", [False, True])
def test_support_is_a_business_value_not_an_evidence_identifier(monkeypatch, mode, supported):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    plan = "计划于2026-10-21复查 E1 的公告。"
    condition = "若到2026-10-21评分仍低于27，应重新评估 E1。"
    detail = "观察阈值为27。" if supported else "参考 E27，尚需观察。"
    result = _verify(plan + condition, detail=detail)

    assert result.public_answer == plan + (condition if supported else "")
    assert result.judge_status == ("passed" if supported else "repaired")


@pytest.mark.parametrize("tail", [
    "【输出要求】请按事实条目逐条整理。",
    "1. 请按事实条目逐条整理。\n2. 请给出后续研究问题。",
    "【输出要求】\n来源：逐项注明。",
])
@pytest.mark.parametrize("writer,answer", [
    (ingest_next_watch, _TRACK_ANSWER),
    (ingest_flip_conditions, RANKING_ANSWER),
], ids=["next_watch", "ranking_flip"])
def test_formatted_financial_request_reaches_real_write_opt_out(tmp_path, tail, writer, answer):
    # Compose the real splitter, router and writers; this is not a run_turn or
    # live model test. The registration control rules out an inert writer.
    query = _R05_BODY + "\n也请跟踪一下后续现金流。\n\n" + tail
    parts = split_user_message(query)
    assert parts.materials == ()
    assert parts.question == query
    understood = understand_query(query)
    assert (understood.question_type, understood.subject) == ("financial_analysis", "中际旭创")
    path = tmp_path / "checkpoints.jsonl"
    ranking_query = "英维克、申菱环境、高澜股份谁更值得优先研究？排个序；"
    write_query = ranking_query + parts.question if writer is ingest_flip_conditions else parts.question
    assert writer(path, answer, query=write_query, as_of="2026-09-16") == []
    assert not path.exists()
    assert writer(
        path, answer, query=ranking_query + "请登记为长期跟踪", as_of="2026-09-16",
    )
    assert path.exists()
