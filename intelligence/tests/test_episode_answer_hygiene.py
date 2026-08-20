"""P1 Q1/Q3：未尝试不得写成未命中；残稿 withhold + 减句回退。

对应 `docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`
§7.7–7.14。Q2 补枪不在本文件。
"""

from __future__ import annotations

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_answer_hygiene import (
    ASKED_DATE_COVERAGE_TYPES,
    choose_repair_rollback,
    classify_asked_date_coverage,
    find_unattempted_claims,
    repair_collapsed_to_stub,
    rewrite_unattempted_claims,
    sentence_count,
)
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _drop_rejected_sentences,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.services.task_frame import TaskFrame, last_explicit_iso_date
from intelligence.tests.test_episode_semantic_verifier import _judge


def _frame(
    question: str,
    question_type: str,
    *,
    subject: str = "锂矿",
) -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal="判断盘面",
        question_type=question_type,
        subject=subject,
        subject_kind="theme",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )


def _structural(
    draft: str,
    *,
    question: str,
    question_type: str,
    traces: tuple[ProviderTrace, ...] = (),
    subject: str = "锂矿",
):
    frame = _frame(question, question_type, subject=subject)
    evidence = AgentEvidence(
        tool="market_data",
        title="盘面快照",
        detail="板块涨跌与成交",
        source="行情快照",
        source_date="2026-07-23",
        content_hash="HASH_HYGIENE_EVIDENCE",
    )
    required_outputs = (
        RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
    )
    contract = ResearchTaskContract(
        task_id="hygiene-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=required_outputs,
        allowed_capabilities=("market_data", "news_search", "finance_query"),
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(evidence,),
        traces=traces,
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),
        ),
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    return frame, verify_episode_outcome(contract, outcome)


def _verify(frame, structural, judge):
    return SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def _padded(tag: str, width: int = 200) -> str:
    body = "盘面观察与成交结构" * 40
    return f"{tag}{body[:width]}。"


def test_last_explicit_iso_date_uses_final_calendar_day() -> None:
    question = "低空经济这波从月初发酵到 2026-07-10，怎么看后续？"
    assert last_explicit_iso_date(question) == "2026-07-10"


def test_directional_news_receipt_counts_as_attempted() -> None:
    """§7.7：电网形。future_of_cutoff 算尝试过，不得改口。"""

    draft = "②news检索未返回7-23同时间窗口的催化消息，无法把上涨归因为具体事件。"
    traces = (
        ProviderTrace(
            provider="eastmoney",
            capability="directional_news",
            status="future_of_cutoff",
            requested_date="2026-07-23",
            detail="future_of_cutoff pages=4",
        ),
    )
    claims = find_unattempted_claims(draft, traces, asked_date="2026-07-23")
    assert claims == ()
    frame, structural = _structural(
        draft,
        question="电网设备这波从月初发酵到 2026-07-23",
        question_type="theme_analysis",
        traces=traces,
        subject="电网设备",
    )
    result = _verify(frame, structural, _judge(True))
    assert result.to_dict()["unattempted_claim_count"] == 0
    assert "news检索未返回" in result.public_answer
    assert "本次未查询" not in result.public_answer


def test_news_search_tool_name_is_not_a_receipt() -> None:
    """陷阱注：判据必须是 capability=directional_news，不是工具名。"""

    draft = "news检索未返回7-23催化。"
    traces = (
        ProviderTrace(
            provider="agent:news_search",
            capability="news_search",
            status="success",
        ),
    )
    claims = find_unattempted_claims(draft, traces, asked_date="2026-07-23")
    assert len(claims) == 1
    assert claims[0].capability == "directional_news"


def test_truncated_finance_query_counts_as_attempted() -> None:
    """§7.8：锂矿形。窗口覆盖锚定日且被截断 ≠ 未尝试。"""

    draft = "7/23当日数据未取到，属数据缺口。"
    traces = (
        ProviderTrace(
            provider="duckdb_semantic_query",
            capability="finance_query",
            status="success",
            requested_date="2026-08-20",
            requested_time_range=("2026-07-10", "2026-07-23"),
            result_count=25,
            detail="truncated; covered 2026-07-10..2026-07-22",
        ),
    )
    claims = find_unattempted_claims(draft, traces, asked_date="2026-07-23")
    assert claims == ()
    coverage = classify_asked_date_coverage(
        "锂矿板块从月初发酵到 2026-07-23",
        "theme_analysis",
        traces,
    )
    assert coverage == "truncated"
    frame, structural = _structural(
        draft,
        question="锂矿板块从月初发酵到 2026-07-23",
        question_type="theme_analysis",
        traces=traces,
    )
    result = _verify(frame, structural, _judge(True))
    assert result.to_dict()["unattempted_claim_count"] == 0
    assert result.to_dict()["asked_date_coverage"] == "truncated"
    assert "当日数据未取到" in result.public_answer
    assert "本次未查询 finance_query" not in result.public_answer


def test_unattempted_news_claim_without_any_trace() -> None:
    """§7.9：完全没有资讯 capability 才改口。"""

    draft = "news检索未返回催化，所以无法归因为订单。"
    claims = find_unattempted_claims(draft, (), asked_date="2026-07-23")
    assert len(claims) >= 1
    rewritten = rewrite_unattempted_claims(draft, claims)
    assert "未返回" not in rewritten
    assert "本次未查询 directional_news 2026-07-23" in rewritten
    frame, structural = _structural(
        draft,
        question="电网设备这波从月初发酵到 2026-07-23",
        question_type="theme_analysis",
        traces=(),
        subject="电网设备",
    )
    result = _verify(frame, structural, _judge(True))
    assert result.to_dict()["unattempted_claim_count"] >= 1
    assert "未返回" not in result.public_answer
    assert "本次未查询 directional_news" in result.public_answer
    assert any("unattempted_claim" in item for item in result.issues)


