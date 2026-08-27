"""D12 资金面三件套：两融 / 大宗 / 未来 90 天解禁时间表。

库内无两融/大宗/解禁表，取数走东财 datacenter（与 a-stock-data 同源）。
意图词命中对应切片才取数；解析不到个股不输出块。只列事实，不构成买卖建议。
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache

DEFAULT_MARKET_DB_PATH = default_market_db_path()
DEFAULT_MARGIN_DAYS = 5
DEFAULT_BLOCK_ROWS = 5
UNLOCK_FORWARD_DAYS = 90
_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

_SLICE_TERMS: dict[str, tuple[str, ...]] = {
    "margin": ("两融", "融资盘", "融资融券", "融资余额", "融券"),
    "block": ("大宗",),
    "unlock": ("解禁", "限售解禁"),
}


@dataclass(frozen=True)
class MarginRow:
    trade_date: str
    financing_yi: float | None
    financing_buy_yi: float | None
    short_yi: float | None


@dataclass(frozen=True)
class BlockTradeRow:
    trade_date: str
    price: float | None
    premium_pct: float | None
    amount_wan: float | None
    buyer: str
    seller: str


@dataclass(frozen=True)
class UnlockRow:
    free_date: str
    share_type: str
    shares_wan: float | None
    ratio_pct: float | None


def parse_capital_slices(query: str) -> frozenset[str]:
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return frozenset()
    return frozenset(
        name for name, terms in _SLICE_TERMS.items() if any(term in text for term in terms)
    )


def parse_capital_intent(query: str) -> bool:
    return bool(parse_capital_slices(query))


def _num(value: Any, scale: float = 1.0) -> float | None:
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("%", "").strip()
        if not cleaned or cleaned in {"--", "-", "None"}:
            return None
        try:
            value = float(cleaned)
        except ValueError:
            return None
    if not isinstance(value, (int, float)) or value != value:
        return None
    return round(float(value) / scale, 2)


def _date_text(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")[:10]


def _fmt(value: float | None) -> str:
    if value is None:
        return "缺"
    return f"{value}"


def resolve_capital_stock(con: Any, query: str) -> tuple[str, str] | None:
    code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
    if code_match:
        raw = code_match.group(1)
        suffix = code_match.group(2)
        if suffix:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code=? limit 1",
                [f"{raw}.{suffix.upper()}"],
            ).fetchall()
        else:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code like ? limit 1",
                [f"{raw}.%"],
            ).fetchall()
        if rows:
            return str(rows[0][0]), str(rows[0][1] or rows[0][0])
    rows = con.execute(
        """
        select stock_ts_code, stock_name
        from fact_stock_daily
        where stock_name is not null and stock_name <> ''
        group by stock_ts_code, stock_name
        """
    ).fetchall()
    q = str(query or "")
    matches = [(str(code), str(name)) for code, name in rows if str(name) and str(name) in q]
    if matches:
        matches.sort(key=lambda item: len(item[1]), reverse=True)
        return matches[0]
    return None


def _eastmoney_rows(
    report_name: str,
    filter_str: str,
    sort_columns: str,
    sort_types: str,
    page_size: int,
    timeout: float,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "reportName": report_name,
            "columns": "ALL",
            "filter": filter_str,
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "WEB",
            "client": "WEB",
        }
    )
    url = f"{_DATACENTER_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    rows = ((payload.get("result") or {}).get("data")) or []
    return rows if isinstance(rows, list) else []


def fetch_margin_rows(
    code: str, limit: int = DEFAULT_MARGIN_DAYS, timeout: float = 8.0
) -> list[MarginRow]:
    rows = _eastmoney_rows(
        "RPTA_WEB_RZRQ_GGMX",
        f'(SCODE="{code}")',
        "DATE",
        "-1",
        limit,
        timeout,
    )
    out: list[MarginRow] = []
    for row in rows:
        out.append(
            MarginRow(
                trade_date=_date_text(row.get("DATE")),
                financing_yi=_num(row.get("RZYE"), 1e8),
                financing_buy_yi=_num(row.get("RZMRE"), 1e8),
                short_yi=_num(row.get("RQYE"), 1e8),
            )
        )
    return out


def fetch_block_rows(
    code: str, limit: int = DEFAULT_BLOCK_ROWS, timeout: float = 8.0
) -> list[BlockTradeRow]:
    rows = _eastmoney_rows(
        "RPT_DATA_BLOCKTRADE",
        f'(SECURITY_CODE="{code}")',
        "TRADE_DATE",
        "-1",
        limit,
        timeout,
    )
    out: list[BlockTradeRow] = []
    for row in rows:
        close = row.get("CLOSE_PRICE")
        price = row.get("DEAL_PRICE")
        premium = None
        if isinstance(close, (int, float)) and close and isinstance(price, (int, float)):
            premium = round((float(price) / float(close) - 1) * 100, 2)
        out.append(
            BlockTradeRow(
                trade_date=_date_text(row.get("TRADE_DATE")),
                price=_num(price),
                premium_pct=premium,
                amount_wan=_num(row.get("DEAL_AMT"), 1e4),
                buyer=str(row.get("BUYER_NAME") or "缺"),
                seller=str(row.get("SELLER_NAME") or "缺"),
            )
        )
    return out


def fetch_unlock_rows(
    code: str,
    as_of: str,
    forward_days: int = UNLOCK_FORWARD_DAYS,
    timeout: float = 8.0,
) -> list[UnlockRow]:
    start = date.fromisoformat(as_of)
    end = start + timedelta(days=int(forward_days))
    rows = _eastmoney_rows(
        "RPT_LIFT_STAGE",
        f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{start.isoformat()}')(FREE_DATE<='{end.isoformat()}')",
        "FREE_DATE",
        "1",
        20,
        timeout,
    )
    out: list[UnlockRow] = []
    for row in rows:
        ratio = _num(row.get("FREE_RATIO"))
        out.append(
            UnlockRow(
                free_date=_date_text(row.get("FREE_DATE")),
                share_type=str(row.get("FREE_SHARES_TYPE") or "缺类型"),
                shares_wan=_num(row.get("CURRENT_FREE_SHARES")),
                ratio_pct=None if ratio is None else round(ratio * 100, 2) if ratio <= 1 else ratio,
            )
        )
    return out


def _render_margin(rows: list[MarginRow]) -> list[str]:
    lines = ["- ### 两融（东财 RPTA_WEB_RZRQ_GGMX，金额=亿元）"]
    if not rows:
        lines.append("- ⚠缺两融：东财未取到该股融资融券明细，按缺口处理，不得编造。")
        return lines
    lines.append("- | 日期 | 融资余额(亿) | 融资买入(亿) | 融券余额(亿) |")
    lines.append("- |---|---|---|---|")
    for row in rows:
        lines.append(
            f"- | {row.trade_date} | {_fmt(row.financing_yi)} | "
            f"{_fmt(row.financing_buy_yi)} | {_fmt(row.short_yi)} |"
        )
    return lines


def _render_block(rows: list[BlockTradeRow]) -> list[str]:
    lines = ["- ### 大宗交易（东财 RPT_DATA_BLOCKTRADE，成交额=万元）"]
    if not rows:
        lines.append("- ⚠缺大宗：东财未取到该股大宗记录，按缺口处理，不得编造。")
        return lines
    lines.append("- | 日期 | 成交价 | 溢价% | 成交额(万) | 买方 | 卖方 |")
    lines.append("- |---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"- | {row.trade_date} | {_fmt(row.price)} | {_fmt(row.premium_pct)} | "
            f"{_fmt(row.amount_wan)} | {row.buyer} | {row.seller} |"
        )
    return lines


def _render_unlock(rows: list[UnlockRow], as_of: str) -> list[str]:
    lines = [
        f"- ### 解禁时间表（东财 RPT_LIFT_STAGE，自 {as_of} 起未来 {UNLOCK_FORWARD_DAYS} 天）"
    ]
    if not rows:
        lines.append(f"- 未来 {UNLOCK_FORWARD_DAYS} 天无待解禁。")
        return lines
    lines.append("- | 解禁日 | 类型 | 解禁量(万股) | 占比% |")
    lines.append("- |---|---|---|---|")
    for row in rows:
        lines.append(
            f"- | {row.free_date} | {row.share_type} | {_fmt(row.shares_wan)} | {_fmt(row.ratio_pct)} |"
        )
    return lines


def build_capital_block(
    target_name: str,
    ts_code: str,
    as_of: str,
    *,
    margin_rows: list[MarginRow] | None = None,
    block_rows: list[BlockTradeRow] | None = None,
    unlock_rows: list[UnlockRow] | None = None,
) -> str:
    lines = [f"## 资金面三件套 [D12]（{target_name} {ts_code}）"]
    lines.append(
        "- 口径：东财 datacenter 免费接口（两融 RPTA_WEB_RZRQ_GGMX / 大宗 RPT_DATA_BLOCKTRADE / "
        f"解禁 RPT_LIFT_STAGE）；解禁只列 {as_of} 起未来 {UNLOCK_FORWARD_DAYS} 天时间表，"
        "是待验证变量+时点，不是涨跌预测。只列事实，不构成买卖建议。"
    )
    if margin_rows is not None:
        lines.extend(_render_margin(margin_rows))
    if block_rows is not None:
        lines.extend(_render_block(block_rows))
    if unlock_rows is not None:
        lines.extend(_render_unlock(unlock_rows, as_of))
    return "\n".join(lines)


def capital_block_for_llm(
    query: str,
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    timeout: float = 8.0,
    margin_fetcher: Callable[..., list[MarginRow]] | None = None,
    block_fetcher: Callable[..., list[BlockTradeRow]] | None = None,
    unlock_fetcher: Callable[..., list[UnlockRow]] | None = None,
) -> str:
    slices = parse_capital_slices(query)
    if not slices:
        return ""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        stock = resolve_capital_stock(con, query)
        if stock is None:
            return ""
        ts_code, name = stock
        code = ts_code.split(".")[0]
        as_of_date = as_of or date.today().isoformat()
        margin_rows = None
        block_rows = None
        unlock_rows = None
        if "margin" in slices:
            fetch = margin_fetcher or fetch_margin_rows
            margin_rows = fetch(code, DEFAULT_MARGIN_DAYS, timeout)
        if "block" in slices:
            fetch_b = block_fetcher or fetch_block_rows
            block_rows = fetch_b(code, DEFAULT_BLOCK_ROWS, timeout)
        if "unlock" in slices:
            fetch_u = unlock_fetcher or fetch_unlock_rows
            unlock_rows = fetch_u(code, as_of_date, UNLOCK_FORWARD_DAYS, timeout)
        return build_capital_block(
            name,
            ts_code,
            as_of_date,
            margin_rows=margin_rows,
            block_rows=block_rows,
            unlock_rows=unlock_rows,
        )
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass
