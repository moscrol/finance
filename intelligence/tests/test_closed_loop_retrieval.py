from __future__ import annotations

from intelligence.services.closed_loop_retrieval import retrieve_closed_loop
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.execution_budget import ExecutionBudget
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult


def _hit(
    title: str,
    score: float,
    *,
    hardness: str = "",
    path: str | None = None,
    excerpt: str | None = None,
    revision: str = "rev-1",
) -> WikiHit:
    return WikiHit(
        page_id=title,
        file_path=path or f"wiki/{title}.md",
        title=title,
        score=score,
        excerpt=excerpt if excerpt is not None else f"{title} 液冷 服务器 供应链",
        best_chunk_id=title,
        content_hash=f"hash-{title}",
        index_source_revision=revision,
        index_freshness="fresh",
        fact_hardness=hardness,
    )


def _response(
    query: str,
    hits: list[WikiHit],
    *,
    status: str | None = None,
    freshness: str = "fresh",
    warning: str = "",
    dense_initializations: int = 0,
    timeout_seconds: float = 10.0,
    revision: str = "rev-1",
    latency_ms: int | None = None,
) -> WikiRagResult:
    resolved_status = status or ("ok" if hits else "empty")
    return WikiRagResult(
        ok=resolved_status == "ok",
        hits=hits,
        telemetry=RetrievalTelemetry(
            status=resolved_status,
            hit_count=len(hits),
            index_freshness=freshness,
            index_source_revision=revision,
            dense_initializations=dense_initializations,
            timeout_seconds=timeout_seconds,
            latency_ms=latency_ms,
        ),
        command=query,
        warning=warning,
    )


def test_subjectless_query_does_not_retrieve() -> None:
    calls: list[tuple[str, str, float]] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append((query, mode, timeout))
        return _response(query, [])

    result = retrieve_closed_loop(
        "如果题材成交占比下降，该怎么判断行情阶段？",
        anchor=None,
        subject=None,
        retrieve=retrieve,
    )

    assert calls == []
    assert result.attempts == []
    assert any("no explicit subject" in warning for warning in result.warnings)


