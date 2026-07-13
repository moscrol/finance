"""同步复盘会每日“主线题材 → 核心板块”到 DuckDB。

数据源: fupanhui.com 公开 API（无需登录）
  - /topics/mainline-themes   → 遍历当日主线题材
  - /topics/mainline-sectors  → 每个题材对应的核心板块 + 周期状态
写入: fact_mainline_sector_daily (upsert, 幂等)。

语义层级: L4_market_signal —— “每日主线题材 → 核心板块 → 板块周期状态”的每日
市场主线归因桥, 不是静态概念归属, 供 Theme Radar / Ask / daily-agent 消费,
不写知识库实体正文。

映射说明: mainline-sectors 返回的 sector_code 已是板块 ts_code 形态
(如 885552.TI / 990001.FP), 直接作为 sector_ts_code 落库; 少数复盘会自有编码
(*.FP) 不在 dim_sector 中, 因此这里不强制 dim_sector 外键校验, 以免丢主线板块。
"""
from __future__ import annotations

import time
from datetime import datetime, date

from ..db import connect, init_db
from ..sources import fupanhui_source as fs


SOURCE = "fupanhui:public-api/topics/mainline-sectors"

UPSERT_SQL = """
    INSERT INTO fact_mainline_sector_daily
        (trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no,
         today_pct, limit_up_count, max_limit_height, amount, amount_estimated,
         amount_relative_ratio, net_inflow_1d, strength, strength_chg,
         cycle_level, cycle_status,
         startup_date_small, startup_date_big, startup_date_super, startup_date_extend,
         high_status, high_status_label,
         near_breakout_status, near_breakout_label, near_breakout_gap_pct,
         note, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, theme_code, sector_ts_code) DO UPDATE SET
        theme_name = excluded.theme_name,
        sector_name = excluded.sector_name,
        sort_no = excluded.sort_no,
        today_pct = excluded.today_pct,
        limit_up_count = excluded.limit_up_count,
        max_limit_height = excluded.max_limit_height,
        amount = excluded.amount,
        amount_estimated = excluded.amount_estimated,
        amount_relative_ratio = excluded.amount_relative_ratio,
        net_inflow_1d = excluded.net_inflow_1d,
        strength = excluded.strength,
        strength_chg = excluded.strength_chg,
        cycle_level = excluded.cycle_level,
        cycle_status = excluded.cycle_status,
        startup_date_small = excluded.startup_date_small,
        startup_date_big = excluded.startup_date_big,
        startup_date_super = excluded.startup_date_super,
        startup_date_extend = excluded.startup_date_extend,
        high_status = excluded.high_status,
        high_status_label = excluded.high_status_label,
        near_breakout_status = excluded.near_breakout_status,
        near_breakout_label = excluded.near_breakout_label,
        near_breakout_gap_pct = excluded.near_breakout_gap_pct,
        note = excluded.note,
        source = excluded.source,
        updated_at = excluded.updated_at
"""


def _parse_date(val):
    """把 YYYY-MM-DD / YY-MM-DD 字符串转 date; 空串或非法返回 None。"""
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def sync(
    trade_date: str,
    *,
    attempts: int = 3,
    retry_delay: float = 0.5,
) -> dict:
    """同步某日“主线题材 → 核心板块”到 fact_mainline_sector_daily。

    - 幂等: 主键 (trade_date, theme_code, sector_ts_code) upsert, 重复执行不膨胀。
    - 单题材失败记入 failures。
    - 全部题材抓取并校验通过后才原子替换当日快照。

    Returns: {"themes": int, "sectors": int, "failures": [...], "status": str}
    """
    themes = None
    last_theme_error = None
    for attempt in range(max(1, attempts)):
        if attempt:
            time.sleep(retry_delay * attempt)
        try:
            candidate = fs.get_mainline_themes(trade_date)
            if candidate:
                themes = candidate
                break
            last_theme_error = RuntimeError("empty theme list")
        except Exception as exc:  # noqa: BLE001
            last_theme_error = exc
    if themes is None:
        return {
            "themes": 0,
            "sectors": 0,
            "expected_themes": 0,
            "failures": [{"scope": "themes", "error": str(last_theme_error)}],
            "status": "failed",
        }

    now = datetime.utcnow().isoformat()
    theme_ok = 0
    all_rows = []
    failures = []
    for t in themes:
        tc = str(t.get("theme_code") or "").strip()
        tn = str(t.get("theme_name") or "").strip()
        if not tc:
            failures.append(
                {"scope": "theme", "theme_code": "", "theme_name": tn, "error": "missing theme_code"}
            )
            continue
        sectors = None
        last_error = None
        for attempt in range(max(1, attempts)):
            if attempt:
                time.sleep(retry_delay * attempt)
            try:
                candidate = fs.get_mainline_sectors(trade_date, tc)
                if not any(str(item.get("sector_code") or "").strip() for item in candidate or []):
                    last_error = RuntimeError("empty sector list")
                    continue
                sectors = candidate
            except Exception as e:  # noqa: BLE001 单题材失败不影响全批
                last_error = e
                continue
            break
        if sectors is None:
            failures.append(
                {"scope": "sectors", "theme_code": tc, "theme_name": tn, "error": str(last_error)}
            )
            continue

        rows = []
        for s in sectors:
            sector_ts_code = str(s.get("sector_code") or "").strip()
            if not sector_ts_code:
                continue
            rows.append((
                trade_date, tc, tn,
                sector_ts_code,
                s.get("sector_name", ""),
                s.get("sort_no"),
                s.get("today_pct"),
                s.get("limit_up_count"),
                s.get("max_limit_height"),
                s.get("amount"),
                s.get("amount_estimated"),
                s.get("amount_relative_ratio"),
                s.get("net_inflow_1d"),
                s.get("strength"),
                s.get("strength_chg"),
                s.get("cycle_level"),
                s.get("cycle_status"),
                _parse_date(s.get("startup_date_small")),
                _parse_date(s.get("startup_date_big")),
                _parse_date(s.get("startup_date_super")),
                _parse_date(s.get("startup_date_extend")),
                s.get("high_status"),
                s.get("high_status_label"),
                s.get("near_breakout_status"),
                s.get("near_breakout_label"),
                s.get("near_breakout_gap_pct"),
                s.get("note", ""),
                SOURCE,
                now,
            ))
        if not rows:
            failures.append(
                {
                    "scope": "sectors",
                    "theme_code": tc,
                    "theme_name": tn,
                    "error": "empty sector list",
                }
            )
            continue
        all_rows.extend(rows)
        theme_ok += 1
        time.sleep(0.3)

    status = "complete" if theme_ok == len(themes) and not failures else (
        "partial" if theme_ok else "failed"
    )
    if status != "complete":
        return {
            "themes": 0,
            "sectors": 0,
            "expected_themes": len(themes),
            "completed_themes": theme_ok,
            "failures": failures,
            "status": status,
        }

    init_db()
    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM fact_mainline_sector_daily WHERE trade_date = ?", [trade_date])
        con.executemany(UPSERT_SQL, all_rows)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    return {
        "themes": theme_ok,
        "sectors": len(all_rows),
        "expected_themes": len(themes),
        "completed_themes": theme_ok,
        "failures": [],
        "status": "complete",
    }


if __name__ == "__main__":
    import json
    import sys

    td = sys.argv[1] if len(sys.argv) > 1 else (fs.get_latest_date_public() or "")
    print(json.dumps(sync(td), ensure_ascii=False, indent=2))