def test_undated_theme_skips_asked_date_coverage() -> None:
    """§7.10：商业航天无日历日 → not_applicable。"""

    coverage = classify_asked_date_coverage(
        "商业航天后续怎么看",
        "theme_analysis",
        (),
    )
    assert coverage == "not_applicable"
    frame, structural = _structural(
        "商业航天仍在发酵，需要观察订单兑现。",
        question="商业航天后续怎么看",
        question_type="theme_analysis",
        subject="商业航天",
    )
    result = _verify(frame, structural, _judge(True))
    assert result.to_dict()["asked_date_coverage"] == "not_applicable"


def test_repair_collapsed_to_stub_truth_table() -> None:
    assert repair_collapsed_to_stub("x" * 800, "盘中涨2.66%。", "market_cause")
    assert not repair_collapsed_to_stub(
        "x" * 640, "甲。" * 3 + "乙。" * 200, "theme_analysis"
    )
    assert not repair_collapsed_to_stub("x" * 80, "短句。", "quick_fact")
    two_sentences = "判断仍在" + ("盘面观察" * 10) + "。反证尚未确认。"
    assert sentence_count(two_sentences) == 2
    assert not repair_collapsed_to_stub("x" * 400, two_sentences, "theme_analysis")
    assert "market_cause" in ASKED_DATE_COVERAGE_TYPES


def test_repair_withholds_collapsed_stub() -> None:
    """§7.11：修后一句残稿 → withhold。闸门 type 含 market_cause。"""

    remnant = "【当前判断】盘中涨2.66%，宏桥南山神火。"
    draft = (
        _padded("事实一")
        + _padded("事实二")
        + _padded("归因三")
        + _padded("前瞻四")
        + remnant
    )
    assert repair_collapsed_to_stub(draft, remnant, "market_cause")
    frame, structural = _structural(
        draft,
        question="2026-07-23 A股铝板块为什么涨",
        question_type="market_cause",
        subject="铝",
    )
    result = _verify(
        frame,
        structural,
        _judge(False, rejected=(1, 2, 3, 4), issues=("超证",)),
    )
    payload = result.to_dict()
    assert result.repair_withheld is True
    assert payload["repair_collapsed_to_stub"] is True
    assert result.judge_status == "repaired"


def test_rollback_subtracts_judge_flagged_sentences() -> None:
    """§7.12：回退是减句，不是整篇修前稿。"""

    kept_a = (
        "铝板块7月23日收盘涨5.33%，成交额226.41亿，这是当日硬事实，"
        "属于问句日收盘口径。"
    )
    kept_b = (
        "盘中快照里宏桥南山神火仍在，属于同步观察而非事后归因，"
        "不能单独当成因果。"
    )
    toxic_a = "07-29复盘解释07-23上涨，属于时点越界。"
    toxic_b = "产能天花板加上海外供给受限，属于发明机制。"
    extra_c = "给出未被要求的前瞻条件，应当删除。"
    extra_d = "把收盘口径和盘中快照混成一条因果。"
    before = kept_a + kept_b + toxic_a + toxic_b + extra_c + extra_d
    minus = _drop_rejected_sentences(before, (3, 4, 5, 6))
    text, mode = choose_repair_rollback(before, minus)
    assert mode == "minus_flagged_sentences"
    assert "07-29复盘解释07-23" not in text
    assert "产能天花板" not in text
    assert "5.33%" in text
    assert "宏桥南山神火" in text


def test_rollback_falls_back_to_whole_draft_when_still_stub() -> None:
    """§7.13：减完仍残稿 → whole_pre_repair，并说明含 N 条未过判官的表述。"""

    remnant = "【当前判断】盘中涨2.66%。"
    draft = _padded("越界一") + _padded("发明二") + _padded("前瞻三") + remnant
    minus = _drop_rejected_sentences(draft, (1, 2, 3))
    text, mode = choose_repair_rollback(draft, minus)
    assert mode == "whole_pre_repair"
    assert text == draft
    frame, structural = _structural(
        draft,
        question="2026-07-23 A股铝板块为什么涨",
        question_type="market_cause",
        subject="铝",
    )
    result = _verify(
        frame,
        structural,
        _judge(
            False,
            rejected=(1, 2, 3),
            issues=("第1句越界", "第2句发明", "第3句前瞻"),
        ),
    )
    assert result.repair_withheld is True
    assert result.to_dict()["repair_rollback_mode"] == "whole_pre_repair"
    assert any("未通过判官的表述" in item for item in result.issues)


def test_repair_keeps_trimmed_but_usable_draft() -> None:
    """§7.14：删一句仍 ≥3 句 → 不 withhold。"""

    draft = _padded("判断") + _padded("链条") + _padded("反证") + _padded("边界")
    frame, structural = _structural(
        draft,
        question="电网设备这波从月初发酵到 2026-07-23",
        question_type="theme_analysis",
        subject="电网设备",
    )
    result = _verify(
        frame,
        structural,
        _judge(False, rejected=(2,), issues=("跨口径一句",)),
    )
    assert result.repair_withheld is False
    assert result.to_dict()["repair_collapsed_to_stub"] is False
    assert result.judge_status == "repaired"
    assert sentence_count(result.public_answer) >= 3
