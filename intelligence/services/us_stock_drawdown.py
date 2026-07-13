from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ALPACA_BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
ALPACA_SOURCE = "Alpaca Market Data（IEX、复权日线）"
DEFAULT_WINDOW = 30
MAX_WINDOW = 120
_CACHE_SCHEMA_VERSION = 1
_CACHE_TTL = timedelta(minutes=15)
_MARKET_TZ = ZoneInfo("America/New_York")
_WINDOW_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\s*(?:个)?(?:美股)?交易日")

HttpTransport = Callable[[str, Mapping[str, str]], bytes]


class AlpacaMarketDataError(RuntimeError):
    pass


class MissingAlpacaCredentials(AlpacaMarketDataError):
    pass


@dataclass(frozen=True)
class WatchlistEntry:
    ticker: str
    name: str
    group: str
    enabled: bool


@dataclass(frozen=True)
class DailyBar:
    trade_date: date
    close: float


@dataclass(frozen=True)
class DrawdownStats:
    max_drawdown_pct: float
    peak_date: str
    peak_price: float
    trough_date: str
    trough_price: float
    start_date: str
    end_date: str
    trading_days: int
    status: str


@dataclass(frozen=True)
class DrawdownRow:
    rank: int | None
    ticker: str
    name: str
    group: str
    max_drawdown_pct: float | None
    peak_date: str | None
    peak_price: float | None
    trough_date: str | None
    trough_price: float | None
    start_date: str | None
    end_date: str | None
    trading_days: int
    status: str


@dataclass(frozen=True)
class DrawdownReport:
    window: int
    rows: tuple[DrawdownRow, ...]
    as_of: str | None
    start_date: str | None
    source: str
    warnings: tuple[str, ...]
    fetched_at: str | None


def parse_trading_day_window(query: str) -> int:
    match = _WINDOW_PATTERN.search(query)
    if match is None:
        return DEFAULT_WINDOW
    window = int(match.group(1))
    return window if 2 <= window <= MAX_WINDOW else DEFAULT_WINDOW


