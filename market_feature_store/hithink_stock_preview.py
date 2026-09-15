"""同花顺个股双日行情的只读标准化预演，不是 canonical 写者或发布许可。

只读显式股票范围的两个计划交易日及目标日除权事件；一条 SQL 取得一致读取快照。
价格保持未复权；普通日用前一计划日裸收，纯现金除息调整参考前收后算涨幅。
缺前日/零成交/送转配股不猜值；没有事件行仅是「未记录事件」，不是证实没有事件。
不借 canonical 的姓名、换手率、前收或停牌处置。无外呼、无 DDL、无 DML。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, InvalidOperation, Overflow,
    ROUND_HALF_UP, localcontext,
)
import hashlib
import json
import math
import re

from .trading_days import closed_dates, previous_scheduled_trading_day

CONTRACT_VERSION = "hithink-stock-preview-v1"
_BAR_SOURCES = frozenset({"hithink:daily-k", "hithink:daily-k-10d"})
_ADJUSTMENT_SOURCE = "hithink:adjustment-factors"
# 只验证 A 股代码形状/市场配对，不冒充上市名册或当天可交易状态证明。
_CODE = re.compile(r"(?:6[08][0-9]{4}\.SH|(?:00|30)[0-9]{4}\.SZ|(?:[48][0-9]{5}|92[0-9]{4})\.BJ)")
_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)
_YI = Decimal(100_000_000)

_INPUT_SQL = """
SELECT 'bar' AS kind, stock_ts_code, trade_date AS observation_date,
       open, high, low, close, volume, turnover, adjusted, source, updated_at
FROM fact_stock_daily_hithink
WHERE trade_date IN (?, ?) AND stock_ts_code IN (SELECT unnest(?::VARCHAR[]))
UNION ALL BY NAME
SELECT 'adjustment' AS kind, stock_ts_code, ex_date AS observation_date,
       dividend_per_share, per_share_bonus, allotment_ratio, allotment_price,
       currency, source, updated_at
