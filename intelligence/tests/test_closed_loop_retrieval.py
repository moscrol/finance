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
            return _response(query, [_hit("液冷温控设备", 0.62)])
        if "风险" in query:
            return _response(query, [_hit("液冷需求不及预期", 0.12)])
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
        "液冷温控设备",
    ]
    assert [item.hit.title for item in result.counter_clues] == [
        "液冷需求不及预期"
    ]


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
    assert result.clues == []
    assert any(item.hit.title == "弱相关首页" for item in result.discarded)


def test_irrelevant_hard_source_cannot_bypass_query_relevance() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [_hit("A股消费公司公告", 0.9, hardness="hard")],
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "昨天美股的涨跌情况",
        anchor=None,
        retrieve=retrieve,
    )

    assert result.conclusion == []
    assert result.counter_clues == []
    assert [item.hit.title for item in result.discarded] == [
        "A股消费公司公告"
    ]


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


def test_timeout_stops_rewrites_for_the_same_aperture() -> None:
    calls: list[str] = []

    def retrieve(query: str) -> WikiRagResult:
        calls.append(query)
        return WikiRagResult(
            ok=False,
            hits=[],
            telemetry=RetrievalTelemetry(status="timeout", hit_count=0),
            command=query,
            warning="retrieval timeout",
        )

    result = retrieve_closed_loop("液冷", anchor=None, retrieve=retrieve)

    assert len(calls) == 3
    assert [attempt.aperture for attempt in result.attempts] == [
        "narrow",
        "broad",
        "counter",
    ]


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


def test_index_style_query_does_not_anchor_substring_entities() -> None:
    queries: list[str] = []

    def retrieve(query: str) -> WikiRagResult:
        queries.append(query)
        if len(queries) <= 3:
            return _response(
                query,
                [
                    WikiHit(
                        page_id="中科创达",
                        file_path="wiki/entities/中科创达.md",
                        title="中科创达（300496）",
                        score=0.8,
                        excerpt="中科创达 智能座舱 AIOS 中间件 芯片",
                        best_chunk_id="中科创达::0",
                    )
                ],
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "科创50的支撑点位在哪",
        anchor=None,
        retrieve=retrieve,
    )

    assert result.conclusion == []
    assert result.clues == []
    assert all(
        "中科创达" not in attempt.query for attempt in result.attempts
    )
    assert any(
        item.hit.title.startswith("中科创达") for item in result.discarded
    )
