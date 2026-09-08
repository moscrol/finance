"""结构视角：MACD 背离与缠论分型 / 笔 / 中枢 / 三买，只在可知的那天写出；定义按老笔与三笔重叠中枢。"""

from __future__ import annotations

from intelligence.services.teaching_framework.flags import compute_flags
from intelligence.services.teaching_framework.structure import (
    STRUCTURE_FIELDS,
    Fractal,
    Stroke,
    macd,
    merge_inclusion,
    pivots,
    strokes,
    structure_daily,
    structure_summary,
)


def _bars(path: list[float], width: float = 1.0) -> list[dict]:
    """A price path → OHLC rows with a fixed high/low band around the close; day k is 2026-01-(k+1) on a fake calendar."""
    rows = []
    for k, c in enumerate(path):
        rows.append({"trade_date": f"2026-{1 + k // 28:02d}-{1 + k % 28:02d}", "sh_index_close": c, "sh_index_high": c + width, "sh_index_low": c - width, "sh_index_open": c})
    return rows


def test_macd_matches_hand_computation_and_restarts_after_none():
    close = [10.0] * 40
    dif, dea, hist = macd(close)
    assert all(abs(x) < 1e-9 for x in dif[:40] if x is not None) and hist[-1] == 0.0
    # 一根 None 让 EMA 重新起算：之后的值从头来。
    close2 = [10.0] * 5 + [None] + [12.0] * 5
    dif2, _, _ = macd(close2)
    assert dif2[5] is None and dif2[6] == 0.0  # 重新起算的第一根 DIF = 0


def test_inclusion_merges_contained_bars_by_direction():
    highs = [10, 11, 10.5, 12, 11.5]
    lows = [9, 10, 10.2, 11, 11.2]
    bars = merge_inclusion(highs, lows)
    # 第三根 (10.5, 10.2) 被第二根 (11, 10) 包含，方向向上 → 合成 高 11 低 10.2；第五根被第四根包含同理。
    assert [(b.high, b.low, b.idx) for b in bars] == [(10, 9, 0), (11, 10.2, 2), (12, 11.2, 4)]


def test_fractals_strokes_pivot_and_third_buy_are_dated_on_confirmation():
    # 走势：下 → 底 A → 上 → 顶 B → 下 → 底 C（高于 A）→ 上 → 顶 D → 下 → 底 E → 上冲出中枢 → 回抽不进中枢（三买）→ 再上。
    path = (
        [20, 19, 18, 17, 16, 15]            # 0-5   下到 15（底 A 在 5）
        + [16, 17, 18, 19, 20]              # 6-10  上到 20（顶 B 在 10）
        + [19, 18, 17, 16.5, 16]            # 11-15 下到 16（底 C 在 15，高于 A）
        + [17, 18, 19, 19.5, 20.5]          # 16-20 上到 20.5（顶 D 在 20）
        + [19.5, 18.5, 17.5, 17, 16.5]      # 21-25 下到 16.5（底 E 在 25）
        + [18, 20, 22, 24, 26]              # 26-30 向上离开中枢（顶 F 在 30）
        + [25, 24, 23, 22.5, 22]            # 31-35 回抽到 22（底 G 在 35，仍在 ZG 20 之上 → 三买）
        + [23, 24, 25, 26, 27]              # 36-40 再上
    )
    rows = _bars(path, width=0.4)
    out = structure_daily(rows)
    assert len(out) == len(path) and set(out[0]) == set(STRUCTURE_FIELDS)
    # 底分型 A 的中间 K 线是第 5 根，第 6 根收盘才确认 → 事件记在 6，不在 5。
    assert out[5]["chan_fractal"] is None and out[6]["chan_fractal"] == "bottom"
    assert out[11]["chan_fractal"] == "top"  # 顶 B（第 10 根）在第 11 根确认
    # 第一笔（A→B，向上）在顶 B 确认日成立：那天起「当前笔」是向下的第 1 天。
    assert out[11]["chan_stroke_count"] == 1 and out[11]["chan_stroke_dir"] == "down" and out[11]["chan_stroke_day"] == 1
    # 中枢：A→B、B→C、C→D 三笔重叠（分型价用高 / 低点，带宽 0.4）→ ZG = min(20.4, 20.4, 20.9) = 20.4，ZD = max(14.6, 15.6, 15.6) = 15.6；
    # 顶 D 第 21 根确认那天中枢才可知。D→E 与 E→F 的区间仍与中枢重叠（E→F 从区间里出发）→ 算延伸；F→G 整段在 ZG 之上 → 中枢到 E→F 结束。
    assert out[20]["chan_pivot_zg"] is None and abs(out[21]["chan_pivot_zg"] - 20.4) < 1e-9 and abs(out[21]["chan_pivot_zd"] - 15.6) < 1e-9
    assert out[21]["chan_pivot_pos"] == "inside" and out[30]["chan_pivot_pos"] == "above"
    assert out[21]["chan_pivot_strokes"] == 3 and out[36]["chan_pivot_strokes"] == 5  # D→E、E→F 两笔延伸进了中枢
    # 三买：向上离开中枢的一笔（E→F）之后回抽到 22（底 G）仍在 ZG 之上；记在底 G 确认日（第 36 根）。
    assert out[36]["chan_third_buy"] is True and sum(1 for r in out if r["chan_third_buy"]) == 1
    assert not any(r["chan_third_sell"] for r in out)
    summary = structure_summary(out)
    assert summary["chan_third_buy"] == 1 and summary["days_with_pivot"] == len(path) - 21 and summary["pivot_pos"]["above"] >= 10


