"""同步 dim_sector: 复盘会板块清单 + 申万一级映射。

数据源: fupanhui sectors/search。
写入: dim_sector (upsert, 保留最早 first_seen_date, 更新 last_seen_date)。
"""
from __future__ import annotations

from datetime import datetime, date

from ..db import connect, init_db
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
    """拉取板块清单写入 dim_sector。返回统计字典。"""
    init_db()
    sectors = fs.list_sectors(trade_date=trade_date)
    seen_date = _parse_date(trade_date) or _parse_date(fs.get_latest_date()) or date.today()
    now = datetime.now()

    rows = []
    unmapped = []
    for s in sectors:
        ts_code = s.get("ts_code")
        name = (s.get("name") or "").strip()
        if not ts_code or not name:
            continue
        sw_l1 = lookup_sw_l1(name)
        if sw_l1 is None:
            unmapped.append(name)
        rows.append((ts_code, name, sw_l1, True, seen_date, seen_date, "fupanhui", now))

    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        con.executemany(
            """
            INSERT INTO dim_sector
                (sector_ts_code, sector_name, sw_l1, is_active,
                 first_seen_date, last_seen_date, source, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT (sector_ts_code) DO UPDATE SET
                sector_name = excluded.sector_name,
                sw_l1 = excluded.sw_l1,
                is_active = excluded.is_active,
                first_seen_date = LEAST(dim_sector.first_seen_date, excluded.first_seen_date),
                last_seen_date = GREATEST(dim_sector.last_seen_date, excluded.last_seen_date),
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        con.execute("COMMIT")
        total = con.execute("SELECT COUNT(*) FROM dim_sector").fetchone()[0]
        mapped = con.execute(
            "SELECT COUNT(*) FROM dim_sector WHERE sw_l1 IS NOT NULL"
        ).fetchone()[0]
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    return {
        "fetched": len(rows),
        "dim_sector_total": total,
        "mapped_sw_l1": mapped,
        "unmapped_names": unmapped,
        "seen_date": str(seen_date),
    }
