"""事件锚点日历：编辑日历 + 官方日程 → ``history_event_calendar``；``latest_known`` 只答何时。

反应日映射（设计稿 §3.3）每类一条规则：
  same_day_or_next                  首个 ≥ event_date 的交易日（09:30 前发布的国内数据、LPR）
  next_trading_day                  首个 > event_date 的交易日（收盘后发布：金融数据）
  next_trading_day_after_us_date    首个 ≥ event_date + 1 自然日 的交易日（FOMC 14:00 ET = 次日凌晨北京）
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH

from intelligence.services.methodology_backtest.store import (
    SOURCE_ALIAS,
    BuildReport,
    attach_source,
    default_labels_db_path,
    detach_source,
    naive_utc,
    open_labels_db,
    utc_now,
    write_meta,
)

from .classify import ClassifiedEvent, EditorialRow, classify_rows, summarize
from .params import EventParams, load_params
from .schedule import (
    SOURCE_GRADE_BOTH,
    SOURCE_GRADE_CONFLICT,
    SOURCE_GRADE_EDITORIAL,
    SOURCE_GRADE_OFFICIAL,
    ScheduleEntry,
    derive_lpr_by_rule,
    load_schedule_files,
)
from .store import CALENDAR_TABLES, ensure_event_schema, reset_event_tables

CONFLICT_WINDOW_TRADING_DAYS = 3
GAP_KIND_CLASSIFY = "classify"
GAP_KIND_CALENDAR = "calendar"
SOURCE_GRADE_EDITORIAL_AMBIGUOUS = "editorial_ambiguous"


# --------------------------------------------------------------------------- #
# 反应日
# --------------------------------------------------------------------------- #
def map_reaction_day(event_date: date, rule: str, trading_days: list[date]) -> date | None:
    """返回 A 股首个可反应交易日；超出日历范围返回 None。``trading_days`` 须已排序。"""
    if rule == "same_day_or_next":
        floor = event_date
    elif rule == "next_trading_day":
        floor = event_date + timedelta(days=1)
    elif rule == "next_trading_day_after_us_date":
        floor = event_date + timedelta(days=1)
    else:
        raise ValueError(f"未知反应日规则 {rule!r}")
    for d in trading_days:
        if d >= floor:
            return d
    return None


# --------------------------------------------------------------------------- #
# 日历行
# --------------------------------------------------------------------------- #
@dataclass
class CalendarRow:
    event_class: str
    indicator: str
    event_date: str
    reaction_day: str | None
    scheduled: bool
    source_grade: str
    schedule_published_at: str | None
    period: str | None
    editorial_date: str | None
    reaction_day_confidence: str
    event_ids: list[str]
    sector_codes: list[str]
    sector_names: list[str]
    title_sample: str | None

    def key(self) -> tuple[str, str, str]:
        return (self.event_class, self.indicator, self.event_date)

    def as_insert(self, ev_version: str, computed_at: datetime) -> list[Any]:
        sectors = [{"ts_code": c, "name": n} for c, n in zip(self.sector_codes, self.sector_names)]
        return [
            self.event_class,
            self.indicator,
            date.fromisoformat(self.event_date),
            date.fromisoformat(self.reaction_day) if self.reaction_day else None,
            self.scheduled,
            self.source_grade,
            date.fromisoformat(self.schedule_published_at) if self.schedule_published_at else None,
            self.period,
            date.fromisoformat(self.editorial_date) if self.editorial_date else None,
            self.reaction_day_confidence,
            json.dumps(sorted(set(self.event_ids)), ensure_ascii=False),
            json.dumps(sectors, ensure_ascii=False) if sectors else None,
            self.title_sample,
            ev_version,
            naive_utc(computed_at),
        ]


def _read_trading_days(con: duckdb.DuckDBPyConnection) -> list[date]:
    rows = con.execute("SELECT trade_date FROM history_calendar ORDER BY trade_date").fetchall()
    if not rows:
        raise RuntimeError("旁路库 history_calendar 为空：先跑 methodology_backtest build-labels")
    return [r[0] for r in rows]


def _read_editorial(con: duckdb.DuckDBPyConnection) -> list[EditorialRow]:
    rows = con.execute(
        f"""
        SELECT event_id, CAST(event_date AS DATE), title, event_type, sectors
        FROM {SOURCE_ALIAS}.fact_event_daily
        WHERE event_date IS NOT NULL AND event_id IS NOT NULL
        ORDER BY event_date, event_id
        """
    ).fetchall()
    return [
        EditorialRow(
            event_id=str(eid),
            event_date=ed.isoformat(),
            title=str(title or ""),
            event_type=(str(et) if et is not None else None),
            sectors_json=(str(sec) if sec is not None else None),
        )
        for eid, ed, title, et, sec in rows
    ]


def _official_rows(entries: list[ScheduleEntry], params: EventParams, tds: list[date]) -> dict[tuple[str, str, str], CalendarRow]:
    out: dict[tuple[str, str, str], CalendarRow] = {}
    for e in entries:
        spec = params.classes[e.event_class]
        rd = map_reaction_day(e.event_date_obj, spec.reaction_rule, tds)
        row = CalendarRow(
            event_class=e.event_class,
            indicator=e.indicator,
            event_date=e.event_date,
            reaction_day=rd.isoformat() if rd else None,
            scheduled=spec.scheduled,
            source_grade=e.source_grade,
            schedule_published_at=e.schedule_published_at,
            period=e.period,
            editorial_date=None,
            reaction_day_confidence=spec.reaction_day_confidence,
            event_ids=[],
            sector_codes=[],
            sector_names=[],
            title_sample=None,
        )
        out[row.key()] = row
    return out


def _editorial_rows(events: list[ClassifiedEvent], params: EventParams, tds: list[date]) -> dict[tuple[str, str, str], CalendarRow]:
    """同 (类, 指标, 反应日) 的多条编辑行合成一条（08-31 三条 PMI → 一条锚点）。"""
    grouped: dict[tuple[str, str, str | None], CalendarRow] = {}
    for ev in events:
        spec = params.classes[ev.event_class]
        rd = map_reaction_day(date.fromisoformat(ev.event_date), spec.rule_for_editorial, tds)
        rd_s = rd.isoformat() if rd else None
        gkey = (ev.event_class, ev.indicator, rd_s or f"nord:{ev.event_date}")
        row = grouped.get(gkey)
        if row is None:
            row = CalendarRow(
                event_class=ev.event_class,
                indicator=ev.indicator,
                event_date=ev.event_date,
                reaction_day=rd_s,
                scheduled=spec.scheduled,
                source_grade=SOURCE_GRADE_EDITORIAL,
                schedule_published_at=None,
                period=ev.period,
                editorial_date=None,
                reaction_day_confidence=spec.reaction_day_confidence,
                event_ids=[],
                sector_codes=[],
                sector_names=[],
                title_sample=ev.title[:120] if ev.title else None,
            )
            grouped[gkey] = row
        else:
            # 同锚点多行：事件日取最早，所属期取第一个解析到的
            if ev.event_date < row.event_date:
                row.event_date = ev.event_date
            if row.period is None and ev.period:
                row.period = ev.period
        row.event_ids.append(ev.event_id)
        for c, n in zip(ev.sector_codes, ev.sector_names):
            if c not in row.sector_codes:
                row.sector_codes.append(c)
                row.sector_names.append(n)
    return {r.key(): r for r in grouped.values()}


def _td_distance(a: str, b: str, td_index: dict[str, int]) -> int | None:
    ia, ib = td_index.get(a), td_index.get(b)
    if ia is None or ib is None:
        return None
    return abs(ia - ib)


def merge_rows(
    official: dict[tuple[str, str, str], CalendarRow],
    editorial: dict[tuple[str, str, str], CalendarRow],
    tds: list[date],
) -> tuple[list[CalendarRow], list[tuple[str, str, str]], list[tuple[str, str, str, str]]]:
    """官方为骨架；编辑同反应日 → both；同所属期 / 邻近但日期不同 → conflict（官方为准，记 editorial_date）；其余编辑独立成行。

    返回 (rows, conflicts, absorbed)：absorbed 是「官方行已有同日编辑行、又来一条日期不同的编辑别名」——不算冲突，
    但是编辑日历的质量信号，调用方写进缺口表。
    """
    td_index = {d.isoformat(): i for i, d in enumerate(tds)}
    by_class_ind: dict[tuple[str, str], list[CalendarRow]] = {}
    for row in official.values():
        by_class_ind.setdefault((row.event_class, row.indicator), []).append(row)
    conflicts: list[tuple[str, str, str]] = []
    out: dict[tuple[str, str, str], CalendarRow] = dict(official)
    matched_same_rd: set[int] = set()
    pending_near: list[tuple[CalendarRow, CalendarRow]] = []

    def _absorb(o: CalendarRow, erow: CalendarRow) -> None:
        o.event_ids.extend(erow.event_ids)
        o.title_sample = o.title_sample or erow.title_sample
        for c, n in zip(erow.sector_codes, erow.sector_names):
            if c not in o.sector_codes:
                o.sector_codes.append(c)
                o.sector_names.append(n)

    # 第一遍：反应日相同 → 吸收进官方行（两源一致）
    for ekey, erow in editorial.items():
        candidates = by_class_ind.get((erow.event_class, erow.indicator), [])
        same_rd = [o for o in candidates if o.reaction_day and o.reaction_day == erow.reaction_day]
        if same_rd:
            o = same_rd[0]
            matched_same_rd.add(id(o))
            _absorb(o, erow)
            if o.event_date != erow.event_date:
                o.editorial_date = erow.event_date
            continue
        near = None
        for o in candidates:
            if erow.period and o.period and erow.period == o.period:
                near = o
                break
            if erow.reaction_day and o.reaction_day:
                dist = _td_distance(erow.reaction_day, o.reaction_day, td_index)
                if dist is not None and dist <= CONFLICT_WINDOW_TRADING_DAYS:
                    near = o
                    break
        if near is not None:
            pending_near.append((near, erow))
            continue
        if ekey in out:
            conflicts.append(ekey)
            continue
        out[ekey] = erow
    # 第二遍：邻近但日期不同的编辑行。官方行若已有同反应日的编辑行（如两日会议的第一天），只是多一条别名，
    # 不算冲突；否则两源日期真的不同 → conflict，官方为准，记 editorial_date。
    absorbed: list[tuple[str, str, str, str]] = []
    for o, erow in pending_near:
        _absorb(o, erow)
        if id(o) in matched_same_rd:
            absorbed.append((erow.event_class, erow.indicator, erow.event_date, o.event_date))
            continue
        o.source_grade = SOURCE_GRADE_CONFLICT
        o.editorial_date = erow.event_date
        conflicts.append((erow.event_class, erow.indicator, erow.event_date))
    for o in official.values():
        if id(o) in matched_same_rd and o.source_grade == SOURCE_GRADE_OFFICIAL:
            o.source_grade = SOURCE_GRADE_BOTH
    _mark_editorial_duplicates(out)
    rows = sorted(out.values(), key=lambda r: (r.event_class, r.indicator, r.event_date))
    return rows, conflicts, absorbed


def _mark_editorial_duplicates(rows: dict[tuple[str, str, str], CalendarRow]) -> None:
    """同 (类, 指标, 所属期) 的多条**编辑独有**行落在不同反应日 → 全部标 ``editorial_ambiguous``（不入锚点）。

    没有官方仲裁时二选一就是猜；fail-closed。典型现场：3 月 M1 记在 04-10、3 月 M0 记在 04-13。
    """
    by_period: dict[tuple[str, str, str], list[CalendarRow]] = {}
    for r in rows.values():
        if r.source_grade == SOURCE_GRADE_EDITORIAL and r.period:
            by_period.setdefault((r.event_class, r.indicator, r.period), []).append(r)
    for group in by_period.values():
        if len({g.reaction_day for g in group}) > 1:
            for g in group:
                g.source_grade = SOURCE_GRADE_EDITORIAL_AMBIGUOUS


# --------------------------------------------------------------------------- #
# 构建
# --------------------------------------------------------------------------- #
def _write_gaps(
    con: duckdb.DuckDBPyConnection,
    kind: str,
    items: list[tuple[str, str, str | None]],
    ev_version: str,
    computed_at: datetime,
) -> None:
    con.execute("DELETE FROM history_event_gaps WHERE gap_kind = ?", [kind])
    seen: set[tuple[str, str]] = set()
    rows = []
    for key, reason, detail in items:
        if (key, reason) in seen:
            continue
        seen.add((key, reason))
        rows.append([kind, key, reason, detail, ev_version, naive_utc(computed_at)])
    if rows:
        con.executemany(
            "INSERT INTO history_event_gaps (gap_kind, gap_key, reason, detail, ev_version, computed_at) VALUES (?,?,?,?,?,?)",
            rows,
        )


def build_calendar(
    source_db: str | Path | None,
    labels_db: str | Path | None,
    *,
    params: EventParams | None = None,
    now: datetime | None = None,
) -> BuildReport:
    """主库 ``fact_event_daily`` + 官方日程文件 → 旁路库 ``history_event_calendar``（可重建、幂等）。"""
    params = params or load_params()
    source = Path(source_db).expanduser() if source_db else CANONICAL_DB_PATH
    labels_path = Path(labels_db).expanduser() if labels_db else default_labels_db_path(source)
    computed_at = naive_utc(now or utc_now())

    con = open_labels_db(labels_path, read_only=False)
    try:
        ensure_event_schema(con)
        source_path = attach_source(con, source)
        try:
            tds = _read_trading_days(con)
            editorial_rows = _read_editorial(con)
            events, class_gaps = classify_rows(editorial_rows, params)
            entries, sources_meta = load_schedule_files(params)
            entries.extend(derive_lpr_by_rule(params, tds, entries))
            official = _official_rows(entries, params, tds)
            editorial = _editorial_rows(events, params, tds)
            rows, conflicts, absorbed = merge_rows(official, editorial, tds)

            reset_event_tables(con, CALENDAR_TABLES)
            con.executemany(
                """
                INSERT INTO history_event_calendar
                    (event_class, indicator, event_date, reaction_day, scheduled, source_grade,
                     schedule_published_at, period, editorial_date, reaction_day_confidence,
                     event_ids_json, sectors_json, title_sample, ev_version, computed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [r.as_insert(params.ev_version, computed_at) for r in rows],
            )
            gap_items: list[tuple[str, str, str | None]] = [
                (f"{g.event_date}:{g.event_id}"[:180], g.reason, g.detail) for g in class_gaps
            ]
            _write_gaps(con, GAP_KIND_CLASSIFY, gap_items, params.ev_version, computed_at)
            cal_items: list[tuple[str, str, str | None]] = [
                (f"{c}:{i}:{d}", "conflict_official_wins", None) for c, i, d in conflicts
            ]
            cal_items += [
                (f"{c}:{i}:{d}", "absorbed_adjacent_editorial", f"official_date={od}") for c, i, d, od in absorbed
            ]
            cal_items += [
                (f"{r.event_class}:{r.indicator}:{r.event_date}", "beyond_calendar", None)
                for r in rows
                if r.reaction_day is None
            ]
            cal_items += [
                (f"{r.event_class}:{r.indicator}:{r.event_date}", "period_unparsed", r.title_sample)
                for r in rows
                if params.classes[r.event_class].period_kind in ("title_month", "release_month") and r.period is None
            ]
            cal_items += [
                (f"{r.event_class}:{r.indicator}:{r.event_date}", "duplicate_period_dates", f"{r.period} | {r.title_sample}")
                for r in rows
                if r.source_grade == SOURCE_GRADE_EDITORIAL_AMBIGUOUS
            ]
            _write_gaps(con, GAP_KIND_CALENDAR, cal_items, params.ev_version, computed_at)

            source_max = con.execute(f"SELECT MAX(trade_date) FROM {SOURCE_ALIAS}.fact_market_daily").fetchone()[0]
            by_grade = dict(
                con.execute(
                    "SELECT source_grade, COUNT(*) FROM history_event_calendar GROUP BY 1 ORDER BY 1"
                ).fetchall()
            )
            by_class = dict(
                con.execute(
                    "SELECT event_class, COUNT(*) FROM history_event_calendar GROUP BY 1 ORDER BY 1"
                ).fetchall()
            )
            write_meta(
                con,
                build_kind="event_calendar",
                label_version=params.ev_version,
                source_db=source_path,
                source_max_trade_date=source_max,
                source_row_counts={
                    "fact_event_daily": len(editorial_rows),
                    "classify": summarize(events, class_gaps),
                    "official_entries": len(entries),
                    "by_source_grade": {str(k): int(v) for k, v in by_grade.items()},
                    "by_class": {str(k): int(v) for k, v in by_class.items()},
                    "conflicts": len(conflicts),
                    "absorbed_adjacent_editorial": len(absorbed),
                    "schedule_files": sources_meta,
                },
                row_count=len(rows),
                horizons=None,
                computed_at=computed_at,
            )
        finally:
            detach_source(con)
    finally:
        con.close()

    return BuildReport(
        build_kind="event_calendar",
        labels_db=str(labels_path),
        source_db=str(source_path),
        label_version=params.ev_version,
        source_max_trade_date=str(source_max) if source_max is not None else None,
        calendar_start=tds[0].isoformat(),
        calendar_end=tds[-1].isoformat(),
        calendar_days=len(tds),
        row_count=len(rows),
        computed_at=computed_at.isoformat(timespec="seconds") + "Z",
        rows_by_label={str(k): int(v) for k, v in by_class.items()},
        extras={
            "by_source_grade": {str(k): int(v) for k, v in by_grade.items()},
            "classify": summarize(events, class_gaps),
            "conflicts": len(conflicts),
            "absorbed_adjacent_editorial": len(absorbed),
            "official_entries": len(entries),
        },
    )


