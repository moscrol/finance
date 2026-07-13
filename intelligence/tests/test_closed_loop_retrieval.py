from __future__ import annotations

from intelligence.services.closed_loop_retrieval import retrieve_closed_loop
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult


def _hit(
    title: str,
    score: float,
    *,
    hardness: str = "",
    path: str | None = None,
) -> WikiHit:
    return WikiHit(
        page_id=title,
        file_path=path or f"wiki/{title}.md",
        title=title,
        score=score,
        excerpt=f"{title} 液冷 服务器 供应链",
        best_chunk_id=title,
        fact_hardness=hardness,
    )


def _response(query: str, hits: list[WikiHit]) -> WikiRagResult:
    return WikiRagResult(
        ok=bool(hits),
        hits=hits,
        telemetry=RetrievalTelemetry(
            status="ok" if hits else "empty",
            hit_count=len(hits),
        ),
        command=query,
    )


def test_closed_loop_uses_entity_code_broad_terms_and_counter_queries() -> None:
    queries: list[str] = []

    def retrieve(query: str) -> WikiRagResult:
        queries.append(query)
        if len(queries) == 1:
            return _response(query, [_hit("液冷服务器", 0.72)])
        if "上下游" in query:
            return _response(query, [_hit("温控设备", 0.62)])
        if "风险" in query:
            return _response(query, [_hit("需求不及预期", 0.12)])
        return _response(query, [])

    result = retrieve_closed_loop(
        "英维克怎么看",
        anchor=EntityAnchor(
            entity="英维克",
            ticker="002837.SZ",
            concepts=("液冷",),
        ),
        retrieve=retrieve,
    )

    assert queries[0] == "英维克 002837.SZ"
    assert any("液冷服务器" in query and "上下游" in query for query in queries)
    assert any("风险 证伪 不及预期" in query for query in queries)
    assert [item.hit.title for item in result.conclusion] == [
        "液冷服务器",
        "温控设备",
    ]
    assert [item.hit.title for item in result.counter_clues] == ["需求不及预期"]


def test_weak_ranked_hit_never_enters_conclusion_bucket() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(query, [_hit("弱相关首页", 0.2)])
        return _response(query, [])

    result = retrieve_closed_loop("短问题", anchor=None, retrieve=retrieve)

    assert result.conclusion == []
    assert any(item.hit.title == "弱相关首页" for item in result.clues)


def test_empty_aperture_stops_after_three_rewrites_and_reports_gap() -> None:
    calls: list[str] = []

    def retrieve(query: str) -> WikiRagResult:
        calls.append(query)
        return _response(query, [])

    result = retrieve_closed_loop("未知对象", anchor=None, retrieve=retrieve)

    for aperture in ("narrow", "broad", "counter"):
        assert len(
            [attempt for attempt in result.attempts if attempt.aperture == aperture]
        ) == 3
    assert len(calls) == 9
    assert len(result.warnings) == 3


def test_hard_evidence_can_enter_conclusion_at_lower_score() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(query, [_hit("公司公告", 0.4, hardness="hard")])
        return _response(query, [])

    result = retrieve_closed_loop("公告影响", anchor=None, retrieve=retrieve)

    assert [item.hit.title for item in result.conclusion] == ["公司公告"]


def test_relevant_hit_is_scale_independent_for_rrf_scores() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(query, [_hit("液冷需求", 0.012)])
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷最近怎么样",
        anchor=EntityAnchor(entity="液冷"),
        retrieve=retrieve,
    )

    assert [item.hit.title for item in result.conclusion] == ["液冷需求"]
