"""同步飞书「连板晋级」表 -> fact_limit_advance_presence。

数据源: 飞书 Bitable limit_advance 表 (tblQsAyuefNoEq1Z)。
结构: 每行=一只连板晋级股(3板+); 字段 股票简称 / 序号 / 一组 MM-DD 日期列。
       某 (股票, 日期) 单元格被填(值=股票名)表示该股当日在连板晋级梯队。
       同一只股可有多段不连续连板序列(单元格非连续)。

入库: 把矩阵展开成 (trade_date, stock_name, sequence_no) 存在性事实。
日期列只有 MM-DD, 通过与已知交易日(fact_stock_daily)对齐推断年份并校验。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime

from ..db import connect, init_db, PROJECT_DIR

sys.path.insert(0, str(PROJECT_DIR / "shared"))
from feishu_utils import load_config, get_token, fetch_all_records  # noqa: E402

_MMDD_RE = re.compile(r"^(\d{2})-(\d{2})$")


def _flat(v):
    """飞书字段可能是 str / [{text:...}] / {text:...}, 统一拍平为字符串。"""
    if isinstance(v, list):
        return "".join(
            seg.get("text", "") if isinstance(seg, dict) else str(seg) for seg in v
        )
    if isinstance(v, dict):
        return v.get("text", "")
    return v


def _txt(v):
    s = _flat(v)
    if s is None:
        return None
    s = str(s).strip()
    return s or None


def _int(v):
    s = _flat(v)
    if s in (None, ""):
        return None
    try:
        return int(float(str(s).strip()))
    except (TypeError, ValueError):
        return None


def _known_trade_dates(con) -> set[str]:
    """已知交易日 (YYYY-MM-DD), 用于把 MM-DD 解析到正确年份并校验。"""
    dates: set[str] = set()
    for tbl in ("fact_stock_daily", "fact_market_daily", "fact_sector_daily"):
        try:
            rows = con.execute(f"SELECT DISTINCT CAST(trade_date AS VARCHAR) FROM {tbl}").fetchall()
            dates.update(r[0] for r in rows if r[0])
        except Exception:  # noqa: BLE001
            pass
    return dates


def _resolve_date(mmdd: str, known: set[str], years: tuple[int, ...]) -> str | None:
    """MM-DD -> YYYY-MM-DD。优先返回落在已知交易日里的年份候选。"""
    m = _MMDD_RE.match(mmdd)
    if not m:
        return None
    mm, dd = m.group(1), m.group(2)
    candidates = [f"{y}-{mm}-{dd}" for y in years]
    for c in candidates:
        if c in known:
            return c
    return None


def sync_limit_advance() -> dict:
    """从飞书连板晋级表回填 fact_limit_advance_presence。"""
    import pandas as pd

    cfg = load_config()
    token = get_token(cfg)
    table_id = cfg["tables"]["limit_advance"]

    init_db()
    con = connect()
    try:
        known = _known_trade_dates(con)
        years = (2026, 2025)  # 数据集年份范围; 先试新年份再试旧年份
        records = fetch_all_records(token, table_id, app_token=cfg["app_token"])

        recs: list[tuple] = []
        now = datetime.now()
        unresolved: set[str] = set()
        stocks = 0
        for r in records:
            fd = r.get("fields", {})
            name = _txt(fd.get("股票简称"))
            if not name:
                continue
            seq = _int(fd.get("序号"))
            stocks += 1
            for field_name, value in fd.items():
                if field_name in ("股票简称", "序号"):
                    continue
                if not _MMDD_RE.match(field_name):
                    continue
                if _txt(value) is None:  # 空单元格 = 当日不在梯队
                    continue
                iso = _resolve_date(field_name, known, years)
                if iso is None:
                    unresolved.add(field_name)
                    continue
                recs.append((iso, name, seq, "feishu:limit_advance", now))

        written = 0
        if recs:
            # 同一 (date, name) 可能多记录(罕见), 去重保留最后一条
            dedup = {(d, n): (d, n, s, src, ts) for d, n, s, src, ts in recs}
            buf = list(dedup.values())
            _buf_df = pd.DataFrame(buf, columns=[  # noqa: F841
                "trade_date", "stock_name", "sequence_no", "source", "updated_at"])
            con.register("_buf_df", _buf_df)
            try:
                con.execute("""
                    INSERT INTO fact_limit_advance_presence
                        (trade_date, stock_name, sequence_no, source, updated_at)
                    SELECT trade_date, stock_name, sequence_no, source, updated_at FROM _buf_df
                    ON CONFLICT (trade_date, stock_name) DO UPDATE SET
                        sequence_no = EXCLUDED.sequence_no,
                        source = EXCLUDED.source,
                        updated_at = EXCLUDED.updated_at
                """)
            finally:
                con.unregister("_buf_df")
            written = len(buf)

        agg = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT stock_name),"
            " MIN(trade_date), MAX(trade_date) FROM fact_limit_advance_presence"
        ).fetchone()
    finally:
        con.close()

    return {
        "table_id": table_id,
        "records": len(records),
        "stocks": stocks,
        "rows_written": written,
        "unresolved_cols": sorted(unresolved),
        "table_total": agg[0],
        "table_dates": agg[1],
        "table_stocks": agg[2],
        "date_min": str(agg[3]) if agg[3] else None,
        "date_max": str(agg[4]) if agg[4] else None,
    }
