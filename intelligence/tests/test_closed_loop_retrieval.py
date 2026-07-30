from __future__ import annotations

from datetime import date

from intelligence.services import closed_loop_retrieval
from intelligence.services.closed_loop_retrieval import (
    parse_source_date,
    retrieve_closed_loop,
)
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


def test_attempts_preserve_first_and_cached_dense_fallback_telemetry() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        fallback_reason = (
            "dense_dependency_missing"
            if calls == 1
            else "dense_dependency_cached_unavailable"
        )
        return WikiRagResult(
            ok=True,
            hits=[_hit("液冷证据", 0.72)],
            telemetry=RetrievalTelemetry(
                status="ok",
                hit_count=1,
                requested_mode="hybrid",
                effective_mode="bm25",
                fallback_reason=fallback_reason,
                degraded=True,
            ),
            command=query,
        )

    result = retrieve_closed_loop(
        "液冷",
        anchor=EntityAnchor(entity="液冷"),
        retrieve=retrieve,
    )

    expected = [
        ("hybrid", "bm25", "dense_dependency_missing", True),
        ("hybrid", "bm25", "dense_dependency_cached_unavailable", True),
        ("hybrid", "bm25", "dense_dependency_cached_unavailable", True),
    ]
    assert [
        (
            item.requested_mode,
            item.effective_mode,
            item.fallback_reason,
            item.degraded,
        )
        for item in result.attempts
    ] == expected
    assert [
        (
            item["requested_mode"],
            item["effective_mode"],
            item["fallback_reason"],
            item["degraded"],
        )
        for item in result.inspector_dict()["attempts"]
    ] == expected


def test_observed_query_cost_skips_apertures_that_cannot_fit_budget(
    monkeypatch,
) -> None:
    clock = iter((0.0, 0.0, 0.0, 6.0, 6.0, 6.0))
    monkeypatch.setattr(
        closed_loop_retrieval.time,
        "monotonic",
        lambda: next(clock),
    )
    calls: list[str] = []

    def retrieve(query: str) -> WikiRagResult:
        calls.append(query)
        return _response(query, [_hit("液冷服务器", 0.72)])

    result = retrieve_closed_loop(
        "液冷",
        anchor=None,
        retrieve=retrieve,
        total_seconds=10.0,
    )

    assert len(calls) == 1
    assert [(attempt.aperture, attempt.status) for attempt in result.attempts] == [
        ("narrow", "ok"),
        ("broad", "budget_exhausted"),
        ("counter", "budget_exhausted"),
    ]
    assert [attempt.executed for attempt in result.attempts] == [True, False, False]
    assert [
        item["executed"] for item in result.inspector_dict()["attempts"]
    ] == [True, False, False]
    assert [item.hit.title for item in result.conclusion] == ["液冷服务器"]
    assert result.warnings == [
        "broad retrieval skipped: remaining budget below observed query cost",
        "counter retrieval skipped: remaining budget below observed query cost",
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


def test_query_only_policy_never_promotes_first_hit_topics() -> None:
    raw_query = "这一周行情下跌的主要原因是什么"
    drift_hit = WikiHit(
        page_id="drift",
        file_path="wiki/sources/晚间卖方研报20260202.md",
        title="半导体与光纤光缆复盘",
        score=0.9,
        excerpt="行情下跌后关注半导体、光纤光缆、牧原股份和猪周期",
        best_chunk_id="drift::0",
    )
    queries: list[str] = []

    def retrieve(query: str) -> WikiRagResult:
        queries.append(query)
        return _response(query, [drift_hit])

    retrieve_closed_loop(
        raw_query,
        anchor=None,
        retrieve=retrieve,
        expansion_policy="query_only",
    )

    assert queries[0] == raw_query
    assert len(queries) == 3
    forbidden = ("实体 代码", "公司 题材", "牧原股份", "猪周期", "半导体", "光纤光缆")
    assert all(
        token not in query
        for query in queries[1:]
        for token in forbidden
    )

    anchored_queries: list[str] = []

    retrieve_closed_loop(
        "瑞华泰的合理估值",
        anchor=EntityAnchor("瑞华泰", "688323.SH"),
        retrieve=lambda query: (
            anchored_queries.append(query) or _response(query, [drift_hit])
        ),
        expansion_policy="query_only",
    )

    assert anchored_queries[0] == "瑞华泰 688323.SH"


def test_parse_source_date_accepts_compact_dates_but_not_yearless_names() -> None:
    assert parse_source_date("wiki/sources/晚间卖方研报20260724.md") == date(
        2026, 7, 24
    )
    assert parse_source_date("wiki/sources/0511卖方观点合集.md") is None


def test_budget_estimate_follows_the_latest_attempt_not_the_worst() -> None:
    """冷启动的成本不得成为后续查询的估计值。

    回归：observed_seconds 取运行最大值，一次 60s 冷启动（常驻 RAG worker 加载
    BGE-m3 与 214MB 稠密索引）会永久钉住估计，can_start 随后要求
    remaining >= 60*1.25，在 turn 预算内不可能满足——broad 与 counter 两趟检索
    每轮都被跳过，三趟只跑一趟。
    """
    import time

    from intelligence.services.closed_loop_retrieval import _AttemptBudget

    budget = _AttemptBudget(deadline=time.monotonic() + 30.0)
    budget.observe(60.1)          # 冷启动
    assert budget.can_start() is False

    budget.observe(4.9)           # worker 已热
    assert budget.can_start() is True
    assert budget.observed_seconds == 4.9


def test_budget_still_stops_when_the_deadline_is_spent() -> None:
    import time

    from intelligence.services.closed_loop_retrieval import _AttemptBudget

    budget = _AttemptBudget(deadline=time.monotonic() - 1.0)
    budget.observe(0.1)

    assert budget.can_start() is False


def test_budget_keeps_a_floor_when_an_attempt_looks_free() -> None:
    """估计值趋零时仍要留最小储备，不能无限开新查询。"""
    import time

    from intelligence.services.closed_loop_retrieval import (
        MIN_ATTEMPT_RESERVE_SECONDS,
        _AttemptBudget,
    )

    budget = _AttemptBudget(deadline=time.monotonic() + MIN_ATTEMPT_RESERVE_SECONDS / 2)
    budget.observe(0.0)

    assert budget.can_start() is False
