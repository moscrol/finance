"""工作台统一查询解析入口。

确定性实体/主题解析先于通用意图分类；追问指代只描述语义，不直接选择 owner。
这样 Controller、ResearchContract 与 Orchestrator 可以共享同一个判断来源。
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.entity_anchor import (
    EntityAnchor,
    entity_concept_names,
    resolve_entity_anchor,
)
from intelligence.services.query_understanding import QueryEnvelope, understand_query


ReferenceKind = Literal[
    "none",
    "entity_pronoun",
    "logic",
    "direction",
    "chain",
    "market_change",
    "continuation",
]

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
    r"^(?:刚才(?:你说的)?|把|再|继续|接着|然后|只按|横向|分别|哪些逻辑|"
    r"和[^，。！？?!]{2,24}(?:比|比较))"
)


@dataclass(frozen=True)
class QueryResolution:
    envelope: QueryEnvelope
    anchor: EntityAnchor | None
    reference_kind: ReferenceKind = "none"
    context_dependent: bool = False


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
        return QueryResolution(
            envelope=understand_query(
                cleaned,
                matched_theme=matched_theme,
                anchor=anchor,
            ),
            anchor=anchor,
            reference_kind=reference_kind,
            context_dependent=reference_kind != "none",
        )

    def _resolve_theme(self, query: str) -> str | None:
        folded = query.casefold()
        for term, canonical in _theme_terms(self.knowledge):
            if term.casefold() in folded:
                return canonical
        return None