def load_watchlist(path: Path) -> tuple[str, tuple[WatchlistEntry, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("美股标的池配置必须是 JSON 对象")
    group_name = str(payload.get("name") or "美股 AI 阵营").strip()
    raw_entries = payload.get("symbols")
    if not isinstance(raw_entries, list):
        raise ValueError("美股标的池缺少 symbols 数组")
    entries: list[WatchlistEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("美股标的池条目必须是 JSON 对象")
        ticker = str(raw_entry.get("ticker") or "").strip().upper()
        name = str(raw_entry.get("name") or ticker).strip()
        subgroup = str(raw_entry.get("group") or group_name).strip()
        enabled = raw_entry.get("enabled", True)
        if not ticker or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
            raise ValueError("美股标的池包含非法 ticker")
        if not isinstance(enabled, bool):
            raise ValueError("美股标的池 enabled 必须是布尔值")
        entries.append(
            WatchlistEntry(
                ticker=ticker,
                name=name,
                group=subgroup,
                enabled=enabled,
            )
        )
    enabled_entries = tuple(entry for entry in entries if entry.enabled)
    if not enabled_entries:
        raise ValueError("美股标的池没有启用的标的")
    if len({entry.ticker for entry in enabled_entries}) != len(enabled_entries):
        raise ValueError("美股标的池包含重复 ticker")
    return group_name, enabled_entries


def calculate_max_drawdown(
    bars: Sequence[DailyBar],
    *,
    window: int,
) -> DrawdownStats | None:
    clean = sorted(
        (bar for bar in bars if bar.close > 0),
        key=lambda bar: bar.trade_date,
    )
    deduplicated = {bar.trade_date: bar for bar in clean}
    selected = sorted(deduplicated.values(), key=lambda bar: bar.trade_date)[-window:]
    if len(selected) < 2:
        return None

    peak = selected[0]
    max_drawdown = 0.0
    drawdown_peak = peak
    trough = peak
    for bar in selected:
        if bar.close > peak.close:
            peak = bar
        drawdown = bar.close / peak.close - 1
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            drawdown_peak = peak
            trough = bar

    return DrawdownStats(
        max_drawdown_pct=round(max_drawdown * 100, 2),
        peak_date=drawdown_peak.trade_date.isoformat(),
        peak_price=round(drawdown_peak.close, 2),
        trough_date=trough.trade_date.isoformat(),
        trough_price=round(trough.close, 2),
        start_date=selected[0].trade_date.isoformat(),
        end_date=selected[-1].trade_date.isoformat(),
        trading_days=len(selected),
        status="完整" if len(selected) == window else "交易日不足",
    )


def completed_market_date(now: datetime) -> date:
    market_now = now.astimezone(_MARKET_TZ)
    if market_now.time() >= time(hour=16, minute=15):
        return market_now.date()
    return market_now.date() - timedelta(days=1)


def _default_transport(url: str, headers: Mapping[str, str]) -> bytes:
    request = Request(url, headers=dict(headers))
    try:
        with urlopen(request, timeout=20) as response:
            return response.read()
    except HTTPError as exc:
        raise AlpacaMarketDataError(
            f"Alpaca 历史日线请求失败（HTTP {exc.code}）"
        ) from exc
    except URLError as exc:
        raise AlpacaMarketDataError("Alpaca 历史日线网络请求失败") from exc


class AlpacaDailyBarClient:
    def __init__(
        self,
        *,
        key_id: str | None = None,
        secret_key: str | None = None,
        transport: HttpTransport = _default_transport,
    ) -> None:
        self.key_id = (key_id or os.environ.get("ALPACA_API_KEY_ID") or "").strip()
        self.secret_key = (
            secret_key or os.environ.get("ALPACA_API_SECRET_KEY") or ""
        ).strip()
        self.transport = transport

    def fetch(
        self,
        tickers: Sequence[str],
        *,
        start: datetime,
        end: datetime,
    ) -> dict[str, tuple[DailyBar, ...]]:
        if not self.key_id or not self.secret_key:
            raise MissingAlpacaCredentials(
                "未配置 Alpaca 行情凭证，无法刷新美股日线"
            )
        result: dict[str, list[DailyBar]] = {ticker: [] for ticker in tickers}
        page_token: str | None = None
        for _page in range(5):
            params = {
                "symbols": ",".join(tickers),
                "timeframe": "1Day",
                "start": start.astimezone(timezone.utc).isoformat(),
                "end": end.astimezone(timezone.utc).isoformat(),
                "limit": "10000",
                "adjustment": "all",
                "feed": "iex",
                "sort": "asc",
            }
            if page_token:
                params["page_token"] = page_token
            payload = self.transport(
                f"{ALPACA_BARS_URL}?{urlencode(params)}",
                {
                    "Accept": "application/json",
                    "APCA-API-KEY-ID": self.key_id,
                    "APCA-API-SECRET-KEY": self.secret_key,
                },
            )
            try:
                page = json.loads(payload.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise AlpacaMarketDataError("Alpaca 日线响应无法解析") from exc
            if not isinstance(page, dict):
                raise AlpacaMarketDataError("Alpaca 日线响应格式错误")
            raw_bars = page.get("bars")
            if not isinstance(raw_bars, dict):
                raise AlpacaMarketDataError("Alpaca 日线响应缺少 bars")
            for ticker in tickers:
                ticker_bars = raw_bars.get(ticker, [])
                if not isinstance(ticker_bars, list):
                    continue
                for raw_bar in ticker_bars:
                    parsed = _parse_bar(raw_bar)
                    if parsed is not None:
                        result[ticker].append(parsed)
            raw_token = page.get("next_page_token")
            page_token = str(raw_token).strip() if raw_token else None
            if not page_token:
                break
        else:
            raise AlpacaMarketDataError("Alpaca 日线分页超过安全上限")
        return {
            ticker: tuple(
                sorted(
                    {bar.trade_date: bar for bar in bars}.values(),
                    key=lambda bar: bar.trade_date,
                )
            )
            for ticker, bars in result.items()
        }


def _parse_bar(raw_bar: object) -> DailyBar | None:
    if not isinstance(raw_bar, dict):
        return None
    timestamp = raw_bar.get("t")
    close = raw_bar.get("c")
    if not isinstance(timestamp, str) or isinstance(close, bool):
        return None
    if not isinstance(close, (int, float)) or float(close) <= 0:
        return None
    try:
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return DailyBar(
        trade_date=parsed_time.astimezone(_MARKET_TZ).date(),
        close=float(close),
    )


class DailyBarCache:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(
        self,
    ) -> tuple[dict[str, tuple[DailyBar, ...]], datetime | None]:
        if not self.path.exists():
            return {}, None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}, None
        if not isinstance(payload, dict):
            return {}, None
        fetched_at_raw = payload.get("fetched_at")
        try:
            fetched_at = (
                datetime.fromisoformat(fetched_at_raw)
                if isinstance(fetched_at_raw, str)
                else None
            )
        except ValueError:
            fetched_at = None
        raw_symbols = payload.get("symbols")
        if not isinstance(raw_symbols, dict):
            return {}, fetched_at
        symbols: dict[str, tuple[DailyBar, ...]] = {}
        for ticker, raw_bars in raw_symbols.items():
            if not isinstance(ticker, str) or not isinstance(raw_bars, list):
                continue
            parsed: list[DailyBar] = []
            for raw_bar in raw_bars:
                if not isinstance(raw_bar, dict):
                    continue
                raw_date = raw_bar.get("trade_date")
                raw_close = raw_bar.get("close")
                if (
                    not isinstance(raw_date, str)
                    or isinstance(raw_close, bool)
                    or not isinstance(raw_close, (int, float))
                ):
                    continue
                try:
                    parsed.append(
                        DailyBar(
                            trade_date=date.fromisoformat(raw_date),
                            close=float(raw_close),
                        )
                    )
                except ValueError:
                    continue
            symbols[ticker] = tuple(sorted(parsed, key=lambda bar: bar.trade_date))
        return symbols, fetched_at

    def is_fresh(self, fetched_at: datetime | None, now: datetime) -> bool:
        if fetched_at is None or fetched_at.tzinfo is None:
            return False
        age = now.astimezone(timezone.utc) - fetched_at.astimezone(timezone.utc)
        return timedelta(0) <= age <= _CACHE_TTL

    def save(
        self,
        symbols: Mapping[str, Sequence[DailyBar]],
        *,
        fetched_at: datetime,
    ) -> None:
        payload = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "source": ALPACA_SOURCE,
            "fetched_at": fetched_at.isoformat(),
            "symbols": {
                ticker: [asdict(bar) for bar in bars]
                for ticker, bars in symbols.items()
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)


class UsStockDrawdownService:
    def __init__(
        self,
        *,
        watchlist_path: Path,
        cache_path: Path,
        client: AlpacaDailyBarClient | None = None,
    ) -> None:
        self.watchlist_path = watchlist_path
        self.cache = DailyBarCache(cache_path)
        self.client = client or AlpacaDailyBarClient()

    def run(
        self,
        *,
        window: int = DEFAULT_WINDOW,
        now: datetime | None = None,
    ) -> DrawdownReport:
        if not 2 <= window <= MAX_WINDOW:
            raise ValueError(f"交易日窗口必须在 2-{MAX_WINDOW} 之间")
        current_time = now or datetime.now(timezone.utc)
        _watchlist_name, entries = load_watchlist(self.watchlist_path)
        tickers = tuple(entry.ticker for entry in entries)
        cutoff = completed_market_date(current_time)
        cached, fetched_at = self.cache.load()
        warnings: list[str] = []
        source = ALPACA_SOURCE
        bars_by_ticker = cached

        if not self.cache.is_fresh(fetched_at, current_time):
            try:
                fetched = self.client.fetch(
                    tickers,
                    start=current_time - timedelta(days=400),
                    end=current_time,
                )
            except AlpacaMarketDataError:
                if not cached:
                    raise
                warnings.append(
                    "Alpaca 刷新失败，当前展示最近一次本地缓存。"
                )
                source = f"{ALPACA_SOURCE} · 本地缓存"
            else:
                bars_by_ticker = fetched
                fetched_at = current_time
                self.cache.save(fetched, fetched_at=current_time)
        else:
            source = f"{ALPACA_SOURCE} · 15 分钟本地缓存"

        rows: list[DrawdownRow] = []
        for entry in entries:
            bars = tuple(
                bar
                for bar in bars_by_ticker.get(entry.ticker, ())
                if bar.trade_date <= cutoff
            )
            calculated = calculate_max_drawdown(bars, window=window)
            if calculated is None:
                rows.append(
                    DrawdownRow(
                        rank=None,
                        ticker=entry.ticker,
                        name=entry.name,
                        group=entry.group,
                        max_drawdown_pct=None,
                        peak_date=None,
                        peak_price=None,
                        trough_date=None,
                        trough_price=None,
                        start_date=None,
                        end_date=None,
                        trading_days=len(bars),
                        status="有效交易日不足",
                    )
                )
                continue
            rows.append(
                DrawdownRow(
                    rank=None,
                    ticker=entry.ticker,
                    name=entry.name,
                    group=entry.group,
                    max_drawdown_pct=calculated.max_drawdown_pct,
                    peak_date=calculated.peak_date,
                    peak_price=calculated.peak_price,
                    trough_date=calculated.trough_date,
                    trough_price=calculated.trough_price,
                    start_date=calculated.start_date,
                    end_date=calculated.end_date,
                    trading_days=calculated.trading_days,
                    status=calculated.status,
                )
            )

        ranked = sorted(
            (row for row in rows if row.max_drawdown_pct is not None),
            key=lambda row: row.max_drawdown_pct or 0,
        )
        unavailable = sorted(
            (row for row in rows if row.max_drawdown_pct is None),
            key=lambda row: row.ticker,
        )
        final_rows = tuple(
            DrawdownRow(**{**asdict(row), "rank": index})
            for index, row in enumerate(ranked, start=1)
        ) + tuple(unavailable)
        successful = tuple(row for row in final_rows if row.end_date is not None)
        if unavailable:
            warnings.append(
                "以下标的数据不足，未参与排序："
                + "、".join(row.ticker for row in unavailable)
            )
        incomplete = tuple(row for row in successful if row.trading_days < window)
        if incomplete:
            warnings.append(
                "以下标的不足完整窗口："
                + "、".join(row.ticker for row in incomplete)
            )
        as_of = max((row.end_date for row in successful if row.end_date), default=None)
        start_date = min(
            (row.start_date for row in successful if row.start_date),
            default=None,
        )
        return DrawdownReport(
            window=window,
            rows=final_rows,
            as_of=as_of,
            start_date=start_date,
            source=source,
            warnings=tuple(warnings),
            fetched_at=fetched_at.isoformat() if fetched_at is not None else None,
        )
