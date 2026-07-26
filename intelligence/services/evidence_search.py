"""Deep closed-loop evidence retrieval for model-owned finance research.

The module keeps the existing narrow/broad/counter retrieval discipline behind
one small interface.  It returns model-safe evidence and a separate inspector
projection; future or semantically rejected hits never enter the observation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from intelligence.services import (
    agent_research,
    closed_loop_retrieval,
    evidence_judge,
)
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.kb_rag import WikiHit, WikiRagResult
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)


SemanticJudge = Callable[
    [str, Sequence[tuple[str, str]], float],
    tuple[set[int], str] | None,
]


@dataclass(frozen=True)
class EvidenceSearchCoverage:
    conclusion_count: int
    clue_count: int
    counter_count: int
    discarded_count: int
    apertures_attempted: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSearchResult:
    evidence: tuple[agent_research.AgentEvidence, ...]
    observation: str
    coverage: EvidenceSearchCoverage
    gaps: tuple[str, ...]
    attempts: tuple[closed_loop_retrieval.RetrievalAttempt, ...]
    warnings: tuple[str, ...]
    diagnostics: tuple[str, ...]
    trace: ProviderTrace


def default_semantic_judge(
    query: str,
    candidates: Sequence[tuple[str, str]],
    timeout: float,
) -> tuple[set[int], str] | None:
    """Use the existing relevance judge when its provider policy enables it."""

    if not evidence_judge.should_judge():
        return None
    return evidence_judge.judge_relevance(
        query,
        candidates,
        timeout=timeout,
    )


class EvidenceSearch:
    """Run one bounded compound search and return an auditable projection."""

    def __init__(
        self,
        retrieve: Callable[[str], WikiRagResult],
        *,
        semantic_judge: SemanticJudge | None = None,
        max_evidence: int = 12,
    ) -> None:
        if max_evidence < 1:
            raise ValueError("max_evidence must be positive")
        self._retrieve = retrieve
        self._semantic_judge = semantic_judge
        self._max_evidence = max_evidence

    def search(
        self,
        *,
        query: str,
        anchor: EntityAnchor | None,
        information_cutoff: InformationCutoff,
        deadline: ResearchDeadline,
    ) -> EvidenceSearchResult:
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            raise ValueError("evidence search query must be non-empty")
        total_seconds = deadline.stage_timeout(
            closed_loop_retrieval.MAX_TOTAL_SECONDS
        )
        if total_seconds <= 0.001:
            return self._empty_deadline_result(
                cleaned_query,
                information_cutoff,
            )
        loop = closed_loop_retrieval.retrieve_closed_loop(
            cleaned_query,
            anchor=anchor,
            retrieve=self._retrieve,
            total_seconds=total_seconds,
            information_cutoff=information_cutoff,
        )
        self._apply_semantic_judge(
            cleaned_query,
            loop,
            deadline=deadline,
        )
        entries = _eligible_entries(loop)
        evidence, stances = _project_evidence(
            entries,
            query=cleaned_query,
            max_evidence=self._max_evidence,
        )
        observation = "；".join(
            f"[{stance}]{item.title}：{item.detail}"
            for item, stance in zip(evidence, stances, strict=True)
        )
        gaps = (
            ()
            if evidence
            else (
                f"尚未找到与“{cleaned_query}”直接相关的可用证据",
            )
        )
        served_date = _latest_date(loop)
        coverage = EvidenceSearchCoverage(
            conclusion_count=_unique_bucket_count(loop.conclusion),
            clue_count=_unique_bucket_count(loop.clues),
            counter_count=_unique_bucket_count(loop.counter_clues),
            discarded_count=_unique_bucket_count(loop.discarded),
            apertures_attempted=tuple(
                dict.fromkeys(item.aperture for item in loop.attempts)
            ),
        )
        trace = ProviderTrace(
            provider="kb_hybrid_closed_loop",
            capability="evidence_search",
            status="success" if evidence else "empty",
            detail=_trace_detail(loop, coverage),
            source_trade_date=served_date,
            result_count=len(evidence),
            requested_date=information_cutoff.as_of_date.isoformat(),
            served_date=served_date,
        )
        return EvidenceSearchResult(
            evidence=evidence,
            observation=observation,
            coverage=coverage,
            gaps=gaps,
            attempts=tuple(loop.attempts),
            warnings=tuple(loop.warnings),
            diagnostics=tuple(loop.diagnostics),
            trace=trace,
        )

    def _apply_semantic_judge(
        self,
        query: str,
        loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
        *,
        deadline: ResearchDeadline,
    ) -> None:
        if self._semantic_judge is None:
            return
        buckets = [*loop.conclusion, *loop.counter_clues]
        if not buckets:
            return
        timeout = deadline.stage_timeout(evidence_judge.DEFAULT_TIMEOUT)
        if timeout <= 0.001:
            return
        candidates = tuple(
            (item.hit.title, item.hit.excerpt) for item in buckets
        )
        try:
            verdict = self._semantic_judge(query, candidates, timeout)
        except Exception as exc:
            loop.diagnostics.append(
                f"semantic_judge_unavailable:{type(exc).__name__}"
            )
            return
        if verdict is None:
            return
        keep_indexes, reason = verdict
        dropped = [
            item for index, item in enumerate(buckets) if index not in keep_indexes
        ]
        if not dropped:
            return
        dropped_keys = {_bucket_key(item) for item in dropped}
        loop.conclusion[:] = [
            item for item in loop.conclusion if _bucket_key(item) not in dropped_keys
        ]
        loop.counter_clues[:] = [
            item
            for item in loop.counter_clues
            if _bucket_key(item) not in dropped_keys
        ]
        loop.clues[:] = [
            item for item in loop.clues if _bucket_key(item) not in dropped_keys
        ]
        existing_discarded = {_bucket_key(item) for item in loop.discarded}
        loop.discarded.extend(
            item for item in dropped if _bucket_key(item) not in existing_discarded
        )
        loop.diagnostics.append(
            f"semantic_judge_discarded={len(dropped)}"
            + (f"; reason={reason}" if reason else "")
        )

    @staticmethod
    def _empty_deadline_result(
        query: str,
        cutoff: InformationCutoff,
    ) -> EvidenceSearchResult:
        gap = f"检索时间预算已耗尽，尚未搜索“{query}”"
        return EvidenceSearchResult(
            evidence=(),
            observation="",
            coverage=EvidenceSearchCoverage(0, 0, 0, 0, ()),
            gaps=(gap,),
            attempts=(),
            warnings=(gap,),
            diagnostics=(),
            trace=ProviderTrace(
                provider="kb_hybrid_closed_loop",
                capability="evidence_search",
                status="empty",
                detail="deadline_exhausted",
                result_count=0,
                requested_date=cutoff.as_of_date.isoformat(),
            ),
        )


def _eligible_entries(
    loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
) -> tuple[tuple[str, closed_loop_retrieval.BucketedHit], ...]:
    entries: list[tuple[str, closed_loop_retrieval.BucketedHit]] = []
    seen: set[tuple[str, str]] = set()
    for stance, items in (
        ("支持", loop.conclusion),
        ("反方", loop.counter_clues),
    ):
        for item in items:
            key = (item.hit.file_path, item.hit.best_chunk_id)
            if key in seen:
                continue
            seen.add(key)
            entries.append((stance, item))
    return tuple(entries)


def _project_evidence(
    entries: tuple[tuple[str, closed_loop_retrieval.BucketedHit], ...],
    *,
    query: str,
    max_evidence: int,
) -> tuple[tuple[agent_research.AgentEvidence, ...], tuple[str, ...]]:
    evidence: list[agent_research.AgentEvidence] = []
    stances: list[str] = []
    for stance, item in entries[:max_evidence]:
        hit = item.hit
        detail = str(
            hit.llm_evidence or hit.display_excerpt or hit.excerpt or ""
        ).strip()
        source_date = closed_loop_retrieval.wiki_hit_source_date(hit)
        draft = agent_research.AgentEvidence(
            tool="evidence_search",
            title=hit.title.strip() or query,
            detail=detail,
            source=hit.file_path,
            internal_locator=(
                f"{hit.file_path}#{hit.best_chunk_id}"
                if hit.best_chunk_id
                else hit.file_path
            ),
            source_date=source_date.isoformat() if source_date is not None else None,
            evidence_tier=hit.evidence_layer or hit.fact_hardness,
            independent_key=hit.file_path,
            freshness=hit.index_freshness or "unknown",
            content_hash=hit.content_hash,
        )
        evidence.append(
            draft
            if draft.content_hash
            else replace(
                draft,
                content_hash=agent_research.evidence_content_hash(draft),
            )
        )
        stances.append(stance)
    return tuple(evidence), tuple(stances)


def _bucket_key(
    item: closed_loop_retrieval.BucketedHit,
) -> tuple[str, str, str]:
    return item.aperture, item.hit.file_path, item.hit.best_chunk_id


def _unique_bucket_count(
    items: Sequence[closed_loop_retrieval.BucketedHit],
) -> int:
    return len({(item.hit.file_path, item.hit.best_chunk_id) for item in items})


def _all_bucket_hits(
    loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
) -> tuple[WikiHit, ...]:
    seen: set[tuple[str, str]] = set()
    hits: list[WikiHit] = []
    for bucket in (
        loop.conclusion,
        loop.clues,
        loop.counter_clues,
        loop.discarded,
    ):
        for item in bucket:
            key = (item.hit.file_path, item.hit.best_chunk_id)
            if key in seen:
                continue
            seen.add(key)
            hits.append(item.hit)
    return tuple(hits)


def _latest_date(
    loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
) -> str | None:
    return closed_loop_retrieval.latest_served_date(
        _all_bucket_hits(loop),
        date_getter=closed_loop_retrieval.wiki_hit_source_date,
    )


def _trace_detail(
    loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
    coverage: EvidenceSearchCoverage,
) -> str:
    attempts = ",".join(
        f"{item.aperture}:{item.status}:{item.hit_count}"
        for item in loop.attempts
    )
    return (
        f"attempts={attempts or 'none'}; "
        f"conclusion={coverage.conclusion_count}; "
        f"counter={coverage.counter_count}; "
        f"discarded={coverage.discarded_count}"
    )


__all__ = [
    "EvidenceSearch",
    "EvidenceSearchCoverage",
    "EvidenceSearchResult",
    "SemanticJudge",
    "default_semantic_judge",
]
