"""同步飞书「每日指标」表 -> fact_market_daily。

数据源: 飞书 Bitable daily 表 (每个交易日 1 条市场复盘指标)。
凭证与工具复用项目根目录 shared/feishu_utils.py。
全部字段在飞书侧为 text, 这里解析为数值/日期后 upsert 进 fact_market_daily。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime

from ..db import connect, init_db, PROJECT_DIR

# 复用 shared/feishu_utils.py
sys.path.insert(0, str(PROJECT_DIR / "shared"))
from feishu_utils import load_config, get_token, fetch_all_records  # noqa: E402


def _flat(v):
    """飞书 text 字段可能是字符串, 也可能是 [{text:...}] 富文本段, 统一拍平。"""
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


def _num(v):
    s = _flat(v)
    if s is None:
        return None
    s = str(s).strip().replace("%", "").replace("+", "").replace(",", "")
    if s in ("", "-", "—", "/", "无", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _int(v):
    f = _num(v)
    return int(f) if f is not None else None


_DATE_YY = re.compile(r"^\d{2}-\d{2}-\d{2}$")
_DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date(v):
    s = _txt(v)
    if not s:
        return None
    if _DATE_YY.match(s):
        s = "20" + s
    if not _DATE_FULL.match(s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


UPSERT_SQL = """
    INSERT INTO fact_market_daily
        (trade_date, market_stage, stage_day, ice_point, total_amount,
         amount_vs_yesterday_pct, amount_ma20, volume_ratio, volume_state,
         advancers, limit_up, limit_down, sh_week_ma, sh_deviation_pct,
         top3_industry_ratio, concentration_state,
         industry_1, industry_1_ratio, industry_2, industry_2_ratio,
         industry_3, industry_3_ratio, note, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date) DO UPDATE SET
        market_stage = excluded.market_stage,
        stage_day = excluded.stage_day,
        ice_point = excluded.ice_point,
        total_amount = excluded.total_amount,
        amount_vs_yesterday_pct = excluded.amount_vs_yesterday_pct,
        amount_ma20 = excluded.amount_ma20,
        volume_ratio = excluded.volume_ratio,
        volume_state = excluded.volume_state,
        advancers = excluded.advancers,
        limit_up = excluded.limit_up,
        limit_down = excluded.limit_down,
        sh_week_ma = excluded.sh_week_ma,
        sh_deviation_pct = excluded.sh_deviation_pct,
        top3_industry_ratio = excluded.top3_industry_ratio,
        concentration_state = excluded.concentration_state,
        industry_1 = excluded.industry_1,
        industry_1_ratio = excluded.industry_1_ratio,
        industry_2 = excluded.industry_2,
        industry_2_ratio = excluded.industry_2_ratio,
        industry_3 = excluded.industry_3,
        industry_3_ratio = excluded.industry_3_ratio,
        note = excluded.note,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def sync_fact_market_daily() -> dict:
    """从飞书 daily 表全量拉取并 upsert 进 fact_market_daily。"""
    cfg = load_config()
    token = get_token(cfg)
    table_id = cfg["tables"]["daily"]
    app_token = cfg["app_token"]
    records = fetch_all_records(token, table_id, app_token=app_token)

    now = datetime.now()
    rows = []
    skipped = []
    for r in records:
        f = r.get("fields", {})
        d = _date(f.get("日期"))
        if not d:
            skipped.append(_txt(f.get("日期")) or r.get("record_id"))
            continue
        rows.append((
            d,
            _txt(f.get("阶段")),
            _int(f.get("天数")),
            _txt(f.get("冰点")),
            _num(f.get("成交额")),
            _num(f.get("较昨日比")),
            _num(f.get("20日均")),
            _num(f.get("相对量能比")),
            _txt(f.get("量能状态")),
            _int(f.get("涨")),
            _int(f.get("涨停")),
            _int(f.get("跌停")),
            _num(f.get("周均线")),
            _num(f.get("偏离度")),
            _num(f.get("前三占比")),
            _txt(f.get("集中度")),
            _txt(f.get("行业1")),
            _num(f.get("占比1")),
            _txt(f.get("行业2")),
            _num(f.get("占比2")),
            _txt(f.get("行业3")),
            _num(f.get("占比3")),
            None,
            "feishu:daily",
            now,
        ))

    if not rows:
        raise RuntimeError(f"飞书 daily 表未解析到有效记录 (拉取 {len(records)} 条)")

    init_db()
    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        con.executemany(UPSERT_SQL, rows)
        con.execute("COMMIT")
        total = con.execute("SELECT COUNT(*) FROM fact_market_daily").fetchone()[0]
        rng = con.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM fact_market_daily"
        ).fetchone()
        null_amt = con.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE total_amount IS NULL"
        ).fetchone()[0]
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    return {
        "fetched": len(records),
        "written": len(rows),
        "skipped": skipped,
        "table_total": total,
        "date_min": str(rng[0]) if rng[0] else None,
        "date_max": str(rng[1]) if rng[1] else None,
        "null_total_amount": null_amt,
    }
