"""Structured episode-issue contract (verifier → release gate).

Gating reads ``Issue.code`` through ``RELEASE_POLICY`` only. ``Issue.message``
is for logs and receipts; changing copy must not change release behavior.

Precedent: ``_CLAIM_POLICY`` in ``episode_semantic_verifier`` is already a
key-keyed dict. This module finishes that pattern for structural/semantic
issues that used to handshake via English prefixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IssueCode(str, Enum):
    """Stable keys for every current producer kind.

    Values are receipt tokens (``code=<value>``). Enum names stay reviewable.
    """

    EVIDENCE_EMPTY_HASH = "evidence_empty_hash"
    EVIDENCE_DUPLICATE_HASH = "evidence_duplicate_hash"
    UNKNOWN_OUTPUT_BINDING = "unknown_output_binding"
    MISSING_REQUIRED_OUTPUT = "missing_required_output"
    GROUNDING_BASIS_MISMATCH = "grounding_basis_mismatch"
    REQUIRED_OUTPUT_GAP = "required_output_gap"
    UNKNOWN_EVIDENCE_HASH = "unknown_evidence_hash"
    AMBIGUOUS_EVIDENCE_HASH = "ambiguous_evidence_hash"
    EVIDENCE_TYPE_STRIPPED = "evidence_type_stripped"
    EVIDENCE_TYPE_UNSUPPORTED = "evidence_type_unsupported"
    FINANCIAL_ANCHOR_MISSING = "financial_anchor_missing"
    MISSING_MANDATORY_CAPABILITY = "missing_mandatory_capability"
    REQUIRED_OUTPUT_NO_SUBSTANCE = "required_output_no_substance"
    NUMERIC_UNSUPPORTED = "numeric_unsupported"
    CALENDAR_WEEKDAY_MISMATCH = "calendar_weekday_mismatch"
    PATH_TREND_MISMATCH = "path_trend_mismatch"
    MARKER_LOSS = "marker_loss"


class ReleaseAction(str, Enum):
    BLOCK = "block"
    PARTIAL_OK = "partial_ok"
    STRIP_OK = "strip_ok"


@dataclass(frozen=True)
class Issue:
    code: IssueCode
    subject: str
    message: str

    def serialize(self) -> str:
        """Human-grepable receipt line. Machines split on the first two fields."""

        return f"code={self.code.value} subject={self.subject} :: {self.message}"


RELEASE_POLICY: dict[IssueCode, ReleaseAction] = {
    IssueCode.EVIDENCE_EMPTY_HASH: ReleaseAction.BLOCK,
    IssueCode.EVIDENCE_DUPLICATE_HASH: ReleaseAction.BLOCK,
    IssueCode.UNKNOWN_OUTPUT_BINDING: ReleaseAction.BLOCK,
    IssueCode.MISSING_REQUIRED_OUTPUT: ReleaseAction.BLOCK,
    IssueCode.GROUNDING_BASIS_MISMATCH: ReleaseAction.BLOCK,
    IssueCode.REQUIRED_OUTPUT_GAP: ReleaseAction.PARTIAL_OK,
    IssueCode.UNKNOWN_EVIDENCE_HASH: ReleaseAction.BLOCK,
    IssueCode.AMBIGUOUS_EVIDENCE_HASH: ReleaseAction.BLOCK,
    IssueCode.EVIDENCE_TYPE_STRIPPED: ReleaseAction.STRIP_OK,
    IssueCode.EVIDENCE_TYPE_UNSUPPORTED: ReleaseAction.PARTIAL_OK,
    IssueCode.FINANCIAL_ANCHOR_MISSING: ReleaseAction.BLOCK,
    IssueCode.MISSING_MANDATORY_CAPABILITY: ReleaseAction.PARTIAL_OK,
    IssueCode.REQUIRED_OUTPUT_NO_SUBSTANCE: ReleaseAction.BLOCK,
    IssueCode.NUMERIC_UNSUPPORTED: ReleaseAction.BLOCK,
    IssueCode.CALENDAR_WEEKDAY_MISMATCH: ReleaseAction.BLOCK,
    IssueCode.PATH_TREND_MISMATCH: ReleaseAction.BLOCK,
    IssueCode.MARKER_LOSS: ReleaseAction.BLOCK,
}

_PARTIAL_RELEASE_ACTIONS = frozenset(
    {ReleaseAction.PARTIAL_OK, ReleaseAction.STRIP_OK}
)


def release_action(code: IssueCode) -> ReleaseAction:
    """Look up release policy. A missing entry is BLOCK (fail closed)."""

    return RELEASE_POLICY.get(code, ReleaseAction.BLOCK)


def allows_partial_release(items: tuple[Issue, ...]) -> bool:
    """True iff every issue is PARTIAL_OK or STRIP_OK.

    An empty tuple is not releasable here; the caller owns the no-issue and
    honest-runtime-partial branches in G11.
    """

    if not items:
        return False
    return all(release_action(item.code) in _PARTIAL_RELEASE_ACTIONS for item in items)


def serialize_issues(items: tuple[Issue, ...]) -> tuple[str, ...]:
    return tuple(item.serialize() for item in items)


# W5：这两种 BLOCK 不是「答案只能越修越薄」，而是缺一次对应能力的取数。
# 映射必须跟 code 走，不能从 message 里抠 capability 名。
BACKFILL_TRIGGER_CODES = frozenset(
    {
        IssueCode.NUMERIC_UNSUPPORTED,
        IssueCode.FINANCIAL_ANCHOR_MISSING,
    }
)
BACKFILL_CAPABILITY_BY_CODE: dict[IssueCode, str] = {
    IssueCode.NUMERIC_UNSUPPORTED: "market_data",
    IssueCode.FINANCIAL_ANCHOR_MISSING: "financial_data",
}


@dataclass(frozen=True)
class BackfillPlan:
    codes: tuple[IssueCode, ...]
    missing_outputs: tuple[str, ...]
    missing_capabilities: tuple[str, ...]


def plan_issue_backfill(items: tuple[Issue, ...]) -> BackfillPlan | None:
    """Return a narrow backfill plan, or None when no trigger code is present."""

    matched = tuple(item for item in items if item.code in BACKFILL_TRIGGER_CODES)
    if not matched:
        return None
    outputs = tuple(
        dict.fromkeys(
            item.subject
            for item in matched
            if item.code == IssueCode.FINANCIAL_ANCHOR_MISSING and item.subject
        )
    )
    capabilities = tuple(
        dict.fromkeys(
            BACKFILL_CAPABILITY_BY_CODE[item.code]
            for item in matched
            if item.code in BACKFILL_CAPABILITY_BY_CODE
        )
    )
    if not capabilities:
        return None
    return BackfillPlan(
        codes=tuple(dict.fromkeys(item.code for item in matched)),
        missing_outputs=outputs,
        missing_capabilities=capabilities,
    )


__all__ = [
    "BACKFILL_CAPABILITY_BY_CODE",
    "BACKFILL_TRIGGER_CODES",
    "BackfillPlan",
    "Issue",
    "IssueCode",
    "RELEASE_POLICY",
    "ReleaseAction",
    "allows_partial_release",
    "plan_issue_backfill",
    "release_action",
    "serialize_issues",
]
