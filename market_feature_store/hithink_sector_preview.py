"""同花顺名单 × canonical 日线的只读计算预览，不发布、不外呼。

目的不是复刻复盘会名单，而是在可追溯的新池上复用边际量/双红规则。
涨幅必须显式选成员等权或同花顺指数收盘收益，缺数据不能相互兜底；成交额在
同一选定名单上比较相邻交易日，不冒充历史供应商日序列。canonical 行情由既有入库链提供；
本模块不将原始 dump（元/股）绕过换算直接写入事实表。

calculation_ready 只证明所选目录和名单内输入可算；production_ready 永远 False：
请求完成度与供应商完整性分别报告，canonical 投影及下游真实产物尚需独立验收。
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math

from .signals import is_double_red
from .hithink_sector_contract import (
    CATALOG_TAGS,
    SOURCE_CATALOG,
    SOURCE_CONSTITUENT,
    SOURCE_KLINE,
)
from .trading_days import closed_dates, previous_scheduled_trading_day

PCT_BASES = ("member_equal_weight", "index_close_return")


def _date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _finite(value, *, positive=False, nonnegative=False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return (math.isfinite(value) and (not positive or value > 0)
            and (not nonnegative or value >= 0))


def _independent_source(source) -> bool:
    from .sync.sync_local_sector_members import VALUE_SOURCE_PREFIXES

    return str(source or "").split(":", 1)[0] in VALUE_SOURCE_PREFIXES


def _index_returns(con, td: date, prev: date) -> dict[str, float]:
    """只认相邻计划交易日的唯一指数 bar；不跨空日、不向等权回落。"""
    bars: dict[tuple, tuple] = {}
    duplicates = set()
    for day, code, close, source in con.execute(
        "SELECT trade_date, sector_ts_code, close, source FROM fact_sector_kline_daily "
        "WHERE trade_date IN (?, ?) ORDER BY 1, 2", [prev, td],
    ).fetchall():
        key = (_date(day), code)
        if key in bars:
            duplicates.add(key)
        bars[key] = (close, source)
    returns = {}
    for day, code in bars:
        current, prior = bars.get((td, code)), bars.get((prev, code))
        if (day != td or not prior or (td, code) in duplicates or (prev, code) in duplicates):
            continue
        if any(source != SOURCE_KLINE or not _finite(close, positive=True)
               for close, source in (current, prior)):
            continue
        pct = (current[0] / prior[0] - 1) * 100
        if _finite(pct):
            returns[code] = round(pct, 4)
    return returns


def preview_sector_calculation(
    con, trade_date, *, member_date, category: str, pct_basis: str,
    max_member_age_days: int = 0, capture_id: str | None = None,
) -> dict:
    """只读；缺任一成员关键值即阻断该板块，不把缺数据默默变成缩小名单。"""
    # CLI 构建参数时只取选项常量，不提前载入复盘计算/供应商模块。
    from .sync.sync_local_sector_daily import diff_ratio

    td, md = _date(trade_date), _date(member_date)
    age = (td - md).days
    if max_member_age_days < 0 or not 0 <= age <= max_member_age_days:
        raise ValueError("member_date 不能晚于目标日或超过显式允许的名单年龄")
    closures = closed_dates(td.year)
    prev = previous_scheduled_trading_day(td)
    if closures is None or td.weekday() >= 5 or td in closures or prev is None:
        raise ValueError("无法确认目标及前一交易日；不以库里最近有行的一天代替")
    if category not in CATALOG_TAGS:
        raise ValueError(f"category 必须为 {CATALOG_TAGS}，不混入宽基指数")
    if pct_basis not in PCT_BASES:
        raise ValueError(f"pct_basis 必须显式选择 {PCT_BASES}")
    index_returns = _index_returns(con, td, prev) if pct_basis == "index_close_return" else {}

    capture_audit = None
    if capture_id is not None:
        from .hithink_sector_capture import capture_inputs

        sectors, members, capture_audit = capture_inputs(con, capture_id, category)
    else:
        sectors = con.execute(
            "SELECT sector_ts_code, sector_name, updated_at, constituent_count, "
            "constituents_captured_at, source FROM dim_sector_hithink "
            "WHERE category=? ORDER BY sector_ts_code", [category],
        ).fetchall()
        members = con.execute(
            "SELECT sector_ts_code, stock_ts_code, source, updated_at "
            "FROM fact_sector_constituent_hithink "
            "WHERE captured_at=? AND in_index=1 ORDER BY sector_ts_code, stock_ts_code", [md],
        ).fetchall()
    by_sector: dict[str, list[tuple]] = {}
    for code, stock, source, updated in members:
        by_sector.setdefault(code, []).append((stock, source, updated))
    daily = con.execute(
        "SELECT trade_date, stock_ts_code, close, pct_chg, amount, source "
        "FROM fact_stock_daily WHERE trade_date IN (?, ?) ORDER BY 1, 2", [prev, td],
    ).fetchall()
    values: dict[tuple, tuple] = {}
    duplicates: set[tuple] = set()
    for day, code, close, pct, amount, source in daily:
        key = (_date(day), code)
        if key in values:
            duplicates.add(key)
        values[key] = (close, pct, amount, source)

    gaps, rows, identities = [], [], []
    value_sources: set[str] = set()
    if not sectors:
        gaps.append({"sector_ts_code": None, "reason": "empty-catalog"})
    duplicate_sectors = {code for code, n in Counter(row[0] for row in sectors).items() if n > 1}
    for code, name, updated, expected_count, declared_capture, catalog_source in sectors:
        stocks = by_sector.get(code, [])
        identities.append((code, name, sorted(str(stock[0]) for stock in stocks)))
        reasons: list[str] = []
        if (catalog_source != SOURCE_CATALOG or updated is None
                or not 0 <= (td - _date(updated)).days <= max_member_age_days):
            reasons.append("catalog-provenance-or-date")
        if not code or code in duplicate_sectors:
            reasons.append("catalog-identity")
        if not stocks:
            reasons.append("missing-members")
        if (expected_count is None or expected_count != len(stocks)
                or declared_capture is None or _date(declared_capture) != md):
            reasons.append("member-snapshot-count-or-date")
        if len({stock[0] for stock in stocks}) != len(stocks):
            reasons.append("duplicate-members")
        if pct_basis == "index_close_return" and code not in index_returns:
            reasons.append("missing-or-invalid-index-bars")
        amounts, prev_amounts, pcts = [], [], []
        for stock, source, captured in stocks:
            # 旧同步器曾把 end-date 写成 captured_at。必须同时验证实际行写入日，
            # 不因为一个被回标的日期就在历史预览里使用未来名单。
            if (not stock or source != SOURCE_CONSTITUENT or captured is None
                    or _date(captured) != md or captured != declared_capture):
                reasons.append(f"{stock}:member-provenance")
            current, prior = values.get((td, stock)), values.get((prev, stock))
            if ((td, stock) in duplicates or (prev, stock) in duplicates
                    or current is None or prior is None):
                reasons.append(f"{stock}:missing-or-duplicate-bars")
                continue
            close, pct, amount, current_source = current
            prev_close, _, prev_amount, previous_source = prior
            if not (_independent_source(current_source) and _independent_source(previous_source)):
                reasons.append(f"{stock}:value-source")
                continue
            if not (_finite(close, positive=True) and _finite(prev_close, positive=True)
                    and (pct_basis != "member_equal_weight" or _finite(pct))
                    and _finite(amount, nonnegative=True) and _finite(prev_amount, nonnegative=True)):
                reasons.append(f"{stock}:invalid-values")
                continue
            amounts.append(amount)
            prev_amounts.append(prev_amount)
            pcts.append(pct)
            value_sources.update((current_source, previous_source))
        amount, previous_amount = sum(amounts), sum(prev_amounts)
        if not math.isfinite(amount) or not math.isfinite(previous_amount) or previous_amount <= 0:
            reasons.append("invalid-previous-denominator-or-total")
        if reasons:
            gaps.append({"sector_ts_code": code, "reasons": sorted(set(reasons))})
            continue
        pct = (index_returns[code] if pct_basis == "index_close_return"
               else round(sum(pcts) / len(pcts), 4))
        dr = diff_ratio(amount, previous_amount)
        if not _finite(pct) or not _finite(dr):
            gaps.append({"sector_ts_code": code, "reason": "nonfinite-calculation"})
            continue
        amount = round(amount, 4)
        rows.append({
            "sector_ts_code": code, "sector_name": name, "member_count": len(stocks),
            "pct_chg": pct, "amount": amount, "previous_amount": round(previous_amount, 4),
            "diff_ratio": dr, "double_red": is_double_red(pct, dr, amount),
        })
    fingerprint = hashlib.sha256(json.dumps(
        {"member_date": str(md), "category": category, "members": identities},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    ready = bool(rows) and not gaps
    return {
        "trade_date": str(td), "previous_trade_date": str(prev),
        "member_date": str(md), "member_age_days": age, "member_fingerprint": fingerprint,
        "category": category, "sector_count": len(sectors), "rows": rows, "gaps": gaps,
        "calculation_ready": ready, "production_ready": False,
        "capture_id": capture_id, "capture_audit": capture_audit,
        "request_complete": capture_audit["request_complete"] if capture_audit else None,
        "provider_completeness": "unverified",
        "double_red_codes": [row["sector_ts_code"] for row in rows if row["double_red"]] if ready else [],
        "value_sources": sorted(value_sources),
        "basis": {
            "amount_unit": "亿元", "pct_unit": "%", "pct_chg": pct_basis,
            "pct_source": SOURCE_KLINE if pct_basis == "index_close_return" else "canonical_fact_stock_daily",
            "previous_amount": "same_selected_members", "values": "canonical_fact_stock_daily",
            "max_member_age_days": max_member_age_days,
            "members": "capture_version" if capture_id is not None else "latest_daily_legacy",
        },
    }
