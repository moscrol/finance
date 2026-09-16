"""消息面（创始人第十六段：「晚间卖方和晨汇那个知识库内容，你认为怎么消费比较好，之前是看边际变化和舆论热度和盘面的对照」）。

消费方式不是「消息定价」的预测，是三组**读数**，全部从知识库的卖方观点事件
（``wiki/raw/theme-radar/opinion-store/opinion-events.jsonl``，每条带 ``report_date`` / ``ingested_at`` / ``concept`` / ``hardness`` /
``resonance_tier`` / ``stance``）聚成市场级一天一个数：

- **舆论热度**：当日事件数、对 20 个交易日均值的比（叙事的「量能比」）、覆盖的概念数、前三概念集中度。
- **边际变化**：当日首次出现的概念数与占比（新叙事 vs 复炒）、硬证据占比、看多占比。
- **与盘面的对照**：当日赚钱效应板块（5 日涨幅前 N）里过去 ``lookback`` 天有卖方叙事的比例（叙事覆盖率）——底部的赚钱效应
  多是没有叙事的纯盘面异动，主线成形时叙事跟上（先量：底部 10% / 顶部 20% / 2.0 45%）。

两条时钟：``report_date`` 是报告日（当晚出的研报，下一交易日可知），按它算读数；``ingested_at`` 是**我们**什么时候入库，
作河对象的 ``recorded_at``——入库普遍滞后（实测 4.6% 同日），回放 / 校准的无前视门该滤就滤。
源断更（最新报告日距 as_of 超过 ``stale_after_days``）时读数全部记缺口 ``narrative_stale``，不给 0——0 条事件和没有事件源是两回事。
概念名与板块名只做**精确**匹配（实测 83 个板块名与概念名完全重合），不做模糊匹配。

第二个源是**晨汇的 Tier 分级**（``raw/theme-radar/opinion-store/briefing-tier-events.jsonl``，知识库
``skills/morning-briefing/scripts/extract_tier_events.py`` 从晨汇正文确定性投影出来，一条 Tier 条目一行）。晨汇 Tier 1 的定义是
「纪要信号 + 知识库主题认知 + 盘面验证」三重共振，是创始人说的「与盘面的对照」的人工版；但 87 份晨汇里只有一份带盘面输入
（``dimensions = 3``），其余 Tier 1 都是「按二维降级为最强双重」——所以 ``briefing_market_confirmed`` 只在三维晨汇的日子有数，
二维的日子记 ``None``（不可知，不是 0）。机器版的对照另算一条：当日 Tier 1 / 2 条目里有多少条的双链或标题正好是当日赚钱效应
板块名（精确匹配，实测 438 个双链里 71 个是板块名）。晨汇的时钟：``available_from`` 是最早可知日（材料日次日；盘前纪要当日），
落到其后第一个交易日；``recorded_at`` 是写成日——回填批次晚数周，``briefing_lag_days`` 把这个滞后写出来。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

OPINION_EVENTS_RELPATH = Path("raw/theme-radar/opinion-store/opinion-events.jsonl")
BRIEFING_EVENTS_RELPATH = Path("raw/theme-radar/opinion-store/briefing-tier-events.jsonl")
DEFAULT_STALE_AFTER_DAYS = 7
DEFAULT_LOOKBACK_DAYS = 5
DEFAULT_DENSITY_WINDOW = 20
BULL_STANCES = ("看多", "偏多", "利好")
HARD_PREFIX = "硬"

NARRATIVE_FIELDS = (
    "narrative_events", "narrative_events_ratio_ma20_pct", "narrative_concepts", "narrative_new_concepts",
    "narrative_new_concept_share_pct", "narrative_hard_share_pct", "narrative_bull_share_pct", "narrative_top3_share_pct",
    "narrative_cover_rps5_pct",
)
BRIEFING_FIELDS = (
    "briefing_tier1_items", "briefing_tier2_items", "briefing_tier3_items", "briefing_market_confirmed",
    "briefing_dimensions", "briefing_hit_rps5_pct", "briefing_lag_days",
)


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def load_opinion_events(kb_wiki: str | Path) -> list[dict[str, Any]]:
    """Read the KB's opinion events; a missing file is a missing source (empty list), never an error here."""
    return _load_jsonl(Path(kb_wiki).expanduser() / OPINION_EVENTS_RELPATH)


