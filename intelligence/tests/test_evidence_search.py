from __future__ import annotations

from dataclasses import replace
from datetime import date

from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.evidence_search import (
    EvidenceSearch,
    EvidenceSearchPolicy,
)
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)


def _response(
    query: str,
    *hits: WikiHit,
    requested_mode: str = "hybrid",
    effective_mode: str = "hybrid",
    fallback_reason: str = "",
    degraded: bool = False,
) -> WikiRagResult:
    return WikiRagResult(
        ok=bool(hits),
        hits=list(hits),
        telemetry=RetrievalTelemetry(
            status="ok" if hits else "empty",
            hit_count=len(hits),
            requested_mode=requested_mode,
            effective_mode=effective_mode,
            fallback_reason=fallback_reason,
            degraded=degraded,
        ),
        command=query,
    )


def _hit(
    key: str,
    title: str,
    excerpt: str,
    *,
    source_date: str = "2026-07-24",
    score: float = 0.9,
) -> WikiHit:
    return WikiHit(
        page_id=key,
        file_path=f"wiki/sources/{key}.md",
        title=title,
        score=score,
        excerpt=excerpt,
        best_chunk_id=f"{key}::0",
        content_hash=f"hash-{key}",
        source_date=source_date,
        evidence_layer="L1",
        index_freshness="fresh",
    )


def _cutoff() -> InformationCutoff:
    return InformationCutoff(date(2026, 7, 24), "requested")


