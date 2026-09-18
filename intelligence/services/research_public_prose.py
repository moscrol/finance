"""Pure public-prose boundary shared by candidate retention and final review.

Sanitation is not evidence admission. Presence is checked on a copy; it must
never truncate or rewrite the delivered analysis merely for quality reasons.
"""
from __future__ import annotations

import re

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.run_store import redact_public_prose
from intelligence.services.research_annotations import CANDIDATE_REVIEW_NOTICE

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])|\n+")
_CONTROL_FIELD_RE = re.compile(
    r"(?:\b(?:content[_ ]?hash|evidence[_ ]?hash|internal[_ ]?locator|"
    r"system[_ ]?prompt|tool[_ ]?calls?)\b\s*[:=]?|"
    r"\bhash\b\s*[:=]|\bprovider(?:[_ ]?name)?\b\s*[:=]|"
    r"\b_?provider_(?:attempts?|trace)\b\s*[:=]?|"
    r"\bendpoint\b\s*[:=]|"
    r"证据哈希|内容哈希|内部定位|系统提示|工具调用)",
    re.IGNORECASE,
)


def sanitize_public_analysis(
    draft: str,
    evidence: tuple[AgentEvidence, ...],
    traces: tuple[ProviderTrace, ...] = (),
) -> str:
    private_tokens = frozenset(
        token.casefold()
        for token in (
            *(item.tool for item in evidence),
            *(item.content_hash for item in evidence),
            *(item.internal_locator for item in evidence),
            *(trace.capability for trace in traces),
        ) if token
    )

    def private(text: str) -> bool:
        return bool(_CONTROL_FIELD_RE.search(text)) or any(
            token in text.casefold() for token in private_tokens
        )

    safe = redact_public_prose(str(draft or ""))
    safe = re.sub(r"(?<![A-Za-z0-9_])(?:news_search|directional_news)(?![A-Za-z0-9_])", "资讯检索", safe, flags=re.IGNORECASE)
    kept: list[str] = []
    for raw in safe.splitlines():
        line = raw.strip()
        if line == "[REDACTED]" or (line.startswith("{") and line.endswith("}")):
            continue
        if not line or not private(line):
            kept.append(raw)
            continue
        for part in _SENTENCE_RE.split(line):
            sentence = part.strip()
            if not sentence or private(sentence):
                continue
            if sentence.startswith("{") and sentence.endswith("}"):
                continue
            kept.append(sentence)
    return "\n".join(kept).strip()


def has_public_analysis(body: str) -> bool:
    """Presence only: headings, empty tables and source notes aren't analysis."""
    lines = body.splitlines()
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("#") or re.fullmatch(r"[| :\-]+", line):
            continue
        if index + 1 < len(lines) and re.fullmatch(r"[| :\-]+", lines[index + 1].strip()):
            continue
        visible = re.sub(r"\[?E[1-9][0-9]{0,2}\]?", "", line)
        visible = visible.replace("[REDACTED]", "").strip(" *。！.!`| :-")
        if re.fullmatch(r"\*\*(?:分析|结论|板块比较|历史边界|风险|证据|来源)\*\*", line):
            continue
        if visible in {"（引用未核验）", "（单源）", "（待核验：所据证据已被取代或证伪）", CANDIDATE_REVIEW_NOTICE.rstrip("。")}:
            continue
        if re.match(r"^(?:来源|引用来源|参考来源)\s*[:：]", visible):
            continue
        if visible and visible not in {"已经完成", "已完成", "完成", "done", "completed"}:
            return True
    return False
