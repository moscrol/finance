"""Deep closed-loop evidence retrieval for model-owned finance research.

The module keeps the existing narrow/broad/counter retrieval discipline behind
one small interface.  It returns model-safe evidence and a separate inspector
projection; future or semantically rejected hits never enter the observation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
import re
from typing import Literal, TypeAlias

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
AnchorEvidenceAdmission: TypeAlias = Literal["open", "subject_local"]
AnchorHitAdmission: TypeAlias = Literal[
    "direct", "relation_clue", "rejected"
]

_VALUATION_ASSERTION_RE = re.compile(
    r"可比估值|合理价格|目标价|估值|市值|市盈率|市净率|市销率"
    r"|(?<![A-Za-z])(?:PE|PB|PS|EV)(?![A-Za-z])",
    re.IGNORECASE,
)
_EXPLICIT_RELATION_CUES = (
    "同属",
    "可比公司",
    "同行",
    "竞争",
    "上游",
    "下游",
    "供应商",
    "客户",
    "替代",
    "产业链",
)


@dataclass(frozen=True)
class EvidenceSearchPolicy:
    expansion_policy: closed_loop_retrieval.RetrievalExpansionPolicy = (
        "anchor_or_hits"
    )
    required_source_start: date | None = None
    required_source_end: date | None = None
    require_counter_evidence: bool = False
    anchor_admission: AnchorEvidenceAdmission = "open"


@dataclass(frozen=True)
class EvidenceSearchCoverage:
    conclusion_count: int
    clue_count: int
    counter_count: int
    discarded_count: int
    apertures_attempted: tuple[str, ...]
    target_window_count: int = 0
    target_window_counter_count: int = 0
    window_rejected_count: int = 0


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
        policy: EvidenceSearchPolicy | None = None,
    ) -> None:
        if max_evidence < 1:
            raise ValueError("max_evidence must be positive")
        self._retrieve = retrieve
        self._semantic_judge = semantic_judge
        self._max_evidence = max_evidence
        self._policy = policy or EvidenceSearchPolicy()

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
            expansion_policy=self._policy.expansion_policy,
        )
        loop = _apply_anchor_admission(
            loop,
            anchor=anchor,
            admission=self._policy.anchor_admission,
        )
        loop = self._apply_semantic_judge(
            cleaned_query,
            loop,
            deadline=deadline,
        )
        entries = _eligible_entries(loop)
        entries, window_rejected = _filter_required_source_window(
            entries,
            start=self._policy.required_source_start,
            end=self._policy.required_source_end,
        )
        evidence, stances = _project_evidence(
            entries,
            query=cleaned_query,
            max_evidence=self._max_evidence,
        )
        observation = "；".join(
            f"[{stance}]{item.title}：{item.detail}"
            for item, stance in zip(evidence, stances, strict=True)
        )
        has_required_window = (
            self._policy.required_source_start is not None
            or self._policy.required_source_end is not None
        )
        target_window_count = len(evidence) if has_required_window else 0
        target_window_counter_count = (
            sum(stance == "反方" for stance in stances)
            if has_required_window
            else 0
        )
        gaps = _policy_gaps(
            query=cleaned_query,
            policy=self._policy,
            evidence_count=len(evidence),
            target_window_counter_count=target_window_counter_count,
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
            target_window_count=target_window_count,
            target_window_counter_count=target_window_counter_count,
            window_rejected_count=len(
                {_hit_identity(item.hit) for _, item in window_rejected}
            ),
        )
        trace = ProviderTrace(
            provider="kb_hybrid_closed_loop",
            capability="evidence_search",
            status=(
                "success"
                if evidence and not gaps
                else "partial"
                if evidence
                else "future_of_cutoff"
                if any(item.status == "future_of_cutoff" for item in loop.attempts)
                else "empty"
            ),
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
    ) -> closed_loop_retrieval.ClosedLoopRetrievalResult:
        if self._semantic_judge is None:
            return loop
        buckets = [*loop.conclusion, *loop.counter_clues]
        if not buckets:
            return loop
        timeout = deadline.stage_timeout(evidence_judge.DEFAULT_TIMEOUT)
        if timeout <= 0.001:
            return loop
        candidates = tuple(
            (item.hit.title, item.hit.excerpt) for item in buckets
        )
        try:
            verdict = self._semantic_judge(query, candidates, timeout)
        except Exception:
            return loop
        if verdict is None:
            return loop
        keep_indexes, reason = verdict
        return closed_loop_retrieval.apply_semantic_filter(
            loop,
            keep_indexes=keep_indexes,
            reason=reason,
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
            key = _hit_identity(item.hit)
            if key in seen:
                continue
            seen.add(key)
            entries.append((stance, item))
    return tuple(entries)


def _apply_anchor_admission(
    loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
    *,
    anchor: EntityAnchor | None,
    admission: AnchorEvidenceAdmission,
) -> closed_loop_retrieval.ClosedLoopRetrievalResult:
    if admission == "open" or anchor is None:
        return loop
    if admission != "subject_local":
        raise ValueError(f"unknown anchor evidence admission: {admission}")

    counter_ids = {_hit_identity(item.hit) for item in loop.counter_clues}
    conclusions: list[closed_loop_retrieval.BucketedHit] = []
    counters: list[closed_loop_retrieval.BucketedHit] = []
    clues = [
        item
        for item in loop.clues
        if _hit_identity(item.hit) not in counter_ids
    ]
    discarded = list(loop.discarded)
    clue_ids = {_hit_identity(item.hit) for item in clues}
    discarded_ids = {_hit_identity(item.hit) for item in discarded}
    decisions: dict[tuple[str, str], AnchorHitAdmission] = {}

    def classify(
        item: closed_loop_retrieval.BucketedHit,
    ) -> AnchorHitAdmission:
        identity = _hit_identity(item.hit)
        cached = decisions.get(identity)
        if cached is not None:
            return cached
        decision = _anchor_hit_admission(item.hit, anchor)
        decisions[identity] = decision
        return decision

    def add_clue(item: closed_loop_retrieval.BucketedHit) -> None:
        identity = _hit_identity(item.hit)
        if identity not in clue_ids:
            clues.append(item)
            clue_ids.add(identity)

    def add_discarded(item: closed_loop_retrieval.BucketedHit) -> None:
        identity = _hit_identity(item.hit)
        if identity not in discarded_ids:
            discarded.append(item)
            discarded_ids.add(identity)

    for item in loop.conclusion:
        decision = classify(item)
        if decision == "direct":
            conclusions.append(item)
        elif decision == "relation_clue":
            add_clue(item)
        else:
            add_discarded(item)
    for item in loop.counter_clues:
        decision = classify(item)
        if decision == "direct":
            counters.append(item)
            add_clue(item)
        elif decision == "relation_clue":
            add_clue(item)
        else:
            add_discarded(item)

    counts = {
        decision: sum(value == decision for value in decisions.values())
        for decision in ("direct", "relation_clue", "rejected")
    }
    diagnostics = [*loop.diagnostics]
    diagnostics.append(
        "anchor_admission="
        f"direct:{counts['direct']},"
        f"relation_clue:{counts['relation_clue']},"
        f"rejected:{counts['rejected']}"
    )
    return closed_loop_retrieval.ClosedLoopRetrievalResult(
        conclusion=conclusions,
        clues=clues,
        discarded=discarded,
        counter_clues=counters,
        attempts=list(loop.attempts),
        warnings=list(loop.warnings),
        diagnostics=diagnostics,
        telemetry=loop.telemetry,
    )


def _anchor_hit_admission(
    hit: WikiHit,
    anchor: EntityAnchor,
) -> AnchorHitAdmission:
    raw_ticker = anchor.ticker.split(".", 1)[0]
    identities = tuple(
        value.casefold()
        for value in (anchor.entity, anchor.ticker, raw_ticker)
        if value
    )
    source_identity = f"{hit.title} {hit.file_path}".casefold()
    if any(value in source_identity for value in identities):
        return "direct"
    body = str(
        hit.llm_evidence or hit.display_excerpt or hit.excerpt or ""
    ).casefold()
    if not any(value in body for value in identities):
        return "rejected"
    if _VALUATION_ASSERTION_RE.search(body):
        return "direct"
    if any(cue in body for cue in _EXPLICIT_RELATION_CUES):
        return "relation_clue"
    return "rejected"


def _filter_required_source_window(
    entries: tuple[tuple[str, closed_loop_retrieval.BucketedHit], ...],
    *,
    start: date | None,
    end: date | None,
) -> tuple[
    tuple[tuple[str, closed_loop_retrieval.BucketedHit], ...],
    tuple[tuple[str, closed_loop_retrieval.BucketedHit], ...],
]:
    if start is None and end is None:
        return entries, ()
    eligible: list[tuple[str, closed_loop_retrieval.BucketedHit]] = []
    rejected: list[tuple[str, closed_loop_retrieval.BucketedHit]] = []
    for entry in entries:
        source_date = closed_loop_retrieval.wiki_hit_source_date(entry[1].hit)
        if (
            source_date is None
            or (start is not None and source_date < start)
            or (end is not None and source_date > end)
        ):
            rejected.append(entry)
        else:
            eligible.append(entry)
    return tuple(eligible), tuple(rejected)


def _policy_gaps(
    *,
    query: str,
    policy: EvidenceSearchPolicy,
    evidence_count: int,
    target_window_counter_count: int,
) -> tuple[str, ...]:
    gaps: list[str] = []
    if evidence_count == 0:
        if (
            policy.required_source_start is not None
            or policy.required_source_end is not None
        ):
            start = (
                policy.required_source_start.isoformat()
                if policy.required_source_start is not None
                else "最早日期"
            )
            end = (
                policy.required_source_end.isoformat()
                if policy.required_source_end is not None
                else "最新日期"
            )
            gaps.append(f"尚未找到 {start} 至 {end} 目标窗口内的可用证据")
        else:
            gaps.append(f"尚未找到与“{query}”直接相关的可用证据")
    elif policy.require_counter_evidence and target_window_counter_count == 0:
        gaps.append("目标窗口内尚缺反证或替代解释证据")
    return tuple(gaps)


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


def _unique_bucket_count(
    items: Sequence[closed_loop_retrieval.BucketedHit],
) -> int:
    return len({_hit_identity(item.hit) for item in items})


def _hit_identity(hit: WikiHit) -> tuple[str, str]:
    content_hash = str(hit.content_hash or "").strip()
    if content_hash:
        return ("content_hash", content_hash)
    return ("source_chunk", f"{hit.file_path}#{hit.best_chunk_id}")


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
            key = _hit_identity(item.hit)
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
    detail = (
        f"attempts={attempts or 'none'}; "
        f"conclusion={coverage.conclusion_count}; "
        f"counter={coverage.counter_count}; "
        f"discarded={coverage.discarded_count}; "
        f"target_window={coverage.target_window_count}; "
        f"target_window_counter={coverage.target_window_counter_count}; "
        f"window_rejected={coverage.window_rejected_count}"
    )
    mode_signatures: list[str] = []
    for attempt in loop.attempts:
        if not (
            attempt.requested_mode
            or attempt.effective_mode
            or attempt.fallback_reason
            or attempt.degraded
        ):
            continue
        requested = attempt.requested_mode or "?"
        effective = attempt.effective_mode or attempt.requested_mode or "?"
        signature = f"{requested}->{effective}"
        if attempt.fallback_reason:
            signature += f":{attempt.fallback_reason}"
        if attempt.degraded:
            signature += ":degraded"
        if signature not in mode_signatures:
            mode_signatures.append(signature)
    if mode_signatures:
        detail += "; retrieval_modes=" + ",".join(mode_signatures)
    return detail


__all__ = [
    "AnchorEvidenceAdmission",
    "AnchorHitAdmission",
    "EvidenceSearch",
    "EvidenceSearchCoverage",
    "EvidenceSearchPolicy",
    "EvidenceSearchResult",
    "SemanticJudge",
    "default_semantic_judge",
]
