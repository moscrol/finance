from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from intelligence.services.entity_anchor import EntityAnchor


SubjectKind = Literal["company", "theme", "market_pattern", "unknown"]
MatchedBy = Literal[
    "ticker",
    "entity",
    "candidate",
    "alias",
    "quoted",
    "explicit",
    "generic",
]

THEME_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "theme_research_specs.json"
)
_DATE_RE = re.compile(r"\b20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?\b")
_QUOTED_RE = re.compile(r"[“《\"]([^”》\"]{2,40})[”》\"]")
_TICKER_RE = re.compile(r"\b\d{6}(?:\.(?:SH|SZ|BJ))?\b", re.I)
_EXPLICIT_THEME_RE = re.compile(
    r"(?:研究|分析|看看|深挖)\s*([\u4e00-\u9fffA-Za-z0-9+.-]{2,16}?)"
    r"(?:题材|板块|产业链|方向)"
)
_MARKET_PATTERN_TERMS = (
    "连续上涨",
    "成交占比",
    "涨停家数",
    "指数上涨",
    "背离",
    "健康分歧",
    "行情高潮",
)


@dataclass(frozen=True)
class QueryEnvelope:
    question_type: str
    subject_kind: SubjectKind
    subject: str | None
    decision_goal: str
    timeframe: str | None
    matched_by: MatchedBy
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def _theme_aliases() -> tuple[str, ...]:
    try:
        doc = json.loads(THEME_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(doc, dict):
        return ()
    aliases = [
        str(alias).strip()
        for pack in doc.get("packs", [])
        if isinstance(pack, dict)
        for alias in pack.get("aliases", [])
        if str(alias).strip()
    ]
    return tuple(sorted(dict.fromkeys(aliases), key=len, reverse=True))


def _decision_goal(query: str) -> str:
    if "健康分歧" in query or "行情高潮" in query:
        return "区分健康分歧与行情高潮"
    if "背离" in query:
        return "解释市场背离"
    return "形成条件化判断"


def understand_query(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> QueryEnvelope:
    text = str(query or "").strip()
    timeframe_match = _DATE_RE.search(text)
    timeframe = timeframe_match.group(0) if timeframe_match else None

    if anchor is not None:
        return QueryEnvelope(
            "stock_deep_dive",
            "company",
            anchor.entity,
            _decision_goal(text),
            timeframe,
            "ticker" if anchor.matched_by == "code" else "entity",
            1.0,
        )

    normalized_theme = str(matched_theme or "").strip()
    if normalized_theme:
        return QueryEnvelope(
            "theme_analysis",
            "theme",
            normalized_theme,
            _decision_goal(text),
            timeframe,
            "candidate",
            0.98,
        )

    folded_text = text.casefold()
    for alias in _theme_aliases():
        if alias.casefold() in folded_text:
            return QueryEnvelope(
                "theme_analysis",
                "theme",
                alias,
                _decision_goal(text),
                timeframe,
                "alias",
                0.92,
            )

    quoted = _QUOTED_RE.search(text)
    if quoted:
        return QueryEnvelope(
            "theme_analysis",
            "theme",
            quoted.group(1).strip(),
            _decision_goal(text),
            timeframe,
            "quoted",
            0.72,
        )

    if sum(term in text for term in _MARKET_PATTERN_TERMS) >= 2:
        return QueryEnvelope(
            "general_finance_qa",
            "market_pattern",
            None,
            _decision_goal(text),
            timeframe,
            "generic",
            0.9,
        )

    explicit = _EXPLICIT_THEME_RE.search(text)
    if explicit:
        return QueryEnvelope(
            "theme_analysis",
            "theme",
            explicit.group(1).strip(),
            _decision_goal(text),
            timeframe,
            "explicit",
            0.8,
        )

    ticker = _TICKER_RE.search(text)
    if ticker:
        return QueryEnvelope(
            "stock_deep_dive",
            "company",
            ticker.group(0),
            _decision_goal(text),
            timeframe,
            "ticker",
            0.82,
        )

    return QueryEnvelope(
        "general_finance_qa",
        "unknown",
        None,
        _decision_goal(text),
        timeframe,
        "generic",
        0.4 if text else 0.1,
    )