def test_subject_uses_three_bm25_queries_and_at_most_one_hybrid() -> None:
    calls: list[tuple[str, str, float]] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append((query, mode, timeout))
        if mode == "bm25" and len(calls) == 1:
            return _response(query, [_hit("液冷服务器", 0.72)])
        if mode == "hybrid":
            return _response(
                query,
                [_hit("液冷产业公告", 0.4, hardness="hard")],
                dense_initializations=1,
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷最近怎么样",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert [mode for _, mode, _ in calls] == ["bm25", "bm25", "bm25", "hybrid"]
    assert all(timeout == 10 for _, _, timeout in calls)
    assert sum(attempt.mode == "hybrid" for attempt in result.attempts) == 1
    assert result.dense_initializations == 1
    assert [item.hit.title for item in result.conclusion] == ["液冷产业公告"]
    assert any("液冷服务器" in query and "上下游" in query for query, _, _ in calls)
    assert any("风险 证伪 不及预期" in query for query, _, _ in calls)


def test_real_adapter_empty_shape_continues_all_layers() -> None:
    calls: list[str] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append(mode)
        return _response(
            query,
            [],
            status="empty",
            freshness="",
            dense_initializations=1 if mode == "hybrid" else 0,
        )

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert calls == ["bm25", "bm25", "bm25", "hybrid"]
    assert len(result.attempts) == 4
    assert result.dense_initializations == 1
    assert not any("untrusted index freshness: missing" in w for w in result.warnings)


def test_explicit_untrusted_empty_response_still_stops() -> None:
    for freshness in ("stale", "unknown"):
        calls = 0

        def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
            nonlocal calls
            calls += 1
            return _response(query, [], status="empty", freshness=freshness)

        result = retrieve_closed_loop(
            "液冷怎么看",
            anchor=None,
            subject="液冷",
            retrieve=retrieve,
        )

        assert calls == 1
        assert len(result.attempts) == 1


def test_hybrid_deduplicates_hits_already_seen_by_bm25() -> None:
    duplicate = _hit("液冷服务器", 0.4, hardness="hard")

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        if mode == "bm25" and "上下游" not in query and "风险" not in query:
            return _response(query, [_hit("液冷服务器", 0.2)])
        if mode == "hybrid":
            return _response(
                query,
                [duplicate, _hit("液冷新公告", 0.5, hardness="hard")],
                dense_initializations=1,
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    all_titles = [
        item.hit.title
        for bucket in (result.conclusion, result.clues, result.discarded)
        for item in bucket
    ]
    assert all_titles.count("液冷服务器") == 1
    assert "液冷新公告" in [item.hit.title for item in result.conclusion]


def test_hybrid_same_identity_cross_snapshot_is_rejected_after_bm25_clue() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        if mode == "bm25" and "上下游" not in query and "风险" not in query:
            return _response(
                query,
                [_hit("液冷共享 chunk", 0.3, revision="rev-1")],
                revision="rev-1",
            )
        if mode == "hybrid":
            return _response(
                query,
                [
                    _hit(
                        "液冷共享 chunk",
                        0.9,
                        hardness="hard",
                        revision="rev-2",
                    )
                ],
                revision="rev-2",
                dense_initializations=1,
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert result.conclusion == []
    assert [item.hit.index_source_revision for item in result.clues] == ["rev-1"]
    assert [item.hit.index_source_revision for item in result.discarded] == ["rev-2"]
    assert any("snapshot conflict" in warning for warning in result.warnings)
    assert result.telemetry is not None
    assert result.telemetry.status == "empty"
    assert result.telemetry.hit_count == 0
    assert result.telemetry.degraded


def test_unrecoverable_status_stops_after_first_attempt() -> None:
    calls: list[tuple[str, str, float]] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append((query, mode, timeout))
        return _response(
            query,
            [_hit("液冷旧索引", 0.8, hardness="hard")],
            status="skipped",
            warning="index unavailable",
        )

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert len(calls) == 1
    assert result.attempts[0].status == "skipped"
    assert result.attempts[0].mode == "bm25"
    assert result.warnings == ["index unavailable"]
    assert result.conclusion == []
    assert result.clues == []
    assert result.counter_clues == []
    assert result.discarded == []


def test_untrusted_freshness_stops_and_never_buckets_returned_hits() -> None:
    for freshness in ("stale", "unknown", "", "unexpected"):
        calls = 0

        def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
            nonlocal calls
            calls += 1
            return _response(query, [_hit("液冷", 0.5)], freshness=freshness)

        result = retrieve_closed_loop(
            "液冷怎么看",
            anchor=None,
            subject="液冷",
            retrieve=retrieve,
        )

        assert calls == 1
        assert len(result.attempts) == 1
        assert result.conclusion == []
        assert result.clues == []
        assert result.counter_clues == []
        assert result.discarded == []


def test_budget_timeout_is_recorded_without_calling_retriever() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        budget=ExecutionBudget(started_at=0, deadline_at=5),
        now=lambda: 0,
    )

    assert calls == 0
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "timeout"
    assert result.attempts[0].timeout_seconds == 0
    assert any(
        "budget exhausted" in warning and "retrieval not executed" in warning
        for warning in result.warnings
    )


def test_budget_skips_dense_when_semantic_window_is_too_small() -> None:
    calls: list[str] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append(mode)
        return _response(query, [_hit("液冷线索", 0.2)]) if len(calls) == 1 else _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        budget=ExecutionBudget(started_at=0, deadline_at=20),
        now=lambda: 10,
    )

    assert calls == ["bm25", "bm25", "bm25"]
    assert result.dense_initializations == 0
    assert any(
        "semantic retrieval skipped" in warning and "insufficient budget" in warning
        for warning in result.warnings
    )


def test_irrelevant_hard_evidence_is_discarded() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [
                    _hit(
                        "公司公告",
                        0.9,
                        hardness="hard",
                        excerpt="半导体设备订单增长",
                    )
                ],
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert result.conclusion == []
    assert result.clues == []
    assert [item.hit.title for item in result.discarded] == ["公司公告"]


def test_generic_query_words_cannot_make_unrelated_hard_evidence_relevant() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [
                    _hit(
                        "半导体投资机会",
                        0.9,
                        hardness="hard",
                        excerpt="半导体设备的投资机会与估值判断",
                    ),
                    _hit(
                        "温控设备",
                        0.3,
                        excerpt="液冷系统需要温控设备与冷却单元",
                    ),
                ],
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看投资机会",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert [item.hit.title for item in result.discarded] == ["半导体投资机会"]
    assert [item.hit.title for item in result.clues] == ["温控设备"]
    assert result.conclusion == []


def test_narrow_generic_terms_do_not_become_relevance_passes() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(query, [_hit("液冷服务器", 0.3)])
        if calls == 2:
            return _response(
                query,
                [
                    _hit(
                        "AI服务器供应链公告",
                        0.9,
                        hardness="hard",
                        excerpt="AI服务器供应链公告披露订单增长",
                    )
                ],
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert result.conclusion == []
    assert [item.hit.title for item in result.discarded] == ["AI服务器供应链公告"]


def test_hybrid_can_use_trusted_subject_alias_but_not_unrelated_hard_hit() -> None:
    calls: list[str] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append(mode)
        if mode == "hybrid":
            return _response(
                query,
                [
                    _hit(
                        "AHCF光纤公告",
                        0.95,
                        hardness="hard",
                        excerpt="AHCF optical fiber product announcement",
                    ),
                    _hit(
                        "hcfoo optical fiber update",
                        0.94,
                        hardness="hard",
                        excerpt="hcfoo optical fiber product update",
                    ),
                    _hit(
                        "HCF Healthcare Fund",
                        0.9,
                        hardness="hard",
                        excerpt="HCF Healthcare Fund portfolio update",
                    ),
                    _hit(
                        "HCF optical fiber progress",
                        0.7,
                        hardness="hard",
                        excerpt="HCF optical fiber commercialization progress",
                    ),
                    _hit(
                        "半导体设备公告",
                        0.9,
                        hardness="hard",
                        excerpt="半导体设备订单增长",
                    ),
                ],
                freshness="fresh",
                dense_initializations=1,
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "空芯光纤怎么看",
        anchor=None,
        subject="空芯光纤",
        retrieve=retrieve,
    )

    assert calls == ["bm25", "bm25", "bm25", "hybrid"]
    assert [item.hit.title for item in result.conclusion] == [
        "HCF optical fiber progress"
    ]
    assert [item.hit.title for item in result.discarded] == [
        "AHCF光纤公告",
        "hcfoo optical fiber update",
        "HCF Healthcare Fund",
        "半导体设备公告",
    ]


def test_long_hollow_core_fiber_alias_remains_bidirectional() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        if mode == "hybrid":
            return _response(
                query,
                [
                    _hit(
                        "Hollow core fiber capacity",
                        0.6,
                        hardness="hard",
                        excerpt="Hollow core fiber capacity expansion",
                    )
                ],
                freshness="fresh",
                dense_initializations=1,
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "空芯光纤怎么看",
        anchor=None,
        subject="空芯光纤",
        retrieve=retrieve,
    )

    assert [item.hit.title for item in result.conclusion] == [
        "Hollow core fiber capacity"
    ]


def test_bare_hcf_subject_does_not_expand_back_to_canonical_aliases() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        if mode == "hybrid":
            return _response(
                query,
                [
                    _hit(
                        "空芯光纤产业进展",
                        0.8,
                        hardness="hard",
                        excerpt="空芯光纤产能扩张",
                    )
                ],
                freshness="fresh",
                dense_initializations=1,
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "HCF怎么看",
        anchor=None,
        subject="HCF",
        retrieve=retrieve,
    )

    assert result.conclusion == []
    assert [item.hit.title for item in result.discarded] == ["空芯光纤产业进展"]


def test_relevant_soft_hit_is_clue_and_hard_hit_is_conclusion() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [
                    _hit("液冷需求", 0.012),
                    _hit("液冷公告", 0.01, hardness="hard"),
                ],
            )
        return _response(query, [])

    result = retrieve_closed_loop(
        "英维克怎么看",
        anchor=EntityAnchor(
            entity="英维克",
            ticker="002837.SZ",
            concepts=("液冷",),
        ),
        subject="ignored",
        retrieve=retrieve,
    )

    assert [item.hit.title for item in result.clues] == ["液冷需求"]
    assert [item.hit.title for item in result.conclusion] == ["液冷公告"]
    assert result.attempts[0].query == "英维克 002837.SZ"
    assert calls == 3
    assert result.dense_initializations == 0


def test_relevant_counter_hit_is_kept_as_counter_clue() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        if "风险 证伪" in query:
            return _response(query, [_hit("液冷需求不及预期", 0.12)])
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert [item.hit.title for item in result.counter_clues] == ["液冷需求不及预期"]
    assert [item.hit.title for item in result.clues] == ["液冷需求不及预期"]


def test_inspector_keeps_attempt_telemetry_and_adds_mode_timeout() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    first = result.inspector_dict()["attempts"][0]
    assert first == {
        "aperture": "narrow",
        "query": "液冷",
        "mode": "bm25",
        "timeout_seconds": 10,
        "status": "empty",
        "hit_count": 0,
    }


def test_attempt_uses_adapter_reported_timeout_after_callback_cap() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        assert timeout == 10.0
        return _response(
            query,
            [],
            timeout_seconds=3.0,
        )

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert all(attempt.timeout_seconds == 3.0 for attempt in result.attempts)


def test_attempt_falls_back_to_requested_timeout_when_adapter_does_not_report() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        return WikiRagResult(
            ok=False,
            telemetry=RetrievalTelemetry(
                status="empty",
                index_freshness="",
            ),
        )

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert all(attempt.timeout_seconds == 10.0 for attempt in result.attempts)


def test_public_telemetry_prefers_contributing_snapshot_over_later_empty() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [
                    _hit(
                        "液冷量产公告",
                        0.9,
                        hardness="hard",
                        revision="rev-contributor",
                    )
                ],
                revision="rev-contributor",
                latency_ms=5,
            )
        return _response(
            query,
            [],
            status="empty",
            freshness="",
            revision="rev-empty",
            latency_ms=2,
        )

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert [item.hit.title for item in result.conclusion] == ["液冷量产公告"]
    assert result.telemetry is not None
    assert result.telemetry.status == "ok"
    assert result.telemetry.hit_count == 1
    assert result.telemetry.index_freshness == "fresh"
    assert result.telemetry.index_source_revision == "rev-contributor"
    assert result.telemetry.latency_ms == 9
    assert (
        result.conclusion[0].hit.index_source_revision
        == result.telemetry.index_source_revision
    )


