"""读向一致性闸：对照注册 ``diff_ratio`` 符号，影子记账不改稿。

P0（R-20260825-12）。语义验证器只核数字是否注册过；本闸核「放量/缩量」
这类方向词有没有贴反。门控唯一条款：本轮观察值含 ``metric="diff_ratio"``。
认不出就 skip；异常回空，不杀 run。不看 ``question_type``。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
from typing import Any

from intelligence.services.agent_research import StructuredObservation

# 词典冻结。扩词必须带新夹具，不改正则骨架。
# 放量/缩量 = 日环比边际量（diff_ratio）符号，不是 20 日均额比。
_DIRECTION_WORDS: tuple[tuple[str, str], ...] = (
    ("边际量转正", "+"),
    ("边际量转负", "-"),
    ("量能放大", "+"),
    ("量能萎缩", "-"),
    ("放量", "+"),
    ("缩量", "-"),
    ("转正", "+"),
    ("转负", "-"),
)
_NEGATION = ("并未", "没有", "尚未", "未见")
_CONDITIONAL = ("如果", "若", "将", "能否", "等待", "预计")
_QUOTE_PAIRS = (("「", "」"), ("『", "』"), ('"', '"'), ("“", "”"))
_STANDING_RE = re.compile(r"当日|站立日")
_ISO_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_CN_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")
_MD_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)")
_SENTENCE_RE = re.compile(r"(?<=[。；\n])")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_STRIP_TOKENS = (
    "当日",
    "站立日",
    "连续",
    "两天",
    "下跌",
    "续跌",
    "回踩",
    "回升",
    "脉冲",
    "第一次",
    "分歧",
    "阴跌",
    "大涨",
    "双红",
    "止跌",
)


@dataclass(frozen=True)
class DirectionMismatch:
    subject: str
    date: str
    word: str
    registered_sign: str
    registered_value: float
    excerpt: str


@dataclass(frozen=True)
class ReadingDirectionGateReceipt:
    text: str
    applied: bool
    checked: int
    skipped: int
    mismatches: tuple[DirectionMismatch, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "skipped": self.skipped,
            "mismatches": [
                {
                    "subject": item.subject,
                    "date": item.date,
                    "word": item.word,
                    "registered_sign": item.registered_sign,
                    "registered_value": item.registered_value,
                    "excerpt": item.excerpt,
                }
                for item in self.mismatches
            ],
        }


def apply_reading_direction_gate(
    text: str,
    *,
    observations: Sequence[StructuredObservation] = (),
    standing: str | None = None,
) -> ReadingDirectionGateReceipt:
    """影子闸。不改稿、不看题型。门关（无 diff_ratio）不 applied。"""

    raw = str(text or "")
    try:
        registry = _diff_ratio_registry(observations)
        if not registry:
            return _closed(raw)
        standing_day = str(standing or "")[:10] or None
        checked = 0
        skipped = 0
        mismatches: list[DirectionMismatch] = []
        for clause in _clauses(raw):
            hits = _direction_hits(clause)
            if not hits:
                continue
            if _should_skip_clause(clause, hits, standing_day):
                skipped += 1
                continue
            word, claimed = hits[0]
            dates = _extract_dates(clause, standing_day)
            if len(dates) != 1:
                skipped += 1
                continue
            subject = _anchor_subject(clause, registry)
            if subject is None:
                skipped += 1
                continue
            observed = registry.get((subject, dates[0]))
            if observed is None or observed == 0:
                skipped += 1
                continue
            sign = "+" if observed > 0 else "-"
            checked += 1
            if sign != claimed:
                mismatches.append(
                    DirectionMismatch(
                        subject=subject,
                        date=dates[0],
                        word=word,
                        registered_sign=sign,
                        registered_value=observed,
                        excerpt=_excerpt(clause, word),
                    )
                )
        return ReadingDirectionGateReceipt(
            text=raw,
            applied=True,
            checked=checked,
            skipped=skipped,
            mismatches=tuple(mismatches),
        )
    except Exception:
        return _closed(raw)


def collect_direction_observations(*sources: Any) -> tuple[StructuredObservation, ...]:
    """从 evidence / private_artifact / PrefetchItem 收集观察值。认不出就跳过。"""

    found: list[StructuredObservation] = []
    seen: set[tuple[str, str, str, float]] = set()

    def add(obs: StructuredObservation) -> None:
        key = (obs.subject, obs.as_of, obs.metric, obs.value)
        if key in seen:
            return
        seen.add(key)
        found.append(obs)

    def from_mapping(item: dict[str, Any]) -> None:
        if {"subject", "as_of", "metric", "value"} <= item.keys():
            try:
                add(
                    StructuredObservation(
                        subject=str(item["subject"]),
                        as_of=str(item["as_of"])[:10],
                        metric=str(item["metric"]),
                        value=float(item["value"]),
                    )
                )
            except (TypeError, ValueError):
                pass
        for nested in item.get("observations") or ():
            if isinstance(nested, StructuredObservation):
                add(nested)
            elif isinstance(nested, dict):
                from_mapping(nested)

    def walk(source: Any) -> None:
        if source is None:
            return
        if isinstance(source, StructuredObservation):
            add(source)
            return
        if isinstance(source, dict):
            if "metric" in source and "subject" in source:
                from_mapping(source)
            for item in source.get("evidence") or ():
                walk(item)
            for item in source.get("observations") or ():
                walk(item)
            return
        if isinstance(source, (list, tuple)):
            for item in source:
                walk(item)
            return
        for obs in getattr(source, "observations", ()) or ():
            walk(obs)
        evidence = getattr(source, "evidence", None)
        if evidence:
            walk(evidence)
        private = getattr(source, "private_artifact", None)
        if isinstance(private, dict):
            walk(private.get("evidence"))

    for source in sources:
        walk(source)
    return tuple(found)


def _closed(text: str) -> ReadingDirectionGateReceipt:
    return ReadingDirectionGateReceipt(
        text=text,
        applied=False,
        checked=0,
        skipped=0,
        mismatches=(),
    )


def _diff_ratio_registry(
    observations: Sequence[StructuredObservation],
) -> dict[tuple[str, str], float]:
    registry: dict[tuple[str, str], float] = {}
    for obs in observations:
        if obs.metric != "diff_ratio":
            continue
        registry[(obs.subject, str(obs.as_of)[:10])] = float(obs.value)
    return registry


def _clauses(text: str) -> list[str]:
    parts: list[str] = []
    for sentence in _SENTENCE_RE.split(text):
        if not sentence:
            continue
        parts.extend(piece for piece in sentence.split("，") if piece)
    return parts


def _direction_hits(clause: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    consumed = [False] * len(clause)
    index = 0
    while index < len(clause):
        if consumed[index]:
            index += 1
            continue
        matched = None
        for word, sign in _DIRECTION_WORDS:
            if clause.startswith(word, index):
                matched = (word, sign)
                break
        if matched is None:
            index += 1
            continue
        word, sign = matched
        hits.append((word, sign))
        for pos in range(index, index + len(word)):
            consumed[pos] = True
        index += len(word)
    return hits


def _should_skip_clause(
    clause: str,
    hits: list[tuple[str, str]],
    standing: str | None,
) -> bool:
    if len({sign for _word, sign in hits}) > 1:
        return True
    quotes = _quote_spans(clause)
    for word, _sign in hits:
        start = clause.find(word)
        if start >= 0 and _in_spans(start, quotes):
            return True
    if any(marker in clause for marker in _NEGATION):
        return True
    if any(marker in clause for marker in _CONDITIONAL):
        return True
    dates = _extract_dates(clause, standing)
    return len(dates) >= 2


def _quote_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for left, right in _QUOTE_PAIRS:
        start = None
        for index, char in enumerate(text):
            if char == left and start is None:
                start = index
            elif char == right and start is not None:
                spans.append((start, index + 1))
                start = None
    return spans


def _in_spans(index: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def _extract_dates(clause: str, standing: str | None) -> list[str]:
    dates: list[str] = []
    masked = clause
    for match in _ISO_DATE_RE.finditer(clause):
        dates.append(match.group())
        masked = masked.replace(match.group(), " ")
    for match in _CN_DATE_RE.finditer(masked):
        resolved = _with_year(int(match.group(1)), int(match.group(2)), standing)
        if resolved:
            dates.append(resolved)
    masked = _CN_DATE_RE.sub(" ", masked)
    for match in _MD_DATE_RE.finditer(masked):
        month, day = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            resolved = _with_year(month, day, standing)
            if resolved:
                dates.append(resolved)
    if _STANDING_RE.search(clause) and standing:
        dates.append(standing)
    return list(dict.fromkeys(dates))


def _with_year(month: int, day: int, standing: str | None) -> str:
    if not standing or len(standing) < 4:
        return ""
    return f"{standing[:4]}-{month:02d}-{day:02d}"


def _anchor_subject(
    clause: str,
    registry: dict[tuple[str, str], float],
) -> str | None:
    subjects = {subject for subject, _date in registry}
    residue = _strip_for_subject(clause)
    candidates: list[str] = []
    for run in _CJK_RUN_RE.findall(residue):
        for start in range(len(run)):
            for end in range(start + 2, len(run) + 1):
                token = run[start:end]
                if token in subjects:
                    candidates.append(token)
    if not candidates:
        return None
    longest = max(len(item) for item in candidates)
    top = {item for item in candidates if len(item) == longest}
    if len(top) != 1:
        return None
    return next(iter(top))


def _strip_for_subject(clause: str) -> str:
    stripped = clause
    for start, end in reversed(_quote_spans(clause)):
        stripped = stripped[:start] + " " + stripped[end:]
    for word, _sign in _DIRECTION_WORDS:
        stripped = stripped.replace(word, " ")
    for token in _STRIP_TOKENS:
        stripped = stripped.replace(token, " ")
    stripped = _ISO_DATE_RE.sub(" ", stripped)
    stripped = _CN_DATE_RE.sub(" ", stripped)
    stripped = _MD_DATE_RE.sub(" ", stripped)
    return stripped


def _excerpt(clause: str, word: str) -> str:
    clipped = clause.strip()
    if len(clipped) <= 40:
        return clipped
    index = clipped.find(word)
    if index < 0:
        return clipped[:40]
    start = max(0, index - 12)
    return clipped[start : start + 40]
