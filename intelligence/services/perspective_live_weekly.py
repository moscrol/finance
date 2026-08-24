"""Bind the latest perspective weekly as live evidence; older hits stay analog.

Services layer only. Do not import runtime. Do not open DuckDB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from intelligence.services import perspective_lab
from intelligence.services.agent_research import AgentEvidence
from intelligence.userspace import UserSpace

EXCERPT_CHARS = 360
LIVE_TAG = "live_weekly"
ANALOG_TAG = "analog"
_ZHONG_GUAN_RE = re.compile(r"(?:^|\n)##?\s*中观[^\n]*\n", re.MULTILINE)

Status = Literal["bound", "missing", "skipped"]


@dataclass(frozen=True)
class LiveWeeklyReceipt:
    perspective_id: str
    article_id: str | None
    date: str | None
    title: str | None
    excerpt: str
    status: Status
    source_date: str | None

    @property
    def bound(self) -> bool:
        return self.status == "bound"


def bind_live_weekly(
    us: UserSpace | None,
    perspective_id: str | None,
    *,
    perspective_mode: str = "neutral",
) -> LiveWeeklyReceipt:
    pid = str(perspective_id or "").strip()
    mode = str(perspective_mode or "neutral").strip() or "neutral"
    if mode == "neutral" or not pid or us is None:
        return LiveWeeklyReceipt(
            perspective_id=pid,
            article_id=None,
            date=None,
            title=None,
            excerpt="",
            status="skipped",
            source_date=None,
        )
    records = [
        rec
        for rec in perspective_lab._read_manifest(  # noqa: SLF001 — same-layer reader
            perspective_lab.manifest_path(us, pid)
        )
        if str(rec.get("date") or "").strip()
    ]
    if not records:
        return LiveWeeklyReceipt(
            perspective_id=pid,
            article_id=None,
            date=None,
            title=None,
            excerpt="",
            status="missing",
            source_date=None,
        )
    ranked = sorted(
        records,
        key=lambda rec: (
            str(rec.get("date") or ""),
            str(rec.get("article_id") or ""),
        ),
        reverse=True,
    )
    chosen = ranked[0]
    day = str(chosen.get("date") or "") or None
    title = str(chosen.get("title") or "") or None
    raw_path = chosen.get("raw_path")
    text = ""
    if raw_path:
        try:
            text = Path(str(raw_path)).read_text(encoding="utf-8")
        except OSError:
            text = ""
    excerpt = _excerpt(text)
    article_id = str(chosen.get("article_id") or title or day or "article")
    return LiveWeeklyReceipt(
        perspective_id=pid,
        article_id=article_id,
        date=day,
        title=title,
        excerpt=excerpt,
        status="bound",
        source_date=day,
    )


def retrieve_analog_snippets(
    us: UserSpace,
    perspective_id: str,
    tape_summary: str,
    *,
    live_date: str,
    limit: int = 3,
    excerpt_chars: int = EXCERPT_CHARS,
) -> list[dict[str, str]]:
    snippets = perspective_lab.retrieve_article_snippets(
        us,
        perspective_id,
        tape_summary,
        limit=max(limit * 3, 6),
        excerpt_chars=excerpt_chars,
    )
    out: list[dict[str, str]] = []
    for snippet in snippets:
        day = str(snippet.get("date") or "")
        if not day or day >= live_date:
            continue
        out.append({**snippet, ANALOG_TAG: "true"})
        if len(out) >= limit:
            break
    return out


def live_weekly_evidence(
    receipt: LiveWeeklyReceipt,
    analogs: list[dict[str, str]] | tuple[dict[str, str], ...] = (),
) -> tuple[AgentEvidence, ...]:
    items: list[AgentEvidence] = []
    if receipt.status == "bound":
        items.append(
            AgentEvidence(
                tool="kb_search",
                title=f"活周报 {receipt.title or ''} ({receipt.date or ''})".strip(),
                detail=receipt.excerpt,
                source=LIVE_TAG,
                source_date=receipt.source_date,
                evidence_tier="L1_research",
                freshness="current",
            )
        )
    elif receipt.status == "missing":
        items.append(
            AgentEvidence(
                tool="kb_search",
                title="活周报缺失",
                detail="选定视角没有可绑定的周报原文，禁止编造文号。",
                source=LIVE_TAG,
                source_date=None,
                evidence_tier="L1_research",
                freshness="unknown",
            )
        )
    for snippet in analogs:
        items.append(
            AgentEvidence(
                tool="kb_search",
                title=f"analog {snippet.get('title') or ''} ({snippet.get('date') or ''})".strip(),
                detail=str(snippet.get("excerpt") or ""),
                source=ANALOG_TAG,
                source_date=str(snippet.get("date") or "") or None,
                evidence_tier="L1_research",
                freshness="historical",
            )
        )
    return tuple(items)


def is_live_weekly_evidence(item: object) -> bool:
    source = str(getattr(item, "source", "") or "")
    title = str(getattr(item, "title", "") or "")
    return source == LIVE_TAG or title.startswith("活周报")


def _excerpt(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    match = _ZHONG_GUAN_RE.search(raw)
    body = raw[match.end() :] if match else raw
    collapsed = re.sub(r"\s+", " ", body).strip()
    if len(collapsed) <= EXCERPT_CHARS:
        return collapsed
    return collapsed[:EXCERPT_CHARS]
