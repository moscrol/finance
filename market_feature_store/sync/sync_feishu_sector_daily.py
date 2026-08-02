"""同步飞书「板块每日涨幅/成交额」表 -> fact_sector_daily (pct_chg / amount 回填)。

数据源: 飞书 Bitable sector_daily 表 (tblXqyf9Av1rGg0n)。
结构: 每行=一个板块(板块字段可能带 (代码) 后缀如 小金属(885552));
       字段成对出现 'YY-MM-DD涨幅' / 'YY-MM-DD成交额'。
成交额单位与复盘会一致(亿), 已对齐校验。

回填策略: 只填 pct_chg / amount, 且用 COALESCE 保留已有(复盘会直连)值,
仅补 NULL; 不动 diff_ratio。日期标签为 YY-MM-DD, 年份明确。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime

from ..db import connect, init_db, PROJECT_DIR, get_published_snapshot_id
from .sync_feishu_sector_marginal import _build_code_map, _canonical

sys.path.insert(0, str(PROJECT_DIR / "shared"))
from feishu_utils import load_config, get_token, fetch_all_records  # noqa: E402

_DATE_RE = re.compile(r"^(\d{2}-\d{2}-\d{2})(涨幅|成交额)$")


def _flat(v):
    if isinstance(v, list):
        return "".join(
            seg.get("text", "") if isinstance(seg, dict) else str(seg) for seg in v
        )
    if isinstance(v, dict):
        return v.get("text", "")
    return v


def _parse_date(label: str) -> str | None:
    """YY-MM-DD -> YYYY-MM-DD (ISO)。"""
    try:
        return datetime.strptime(label, "%y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _parse_pct(v):
    s = _flat(v)
    if s in (None, ""):
        return None
    s = str(s).strip().replace("+", "").replace("%", "").replace(",", "")
    if not s or s in ("—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_amount(v):
    s = _flat(v)
    if s in (None, ""):
        return None
    s = str(s).strip().replace(",", "").replace("亿", "")
    if not s or s in ("—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sync_sector_daily_metrics() -> dict:
    """从飞书板块每日表回填 fact_sector_daily 的 pct_chg / amount。"""
    import pandas as pd

    cfg = load_config()
    token = get_token(cfg)
    table_id = cfg["tables"]["sector_daily"]

    init_db()
    con = connect()
    try:
        records = fetch_all_records(token, table_id, app_token=cfg["app_token"])
        names = [str(_flat(r.get("fields", {}).get("板块", ""))).strip()
                 for r in records]
        names = [n for n in names if n]
        name_to_code, sw_by_code, unmatched = _build_code_map(con, names)

        # 聚合 {(ts_code, iso_date): {pct, amt, name}}
        agg: dict[tuple, dict] = {}
        bad_labels: set[str] = set()
        for r in records:
            fd = r.get("fields", {})
            raw_name = str(_flat(fd.get("板块", ""))).strip()
            if not raw_name:
                continue
            ts_code = name_to_code.get(raw_name)
            if not ts_code:
                continue
            cname = _canonical(raw_name)
            for field_name, value in fd.items():
                m = _DATE_RE.match(field_name)
                if not m:
                    continue
                iso = _parse_date(m.group(1))
                if iso is None:
                    bad_labels.add(field_name)
                    continue
                key = (iso, ts_code)
                cell = agg.setdefault(key, {"name": cname})
                if m.group(2) == "涨幅":
                    pct = _parse_pct(value)
                    if pct is not None:
                        cell["pct"] = pct
                else:
                    amt = _parse_amount(value)
                    if amt is not None:
                        cell["amt"] = amt

        now = datetime.now()
        rows = []
        # 每个交易日解析一次 published 快照即可；无 published 时回退 'legacy'。
        snap_cache: dict[str, str] = {}
        for (iso, ts_code), v in agg.items():
            if "pct" not in v and "amt" not in v:
                continue
            if iso not in snap_cache:
                snap_cache[iso] = get_published_snapshot_id(con, iso)
            rows.append((iso, snap_cache[iso], ts_code, v.get("name"), sw_by_code.get(ts_code),
                         v.get("pct"), v.get("amt"), "feishu:sector_daily", now))

        # fact_sector_daily 是 VIEW，写入必须落 *_generation 表，主键含 snapshot_id。
        written = 0
        if rows:
            _buf_df = pd.DataFrame(rows, columns=[  # noqa: F841
                "trade_date", "sector_universe_snapshot_id", "sector_ts_code", "sector_name",
                "sw_l1", "pct_chg", "amount", "source", "updated_at"])
            con.register("_buf_df", _buf_df)
            try:
                con.execute("""
                    INSERT INTO fact_sector_daily_generation
                        (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                         sw_l1, pct_chg, amount, source, updated_at)
                    SELECT trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                           sw_l1, pct_chg, amount, source, updated_at
                    FROM _buf_df
                    ON CONFLICT (trade_date, sector_universe_snapshot_id, sector_ts_code) DO UPDATE SET
                        pct_chg = COALESCE(fact_sector_daily_generation.pct_chg, EXCLUDED.pct_chg),
                        amount = COALESCE(fact_sector_daily_generation.amount, EXCLUDED.amount),
                        sw_l1 = COALESCE(fact_sector_daily_generation.sw_l1, EXCLUDED.sw_l1),
                        sector_name = COALESCE(fact_sector_daily_generation.sector_name, EXCLUDED.sector_name),
                        updated_at = EXCLUDED.updated_at
                """)
            finally:
                con.unregister("_buf_df")
            written = len(rows)

        a = con.execute(
            "SELECT COUNT(*), COUNT(pct_chg), COUNT(amount), COUNT(diff_ratio),"
            " COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date)"
            " FROM fact_sector_daily"
        ).fetchone()
    finally:
        con.close()

    return {
        "table_id": table_id,
        "records": len(records),
        "rows_written": written,
        "unmatched_sectors": unmatched,
        "bad_labels": sorted(bad_labels),
        "table_total": a[0],
        "table_pct": a[1],
        "table_amount": a[2],
        "table_diff": a[3],
        "table_dates": a[4],
        "date_min": str(a[5]) if a[5] else None,
        "date_max": str(a[6]) if a[6] else None,
    }
