from __future__ import annotations

from scripts.measure_sector_member_latency import (
    project_wall_clock,
    select_probe_batches,
    select_probe_sectors,
)


def test_select_probe_sectors_spans_small_median_high_and_largest_counts() -> None:
    counts = (5, 10, 20, 40, 80, 160, 320, 640, 1204)
    sectors = [
        {"ts_code": f"BK{index:04d}", "name": f"板块{index}", "stock_count": count}
        for index, count in enumerate(counts)
    ]

    selected = select_probe_sectors(sectors)

    assert [row["stock_count"] for row in selected] == [5, 80, 640, 1204]


def test_project_wall_clock_uses_batch_p95_for_nightly_projection() -> None:
    projection = project_wall_clock(
        sector_count=407,
        batch_size=10,
        batch_elapsed_seconds=(8, 10, 12, 14),
        nightly_window_seconds=7200,
    )

    assert projection == {
        "batches": 41,
        "batch_p50_seconds": 11.0,
        "batch_p95_seconds": 14.0,
        "projected_seconds": 574.0,
        "nightly_window_seconds": 7200.0,
        "fits_nightly_window": True,
    }


def test_select_probe_batches_centres_windows_and_deduplicates_tail() -> None:
    sectors = [
        {"ts_code": f"BK{index:04d}", "stock_count": count}
        for index, count in enumerate((5, 10, 20, 40, 80, 160, 320, 640, 1204))
    ]

    batches = select_probe_batches(sectors, batch_size=3)

    assert batches == (
        ("BK0000", "BK0001", "BK0002"),
        ("BK0003", "BK0004", "BK0005"),
        ("BK0006", "BK0007", "BK0008"),
    )
