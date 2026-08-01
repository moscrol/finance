from __future__ import annotations

import sys
from datetime import datetime, date

from ..db import connect, init_db, PROJECT_DIR, get_published_snapshot_id
from .sync_feishu_sector_marginal import _build_code_map, _canonical

sys.path.insert(0, str(PROJECT_DIR / "shared"))
from feishu_utils import load_config, get_token, fetch_all_records  # noqa: E402

TABLE_ID = "tblshRMmRnQYrM4K"
MANUAL_ALIASES = {
    "煤炭": "煤炭开采加工",
}

UPSERT_SQL = """
    INSERT INTO fact_sector_daily_generation
        (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, sw_l1,
         multi_period_resonance, multi_period_source, multi_period_updated_at,
         source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, sector_universe_snapshot_id, sector_ts_code) DO UPDATE SET
        sector_name = COALESCE(fact_sector_daily_generation.sector_name, excluded.sector_name),
        sw_l1 = COALESCE(fact_sector_daily_generation.sw_l1, excluded.sw_l1),
        multi_period_resonance = excluded.multi_period_resonance,
        multi_period_source = excluded.multi_period_source,
        multi_period_updated_at = excluded.multi_period_updated_at,
        updated_at = excluded.updated_at
"""


def _flat(v):
    if isinstance(v, list):
        return "".join(
            seg.get("text", "") if isinstance(seg, dict) else str(seg) for seg in v
        )
    if isinstance(v, dict):
        return v.get("text", "")
    return v


def _parse_date(val, md_to_date: dict[str, date] | None = None):
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(_flat(val)).strip()
    for fmt in ("%y-%m-%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    if md_to_date:
        return md_to_date.get(s)
    return None


def _ensure_columns(con):
    con.execute("ALTER TABLE fact_sector_daily_generation ADD COLUMN IF NOT EXISTS multi_period_resonance BOOLEAN")
    con.execute("ALTER TABLE fact_sector_daily_generation ADD COLUMN IF NOT EXISTS multi_period_source TEXT")
    con.execute("ALTER TABLE fact_sector_daily_generation ADD COLUMN IF NOT EXISTS multi_period_updated_at TIMESTAMP")


def _augment_concept_aliases(con, name_to_code: dict, sw_by_code: dict, names: list[str]) -> None:
    rows = con.execute(
        "SELECT sector_ts_code, sector_name, sw_l1 FROM dim_sector"
    ).fetchall()
    by_name: dict[str, list[tuple[str, str | None]]] = {}
    for ts_code, name, sw_l1 in rows:
        by_name.setdefault(name, []).append((ts_code, sw_l1))
    for raw_name in names:
        if raw_name in MANUAL_ALIASES and raw_name not in name_to_code:
            candidates = by_name.get(MANUAL_ALIASES[raw_name], [])
            if candidates:
                ts_code, sw_l1 = candidates[0]
                name_to_code[raw_name] = ts_code
                sw_by_code[ts_code] = sw_l1
                continue
        if raw_name in name_to_code or not raw_name.endswith("概念"):
            continue
        base = raw_name[:-2].strip()
        candidates = by_name.get(base, [])
        if not candidates:
            continue
        preferred = [c for c in candidates if not c[0].startswith("881")]
        ts_code, sw_l1 = (preferred or candidates)[0]
        name_to_code[raw_name] = ts_code
        sw_by_code[ts_code] = sw_l1


def sync_sector_multi_period_resonance() -> dict:
    cfg = load_config()
    token = get_token(cfg)
    records = fetch_all_records(token, TABLE_ID, app_token=cfg["app_token"])

    init_db()
    con = connect()
    try:
        _ensure_columns(con)
        md_rows = con.execute(
            "SELECT DISTINCT strftime(trade_date, '%m-%d'), trade_date FROM fact_sector_daily"
        ).fetchall()
        md_to_date = {}
        for md, d in md_rows:
            md_to_date[md] = d if md not in md_to_date else max(md_to_date[md], d)

        names = []
        for r in records:
            name = str(_flat(r.get("fields", {}).get("板块", ""))).strip()
            if name and name not in names:
                names.append(name)
        name_to_code, sw_by_code, unmatched = _build_code_map(con, names)
        _augment_concept_aliases(con, name_to_code, sw_by_code, names)
        unresolved_names = {n for n in unmatched if n not in name_to_code}

        now = datetime.now()
        rows = []
        skipped_bad_date = []
        skipped_unmatched = set()
        snap_cache: dict[str, str] = {}  # trade_date_str -> snapshot_id
        for r in records:
            f = r.get("fields", {})
            raw_name = str(_flat(f.get("板块", ""))).strip()
            if not raw_name:
                continue
            trade_date = _parse_date(f.get("日期"), md_to_date)
            if not trade_date:
                skipped_bad_date.append(f.get("日期"))
                continue
            ts_code = name_to_code.get(raw_name)
            if not ts_code:
                skipped_unmatched.add(raw_name)
                continue
            td_str = str(trade_date)
            if td_str not in snap_cache:
                snap_cache[td_str] = get_published_snapshot_id(con, td_str)
            rows.append((
                trade_date,
                snap_cache[td_str],
                ts_code,
                _canonical(raw_name),
                sw_by_code.get(ts_code),
                bool(f.get("全周期出现")),
                "feishu:sector_multi_period_resonance",
                now,
                "feishu:sector_multi_period_resonance",
                now,
            ))

        if rows:
            con.execute("BEGIN TRANSACTION")
            con.executemany(UPSERT_SQL, rows)
            con.execute("COMMIT")

        stats = con.execute(
            """
            SELECT COUNT(*), COUNT(multi_period_resonance),
                   SUM(CASE WHEN multi_period_resonance THEN 1 ELSE 0 END),
                   COUNT(DISTINCT CASE WHEN multi_period_resonance THEN trade_date END),
                   MIN(CASE WHEN multi_period_resonance IS NOT NULL THEN trade_date END),
                   MAX(CASE WHEN multi_period_resonance IS NOT NULL THEN trade_date END)
            FROM fact_sector_daily_generation
            """
        ).fetchone()
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    return {
        "table_id": TABLE_ID,
        "records": len(records),
        "rows_written": len(rows),
        "unmatched_sectors": sorted(unresolved_names | skipped_unmatched),
        "bad_dates": skipped_bad_date,
        "table_total": stats[0],
        "resonance_labeled": stats[1],
        "resonance_true": int(stats[2] or 0),
        "resonance_true_dates": stats[3],
        "date_min": str(stats[4]) if stats[4] else None,
        "date_max": str(stats[5]) if stats[5] else None,
    }
