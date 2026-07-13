from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.execution_budget import ExecutionBudget
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult

RetrievalAperture: TypeAlias = Literal["narrow", "broad", "counter"]
RetrievalMode: TypeAlias = Literal["bm25", "hybrid"]
Retrieve: TypeAlias = Callable[[str, RetrievalMode, float], WikiRagResult]

_TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9.+-]{2,20}")
_GENERIC_TERMS = {
    "公司",
    "行业",
    "市场",
    "相关",
    "研究",
    "分析",
    "情况",
    "目前",
    "未来",
    "影响",
    "数据",
    "逻辑",
}


@dataclass(frozen=True)
class RetrievalAttempt:
    aperture: RetrievalAperture
    query: str
    mode: RetrievalMode
    timeout_seconds: float
    status: str
    hit_count: int


@dataclass(frozen=True)
class BucketedHit:
    aperture: RetrievalAperture
    hit: WikiHit


@dataclass
class ClosedLoopRetrievalResult:
    conclusion: list[BucketedHit] = field(default_factory=list)
    clues: list[BucketedHit] = field(default_factory=list)
    discarded: list[BucketedHit] = field(default_factory=list)
    counter_clues: list[BucketedHit] = field(default_factory=list)
    attempts: list[RetrievalAttempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    telemetry: RetrievalTelemetry | None = None
    dense_initializations: int = 0

    def inspector_dict(self) -> dict[str, object]:
        return {
            "attempts": [
                {
                    "aperture": attempt.aperture,
                    "query": attempt.query,
                    "mode": attempt.mode,
                    "timeout_seconds": attempt.timeout_seconds,
                    "status": attempt.status,
                    "hit_count": attempt.hit_count,
                }
                for attempt in self.attempts
            ],
            "buckets": {
                "conclusion": len(self.conclusion),
                "clue": len(self.clues),
                "discarded": len(self.discarded),
                "counter_clue": len(self.counter_clues),
            },
            "warnings": list(self.warnings),
            "dense_initializations": self.dense_initializations,
        }


def retrieve_closed_loop(
    query: str,
    *,
    anchor: EntityAnchor | None,
    retrieve: Retrieve,
    subject: str | None = None,
    budget: ExecutionBudget | None = None,
    semantic_min_seconds: float = 15,
    now: Callable[[], float] = time.monotonic,
) -> ClosedLoopRetrievalResult:
    result = ClosedLoopRetrievalResult()
    explicit_subject = anchor.entity if anchor is not None else (subject or "").strip()
    if not explicit_subject:
        result.warnings.append("no explicit subject; closed-loop retrieval skipped")
        return result

    narrow_query = _narrow_queries(explicit_subject, anchor)[0]
    narrow_hits, stop = _run_one(
        "narrow", narrow_query, "bm25", retrieve, result, budget=budget, now=now
    )
    broad_hits: list[WikiHit] = []
    counter_hits: list[WikiHit] = []
    if not stop:
        broad_query = _broad_queries(explicit_subject, anchor, narrow_hits)[0]
        broad_hits, stop = _run_one(
            "broad", broad_query, "bm25", retrieve, result, budget=budget, now=now
        )
    if not stop:
        counter_query = _counter_queries(explicit_subject, anchor, narrow_hits)[0]
        counter_hits, stop = _run_one(
            "counter", counter_query, "bm25", retrieve, result, budget=budget, now=now
        )

    relevance_terms = _relevance_terms(anchor, (), subject=explicit_subject)
    broad_relevance_terms = _relevance_terms(
        anchor, narrow_hits, subject=explicit_subject
    )
    bm25_entries = (
        *(("narrow", hit) for hit in narrow_hits),
        *(("broad", hit) for hit in broad_hits),
        *(("counter", hit) for hit in counter_hits),
    )
    _bucket_hits(
        bm25_entries,
        result,
        relevance_terms=relevance_terms,
        broad_relevance_terms=broad_relevance_terms,
    )

    remaining = (
        float("inf")
        if budget is None
        else budget.remaining_seconds(now=now())
    )
    should_consider_semantic = not stop and not result.conclusion
    if should_consider_semantic and remaining < semantic_min_seconds:
        result.warnings.append(
            "semantic retrieval skipped: insufficient budget "
            f"({remaining:.1f}s remaining, {semantic_min_seconds:.1f}s required)"
        )
    if should_consider_semantic and remaining >= semantic_min_seconds:
        hybrid_hits, _ = _run_one(
            "narrow",
            narrow_query,
            "hybrid",
            retrieve,
            result,
            budget=budget,
            now=now,
        )
        if result.attempts[-1].timeout_seconds > 0:
            result.dense_initializations = 1
        bm25_identities = {
            _hit_identity(hit)
            for hit in (*narrow_hits, *broad_hits, *counter_hits)
        }
        novel_hybrid_hits = [
            hit for hit in hybrid_hits if _hit_identity(hit) not in bm25_identities
        ]
        _bucket_hits(
            tuple(("narrow", hit) for hit in novel_hybrid_hits),
            result,
            relevance_terms=relevance_terms,
            broad_relevance_terms=broad_relevance_terms,
        )

    for aperture in ("narrow", "broad", "counter"):
        attempts = [item for item in result.attempts if item.aperture == aperture]
        if attempts and all(item.hit_count == 0 for item in attempts):
            result.warnings.append(
                f"{aperture} retrieval empty after {len(attempts)} attempts"
            )
    return result


def _run_one(
    aperture: RetrievalAperture,
    query: str,
    mode: RetrievalMode,
    retrieve: Retrieve,
    result: ClosedLoopRetrievalResult,
    *,
    budget: ExecutionBudget | None,
    now: Callable[[], float],
) -> tuple[list[WikiHit], bool]:
    timeout = (
        10.0
        if budget is None
        else budget.child_timeout(10, reserve=5, now=now())
    )
    if timeout <= 0:
        result.attempts.append(
            RetrievalAttempt(
                aperture=aperture,
                query=query,
                mode=mode,
                timeout_seconds=timeout,
                status="timeout",
                hit_count=0,
            )
        )
        result.warnings.append(
            f"{aperture} {mode} retrieval not executed: budget exhausted"
        )
        return [], True

    response = retrieve(query, mode, timeout)
    result.telemetry = response.telemetry
    result.attempts.append(
        RetrievalAttempt(
            aperture=aperture,
            query=query,
            mode=mode,
            timeout_seconds=timeout,
            status=response.telemetry.status,
            hit_count=len(response.hits),
        )
    )
    if response.warning and response.warning not in result.warnings:
        result.warnings.append(response.warning)

    status = response.telemetry.status.casefold()
    freshness = response.telemetry.index_freshness.casefold()
    untrusted_freshness = freshness != "fresh"
    stop = status in {"skipped", "error", "timeout"} or untrusted_freshness
    if untrusted_freshness:
        freshness_label = freshness or "missing"
        warning = f"untrusted index freshness: {freshness_label}"
        if warning not in result.warnings:
            result.warnings.append(warning)
    if stop:
        return [], True
    if response.ok and response.hits:
        return response.hits, False
    return [], False


def _narrow_queries(subject: str, anchor: EntityAnchor | None) -> tuple[str, ...]:
    if anchor is None:
        return (
            subject,
            f"{subject} 实体 代码",
            f"{subject} 公司 题材",
        )
    raw_code = anchor.ticker.split(".", 1)[0]
    return (
        " ".join(part for part in (anchor.entity, anchor.ticker) if part),
        " ".join(part for part in (anchor.entity, raw_code) if part),
        anchor.graph_query,
    )


def _broad_queries(
    subject: str,
    anchor: EntityAnchor | None,
    narrow_hits: Sequence[WikiHit],
) -> tuple[str, ...]:
    subject = anchor.entity if anchor is not None else subject
    terms = list(anchor.concepts if anchor is not None else ())
    terms.extend(_extract_terms(narrow_hits))
    context = " ".join(dict.fromkeys(terms[:6]))
    return (
        f"{subject} {context} 上下游 同业".strip(),
        f"{subject} {context} 产业链 替代表达".strip(),
        f"{subject} {context} 宏观 需求 竞争格局".strip(),
    )


def _counter_queries(
    subject: str,
    anchor: EntityAnchor | None,
    narrow_hits: Sequence[WikiHit],
) -> tuple[str, ...]:
    subject = anchor.entity if anchor is not None else subject
    terms = " ".join(_extract_terms(narrow_hits)[:4])
    return (
        f"{subject} {terms} 风险 证伪 不及预期".strip(),
        f"{subject} {terms} 替代 竞争 受损".strip(),
        f"{subject} {terms} 反方 下滑 失败".strip(),
    )


def _extract_terms(hits: Sequence[WikiHit]) -> list[str]:
    terms: list[str] = []
    for hit in hits[:5]:
        for term in _TERM_RE.findall(f"{hit.title} {hit.excerpt}"):
            normalized = term.strip()
            if normalized in _GENERIC_TERMS or normalized in terms:
                continue
            terms.append(normalized)
            if len(terms) == 8:
                return terms
    return terms


def _relevance_terms(
    anchor: EntityAnchor | None,
    narrow_hits: Sequence[WikiHit],
    *,
    subject: str = "",
) -> tuple[str, ...]:
    terms: list[str] = [subject]
    if anchor is not None:
        terms.extend((anchor.entity, anchor.ticker, *anchor.concepts))
    base_terms = tuple(
        dict.fromkeys(
            term.strip().casefold()
            for term in terms
            if len(term.strip()) >= 2 and term.strip() not in _GENERIC_TERMS
        )
    )
    anchored_narrow_hits = [
        hit
        for hit in narrow_hits
        if hit.score > 0
        and any(
            term in f"{hit.title} {hit.excerpt}".casefold()
            for term in base_terms
        )
    ]
    expanded_terms = (*base_terms, *_extract_terms(anchored_narrow_hits))
    return tuple(
        dict.fromkeys(
            term.strip().casefold()
            for term in expanded_terms
            if len(term.strip()) >= 2 and term.strip() not in _GENERIC_TERMS
        )
    )


def _bucket_hits(
    entries: Sequence[tuple[str, WikiHit]],
    result: ClosedLoopRetrievalResult,
    *,
    relevance_terms: Sequence[str],
    broad_relevance_terms: Sequence[str],
) -> None:
    seen: set[tuple[str, str, str]] = set()
    for raw_aperture, hit in entries:
        aperture = raw_aperture
        if aperture not in {"narrow", "broad", "counter"}:
            continue
        typed_aperture: RetrievalAperture = aperture
        key = (typed_aperture, hit.file_path, hit.best_chunk_id)
        if key in seen:
            continue
        seen.add(key)
        item = BucketedHit(typed_aperture, hit)
        searchable = f"{hit.title} {hit.excerpt}".casefold()
        aperture_terms = (
            broad_relevance_terms
            if typed_aperture == "broad"
            else relevance_terms
        )
        direct_overlap = any(term in searchable for term in aperture_terms)
        if hit.score <= 0 or not direct_overlap:
            result.discarded.append(item)
            continue
        if typed_aperture == "counter":
            result.counter_clues.append(item)
            result.clues.append(item)
            continue
        hardness = hit.fact_hardness.casefold()
        layer = hit.evidence_layer.casefold()
        hard_source = hardness in {"hard", "verified", "canonical"} or layer in {
            "l3",
            "l4",
            "canonical",
        }
        if hard_source:
            result.conclusion.append(item)
        else:
            result.clues.append(item)


def _hit_identity(hit: WikiHit) -> tuple[str, str]:
    return hit.file_path, hit.best_chunk_id
