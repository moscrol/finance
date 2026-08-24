"""工作台统一查询解析入口。

确定性实体/主题解析先于通用意图分类；追问指代只描述语义，不直接选择 owner。
这样 Controller、ResearchContract 与 Orchestrator 可以共享同一个判断来源。
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.entity_anchor import (
    EntityAnchor,
    entity_concept_names,
    resolve_entity_anchor,
)
from intelligence.services.query_understanding import (
    QueryEnvelope,
    cjk_span_embedding_term,
    has_clean_theme_occurrence,
    understand_query,
)


ReferenceKind = Literal[
    "none",
    "entity_pronoun",
    "logic",
    "direction",
    "chain",
    "market_change",
    "continuation",
]
ResolveStatus = Literal["resolved", "candidate", "unresolved"]
SuggestedAction = Literal["proceed", "clarify", "disclose"]
ResolveCandidateKind = Literal["company", "theme"]

_DETERMINED_QUESTION_TYPES = frozenset(
    {
        "market_watch",
        "dated_market_review",
        "market_forecast",
        "market_cause",
        "market_technical",
        "external_market",
        "methodology_discussion",
        "comparison",
        "event_forecast",
        "concept_definition",
        "stock_deep_dive",
        "theme_analysis",
        "news_impact",
        "financial_analysis",
        "valuation_estimate",
        "quick_fact",
    }
)

_CHAIN_REFERENCE_RE = re.compile(r"(?:这|那|该|上述|前述)(?:条)?(?:产业)?链")
_LOGIC_REFERENCE_RE = re.compile(r"(?:这|那|该|上述|前述)(?:个)?逻辑")
_DIRECTION_REFERENCE_RE = re.compile(r"(?:这|那|该|上述|前述)(?:个)?方向")
_MARKET_CHANGE_REFERENCE_RE = re.compile(
    r"^(?:这个|那个|该|上述|前述)?(?:边际|预期差|最近|近期)?变化"
    r"(?:呢|如何|怎么样|怎么看)?[？?。！!]*$|^边际变化"
)
_ENTITY_PRONOUN_RE = re.compile(
    r"(?:^|[，。！？?!；;\s])(?:那|它|其|该公司|这个公司|那个公司|上述|前述|前面)"
)
_CONTINUATION_RE = re.compile(
    r"^(?:把|再|继续|接着|然后|只按|横向|分别|哪些逻辑|"
    r"和[^，。！？?!]{2,24}(?:比|比较))"
)


@dataclass(frozen=True)
class ResolveCandidate:
    name: str
    kind: ResolveCandidateKind
    ticker: str | None = None


@dataclass(frozen=True)
class QueryResolution:
    envelope: QueryEnvelope
    anchor: EntityAnchor | None
    reference_kind: ReferenceKind = "none"
    context_dependent: bool = False
    status: ResolveStatus = "resolved"
    candidates: tuple[ResolveCandidate, ...] = ()
    suggested_action: SuggestedAction = "proceed"


@dataclass(frozen=True)
class _ThemeLexiconCacheEntry:
    fingerprint: tuple[tuple[int, int] | None, tuple[int, int] | None]
    terms: tuple[tuple[str, str], ...]


_THEME_CACHE: dict[str, _ThemeLexiconCacheEntry] = {}
_THEME_CACHE_LOCK = threading.RLock()


def _fingerprint(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _theme_terms(knowledge: KnowledgeAdapter) -> tuple[tuple[str, str], ...]:
    entity_path = knowledge.relation_path("entity_exposures").resolve()
    aliases_path = knowledge.relation_path("aliases").resolve()
    fingerprint = (_fingerprint(entity_path), _fingerprint(aliases_path))
    cache_key = f"{entity_path}\n{aliases_path}"
    with _THEME_CACHE_LOCK:
        cached = _THEME_CACHE.get(cache_key)
        if cached is not None and cached.fingerprint == fingerprint:
            return cached.terms

        concepts = set(entity_concept_names(knowledge))
        terms: dict[str, str] = {concept: concept for concept in concepts}
        aliases_relation = knowledge.load_relation("aliases")
        aliases = aliases_relation.get("data", {}).get("aliases", {})
        if isinstance(aliases, dict):
            for alias, canonical in aliases.items():
                alias_text = str(alias).strip()
                canonical_text = str(canonical).strip()
                if len(alias_text) >= 2 and canonical_text in concepts:
                    terms[alias_text] = canonical_text
        ordered = tuple(
            sorted(terms.items(), key=lambda item: len(item[0]), reverse=True)
        )
        _THEME_CACHE[cache_key] = _ThemeLexiconCacheEntry(fingerprint, ordered)
        return ordered


def classify_reference(query: str) -> ReferenceKind:
    cleaned = str(query or "").strip()
    if not cleaned:
        return "none"
    if _CHAIN_REFERENCE_RE.search(cleaned):
        return "chain"
    if _LOGIC_REFERENCE_RE.search(cleaned):
        return "logic"
    if _DIRECTION_REFERENCE_RE.search(cleaned):
        return "direction"
    if _MARKET_CHANGE_REFERENCE_RE.search(cleaned):
        return "market_change"
    if _ENTITY_PRONOUN_RE.search(cleaned):
        return "entity_pronoun"
    if _CONTINUATION_RE.search(cleaned):
        return "continuation"
    if re.search(r"上一轮「[^」]+」未完成核验", cleaned):
        return "continuation"
    return "none"


def is_contextual_reference(query: str) -> bool:
    return classify_reference(query) != "none"


class QueryResolver:
    def __init__(self, knowledge: KnowledgeAdapter | None = None):
        self.knowledge = knowledge or KnowledgeAdapter()

    def resolve(self, query: str) -> QueryResolution:
        cleaned = str(query or "").strip()
        anchor = resolve_entity_anchor(cleaned, self.knowledge)
        matched_theme = None if anchor is not None else self._resolve_theme(cleaned)
        reference_kind = classify_reference(cleaned)
        envelope = understand_query(
            cleaned,
            matched_theme=matched_theme,
            anchor=anchor,
        )
        status, action, candidates = _resolve_tristate(
            query=cleaned,
            knowledge=self.knowledge,
            anchor=anchor,
            matched_theme=matched_theme,
            envelope=envelope,
            reference_kind=reference_kind,
        )
        return QueryResolution(
            envelope=envelope,
            anchor=anchor,
            reference_kind=reference_kind,
            context_dependent=reference_kind != "none",
            status=status,
            candidates=candidates,
            suggested_action=action,
        )

    def _resolve_theme(self, query: str) -> str | None:
        folded = query.casefold()
        for term, canonical in _theme_terms(self.knowledge):
            if has_clean_theme_occurrence(folded, term.casefold()):
                return canonical
        return None


def format_resolve_clarification(resolution: QueryResolution) -> str:
    company = next((item for item in resolution.candidates if item.kind == "company"), None)
    theme = next((item for item in resolution.candidates if item.kind == "theme"), None)
    if company is not None and theme is not None:
        label = (
            f"{company.name}({company.ticker})"
            if company.ticker
            else company.name
        )
        return f"你问的是{label}还是{theme.name}板块？"
    names = "、".join(item.name for item in resolution.candidates if item.name)
    return f"你问的是哪一个：{names}？" if names else "你问的是哪家公司，还是哪个板块？"


def apply_entity_tristate_answer(frame: object, answer: str):
    """把「公司名还是主题」这一轮澄清收成确定主体。

    在线预算只有一轮。认不出的回答默认取更长的公司名，避免再把问题
    偷回主题（R13-A3 的原事故）。
    """

    from intelligence.services.task_frame import TaskFrame, rebase_task_frame

    if not isinstance(frame, TaskFrame):
        raise TypeError("apply_entity_tristate_answer expects a TaskFrame")
    match = _ENTITY_TRISTATE_QUESTION_RE.search(frame.clarification_question or "")
    if match is None:
        return frame
    company = match.group("company")
    theme = match.group("theme")
    cleaned = re.sub(r"\s+", "", str(answer or ""))
    prefer_theme = (
        bool(theme)
        and theme in cleaned
        and company not in cleaned
    ) or (
        company not in cleaned
        and any(token in cleaned for token in ("板块", "主题", "题材"))
    )
    if prefer_theme:
        subject, subject_kind, question_type = theme, "theme", "theme_analysis"
    else:
        subject, subject_kind, question_type = company, "company", "stock_deep_dive"
    assumption = (
        f"用户在唯一一次澄清中确认主体为{subject}"
        if cleaned
        else f"澄清预算已用尽，按公司名{subject}继续"
    )
    rebased = rebase_task_frame(
        frame,
        question_type=question_type,
        subject=subject,
        subject_kind=subject_kind,
    )
    return replace(
        rebased,
        assumptions=tuple(dict.fromkeys((*rebased.assumptions, assumption))),
        ambiguities=(),
        clarification_question=None,
    )


def is_entity_tristate_clarification(frame: object) -> bool:
    question = getattr(frame, "clarification_question", None)
    return bool(question) and _ENTITY_TRISTATE_QUESTION_RE.search(str(question)) is not None


def _resolve_tristate(
    *,
    query: str,
    knowledge: KnowledgeAdapter,
    anchor: EntityAnchor | None,
    matched_theme: str | None,
    envelope: QueryEnvelope,
    reference_kind: ReferenceKind,
) -> tuple[ResolveStatus, SuggestedAction, tuple[ResolveCandidate, ...]]:
    if anchor is not None:
        return "resolved", "proceed", ()
    if matched_theme:
        return "resolved", "proceed", ()
    conflict = _embedded_theme_conflict(query, knowledge)
    if conflict is not None:
        token, theme = conflict
        if envelope.subject_kind == "theme" and envelope.subject == token:
            return "resolved", "proceed", ()
        ticker = anchor.ticker if anchor is not None and anchor.ticker else None
        return (
            "candidate",
            "clarify",
            (
                ResolveCandidate(name=token, kind="company", ticker=ticker),
                ResolveCandidate(name=theme, kind="theme"),
            ),
        )
    if reference_kind != "none":
        return "resolved", "proceed", ()
    if envelope.subject_kind in {"company", "theme", "index", "external_market"} and envelope.subject:
        return "resolved", "proceed", ()
    if envelope.question_type in _DETERMINED_QUESTION_TYPES:
        return "resolved", "proceed", ()
    return "unresolved", "disclose", ()


def _embedded_theme_conflict(
    query: str,
    knowledge: KnowledgeAdapter,
) -> tuple[str, str] | None:
    terms = _theme_terms(knowledge)
    registered = {term for term, _canonical in terms} | {canonical for _term, canonical in terms}
    for term, canonical in terms:
        if sum(1 for char in term if "\u4e00" <= char <= "\u9fff") < 2:
            continue
        token = cjk_span_embedding_term(query, term)
        if not token or token == term or token == canonical:
            continue
        if token in registered:
            continue
        if not _looks_like_company_token(token):
            continue
        return token, canonical
    return None


_COMPANY_TOKEN_NOISE_RE = re.compile(r"[和与或的是在及、，？?。！!]")


def _looks_like_company_token(token: str) -> bool:
    if _COMPANY_TOKEN_NOISE_RE.search(token):
        return False
    cjk = sum(1 for char in token if "\u4e00" <= char <= "\u9fff")
    return 3 <= cjk <= 8 and cjk * 10 >= len(token) * 7


_ENTITY_TRISTATE_QUESTION_RE = re.compile(
    r"你问的是(?P<company>.+?)(?:\((?P<ticker>[^)]+)\))?还是(?P<theme>.+?)板块"
)
