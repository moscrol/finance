"""第三个源：知识库的卖方观点事件文件 → 板块锚点（创始人 09-08：「卖方事件文件让 ev 直接消费」）。

文件是 ``<kb_wiki>/raw/theme-radar/opinion-store/opinion-events.jsonl``（你的 agent 从晚间卖方研报投影出来的结构化事件，
一条观点一行：``report_date`` / ``ingested_at`` / ``concept`` / ``hardness`` / ``stance`` / ``target`` …）。这里不读正文、
不做模糊匹配、不猜概念属于哪个板块：**概念名与板块名精确相同**才成板块事件，其余概念记缺口 ``concept_not_sector``。

一条锚点 = 一个「概念 × 报告日」满足该类的 ``narrative.select``：

- ``hard_evidence``：当天该概念至少 ``min_events`` 条 ``hardness = 硬证据`` 的观点（订单 / 产能 / 招标这种可核的东西）；
- ``first_mention``：该概念在整个文件里第一次出现的那天（新叙事）——文件起点之后 ``burn_in_days`` 个交易日内的「首提」
  只是文件刚开始记录，不是叙事刚出现，记缺口 ``first_mention_in_burn_in``，不入锚点。

反应日按类的 ``reaction_rule``（晚间研报 → 次一交易日）。板块代码按**反应日当天有价格序列**的那个代码取（07-27 板块宇宙
从 ``.TI`` 换成 ``.FP``，同名两套代码；都覆盖时取历史更长的那套），当天哪套都没有 → 缺口 ``no_sector_series_on_day``。
``ingested_at`` 是我们入库的日子，普遍滞后报告日一周以上：写进日历行的 ``title_sample`` 与构建元数据（``ingest_lag_days``），
回放时按需过滤；锚点日本身按报告日算——研报当晚就公开了，滞后的是我们。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .classify import ClassifiedEvent, ClassifyGap
from .params import EventParams

HARD_EVIDENCE = "硬证据"
BULLISH = "看多"

GAP_SOURCE_ABSENT = "source_absent"
GAP_SOURCE_STALE = "source_stale"
GAP_CONCEPT_NOT_SECTOR = "concept_not_sector"
GAP_NO_SERIES_ON_DAY = "no_sector_series_on_day"
GAP_FIRST_MENTION_BURN_IN = "first_mention_in_burn_in"
GAP_ROW_UNUSABLE = "row_unusable"


@dataclass(frozen=True)
class OpinionRow:
    event_id: str
    report_date: str
    ingested_at: str | None
    concept: str
    hardness: str | None
    stance: str | None


@dataclass(frozen=True)
class SectorSeries:
    """一套板块代码在主库里有价格的日期范围。"""

    ts_code: str
    first_day: date
    last_day: date

    def covers(self, day: date) -> bool:
        return self.first_day <= day <= self.last_day


SectorResolver = Callable[[str, date], str | None]


def load_opinion_events(kb_wiki: str | Path, relpath: str) -> tuple[list[OpinionRow], list[ClassifyGap]]:
    """读事件文件；缺 ``report_date`` / ``concept`` 的行记 ``row_unusable``，不猜。文件不存在返回空列表（调用方记 source_absent）。"""
    path = Path(kb_wiki).expanduser() / relpath
    if not path.is_file():
        return [], []
    rows: list[OpinionRow] = []
    gaps: list[ClassifyGap] = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                gaps.append(ClassifyGap(f"line:{n}", "", GAP_ROW_UNUSABLE, "not json"))
                continue
            rd = str(raw.get("report_date") or "").strip()
            concept = str(raw.get("concept") or "").strip()
            try:
                date.fromisoformat(rd)
            except ValueError:
                rd = ""
            if not rd or not concept:
                gaps.append(ClassifyGap(str(raw.get("event_id") or f"line:{n}"), rd, GAP_ROW_UNUSABLE, "missing report_date or concept"))
                continue
            rows.append(
                OpinionRow(
                    event_id=str(raw.get("event_id") or f"line:{n}"),
                    report_date=rd,
                    ingested_at=(str(raw["ingested_at"]) if raw.get("ingested_at") else None),
                    concept=concept,
                    hardness=(str(raw["hardness"]) if raw.get("hardness") else None),
                    stance=(str(raw["stance"]) if raw.get("stance") else None),
                )
            )
    return rows, gaps


def sector_resolver(series_by_name: Mapping[str, Sequence[SectorSeries]]) -> SectorResolver:
    """名字 → 反应日当天有序列的代码；同名多套都覆盖时取历史更长（first_day 更早）的那套。"""

    def resolve(name: str, day: date) -> str | None:
        candidates = [s for s in series_by_name.get(name, ()) if s.covers(day)]
        if not candidates:
            return None
        return min(candidates, key=lambda s: (s.first_day, s.ts_code)).ts_code

    return resolve


def _next_trading_day(after: date, trading_days: Sequence[date]) -> date | None:
    for d in trading_days:
        if d > after:
            return d
    return None


def narrative_events(
    rows: Sequence[OpinionRow],
    params: EventParams,
    trading_days: Sequence[date],
    resolve: SectorResolver,
    sector_names: set[str],
) -> tuple[list[ClassifiedEvent], list[ClassifyGap], dict[str, Any]]:
    """概念 × 报告日 → 各 narrative 类的事件（一条观点一条 ``ClassifiedEvent``，日历层按 (类, 概念, 反应日) 合并）。

    返回 (events, gaps, stats)。gaps 的 event_id 在概念级缺口里就是概念名（一个概念一条，detail 是条数）。
    """
    by_key: dict[tuple[str, str], list[OpinionRow]] = defaultdict(list)
    for r in rows:
        by_key[(r.concept, r.report_date)].append(r)
    first_seen: dict[str, str] = {}
    for concept, rd in sorted(by_key):
        first_seen.setdefault(concept, rd)
    file_start = min((r.report_date for r in rows), default=None)
    burn_in_end: dict[int, date | None] = {}
    concept_counts = Counter(r.concept for r in rows)
    unmatched = {c: n for c, n in concept_counts.items() if c not in sector_names}

    events: list[ClassifiedEvent] = []
    gaps: list[ClassifyGap] = [
        ClassifyGap(concept, "", GAP_CONCEPT_NOT_SECTOR, f"events={n}") for concept, n in sorted(unmatched.items())
    ]
    stats_by_class: dict[str, Counter[str]] = {c: Counter() for c in params.narrative_classes}

    for cls in params.narrative_classes:
        spec = params.classes[cls]
        if spec.narrative_burn_in_days not in burn_in_end:
            if file_start is None:
                burn_in_end[spec.narrative_burn_in_days] = None
            else:
                start = date.fromisoformat(file_start)
                later = [d for d in trading_days if d >= start]
                k = spec.narrative_burn_in_days
                burn_in_end[spec.narrative_burn_in_days] = later[k] if k < len(later) else (later[-1] if later else start)
        for (concept, rd), group in sorted(by_key.items()):
            if concept not in sector_names:
                continue
            n_hard = sum(1 for r in group if r.hardness == HARD_EVIDENCE)
            n_bull = sum(1 for r in group if r.stance == BULLISH)
            if spec.narrative_select == "hard_evidence":
                if n_hard < spec.narrative_min_events:
                    continue
            elif spec.narrative_select == "first_mention":
                if first_seen.get(concept) != rd:
                    continue
                end = burn_in_end[spec.narrative_burn_in_days]
                if end is not None and date.fromisoformat(rd) < end:
                    gaps.append(ClassifyGap(f"{cls}:{concept}", rd, GAP_FIRST_MENTION_BURN_IN, f"burn_in_until={end.isoformat()}"))
                    stats_by_class[cls]["burn_in"] += 1
                    continue
            else:  # pragma: no cover — params 已校验
                continue
            reaction_day = _next_trading_day(date.fromisoformat(rd), trading_days)
            code = resolve(concept, reaction_day) if reaction_day is not None else None
            if reaction_day is not None and code is None:
                gaps.append(ClassifyGap(f"{cls}:{concept}", rd, GAP_NO_SERIES_ON_DAY, f"reaction_day={reaction_day.isoformat()}"))
                stats_by_class[cls]["no_series"] += 1
                continue
            ingested = sorted(r.ingested_at for r in group if r.ingested_at)
            title = (
                f"{concept} | 观点 {len(group)} 条 · 硬证据 {n_hard} · 看多 {n_bull}"
                + (" · 首提" if first_seen.get(concept) == rd else "")
                + (f" | ingested_at≤{ingested[-1]}" if ingested else "")
            )
            codes = (code,) if code else ()
            names = (concept,) if code else ()
            for r in group:
                events.append(ClassifiedEvent(cls, concept, rd, None, r.event_id, title, codes, names))
            stats_by_class[cls]["concept_days"] += 1
    lag = _ingest_lag(rows)
    stats = {
        "rows": len(rows),
        "concepts": len(concept_counts),
        "concepts_matching_sector_name": len(concept_counts) - len(unmatched),
        "events_on_matched_concepts": sum(n for c, n in concept_counts.items() if c not in unmatched),
        "report_date_range": [file_start, max((r.report_date for r in rows), default=None)],
        "ingest_lag_days": lag,
        "by_class": {c: dict(sorted(v.items())) for c, v in stats_by_class.items()},
    }
    return events, gaps, stats


def _ingest_lag(rows: Sequence[OpinionRow]) -> dict[str, Any]:
    lags: list[int] = []
    for r in rows:
        if not r.ingested_at:
            continue
        try:
            lags.append((date.fromisoformat(r.ingested_at[:10]) - date.fromisoformat(r.report_date)).days)
        except ValueError:
            continue
    if not lags:
        return {"n": 0}
    lags.sort()
    pick = lambda q: lags[min(len(lags) - 1, int(q * (len(lags) - 1)))]  # noqa: E731
    return {"n": len(lags), "p50": pick(0.5), "p90": pick(0.9), "share_same_day": round(sum(1 for x in lags if x <= 0) / len(lags), 3)}
