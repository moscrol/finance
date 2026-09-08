"""成分拼接器：identity（谁在名单里）走复盘会低频，value（今天多少钱）走东财日更。

为什么存在：原 sync-sector-stocks 每天对 403 个板块各打一次复盘会明细接口，是整条
daily-full 里请求量最大的一步；而 5 日 Jaccard 0.999 说明名单几乎不变，变的只是数字
（consumption_registry.yaml sector_members）。本模块把两者拆开：

- **探针** ``identity_delta``：拿当日已发布宇宙与前一发布日比 expected_stock_count。
  没变的板块视为 identity 未动；变了 / 新增的留给复盘会 delta 拉取。
  这个探针不发请求——宇宙请求本来每天就要发一次。
- **拼接** ``stitch_sector_members``：对 identity 未动的板块，取该板块最近一次
  ``source='fupanhui'`` 的成分名单作 identity 基线，逐只 join 当日东财真值，
  经 ``SectorUniverseStore.record_member_result`` 写入（校验 + 台账与正常抓取同一套），
  ``source='local:stitch'``。

三条硬约束（都来自门禁 / 深模块的既有契约，不是本模块自设）：
1. 值只接受东财快照源。``fill-stock-daily-fallback`` 的行来自成分表本身，拿它拼接是循环。
2. 东财无当日值的成员（停牌/退市）**剔除**，不留 NULL——``check_daily_review_data`` 不容
   price/pct_chg/amount 为空；``fast_daily_sync.py`` 被禁正是因为拷旧行留空值。
3. 交付数不得超过声明数，缺口不得超过 ``sector_universe`` 的既有上界；超了就不拼，
   留 pending 给复盘会。这样拼接永远不会让完成度审计比真抓取更宽松。

基线为什么取「最近一次 fupanhui 名单」而不是「昨日行」：昨日行可能本身是拼接行；
若链式拼接，某只股停牌一天被剔除后就再也回不来，直到周五全量。以 fupanhui 名单为锚，
停牌复牌当天自动回归。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..db import connect, init_db
from ..sector_universe import (
    MEMBER_SHORTFALL_MAX_ABSOLUTE,
    MEMBER_SHORTFALL_MAX_RATIO,
    MemberResult,
    SectorUniverseStore,
)

STITCH_SOURCE = "local:stitch"
PROVIDER_SOURCE = "fupanhui"
# 只接受这些前缀的个股日线作为 value 源；fallback 源来自成分表自身（循环）。
VALUE_SOURCE_PREFIXES = ("eastmoney", "mootdx", "tencent")
# 基线最多回看多少个日历日；再旧说明该板块长期抓不到，交回复盘会。
DEFAULT_MAX_BASELINE_AGE_DAYS = 10
# N 日涨幅复算需要的历史窗口（日历日；20 个交易日约 28~30 个日历日）。
_HISTORY_CALENDAR_DAYS = 45


def _shortfall_bound(expected: int) -> float:
    return max(float(MEMBER_SHORTFALL_MAX_ABSOLUTE), expected * MEMBER_SHORTFALL_MAX_RATIO)


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass(frozen=True)
class IdentityDelta:
    """当日已发布宇宙相对前一发布日的 expected_stock_count 变动。"""

    trade_date: date
    prev_date: date | None
    snapshot_id: str
    expected: dict[str, int]
    unchanged: tuple[str, ...]
    changed: tuple[str, ...]
    new: tuple[str, ...]
    gone: tuple[str, ...]

    def brief(self) -> str:
        return (
            f"{self.trade_date} vs {self.prev_date or '-'}: unchanged={len(self.unchanged)} "
            f"changed={len(self.changed)} new={len(self.new)} gone={len(self.gone)}"
        )


def identity_delta(con, trade_date) -> IdentityDelta:
    td = _as_date(trade_date)
    today = con.execute(
        """
        SELECT u.sector_ts_code, u.expected_stock_count, u.snapshot_id
        FROM fact_sector_universe_daily AS u
        JOIN ops_sector_universe_snapshot_daily AS h
          ON h.trade_date = u.trade_date AND h.snapshot_id = u.snapshot_id
        WHERE u.trade_date = ? AND h.status = 'published'
        """,
        [td],
    ).fetchall()
    if not today:
        raise RuntimeError(f"{td} 无已发布板块宇宙，先运行 sync-sectors")
    snapshot_ids = {row[2] for row in today}
    if len(snapshot_ids) != 1:
        raise RuntimeError(f"{td} 有多份 published 快照: {sorted(snapshot_ids)}")
    snapshot_id = snapshot_ids.pop()
    expected = {row[0]: int(row[1]) for row in today}

    prev_row = con.execute(
        """
        SELECT MAX(trade_date) FROM ops_sector_universe_snapshot_daily
        WHERE status = 'published' AND trade_date < ?
        """,
        [td],
    ).fetchone()
    prev_date = _as_date(prev_row[0]) if prev_row and prev_row[0] else None
    prev: dict[str, int] = {}
    if prev_date is not None:
        prev = {
            row[0]: int(row[1])
            for row in con.execute(
                """
                SELECT u.sector_ts_code, u.expected_stock_count
                FROM fact_sector_universe_daily AS u
                JOIN ops_sector_universe_snapshot_daily AS h
                  ON h.trade_date = u.trade_date AND h.snapshot_id = u.snapshot_id
                WHERE u.trade_date = ? AND h.status = 'published'
                """,
                [prev_date],
            ).fetchall()
        }
    unchanged, changed, new = [], [], []
    for code, count in sorted(expected.items()):
        if code not in prev:
            new.append(code)
        elif prev[code] == count:
            unchanged.append(code)
        else:
            changed.append(code)
    gone = sorted(set(prev) - set(expected))
    return IdentityDelta(
        trade_date=td,
        prev_date=prev_date,
        snapshot_id=snapshot_id,
        expected=expected,
        unchanged=tuple(unchanged),
        changed=tuple(changed),
        new=tuple(new),
        gone=tuple(gone),
    )


def _member_statuses(con, trade_date: date, snapshot_id: str) -> dict[str, str]:
    return {
        row[0]: row[1]
        for row in con.execute(
            """
            SELECT sector_ts_code, status FROM ops_sector_member_sync_daily
            WHERE trade_date = ? AND snapshot_id = ?
            """,
            [trade_date, snapshot_id],
        ).fetchall()
    }


def _today_values(con, trade_date: date) -> dict[str, dict]:
    """当日东财真值 + N 日涨幅本地复算。只保留 price/pct_chg/amount 三者齐全的行。"""
    since = trade_date - timedelta(days=_HISTORY_CALENDAR_DAYS)
    like_clauses = " OR ".join("source LIKE ?" for _ in VALUE_SOURCE_PREFIXES)
    params = [since, trade_date, *[f"{p}%" for p in VALUE_SOURCE_PREFIXES], trade_date]
    rows = con.execute(
        f"""
        WITH hist AS (
            SELECT stock_ts_code, trade_date, close, pct_chg, amount, source,
                   LAG(close, 3)  OVER w AS c3,
                   LAG(close, 5)  OVER w AS c5,
                   LAG(close, 10) OVER w AS c10,
                   LAG(close, 20) OVER w AS c20
            FROM fact_stock_daily
            WHERE trade_date >= ? AND trade_date <= ?
            WINDOW w AS (PARTITION BY stock_ts_code ORDER BY trade_date)
        )
        SELECT stock_ts_code, close, pct_chg, amount, c3, c5, c10, c20
        FROM hist
        WHERE ({like_clauses}) AND trade_date = ?
          AND close IS NOT NULL AND pct_chg IS NOT NULL AND amount IS NOT NULL
        """,
        params,
    ).fetchall()

    def _ret(close, base):
        if close is None or base in (None, 0):
            return None
        return round((float(close) / float(base) - 1.0) * 100.0, 4)

    out: dict[str, dict] = {}
    for code, close, pct, amt, c3, c5, c10, c20 in rows:
        out[code] = {
            "price": float(close),
            "pct_chg": float(pct),
            "amount": float(amt),
            "pct_chg_3d": _ret(close, c3),
            "pct_chg_5d": _ret(close, c5),
            "pct_chg_10d": _ret(close, c10),
            "pct_chg_20d": _ret(close, c20),
        }
    return out


def _high_status(con, trade_date: date) -> dict[str, tuple[str | None, str | None]]:
    return {
        row[0]: (row[1], row[2])
        for row in con.execute(
            """
            SELECT stock_ts_code, primary_high_period, primary_high_label
            FROM fact_stock_high_daily WHERE trade_date = ?
            """,
            [trade_date],
        ).fetchall()
    }


def _limit_times(con, trade_date: date) -> dict[str, int]:
    return {
        row[0]: int(row[1])
        for row in con.execute(
            """
            SELECT stock_ts_code, MAX(limit_times)
            FROM fact_theme_limit_stock_daily
            WHERE trade_date = ? AND limit_times IS NOT NULL
            GROUP BY 1
            """,
            [trade_date],
        ).fetchall()
    }


def _baselines(con, trade_date: date, sectors, max_age_days: int) -> dict[str, tuple[date, list[dict]]]:
    """每个板块最近一次 fupanhui 名单（trade_date 之前、max_age_days 以内）。"""
    if not sectors:
        return {}
    since = trade_date - timedelta(days=max_age_days)
    placeholders = ",".join("?" for _ in sectors)
    rows = con.execute(
        f"""
        WITH latest AS (
            SELECT sector_ts_code, MAX(trade_date) AS base_date
            FROM fact_sector_stock_daily
            WHERE trade_date < ? AND trade_date >= ? AND source = ?
              AND sector_ts_code IN ({placeholders})
            GROUP BY 1
        )
        SELECT s.sector_ts_code, s.trade_date, s.stock_ts_code, s.stock_name,
               s.price, s.sw_industry, s.leader_plate, s.leader_sub_plate,
               s.role_tags_json, s.circ_mv, s.float_mcap_yi, s.total_mcap_yi,
               s.free_float_mcap_yi, s.mcap_source
        FROM fact_sector_stock_daily AS s
        JOIN latest AS l
          ON l.sector_ts_code = s.sector_ts_code AND l.base_date = s.trade_date
        WHERE s.source = ?
        ORDER BY s.sector_ts_code, s.stock_ts_code
        """,
        [trade_date, since, PROVIDER_SOURCE, *sectors, PROVIDER_SOURCE],
    ).fetchall()
    out: dict[str, tuple[date, list[dict]]] = {}
    for row in rows:
        sector = row[0]
        base_date = _as_date(row[1])
        member = {
            "stock_ts_code": row[2],
            "stock_name": row[3],
            "base_price": row[4],
            "sw_industry": row[5],
            "leader_plate": row[6],
            "leader_sub_plate": row[7],
            "role_tags_json": row[8],
            "circ_mv": row[9],
            "float_mcap_yi": row[10],
            "total_mcap_yi": row[11],
            "free_float_mcap_yi": row[12],
            "mcap_source": row[13],
        }
        out.setdefault(sector, (base_date, []))[1].append(member)
    return out


def _scale(value, price, base_price):
    if value is None or price is None or base_price in (None, 0):
        return None
    return float(value) * float(price) / float(base_price)


def _fetch_caps(codes: list[str]) -> dict[str, dict]:
    """腾讯行情市值（非复盘会源）。任何失败都退回空 dict，由调用方按基线缩放。"""
    try:
        from .sync_fupanhui_sector_stock_daily import _tencent_market_caps

        return _tencent_market_caps(codes)
    except Exception:  # noqa: BLE001 —— 市值是附属字段，拿不到不该阻断拼接
        return {}


def build_rows(
    members: list[dict],
    values: dict[str, dict],
    *,
    highs: dict[str, tuple[str | None, str | None]],
    limits: dict[str, int],
    caps: dict[str, dict],
) -> tuple[list[dict], list[str]]:
    """基线成员 × 当日真值 → record_member_result 需要的 stocks 映射；返回 (rows, dropped)。"""
    rows: list[dict] = []
    dropped: list[str] = []
    for m in members:
        code = m["stock_ts_code"]
        v = values.get(code)
        if v is None:
            dropped.append(code)
            continue
        cap = caps.get(code) or {}
        hs, hl = highs.get(code, (None, None))
        if cap.get("float_mcap_yi") is not None or cap.get("total_mcap_yi") is not None:
            float_mcap = cap.get("float_mcap_yi")
            total_mcap = cap.get("total_mcap_yi")
            mcap_source = cap.get("mcap_source") or "tencent"
        else:
            float_mcap = _scale(m.get("float_mcap_yi"), v["price"], m.get("base_price"))
            total_mcap = _scale(m.get("total_mcap_yi"), v["price"], m.get("base_price"))
            mcap_source = "local:scaled" if (float_mcap is not None or total_mcap is not None) else None
        rows.append(
            {
                "ts_code": code,
                "name": m.get("stock_name"),
                "price": v["price"],
                "pct_chg": v["pct_chg"],
                "amount": v["amount"],
                "pct_chg_3d": v["pct_chg_3d"],
                "pct_chg_5d": v["pct_chg_5d"],
                "pct_chg_10d": v["pct_chg_10d"],
                "pct_chg_20d": v["pct_chg_20d"],
                "high_status": hs,
                "high_status_label": hl,
                "limit_times": limits.get(code),
                "fund_flow_1d": None,
                "fund_flow_5d": None,
                "sw_industry": m.get("sw_industry"),
                "leader_plate": m.get("leader_plate"),
                "leader_sub_plate": m.get("leader_sub_plate"),
                "role_tags_json": m.get("role_tags_json"),
                "circ_mv": _scale(m.get("circ_mv"), v["price"], m.get("base_price")),
                "float_mcap_yi": float_mcap,
                "total_mcap_yi": total_mcap,
                "free_float_mcap_yi": None,
                "mcap_source": mcap_source,
                "source": STITCH_SOURCE,
            }
        )
    return rows, dropped


def stitch_sector_members(
    trade_date,
    *,
    con=None,
    fetch_caps: bool = True,
    dry_run: bool = False,
    include_completed: bool = False,
    max_baseline_age_days: int = DEFAULT_MAX_BASELINE_AGE_DAYS,
) -> dict:
    """对 identity 未动且尚未完成的板块做本地拼接。返回可进 runlog 的摘要。

    ``dry_run`` 只算不写，摘要里带 ``rows``（按板块）供对账；``include_completed``
    连已 success 的板块也算（仅供在历史快照上回测拼接精度，生产路径不用）。
    """
    td = _as_date(trade_date)
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        store = SectorUniverseStore(con)
        delta = identity_delta(con, td)
        statuses = _member_statuses(con, td, delta.snapshot_id)
        candidates = [
            code
            for code in delta.unchanged
            if include_completed or statuses.get(code) in {"pending", "empty", "error"}
        ]
        values = _today_values(con, td)
        if not values:
            raise RuntimeError(
                f"{td} fact_stock_daily 没有东财/通达信源的当日行，先运行 sync-stock-daily-snapshot"
            )
        highs = _high_status(con, td)
        limits = _limit_times(con, td)
        baselines = _baselines(con, td, candidates, max_baseline_age_days)

        caps: dict[str, dict] = {}
        if fetch_caps and not dry_run and candidates:
            codes = sorted(
                {m["stock_ts_code"] for code in candidates for m in baselines.get(code, (None, []))[1]}
            )
            caps = _fetch_caps(codes)

        stitched: list[str] = []
        skipped: dict[str, list[str]] = {}
        failed: list[tuple[str, str]] = []
        dropped_total = 0
        base_dates: Counter = Counter()
        dry_rows: dict[str, list[dict]] = {}

        def _skip(code: str, reason: str) -> None:
            skipped.setdefault(reason, []).append(code)

        for code in candidates:
            base = baselines.get(code)
            if base is None:
                _skip(code, "no_baseline")
                continue
            base_date, members = base
            rows, dropped = build_rows(members, values, highs=highs, limits=limits, caps=caps)
            expected = delta.expected[code]
            if len(rows) > expected:
                _skip(code, "surplus")
                continue
            if expected - len(rows) > _shortfall_bound(expected):
                _skip(code, "shortfall")
                continue
            dropped_total += len(dropped)
            base_dates[str(base_date)] += 1
            if dry_run:
                dry_rows[code] = rows
                stitched.append(code)
                continue
            receipt = store.record_member_result(
                delta.snapshot_id,
                code,
                MemberResult.success(served_date=str(td), stocks=rows),
            )
            if receipt.status == "success":
                stitched.append(code)
            else:
                failed.append((code, receipt.last_error_code or receipt.status))

        audit = None
        if not dry_run:
            audit = store.completion_audit(td, declared_tables=frozenset({"fact_sector_stock_daily"}))
    finally:
        if own:
            con.close()

    skipped_count = sum(len(v) for v in skipped.values())
    pending_for_provider = len(delta.changed) + len(delta.new) + skipped_count + len(failed)
    summary = {
        "trade_date": str(td),
        "snapshot_id": delta.snapshot_id,
        "identity": delta.brief(),
        "candidates": len(candidates),
        "stitched": len(stitched),
        "skipped": {k: len(v) for k, v in skipped.items()},
        "skipped_codes": skipped,
        "failed": failed,
        "dropped_members": dropped_total,
        "baseline_dates": dict(base_dates),
        "pending_for_provider": pending_for_provider,
        "caps_fetched": len(caps),
        "audit": audit.brief() if audit is not None else None,
        "audit_complete": bool(audit.complete) if audit is not None else None,
        "dry_run": dry_run,
    }
    if dry_run:
        summary["rows"] = dry_rows
    return summary


def brief(summary: dict) -> str:
    """一行进 runlog。"""
    skipped = ",".join(f"{k}={v}" for k, v in (summary.get("skipped") or {}).items()) or "-"
    return (
        f"stitched={summary['stitched']}/{summary['candidates']} "
        f"skipped[{skipped}] provider_pending={summary['pending_for_provider']} "
        f"dropped={summary['dropped_members']} | {summary['identity']}"
    )
