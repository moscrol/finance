"""Public-answer quality scans: retain analysis and disclose doubtful clauses."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Sequence

from intelligence.services.research_annotations import annotate_research_answer

_VERIFY_RE = re.compile(r"(已给部分验证|已经验证|已验证|已兑现|证明剧本|证明了剧本)")
_ANALOG_AS_LIVE_RE = re.compile(r"原文判断|本周剧本")
_ANALOG_OK_RE = re.compile(r"结构类比|analog")
_OLD_MAINLINE_RE = re.compile(r"医药老主线|老主线医药")
_ISSUE_RE = re.compile(r"20\d{2}\.\d{1,2}")
_UNGROUNDED_BAND_RE = re.compile(r"110\s*[–\-〜~到至]\s*120\s*%")
_MA20_RE = re.compile(r"MA\s*20", re.IGNORECASE)
_FLAG_HOLD_RE = re.compile(r"旗型蓄能")
# market_watch 残差/正文里的方法阈值语言：注册与否以本轮网格（包渲染/证据）
# 为准，网格里没有的整句删（R-20260824-04，盘面包 spec §7.4 #10）。
_WATCH_METHOD_RES: tuple[re.Pattern[str], ...] = (
    _UNGROUNDED_BAND_RE,
    _MA20_RE,
    _FLAG_HOLD_RE,
)


@dataclass(frozen=True)
class OutlookGateReceipt:
    text: str
    dropped: int
    applied: bool
    annotated: int = 0


def apply_outlook_delivery_gate(
    text: str,
    *,
    question_type: str,
    evidence: Sequence[Any] = (),
) -> OutlookGateReceipt:
    """Only forecast answers receive outlook-specific quality annotations."""

    if question_type != "market_forecast":
        return OutlookGateReceipt(text=text, dropped=0, applied=False)
    context = _context_from_evidence(evidence)
    violations = _outlook_violations(text, **context)
    return OutlookGateReceipt(
        text=_annotate_outlook(text, violations), dropped=0, applied=True,
        annotated=len(violations),
    )


def apply_market_watch_delivery_gate(
    text: str,
    *,
    question_type: str,
    grid_text: str = "",
) -> OutlookGateReceipt:
    """Unregistered method thresholds stay visible as unverified proposals."""

    if question_type != "market_watch":
        return OutlookGateReceipt(text=text, dropped=0, applied=False)
    grid = str(grid_text or "")
    parts = _clauses(text)
    doubtful = [
        part for part in parts
        if any(pattern.search(part) and not pattern.search(grid) for pattern in _WATCH_METHOD_RES)
    ]
    return OutlookGateReceipt(
        text=annotate_research_answer(text, (
            "盘面分析含本轮证据未登记的方法或阈值；相关条件保留为待验证设想，不代表已验证规律。",
        ) if doubtful else ()),
        dropped=0, applied=True, annotated=len(doubtful),
    )


def evidence_grid_text(evidence: Sequence[Any]) -> str:
    """把证据条目折成网格文本，供删句闸判「注册与否」。"""

    return str(_context_from_evidence(evidence)["grid_text"])


def strip_outlook_violations(text: str, **context: Any) -> str:
    """Compatibility name; findings no longer have deletion rights."""
    return _annotate_outlook(text, _outlook_violations(text, **context))


def _annotate_outlook(text: str, violations: tuple[str, ...]) -> str:
    return annotate_research_answer(text, (
        "前瞻分析含未经支持的验证、时点或阈值表述；相关分析保留，不能当作当期观察或已经兑现的结论。",
    ) if violations else ())


def _outlook_violations(
    text: str,
    *,
    live_date: str | None = None,
    live_excerpt: str = "",
    last_mainline_names: tuple[str, ...] = (),
    analog_issue_ids: tuple[str, ...] = (),
    grid_text: str = "",
) -> tuple[str, ...]:
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
    return tuple(part for part in _clauses(text) if part not in kept)


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