# --------------------------------------------------------------------------- #
# latest_known：只答何时，不答多少
# --------------------------------------------------------------------------- #
STATUS_RELEASED = "released"
STATUS_NOT_YET = "not_yet_released"
STATUS_UNKNOWN = "unknown_schedule"
_FORBIDDEN_KEYS = ("value", "actual", "consensus", "forecast", "number")


def latest_known(con: duckdb.DuckDBPyConnection, indicator: str, as_of: str | date) -> dict[str, Any]:
    """站在 ``as_of`` 收盘，``indicator`` 已知的最新一期是哪期、哪天发布；没有则下一期何时发布。

    「已知」= 反应日 ≤ as_of（09:30 前发布的同日即知；收盘后发布的次日才知）。返回值里**没有数值字段**。
    """
    as_of_d = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    rows = con.execute(
        """
        SELECT event_date, reaction_day, period, source_grade, event_class
        FROM history_event_calendar
        WHERE indicator = ? AND source_grade <> ?
        ORDER BY event_date
        """,
        [indicator, SOURCE_GRADE_EDITORIAL_AMBIGUOUS],
    ).fetchall()
    if not rows:
        return {"indicator": indicator, "as_of": as_of_d.isoformat(), "status": STATUS_UNKNOWN, "reason": "calendar_has_no_rows_for_indicator"}
    released = [r for r in rows if r[1] is not None and r[1] <= as_of_d]
    upcoming = [r for r in rows if (r[1] is not None and r[1] > as_of_d) or (r[1] is None and r[0] > as_of_d)]
    out: dict[str, Any] = {"indicator": indicator, "as_of": as_of_d.isoformat(), "event_class": rows[0][4]}
    if released:
        # 所属期可比时按所属期取最大，否则按发布日
        last = max(released, key=lambda r: ((r[2] or ""), r[0]))
        out.update(
            {
                "status": STATUS_RELEASED,
                "period": last[2],
                "release_date": last[0].isoformat(),
                "known_from": last[1].isoformat(),
                "source_grade": last[3],
            }
        )
    else:
        out["status"] = STATUS_NOT_YET
    if upcoming:
        nxt = min(upcoming, key=lambda r: r[0])
        out["next_release_date"] = nxt[0].isoformat()
        out["next_period"] = nxt[2]
        out["next_source_grade"] = nxt[3]
    elif not released:
        out["status"] = STATUS_UNKNOWN
        out["reason"] = "no_row_after_as_of"
    for k in out:
        if any(f in k.lower() for f in _FORBIDDEN_KEYS):
            raise AssertionError(f"latest_known 不得返回数值类字段: {k}")
    return out