def test_bottom_divergence_needs_lower_low_with_higher_indicator():
    # 用最短的构造直接测背离判定：两个底分型，价格更低而指标更高。
    fr = [Fractal("bottom", 2, 2, 3, 100.0), Fractal("bottom", 8, 8, 9, 95.0)]
    series = [None] * 2 + [-1.0] + [None] * 5 + [-0.5, None]
    from intelligence.services.teaching_framework.structure import _divergence_events

    assert _divergence_events(fr, series, "bottom", 60) == {9: 8}   # 记在第二个底分型的确认日 9，锚点是极值日 8
    assert _divergence_events(fr, [None] * 2 + [-0.5] + [None] * 5 + [-1.0, None], "bottom", 60) == {}  # 指标也更低 → 不是背离
    assert _divergence_events(fr, series, "bottom", 3) == {}  # 两个底相隔超过 lookback → 不比


def test_strokes_replace_the_endpoint_with_a_more_extreme_same_kind_fractal():
    fr = [
        Fractal("bottom", 0, 0, 1, 10.0), Fractal("top", 5, 5, 6, 15.0),
        Fractal("top", 7, 7, 8, 16.0),   # 更高的顶：替换第一笔的终点
        Fractal("bottom", 12, 12, 13, 12.0),
    ]
    st = strokes(fr)
    assert [(s.direction, s.start.price, s.end.price, s.confirm_idx) for s in st] == [("up", 10.0, 16.0, 8), ("down", 16.0, 12.0, 13)]
    # 中间不到 4 根合并 K 线的反向分型不成笔。
    assert strokes([Fractal("bottom", 0, 0, 1, 10.0), Fractal("top", 2, 2, 3, 15.0)]) == []
    # 三笔不重叠就没有中枢：上 10→12、下 12→8、上 8→9（反弹不到第一笔的起点）→ ZG = 9 ≤ ZD = 10。
    no_overlap = [Stroke("up", Fractal("bottom", 0, 0, 1, 10), Fractal("top", 5, 5, 6, 12), 6), Stroke("down", Fractal("top", 5, 5, 6, 12), Fractal("bottom", 10, 10, 11, 8), 11), Stroke("up", Fractal("bottom", 10, 10, 11, 8), Fractal("top", 15, 15, 16, 9), 16)]
    assert pivots(no_overlap) == []


def test_missing_high_low_breaks_the_kline_segment_but_macd_continues():
    path = [10, 11, 12, 11, 10, 9, 10, 11, 12, 13, 12, 11]
    rows = _bars(path)
    rows[5]["sh_index_high"] = None  # 08-17 那类缺高低价的日子
    out = structure_daily(rows)
    assert out[5]["chan_fractal"] is None and out[5]["macd_dif"] is not None
    # 缺口之后的分型从缺口后重新数：第 6 根起的段里，第 9 根是顶，第 10 根确认。
    assert out[10]["chan_fractal"] == "top"


def test_flags_carry_structure_fields_as_tf_labels():
    days = [f"2026-01-{d:02d}" for d in range(1, 29)]
    rows = _bars([100 + ((k * 7) % 5) for k in range(28)])
    for r, d in zip(rows, days):
        r["trade_date"] = d
        r.update({"sh_week_ma": 100.0, "sh_deviation_pct": 0.5, "total_amount": 100.0, "amount_ma20": 90.0, "amount_vs_yesterday_pct": 1.0})
    out = compute_flags(rows, calendar=days)
    assert "macd_dif" in out[-1] and "chan_stroke_dir" in out[-1] and "chan_third_buy" in out[-1]
    assert isinstance(out[-1]["macd_bottom_div_dif"], bool)
