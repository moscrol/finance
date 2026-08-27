from __future__ import annotations

from datetime import date
from pathlib import Path

from intelligence.services.ask_types import DEFAULT_STALE_DAYS
from intelligence.services.evidence_freshness import (
    collect_hits_from_questions,
    collect_hits_from_run_store,
    priority_gaps,
    render_freshness_report,
    report_path,
    summarize_hosts,
)


AS_OF = date(2026, 8, 18)


def _item(target: str, source_date: str, target_type: str = "entity") -> dict[str, str]:
    return {
        "target": target,
        "target_type": target_type,
        "source_date": source_date,
        "source": "fixture",
        "evidence": "夹具",
    }


def test_stale_and_recently_asked_host_is_priority_gap() -> None:
    items = (
        _item("厦钨新能", "2026-01-29"),
        _item("中际旭创", "2026-08-10"),
    )
    hits = collect_hits_from_questions(
        (("厦钨新能怎么看", date(2026, 8, 16)),),
        ("厦钨新能", "中际旭创"),
        as_of=AS_OF,
    )
    rows = summarize_hosts(items, as_of=AS_OF, hits=hits)
    gaps = priority_gaps(rows)

    assert DEFAULT_STALE_DAYS == 45
    assert [row.host for row in gaps] == ["厦钨新能"]
    assert gaps[0].age_days == 201
    assert gaps[0].hit_count == 1


def test_stale_host_without_recent_hit_is_not_priority() -> None:
    items = (_item("冷门公司", "2026-01-01"),)
    rows = summarize_hosts(items, as_of=AS_OF, hits={})

    assert rows[0].is_stale is True
    assert priority_gaps(rows) == ()


def test_fresh_host_with_hits_is_not_priority() -> None:
    items = (_item("中际旭创", "2026-08-10"),)
    hits = collect_hits_from_questions(
        (("中际旭创怎么看", date(2026, 8, 17)),),
        ("中际旭创",),
        as_of=AS_OF,
    )
    rows = summarize_hosts(items, as_of=AS_OF, hits=hits)

    assert rows[0].hit_count == 1
    assert rows[0].is_stale is False
    assert priority_gaps(rows) == ()


def test_hit_outside_lookback_does_not_count() -> None:
    hits = collect_hits_from_questions(
        (("厦钨新能怎么看", date(2026, 7, 1)),),
        ("厦钨新能",),
        as_of=AS_OF,
    )
    assert hits == {}


def test_empty_source_date_is_not_treated_as_stale() -> None:
    items = (_item("无日期宿主", ""),)
    hits = {"无日期宿主": (2, date(2026, 8, 17))}
    rows = summarize_hosts(items, as_of=AS_OF, hits=hits)

    assert rows[0].latest_source_date is None
    assert rows[0].is_stale is False
    assert priority_gaps(rows) == ()


def test_run_store_counts_recent_questions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_20260816_120000_1"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        '{"question": "厦钨新能现在怎么看", "source_date": "2026-08-16"}',
        encoding="utf-8",
    )
    hits = collect_hits_from_run_store(tmp_path, ("厦钨新能",), as_of=AS_OF)
    assert hits["厦钨新能"] == (1, date(2026, 8, 16))


def test_report_uses_same_45_day_marker_and_agreed_path(tmp_path: Path) -> None:
    items = (_item("厦钨新能", "2026-01-29"),)
    hits = {"厦钨新能": (3, date(2026, 8, 16))}
    rows = summarize_hosts(items, as_of=AS_OF, hits=hits)
    text = render_freshness_report(rows, as_of=AS_OF)

    assert "厦钨新能" in text
    assert f"⚠️{DEFAULT_STALE_DAYS} 天复核" in text
    assert report_path(tmp_path, AS_OF).name == "evidence-host-freshness-2026-08-18.md"
