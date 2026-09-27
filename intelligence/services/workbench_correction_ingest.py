"""Deterministic, fail-closed text gate for Workbench correction ingestion.

The runtime owns identity and environment guards. This module only inspects the
user text and an explicitly supplied previous assistant message, then appends
through the canonical correction writer when the text is a correction of that
answer rather than a market comment.
"""

from __future__ import annotations

import fcntl
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
_ANSWER_REFERENCE_PATTERN = re.compile(
    r"你(?:刚才|上次|之前)?(?:的)?(?:说|提到|写|判断|理解|回答)|"
    r"(?:刚才|上次|之前)(?:的)?(?:回答|说法|判断|结论)|"
    r"上一(?:条|轮)(?:回答|回复)?|这个回答|上一篇"
)
_LOCAL_METHOD_REFERENCE_PATTERN = re.compile(r"(?:这里|这一步|这一点)\s*$")
_METHOD_PAYLOAD_PATTERN = re.compile(r"先(?:看|核验|核实|确认|验证|检查|区分|比较|分析)")
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
    if _ANSWER_REFERENCE_PATTERN.search(left):
        return False
    return bool(_MARKET_INDICATOR_PATTERN.search(left))


def _extract_correction(text: str, previous_content: str) -> str | None:
    for pattern in _PAYLOAD_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        correction = _trim_payload(match.group("correction"))
        prefix = text[: match.start()]
        wrong = _compact(match.groupdict().get("wrong")).strip("「」『』\"'“”")
        # Payload wording alone also describes a market opinion. Require an
        # answer target: explicit denial/reference, or A actually in the answer.
        # "这里应该是先看…" is a local method correction; "这里应该是退潮" isn't.
        targets_answer = (
            _DENIAL_PATTERN.search(text[: match.start("correction")])
            or _ANSWER_REFERENCE_PATTERN.search(prefix)
            or (wrong and wrong in _compact(previous_content))
            or (
                _LOCAL_METHOD_REFERENCE_PATTERN.search(prefix)
                and _METHOD_PAYLOAD_PATTERN.match(correction)
            )
        )
        if correction and targets_answer:
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
    records, warning = corrections.load_corrections(path, window=0, strict=True)
    if warning:
        raise OSError("correction ledger unavailable")
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

    correction = _extract_correction(text, previous_content)
    if not correction:
        return CorrectionIngestResult("skipped", "no_payload")
    if _is_market_commentary(text):
        return CorrectionIngestResult("skipped", "market_commentary")

    target = Path(path).expanduser()
    record_ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    now = _parse_timestamp(record_ts)
    if now is None:
        return CorrectionIngestResult("failed", "write_failed", error_type="invalid_timestamp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # One inode lock covers both checking and the canonical append. A local
        # threading lock would still race between Workbench worker processes.
        # Closing this handle releases the lock on success, skip, and failure.
        with target.open("a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if _within_dedup_window(target, correction, now):
                return CorrectionIngestResult("skipped", "dedup")
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
