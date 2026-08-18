"""KC-07：召回自评四问。装配完只披露、不补搜。

Knevo 检索是发射→自评→定向补搜。第一版只做确定性四问，把缺口写进
合成上下文的证据缺口披露段；补搜留给第二版，避免预算失控。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from intelligence.services.counter_retrieval import COUNTER_MARK, MISSING_COUNTER_EVIDENCE

GAP_NO_SUPPORT = "正面证据 0 条"
GAP_NO_COUNTER = "反方证据 0 条"
GAP_NO_CHAIN = "产业链关系 0 条"
GAP_NO_FRESH = "最近 30 天证据 0 条"
GAP_FEW_SOURCES = "独立来源不足 3 个"

FRESH_DAYS = 30
MIN_INDEPENDENT_SOURCES = 3
DISCLOSURE_PREFIX = "召回自评："

# 产业链关系：上下游/供应链角色。不用光秃「客户」——客户验证是硬度词，不是链。
CHAIN_TERMS = ("上游", "下游", "中游", "产业链", "供应链", "供应商", "同业")

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_WIKI_PAGE_RE = re.compile(r"\[\[([^\]]+)\]\]")
_R_SOURCE_RE = re.compile(r"[（(]([^,，()（）]+),\s*\d{4}-\d{2}-\d{2}")
_WIKI_TITLE_RE = re.compile(
    r"^(?:\[反\]\s*)?(?:〔第2跳〕\s*)?([^：:(（]+?)（相关度"
)
_COUNTER_TITLE_RE = re.compile(r"反方线索（待进一步核验）：([^：]+)：")


@dataclass(frozen=True)
class RecallAudit:
    gaps: tuple[str, ...]

    def disclosure_lines(self) -> tuple[str, ...]:
        return tuple(f"{DISCLOSURE_PREFIX}{gap}" for gap in self.gaps)


def parse_as_of(*candidates: str | None) -> date | None:
    """从交易日/选项日期里取第一个可解析的 YYYY-MM-DD。"""
    for raw in candidates:
        match = _DATE_RE.search(str(raw or ""))
        if match is None:
            continue
        parsed = _parse_date(match.group(1))
        if parsed is not None:
            return parsed
    return None


def audit_recall(
    lines: Sequence[str] | None,
    *,
    as_of: date,
    fresh_days: int = FRESH_DAYS,
    min_sources: int = MIN_INDEPENDENT_SOURCES,
) -> RecallAudit:
    support = 0
    counter = 0
    chain = 0
    fresh = 0
    sources: set[str] = set()
    cutoff = as_of - timedelta(days=fresh_days)
    for raw in lines or ():
        line = str(raw or "").strip()
        if _is_meta(line):
            continue
        if _is_counter(line):
            counter += 1
        else:
            support += 1
        if any(term in line for term in CHAIN_TERMS):
            chain += 1
        for match in _DATE_RE.finditer(line):
            parsed = _parse_date(match.group(1))
            if parsed is not None and cutoff <= parsed <= as_of:
                fresh += 1
                break
        sources |= _sources_in(line)

    gaps: list[str] = []
    if support == 0:
        gaps.append(GAP_NO_SUPPORT)
    if counter == 0:
        gaps.append(GAP_NO_COUNTER)
    if chain == 0:
        gaps.append(GAP_NO_CHAIN)
    if fresh == 0:
        gaps.append(GAP_NO_FRESH)
    if len(sources) < min_sources:
        gaps.append(GAP_FEW_SOURCES)
    return RecallAudit(gaps=tuple(gaps))


def _is_counter(line: str) -> bool:
    return COUNTER_MARK in line or line.startswith("反方线索")


def _is_meta(line: str) -> bool:
    text = line.strip()
    if not text or text == MISSING_COUNTER_EVIDENCE:
        return True
    return text.startswith(DISCLOSURE_PREFIX)


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _sources_in(line: str) -> set[str]:
    found: set[str] = set()
    for match in _WIKI_PAGE_RE.finditer(line):
        name = match.group(1).strip()
        if name:
            found.add(name)
    for match in _R_SOURCE_RE.finditer(line):
        name = match.group(1).strip()
        if name and not name.startswith("相关度"):
            found.add(name)
    title = _WIKI_TITLE_RE.search(line)
    if title is not None:
        name = title.group(1).strip()
        if name:
            found.add(name)
    counter_title = _COUNTER_TITLE_RE.search(line)
    if counter_title is not None:
        name = counter_title.group(1).strip()
        if name:
            found.add(name)
    return found
