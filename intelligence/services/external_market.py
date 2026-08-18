from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from intelligence.services.provider_observability import ProviderTrace

FUPANHUI_PROVIDER = "fupanhui_global_market"
YAHOO_PROVIDER = "yahoo_finance_chart"
BING_NEWS_PROVIDER = "bing_news"

_SYMBOLS: Mapping[str, tuple[str, str]] = {
    "DJI": ("^DJI", "道琼斯"),
    "SPX": ("^GSPC", "标普500"),
    "IXIC": ("^IXIC", "纳斯达克"),
    "SOX": ("^SOX", "费城半导体"),
    "SOXX": ("SOXX", "SOXX"),
    "QQQ": ("QQQ", "QQQ"),
    "NVDA": ("NVDA", "英伟达"),
    "MU": ("MU", "美光"),
    "HYNIX": ("000660.KS", "SK海力士"),
    "SNDK": ("SNDK", "闪迪"),
}
_OVERNIGHT_LEADER_CODES: tuple[str, ...] = ("SOX", "NVDA", "MU", "HYNIX", "SNDK")
_QUERY_SYMBOL_TERMS: Mapping[str, tuple[str, ...]] = {
    "DJI": ("道指", "道琼斯", "dow"),
    "SPX": ("标普500", "标普", "s&p", "sp500"),
    "IXIC": ("纳指", "纳斯达克", "nasdaq"),
    "SOX": ("费半", "费城半导体"),
    "SOXX": ("soxx",),
    "QQQ": ("qqq",),
}
_DATE_PATTERN = re.compile(r"\b(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?\b")


@dataclass(frozen=True)
class ExternalMarketQuote:
    code: str
    name: str
    close: float
    pct_chg: float
    trade_date: str
    source: str


@dataclass(frozen=True)
class ExternalMarketResult:
    target_trade_date: str
    source_trade_date: str | None
    selected_provider: str | None
    quotes: tuple[ExternalMarketQuote, ...]
    provider_traces: tuple[ProviderTrace, ...]
    gap: str | None = None


@dataclass(frozen=True)
class _ProviderQuotes:
    quotes: tuple[ExternalMarketQuote, ...]
    source_trade_date: str | None
    trace: ProviderTrace


StructuredFetcher = Callable[[str, dict[str, str], int], object]


def overnight_leader_codes() -> tuple[str, ...]:
    """Index + current AI/storage sample for overnight-hybrid forecasts.

    Ask-side ``requested_symbols`` stays index-only. These names are the
    missing constituent layer from spec P0-B, not a new datasource.
    """

    return _OVERNIGHT_LEADER_CODES


def format_quote_line(quote: ExternalMarketQuote) -> str:
    sign = "+" if quote.pct_chg >= 0 else ""
    return (
        f"{quote.name}（{quote.code}）：收盘 {quote.close:,.2f}，"
        f"涨跌幅 {sign}{quote.pct_chg:.2f}%（{quote.trade_date}）；"
        f"来源 {quote.source}。新闻标题不作为精确涨跌。"
    )