def load_briefing_tier_events(kb_wiki: str | Path) -> list[dict[str, Any]]:
    """Read the KB's briefing Tier projection (one row per Tier item); a missing file is a missing source."""
    return _load_jsonl(Path(kb_wiki).expanduser() / BRIEFING_EVENTS_RELPATH)


def narrative_daily(
    events: Iterable[Mapping[str, Any]],
    calendar: Iterable[Any],
    *,
    rps5_names: Mapping[Any, Iterable[str]] | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    density_window: int = DEFAULT_DENSITY_WINDOW,
) -> dict[date, dict[str, Any]]:
    """Per trading day T: the nine narrative readouts (or a ``gap`` reason) plus ``recorded_at`` (max ingested_at of the window's events).

    The window of T is the **overnight narrative available at T's open**: reports dated from the previous trading day up to
    the calendar day before T (a Friday-evening or weekend report belongs to Monday).  Same-day evening reports describe T's
    own session and are not counted for T.  ``calendar`` orders the trading days; ``rps5_names[day]`` are T's 赚钱效应
    sector names (5 日涨幅前 N).  Days before the source started or after it went stale are gaps, not zeros.
    """
    by_day: dict[date, list[Mapping[str, Any]]] = defaultdict(list)
    for e in events:
        d = _date(e.get("report_date"))
        if d is not None:
            by_day[d].append(e)
    if not by_day:
        return {}
    earliest_report, latest_report = min(by_day), max(by_day)
    first_seen: dict[str, date] = {}
    for d in sorted(by_day):
        for e in by_day[d]:
            c = str(e.get("concept") or "").strip()
            if c and c not in first_seen:
                first_seen[c] = d
    concept_days: dict[str, set[date]] = defaultdict(set)
    for d, evs in by_day.items():
        for e in evs:
            c = str(e.get("concept") or "").strip()
            if c:
                concept_days[c].add(d)
    days = [_date(d) for d in calendar]
    days = [d for d in days if d is not None]

    def window_events(i: int) -> list[Mapping[str, Any]]:
        start = days[i - 1]
        end = days[i] - timedelta(days=1)
        d = start
        out_events: list[Mapping[str, Any]] = []
        while d <= end:
            out_events.extend(by_day.get(d, []))
            d += timedelta(days=1)
        return out_events

    counts = {i: (len(window_events(i)) if i > 0 else 0) for i in range(len(days))}
    out: dict[date, dict[str, Any]] = {}
    for i, d in enumerate(days):
        if i == 0 or d <= earliest_report:
            out[d] = {"gap": "narrative_before_source", "earliest_report_date": earliest_report}
            continue
        if (d - latest_report).days > stale_after_days:
            out[d] = {"gap": "narrative_stale", "latest_report_date": latest_report}
            continue
        evs = window_events(i)
        concepts = [str(e.get("concept") or "").strip() for e in evs]
        concepts = [c for c in concepts if c]
        distinct = set(concepts)
        window_start = days[i - 1]
        new = {c for c in distinct if first_seen.get(c) is not None and first_seen[c] >= window_start}
        base = [counts[k] for k in range(max(1, i - density_window), i)]
        ratio = (100.0 * len(evs) / (sum(base) / len(base))) if len(base) == density_window and sum(base) else None
        rec: dict[str, Any] = {
            "narrative_events": len(evs),
            "narrative_events_ratio_ma20_pct": ratio,
            "narrative_concepts": len(distinct),
            "narrative_new_concepts": len(new),
            "narrative_new_concept_share_pct": (100.0 * len(new) / len(distinct)) if distinct else None,
            "narrative_hard_share_pct": (100.0 * sum(1 for e in evs if str(e.get("hardness") or "").startswith(HARD_PREFIX)) / len(evs)) if evs else None,
            "narrative_bull_share_pct": (100.0 * sum(1 for e in evs if e.get("stance") in BULL_STANCES) / len(evs)) if evs else None,
            "narrative_top3_share_pct": None,
            "narrative_cover_rps5_pct": None,
            "recorded_at": max((str(e.get("ingested_at")) for e in evs if e.get("ingested_at")), default=None),
        }
        if concepts:
            c = Counter(concepts)
            rec["narrative_top3_share_pct"] = 100.0 * sum(v for _, v in c.most_common(3)) / sum(c.values())
        names = list((rps5_names or {}).get(d) or (rps5_names or {}).get(str(d)) or [])
        if names:
            # 叙事在前、盘面在后：只看 T 之前 lookback 个日历日的报告，不含 T 当晚的。
            window = {d - timedelta(days=k) for k in range(1, lookback_days + 1)}
            rec["narrative_cover_rps5_pct"] = 100.0 * sum(1 for n in names if concept_days.get(str(n), set()) & window) / len(names)
        out[d] = rec
    return out


