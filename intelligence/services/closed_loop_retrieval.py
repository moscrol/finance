from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
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

# theme_research_specs.json groups related research directions (for example,
# 算力 and 液冷) rather than strict synonyms.  Reusing an entire pack here
# would therefore weaken the evidence gate.  Keep only reviewed lexical
# equivalences that are safe to treat as subject anchors without model or IO.
_TRUSTED_ALIAS_GROUPS = (
    frozenset({"空芯光纤", "空心光纤", "hcf", "hollow core fiber", "hollow-core fiber"}),
    frozenset({"液冷", "liquid cooling", "liquid-cooling"}),
)
_NON_REVERSIBLE_SHORT_ALIASES = frozenset({"hcf"})
_SHORT_ASCII_TERM_RE = re.compile(r"[a-z][a-z0-9]{1,4}", re.I)
_HCF_CONTEXT_TERMS = ("fiber", "optical", "光纤", "光通信")


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
    _attempt_telemetries: list[RetrievalTelemetry] = field(
        default_factory=list,
        init=False,
        repr=False,
        compare=False,
    )
    _hit_provenance: dict[int, tuple[int, RetrievalTelemetry]] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

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

    relevance_terms = _relevance_terms(anchor, subject=explicit_subject)
    broad_relevance_terms = relevance_terms
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
        _bucket_hits(
            tuple(("narrow", hit) for hit in hybrid_hits),
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
    _finalize_telemetry(result)
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
    response_telemetry = response.telemetry
    result._attempt_telemetries.append(response_telemetry)
    result.dense_initializations = (
        result.dense_initializations
        + int(response_telemetry.dense_initializations)
    )
    attempt_index = len(result._attempt_telemetries) - 1
    for hit in response.hits:
        result._hit_provenance.setdefault(
            id(hit),
            (attempt_index, response_telemetry),
        )
    actual_timeout = (
        response_telemetry.timeout_seconds
        if response_telemetry.timeout_seconds is not None
        else timeout
    )
    result.attempts.append(
        RetrievalAttempt(
            aperture=aperture,
            query=query,
            mode=mode,
            timeout_seconds=actual_timeout,
            status=response_telemetry.status,
            hit_count=len(response.hits),
        )
    )
    if response.warning and response.warning not in result.warnings:
        result.warnings.append(response.warning)

    status = response_telemetry.status.casefold()
    freshness = response_telemetry.index_freshness.casefold()
    recoverable_empty_without_freshness = (
        status == "empty" and not response.hits and not freshness
    )
    untrusted_freshness = (
        freshness != "fresh" and not recoverable_empty_without_freshness
    )
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


def _finalize_telemetry(result: ClosedLoopRetrievalResult) -> None:
    """Publish evidence provenance while retaining aggregate execution cost.

    Only conclusion/counter-clue provenance can win over later empty/error
    attempts because those are the buckets Ask actually emits as W citations.
    When nothing outputtable survives, the terminal response remains public for
    failure diagnosis. Latency and dense initialization are whole-loop
    aggregates in both cases.
    """
    if not result._attempt_telemetries:
        return

    # 先纳入所有已通过相关性闸门的命中（包括普通 clue），再按
    # 真实 attempt 顺序校验快照。这样 BM25 clue 不会被后来同 chunk 的
    # hybrid 输出用另一 revision 覆盖。counter 在 clues 中的镜像用
    # BucketedHit 对象 identity 去重，但 chunk identity 此时仍必须保留。
    accepted_items: list[BucketedHit] = []
    seen_items: set[int] = set()
    for item in (*result.conclusion, *result.clues):
        if id(item) in seen_items:
            continue
        seen_items.add(id(item))
        accepted_items.append(item)

    output_item_ids = {
        id(item) for item in (*result.conclusion, *result.counter_clues)
    }
    records: list[
        tuple[BucketedHit, RetrievalTelemetry, tuple[str, str], int]
    ] = []
    for item in accepted_items:
        provenance = result._hit_provenance.get(id(item.hit))
        if provenance is None:
            continue
        attempt_index, item_telemetry = provenance
        snapshot = (
            item.hit.index_source_revision
            or item_telemetry.index_source_revision,
            item.hit.index_freshness or item_telemetry.index_freshness,
        )
        records.append((item, item_telemetry, snapshot, attempt_index))
    records.sort(key=lambda record: record[3])

    def remove_items(items: list[BucketedHit], *, discard: bool) -> None:
        remove_ids = {id(item) for item in items}
        if not remove_ids:
            return
        result.conclusion = [
            item for item in result.conclusion if id(item) not in remove_ids
        ]
        result.counter_clues = [
            item for item in result.counter_clues if id(item) not in remove_ids
        ]
        # counter_clues 与普通 clue 都必须精确按对象同步移除，
        # 不能用 (aperture, chunk) 一刀切误删 canonical item。
        result.clues = [item for item in result.clues if id(item) not in remove_ids]
        if discard:
            discarded_ids = {id(item) for item in result.discarded}
            result.discarded.extend(
                item for item in items if id(item) not in discarded_ids
            )

    had_snapshot_conflict = False
    canonical_by_identity: dict[tuple[str, str], tuple[str, str]] = {}
    identity_conflicts: list[BucketedHit] = []
    for item, _, snapshot, _ in records:
        identity = _hit_identity(item.hit)
        canonical = canonical_by_identity.setdefault(identity, snapshot)
        if snapshot != canonical:
            identity_conflicts.append(item)
    if identity_conflicts:
        had_snapshot_conflict = True
        remove_items(identity_conflicts, discard=True)
        result.warnings.append(
            "snapshot conflict: discarded "
            f"{len(identity_conflicts)} same-identity hit(s) before output"
        )
        conflict_ids = {id(item) for item in identity_conflicts}
        records = [record for record in records if id(record[0]) not in conflict_ids]

    # 同快照、同 chunk 在安全校验后才去重；保留真实召回顺序
    # 中的第一项，只精确移除后续重复项及 counter 镜像。
    unique_records: list[
        tuple[BucketedHit, RetrievalTelemetry, tuple[str, str], int]
    ] = []
    seen_identities: set[tuple[str, str]] = set()
    duplicates: list[BucketedHit] = []
    for record in records:
        identity = _hit_identity(record[0].hit)
        if identity in seen_identities:
            duplicates.append(record[0])
            continue
        seen_identities.add(identity)
        unique_records.append(record)
    if duplicates:
        remove_items(duplicates, discard=False)
    records = unique_records

    # 不同 chunk 的最终 W 输出也必须处于同一快照。
    output_records = [record for record in records if id(record[0]) in output_item_ids]
    if output_records:
        canonical_output_snapshot = output_records[0][2]
        output_conflicts = [
            record
            for record in output_records
            if record[2] != canonical_output_snapshot
        ]
        if output_conflicts:
            had_snapshot_conflict = True
            conflict_items = [record[0] for record in output_conflicts]
            remove_items(conflict_items, discard=True)
            result.warnings.append(
                "snapshot conflict: discarded "
                f"{len(conflict_items)} output hit(s); canonical "
                f"revision={canonical_output_snapshot[0] or 'missing'}, "
                f"freshness={canonical_output_snapshot[1] or 'missing'}"
            )
            conflict_ids = {id(item) for item in conflict_items}
            output_records = [
                record
                for record in output_records
                if id(record[0]) not in conflict_ids
            ]

    contributors = output_records

    if contributors:
        public = replace(contributors[0][1])
        contributor_hits = [item.hit for item, _, _, _ in contributors]
        representative = contributor_hits[0]
        canonical_snapshot = contributors[0][2]
        public.status = "ok"
        public.hit_count = len(contributor_hits)
        public.neighbor_hits = sum(hit.via_neighbor for hit in contributor_hits)
        scores = [hit.score for hit in contributor_hits]
        public.score_max = max(scores)
        public.score_min = min(scores)
        public.score_mean = sum(scores) / len(scores)
        public.index_built_at = (
            representative.index_built_at or public.index_built_at
        )
        public.index_source_revision = canonical_snapshot[0]
        public.index_freshness = canonical_snapshot[1]
    else:
        public = replace(result._attempt_telemetries[-1])
        has_non_output_hits = bool(result.clues or result.discarded) or any(
            attempt.hit_count > 0 for attempt in result.attempts
        )
        terminal_status = public.status.casefold()
        if has_non_output_hits and terminal_status not in {
            "error",
            "timeout",
            "skipped",
        }:
            # Adapter 成功只说明检索子进程正常；若命中全部被
            # relevance/snapshot/output gate 拒绝，Ask 实际没有 W 证据，
            # 即使最后一次恰好是 empty，公开遥测也必须带上整轮
            # degraded 门禁语义；真正的 terminal failure 则原样保留。
            public.status = "empty"
            public.degraded = True
            public.hit_count = 0
            public.neighbor_hits = 0
            public.score_max = None
            public.score_min = None
            public.score_mean = None
            gate_warning = "all retrieved hits rejected by output evidence gates"
            public.warning = "；".join(
                filter(None, (public.warning, gate_warning))
            )
            if gate_warning not in result.warnings:
                result.warnings.append(gate_warning)

    latencies = [
        telemetry.latency_ms
        for telemetry in result._attempt_telemetries
        if telemetry.latency_ms is not None
    ]
    public.latency_ms = sum(latencies) if latencies else None
    public.dense_initializations = result.dense_initializations
    result.telemetry = public


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
    aliases: list[str] = []
    for group in _TRUSTED_ALIAS_GROUPS:
        if any(
            term in group and term not in _NON_REVERSIBLE_SHORT_ALIASES
            for term in base_terms
        ):
            aliases.extend(group)
    expanded_terms = (*base_terms, *aliases)
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
        direct_overlap = any(
            _relevance_term_matches(term, searchable) for term in aperture_terms
        )
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


def _relevance_term_matches(term: str, searchable: str) -> bool:
    if _SHORT_ASCII_TERM_RE.fullmatch(term):
        token_pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
        if re.search(token_pattern, searchable, flags=re.I) is None:
            return False
        if term.casefold() == "hcf":
            return any(context in searchable for context in _HCF_CONTEXT_TERMS)
        return True
    return term in searchable
