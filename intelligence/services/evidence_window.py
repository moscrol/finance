"""Turn-local evidence windowing.

Retrieval can be broad, but the presenter should see a small, ranked window.
This module is deliberately deterministic: it ranks evidence by query
relevance, source hardness, freshness and independence, then applies one
global character budget.  The full provider trace remains available for audit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence


_HARD_TERMS = (
    "公告", "年报", "季报", "半年报", "交易所", "互动易", "合同", "订单",
    "中标", "认证", "量产", "出货", "收入", "财报", "官方",
)
_FRESH_TERMS = ("截至", "本周", "近期", "最新", "当前", "2026-07", "2026/07")
_SOURCE_TOOL_WEIGHT = {
    "l3_lookup": 7.0,
    "market_data": 6.0,
    "news_search": 5.0,
    "evidence_lookup": 4.0,
    "web_search": 3.0,
    "kb_search": 2.5,
    "graph_lookup": 1.5,
}


def _tool_weight(tool: str) -> float:
    if tool in _SOURCE_TOOL_WEIGHT:
        return _SOURCE_TOOL_WEIGHT[tool]
    section = str(tool or "")
    for term, score in (
        ("L3", 7.0),
        ("官方", 7.0),
        ("盘面", 6.0),
        ("市场", 5.5),
        ("证据索引", 4.0),
        ("Web", 3.0),
        ("agent", 3.0),
        ("知识库", 2.5),
        ("图谱", 1.5),
    ):
        if term in section:
            return score
    return 1.0


@dataclass(frozen=True)
class EvidenceWindowItem:
    key: str
    tool: str
    title: str
    detail: str
    source: str
    source_date: str | None = None
    evidence_tier: str = ""
    independent_key: str = ""
    score: float = 0.0


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def _query_tokens(query: str) -> tuple[str, ...]:
    text = _normalize(query)
    # Chinese queries have no spaces; retain meaningful 2-4 character chunks
    # as a cheap lexical relevance signal, plus Latin/number tokens.
    tokens = set(re.findall(r"[a-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,4}", text))
    return tuple(sorted(tokens, key=lambda item: (-len(item), item)))


def _freshness_score(source_date: str | None, text: str) -> float:
    if any(term in text for term in _FRESH_TERMS):
        return 2.0
    if not source_date:
        return 0.0
    try:
        parsed = date.fromisoformat(str(source_date)[:10].replace("/", "-"))
    except ValueError:
        return 0.0
    age = max(0, (date.today() - parsed).days)
    return 2.5 if age <= 14 else 1.2 if age <= 45 else 0.0


def is_time_aligned_evidence(
    item: object,
    *,
    max_age_days: int = 14,
    reference_date: date | None = None,
) -> bool:
    """Whether an external item is current enough for a current-window claim."""
    tool = str(getattr(item, "tool", ""))
    if tool == "market_data":
        return True
    source_date = getattr(item, "source_date", None)
    if not source_date:
        return False
    try:
        parsed = date.fromisoformat(str(source_date)[:10].replace("/", "-"))
    except ValueError:
        return False
    age = ((reference_date or date.today()) - parsed).days
    return 0 <= age <= max_age_days


def _rank(
    *,
    query: str,
    tool: str,
    title: str,
    detail: str,
    source: str,
    source_date: str | None,
    evidence_tier: str,
) -> float:
    text = _normalize(f"{title} {detail} {source}")
    relevance = sum(min(2.5, len(token) * 0.45) for token in _query_tokens(query) if token in text)
    hardness = 2.0 if any(term in text for term in _HARD_TERMS) else 0.0
    tier = 1.5 if str(evidence_tier).lower().startswith(("l3", "official", "公告")) else 0.0
    return _tool_weight(tool) + relevance + hardness + tier + _freshness_score(source_date, text)


def select_agent_evidence(
    query: str,
    evidence: Sequence[object],
    *,
    max_chars: int = 6000,
    max_items: int = 12,
) -> list[object]:
    """Return a relevance/hardness/freshness/independence ranked evidence window."""
    ranked: list[tuple[float, str, object]] = []
    for index, item in enumerate(evidence):
        tool = str(getattr(item, "tool", ""))
        title = str(getattr(item, "title", ""))
        detail = str(getattr(item, "detail", ""))
        source = str(getattr(item, "source", ""))
        source_date = getattr(item, "source_date", None)
        evidence_tier = str(getattr(item, "evidence_tier", ""))
        key = str(getattr(item, "independent_key", "") or "")
        if not key:
            key = _normalize(f"{tool}:{title}:{source}")[:160]
        score = _rank(
            query=query,
            tool=tool,
            title=title,
            detail=detail,
            source=source,
            source_date=source_date,
            evidence_tier=evidence_tier,
        )
        ranked.append((score, f"{key}:{index}", item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    selected: list[object] = []
    used_independent: set[str] = set()
    used_chars = 0
    for score, _key, item in ranked:
        del score
        independent = str(getattr(item, "independent_key", "") or "")
        if independent and independent in used_independent:
            continue
        title = str(getattr(item, "title", ""))
        detail = str(getattr(item, "detail", ""))
        cost = len(title) + len(detail) + 18
        if selected and used_chars + cost > max_chars:
            continue
        selected.append(item)
        used_chars += cost
        if independent:
            used_independent.add(independent)
        if len(selected) >= max_items:
            break
    return selected


def select_text_window(
    query: str,
    lines: Iterable[str],
    *,
    max_chars: int = 9000,
    max_items: int = 36,
) -> list[str]:
    """Rank plain evidence-chain lines while preserving section headings."""
    items: list[tuple[float, int, str]] = []
    current_section = ""
    for index, raw in enumerate(lines):
        line = str(raw or "").strip()
        if not line:
            continue
        if line.startswith("\x00SUB\x00"):
            current_section = line
            continue
        score = _rank(
            query=query,
            tool=current_section,
            title=line[:80],
            detail=line,
            source=current_section,
            source_date=None,
            evidence_tier="",
        )
        items.append((score, index, line))
    items.sort(key=lambda row: (-row[0], row[1]))
    selected: list[str] = []
    used_chars = 0
    for _score, _index, line in items:
        cost = len(line) + 3
        if selected and used_chars + cost > max_chars:
            continue
        selected.append(line)
        used_chars += cost
        if len(selected) >= max_items:
            break
    return selected
