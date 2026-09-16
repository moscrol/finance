"""板块日行情本地派生：成交额 = 成分求和，边际量 = 本地公式，涨幅优先官方 payload。

原 sync-sector-daily 对 403 个板块各打一次复盘会 K 线接口（403 请求/日）。回测
（consumption_registry.yaml sector_daily.formulas）表明：

- 成交额 = SUM(成分 amount)：相对误差中位 0.001%；
- 边际量 = (今额−昨额)/昨额×100：误差中位 0.003pp；
- 涨幅：题材类板块与成分等权几乎重合，但申万行业类板块是指数口径，等权会出现
  符号不一致 —— 所以涨幅**优先取** sectors/search payload 的官方值
  （ops_sector_search_payload_daily，宇宙请求顺带落库），缺则退等权均值。

写入走 ``SectorUniverseStore.replace_sector_daily``：行集合必须与当日宇宙精确相等、
关键列非空，与原抓取同一套校验。``multi_period_*`` 三列不是本模块产出，替换前先读
出来原样带回，不把别人的字段刷成 NULL。

``reconcile_sector_daily`` 是周抽样对账：挑 N 个板块打复盘会 K 线，对比本地行的
pct_chg/amount/diff_ratio 与双红判定。它是唯一还打复盘会 K 线的地方，成本 = N 请求。
"""
from __future__ import annotations

from datetime import date, datetime
import random
import statistics

from ..db import connect, init_db
from ..sector_universe import SectorUniverseStore
from ..signals import is_double_red
from ..sources import fupanhui_source as fs

LOCAL_SOURCE = "local:agg"
PCT_OFFICIAL = "pct=official"
PCT_EQW = "pct=eqw"


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _published_snapshot_id(con, td: date) -> str:
    rows = con.execute(
        """
        SELECT snapshot_id FROM ops_sector_universe_snapshot_daily
        WHERE trade_date = ? AND status = 'published'
        """,
        [td],
    ).fetchall()
    if len(rows) != 1:
        raise RuntimeError(f"{td} 需要且只能有一份 published 宇宙（当前 {len(rows)} 份），先 sync-sectors")
    return rows[0][0]


def _member_aggregates(con, td: date) -> dict[str, dict]:
    return {
        row[0]: {"amount": float(row[1]), "eq_pct": float(row[2]), "members": int(row[3])}
        for row in con.execute(
            """
            SELECT sector_ts_code, SUM(amount), AVG(pct_chg), COUNT(*)
            FROM fact_sector_stock_daily
            WHERE trade_date = ? AND amount IS NOT NULL AND pct_chg IS NOT NULL
            GROUP BY 1
            """,
            [td],
        ).fetchall()
    }


def _payload(con, td: date, snapshot_id: str) -> dict[str, dict]:
    return {
        row[0]: {"pct_chg": row[1], "strength": row[2]}
        for row in con.execute(
            """
            SELECT sector_ts_code, pct_chg, strength
            FROM ops_sector_search_payload_daily
            WHERE trade_date = ? AND snapshot_id = ?
            """,
            [td, snapshot_id],
        ).fetchall()
    }


def _prev_sector_amounts(con, td: date) -> tuple[date | None, dict[str, float]]:
    row = con.execute(
        "SELECT MAX(trade_date) FROM fact_sector_daily WHERE trade_date < ? AND amount IS NOT NULL",
        [td],
    ).fetchone()
    if not row or not row[0]:
        return None, {}
    prev = _as_date(row[0])
    amounts = {
        r[0]: float(r[1])
        for r in con.execute(
            "SELECT sector_ts_code, amount FROM fact_sector_daily WHERE trade_date = ? AND amount IS NOT NULL",
            [prev],
        ).fetchall()
    }
    return prev, amounts


def _prev_proxy_amounts(con, td: date, prev: date, sectors) -> dict[str, float]:
    """新板块没有昨日板块额：用今日成分 × 昨日个股额代理。"""
    if not sectors:
        return {}
    placeholders = ",".join("?" for _ in sectors)
    return {
        row[0]: float(row[1])
        for row in con.execute(
            f"""
            SELECT m.sector_ts_code, SUM(d.amount)
            FROM fact_sector_stock_daily AS m
            JOIN fact_stock_daily AS d
              ON d.trade_date = ? AND d.stock_ts_code = m.stock_ts_code
            WHERE m.trade_date = ? AND m.sector_ts_code IN ({placeholders})
            GROUP BY 1
            """,
            [prev, td, *sectors],
        ).fetchall()
    }


