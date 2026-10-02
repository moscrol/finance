"""Optional, bounded rereading of evidence already presented in this Episode.

No files, provider queries, new source identity, or semantic decisions. The
caller supplies this Episode's *presented* pool, not all branch-ledger items.
Activation and authorization are separate: the environment switch never grants
``evidence_read`` capability. Citation identity remains the original E-number.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
import os

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.closed_loop_retrieval import parse_source_date
from intelligence.services.episode_protocol import (
    evidence_ordinal_table,
    parse_evidence_ordinal,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments,
    ToolRunResult,
    ToolSpec,
)
from intelligence.services.tool_result_budget import MAX_OBSERVATION_CHARS

EVIDENCE_READ_ENV = "ASK_EPISODE_EVIDENCE_READ"
MAX_PAGE_CHARS = 600
_FIELDS = ("title", "detail")


def evidence_read_enabled() -> bool:
    return os.environ.get(EVIDENCE_READ_ENV, "").strip().lower() in {
        "on",
        "1",
        "true",
        "yes",
    }


def _by_ref(items: Sequence[AgentEvidence]) -> dict[str, AgentEvidence]:
    ordinals = evidence_ordinal_table(tuple(items))
    result: dict[str, AgentEvidence] = {}
    for item in items:
        ref = ordinals.get(item.content_hash)
        if ref is not None:
            result.setdefault(ref, item)
    return result


def parse_evidence_read_arguments(arguments: Mapping[str, object]) -> tuple[str, str]:
    if set(arguments) - {"evidence_id", "field", "offset", "limit"}:
        raise InvalidResearchToolArguments(
            "evidence_read accepts evidence_id, field, offset, limit only"
        )
    ref = arguments.get("evidence_id")
    if not isinstance(ref, str) or parse_evidence_ordinal(ref) is None:
        raise InvalidResearchToolArguments(
            "evidence_id must be a presented E-number, not a path or hash"
        )
    field_name = arguments.get("field", "detail")
    if field_name not in _FIELDS:
        raise InvalidResearchToolArguments("field must be title or detail")
    offset, limit = arguments.get("offset", 0), arguments.get("limit", MAX_PAGE_CHARS)
    if type(offset) is not int or not 0 <= offset <= 10_000_000:
        raise InvalidResearchToolArguments(
            "offset must be a non-negative character index <= 10000000"
        )
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE_CHARS:
        raise InvalidResearchToolArguments("limit must be an integer between 1 and 600")
    value = json.dumps(
        {
            "evidence_id": f"E{parse_evidence_ordinal(ref)}",
            "field": field_name,
            "offset": offset,
            "limit": limit,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return value, value


def _page(ref: str, field_name: str, text: str, offset: int, limit: int) -> str:
    if offset > len(text):
        raise InvalidResearchToolArguments(
            "offset exceeds total_chars; use a returned next_offset"
        )
    end = min(len(text), offset + limit)
    # Budget the serialized observation, not just its source characters. Escaped
    # newlines/control characters must not turn the downstream 900-char clip
    # into malformed JSON or silently discard the page's continuation cursor.
    while True:
        value = json.dumps(
            {
                "kind": "evidence_page",
                "evidence_id": ref,
                "field": field_name,
                "offset": offset,
                "end_offset": end,
                "total_chars": len(text),
                "next_offset": end if end < len(text) else None,
                "text": text[offset:end],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(value) <= MAX_OBSERVATION_CHARS:
            return value
        end -= max(1, (len(value) - MAX_OBSERVATION_CHARS + 5) // 6)
        if end <= offset:
            raise InvalidResearchToolArguments(
                "page metadata exceeds the observation budget"
            )


def bind_evidence_read_tool(
    *, presented_evidence: Callable[[], Sequence[AgentEvidence]]
) -> ToolSpec:
    def runner(value: str, context: AgentToolContext) -> ToolRunResult:
        context.check_cancelled()
        context.timeout(1.0)
        args = json.loads(value)
        item = _by_ref(tuple(presented_evidence())).get(args["evidence_id"])
        if item is None:
            raise InvalidResearchToolArguments(
                "evidence_id is not in this Episode's presented pool"
            )
        source_date = parse_source_date(item.source_date)
        cutoff = context.information_cutoff
        history = context.history_intent
        if (
            cutoff is not None
            and source_date is not None
            and source_date > cutoff.as_of_date
        ):
            raise InvalidResearchToolArguments(
                "evidence is outside the current information cutoff"
            )
        if (
            history is not None
            and history.strict_window
            and (
                source_date is None
                or (
                    history.requested_start
                    and source_date.isoformat() < history.requested_start
                )
                or (
                    history.requested_end
                    and source_date.isoformat() > history.requested_end
                )
            )
        ):
            raise InvalidResearchToolArguments(
                "evidence is outside the current authorized history window"
            )
        observation = _page(
            args["evidence_id"],
            args["field"],
            getattr(item, args["field"]),
            args["offset"],
            args["limit"],
        )
        context.check_cancelled()
        return ToolRunResult(
            # Re-delivery, not a new atom: the accumulator deduplicates this hash
            # and retains original provenance. Ordinary cutoff gates still run.
            evidence=(item,),
            observation=observation,
            trace=ProviderTrace(
                provider="episode:presented_evidence",
                capability="evidence_read",
                status="success",
                result_count=1,
            ),
        )

    return ToolSpec(
        name="evidence_read",
        capability="evidence_read",
        description="分页补读本研究回合已交付证据的原始标题或正文",
        cost="local",
        freshness="original",
        io_effect="local_read",
        runner=runner,
        cache_result=False,
        contract=(
            "仅补读菜单当前允许的、本回合已交付 E 编号原件；不是新来源、不更新日期，不获取底层数据库或网页。"
            "是否需要补读由你决定；offset 从零开始按字符计，limit 最多600；按返回的 next_offset 继续。"
            "补读仍消耗工具次数与时间预算；保留原编号引用，不把重复交付当成独立互证。"
        ),
        parameters={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "evidence_id": {"type": "string", "pattern": "^[Ee][1-9][0-9]{0,2}$"},
                "field": {"type": "string", "enum": list(_FIELDS), "default": "detail"},
                "offset": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10_000_000,
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_PAGE_CHARS,
                    "default": MAX_PAGE_CHARS,
                },
            },
            "required": ["evidence_id"],
        },
        parse_arguments=parse_evidence_read_arguments,
    )


@dataclass
class EvidenceReadCoverage:
    """Count newly displayed original characters, never new evidence sources.

    Called on the *delivered model projection*, not on runner completion. It
    verifies literal slices against the current pool and unions intervals, so
    overlaps, repeats, forged page text, and source-side-only reads gain nothing.
    Ordinary previews seed coverage but do not earn a reread progress increment.
    """

    ranges: dict[tuple[str, str], list[tuple[int, int]]] = field(default_factory=dict)

    def _add(self, key: tuple[str, str], start: int, end: int) -> int:
        old = self.ranges.get(key, [])
        before = sum(b - a for a, b in old)
        merged: list[tuple[int, int]] = []
        for a, b in sorted([*old, (start, end)]):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        self.ranges[key] = merged
        return sum(b - a for a, b in merged) - before

    def note_complete(self, evidence: Sequence[AgentEvidence]) -> None:
        """For the opening-prefetch renderer that displays title/detail in full."""
        for item in evidence:
            if item.content_hash:
                for name in _FIELDS:
                    self._add((item.content_hash, name), 0, len(getattr(item, name)))

    def observe(self, model_content: str, *, evidence: Sequence[AgentEvidence]) -> int:
        try:
            view = json.loads(model_content)
        except (ValueError, TypeError):
            return 0
        if not isinstance(view, dict):
            return 0
        pool = _by_ref(evidence)
        # Free-text observations can already contain the whole card (or a
        # longer prefix) even when the separate evidence.detail is clipped.
        prose = view.get("observation")
        if view.get("tool") != "evidence_read" and isinstance(prose, str):
            for original in pool.values():
                for name in _FIELDS:
                    full = getattr(original, name)
                    if not full:
                        continue
                    if full in prose:
                        self._add((original.content_hash, name), 0, len(full))
                    elif prose.endswith("…"):
                        prefix = prose[:-1]
                        pos = prefix.find(full[0])
                        while pos >= 0:
                            if full.startswith(prefix[pos:]):
                                self._add(
                                    (original.content_hash, name), 0, len(prefix) - pos
                                )
                                break
                            pos = prefix.find(full[0], pos + 1)
        shown_items = view.get("evidence", ())
        if not isinstance(shown_items, (list, tuple)):
            shown_items = ()
        for shown in shown_items:
            if not isinstance(shown, dict):
                continue
            ref = shown.get("evidence_id", shown.get("ref"))
            original = pool.get(ref) if isinstance(ref, str) else None
            if original is None:
                continue
            for name in _FIELDS:
                text, full = shown.get(name), getattr(original, name)
                if not isinstance(text, str):
                    continue
                if full.startswith(text):
                    kept = len(text)
                elif text.endswith("…") and full.startswith(text[:-1]):
                    kept = len(text) - 1
                else:
                    continue
                self._add((original.content_hash, name), 0, kept)
        if view.get("tool") != "evidence_read":
            return 0
        try:
            page = json.loads(view.get("observation", ""))
        except (ValueError, TypeError):
            return 0
        if not isinstance(page, dict) or page.get("kind") != "evidence_page":
            return 0
        ref = page.get("evidence_id")
        original = pool.get(ref) if isinstance(ref, str) else None
        name, text, start, end = (
            page.get(k) for k in ("field", "text", "offset", "end_offset")
        )
        if (
            original is None
            or name not in _FIELDS
            or not isinstance(text, str)
            or type(start) is not int
            or type(end) is not int
        ):
            return 0
        full = getattr(original, name)
        if (
            not (0 <= start <= end <= len(full))
            or end - start != len(text)
            or full[start:end] != text
        ):
            return 0
        return self._add((original.content_hash, name), start, end)