def test_search_preserves_apertures_buckets_and_counter_evidence() -> None:
    narrow = _hit("narrow", "瑞华泰估值锚", "瑞华泰收入与利润估值锚")
    broad = _hit("broad", "瑞华泰同业", "瑞华泰同业可比公司估值")
    counter = _hit("counter", "瑞华泰风险", "瑞华泰需求不及预期风险")

    def retrieve(query: str) -> WikiRagResult:
        if "风险" in query:
            return _response(query, counter)
        if "上下游" in query:
            return _response(query, broad)
        return _response(query, narrow)

    result = EvidenceSearch(retrieve).search(
        query="瑞华泰估值",
        anchor=EntityAnchor("瑞华泰", "688323.SH", ("PI薄膜",)),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert tuple(item.aperture for item in result.attempts) == (
        "narrow",
        "broad",
        "counter",
    )
    assert result.coverage.conclusion_count == 2
    assert result.coverage.counter_count == 1
    assert result.coverage.discarded_count == 0
    assert [item.title for item in result.evidence] == [
        "瑞华泰估值锚",
        "瑞华泰同业",
        "瑞华泰风险",
    ]
    assert "[支持]" in result.observation
    assert "[反方]" in result.observation
    assert result.gaps == ()


def test_search_trace_preserves_first_and_cached_dense_fallbacks() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        return _response(
            query,
            _hit(
                f"fallback-{calls}",
                "瑞华泰估值证据",
                "瑞华泰估值与风险证据",
            ),
            effective_mode="bm25",
            fallback_reason=(
                "dense_dependency_missing"
                if calls == 1
                else "dense_dependency_cached_unavailable"
            ),
            degraded=True,
        )

    result = EvidenceSearch(retrieve).search(
        query="瑞华泰估值",
        anchor=EntityAnchor("瑞华泰", "688323.SH", ("PI薄膜",)),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert [item.fallback_reason for item in result.attempts] == [
        "dense_dependency_missing",
        "dense_dependency_cached_unavailable",
        "dense_dependency_cached_unavailable",
    ]
    assert all(item.requested_mode == "hybrid" for item in result.attempts)
    assert all(item.effective_mode == "bm25" for item in result.attempts)
    assert all(item.degraded for item in result.attempts)
    assert (
        "retrieval_modes="
        "hybrid->bm25:dense_dependency_missing:degraded,"
        "hybrid->bm25:dense_dependency_cached_unavailable:degraded"
        in result.trace.detail
    )


def test_search_trace_marks_true_hybrid_without_degradation() -> None:
    result = EvidenceSearch(
        lambda query: _response(
            query,
            _hit("hybrid", "瑞华泰估值证据", "瑞华泰估值与风险证据"),
        )
    ).search(
        query="瑞华泰估值",
        anchor=EntityAnchor("瑞华泰", "688323.SH", ("PI薄膜",)),
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert all(item.requested_mode == "hybrid" for item in result.attempts)
    assert all(item.effective_mode == "hybrid" for item in result.attempts)
    assert all(item.fallback_reason == "" for item in result.attempts)
    assert not any(item.degraded for item in result.attempts)
    assert "retrieval_modes=hybrid->hybrid" in result.trace.detail


def test_same_chunk_from_two_apertures_becomes_one_evidence_item() -> None:
    duplicate = _hit("same", "液冷证据", "液冷需求与液冷产业链证据")

    def retrieve(query: str) -> WikiRagResult:
        if "风险" in query:
            return _response(query)
        return _response(query, duplicate)

    result = EvidenceSearch(retrieve).search(
        query="液冷需求",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert len(result.evidence) == 1
    assert result.evidence[0].content_hash == "hash-same"


def test_same_content_hash_from_two_paths_becomes_one_evidence_item() -> None:
    canonical = _hit("canonical", "液冷证据", "液冷需求与产业链证据")
    copied = replace(
        _hit("copied", "液冷证据副本", "液冷需求与产业链证据"),
        content_hash=canonical.content_hash,
    )

    def retrieve(query: str) -> WikiRagResult:
        if "风险" in query:
            return _response(query)
        if "上下游" in query:
            return _response(query, copied)
        return _response(query, canonical)

    result = EvidenceSearch(retrieve).search(
        query="液冷需求",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert len(result.evidence) == 1
    assert result.evidence[0].source == "wiki/sources/canonical.md"
    assert result.evidence[0].independent_key == "wiki/sources/canonical.md"
    assert result.coverage.conclusion_count == 1


def test_empty_search_returns_question_specific_gap() -> None:
    result = EvidenceSearch(lambda query: _response(query)).search(
        query="陌生材料兑现进展",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert result.evidence == ()
    assert result.trace.status == "empty"
    assert result.gaps == (
        "尚未找到与“陌生材料兑现进展”直接相关的可用证据",
    )


def test_future_high_score_hit_never_enters_model_observation() -> None:
    future = _hit(
        "future",
        "液冷未来订单",
        "液冷未来订单大幅增长",
        source_date="2026-07-25",
        score=0.999,
    )
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        return _response(query, future) if calls == 1 else _response(query)

    result = EvidenceSearch(retrieve).search(
        query="液冷订单",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert result.evidence == ()
    assert "液冷未来订单" not in result.observation
    assert result.coverage.discarded_count == 1
    assert result.trace.status == "future_of_cutoff"
    assert result.trace.requested_date == "2026-07-24"
    assert result.trace.served_date == "2026-07-25"


def test_semantic_judge_rejection_moves_hit_to_discarded_before_projection() -> None:
    relevant = _hit("relevant", "科创50指数", "科创50指数估值与走势")
    polluted = _hit("polluted", "兰花科创", "兰花科创煤价提供基本面支撑")

    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        return _response(query, relevant, polluted) if calls == 1 else _response(query)

    seen: list[tuple[str, str]] = []

    def judge(_query: str, candidates, _timeout: float):
        seen.extend(candidates)
        return {0}, "丢弃同词异义公司材料"

    result = EvidenceSearch(retrieve, semantic_judge=judge).search(
        query="科创50支撑",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert [item.title for item in result.evidence] == ["科创50指数"]
    assert "兰花科创" not in result.observation
    assert result.coverage.discarded_count == 1
    assert seen == [
        ("科创50指数", "科创50指数估值与走势"),
        ("兰花科创", "兰花科创煤价提供基本面支撑"),
    ]


def test_search_evidence_keeps_source_lineage_and_dates() -> None:
    hit = _hit("lineage", "电力主线", "电力板块成交与强度同步提升")

    result = EvidenceSearch(lambda query: _response(query, hit)).search(
        query="电力主线",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    item = result.evidence[0]
    assert item.tool == "evidence_search"
    assert item.source == "wiki/sources/lineage.md"
    assert item.internal_locator == "wiki/sources/lineage.md#lineage::0"
    assert item.source_date == "2026-07-24"
    assert item.independent_key == "wiki/sources/lineage.md"
    assert item.evidence_tier == "L1"
    assert item.freshness == "fresh"


def _causal_policy() -> EvidenceSearchPolicy:
    return EvidenceSearchPolicy(
        expansion_policy="query_only",
        required_source_start=date(2026, 7, 20),
        required_source_end=date(2026, 7, 24),
        require_counter_evidence=True,
    )


def test_causal_policy_rejects_off_window_evidence_before_observation() -> None:
    old = _hit(
        "old",
        "旧行情归因",
        "行情下跌与风险偏好下降",
        source_date="2026-07-09",
    )

    result = EvidenceSearch(
        lambda query: _response(query, old),
        policy=_causal_policy(),
    ).search(
        query="这一周行情下跌的主要原因是什么",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert result.evidence == ()
    assert result.observation == ""
    assert result.trace.status == "empty"
    assert result.coverage.target_window_count == 0
    assert result.coverage.target_window_counter_count == 0
    assert result.coverage.window_rejected_count == 1
    assert any("2026-07-20" in gap for gap in result.gaps)


def test_causal_policy_requires_counter_before_success() -> None:
    support = _hit(
        "support",
        "本周行情下跌归因",
        "本周行情下跌与资金风险偏好下降有关",
    )

    def retrieve(query: str) -> WikiRagResult:
        if "反证" in query or "数据不支持" in query:
            return _response(query)
        return _response(query, support)

    result = EvidenceSearch(retrieve, policy=_causal_policy()).search(
        query="这一周行情下跌的主要原因是什么",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert [item.title for item in result.evidence] == ["本周行情下跌归因"]
    assert result.trace.status == "partial"
    assert result.coverage.target_window_count == 1
    assert result.coverage.target_window_counter_count == 0
    assert any("反证" in gap for gap in result.gaps)


def test_causal_policy_succeeds_with_target_window_support_and_counter() -> None:
    support = _hit(
        "support",
        "本周行情下跌归因",
        "本周行情下跌与资金风险偏好下降有关",
    )
    counter = _hit(
        "counter",
        "本周行情下跌反证",
        "本周行情下跌也可能来自外部催化而非内部风险偏好",
    )

    def retrieve(query: str) -> WikiRagResult:
        if "反证" in query:
            return _response(query, counter)
        return _response(query, support)

    result = EvidenceSearch(retrieve, policy=_causal_policy()).search(
        query="这一周行情下跌的主要原因是什么",
        anchor=None,
        information_cutoff=_cutoff(),
        deadline=ResearchDeadline.from_timeout(2.0),
    )

    assert [item.title for item in result.evidence] == [
        "本周行情下跌归因",
        "本周行情下跌反证",
    ]
    assert result.trace.status == "success"
    assert result.coverage.target_window_count == 2
    assert result.coverage.target_window_counter_count == 1
    assert result.coverage.window_rejected_count == 0
    assert result.gaps == ()
