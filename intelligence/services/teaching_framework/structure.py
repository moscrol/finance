"""结构视角（创始人 09-08：「我之前的 MACD 底背离和缠论的用法，能结合起来吗」）：上证日线上的 MACD 背离与缠论结构，逐日只写出。

位置（骨架 §0 的分类）：这些**不是阶段**——阶段是赚钱效应的水位（§8.17）；它们是**转点证据的候选与事件锚点**：
底背离 / 缠论二买出在第二个底上，正好是「缩量右底 = 周均线下方回踩探底」那一格的确认（经典「背驰右底」）；
三买（回踩不进中枢）对应共建主线「放量上穿后回踩不破」；顶背离对应见顶。先算成视角写出，用 ``views_by_event``
看事件后 5 / 10 / 20 日各段怎么走、用 ``stage_separation`` 靶子看分不分得开，过了门才进证据。**输出永远是
观察 / 确认 / 失效的事件，不是买卖点**（fph2026 旁路库同一条红线）。

三条工程纪律：

1. **只在可知的那天写出。** 分型要第三根 K 线收盘才成立，笔要下一个反向分型确认，中枢要第三笔走完——每个事件都记在它
   **被确认的那一天**，事件本身指向的极值日另存（``*_anchor_date``）。当天写不出来的就是 None，不猜。
2. **日线只用日线。** 主库只有上证日线 OHLC（``sh_index_open/high/low/close``）；个股没有高低价，缠论做不了；30 分钟级
   没有分钟线源（09-08 探过：东财 / 腾讯的 K 线主机被本机代理拦了，见交接）。所以本模块只算上证日线。
3. **定义是 B 类候选，写在参数里。** MACD 12 / 26 / 9；背离看 DIF 和 MACD 柱两种口径分别写出；分型 / 笔按「老笔」（相邻
   顶底分型的中间 K 线至少隔 4 根合并后 K 线）；中枢 = 连续三笔的重叠区间（ZG = 三笔高点的最小值，ZD = 三笔低点的最大值），
   后续笔与它有重叠就延伸；三买 = 向上离开中枢后第一笔回落的低点仍在 ZG 之上、且该低点的底分型已确认。这些都是 agent 的
   操作化，创始人未逐条认可，等他改。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
STROKE_MIN_GAP = 4          # 老笔：相邻顶 / 底分型的中间 K 线（合并后序号）至少隔 4 根 → 至少 5 根 K 线
DIVERGENCE_LOOKBACK = 60    # 背离比较的两个极值不超过 60 个交易日

# 正式口径（第二十三段，全 A 个股日线过四态门后定）：只看 DIF；两低 = 观察，三低 = 确认；跌破锚点低点 = 失效；顶背离只记 DIF 两高。
# 摆动低点按收盘算（前后各 SWING_K 天里唯一最低，第 SWING_K 天后确认），指数 / 板块 / 个股同一定义。
DIVERGENCE_EVENT_FIELDS: tuple[str, ...] = (
    "macd_bottom_div_observe", "macd_bottom_div_confirm", "macd_bottom_div_failed", "macd_top_div", "macd_div_anchor_idx",
)
STRUCTURE_FIELDS: tuple[str, ...] = (
    "macd_dif", "macd_dea", "macd_hist",
    "macd_bottom_div_dif", "macd_bottom_div_hist", "macd_top_div_dif", "macd_top_div_hist",
    "days_since_macd_bottom_div", "days_since_macd_top_div",
    "chan_fractal", "chan_stroke_dir", "chan_stroke_day", "chan_stroke_count",
    "chan_pivot_zg", "chan_pivot_zd", "chan_pivot_pos", "chan_pivot_strokes",
    "chan_third_buy", "chan_third_sell", "chan_stroke_bottom_divergence", "chan_stroke_top_divergence",
) + DIVERGENCE_EVENT_FIELDS
SWING_K = 2
FAIL_HORIZON = 20


def structure_params(params: Mapping[str, Any] | None) -> dict[str, int]:
    """参数文件 ``structure`` 块 → ``structure_daily`` / ``divergence_events`` 的关键字参数（指数、板块、个股共用同一份口径）。"""
    block = (params or {}).get("structure") or {}
    return {
        "lookback": int(block.get("divergence_lookback", DIVERGENCE_LOOKBACK)),
        "swing_k": int(block.get("swing_k", SWING_K)),
        "fail_horizon": int(block.get("fail_horizon", FAIL_HORIZON)),
    }


def close_swings(close: Sequence[float | None], k: int = SWING_K, kind: str = "low") -> list[int]:
    """收盘的摆动低点 / 高点：位置 i 的收盘是 [i−k, i+k] 里唯一的最小 / 最大值（窗口内不能有 None）。"""
    out: list[int] = []
    pick = min if kind == "low" else max
    for i in range(k, len(close) - k):
        window = close[i - k : i + k + 1]
        if any(v is None for v in window):
            continue
        if close[i] == pick(window) and window.count(close[i]) == 1:
            out.append(i)
    return out


def divergence_events(
    close: Sequence[float | None], *, k: int = SWING_K, lookback: int = DIVERGENCE_LOOKBACK, fail_horizon: int = FAIL_HORIZON
) -> list[dict[str, Any]]:
    """正式的 MACD 背离事件序列（观察 / 确认 / 失效 / 顶背离），每个记在可知的那一天，任何收盘序列都能套。

    观察 = 相邻两个摆动低点，后者收盘更低而 DIF 更高（两低相隔 ≤ lookback），记在后一个低点确认日（低点 + k）；
    确认 = 连续三个摆动低点收盘递降、DIF 递升，记在第三个低点确认日；失效 = 观察 / 确认之后 fail_horizon 个交易日内
    收盘跌破锚点低点的第一天；顶背离 = 相邻两个摆动高点收盘更高而 DIF 更低。``macd_div_anchor_idx`` 是当日事件指向的极值位置。
    全 A 个股日线上的读数（骨架 §8.18）：两低 52.9% / 三低 56.6% 的 20 日超额为正（基准 50%），三低超额中位 +1.25%。
    """
    n = len(close)
    dif, _, _ = macd(close)
    out: list[dict[str, Any]] = [
        {"macd_bottom_div_observe": False, "macd_bottom_div_confirm": False, "macd_bottom_div_failed": False, "macd_top_div": False, "macd_div_anchor_idx": None}
        for _ in range(n)
    ]
    lows = close_swings(close, k, "low")
    anchors: list[tuple[int, int]] = []  # (确认日, 锚点低点)
    for a, b in zip(lows, lows[1:]):
        if b - a > lookback or dif[a] is None or dif[b] is None or b + k >= n:
            continue
        if close[b] < close[a] and dif[b] > dif[a]:
            out[b + k]["macd_bottom_div_observe"] = True
            out[b + k]["macd_div_anchor_idx"] = b
            anchors.append((b + k, b))
    for a, b, c in zip(lows, lows[1:], lows[2:]):
        if c - a > lookback or any(dif[x] is None for x in (a, b, c)) or c + k >= n:
            continue
        if close[c] < close[b] < close[a] and dif[c] > dif[b] > dif[a]:
            out[c + k]["macd_bottom_div_confirm"] = True
            out[c + k]["macd_div_anchor_idx"] = c
    for confirm_i, low_i in anchors:
        floor = close[low_i]
        for j in range(confirm_i + 1, min(n, confirm_i + 1 + fail_horizon)):
            if close[j] is not None and close[j] < floor:
                out[j]["macd_bottom_div_failed"] = True
                if out[j]["macd_div_anchor_idx"] is None:
                    out[j]["macd_div_anchor_idx"] = low_i
                break
    highs = close_swings(close, k, "high")
    for a, b in zip(highs, highs[1:]):
        if b - a > lookback or dif[a] is None or dif[b] is None or b + k >= n:
            continue
        if close[b] > close[a] and dif[b] < dif[a]:
            out[b + k]["macd_top_div"] = True
            if out[b + k]["macd_div_anchor_idx"] is None:
                out[b + k]["macd_div_anchor_idx"] = b
    return out


def ema(values: Sequence[float | None], n: int) -> list[float | None]:
    """Standard EMA (alpha = 2 / (n + 1)); the series is None until the first value and after any None input."""
    out: list[float | None] = []
    prev: float | None = None
    alpha = 2.0 / (n + 1)
    for v in values:
        if v is None:
            out.append(None)
            prev = None
            continue
        prev = v if prev is None else prev + alpha * (v - prev)
        out.append(prev)
    return out


def macd(close: Sequence[float | None], fast: int = MACD_FAST, slow: int = MACD_SLOW, signal: int = MACD_SIGNAL) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """DIF = EMA(fast) − EMA(slow); DEA = EMA(DIF, signal); HIST = 2 × (DIF − DEA)（国内软件的 MACD 柱口径）."""
    ef, es = ema(close, fast), ema(close, slow)
    dif = [None if a is None or b is None else a - b for a, b in zip(ef, es)]
    dea = ema(dif, signal)
    hist = [None if a is None or b is None else 2.0 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, hist


@dataclass
class Bar:
    idx: int            # 合并后这根 Bar 覆盖到的最后一根原始 K 线序号
    high: float
    low: float


def merge_inclusion(highs: Sequence[float], lows: Sequence[float]) -> list[Bar]:
    """缠论包含关系处理：相邻两根 K 线一根完全包住另一根时，按当前方向合成一根（向上取高高，向下取低低）。"""
    bars: list[Bar] = []
    direction = 0  # +1 上，−1 下，0 未定
    for i, (hi, lo) in enumerate(zip(highs, lows)):
        if not bars:
            bars.append(Bar(i, hi, lo))
            continue
        last = bars[-1]
        contains = (hi >= last.high and lo <= last.low) or (hi <= last.high and lo >= last.low)
        if contains:
            if direction >= 0:
                last.high, last.low = max(last.high, hi), max(last.low, lo)
            else:
                last.high, last.low = min(last.high, hi), min(last.low, lo)
            last.idx = i
            continue
        direction = 1 if hi > last.high else -1
        bars.append(Bar(i, hi, lo))
    return bars


@dataclass
class Fractal:
    kind: str           # "top" / "bottom"
    bar: int            # 合并后 K 线序号（分型中间那根）
    raw_idx: int        # 中间那根对应的原始 K 线序号（极值日）
    confirm_idx: int    # 第三根 K 线的原始序号：这一天才知道分型成立
    price: float


def fractals(bars: Sequence[Bar]) -> list[Fractal]:
    out: list[Fractal] = []
    for k in range(1, len(bars) - 1):
        a, b, c = bars[k - 1], bars[k], bars[k + 1]
        if b.high > a.high and b.high > c.high and b.low > a.low and b.low > c.low:
            out.append(Fractal("top", k, b.idx, c.idx, b.high))
        elif b.low < a.low and b.low < c.low and b.high < a.high and b.high < c.high:
            out.append(Fractal("bottom", k, b.idx, c.idx, b.low))
    return out


@dataclass
class Stroke:
    direction: str      # "up" / "down"
    start: Fractal
    end: Fractal
    confirm_idx: int    # 终点分型确认的原始序号（这一天才知道这一笔结束）

    @property
    def high(self) -> float:
        return max(self.start.price, self.end.price)

    @property
    def low(self) -> float:
        return min(self.start.price, self.end.price)


def strokes(fractals_: Sequence[Fractal], min_gap: int = STROKE_MIN_GAP) -> list[Stroke]:
    """老笔：顶底交替、中间至少 min_gap 根合并 K 线；同向更极端的分型替换当前端点（顶更高 / 底更低）。"""
    out: list[Stroke] = []
    anchor: Fractal | None = None
    for f in fractals_:
        if anchor is None:
            anchor = f
            continue
        if f.kind == anchor.kind:
            better = f.price > anchor.price if f.kind == "top" else f.price < anchor.price
            if better:
                if out and out[-1].end is anchor:
                    out[-1].end, out[-1].confirm_idx = f, f.confirm_idx
                anchor = f
            continue
        if f.bar - anchor.bar < min_gap:
            continue
        direction = "up" if f.kind == "top" else "down"
        if direction == "up" and f.price <= anchor.price or direction == "down" and f.price >= anchor.price:
            continue
        out.append(Stroke(direction, anchor, f, f.confirm_idx))
        anchor = f
    return out


@dataclass
class Pivot:
    zg: float
    zd: float
    start_stroke: int   # 构成中枢的第一笔在 strokes 里的序号
    end_stroke: int     # 最后一笔（含延伸）
    confirm_idx: int    # 第三笔确认那天的原始序号


def pivots(strokes_: Sequence[Stroke]) -> list[Pivot]:
    """中枢：连续三笔重叠 [max(lows), min(highs)] 非空；之后每一笔与区间有重叠就延伸，否则中枢结束。"""
    out: list[Pivot] = []
    k = 0
    while k + 2 < len(strokes_):
        trio = strokes_[k : k + 3]
        zg, zd = min(s.high for s in trio), max(s.low for s in trio)
        if zg <= zd:
            k += 1
            continue
        piv = Pivot(zg, zd, k, k + 2, trio[2].confirm_idx)
        j = k + 3
        while j < len(strokes_) and strokes_[j].low <= zg and strokes_[j].high >= zd:
            piv.end_stroke = j
            j += 1
        out.append(piv)
        k = j if j > k else k + 1
    return out


def _divergence_events(
    fr: Sequence[Fractal], series: Sequence[float | None], kind: str, lookback: int
) -> dict[int, int]:
    """Bottom (kind='bottom') or top divergence between the last two same-kind fractals, keyed by confirmation day.

    价格创更低的低点（更高的高点）而指标没有：底背离 = 后一个底分型价格更低、指标值更高；顶背离对称。两个分型的极值日
    相距不超过 lookback。值 = 极值日的原始序号（锚点）。
    """
    out: dict[int, int] = {}
    same = [f for f in fr if f.kind == kind]
    for prev, cur in zip(same, same[1:]):
        if cur.raw_idx - prev.raw_idx > lookback:
            continue
        a, b = series[prev.raw_idx], series[cur.raw_idx]
        if a is None or b is None:
            continue
        if kind == "bottom" and cur.price < prev.price and b > a:
            out[cur.confirm_idx] = cur.raw_idx
        if kind == "top" and cur.price > prev.price and b < a:
            out[cur.confirm_idx] = cur.raw_idx
    return out


def _stroke_divergence(strokes_: Sequence[Stroke], hist: Sequence[float | None], direction: str) -> dict[int, int]:
    """笔背驰：同向的连续两笔（中间隔一笔），后一笔创新低（新高）而 MACD 柱面积更小。键 = 后一笔确认日，值 = 终点极值日。"""
    out: dict[int, int] = {}
    same = [s for s in strokes_ if s.direction == direction]
    for prev, cur in zip(same, same[1:]):
        if cur.start.raw_idx - prev.end.raw_idx > DIVERGENCE_LOOKBACK:
            continue
        def area(s: Stroke) -> float | None:
            vals = [hist[i] for i in range(s.start.raw_idx, s.end.raw_idx + 1)]
            if any(v is None for v in vals):
                return None
            sign = -1.0 if direction == "down" else 1.0
            return sum(v for v in vals if v * sign > 0) * sign
        a, b = area(prev), area(cur)
        if a is None or b is None:
            continue
        lower_low = direction == "down" and cur.end.price < prev.end.price
        higher_high = direction == "up" and cur.end.price > prev.end.price
        if (lower_low or higher_high) and abs(b) < abs(a):
            out[cur.confirm_idx] = cur.end.raw_idx
    return out


def _third_buys(strokes_: Sequence[Stroke], pivots_: Sequence[Pivot]) -> tuple[dict[int, int], dict[int, int]]:
    """三买 / 三卖。

    中枢的最后一笔（``end_stroke``）就是离开段——它从区间里出发、终点已在 ZG 之上（ZD 之下），所以按区间重叠它仍算中枢的一部分；
    紧接着第一笔整段在区间之外的回抽（向下、低点 > ZG）就是三买，记在回抽笔确认日，锚点 = 回抽终点。三卖对称。
    """
    buys: dict[int, int] = {}
    sells: dict[int, int] = {}
    for p in pivots_:
        pull = p.end_stroke + 1
        if pull >= len(strokes_):
            continue
        leave, pb = strokes_[p.end_stroke], strokes_[pull]
        if leave.direction == "up" and leave.end.price > p.zg and pb.direction == "down" and pb.end.price > p.zg:
            buys[pb.confirm_idx] = pb.end.raw_idx
        if leave.direction == "down" and leave.end.price < p.zd and pb.direction == "up" and pb.end.price < p.zd:
            sells[pb.confirm_idx] = pb.end.raw_idx
    return buys, sells


def structure_daily(
    rows: Sequence[Mapping[str, Any]],
    *,
    close_col: str = "sh_index_close",
    high_col: str = "sh_index_high",
    low_col: str = "sh_index_low",
    lookback: int = DIVERGENCE_LOOKBACK,
    swing_k: int = SWING_K,
    fail_horizon: int = FAIL_HORIZON,
) -> list[dict[str, Any]]:
    """Per day: MACD values, divergence events, 缠论 fractal / stroke / pivot state, third buy / sell — each only on the day it is knowable.

    Rows must already be the contiguous trading-day sequence (the caller's calendar).  Any day missing high / low / close
    breaks the K-line sequence: everything from that day on that needs the structure is None until the sequence is
    complete again (we do not interpolate).  The MACD series simply restarts after a None close.
    """
    n = len(rows)
    close = [_num(r.get(close_col)) for r in rows]
    high = [_num(r.get(high_col)) for r in rows]
    low = [_num(r.get(low_col)) for r in rows]
    dif, dea, hist = macd(close)
    out: list[dict[str, Any]] = [{k: None for k in STRUCTURE_FIELDS} for _ in range(n)]
    formal = divergence_events(close, k=swing_k, lookback=lookback, fail_horizon=fail_horizon)
    for i in range(n):
        out[i]["macd_dif"], out[i]["macd_dea"], out[i]["macd_hist"] = dif[i], dea[i], hist[i]
        out[i].update(formal[i])
    # 缠论只在高低收齐全的最长尾段上算（中间缺一天就从缺口后重来），分段处理。
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for i in range(n + 1):
        ok = i < n and high[i] is not None and low[i] is not None and close[i] is not None
        if ok and start is None:
            start = i
        if not ok and start is not None:
            segments.append((start, i))
            start = None
    for seg_start, seg_end in segments:
        _fill_segment(out, seg_start, seg_end, high, low, close, dif, hist, lookback)
    # 距上一次背离的天数（含当天 = 0）。
    for key, src in (("days_since_macd_bottom_div", "macd_bottom_div_dif"), ("days_since_macd_top_div", "macd_top_div_dif")):
        last: int | None = None
        for i in range(n):
            if out[i][src] is True:
                last = i
            out[i][key] = None if last is None else i - last
    return out


def _fill_segment(out, seg_start, seg_end, high, low, close, dif, hist, lookback) -> None:
    hs = [high[i] for i in range(seg_start, seg_end)]
    ls = [low[i] for i in range(seg_start, seg_end)]
    bars = merge_inclusion(hs, ls)
    for b in bars:  # 合并后序号回到原始序号
        b.idx += seg_start
    fr = fractals(bars)
    st = strokes(fr)
    pv = pivots(st)
    bottom_dif = _divergence_events(fr, dif, "bottom", lookback)
    bottom_hist = _divergence_events(fr, hist, "bottom", lookback)
    top_dif = _divergence_events(fr, dif, "top", lookback)
    top_hist = _divergence_events(fr, hist, "top", lookback)
    stroke_bottom = _stroke_divergence(st, hist, "down")
    stroke_top = _stroke_divergence(st, hist, "up")
    buys, sells = _third_buys(st, pv)
    fractal_by_confirm = {f.confirm_idx: f.kind for f in fr}
    for i in range(seg_start, seg_end):
        rec = out[i]
        rec["chan_fractal"] = fractal_by_confirm.get(i)
        rec["macd_bottom_div_dif"] = i in bottom_dif
        rec["macd_bottom_div_hist"] = i in bottom_hist
        rec["macd_top_div_dif"] = i in top_dif
        rec["macd_top_div_hist"] = i in top_hist
        rec["chan_stroke_bottom_divergence"] = i in stroke_bottom
        rec["chan_stroke_top_divergence"] = i in stroke_top
        rec["chan_third_buy"] = i in buys
        rec["chan_third_sell"] = i in sells
        # 当日已确认的笔：最后一个 confirm_idx ≤ i 的笔的方向是「上一笔」，当前笔 = 它的反向，从它终点起数。
        done = [s for s in st if s.confirm_idx <= i]
        rec["chan_stroke_count"] = len(done)
        if done:
            last = done[-1]
            rec["chan_stroke_dir"] = "down" if last.direction == "up" else "up"
            rec["chan_stroke_day"] = i - last.end.raw_idx
        known = [p for p in pv if p.confirm_idx <= i]
        if known:
            p = known[-1]
            # 中枢吃了几笔按当日已确认的笔数算（终版的 end_stroke 含日后的延伸，不能提前知道）。
            as_of_end = min(p.end_stroke, len(done) - 1)
            rec["chan_pivot_zg"], rec["chan_pivot_zd"], rec["chan_pivot_strokes"] = p.zg, p.zd, as_of_end - p.start_stroke + 1
            c = close[i]
            rec["chan_pivot_pos"] = None if c is None else ("above" if c > p.zg else "below" if c < p.zd else "inside")


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def structure_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts for the receipt: how many of each event fired, how many days have a known stroke / pivot."""
    recs = list(records)
    def count(key: str) -> int:
        return sum(1 for r in recs if r.get(key) is True)
    return {
        "days": len(recs),
        "macd_bottom_div_dif": count("macd_bottom_div_dif"),
        "macd_bottom_div_hist": count("macd_bottom_div_hist"),
        "macd_top_div_dif": count("macd_top_div_dif"),
        "macd_top_div_hist": count("macd_top_div_hist"),
        "chan_stroke_bottom_divergence": count("chan_stroke_bottom_divergence"),
        "chan_stroke_top_divergence": count("chan_stroke_top_divergence"),
        "chan_third_buy": count("chan_third_buy"),
        "chan_third_sell": count("chan_third_sell"),
        "days_with_stroke": sum(1 for r in recs if r.get("chan_stroke_dir") is not None),
        "days_with_pivot": sum(1 for r in recs if r.get("chan_pivot_zg") is not None),
        "pivot_pos": {pos: sum(1 for r in recs if r.get("chan_pivot_pos") == pos) for pos in ("above", "inside", "below")},
    }