def briefing_daily(
    rows: Iterable[Mapping[str, Any]],
    calendar: Iterable[Any],
    *,
    rps5_names: Mapping[Any, Iterable[str]] | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> dict[date, dict[str, Any]]:
    """Per trading day T: the briefing Tier readouts (or a ``gap`` reason) plus ``recorded_at`` (latest write date).

    A row whose ``available_from`` is d lands on the first trading day ≥ d (a 晨汇 of material day m has
    ``available_from = m + 1``, so a Friday / weekend briefing lands on Monday; a pre-market cross-analysis lands on its
    own day).  Days before the first landing are ``briefing_before_source``; more than ``stale_after_days`` after the
    latest ``available_from`` is ``briefing_stale``; a day in between with no briefing is ``briefing_absent_day`` —
    none of these is a 0.  ``briefing_market_confirmed`` is only a number on days whose briefing had a market
    dimension (``dimensions == 3``); on two-dimension days it is ``None`` (unknowable, not 0).  ``briefing_lag_days``
    is how many days after the landing trading day the briefing was actually written (0 = on time; backfills are weeks).
    """
    days = [x for x in (_date(d) for d in calendar) if x is not None]
    if not days:
        return {}
    by_day: dict[date, list[Mapping[str, Any]]] = defaultdict(list)
    availables: list[date] = []
    for r in rows:
        af = _date(r.get("available_from"))
        if af is None:
            continue
        availables.append(af)
        landing = next((d for d in days if d >= af), None)
        if landing is not None:
            by_day[landing].append(r)
    if not availables:
        return {}
    earliest_landing = min(by_day) if by_day else None
    latest_available = max(availables)
    out: dict[date, dict[str, Any]] = {}
    for d in days:
        if earliest_landing is None or d < earliest_landing:
            out[d] = {"gap": "briefing_before_source", "earliest_available_from": min(availables)}
            continue
        if (d - latest_available).days > stale_after_days:
            out[d] = {"gap": "briefing_stale", "latest_available_from": latest_available}
            continue
        items = by_day.get(d)
        if not items:
            out[d] = {"gap": "briefing_absent_day"}
            continue
        tiers = {t: [r for r in items if r.get("tier") == t] for t in (1, 2, 3)}
        dims = max(int(r.get("dimensions") or 2) for r in items)
        top = tiers[1] + tiers[2]
        rec: dict[str, Any] = {
            "briefing_tier1_items": len(tiers[1]),
            "briefing_tier2_items": len(tiers[2]),
            "briefing_tier3_items": len(tiers[3]),
            # 只有带盘面输入的晨汇才知道哪条 Tier 1 真有盘面共振；二维晨汇的 Tier 1 是降级的最强双重，这里不给 0。
            "briefing_market_confirmed": sum(1 for r in tiers[1] if r.get("market_confirmed")) if dims == 3 else None,
            "briefing_dimensions": dims,
            "briefing_hit_rps5_pct": None,
            "briefing_lag_days": None,
            "recorded_at": max((str(r.get("recorded_at")) for r in items if r.get("recorded_at")), default=None),
        }
        names = set(str(n) for n in ((rps5_names or {}).get(d) or (rps5_names or {}).get(str(d)) or []))
        if top and names:
            hit = sum(1 for r in top if names & set(str(x) for x in (r.get("wikilinks") or [])) or str(r.get("theme") or "") in names)
            rec["briefing_hit_rps5_pct"] = 100.0 * hit / len(top)
        # 写成日晚于它落到的交易日几天：当天或之前写成 = 0；回填批次是几十天。
        lags = [(_date(r.get("recorded_at")) - d).days for r in items if _date(r.get("recorded_at")) is not None]
        if lags:
            rec["briefing_lag_days"] = max(0, max(lags))
        out[d] = rec
    return out