def _existing_multi_period(con, td: date, snapshot_id: str) -> dict[str, tuple]:
    # 读公开 VIEW 而不是代际表：视图只暴露 published 代际，且本模块不该出现在
    # check_sector_fact_access.py 的物理表访问名单里。
    return {
        row[0]: (row[1], row[2], row[3])
        for row in con.execute(
            """
            SELECT sector_ts_code, multi_period_resonance, multi_period_source, multi_period_updated_at
            FROM fact_sector_daily
            WHERE trade_date = ? AND sector_universe_snapshot_id = ?
            """,
            [td, snapshot_id],
        ).fetchall()
    }


def _previous_trading_day(con, td: date) -> date | None:
    row = con.execute(
        "SELECT MAX(trade_date) FROM fact_market_daily WHERE trade_date < ?", [td]
    ).fetchone()
    return _as_date(row[0]) if row and row[0] else None


def diff_ratio(amount: float, prev_amount: float | None) -> float | None:
    if prev_amount in (None, 0):
        return None
    return round((amount - prev_amount) / prev_amount * 100.0, 4)


def sync_sector_daily_local(trade_date, *, con=None, prefer_payload: bool = True) -> dict:
    """用当日成分行 + 宇宙 payload 派生 fact_sector_daily 当日全部行并原子替换。"""
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        snapshot_id = _published_snapshot_id(con, td)
        store = SectorUniverseStore(con)
        universe = store.published_snapshot(td)
        agg = _member_aggregates(con, td)
        missing_members = [s.sector_ts_code for s in universe.sectors if s.sector_ts_code not in agg]
        if missing_members:
            # fail closed：成分不齐就不派生，否则会把「没抓到」写成成交额 0。
            raise RuntimeError(
                f"{td} 有 {len(missing_members)} 个板块无成分行，先补 sector-stocks："
                f"{', '.join(missing_members[:8])}{'…' if len(missing_members) > 8 else ''}"
            )
        payload = _payload(con, td, snapshot_id) if prefer_payload else {}
        prev_date, prev_amounts = _prev_sector_amounts(con, td)
        calendar_prev = _previous_trading_day(con, td)
        need_proxy = [s.sector_ts_code for s in universe.sectors if s.sector_ts_code not in prev_amounts]
        proxy = _prev_proxy_amounts(con, td, prev_date, need_proxy) if prev_date and need_proxy else {}
        existing_mp = _existing_multi_period(con, td, snapshot_id)

        rows = []
        pct_official = pct_eqw = 0
        proxied = []
        no_prev = []
        now = datetime.now()
        for s in universe.sectors:
            code = s.sector_ts_code
            a = agg[code]
            official = payload.get(code, {}).get("pct_chg")
            if official is not None:
                pct = float(official)
                pct_official += 1
                tag = PCT_OFFICIAL
            else:
                pct = round(a["eq_pct"], 4)
                pct_eqw += 1
                tag = PCT_EQW
            prev_amt = prev_amounts.get(code)
            if prev_amt is None:
                prev_amt = proxy.get(code)
                if prev_amt is not None:
                    proxied.append(code)
            dr = diff_ratio(a["amount"], prev_amt)
            if dr is None:
                no_prev.append(code)
            mp = existing_mp.get(code, (None, None, None))
            rows.append(
                {
                    "sector_ts_code": code,
                    "pct_chg": pct,
                    "amount": round(a["amount"], 4),
                    "diff_ratio": dr,
                    "strength": payload.get(code, {}).get("strength"),
                    "multi_period_resonance": mp[0],
                    "multi_period_source": mp[1],
                    "multi_period_updated_at": mp[2],
                    "source": f"{LOCAL_SOURCE}/{tag}",
                    "updated_at": now,
                }
            )
        if no_prev:
            raise RuntimeError(
                f"{td} 有 {len(no_prev)} 个板块算不出边际量（无昨日板块额且无代理）："
                f"{', '.join(no_prev[:8])}"
            )
        written = store.replace_sector_daily(snapshot_id, rows)
    finally:
        if own:
            con.close()
    return {
        "trade_date": str(td),
        "snapshot_id": snapshot_id,
        "rows_written": written,
        "pct_official": pct_official,
        "pct_eqw": pct_eqw,
        "prev_date": str(prev_date) if prev_date else None,
        "prev_is_previous_trading_day": (prev_date == calendar_prev) if prev_date and calendar_prev else None,
        "prev_proxied": len(proxied),
        "prev_proxied_codes": proxied,
    }


