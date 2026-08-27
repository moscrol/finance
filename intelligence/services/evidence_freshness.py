"""证据宿主鲜度体检（KC-20）。

按 evidence_index 的 ``target`` 聚最新 ``source_date``（库里没有 updated_at，
与 ``scripts/check_kb_freshness.py`` 同一口径：不看文件 mtime）。断更超过
``DEFAULT_STALE_DAYS``（45，与 ask 的 ⚠️复核标记同一阈值）且近 7 天有人问过
的宿主进清单——「有人在问但料是旧的」优先补。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping

from intelligence.services.ask_types import DEFAULT_STALE_DAYS

HIT_LOOKBACK_DAYS = 7
REPORT_NAME_PREFIX = "evidence-host-freshness-"
_DATE_RE = re.compile(r"(20\d{2})\D?(\d{2})\D?(\d{2})")


@dataclass(frozen=True)
class HostFreshness:
    host: str
    target_type: str
    latest_source_date: date | None
    age_days: int | None
    item_count: int
    hit_count: int = 0
    last_hit_on: date | None = None

    @property
    def is_stale(self) -> bool:
        return self.age_days is not None and self.age_days > DEFAULT_STALE_DAYS

    @property
    def is_priority_gap(self) -> bool:
        return self.is_stale and self.hit_count > 0


def parse_source_date(raw: object) -> date | None:
    text = str(raw or "")
    match = _DATE_RE.search(text)
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def summarize_hosts(
    items: Iterable[Mapping[str, object]],
    *,
    as_of: date,
    hits: Mapping[str, tuple[int, date | None]] | None = None,
) -> tuple[HostFreshness, ...]:
    grouped: dict[tuple[str, str], list[date]] = defaultdict(list)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for item in items:
        if not isinstance(item, Mapping):
            continue
        host = str(item.get("target") or "").strip()
        if not host:
            continue
        target_type = str(item.get("target_type") or "unknown").strip() or "unknown"
        key = (host, target_type)
        counts[key] += 1
        parsed = parse_source_date(item.get("source_date"))
        if parsed is not None:
            grouped[key].append(parsed)

    rows: list[HostFreshness] = []
    hit_map = hits or {}
    for key, count in counts.items():
        host, target_type = key
        latest = max(grouped[key]) if grouped[key] else None
        age = (as_of - latest).days if latest is not None else None
        hit_count, last_hit = hit_map.get(host, (0, None))
        rows.append(
            HostFreshness(
                host=host,
                target_type=target_type,
                latest_source_date=latest,
                age_days=age,
                item_count=count,
                hit_count=hit_count,
                last_hit_on=last_hit,
            )
        )
    rows.sort(
        key=lambda row: (
            0 if row.is_priority_gap else 1,
            -(row.hit_count),
            -(row.age_days or -1),
            row.host,
        )
    )
    return tuple(rows)


def priority_gaps(rows: Iterable[HostFreshness]) -> tuple[HostFreshness, ...]:
    return tuple(row for row in rows if row.is_priority_gap)


def collect_hits_from_questions(
    questions: Iterable[tuple[str, date]],
    hosts: Iterable[str],
    *,
    as_of: date,
    lookback_days: int = HIT_LOOKBACK_DAYS,
) -> dict[str, tuple[int, date | None]]:
    """问句里出现宿主名即计一次命中。只统计 lookback 窗口内。"""

    names = tuple(dict.fromkeys(name for name in hosts if name))
    start = as_of - timedelta(days=lookback_days)
    tallies: dict[str, list[date]] = defaultdict(list)
    for question, asked_on in questions:
        if asked_on < start or asked_on > as_of:
            continue
        text = str(question or "")
        for host in names:
            if host and host in text:
                tallies[host].append(asked_on)
    return {
        host: (len(dates), max(dates))
        for host, dates in tallies.items()
    }


def collect_hits_from_run_store(
    runs_root: Path,
    hosts: Iterable[str],
    *,
    as_of: date,
    lookback_days: int = HIT_LOOKBACK_DAYS,
) -> dict[str, tuple[int, date | None]]:
    questions: list[tuple[str, date]] = []
    if not runs_root.exists():
        return {}
    for run_json in runs_root.glob("run_*/run.json"):
        try:
            payload = json.loads(run_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        asked_on = _run_date(payload, run_json)
        if asked_on is None:
            continue
        question = str(payload.get("question") or "")
        if question:
            questions.append((question, asked_on))
    return collect_hits_from_questions(
        questions,
        hosts,
        as_of=as_of,
        lookback_days=lookback_days,
    )


def render_freshness_report(
    rows: Iterable[HostFreshness],
    *,
    as_of: date,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> str:
    gaps = priority_gaps(rows)
    lines = [
        f"# 证据宿主鲜度体检 {as_of.isoformat()}",
        "",
        f"阈值：断更 >{stale_days} 天（与 ask 的 ⚠️{stale_days} 天复核标记同一闸）"
        f"且近 {HIT_LOOKBACK_DAYS} 天被问过。日期取 evidence_index.source_date，不看 mtime。",
        "",
        f"优先补（有人在问但料是旧的）：{len(gaps)} 个宿主",
        "",
    ]
    if not gaps:
        lines.append("本窗口没有同时满足断更与近 7 天命中的宿主。")
        lines.append("")
        return "\n".join(lines)
    lines.extend(
        (
            "| 宿主 | 类型 | 最新 source_date | 龄期（天） | 条目 | 近7天命中 | 最近一问 |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        )
    )
    for row in gaps:
        latest = row.latest_source_date.isoformat() if row.latest_source_date else "—"
        last_hit = row.last_hit_on.isoformat() if row.last_hit_on else "—"
        lines.append(
            f"| {row.host} | {row.target_type} | {latest} | {row.age_days} "
            f"| {row.item_count} | {row.hit_count} | {last_hit} |"
        )
    lines.extend(("", f"⚠️{stale_days} 天复核：上表宿主的证据批次已超阈值，优先安排 ingest。", ""))
    return "\n".join(lines)


def report_path(output_dir: Path, as_of: date) -> Path:
    return output_dir / f"{REPORT_NAME_PREFIX}{as_of.isoformat()}.md"


def _run_date(payload: Mapping[str, object], run_json: Path) -> date | None:
    for key in ("source_date", "created_at", "finished_at"):
        parsed = parse_source_date(payload.get(key))
        if parsed is not None:
            return parsed
    match = re.search(r"run_(\d{8})_", run_json.name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None
