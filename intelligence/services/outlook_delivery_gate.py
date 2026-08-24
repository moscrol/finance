"""Public-answer scans for outlook packs. Fail closed: drop the clause."""

from __future__ import annotations

import re

_VERIFY_RE = re.compile(r"(已给部分验证|已经验证|已验证|已兑现|证明剧本|证明了剧本)")
_ANALOG_AS_LIVE_RE = re.compile(r"原文判断|本周剧本")
_ANALOG_OK_RE = re.compile(r"结构类比|analog")
_OLD_MAINLINE_RE = re.compile(r"医药老主线|老主线医药")
_ISSUE_RE = re.compile(r"20\d{2}\.\d{1,2}")


def strip_outlook_violations(
    text: str,
    *,
    live_date: str | None = None,
    live_excerpt: str = "",
    last_mainline_names: tuple[str, ...] = (),
    analog_issue_ids: tuple[str, ...] = (),
) -> str:
    kept: list[str] = []
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
        kept.append(part)
    return "".join(kept)


def _clauses(text: str) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []
    parts = re.split(r"(?<=[。！？\n])", raw)
    return [part for part in parts if part]
