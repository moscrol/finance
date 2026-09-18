"""Additive research-quality disclosure; never a publication permission grant.

Callers must sanitize body, snippets and notes at their own security boundary.
The renderer has no IO and never deletes, rewrites or truncates the body.
"""
from __future__ import annotations

from collections.abc import Iterable

RESEARCH_REVIEW_HEADING = "### 核验批注（分析保留，不代表已证实）"


def annotate_research_answer(body: str, notes: Iterable[str] = ()) -> str:
    unique = tuple(dict.fromkeys(str(note).strip() for note in notes if str(note).strip()))
    if not unique:
        return body
    notice = RESEARCH_REVIEW_HEADING + "\n" + "\n".join(f"- {note}" for note in unique)
    return "\n\n".join(part for part in (body, notice) if part)


def append_research_supplement(body: str, supplement: str) -> str:
    """Attach a correction/coverage attempt without granting it overwrite rights.

    Both arguments must already have crossed the caller's security boundary.
    No fuzzy text diff: it could erase qualifiers or pair the wrong sentences.
    """
    if not supplement.strip() or supplement.strip() == body.strip():
        return body
    if not body.strip() or supplement.startswith(body):
        return supplement
    return "\n\n".join(part for part in (
        body, "### 补充与修订（原分析保留）\n" + supplement,
    ) if part)


def research_body_for_validation(public: str, notes: Iterable[str]) -> str:
    """Exclude only this runtime's exact appendix from answer-slot validation.

    A model-written heading alone never grants an exemption. If a later
    sanitizer changed the appendix we conservatively keep it for validation.
    This helper changes the validation copy, never the delivered report.
    """
    appendix = annotate_research_answer("", notes)
    suffix = "\n\n" + appendix
    if appendix and public.endswith(suffix):
        return public[:-len(suffix)]
    return public
