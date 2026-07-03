"""题材催化剂归因：为触发题材回答"推动它的是什么"。

盘面触发只说明"题材动了"，不说明"为什么动"。本服务把研究任务队列里的每个题材
对照两条叙事线做归因：

1. 卖方观点事件（知识库 ``wiki/raw/theme-radar/opinion-store/opinion-events.jsonl``）
2. 晨汇（知识库 ``wiki/briefings/<date>.md``）

命中 = 叙事驱动（产业/研报催化在先，盘面是预期扩散）；
未命中 = 纯盘面异动（无叙事支撑，研究路径不同，先确认是否有场外产业事件）。

归因是只读的：不改判级、不降级，只补充"驱动来源"字段供人工判断。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Any


STATUS_NARRATIVE_HIT = "narrative_hit"
STATUS_MARKET_ONLY = "market_only"
STATUS_SOURCE_MISSING = "source_missing"

STATUS_LABELS = {
    STATUS_NARRATIVE_HIT: "叙事驱动",
    STATUS_MARKET_ONLY: "纯盘面异动",
    STATUS_SOURCE_MISSING: "叙事源缺失",
}

DEFAULT_WINDOW_DAYS = 5
MAX_EVENTS_PER_THEME = 3
_EXCERPT_MAX_CHARS = 80

OPINION_EVENTS_RELPATH = Path("raw/theme-radar/opinion-store/opinion-events.jsonl")
BRIEFINGS_RELPATH = Path("briefings")


@dataclass
class CatalystIndex:
    market_date: str
    window_days: int
    opinion_events: list[dict[str, Any]] = field(default_factory=list)
    briefing_lines: list[tuple[str, str]] = field(default_factory=list)
    opinion_source_available: bool = False
    briefing_dates_found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def sources_available(self) -> bool:
        return self.opinion_source_available or bool(self.briefing_dates_found)


def build_catalyst_index(
    kb_wiki: str | Path,
    market_date: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> CatalystIndex:
    wiki = Path(kb_wiki).expanduser()
    index = CatalystIndex(market_date=market_date, window_days=window_days)
    window_dates = _window_dates(market_date, window_days)
    if not window_dates:
        index.warnings.append(f"无法解析日期 {market_date}，催化归因跳过。")
        return index

    events_path = wiki / OPINION_EVENTS_RELPATH
    if events_path.is_file():
        index.opinion_source_available = True
        index.opinion_events = _load_opinion_events(events_path, set(window_dates), index.warnings)
    else:
        index.warnings.append(f"卖方观点事件缺失：{events_path}")

    briefings_dir = wiki / BRIEFINGS_RELPATH
    for day in window_dates:
        briefing = briefings_dir / f"{day}.md"
        if not briefing.is_file():
            continue
        index.briefing_dates_found.append(day)
        index.briefing_lines.extend((day, line) for line in _significant_lines(briefing, index.warnings))
    if not index.briefing_dates_found:
        index.warnings.append(f"窗口 {window_dates[-1]}~{window_dates[0]} 内无晨汇：{briefings_dir}")
    return index


def freshness_problems(
    kb_wiki: str | Path,
    market_date: str,
    *,
    briefing_max_age_days: int = 1,
    opinion_max_age_days: int = 3,
) -> list[str]:
    """叙事源时效自检：晨汇/卖方观点断更时第一时间报出来，不等归因变盲区才发现。"""
    wiki = Path(kb_wiki).expanduser()
    problems: list[str] = []
    try:
        anchor = date_cls.fromisoformat(str(market_date))
    except ValueError:
        return [f"无法解析日期 {market_date}，叙事源时效检查跳过"]

    briefings_dir = wiki / BRIEFINGS_RELPATH
    latest_briefing = max(
        (p.stem for p in briefings_dir.glob("????-??-??.md")),
        default="",
    ) if briefings_dir.is_dir() else ""
    if not latest_briefing:
        problems.append(f"晨汇目录缺失或为空：{briefings_dir}")
    else:
        try:
            age = (anchor - date_cls.fromisoformat(latest_briefing)).days
        except ValueError:
            age = None
        if age is not None and age > briefing_max_age_days:
            problems.append(
                f"晨汇断更：最新 {latest_briefing}，距 {market_date} 已 {age} 天（阈值 {briefing_max_age_days} 天）；"
                "催化归因会缺档，建议先补当日晨汇"
            )

    events_path = wiki / OPINION_EVENTS_RELPATH
    if not events_path.is_file():
        problems.append(f"卖方观点事件缺失：{events_path}")
    else:
        latest_event = ""
        scratch: list[str] = []
        for event in _load_opinion_events(events_path, window_dates=None, warnings=scratch):
            event_date = str(event.get("report_date") or event.get("ingested_at") or "")
            if event_date > latest_event:
                latest_event = event_date
        try:
            age = (anchor - date_cls.fromisoformat(latest_event)).days if latest_event else None
        except ValueError:
            age = None
        if age is None:
            problems.append(f"卖方观点事件无法解析最新日期：{events_path}")
        elif age > opinion_max_age_days:
            problems.append(
                f"卖方观点事件断更：最新 {latest_event}，距 {market_date} 已 {age} 天（阈值 {opinion_max_age_days} 天）；"
                "建议先跑晚间研报 ingest 再复盘"
            )
    return problems


def attribute_theme(
    index: CatalystIndex,
    theme: str,
    strong_stocks: list[str] | None = None,
) -> dict[str, Any]:
    theme = str(theme or "").strip()
    stocks = [str(item).strip() for item in (strong_stocks or []) if str(item).strip()]
    events: list[dict[str, Any]] = []

    for event in index.opinion_events:
        matched_by = _match_opinion_event(event, theme, stocks)
        if not matched_by:
            continue
        events.append(
            {
                "date": event.get("report_date") or event.get("ingested_at") or "-",
                "source_type": "sellside_opinion",
                "source": event.get("source") or event.get("report_title") or "-",
                "excerpt": _event_excerpt(event),
                "stance": event.get("stance") or "-",
                "matched_by": matched_by,
            }
        )

    for day, line in index.briefing_lines:
        matched_by = _match_line(line, theme, stocks)
        if not matched_by:
            continue
        events.append(
            {
                "date": day,
                "source_type": "morning_briefing",
                "source": f"晨汇 {day}",
                "excerpt": _clip(line),
                "stance": "-",
                "matched_by": matched_by,
            }
        )

    events.sort(key=lambda item: (str(item.get("date") or ""), item.get("source_type") == "sellside_opinion"), reverse=True)
    events = events[:MAX_EVENTS_PER_THEME]

    if events:
        status = STATUS_NARRATIVE_HIT
    elif index.sources_available:
        status = STATUS_MARKET_ONLY
    else:
        status = STATUS_SOURCE_MISSING
    return {
        "status": status,
        "label": STATUS_LABELS[status],
        "window_days": index.window_days,
        "events": events,
        "summary": _summary(status, events),
    }


def enrich_research_queue(index: CatalystIndex, queue: dict[str, Any]) -> None:
    for key in ("today_do_ima", "today_find_official_evidence", "today_wait_market_validation", "today_downgrade_or_watch"):
        for item in queue.get(key) or []:
            item["催化归因"] = attribute_theme(index, item.get("目标") or "", item.get("强势股") or [])


def enrich_kb_ingest_queue(index: CatalystIndex, queue: dict[str, Any]) -> None:
    for task in queue.get("tasks") or []:
        task["catalyst"] = attribute_theme(index, task.get("theme") or "", task.get("strong_stocks") or [])


def catalyst_brief(catalyst: dict[str, Any] | None) -> str:
    if not catalyst:
        return "-"
    label = str(catalyst.get("label") or "-")
    events = list(catalyst.get("events") or [])
    if not events:
        return label
    first = events[0]
    return f"{label}（{first.get('date', '-')} {first.get('source', '-')}：{first.get('excerpt', '-')}）"


def _summary(status: str, events: list[dict[str, Any]]) -> str:
    if status == STATUS_NARRATIVE_HIT:
        first = events[0]
        return f"驱动在叙事端：{first.get('date', '-')} {first.get('source', '-')}｜{first.get('excerpt', '-')}"
    if status == STATUS_MARKET_ONLY:
        return "研报/晨汇窗口内未命中催化；先确认是否有场外产业事件，再决定研究路径。"
    return "叙事源（研报观点/晨汇）本身缺失，无法归因；先补数据源。"


def _window_dates(market_date: str, window_days: int) -> list[str]:
    try:
        anchor = date_cls.fromisoformat(str(market_date))
    except ValueError:
        return []
    return [(anchor - timedelta(days=offset)).isoformat() for offset in range(max(1, window_days))]


def _load_opinion_events(path: Path, window_dates: set[str] | None, warnings: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                event_date = str(event.get("report_date") or event.get("ingested_at") or "")
                if window_dates is None or event_date in window_dates:
                    events.append(event)
    except OSError as exc:
        warnings.append(f"读取卖方观点事件失败：{exc}")
    return events


def _significant_lines(path: Path, warnings: list[str]) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"读取晨汇失败：{exc}")
        return []
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("#-*>|").strip()
        if len(line) >= 6:
            lines.append(line)
    return lines


def _match_opinion_event(event: dict[str, Any], theme: str, stocks: list[str]) -> str:
    term = str(event.get("term") or "")
    concept = str(event.get("concept") or "")
    if theme and (_terms_overlap(theme, term) or _terms_overlap(theme, concept)):
        return f"题材词：{theme}"
    target = str(event.get("target") or "")
    if target and target in stocks:
        return f"强势股：{target}"
    return ""


def _match_line(line: str, theme: str, stocks: list[str]) -> str:
    if theme and theme in line:
        return f"题材词：{theme}"
    for stock in stocks:
        if stock in line:
            return f"强势股：{stock}"
    return ""


def _terms_overlap(theme: str, term: str) -> bool:
    if not theme or not term:
        return False
    return theme in term or term in theme


def _event_excerpt(event: dict[str, Any]) -> str:
    for key in ("catalysts", "hard_evidence", "soft_claims"):
        values = event.get(key)
        if isinstance(values, list) and values:
            return _clip(str(values[0]))
    return _clip(str(event.get("report_title") or event.get("concept") or event.get("term") or "-"))


def _clip(text: str) -> str:
    text = " ".join(str(text).split())
    if len(text) <= _EXCERPT_MAX_CHARS:
        return text
    return text[: _EXCERPT_MAX_CHARS - 1] + "…"
