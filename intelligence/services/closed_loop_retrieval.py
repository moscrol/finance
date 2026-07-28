from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, TypeAlias, TypeVar

from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult
from intelligence.services.research_contract import InformationCutoff

RetrievalAperture: TypeAlias = Literal["narrow", "broad", "counter"]
RetrievalExpansionPolicy: TypeAlias = Literal["anchor_or_hits", "query_only"]
Retrieve: TypeAlias = Callable[[str], WikiRagResult]
T = TypeVar("T")

MAX_EMPTY_ATTEMPTS = 3
MAX_TOTAL_SECONDS = 90.0
MIN_ATTEMPT_RESERVE_SECONDS = 1.0
ATTEMPT_COST_SAFETY_MULTIPLIER = 1.25
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
_ISO_DATE_RE = re.compile(r"(?<!\d)(20\d{2}-\d{1,2}-\d{1,2})(?!\d)")
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
    executed: bool = True
    requested_mode: str = ""
    effective_mode: str = ""
    fallback_reason: str = ""
    degraded: bool = False


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
    diagnostics: list[str] = field(default_factory=list)
    telemetry: RetrievalTelemetry | None = None

    def inspector_dict(self) -> dict[str, object]:
        return {
            "attempts": [
                {
                    "aperture": attempt.aperture,
                    "query": attempt.query,
                    "status": attempt.status,
                    "hit_count": attempt.hit_count,
                    "executed": attempt.executed,
                    "requested_mode": attempt.requested_mode,
                    "effective_mode": attempt.effective_mode,
                    "fallback_reason": attempt.fallback_reason,
                    "degraded": attempt.degraded,
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
            "diagnostics": list(self.diagnostics),
        }


def apply_semantic_filter(
    result: ClosedLoopRetrievalResult,
    *,
    keep_indexes: set[int],
    reason: str = "",
) -> ClosedLoopRetrievalResult:
    """Return a new bucket projection after semantic relevance adjudication."""

    candidates = [*result.conclusion, *result.counter_clues]
    dropped = [
        item for index, item in enumerate(candidates) if index not in keep_indexes
    ]
    if not dropped:
        return result
    dropped_keys = {_bucket_identity(item) for item in dropped}

    def kept(items: Sequence[BucketedHit]) -> list[BucketedHit]:
        return [item for item in items if _bucket_identity(item) not in dropped_keys]

    discarded = list(result.discarded)
    existing = {_bucket_identity(item) for item in discarded}
    discarded.extend(
        item for item in dropped if _bucket_identity(item) not in existing
    )
    diagnostics = [*result.diagnostics]
    diagnostics.append(
        f"semantic_judge_discarded={len(dropped)}"
        + (f"; reason={reason}" if reason else "")
    )
    return ClosedLoopRetrievalResult(
        conclusion=kept(result.conclusion),
        clues=kept(result.clues),
        discarded=discarded,
        counter_clues=kept(result.counter_clues),
        attempts=list(result.attempts),
        warnings=list(result.warnings),
        diagnostics=diagnostics,
        telemetry=result.telemetry,
    )


@dataclass
class _AttemptBudget:
    deadline: float
    observed_seconds: float | None = None

    def can_start(self) -> bool:
        remaining = max(0.0, self.deadline - time.monotonic())
        required = MIN_ATTEMPT_RESERVE_SECONDS
        if self.observed_seconds is not None:
            required = max(
                required,
                self.observed_seconds * ATTEMPT_COST_SAFETY_MULTIPLIER,
            )
        return remaining >= required

    def observe(self, elapsed_seconds: float) -> None:
        elapsed = max(0.0, elapsed_seconds)
        if self.observed_seconds is None:
            self.observed_seconds = elapsed
        else:
            self.observed_seconds = max(self.observed_seconds, elapsed)


def retrieve_closed_loop(
    query: str,
    *,
    anchor: EntityAnchor | None,
    retrieve: Retrieve,
    total_seconds: float | None = None,
    information_cutoff: InformationCutoff | None = None,
    expansion_policy: RetrievalExpansionPolicy = "anchor_or_hits",
) -> ClosedLoopRetrievalResult:
    """闭环检索。``total_seconds`` 由调用方传入 turn 级预算切片；
    与本模块自身的 MAX_TOTAL_SECONDS 取 min——闭环不得突破 turn 根截止时间。"""
    if expansion_policy not in {"anchor_or_hits", "query_only"}:
        raise ValueError(f"unknown retrieval expansion policy: {expansion_policy}")
    result = ClosedLoopRetrievalResult()
    budget = (
        min(MAX_TOTAL_SECONDS, max(0.0, float(total_seconds)))
        if total_seconds is not None
        else MAX_TOTAL_SECONDS
    )
    if budget <= 0:
        return result
    attempt_budget = _AttemptBudget(deadline=time.monotonic() + budget)
    query_terms = _relevance_terms(query, anchor, ())
    query_only = expansion_policy == "query_only" and anchor is None
    narrow_hits = _run_aperture(
        "narrow",
        (query,) if query_only else _narrow_queries(query, anchor),
        retrieve,
        result,
        attempt_budget,
        information_cutoff,
    )
    relevant_narrow_hits = tuple(
        hit for hit in narrow_hits if _hit_overlaps_terms(hit, query_terms)
    )
    expansion_hits = () if query_only else relevant_narrow_hits
    broad_hits = _run_aperture(
        "broad",
        (
            _query_only_broad_queries(query)
            if query_only
            else _broad_queries(query, anchor, relevant_narrow_hits)
        ),
        retrieve,
        result,
        attempt_budget,
        information_cutoff,
    )
    counter_hits = _run_aperture(
        "counter",
        (
            _query_only_counter_queries(query)
            if query_only
            else _counter_queries(query, anchor, relevant_narrow_hits)
        ),
        retrieve,
        result,
        attempt_budget,
        information_cutoff,
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
            expansion_hits,
        ),
    )
    for aperture in ("narrow", "broad", "counter"):
        attempts = [item for item in result.attempts if item.aperture == aperture]
        if (
            attempts
            and any(item.status != "budget_exhausted" for item in attempts)
            and all(item.hit_count == 0 for item in attempts)
        ):
            result.warnings.append(
                f"{aperture} retrieval empty after {len(attempts)} attempts"
            )
    return result


def _run_aperture(
    aperture: RetrievalAperture,
    queries: Sequence[str],
    retrieve: Retrieve,
    result: ClosedLoopRetrievalResult,
    budget: _AttemptBudget,
    information_cutoff: InformationCutoff | None,
) -> list[WikiHit]:
    for candidate in list(dict.fromkeys(q.strip() for q in queries if q.strip()))[
        :MAX_EMPTY_ATTEMPTS
    ]:
        if not budget.can_start():
            result.attempts.append(
                RetrievalAttempt(
                    aperture=aperture,
                    query=candidate,
                    status="budget_exhausted",
                    hit_count=0,
                    executed=False,
                )
            )
            warning = (
                f"{aperture} retrieval skipped: "
                "remaining budget below observed query cost"
            )
            if warning not in result.warnings:
                result.warnings.append(warning)
            break
        started = time.monotonic()
        response = retrieve(candidate)
        budget.observe(time.monotonic() - started)
        eligible_hits, future_hits = filter_future_dated(
            response.hits,
            information_cutoff=information_cutoff,
            date_getter=wiki_hit_source_date,
        )
        for hit in future_hits:
            result.discarded.append(BucketedHit(aperture, hit))
        if future_hits:
            warning = (
                f"{aperture} retrieval rejected {len(future_hits)} "
                "future_of_cutoff hit(s)"
            )
            if warning not in result.warnings:
                result.warnings.append(warning)
        if result.telemetry is None or response.hits:
            result.telemetry = response.telemetry
        result.attempts.append(
            RetrievalAttempt(
                aperture=aperture,
                query=candidate,
                status=(
                    "future_of_cutoff"
                    if future_hits and not eligible_hits
                    else response.telemetry.status
                ),
                hit_count=len(eligible_hits),
                requested_mode=response.telemetry.requested_mode,
                effective_mode=response.telemetry.effective_mode,
                fallback_reason=response.telemetry.fallback_reason,
                degraded=response.telemetry.degraded,
            )
        )
        if response.warning:
            if response.warning not in result.warnings:
                result.warnings.append(response.warning)
        if response.ok and eligible_hits:
            return eligible_hits
        if response.telemetry.status == "timeout":
            break
    return []


def parse_source_date(value: object) -> date | None:
    if type(value) is date:
        return value
    if not isinstance(value, str):
        return None
    match = _ISO_DATE_RE.search(value.strip())
    if match is None:
        return None
    try:
        year, month, day = (int(part) for part in match.group(1).split("-"))
        return date(year, month, day)
    except ValueError:
        return None


def wiki_hit_source_date(hit: WikiHit) -> date | None:
    explicit = parse_source_date(hit.source_date)
    if explicit is not None:
        return explicit
    # Content may discuss future forecast dates. Only source metadata or a
    # date-stamped path is safe to treat as the document's publication date.
    return parse_source_date(hit.file_path)


def filter_future_dated(
    items: Sequence[T],
    *,
    information_cutoff: InformationCutoff | None,
    date_getter: Callable[[T], object],
) -> tuple[list[T], list[T]]:
    if information_cutoff is None:
        return list(items), []
    eligible: list[T] = []
    future: list[T] = []
    for item in items:
        item_date = parse_source_date(date_getter(item))
        if item_date is not None and item_date > information_cutoff.as_of_date:
            future.append(item)
        else:
            eligible.append(item)
    return eligible, future


def latest_served_date(
    items: Sequence[T],
    *,
    date_getter: Callable[[T], object],
) -> str | None:
    dates = tuple(
        parsed
        for item in items
        if (parsed := parse_source_date(date_getter(item))) is not None
    )
    return max(dates).isoformat() if dates else None


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


def _query_only_broad_queries(query: str) -> tuple[str, ...]:
    return (
        f"{query} 市场内部机制 资金 风险偏好",
        f"{query} 宏观 政策 外部事件",
        f"{query} 行业结构 权重板块",
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


def _query_only_counter_queries(query: str) -> tuple[str, ...]:
    return (
        f"{query} 反证 替代解释",
        f"{query} 市场内部 外部催化 区分",
        f"{query} 数据不支持 证据不足",
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


def _bucket_identity(item: BucketedHit) -> tuple[str, str, str]:
    return item.aperture, item.hit.file_path, item.hit.best_chunk_id
