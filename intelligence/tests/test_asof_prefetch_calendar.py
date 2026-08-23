"""周历题预取 event_daily；「周末发酵 + 下周大事」不得走题材发酵预取。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from intelligence.services.asof_prefetch import (
    calendar_event_window,
    collect_prefetch_items,
    is_fermentation_query,
)

_CALENDAR_PROBE = "周末发酵了什么新闻？下周（8月24日-8月28日）有什么大事？"


def _write_event_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            create table fact_event_daily(
                event_date date, event_id varchar, title varchar, content varchar,
                importance integer, event_type varchar, source_types varchar,
                sectors varchar, is_future boolean, source varchar,
                updated_at timestamp
            )
            """
        )
        con.executemany(
            "insert into fact_event_daily values (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "2026-08-26",
                    "e-nvda",
                    "英伟达2026Q2财报",
                    "",
                    5,
                    None,
                    None,
                    None,
                    True,
                    "fupanhui",
                    "2026-08-21 15:43:00",
                ),
                (
                    "2026-08-27",
                    "e-jh",
                    "杰克逊霍尔全球央行年会",
                    "",
                    6,
                    None,
                    None,
                    None,
                    True,
                    "fupanhui",
                    "2026-08-21 15:43:00",
                ),
            ],
        )
        con.execute(
            """
            create table fact_sector_daily(
                trade_date date,
                sector_ts_code varchar,
                sector_name varchar,
                pct_chg double,
                amount double,
                diff_ratio double
            )
            """
        )
    finally:
        con.close()
    return path


def test_probe_is_calendar_not_fermentation() -> None:
    assert is_fermentation_query(_CALENDAR_PROBE) is False
    assert is_fermentation_query("锂矿怎么发酵到现在的") is True
    assert calendar_event_window(_CALENDAR_PROBE, date(2026, 8, 21)) == (
        "2026-08-24",
        "2026-08-28",
    )


def test_calendar_prefetch_returns_future_events_known_by_cutoff(
    tmp_path: Path,
) -> None:
    db = _write_event_db(tmp_path / "market.duckdb")
    items = collect_prefetch_items(
        question=_CALENDAR_PROBE,
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=db,
    )
    calendar = [item for item in items if item.tool == "finance_query"]
    assert calendar, [item.title for item in items]
    detail = " ".join(item.detail for item in calendar)
    assert "英伟达2026Q2财报" in detail
    assert "杰克逊霍尔全球央行年会" in detail
    assert not any(item.title == "发酵板块未锚定" for item in items)


def test_calendar_prefetch_empty_window_still_records_lookup(
    tmp_path: Path,
) -> None:
    db = _write_event_db(tmp_path / "empty.duckdb")
    con = duckdb.connect(str(db))
    try:
        con.execute("delete from fact_event_daily")
    finally:
        con.close()
    items = collect_prefetch_items(
        question="下周有什么大事",
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=db,
    )
    calendar = [item for item in items if "事件日历" in item.title]
    assert calendar
    assert "库无行" in calendar[0].detail