FROM fact_stock_adjustment_hithink
WHERE ex_date = ? AND stock_ts_code IN (SELECT unnest(?::VARCHAR[]))
"""


def _scope(trade_date, stock_codes) -> tuple[date, date, list[str]]:
    if isinstance(trade_date, datetime):
        raise ValueError("trade_date must be a date without time")
    if isinstance(trade_date, date):
        td = trade_date
    elif isinstance(trade_date, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", trade_date):
        td = date.fromisoformat(trade_date)
    else:
        raise ValueError("trade_date must be ISO YYYY-MM-DD")
    closures = closed_dates(td.year)
    prev = previous_scheduled_trading_day(td)
    if closures is None or td.weekday() >= 5 or td in closures or prev is None:
        raise ValueError("target and previous scheduled trading days must be known")
    if (not isinstance(stock_codes, Sequence) or isinstance(stock_codes, (str, bytes))
            or not stock_codes):
        raise ValueError("stock_codes must be an explicit nonempty sequence")
    if any(not isinstance(code, str) or not _CODE.fullmatch(code) for code in stock_codes):
        raise ValueError("stock_codes must use A-share identities with matching exchange suffix")
    if len(set(stock_codes)) != len(stock_codes):
        raise ValueError("stock_codes must be unique")
    return td, prev, sorted(stock_codes)


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _read_inputs(con, td, prev, codes):
    cursor = con.execute(_INPUT_SQL, [prev, td, codes, td, codes])
    columns = [item[0] for item in cursor.description]
    rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    # 白名单列的字符串表示包含 NULL/非有限值；损坏数字也能留指纹，但不进入输出值。
    # 排序保留重复行，不以集合去重掩盖重复身份。不是供应商签名或历史版本存储。
    fingerprint_rows = sorted(json.dumps(
        [None if row[col] is None else str(row[col]) for col in columns],
        ensure_ascii=False, separators=(",", ":"),
    ) for row in rows)
    fingerprint = _hash({
        "contract_version": CONTRACT_VERSION, "trade_date": str(td),
        "previous_trade_date": str(prev), "stock_codes": codes,
        "columns": columns, "rows": fingerprint_rows,
    })
    by_key: dict[tuple, list[dict]] = {}
    for row in rows:
        key = row["kind"], row["observation_date"], row["stock_ts_code"]
        by_key.setdefault(key, []).append(row)
    return by_key, fingerprint


def _number(value) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    number = Decimal(str(value))
    return number if number.is_finite() else None


def _bar_gaps(row: dict, label: str) -> list[str]:
    reasons = []
    if (row["source"] not in _BAR_SOURCES or row["adjusted"] != "none"
            or not isinstance(row["updated_at"], datetime)):
        reasons.append("bar-provenance")
    prices = [_number(row[col]) for col in ("open", "high", "low", "close")]
    if any(value is None or value <= 0 for value in prices):
        reasons.append("invalid-price")
    else:
        if any(value.quantize(_CENT, rounding=ROUND_HALF_UP) != value for value in prices):
            reasons.append("invalid-price-tick")
        op, high, low, close = prices
        if not low <= min(op, close) <= max(op, close) <= high:
            reasons.append("invalid-ohlc")
    vol, amount = _number(row["volume"]), _number(row["turnover"])
    if (vol is None or amount is None or vol < 0 or amount < 0
            or vol != vol.to_integral_value()):
        reasons.append("invalid-volume-or-amount")
    elif vol == 0 or amount == 0:
        # 没有独立停牌/交易状态：不能凭零成交合成一根「正常的平盘 K 线」。
        reasons.append("nontrading-or-zero-volume-amount")
    return [f"{label}:{reason}" for reason in reasons]


def _reference(previous: dict, action: dict | None):
    raw_close = _number(previous["close"])
    if action is None:
        return raw_close, "previous_scheduled_close_no_recorded_event", []
    if (action["source"] != _ADJUSTMENT_SOURCE or action["currency"] != "CNY"
            or not isinstance(action["updated_at"], datetime)):
        return None, None, ["adjustment-provenance"]
    values = [_number(action[col]) for col in (
        "dividend_per_share", "per_share_bonus", "allotment_ratio", "allotment_price",
    )]
    if any(value is None or value < 0 for value in values):
        return None, None, ["invalid-adjustment-values"]
    cash, bonus, ratio, price = values
    if bonus != 0 or ratio != 0 or price != 0:
        return None, None, ["unsupported-noncash-action"]
    reference = (raw_close - cash).quantize(_CENT, rounding=ROUND_HALF_UP)
    if reference <= 0:
        return None, None, ["invalid-reference-price"]
    return reference, "cash_dividend_reference", []


def _as_float(value: Decimal) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite calculation")
    return 0.0 if result == 0 else result


def _calculate(code, current, previous, action):
    # 不继承进程 context 或可变的 DefaultContext（包括指数范围与 traps）。
    context = Context(
        prec=50, rounding=ROUND_HALF_UP, Emin=-999999, Emax=999999,
        capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    with localcontext(context):
        # 输入来自 DOUBLE 的十进制文本，不声称还原供应商原始无限精度。
        gaps = _bar_gaps(current, "current") + _bar_gaps(previous, "previous")
        if gaps:
            return None, gaps
        reference, basis, gaps = _reference(previous, action)
        if gaps:
            return None, gaps
        close = _number(current["close"])
        pct = ((close - reference) * _HUNDRED / reference).quantize(_CENT)
        amount = (_number(current["turnover"]) / _YI).quantize(Decimal("0.0001"))
        volume = (_number(current["volume"]) / _HUNDRED).quantize(Decimal(1))
        # 换算后0手/0亿元不等于停牌；报告原单位量，避免微额舍入隐藏事实。
        return {
            "stock_ts_code": code,
            "stock_name": None, "turnover": None,
            **{col: _as_float(_number(current[col])) for col in ("open", "high", "low", "close")},
            "pre_close": _as_float(reference), "pct_chg": _as_float(pct),
            "amount": _as_float(amount), "volume": _as_float(volume),
            "raw_amount_yuan": _as_float(_number(current["turnover"])),
            "raw_volume_shares": _as_float(_number(current["volume"])),
            "reference_basis": basis, "bar_source": current["source"],
            "previous_bar_source": previous["source"],
            "adjustment_source": action["source"] if action else None,
        }, []


def preview_stock_calculation(con, trade_date, *, stock_codes: Sequence[str]) -> dict:
    """只读显式范围，未支持/缺值逐股报缺口，不缩分母、不回退旧 canonical。"""
    td, prev, codes = _scope(trade_date, stock_codes)
    inputs, fingerprint = _read_inputs(con, td, prev, codes)
    rows, gaps = [], []
    for code in codes:
        current = inputs.get(("bar", td, code), [])
        previous = inputs.get(("bar", prev, code), [])
        actions = inputs.get(("adjustment", td, code), [])
        # row 每股重置：_calculate 抛异常时不得残留上一只股票的行。
        row, reasons = None, []
        for label, bars in (("current", current), ("previous", previous)):
            if len(bars) != 1:
                reasons.append(f"{'missing' if not bars else 'duplicate'}-{label}-bar")
        if len(actions) > 1:
            reasons.append("duplicate-adjustment")
        if not reasons:
            try:
                row, reasons = _calculate(code, current[0], previous[0], actions[0] if actions else None)
            except (DecimalException, ValueError, OverflowError):
                reasons = ["invalid-numeric-result"]
            if not reasons:
                rows.append(row)
        if reasons:
            gaps.append({"stock_ts_code": code, "reasons": sorted(set(reasons))})
    return {
        "contract_version": CONTRACT_VERSION,
        "trade_date": str(td), "previous_trade_date": str(prev),
        "stock_codes": codes, "requested_stock_count": len(codes),
        "calculated_stock_count": len(rows), "rows": rows, "gaps": gaps,
        "calculation_ready": bool(rows) and not gaps, "production_ready": False,
        "request_complete": None, "provider_completeness": "unverified",
        "adjustment_coverage": "unverified",
        "scope_fingerprint": _hash({"trade_date": str(td), "stock_codes": codes}),
        "input_fingerprint": fingerprint,
        "basis": {
            "values": "fact_stock_daily_hithink",
            "actions": "fact_stock_adjustment_hithink", "price_adjustment": "none",
            "pre_close": "previous_scheduled_close_or_cash_dividend_reference",
            "pct_chg": "(close-reference_price)*100/reference_price",
            "price_unit": "元", "amount_unit": "亿元", "volume_unit": "手", "pct_unit": "%",
            "rounding": "decimal_from_double_text_half_up",
            "pre_close_decimals": 2, "pct_decimals": 2, "amount_decimals": 4, "volume_decimals": 0,
            "window": "two_adjacent_scheduled_trading_days",
            "scope": "explicit_stock_codes_not_market_universe",
            "missing_event": "no_recorded_event_not_verified_absence",
            "unsupported": ["noncash_actions", "missing_previous_bar", "zero_volume_or_amount"],
            "unavailable_fields": ["stock_name", "turnover"],
        },
    }