def brief(summary: dict) -> str:
    gap = "" if summary.get("prev_is_previous_trading_day") in (True, None) else " prev_gap!"
    return (
        f"rows={summary['rows_written']} pct_official={summary['pct_official']} "
        f"pct_eqw={summary['pct_eqw']} prev={summary['prev_date']}{gap} proxied={summary['prev_proxied']}"
    )


# ---------------------------------------------------------------------------
# 周抽样对账
# ---------------------------------------------------------------------------

def _is_shuanghong(pct, amount, dr) -> bool | None:
    """严格双红判定；阈值只认 signals.py 那一份（单一真本源，棘轮测试守着）。"""
    if pct is None or amount is None or dr is None:
        return None
    return is_double_red(pct, dr, amount)


def compare_rows(local: dict[str, dict], provider: dict[str, dict]) -> dict:
    """本地行 vs 复盘会行，返回误差分位与双红翻转。纯函数，便于测试。"""
    amt_err, pct_err, dr_err = [], [], []
    sign_mismatch = 0
    flips = []
    compared = 0
    for code, p in provider.items():
        mine = local.get(code)
        if mine is None:
            continue
        compared += 1
        if p.get("amount") and mine.get("amount") is not None:
            amt_err.append(abs(mine["amount"] - p["amount"]) / abs(p["amount"]))
        if p.get("pct_chg") is not None and mine.get("pct_chg") is not None:
            pct_err.append(abs(mine["pct_chg"] - p["pct_chg"]))
            if (mine["pct_chg"] > 0) != (p["pct_chg"] > 0):
                sign_mismatch += 1
        if p.get("diff_ratio") is not None and mine.get("diff_ratio") is not None:
            dr_err.append(abs(mine["diff_ratio"] - p["diff_ratio"]))
        ls = _is_shuanghong(mine.get("pct_chg"), mine.get("amount"), mine.get("diff_ratio"))
        ps = _is_shuanghong(p.get("pct_chg"), p.get("amount"), p.get("diff_ratio"))
        if ls is not None and ps is not None and ls != ps:
            flips.append(code)

    def _q(values, q):
        if not values:
            return None
        values = sorted(values)
        idx = min(len(values) - 1, int(round(q * (len(values) - 1))))
        return round(values[idx], 6)

    return {
        "compared": compared,
        "amount_relerr_median": _q(amt_err, 0.5),
        "amount_relerr_max": round(max(amt_err), 6) if amt_err else None,
        "pct_abs_err_median": _q(pct_err, 0.5),
        "pct_abs_err_p95": _q(pct_err, 0.95),
        "pct_sign_mismatch": sign_mismatch,
        "diff_ratio_abs_err_median": _q(dr_err, 0.5),
        "diff_ratio_abs_err_p95": _q(dr_err, 0.95),
        "shuanghong_flips": flips,
        "ok": not flips and (statistics.median(amt_err) < 0.01 if amt_err else True),
    }


def reconcile_sector_daily(trade_date, *, con=None, sample: int = 20, seed: int | None = None) -> dict:
    """抽样 N 个板块打复盘会 K 线，对比本地派生行。成本 = N 请求。"""
    td = _as_date(trade_date)
    own = con is None
    if own:
        con = connect(read_only=True)
    try:
        local = {
            row[0]: {"pct_chg": row[1], "amount": row[2], "diff_ratio": row[3], "source": row[4]}
            for row in con.execute(
                "SELECT sector_ts_code, pct_chg, amount, diff_ratio, source FROM fact_sector_daily WHERE trade_date = ?",
                [td],
            ).fetchall()
        }
    finally:
        if own:
            con.close()
    if not local:
        raise RuntimeError(f"{td} 无 fact_sector_daily 行")
    codes = sorted(local)
    # 一半按成交额最大（双红候选集中在这里），一半随机，兼顾头部与长尾。
    by_amount = sorted(codes, key=lambda c: -(local[c]["amount"] or 0))
    head = by_amount[: max(1, sample // 2)]
    rng = random.Random(seed)
    tail_pool = [c for c in codes if c not in head]
    tail = rng.sample(tail_pool, min(len(tail_pool), sample - len(head)))
    picked = head + tail
    klines = fs.get_sector_klines_batch(picked, trade_date=str(td), days=20)
    provider: dict[str, dict] = {}
    for code, points in klines.items():
        for p in points or []:
            if str(p.get("trade_date"))[:10] == str(td):
                provider[code] = {
                    "pct_chg": p.get("pct_chg"),
                    "amount": p.get("amount"),
                    "diff_ratio": p.get("diff_ratio"),
                }
    result = compare_rows(local, provider)
    result.update({"trade_date": str(td), "sampled": len(picked), "provider_rows": len(provider)})
    return result
