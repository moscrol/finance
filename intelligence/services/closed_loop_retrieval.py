from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult

RetrievalAperture: TypeAlias = Literal["narrow", "broad", "counter"]
Retrieve: TypeAlias = Callable[[str], WikiRagResult]

MAX_EMPTY_ATTEMPTS = 3
MAX_TOTAL_SECONDS = 90.0
# 中文+数字混合词（科创50/沪深300/中证1000）优先整词捕获，避免被拆出
# 「科创」这类子串后误锚到无关实体（如 中科创达）。
_TERM_RE = re.compile(
    r"[\u4e00-\u9fff]{2,8}\d{1,6}[A-Za-z]{0,4}"
    r"|[\u4e00-\u9fff]{2,8}"
    r"|[A-Za-z][A-Za-z0-9.+-]{2,20}"
)
_QUESTION_WORDS_RE = re.compile(
    r"最近|怎么样|怎么看|是什么|为什么|为何|分析|输出|请|一下|能否|是否"
)
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

    def inspector_dict(self) -> dict[str, object]:
        return {
            "attempts": [
                {
                    "aperture": attempt.aperture,
                    "query": attempt.query,
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
        }


def retrieve_closed_loop(
    query: str,
    *,
    anchor: EntityAnchor | None,
    retrieve: Retrieve,
) -> ClosedLoopRetrievalResult:
    result = ClosedLoopRetrievalResult()
    deadline = time.monotonic() + MAX_TOTAL_SECONDS
    query_terms = _relevance_terms(query, anchor, ())
    narrow_hits = _run_aperture(
        "narrow",
        _narrow_queries(query, anchor),
        retrieve,
        result,
        deadline,
    )
    relevant_narrow_hits = tuple(
        hit for hit in narrow_hits if _hit_overlaps_terms(hit, query_terms)
    )
    broad_hits = _run_aperture(
        "broad",
        _broad_queries(query, anchor, relevant_narrow_hits),
        retrieve,
        result,
        deadline,
    )
    counter_hits = _run_aperture(
        "counter",
        _counter_queries(query, anchor, relevant_narrow_hits),
        retrieve,
        result,
        deadline,
    )
    _bucket_hits(
        (
            *(("narrow", hit) for hit in narrow_hits),
            *(("broad", hit) for hit in broad_hits),
            *(("counter", hit) for hit in counter_hits),
        ),
        result,
        relevance_terms=query_terms,
        broad_relevance_terms=_relevance_terms(
            query,
            anchor,
            relevant_narrow_hits,
        ),
    )
    for aperture in ("narrow", "broad", "counter"):
        attempts = [item for item in result.attempts if item.aperture == aperture]
        if attempts and all(item.hit_count == 0 for item in attempts):
            result.warnings.append(
                f"{aperture} retrieval empty after {len(attempts)} attempts"
            )
    return result


def _run_aperture(
    aperture: RetrievalAperture,
    queries: Sequence[str],
    retrieve: Retrieve,
    result: ClosedLoopRetrievalResult,
    deadline: float,
) -> list[WikiHit]:
    for candidate in list(dict.fromkeys(q.strip() for q in queries if q.strip()))[
        :MAX_EMPTY_ATTEMPTS
    ]:
        if time.monotonic() >= deadline:
            break
        response = retrieve(candidate)
        if result.telemetry is None or response.hits:
            result.telemetry = response.telemetry
        result.attempts.append(
            RetrievalAttempt(
                aperture=aperture,
                query=candidate,
                status=response.telemetry.status,
                hit_count=len(response.hits),
            )
        )
        if response.warning:
            if response.warning not in result.warnings:
                result.warnings.append(response.warning)
        if response.ok and response.hits:
            return response.hits
        if response.telemetry.status == "timeout":
            break
    return []


def _narrow_queries(query: str, anchor: EntityAnchor | None) -> tuple[str, ...]:
    if anchor is None:
        return (
            query,
            f"{query} 实体 代码",
            f"{query} 公司 题材",
        )
    raw_code = anchor.ticker.split(".", 1)[0]
    return (
        " ".join(part for part in (anchor.entity, anchor.ticker) if part),
        " ".join(part for part in (anchor.entity, raw_code) if part),
        anchor.graph_query,
    )


def _broad_queries(
    query: str,
    anchor: EntityAnchor | None,
    narrow_hits: Sequence[WikiHit],
) -> tuple[str, ...]:
    subject = anchor.entity if anchor is not None else query
    terms = list(anchor.concepts if anchor is not None else ())
    terms.extend(_extract_terms(narrow_hits))
    context = " ".join(dict.fromkeys(terms[:6]))
    return (
        f"{subject} {context} 上下游 同业".strip(),
        f"{subject} {context} 产业链 替代表达".strip(),
        f"{subject} {context} 宏观 需求 竞争格局".strip(),
    )


def _counter_queries(
    query: str,
    anchor: EntityAnchor | None,
    narrow_hits: Sequence[WikiHit],
) -> tuple[str, ...]:
    subject = anchor.entity if anchor is not None else query
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
    query: str,
    anchor: EntityAnchor | None,
    narrow_hits: Sequence[WikiHit],
) -> tuple[str, ...]:
    stripped_query = _QUESTION_WORDS_RE.sub(" ", query)
    terms = _TERM_RE.findall(stripped_query)
    if anchor is not None:
        terms.extend((anchor.entity, anchor.ticker, *anchor.concepts))
    terms.extend(_extract_terms(narrow_hits))
    expanded: list[str] = []
    for raw_term in terms:
        term = raw_term.strip().casefold()
        if len(term) < 2 or term in _GENERIC_TERMS:
            continue
        expanded.append(term)
        if len(term) > 2 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
            expanded.extend(
                term[index : index + 2]
                for index in range(len(term) - 1)
                if term[index : index + 2] not in _GENERIC_TERMS
            )
    return tuple(dict.fromkeys(expanded))


def _hit_overlaps_terms(hit: WikiHit, terms: Sequence[str]) -> bool:
    searchable = f"{hit.title} {hit.excerpt}".casefold()
    return bool(terms) and any(term in searchable for term in terms)


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
        aperture_terms = (
            broad_relevance_terms
            if typed_aperture == "broad"
            else relevance_terms
        )
        direct_overlap = _hit_overlaps_terms(hit, aperture_terms)
        if hit.score <= 0 or not direct_overlap:
            result.discarded.append(item)
            continue
        if typed_aperture == "counter":
            result.counter_clues.append(item)
            result.clues.append(item)
        elif direct_overlap:
            result.conclusion.append(item)
