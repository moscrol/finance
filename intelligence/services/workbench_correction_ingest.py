"""Deterministic, fail-closed text gate for Workbench correction ingestion.

The runtime owns identity and environment guards. This module only inspects the
user text and an explicitly supplied previous assistant message, then appends
through the canonical correction writer when the text is a correction of that
answer rather than a market comment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Mapping

from intelligence.services import corrections

CorrectionStatus = Literal["recorded", "skipped", "failed"]

REASONS = frozenset(
    {
        "no_prior_answer",
        "no_payload",
        "market_commentary",
        "engineering",
        "dedup",
        "recorded",
        "write_failed",
    }
)

_ENGINEERING_TERMS = (
    "pr",
    "分支",
    "commit",
    "pytest",
    "8792",
    "harness",
    "worktree",
    "合入",
    "强推",
)
_REFERENCE_TERMS = ("你", "刚才", "上一条", "这个回答", "上一篇", "你说")
_MARKET_INDICATOR_PATTERN = re.compile(
    r"(?:这波|这轮|今天|大盘|行情|这只|它)$",
)
_DENIAL_PATTERN = re.compile(r"不对|错了|不是这样")
# A question or a hedged guess asks about the market; it does not state how the
# previous answer should have been done. Precision first (design §0: 宁可不记).
_QUESTION_PATTERN = re.compile(r"[？?]|(?:吗|呢|吧|么|嘛)[\s。！!…~～]*$")

# Match only the forms frozen in the correction-loop design (§5.2). A bare
# "应该…" is not one of them: it is also how users ask ("应该怎么看") or guess
# ("应该还有一波"). The canonical positive "不对，应该先…" is covered by the
# denial-prefixed form below.
_PAYLOAD_PATTERNS = (
    re.compile(r"(?:不对|错了|不是这样)\s*[，,:：]?\s*(?:应该是|应该|应为)\s*(?P<correction>.+)$"),
    re.compile(r"你理解错了.*?应为\s*(?P<correction>.+)$"),
    re.compile(r"(?<!不)应该是\s*(?P<correction>.+)$"),
    re.compile(r"(?<!不)应为\s*(?P<correction>.+)$"),
    re.compile(
        r"不是\s*(?P<wrong>[^，,。；;！？!?]{1,80})\s*[，,]?\s*是\s*"
        r"(?P<correction>.+)$"
    ),
)


@dataclass(frozen=True)
class CorrectionIngestResult:
    status: CorrectionStatus
    reason: str
    record_id: str | None = None
    corrected_message_id: str | None = None
    error_type: str | None = None

    def to_trace(self) -> dict[str, object]:
        """Return a privacy-bounded trace payload."""
        payload: dict[str, object] = {
            "status": self.status,
            "reason": self.reason,
            "plane": "user_method",
        }
        if self.record_id:
            payload["id"] = self.record_id
        if self.corrected_message_id:
            payload["corrected_message_id"] = self.corrected_message_id
        if self.error_type:
            payload["error_type"] = self.error_type
        return payload


def _compact(text: object) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _normalize_text(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _trim_payload(text: str) -> str:
    return text.strip(" \t\r\n，,。；;：:！？!?")


def _previous_message_value(
    message: Mapping[str, object] | None,
    key: str,
) -> str:
    if not message:
        return ""
    return str(message.get(key) or "").strip()


def _has_engineering_term(text: str) -> bool:
    compact = _compact(text)
    return any(term in compact for term in _ENGINEERING_TERMS)


def _is_market_commentary(text: str) -> bool:
    match = _DENIAL_PATTERN.search(text)
    if match is None:
        return False
    left = text[: match.start()]
    left = re.sub(r"[\s，,：:]+$", "", left)
    if any(term in left for term in _REFERENCE_TERMS):
        return False
    return bool(_MARKET_INDICATOR_PATTERN.search(left))


def _extract_correction(text: str) -> str | None:
    for pattern in _PAYLOAD_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        correction = _trim_payload(match.group("correction"))
        if correction:
            return correction
    return None


def _parse_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _within_dedup_window(
    path: Path,
    correction: str,
    now: datetime,
) -> bool:
    records, _ = corrections.load_corrections(path, window=0)
    normalized = _compact(correction)
    for record in records:
        if _compact(record.get("correction")) != normalized:
            continue
        created = _parse_timestamp(record.get("ts"))
        if created is None:
            continue
        age = now - created
        if timedelta(0) <= age <= timedelta(hours=24):
            return True
    return False


def maybe_record_workbench_correction(
    path: str | Path,
    *,
    user_text: str,
    previous_assistant: Mapping[str, object] | None,
    conversation_id: str,
    corrected_message_id: str,
    themes: list[str] | tuple[str, ...] = (),
    ts: str | None = None,
) -> CorrectionIngestResult:
    """Append one eligible Workbench correction, or return a bounded skip.

    Runtime identity/environment guards intentionally do not live here. The
    explicit path is the authority boundary and keeps this function directly
    testable with a temporary user root.
    """
    previous_role = _previous_message_value(previous_assistant, "role")
    previous_status = _previous_message_value(previous_assistant, "status")
    previous_content = _previous_message_value(previous_assistant, "content")
    previous_id = _previous_message_value(previous_assistant, "message_id")
    if (
        previous_role != "assistant"
        or previous_status != "completed"
        or not previous_content
        or not previous_id
    ):
        return CorrectionIngestResult("skipped", "no_prior_answer")

    text = _normalize_text(user_text)
    if len(_compact(text)) < 8:
        return CorrectionIngestResult("skipped", "no_payload")
    if _has_engineering_term(text):
        return CorrectionIngestResult("skipped", "engineering")
    if _QUESTION_PATTERN.search(text):
        return CorrectionIngestResult("skipped", "no_payload")

    correction = _extract_correction(text)
    if not correction:
        return CorrectionIngestResult("skipped", "no_payload")
    if _is_market_commentary(text):
        return CorrectionIngestResult("skipped", "market_commentary")

    target = Path(path).expanduser()
    record_ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    now = _parse_timestamp(record_ts)
    if now is None:
        return CorrectionIngestResult("failed", "write_failed", error_type="invalid_timestamp")
    if _within_dedup_window(target, correction, now):
        return CorrectionIngestResult("skipped", "dedup")

    try:
        _, record = corrections.record_correction(
            target,
            correction=correction,
            original=previous_content[:240],
            themes=list(themes),
            ts=record_ts,
            source="workbench_conversation",
            conversation_id=conversation_id,
            corrected_message_id=corrected_message_id or previous_id,
            plane="user_method",
        )
    except Exception as exc:  # fail-open is completed by the runtime caller
        return CorrectionIngestResult(
            "failed",
            "write_failed",
            corrected_message_id=corrected_message_id or previous_id,
            error_type=type(exc).__name__,
        )
    return CorrectionIngestResult(
        "recorded",
        "recorded",
        record_id=str(record["id"]),
        corrected_message_id=corrected_message_id or previous_id,
    )
