"""KC-06：第二跳检索规划。

Knevo 宽口径词必须从窄命中里抽。第一轮 R/W 命中后，用词表交集+频次
（可加图谱邻居）抽出 2-5 个实体/概念，再取前 ``SECOND_HOP_TARGET_CAP``
个当第二轮 target。总证据行上限不变，第二跳只参与排序挤占。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

SECOND_HOP_MARK = "〔第2跳〕"
SECOND_HOP_EXTRACT_MAX = 5
SECOND_HOP_TARGET_CAP = 3
SECOND_HOP_SLOT_RESERVE = 1
RETRIEVAL_HOP_KEY = "_retrieval_hop"


def extract_second_hop_targets(
    texts: Sequence[str],
    lexicon: Sequence[str],
    *,
    neighbors: Sequence[str] = (),
    exclude: Sequence[str] = (),
    limit: int = SECOND_HOP_TARGET_CAP,
) -> tuple[str, ...]:
    """从正文频次与邻居名抽第二跳 target。只返回词表内、未被排除、出现过的词。"""
    if limit <= 0:
        return ()
    blocked = {str(item or "").strip() for item in exclude if str(item or "").strip()}
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in lexicon:
        term = str(raw or "").strip()
        if not term or term in blocked or term in seen:
            continue
        seen.add(term)
        ordered.append(term)
    if not ordered:
        return ()
    blob = "\n".join(str(text or "") for text in texts)
    counts = {term: blob.count(term) for term in ordered}
    for raw in neighbors:
        term = str(raw or "").strip()
        if term in counts:
            counts[term] += 1
    ranked = sorted(
        (term for term in ordered if counts[term] > 0),
        key=lambda term: (-counts[term], ordered.index(term)),
    )
    return tuple(ranked[: min(limit, SECOND_HOP_EXTRACT_MAX)])


def reserve_second_hop_slots(
    first_hop: Sequence[T],
    second_hop: Sequence[T],
    *,
    room: int,
    reserve: int = SECOND_HOP_SLOT_RESERVE,
) -> list[T]:
    """在 support 名额里保底 ``min(reserve, 第二跳命中)`` 条，其余仍由第一跳占。"""
    if room <= 0:
        return []
    guaranteed = min(len(second_hop), max(0, reserve), room)
    take_first = list(first_hop[: room - guaranteed])
    remaining = room - len(take_first)
    return take_first + list(second_hop[:remaining])


def hop_lexicon(
    *,
    theme: str | None,
    company_evidence_concepts: dict[str, str],
    concept_names: Sequence[str] = (),
    company_names: Sequence[str] = (),
) -> tuple[str, ...]:
    """装配层用的词表：题材、暴露概念、图谱概念名、暴露公司名。"""
    names: list[str] = []
    if theme:
        names.append(theme)
    names.extend(company_evidence_concepts)
    names.extend(company_evidence_concepts.values())
    names.extend(concept_names)
    names.extend(company_names)
    return tuple(dict.fromkeys(item.strip() for item in names if str(item or "").strip()))