def test_soft_clue_does_not_hide_terminal_hybrid_error() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(query, [_hit("液冷需求线索", 0.4)])
        if mode == "hybrid":
            return _response(
                query,
                [],
                status="error",
                warning="dense unavailable",
                dense_initializations=1,
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert [item.hit.title for item in result.clues] == ["液冷需求线索"]
    assert result.telemetry is not None
    assert result.telemetry.status == "error"


def test_soft_clue_only_success_is_published_as_empty_not_ok() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if "风险 证伪" in query:
            return _response(query, [], status="empty", freshness="")
        return _response(
            query,
            [_hit(f"液冷软线索{calls}", 0.3)],
            dense_initializations=1 if mode == "hybrid" else 0,
        )

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert result.conclusion == []
    assert result.counter_clues == []
    assert result.clues
    assert result.telemetry is not None
    assert result.telemetry.status == "empty"
    assert result.telemetry.hit_count == 0
    assert result.telemetry.neighbor_hits == 0
    assert result.telemetry.score_max is None
    assert result.telemetry.score_min is None
    assert result.telemetry.score_mean is None
    assert result.telemetry.degraded
    assert "all retrieved hits rejected" in result.telemetry.warning
    assert any("all retrieved hits rejected" in warning for warning in result.warnings)


def test_snapshot_conflict_discards_later_broad_output() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [_hit("液冷 rev1 公告", 0.9, hardness="hard", revision="rev-1")],
                revision="rev-1",
            )
        if calls == 2:
            return _response(
                query,
                [_hit("液冷 rev2 公告", 0.8, hardness="hard", revision="rev-2")],
                revision="rev-2",
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert [item.hit.title for item in result.conclusion] == ["液冷 rev1 公告"]
    assert [item.hit.title for item in result.discarded] == ["液冷 rev2 公告"]
    assert any("snapshot conflict" in warning for warning in result.warnings)
    assert result.telemetry is not None
    assert result.telemetry.hit_count == 1
    assert result.telemetry.index_source_revision == "rev-1"


def test_same_snapshot_outputs_aggregate_across_responses() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [_hit("液冷狭口公告", 0.9, hardness="hard", revision="rev-1")],
                revision="rev-1",
            )
        if calls == 2:
            return _response(
                query,
                [_hit("液冷广口公告", 0.7, hardness="hard", revision="rev-1")],
                revision="rev-1",
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert len(result.conclusion) == 2
    assert result.telemetry is not None
    assert result.telemetry.hit_count == 2
    assert result.telemetry.score_max == 0.9
    assert result.telemetry.score_min == 0.7
    assert result.telemetry.score_mean == 0.8


def test_counter_snapshot_conflict_is_removed_from_both_output_buckets() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [_hit("液冷 rev1 公告", 0.9, hardness="hard", revision="rev-1")],
                revision="rev-1",
            )
        if calls == 3:
            return _response(
                query,
                [_hit("液冷 rev2 风险", 0.6, revision="rev-2")],
                revision="rev-2",
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert result.counter_clues == []
    assert all(item.hit.title != "液冷 rev2 风险" for item in result.clues)
    assert [item.hit.title for item in result.discarded] == ["液冷 rev2 风险"]


def test_same_identity_snapshot_conflict_is_checked_before_deduplication() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [
                    _hit(
                        "液冷共享 chunk",
                        0.9,
                        hardness="hard",
                        revision="rev-1",
                    )
                ],
                revision="rev-1",
            )
        if calls == 3:
            return _response(
                query,
                [_hit("液冷共享 chunk", 0.6, revision="rev-2")],
                revision="rev-2",
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert [item.hit.title for item in result.conclusion] == ["液冷共享 chunk"]
    assert result.counter_clues == []
    assert all(item.aperture != "counter" for item in result.clues)
    assert [item.aperture for item in result.discarded] == ["counter"]
    assert any("snapshot conflict" in warning for warning in result.warnings)


def test_same_snapshot_same_identity_is_deduplicated_after_validation() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                query,
                [
                    _hit(
                        "液冷共享 chunk",
                        0.9,
                        hardness="hard",
                        revision="rev-1",
                    )
                ],
                revision="rev-1",
            )
        if calls == 3:
            return _response(
                query,
                [_hit("液冷共享 chunk", 0.6, revision="rev-1")],
                revision="rev-1",
            )
        return _response(query, [], status="empty", freshness="")

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
        semantic_min_seconds=100,
    )

    assert len(result.conclusion) == 1
    assert result.counter_clues == []
    assert all(item.aperture != "counter" for item in result.clues)
    assert result.telemetry is not None
    assert result.telemetry.hit_count == 1
    assert not any("snapshot conflict" in warning for warning in result.warnings)


def test_telemetry_tracks_last_attempt_including_hybrid_error() -> None:
    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        if mode == "hybrid":
            return _response(
                query,
                [],
                status="error",
                freshness="fresh",
                warning="dense unavailable",
                dense_initializations=2,
                timeout_seconds=3.0,
                latency_ms=7,
            )
        return _response(query, [], freshness="fresh", latency_ms=2)

    result = retrieve_closed_loop(
        "液冷怎么看",
        anchor=None,
        subject="液冷",
        retrieve=retrieve,
    )

    assert result.telemetry is not None
    assert result.telemetry.status == "error"
    assert result.telemetry.latency_ms == 13
    assert result.telemetry.dense_initializations == 2
    assert result.dense_initializations == 2
    assert result.attempts[-1].mode == "hybrid"
    assert result.attempts[-1].status == "error"
    assert result.attempts[-1].timeout_seconds == 3.0
