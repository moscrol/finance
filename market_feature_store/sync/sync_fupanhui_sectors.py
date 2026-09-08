"""发布复盘会每日板块宇宙，并维护 dim_sector 身份历史。

数据源: fupanhui sectors/search。
写入: 仅通过 SectorUniverseStore 原子发布快照、回执与 active identities；
     随行情 payload 字段另落 ops_sector_search_payload_daily（见 consumption_registry.yaml
     sector_universe：这一个请求同时是宇宙、成分 delta 探针、板块日行情官方涨幅来源）。
"""
from __future__ import annotations

import json
from datetime import datetime, date

from ..db import connect, init_db
from ..sector_universe import (
    SectorDescriptor,
    SectorUniverseStore,
    SectorUniverseValidationError,
)
from ..sources import fupanhui_source as fs
from ..sources.sector_mapping import lookup_sw_l1

# payload 字段名候选：供应商字段未经实测确认，按候选顺序取第一个非空值；
# 原文整份落 raw_json，映射错了可以事后从原文修正，不用再打请求。
_PAYLOAD_FIELDS = {
    "pct_chg": ("pct_chg", "pct_change", "change_pct", "chg_pct"),
    "strength": ("strength", "sector_strength"),
    "amount": ("amount", "turnover", "amt"),
    "diff_ratio": ("diff_ratio", "marginal_ratio", "amount_diff_ratio"),
    "stock_count": ("stock_count", "count", "stocks"),
}


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


def _num(val):
    if val is None or isinstance(val, bool):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pick(sector: dict, candidates: tuple[str, ...]):
    for key in candidates:
        if sector.get(key) is not None:
            return sector[key]
    return None


def payload_rows(sectors: list[dict], *, trade_date: date, snapshot_id: str, captured_at: datetime) -> list[tuple]:
    """把 sectors/search 的每一项压成 ops_sector_search_payload_daily 的一行。"""
    rows = []
    for sector in sectors:
        ts_code = str(sector.get("ts_code") or "").strip().upper()
        if not ts_code:
            continue
        count = _pick(sector, _PAYLOAD_FIELDS["stock_count"])
        try:
            count = int(count) if count is not None and not isinstance(count, (list, dict)) else None
        except (TypeError, ValueError):
            count = None
        rows.append(
            (
                trade_date,
                snapshot_id,
                ts_code,
                _num(_pick(sector, _PAYLOAD_FIELDS["pct_chg"])),
                _num(_pick(sector, _PAYLOAD_FIELDS["strength"])),
                _num(_pick(sector, _PAYLOAD_FIELDS["amount"])),
                _num(_pick(sector, _PAYLOAD_FIELDS["diff_ratio"])),
                count,
                json.dumps(sector, ensure_ascii=False, default=str),
                captured_at,
            )
        )
    return rows


def write_payload(con, rows: list[tuple]) -> int:
    if not rows:
        return 0
    con.executemany(
        """
        INSERT INTO ops_sector_search_payload_daily
            (trade_date, snapshot_id, sector_ts_code, pct_chg, strength, amount,
             diff_ratio, stock_count, raw_json, captured_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date, snapshot_id, sector_ts_code) DO UPDATE SET
            pct_chg = excluded.pct_chg,
            strength = excluded.strength,
            amount = excluded.amount,
            diff_ratio = excluded.diff_ratio,
            stock_count = excluded.stock_count,
            raw_json = excluded.raw_json,
            captured_at = excluded.captured_at
        """,
        rows,
    )
    return len(rows)


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
        payload_written = write_payload(
            con,
            payload_rows(
                sectors,
                trade_date=seen_date,
                snapshot_id=published.snapshot_id,
                captured_at=captured_at,
            ),
        )
        payload_pct = con.execute(
            "SELECT COUNT(*) FROM ops_sector_search_payload_daily "
            "WHERE trade_date = ? AND snapshot_id = ? AND pct_chg IS NOT NULL",
            [seen_date, published.snapshot_id],
        ).fetchone()[0]
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
        "payload_rows": payload_written,
        "payload_pct_chg_rows": int(payload_pct),
    }