def requested_symbols(query: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", "", str(query or "")).casefold()
    explicit = tuple(
        code
        for code, terms in _QUERY_SYMBOL_TERMS.items()
        if any(term in normalized for term in terms)
    )
    return explicit or ("DJI", "SPX", "IXIC")


def target_trade_date(
    query: str,
    *,
    now: datetime | None = None,
) -> date:
    match = _DATE_PATTERN.search(str(query or ""))
    if match:
        return date(*(int(part) for part in match.groups()))
    eastern_now = now or datetime.now(ZoneInfo("America/New_York"))
    if eastern_now.tzinfo is None:
        eastern_now = eastern_now.replace(tzinfo=ZoneInfo("America/New_York"))
    text = re.sub(r"\s+", "", str(query or ""))
    if any(term in text for term in ("昨天", "昨日")):
        candidate = eastern_now.date() - timedelta(days=1)
    elif eastern_now.time() >= time(16, 15):
        candidate = eastern_now.date()
    else:
        candidate = eastern_now.date() - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def fetch_fupanhui_global_market(
    query: str,
    *,
    timeout: int = 60,
    fetcher: StructuredFetcher | None = None,
    today: date | None = None,
) -> _ProviderQuotes:
    if fetcher is None:
        from market_feature_store.sources.fupanhui_source import api_get

        fetcher = api_get
    request_date = (today or date.today()).isoformat()
    try:
        payload = fetcher(
            "/api/v1/client/reviews/global-market",
            {"trade_date": request_date},
            timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return _ProviderQuotes(
            (),
            None,
            ProviderTrace(
                provider=FUPANHUI_PROVIDER,
                capability="structured_market_quotes",
                status="request_error",
                detail=type(exc).__name__,
            ),
        )
    if not isinstance(payload, dict):
        return _ProviderQuotes(
            (),
            None,
            ProviderTrace(
                provider=FUPANHUI_PROVIDER,
                capability="structured_market_quotes",
                status="parse_error",
                detail="response_not_object",
            ),
        )
    source_date = str(
        payload.get("source_trade_date") or payload.get("trade_date") or ""
    ).strip()
    raw_markets = payload.get("markets")
    if not isinstance(raw_markets, list):
        return _ProviderQuotes(
            (),
            source_date or None,
            ProviderTrace(
                provider=FUPANHUI_PROVIDER,
                capability="structured_market_quotes",
                status="parse_error",
                detail="markets_not_list",
                source_trade_date=source_date or None,
            ),
        )
    wanted = set(requested_symbols(query))
    quotes: list[ExternalMarketQuote] = []
    for raw in raw_markets:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or "").strip().upper()
        if code not in wanted:
            continue
        try:
            close = float(raw["close"])
            pct_chg = float(raw["pct_chg"])
        except (KeyError, TypeError, ValueError):
            continue
        name = str(raw.get("name") or _SYMBOLS.get(code, ("", code))[1]).strip()
        quotes.append(
            ExternalMarketQuote(
                code=code,
                name=name,
                close=close,
                pct_chg=pct_chg,
                trade_date=source_date,
                source=FUPANHUI_PROVIDER,
            )
        )
    status = "success" if quotes else "empty"
    return _ProviderQuotes(
        tuple(quotes),
        source_date or None,
        ProviderTrace(
            provider=FUPANHUI_PROVIDER,
            capability="structured_market_quotes",
            status=status,
            detail="structured global-market response",
            source_trade_date=source_date or None,
            result_count=len(quotes),
        ),
    )


def _fetch_yahoo_symbol(
    code: str,
    target: date,
    *,
    timeout: int,
) -> ExternalMarketQuote | None:
    symbol, name = _SYMBOLS[code]
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol, safe='')}"
        "?range=10d&interval=1d&events=div%2Csplits"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    chart = payload["chart"]["result"][0]
    timestamps = chart["timestamp"]
    closes = chart["indicators"]["quote"][0]["close"]
    sessions: list[tuple[date, float]] = []
    for timestamp, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        session_date = datetime.fromtimestamp(
            int(timestamp),
            ZoneInfo("America/New_York"),
        ).date()
        if session_date <= target:
            sessions.append((session_date, float(close)))
    if len(sessions) < 2:
        return None
    current_date, current_close = sessions[-1]
    _, previous_close = sessions[-2]
    if previous_close == 0:
        return None
    return ExternalMarketQuote(
        code=code,
        name=name,
        close=current_close,
        pct_chg=(current_close / previous_close - 1) * 100,
        trade_date=current_date.isoformat(),
        source=YAHOO_PROVIDER,
    )


def fetch_yahoo_finance_quotes(
    query: str,
    target: date,
    *,
    timeout: int = 15,
    symbols: Sequence[str] | None = None,
) -> _ProviderQuotes:
    wanted = tuple(symbols or requested_symbols(query))
    quotes: list[ExternalMarketQuote] = []
    request_errors = 0
    parse_errors = 0
    for code in wanted:
        try:
            quote = _fetch_yahoo_symbol(code, target, timeout=timeout)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            parse_errors += 1
            continue
        except Exception:  # noqa: BLE001
            request_errors += 1
            continue
        if quote is not None:
            quotes.append(quote)
    source_date = max((quote.trade_date for quote in quotes), default=None)
    if quotes:
        status = "success"
        detail = "finance chart quotes"
    elif request_errors:
        status = "request_error"
        detail = f"request_errors={request_errors}"
    elif parse_errors:
        status = "parse_error"
        detail = f"parse_errors={parse_errors}"
    else:
        status = "empty"
        detail = "no completed sessions for target date"
    return _ProviderQuotes(
        tuple(quotes),
        source_date,
        ProviderTrace(
            provider=YAHOO_PROVIDER,
            capability="finance_market_quotes",
            status=status,
            detail=detail,
            source_trade_date=source_date,
            result_count=len(quotes),
        ),
    )


def resolve_overnight_leaders(
    query: str,
    *,
    now: datetime | None = None,
    timeout: float = 15,
) -> ExternalMarketResult:
    """Yahoo-only leader tape. Fupanhui global-market has indices, not NVDA/MU."""

    target = target_trade_date(query, now=now)
    wanted = overnight_leader_codes()
    finance = fetch_yahoo_finance_quotes(
        query,
        target,
        symbols=wanted,
        timeout=max(1, int(timeout)),
    )
    target_key = target.isoformat()
    fresh = tuple(
        quote for quote in finance.quotes if quote.trade_date == target_key
    )
    stale = tuple(
        quote for quote in finance.quotes if quote.trade_date != target_key
    )
    quotes = tuple(
        sorted(fresh, key=lambda quote: wanted.index(quote.code))
    )
    missing = tuple(code for code in wanted if code not in {quote.code for quote in quotes})
    gap_parts: list[str] = []
    if not quotes:
        gap_parts.append(
            f"未取得 {target_key} 的美股龙头结构化报价；"
            "新闻标题不会被当作精确涨跌数据。"
        )
    elif missing:
        missing_names = "、".join(_SYMBOLS[code][1] for code in missing)
        gap_parts.append(
            f"已取得部分美股龙头行情，但仍缺少：{missing_names}；"
            "不会用新闻标题补齐精确点位。"
        )
    if stale:
        stale_names = "、".join(
            f"{quote.name}({quote.trade_date or '日期未记录'})" for quote in stale
        )
        gap_parts.append(f"滞后交易日未计入绑定数字：{stale_names}")
    gap = "；".join(gap_parts) or None
    return ExternalMarketResult(
        target_trade_date=target.isoformat(),
        source_trade_date=finance.source_trade_date,
        selected_provider=YAHOO_PROVIDER if quotes else None,
        quotes=quotes,
        provider_traces=(finance.trace,),
        gap=gap,
    )


