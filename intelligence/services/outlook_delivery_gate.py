"""Public-answer scans for outlook packs. Fail closed: drop the clause."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Sequence

_VERIFY_RE = re.compile(r"(已给部分验证|已经验证|已验证|已兑现|证明剧本|证明了剧本)")
_ANALOG_AS_LIVE_RE = re.compile(r"原文判断|本周剧本")
_ANALOG_OK_RE = re.compile(r"结构类比|analog")
_OLD_MAINLINE_RE = re.compile(r"医药老主线|老主线医药")
_ISSUE_RE = re.compile(r"20\d{2}\.\d{1,2}")
_UNGROUNDED_BAND_RE = re.compile(r"110\s*[–\-〜~到至]\s*120\s*%")


@dataclass(frozen=True)
class OutlookGateReceipt:
    text: str
    dropped: int
    applied: bool


def apply_outlook_delivery_gate(
    text: str,
    *,
    question_type: str,
    evidence: Sequence[Any] = (),
) -> OutlookGateReceipt:
    """拦输出的最后一道：只对 market_forecast 删违规分句。主题题不扩权。"""

    if question_type != "market_forecast":
        return OutlookGateReceipt(text=text, dropped=0, applied=False)
    context = _context_from_evidence(evidence)
    cleaned = strip_outlook_violations(text, **context)
    dropped = max(0, len(_clauses(text)) - len(_clauses(cleaned)))
    return OutlookGateReceipt(text=cleaned, dropped=dropped, applied=True)


def strip_outlook_violations(
    text: str,
    *,
    live_date: str | None = None,
    live_excerpt: str = "",
    last_mainline_names: tuple[str, ...] = (),
    analog_issue_ids: tuple[str, ...] = (),
    grid_text: str = "",
) -> str:
    kept: list[str] = []
    grid = f"{live_excerpt} {grid_text}"
    for part in _clauses(text):
        if _VERIFY_RE.search(part):
            continue
        if _ANALOG_AS_LIVE_RE.search(part) and not _ANALOG_OK_RE.search(part):
            continue
        if analog_issue_ids and any(issue in part for issue in analog_issue_ids):
            if _ANALOG_AS_LIVE_RE.search(part) and not _ANALOG_OK_RE.search(part):
                continue
            if "原文判断" in part:
                continue
        if (
            _OLD_MAINLINE_RE.search(part)
            and any("医药" in name or "药" in name for name in last_mainline_names)
            and ("新主线" in live_excerpt or "断代" in live_excerpt)
        ):
            continue
        if live_date and _ISSUE_RE.search(part) and "原文判断" in part and not _ANALOG_OK_RE.search(part):
            continue
        if _UNGROUNDED_BAND_RE.search(part) and not _UNGROUNDED_BAND_RE.search(grid):
            continue
        kept.append(part)
    return "".join(kept)


def _context_from_evidence(evidence: Sequence[Any]) -> dict[str, Any]:
    live_date = None
    live_excerpt = ""
    analog_ids: list[str] = []
    mainline: list[str] = []
    grid_parts: list[str] = []
    for item in evidence:
        source = _field(item, "source")
        title = _field(item, "title")
        detail = _field(item, "detail")
        date = _field(item, "source_date") or _field(item, "date")
        if title or detail:
            grid_parts.append(f"{title} {detail}")
        if source == "live_weekly" or title.startswith("活周报"):
            live_date = date or live_date
            live_excerpt = detail
        if source == "analog" or title.startswith("analog"):
            analog_ids.extend(_ISSUE_RE.findall(f"{title} {detail}"))
        if title.endswith("四袋") and "主线" in detail:
            mainline.extend(
                name for name in ("医药", "药", "有色") if name in detail
            )
    return {
        "live_date": live_date,
        "live_excerpt": live_excerpt,
        "last_mainline_names": tuple(dict.fromkeys(mainline)),
        "analog_issue_ids": tuple(dict.fromkeys(analog_ids)),
        "grid_text": " ".join(grid_parts),
    }


def _field(item: Any, name: str) -> str:
    if isinstance(item, dict):
        return str(item.get(name) or "")
    return str(getattr(item, name, "") or "")


def _clauses(text: str) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []
    parts = re.split(r"(?<=[。！？\n])", raw)
    return [part for part in parts if part]
