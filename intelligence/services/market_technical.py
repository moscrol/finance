"""market_technical：指数/个股技术位（支撑、压力）的确定性直查与计算。

设计（与 market_timeseries 的 D0 数据块同一纪律）：

- **结构化行情优先，成功即停**：该题型只需要 OHLCV 日线，取到后用固定算法
  计算 MA / 摆动低点 / 区间低点 / 缺口，不进 Wiki RAG、知识图谱、agent web loop。
- **确定性计算，LLM 只做表述**：支撑位是算出来的，不是模型猜的；每个候选位
  必须带计算口径与数据截止日。
- **fail-closed**：取不到 OHLCV 时返回明确的数据缺口短答素材，禁止用题材结构、
  公司公告等无关模板代答。

数据源：腾讯行情 K 线 API（web.ifzq.gtimg.cn，免认证公开接口，指数与个股同一
口径）。选它而不是 fupanhui/CDP：无登录态依赖、无浏览器依赖、可在服务端直连。
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from intelligence.services.query_understanding import (
    match_index_subject,
)

_KLINE_URL = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    "?param={symbol},day,,,{count},qfq"
)
DEFAULT_BARS = 120
_TIMEOUT_SECONDS = 10.0
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_CLOSE_READY_TIME = time(15, 5)
_CLOSE_MARK_TIME = time(15, 0)

# ts_code → 腾讯行情代码。指数用交易所前缀小写 + 6 位代码。
_TS_TO_TENCENT: dict[str, str] = {
    "000688.SH": "sh000688",
    "000698.SH": "sh000698",
    "000016.SH": "sh000016",
    "000001.SH": "sh000001",
    "000300.SH": "sh000300",
    "000905.SH": "sh000905",
    "000852.SH": "sh000852",
    "399001.SZ": "sz399001",
    "399006.SZ": "sz399006",
    "899050.BJ": "bj899050",
}
_TICKER_RE = re.compile(
    r"(?<![A-Za-z0-9])(\d{6})(?:\.(SH|SZ|BJ))?(?![A-Za-z0-9])", re.I
)


@dataclass(frozen=True)
class DailyBar:
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float | None = None


@dataclass(frozen=True)
class MarketInstrument:
    display_name: str
    ts_code: str | None
    exchange: str
    provider_symbol: str
    security_kind: str = "equity"


@dataclass(frozen=True)
class LiveQuote:
    price: float
    as_of: str
    source: str


@dataclass(frozen=True)
class MarketSeries:
    instrument: MarketInstrument
    completed_bars: tuple[DailyBar, ...]
    live_bar: DailyBar | None
    live_quote: LiveQuote | None
    source_as_of: str | None


@dataclass(frozen=True)
class SupportLevel:
    zone_low: float
    zone_high: float
    basis: tuple[str, ...]  # 计算口径，如 "MA20=1043.2"、"7/8 摆动低点 1039.5"


@dataclass(frozen=True)
class TechnicalLevels:
    subject: str
    symbol: str
    as_of: str  # 数据截止日
    close: float
    ma: dict[str, float | None]
    supports: tuple[SupportLevel, ...]
    resistances: tuple[SupportLevel, ...]
    invalidation: str  # 失效条件
    warnings: tuple[str, ...] = ()
    live_quote: LiveQuote | None = None
    volume_confirmation: str | None = None
    volume_available: bool = False


@dataclass(frozen=True)
class TechnicalGap:
    subject: str
    symbol: str | None
    reason: str


def now_shanghai() -> datetime:
    """返回可替换的上海时区当前时间，便于盘中/收盘边界回归。"""

    return datetime.now(_SHANGHAI_TZ)


def _parse_decimal(value: object) -> float | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return float(parsed)


def _parse_quote_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{14}", text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d%H%M%S").replace(
            tzinfo=_SHANGHAI_TZ
        )
    except ValueError:
        return None


def _bar_date(value: str) -> datetime.date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def split_completed_bars(
    bars: list[DailyBar],
    *,
    quote_timestamp: datetime | None,
    now: datetime | None = None,
) -> tuple[tuple[DailyBar, ...], DailyBar | None]:
    """把最新日线拆为已完成数据和盘中行。

    同日行在收盘后也必须有可信 quote timestamp 才能进入 completed，
    这样 provider 返回半截/无时间戳数据时会 fail-closed。
    """

    if not bars:
        return (), None
    ordered = tuple(sorted(bars, key=lambda bar: bar.date))
    latest = ordered[-1]
    latest_date = _bar_date(latest.date)
    current = now or now_shanghai()
    if latest_date is None:
        return ordered[:-1], latest
    if latest_date < current.date():
        return ordered, None
    timestamp_ready = (
        quote_timestamp is not None
        and quote_timestamp.date() == latest_date
        and quote_timestamp.time() >= _CLOSE_MARK_TIME
        and current.time() >= _CLOSE_READY_TIME
    )
    if timestamp_ready:
        return ordered, None
    return ordered[:-1], latest


def resolve_market_instrument(query: str) -> MarketInstrument | None:
    """解析主体为规范证券与 provider 代码；无法唯一判断时不猜测。"""

    index_hit = match_index_subject(query)
    if index_hit is not None:
        name, ts_code = index_hit
        tencent = _TS_TO_TENCENT.get(ts_code)
        if tencent is not None:
            exchange = ts_code.rsplit(".", 1)[-1]
            return MarketInstrument(
                display_name=name,
                ts_code=ts_code,
                exchange=exchange,
                provider_symbol=tencent,
                security_kind="index",
            )
        return None
    match = _TICKER_RE.search(str(query or ""))
    if match is not None:
        code, suffix = match.group(1), (match.group(2) or "").upper()
        if not suffix:
            if code.startswith("92"):
                suffix = "BJ"
            elif code.startswith(("4", "8")):
                suffix = "BJ"
            elif code.startswith(("6", "9", "5")):
                suffix = "SH"
            else:
                suffix = "SZ"
        if suffix not in {"SH", "SZ", "BJ"}:
            return None
        return MarketInstrument(
            display_name=f"{code}.{suffix}",
            ts_code=f"{code}.{suffix}",
            exchange=suffix,
            provider_symbol=f"{suffix.lower()}{code}",
        )
    return None


def resolve_technical_symbol(query: str) -> tuple[str, str] | None:
    """兼容旧调用：返回 (显示名, 腾讯代码)。"""

    instrument = resolve_market_instrument(query)
    if instrument is None:
        return None
    return instrument.display_name, instrument.provider_symbol


def fetch_daily_bars(
    symbol: str,
    *,
    count: int = DEFAULT_BARS,
    timeout: float = _TIMEOUT_SECONDS,
    opener=None,
) -> tuple[list[DailyBar], str | None]:
    """拉取日线。返回 (bars, error)；失败时 bars 为空且 error 非 None。"""
    node, error = _fetch_node(symbol, count=count, timeout=timeout, opener=opener)
    if error is not None:
        return [], error
    rows = node.get("qfqday") or node.get("day")
    bars = _parse_daily_rows(rows)
    if len(bars) < 25:
        return [], f"日线数据不足（仅 {len(bars)} 根，需要 ≥25 根）"
    return bars, None


def _fetch_node(
    symbol: str,
    *,
    count: int,
    timeout: float,
    opener=None,
) -> tuple[dict[str, object], str | None]:
    url = _KLINE_URL.format(symbol=symbol, count=count)
    try:
        open_fn = opener or urllib.request.urlopen
        with open_fn(url, timeout=timeout) as resp:  # noqa: S310 白名单域名
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {}, f"行情接口请求失败：{type(exc).__name__}: {exc}"
    node = (payload or {}).get("data", {}).get(symbol, {})
    if not isinstance(node, dict):
        return {}, "行情接口返回中没有有效证券节点"
    return node, None


def _parse_daily_rows(rows: object) -> list[DailyBar]:
    if not isinstance(rows, list) or not rows:
        return []
    bars: list[DailyBar] = []
    for row in rows:
        try:
            volume = _parse_decimal(row[5]) if len(row) > 5 else None
            bars.append(
                DailyBar(
                    date=str(row[0]),
                    open=float(row[1]),
                    close=float(row[2]),
                    high=float(row[3]),
                    low=float(row[4]),
                    volume=volume,
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    return bars


def _quote_from_node(node: dict[str, object], symbol: str) -> tuple[LiveQuote | None, datetime | None]:
    raw_qt = node.get("qt")
    quote_rows = raw_qt.get(symbol) if isinstance(raw_qt, dict) else None
    if not isinstance(quote_rows, list):
        return None, None
    price = _parse_decimal(quote_rows[4]) if len(quote_rows) > 4 else None
    timestamp = _parse_quote_timestamp(quote_rows[30] if len(quote_rows) > 30 else None)
    if price is None or timestamp is None:
        return None, timestamp
    return (
        LiveQuote(
            price=price,
            as_of=timestamp.isoformat(timespec="seconds"),
            source=f"tencent_quote:{symbol}",
        ),
        timestamp,
    )


def fetch_market_series(
    instrument: MarketInstrument,
    *,
    count: int = DEFAULT_BARS,
    timeout: float = _TIMEOUT_SECONDS,
    opener=None,
    now: datetime | None = None,
) -> tuple[MarketSeries | None, str | None]:
    """获取原始日线并分离已完成日线与实时行。"""

    node, error = _fetch_node(
        instrument.provider_symbol,
        count=count,
        timeout=timeout,
        opener=opener,
    )
    if error is not None:
        return None, error
    rows = node.get("qfqday") or node.get("day")
    bars = _parse_daily_rows(rows)
    if not bars:
        return None, "行情接口返回中没有日线数据"
    if len(bars) < 25:
        return None, f"日线数据不足（仅 {len(bars)} 根，需要 ≥25 根）"
    live_quote, quote_timestamp = _quote_from_node(node, instrument.provider_symbol)
    completed, live_bar = split_completed_bars(
        bars,
        quote_timestamp=quote_timestamp,
        now=now,
    )
    source_as_of = completed[-1].date if completed else None
    return (
        MarketSeries(
            instrument=instrument,
            completed_bars=completed,
            live_bar=live_bar,
            live_quote=live_quote,
            source_as_of=source_as_of,
        ),
        None,
    )


def _ma(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def _swing_lows(bars: list[DailyBar], lookback: int = 60, wing: int = 2) -> list[DailyBar]:
    """近 lookback 日内的摆动低点：low 低于左右各 wing 日的 low。"""
    window = bars[-lookback:]
    lows: list[DailyBar] = []
    for i in range(wing, len(window) - wing):
        low = window[i].low
        if all(low < window[j].low for j in range(i - wing, i)) and all(
            low <= window[j].low for j in range(i + 1, i + wing + 1)
        ):
            lows.append(window[i])
    return lows


def _gap_zones(bars: list[DailyBar], lookback: int = 60) -> list[tuple[str, float, float]]:
    """向上跳空缺口（回补即支撑）：前日 high < 当日 low。"""
    window = bars[-lookback:]
    zones: list[tuple[str, float, float]] = []
    for prev, cur in zip(window, window[1:]):
        if prev.high < cur.low:
            zones.append((cur.date, prev.high, cur.low))
    return zones


def _cluster(
    candidates: list[tuple[float, str]], tolerance_pct: float = 0.6
) -> list[SupportLevel]:
    """把价格相近（±tolerance%）的候选位聚成支撑区。"""
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda item: item[0], reverse=True)
    clusters: list[list[tuple[float, str]]] = [[ordered[0]]]
    for price, basis in ordered[1:]:
        anchor = clusters[-1][0][0]
        if anchor and abs(anchor - price) / anchor * 100 <= tolerance_pct:
            clusters[-1].append((price, basis))
        else:
            clusters.append([(price, basis)])
    levels = []
    for cluster in clusters:
        prices = [p for p, _ in cluster]
        levels.append(
            SupportLevel(
                zone_low=min(prices),
                zone_high=max(prices),
                basis=tuple(b for _, b in cluster),
            )
        )
    return levels


def bars_at_or_before(
    bars: list[DailyBar] | tuple[DailyBar, ...],
    as_of: str,
) -> list[DailyBar]:
    """保留 `bar.date <= as_of` 的已完成日线。ISO 日期可直接按字符串比较。"""
    cutoff = str(as_of or "").strip()
    if not cutoff:
        return list(bars)
    return [bar for bar in bars if bar.date <= cutoff]


def compute_technical_levels(
    subject: str,
    symbol: str,
    bars: list[DailyBar],
    *,
    live_quote: LiveQuote | None = None,
) -> TechnicalLevels:
    closes = [bar.close for bar in bars]
    close = closes[-1]
    as_of = bars[-1].date
    ma = {f"MA{w}": _ma(closes, w) for w in (5, 10, 20, 60)}
    warnings: list[str] = []

    support_candidates: list[tuple[float, str]] = []
    resistance_candidates: list[tuple[float, str]] = []
    for name, value in ma.items():
        if value is None:
            warnings.append(f"{name} 数据不足未计算")
            continue
        if value <= close:
            support_candidates.append((value, f"{name}={value:.2f}"))
        else:
            resistance_candidates.append((value, f"{name}={value:.2f}"))
    for bar in _swing_lows(bars):
        if bar.low <= close:
            support_candidates.append((bar.low, f"{bar.date} 摆动低点 {bar.low:.2f}"))
    low20 = min(bar.low for bar in bars[-20:])
    low60 = min(bar.low for bar in bars[-60:])
    support_candidates.append((low20, f"20日最低 {low20:.2f}"))
    if low60 < low20:
        support_candidates.append((low60, f"60日最低 {low60:.2f}"))
    for gap_date, zone_low, zone_high in _gap_zones(bars):
        if zone_high <= close:
            support_candidates.append(
                ((zone_low + zone_high) / 2,
                 f"{gap_date} 向上跳空缺口 {zone_low:.2f}~{zone_high:.2f}")
            )
    high20 = max(bar.high for bar in bars[-20:])
    high60 = max(bar.high for bar in bars[-60:])
    if high20 > close:
        resistance_candidates.append((high20, f"20日最高 {high20:.2f}"))
    if high60 > high20:
        resistance_candidates.append((high60, f"60日最高 {high60:.2f}"))

    supports = tuple(_cluster(support_candidates)[:4])
    resistances = tuple(
        sorted(_cluster(resistance_candidates), key=lambda lv: lv.zone_low)[:3]
    )
    if supports:
        floor = min(level.zone_low for level in supports)
        invalidation = (
            f"若收盘价跌破最低支撑区下沿 {floor:.2f}（约 -"
            f"{(close - floor) / close * 100:.1f}%），上述支撑判断失效，"
            "需按新低重新计算。"
        )
    else:
        invalidation = "当前收盘价已低于全部候选支撑，技术支撑框架失效。"
    volume_confirmation: str | None = None
    volumes = [bar.volume for bar in bars[-20:] if bar.volume is not None]
    if len(volumes) == 20 and bars[-1].volume is not None:
        baseline = sum(volumes[:-1]) / 19 if len(volumes) > 1 else 0.0
        if baseline > 0:
            ratio = bars[-1].volume / baseline
            volume_confirmation = (
                f"最近完整日成交量约为20日均量的 {ratio:.2f} 倍"
            )
    return TechnicalLevels(
        subject=subject,
        symbol=symbol,
        as_of=as_of,
        close=close,
        ma=ma,
        supports=supports,
        resistances=resistances,
        invalidation=invalidation,
        warnings=tuple(warnings),
        live_quote=live_quote,
        volume_confirmation=volume_confirmation,
        volume_available=all(bar.volume is not None for bar in bars[-20:]),
    )


def resolve_market_technical(
    query: str,
    *,
    as_of: str | None = None,
    count: int = DEFAULT_BARS,
    timeout: float = _TIMEOUT_SECONDS,
    opener=None,
) -> TechnicalLevels | TechnicalGap:
    """入口：解析主体 → 拉日线 → 确定性计算。失败返回 TechnicalGap。

    ``as_of`` 非空时把已完成日线截断到该日（含）再算；早于窗口或截断后
    样本不足则 fail closed，不得回落到最新一根。
    """
    index_hit = match_index_subject(query)
    instrument = resolve_market_instrument(query)
    if index_hit is not None and instrument is None:
        return TechnicalGap(
            subject=index_hit[0],
            symbol=None,
            reason=f"provider_unsupported：{index_hit[1]} 暂无可执行日线映射",
        )
    if instrument is None:
        return TechnicalGap(
            subject=str(query or "").strip()[:32],
            symbol=None,
            reason="未能从问题中解析出可取行情的指数或股票代码",
        )
    series, error = fetch_market_series(
        instrument,
        count=count,
        timeout=timeout,
        opener=opener,
    )
    if error is not None:
        return TechnicalGap(
            subject=instrument.display_name,
            symbol=instrument.provider_symbol,
            reason=error,
        )
    assert series is not None
    bars = list(series.completed_bars)
    live_quote = series.live_quote
    requested = str(as_of or "").strip() or None
    if requested:
        earliest = bars[0].date if bars else "无"
        bars = bars_at_or_before(bars, requested)
        if not bars:
            return TechnicalGap(
                subject=instrument.display_name,
                symbol=instrument.provider_symbol,
                reason=f"窗口不足，最早可得 {earliest}",
            )
        if series.completed_bars and bars[-1].date != series.completed_bars[-1].date:
            live_quote = None
    if len(bars) < 60:
        return TechnicalGap(
            subject=instrument.display_name,
            symbol=instrument.provider_symbol,
            reason=(
                f"已完成日线不足（仅 {len(bars)} 根，需要 ≥60 根；"
                f"最新行 {series.live_bar.date if series.live_bar else '无'} 未确认）"
            ),
        )
    return compute_technical_levels(
        instrument.display_name,
        instrument.provider_symbol,
        bars,
        live_quote=live_quote,
    )


def gap_answer_text(gap: TechnicalGap) -> str:
    """fail-closed 数据缺口短答：只报缺口，不用其他题材/模板代答。"""
    return (
        f"截至当前，尚未取得{gap.subject}的近期日线行情（OHLCV），"
        f"因此无法可靠计算支撑位。缺口原因：{gap.reason}。"
        "请稍后重试，或指定明确的指数/股票代码。"
    )