def resolve_external_market(
    query: str,
    *,
    structured_fetcher: StructuredFetcher | None = None,
    now: datetime | None = None,
    timeout: float = 60,
) -> ExternalMarketResult:
    target = target_trade_date(query, now=now)
    structured = fetch_fupanhui_global_market(
        query,
        fetcher=structured_fetcher,
        today=target + timedelta(days=1),
        timeout=timeout,
    )
    traces: list[ProviderTrace] = []
    wanted = requested_symbols(query)
    structured_codes = {quote.code for quote in structured.quotes}
    missing_codes = tuple(code for code in wanted if code not in structured_codes)
    source_date_mismatch = bool(
        structured.quotes
        and structured.source_trade_date != target.isoformat()
    )
    if source_date_mismatch:
        traces.append(
            replace(
                structured.trace,
                status="stale",
                detail=(
                    f"source_trade_date={structured.source_trade_date}; "
                    f"target_trade_date={target.isoformat()}"
                ),
            )
        )
    else:
        traces.append(structured.trace)
    need_finance = (
        not structured.quotes or source_date_mismatch or bool(missing_codes)
    )
    finance = (
        fetch_yahoo_finance_quotes(
            query,
            target,
            symbols=(
                wanted
                if source_date_mismatch or not structured.quotes
                else missing_codes
            ),
            timeout=timeout,
        )
        if need_finance
        else _ProviderQuotes(
            (),
            None,
            ProviderTrace(
                provider=YAHOO_PROVIDER,
                capability="finance_market_quotes",
                status="not_attempted",
                detail="structured provider covered requested date and symbols",
            ),
        )
    )
    selected = list(structured.quotes)
    if need_finance and finance.quotes:
        finance_by_code = {quote.code: quote for quote in finance.quotes}
        selected = [
            finance_by_code.get(quote.code, quote)
            if source_date_mismatch
            else quote
            for quote in selected
        ]
        selected_codes = {quote.code for quote in selected}
        selected.extend(
            quote for quote in finance.quotes if quote.code not in selected_codes
        )
        traces.append(replace(finance.trace, status="fallback_success"))
    elif need_finance:
        traces.append(replace(finance.trace, status="fallback_failed"))
    else:
        traces.append(finance.trace)
    traces.append(
        ProviderTrace(
            provider=BING_NEWS_PROVIDER,
            capability="directional_news",
            status="not_attempted",
            detail="news headlines are not used as exact quote data",
        )
    )
    selected.sort(key=lambda quote: wanted.index(quote.code))
    source_date = max((quote.trade_date for quote in selected), default=None)
    provider = None
    if selected:
        provider = (
            YAHOO_PROVIDER
            if any(quote.source == YAHOO_PROVIDER for quote in selected)
            else FUPANHUI_PROVIDER
        )
    gap = None
    final_codes = {quote.code for quote in selected}
    final_missing = tuple(code for code in wanted if code not in final_codes)
    stale_quotes = tuple(
        quote for quote in selected if quote.trade_date != target.isoformat()
    )
    if not selected:
        gap = (
            f"未取得 {target.isoformat()} 的海外指数结构化行情或 finance quote；"
            "新闻标题不会被当作精确涨跌数据。"
        )
    elif final_missing or stale_quotes:
        gaps: list[str] = []
        if final_missing:
            missing_names = "、".join(
                _SYMBOLS[code][1] for code in final_missing
            )
            gaps.append(f"仍缺少：{missing_names}")
        if stale_quotes:
            stale_names = "、".join(
                f"{quote.name}({quote.trade_date or '日期未记录'})"
                for quote in stale_quotes
            )
            gaps.append(f"仍为滞后交易日：{stale_names}")
        gap = (
            "已取得部分海外指数行情，但"
            + "；".join(gaps)
            + "；不会用新闻标题或 A 股资料补齐精确点位。"
        )
    return ExternalMarketResult(
        target_trade_date=target.isoformat(),
        source_trade_date=source_date,
        selected_provider=provider,
        quotes=tuple(selected),
        provider_traces=tuple(traces),
        gap=gap,
    )
