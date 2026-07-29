"""发布复盘会每日板块宇宙，并维护 dim_sector 身份历史。

数据源: fupanhui sectors/search。
写入: 仅通过 SectorUniverseStore 原子发布快照、回执与 active identities。
"""
from __future__ import annotations

from datetime import datetime, date

from ..db import connect, init_db
from ..sector_universe import (
    SectorDescriptor,
    SectorUniverseStore,
    SectorUniverseValidationError,
)
from ..sources import fupanhui_source as fs
from ..sources.sector_mapping import lookup_sw_l1


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def sync_dim_sector(trade_date: str | None = None) -> dict:
    """拉取并发布一份带精确成员分母的每日板块宇宙。"""
    requested_date = trade_date if trade_date is not None else fs.get_latest_date()
    seen_date = _parse_date(requested_date)
    if seen_date is None:
        raise SectorUniverseValidationError("canonical provider trade date is unavailable")
    init_db()
    sectors = fs.list_sectors(trade_date=str(seen_date))
    captured_at = datetime.now().astimezone()

    descriptors = []
    unmapped = []
    for sector in sectors:
        ts_code = sector.get("ts_code")
        name = (sector.get("name") or "").strip()
        sw_l1 = lookup_sw_l1(name) if name else None
        if name and sw_l1 is None:
            unmapped.append(name)
        descriptors.append(
            SectorDescriptor(
                sector_ts_code=str(ts_code or ""),
                sector_name=name,
                expected_stock_count=sector.get("stock_count"),
                sw_l1=sw_l1,
            )
        )

    con = connect()
    try:
        published = SectorUniverseStore(con).publish_snapshot(
            trade_date=seen_date,
            provider_source="fupanhui",
            sectors=descriptors,
            captured_at=captured_at,
        )
        total = con.execute("SELECT COUNT(*) FROM dim_sector").fetchone()[0]
        mapped = con.execute(
            "SELECT COUNT(*) FROM dim_sector WHERE sw_l1 IS NOT NULL"
        ).fetchone()[0]
    finally:
        con.close()

    return {
        "fetched": len(descriptors),
        "snapshot_id": published.snapshot_id,
        "sector_count": published.sector_count,
        "declared_relationship_count": published.declared_relationship_count,
        "dim_sector_total": total,
        "mapped_sw_l1": mapped,
        "unmapped_names": unmapped,
        "seen_date": str(seen_date),
    }
