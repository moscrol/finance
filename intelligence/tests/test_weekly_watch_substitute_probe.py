"""替补观察 P1-a：weekly 五日包只在最新交易日袋接探针。

Spec: docs/superpowers/specs/2026-08-25-substitute-observation-probe-design.md §8 P1-a
其余日子的袋行为逐字节不变（默认关是 P0 契约，变异测试在 P0 文件锁）。
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from intelligence.services.market_watch_pack import PROBE_ROLE_OBSERVATION
from intelligence.services.weekly_watch_pack import (
    day_bag_details,
    run_weekly_watch_pack,
)

DAYS = ("2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22")


def _db(tmp_path: Path, *, latest_covered: bool = False) -> Path:
    path = tmp_path / "weekly.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily(trade_date date, market_stage varchar,"
        " stage_day integer, total_amount double, amount_vs_yesterday_pct double,"
        " volume_state varchar, limit_up integer, limit_down integer,"
        " sh_index_pct_chg double)"
    )
    for i, day in enumerate(DAYS):
        con.execute(
            "insert into fact_market_daily values (?, '反弹', ?, 20000, -5,"
            " '缩量', 90, 1, 0.1)",
            [day, i + 1],
        )
    con.execute(
        "create table fact_mainline_theme_daily(trade_date date,"
        " theme_name varchar, sector_count integer, min_sort integer)"
    )
    # 每一天主线都有医药（无双红匹配的形状）；只有最新日应产探针。
    for day in DAYS:
        con.execute(
            "insert into fact_mainline_theme_daily values (?, '医药', 6, 1)",
            [day],
        )
    con.execute(
        "create table fact_sector_daily(trade_date date, sector_name varchar,"
        " pct_chg double, diff_ratio double, amount double)"
    )
    med_latest = (1.2, 12.0, 900.0) if latest_covered else (-0.5, 3.0, 900.0)
    for day in DAYS:
        con.execute(
            "insert into fact_sector_daily values (?, '通信设备', 2.5, 15.0, 900)",
            [day],
        )
        row = med_latest if day == DAYS[-1] else (-0.5, 3.0, 900.0)
        con.execute(
            "insert into fact_sector_daily values (?, '医药商业', ?, ?, ?)",
            [day, *row],
        )
    con.execute(
        "create table fact_sector_stock_daily(trade_date date,"
        " sector_name varchar, stock_name varchar, stock_ts_code varchar,"
        " amount double, pct_chg double)"
    )
    for day in DAYS:
        con.execute(
            "insert into fact_sector_stock_daily values"
            " (?, '医药商业', '国药一致', '000028.SZ', 25.0, -0.8),"
            " (?, '医药商业', '上海医药', '601607.SH', 20.0, 0.3)",
            [day, day],
        )
    con.execute(
        "create table fact_theme_limit_heat_daily(trade_date date,"
        " sector_name varchar, limit_up_count integer, market_share double)"
    )
    con.close()
    return path


def test_only_latest_day_gets_probes(tmp_path: Path) -> None:
    pack = run_weekly_watch_pack(
        DAYS[-1], market_db_path=_db(tmp_path), window=5
    )
    assert pack.days == DAYS
    assert len(pack.packs[-1].probes) == 1
    probe = pack.packs[-1].probes[0]
    assert probe.status == "hit"
    assert probe.served_date == DAYS[-1]
    for daily in pack.packs[:-1]:
        assert daily.probes == ()


def test_latest_day_detail_carries_label_first(tmp_path: Path) -> None:
    pack = run_weekly_watch_pack(
        DAYS[-1], market_db_path=_db(tmp_path), window=5
    )
    details = dict(day_bag_details(pack))
    latest = details[f"{DAYS[-1]} 四袋"]
    assert PROBE_ROLE_OBSERVATION in latest
    assert latest.index(PROBE_ROLE_OBSERVATION) < latest.index("国药一致")
    for day in DAYS[:-1]:
        assert "替补观察" not in details[f"{day} 四袋"]
        assert "国药一致" not in details[f"{day} 四袋"]


def test_no_probe_block_when_latest_theme_covered(tmp_path: Path) -> None:
    pack = run_weekly_watch_pack(
        DAYS[-1], market_db_path=_db(tmp_path, latest_covered=True), window=5
    )
    assert pack.packs[-1].probes == ()
    details = dict(day_bag_details(pack))
    assert "替补观察" not in details[f"{DAYS[-1]} 四袋"]
