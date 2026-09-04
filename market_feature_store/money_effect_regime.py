"""赚钱效应 regime：把交易日按情绪结构判成四种可命名状态，并识别切换日。

这是 registry recipe ``money_effect_clustering`` 的「规则守生产」段
（``consumption_registry.yaml``；两段式 = 聚类找边界、规则守生产）。
D 档纯派生：0 请求、只读主库、不落表。k-means 的簇标签只在实验目录里存在，
生产只跑下面这几条可解释、可测试的规则。

口径（与 round 2 实验 ``money_effect_rules.py`` 一致，回放对照写在 registry ``decisions``）：

输入
    ``market_regime_vectors.load_market_regime_vectors`` 的每日情绪向量（D10 十维底座）。
    一天「可用」= 除 ``sh_deviation_pct`` 外九维全非空——该维 2026-07 起源失效，规则也不用它；
    其余五维虽不进规则，但仍要求非空，为的是与实验的 281 天样本逐日对齐（回放才可对照）。

窗口
    trailing ``WINDOW`` 个可用交易日的**原始量纲**均值，只用当日及之前（无前视）。
    可用日序列有缺口（库里 2026-01~03 没数据）时窗口直接跨过缺口，不补零、不插值。

阈值
    不写死亿元——同一个 2.2 万亿在牛熊两头含义不同。改为对每个轴取
    「最近 ``PERCENTILE_LOOKBACK`` 个窗口（含今日）」的经验分位，分位数由 round 2 的绝对阈值
    在 277 窗口样本上反推一次（``THRESHOLD_QUANTILES``，2026-09-05）。这就是监控里的
    动态基线（dynamic baseline）：阈值定义在「相对当下的历史」上，代价是基线本身要有窗口与
    最小样本——不足 ``MIN_HISTORY`` 个窗口时**不出簇名**（fail closed），不用短样本硬算分位。

规则
    4 条决策表按序命中，见 ``classify``。

去抖
    因果式：新簇连续 ``DEBOUNCE_DAYS`` 日才切换，切换日 = 新簇第 2 日。
    实验脚本的去抖是回看式（看到明天也是新簇就在第 1 日切），生产不能看明天；
    两者切换**次数**相同、切换**日期**差 1 日。

不做的事
    不落 ``fact_`` / ``feature_`` 表（阈值仍在校准期，样本外验证要等 2026-09 起的新窗口）；
    不给概率——``proactive`` 附的「之后 5/10 日走法」只列历史事实与样本数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from market_feature_store.market_regime_vectors import FEATURES, load_market_regime_vectors

WINDOW = 5                 # trailing 窗口长度（可用交易日数）
PERCENTILE_LOOKBACK = 250  # 分位阈值的滚动窗口（个窗口，含今日）
MIN_HISTORY = 60           # 分位阈值至少要这么多个窗口；不足则不出簇名
DEBOUNCE_DAYS = 2          # 新簇连续 N 日才算切换

# 四簇名（round 2，用户「你来命名，没有异议」）；顺序即决策表命中顺序。
REGIME_HUGE_ROTATION = "巨量轮动"
REGIME_HIGH_VOLUME_DIVERGENCE = "放量分化"
REGIME_MAINLINE_LED = "主线引领"
REGIME_LOW_VOLUME_BROAD = "缩量普涨"
REGIMES: tuple[str, ...] = (
    REGIME_HUGE_ROTATION,
    REGIME_HIGH_VOLUME_DIVERGENCE,
    REGIME_MAINLINE_LED,
    REGIME_LOW_VOLUME_BROAD,
)

# 规则用到的四个轴（键 = 向量字段名）与展示标签。
AXES: tuple[str, ...] = ("total_amount", "new_high_count", "top1_theme_share", "max_boards")
AXIS_LABELS: dict[str, tuple[str, str]] = {
    "total_amount": ("成交额₅", "亿"),
    "new_high_count": ("新高₅", "家"),
    "top1_theme_share": ("第一题材份额₅", "%"),
    "max_boards": ("最高连板₅", "板"),
}

# 分位阈值——**唯一**一份定义。值 = (轴, 分位数)。
# 分位数由 round 2 冻结的绝对阈值在 277 个 5 日窗口（2025-01-14 ~ 2026-09-02）上反推：
#   amount_huge  26196 亿 → P78    amount_high  22114 亿 → P59
#   new_high_low   464 家 → P36    share_high      29 %  → P50    boards_high  6 板 → P75
# 反推脚本与读数：~/.finance-runtime/experiments/money-effect-20260905/labels_and_quantiles_2026-09-05.md
THRESHOLD_QUANTILES: dict[str, tuple[str, float]] = {
    "amount_huge": ("total_amount", 0.78),
    "amount_high": ("total_amount", 0.59),
    "new_high_low": ("new_high_count", 0.36),
    "share_high": ("top1_theme_share", 0.50),
    "boards_high": ("max_boards", 0.75),
}

# 「可用日」要求非空的维：九维（剔 sh_deviation_pct）。
REQUIRED_FEATURES: tuple[str, ...] = tuple(f for f in FEATURES if f != "sh_deviation_pct")

FORWARD_HORIZONS: tuple[int, ...] = (5, 10)


# ---------------------------------------------------------------------------
# 纯函数层：不碰数据库
# ---------------------------------------------------------------------------


def quantile(values: list[float], q: float) -> float:
    """线性插值分位（与 numpy 默认 ``method='linear'`` 一致），values 非空。"""
    if not values:
        raise ValueError("quantile 需要非空样本")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q 必须在 [0, 1]，得到 {q}")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def available_days(vectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """保留九维全非空的交易日（与实验样本口径一致）。"""
    return [v for v in vectors if all(v.get(f) is not None for f in REQUIRED_FEATURES)]


@dataclass(frozen=True)
class RegimeWindow:
    """一个 trailing 窗口：末日、覆盖的交易日、四轴均值。"""

    trade_date: str
    dates: tuple[str, ...]
    means: dict[str, float]


def trailing_windows(days: list[dict[str, Any]], window: int = WINDOW) -> list[RegimeWindow]:
    out: list[RegimeWindow] = []
    for i in range(window - 1, len(days)):
        chunk = days[i - window + 1 : i + 1]
        means = {axis: sum(float(d[axis]) for d in chunk) / window for axis in AXES}
        out.append(
            RegimeWindow(
                trade_date=str(days[i]["trade_date"]),
                dates=tuple(str(d["trade_date"]) for d in chunk),
                means=means,
            )
        )
    return out


def rolling_thresholds(
    windows: list[RegimeWindow],
    index: int,
    *,
    lookback: int = PERCENTILE_LOOKBACK,
    min_history: int = MIN_HISTORY,
) -> dict[str, float] | None:
    """第 index 个窗口的分位阈值：取 [index-lookback+1, index] 的窗口均值算分位。

    样本不足 min_history 个 → None（调用方据此不出簇名）。
    """
    start = max(0, index - lookback + 1)
    sample = windows[start : index + 1]
    if len(sample) < min_history:
        return None
    thresholds: dict[str, float] = {}
    for key, (axis, q) in THRESHOLD_QUANTILES.items():
        thresholds[key] = quantile([w.means[axis] for w in sample], q)
    return thresholds


def classify(means: dict[str, float], thresholds: dict[str, float]) -> str:
    """4 条决策表，按序命中（round 2 冻结的形状，阈值换成分位）。"""
    amount = means["total_amount"]
    new_high = means["new_high_count"]
    share = means["top1_theme_share"]
    boards = means["max_boards"]
    if amount > thresholds["amount_huge"] and new_high <= thresholds["new_high_low"]:
        return REGIME_HUGE_ROTATION
    if amount > thresholds["amount_high"]:
        return REGIME_HIGH_VOLUME_DIVERGENCE
    if share > thresholds["share_high"] and boards > thresholds["boards_high"]:
        return REGIME_MAINLINE_LED
    return REGIME_LOW_VOLUME_BROAD


def rule_hits(means: dict[str, float], thresholds: dict[str, float]) -> dict[str, bool]:
    """每个阈值比较的命中情况（给日报/CLI 解释「为什么是这个簇」）。"""
    return {
        "amount_huge": means["total_amount"] > thresholds["amount_huge"],
        "amount_high": means["total_amount"] > thresholds["amount_high"],
        "new_high_low": means["new_high_count"] <= thresholds["new_high_low"],
        "share_high": means["top1_theme_share"] > thresholds["share_high"],
        "boards_high": means["max_boards"] > thresholds["boards_high"],
    }


def debounce(raw: list[str | None], days: int = DEBOUNCE_DAYS) -> list[str | None]:
    """因果去抖：只有最近 ``days`` 个原始标签都等于同一个新簇时才切换。

    raw 里的 None（样本不足）原样保留、不参与连续计数；第一个非 None 直接作为初始状态。
    """
    if days < 1:
        raise ValueError(f"去抖天数必须 >= 1，得到 {days}")
    out: list[str | None] = []
    current: str | None = None
    for i, label in enumerate(raw):
        if label is None:
            out.append(None)
            continue
        if current is None:
            current = label
        elif label != current:
            recent = raw[max(0, i - days + 1) : i + 1]
            if len(recent) == days and all(r == label for r in recent):
                current = label
        out.append(current)
    return out


@dataclass(frozen=True)
class RegimeDay:
    trade_date: str
    window_dates: tuple[str, ...]
    means: dict[str, float]
    thresholds: dict[str, float] | None
    lookback_windows: int
    raw_regime: str | None
    regime: str | None
    prev_regime: str | None
    switched: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "window_dates": list(self.window_dates),
            "means": dict(self.means),
            "thresholds": dict(self.thresholds) if self.thresholds is not None else None,
            "lookback_windows": self.lookback_windows,
            "raw_regime": self.raw_regime,
            "regime": self.regime,
            "prev_regime": self.prev_regime,
            "switched": self.switched,
        }


def compute_regime_series(
    vectors: list[dict[str, Any]],
    *,
    window: int = WINDOW,
    lookback: int = PERCENTILE_LOOKBACK,
    min_history: int = MIN_HISTORY,
    debounce_days: int = DEBOUNCE_DAYS,
) -> list[RegimeDay]:
    """整段历史的逐日 regime。每一天只用它之前（含）的数据，所以整段一次算完
    与逐日 ``as_of`` 截断后各算一次结果相同（测试守着这条）。"""
    days = available_days(vectors)
    windows = trailing_windows(days, window)
    raw: list[str | None] = []
    thresholds_by_index: list[dict[str, float] | None] = []
    lookback_n: list[int] = []
    for i, w in enumerate(windows):
        thr = rolling_thresholds(windows, i, lookback=lookback, min_history=min_history)
        thresholds_by_index.append(thr)
        lookback_n.append(min(i + 1, lookback))
        raw.append(classify(w.means, thr) if thr is not None else None)
    committed = debounce(raw, debounce_days)
    series: list[RegimeDay] = []
    prev: str | None = None
    for i, w in enumerate(windows):
        regime = committed[i]
        switched = regime is not None and prev is not None and regime != prev
        series.append(
            RegimeDay(
                trade_date=w.trade_date,
                window_dates=w.dates,
                means=w.means,
                thresholds=thresholds_by_index[i],
                lookback_windows=lookback_n[i],
                raw_regime=raw[i],
                regime=regime,
                prev_regime=prev,
                switched=switched,
            )
        )
        if regime is not None:
            prev = regime
    return series


def _cumulative_index_return(days: list[dict[str, Any]], start: int, horizon: int) -> float | None:
    """days[start+1 .. start+horizon] 的上证累计涨跌（%）；不够 horizon 天 → None。"""
    if start + horizon >= len(days):
        return None
    growth = 1.0
    for d in days[start + 1 : start + horizon + 1]:
        pct = d.get("sh_index_pct_chg")
        if pct is None:
            return None
        growth *= 1.0 + float(pct) / 100.0
    return (growth - 1.0) * 100.0


def forward_facts_by_regime(
    series: list[RegimeDay],
    vectors: list[dict[str, Any]],
    *,
    before_index: int | None = None,
    horizons: tuple[int, ...] = FORWARD_HORIZONS,
) -> dict[str, dict[str, Any]]:
    """每个簇「历史上进入之后」的事实走法：以切换日为起点的上证累计涨跌分布。

    只统计 ``before_index`` 之前的切换日（默认全部），只列 n / 中位 / p25 / p75 / 为正次数，
    不给概率。用切换日而不是簇内每一天，是为了避免重叠窗口把 n 虚增。
    """
    days = available_days(vectors)
    day_index = {str(d["trade_date"]): i for i, d in enumerate(days)}
    limit = len(series) if before_index is None else before_index
    facts: dict[str, dict[str, Any]] = {}
    for i in range(limit):
        rd = series[i]
        if not rd.switched or rd.regime is None:
            continue
        entry = facts.setdefault(rd.regime, {"entries": 0, "horizons": {h: [] for h in horizons}})
        entry["entries"] += 1
        start = day_index[rd.trade_date]
        for h in horizons:
            ret = _cumulative_index_return(days, start, h)
            if ret is not None:
                entry["horizons"][h].append(ret)
    out: dict[str, dict[str, Any]] = {}
    for regime, entry in facts.items():
        summary: dict[str, Any] = {"entries": entry["entries"], "horizons": {}}
        for h, rets in entry["horizons"].items():
            if not rets:
                summary["horizons"][str(h)] = None
                continue
            summary["horizons"][str(h)] = {
                "n": len(rets),
                "median_pct": round(quantile(rets, 0.5), 2),
                "p25_pct": round(quantile(rets, 0.25), 2),
                "p75_pct": round(quantile(rets, 0.75), 2),
                "positive": sum(1 for r in rets if r > 0),
            }
        out[regime] = summary
    return out


def replay(
    series: list[RegimeDay],
    cluster_labels: dict[str, str] | None = None,
    *,
    since: str | None = None,
) -> dict[str, Any]:
    """回放统计：覆盖窗口数、去抖前/后切换次数、（有簇标签时）一致率与混淆矩阵。"""
    rows = [rd for rd in series if rd.regime is not None and (since is None or rd.trade_date >= since)]
    raw_switches = sum(
        1 for a, b in zip(rows, rows[1:]) if a.raw_regime is not None and b.raw_regime != a.raw_regime
    )
    committed_switches = sum(1 for rd in rows[1:] if rd.switched)
    runs: list[list[Any]] = []
    for rd in rows:
        if runs and runs[-1][0] == rd.regime:
            runs[-1][1] += 1
        else:
            runs.append([rd.regime, 1])
    run_lengths = [float(n) for _, n in runs]
    result: dict[str, Any] = {
        "since": since,
        "windows": len(rows),
        "first_date": rows[0].trade_date if rows else None,
        "last_date": rows[-1].trade_date if rows else None,
        "raw_switches": raw_switches,
        "switches": committed_switches,
        "windows_per_switch": round(len(rows) / committed_switches, 1) if committed_switches else None,
        "median_run": quantile(run_lengths, 0.5) if run_lengths else None,
        "regime_counts": {r: sum(1 for rd in rows if rd.regime == r) for r in REGIMES},
    }
    if cluster_labels:
        paired = [(rd, cluster_labels[rd.trade_date]) for rd in rows if rd.trade_date in cluster_labels]
        agree_raw = sum(1 for rd, c in paired if rd.raw_regime == c)
        agree = sum(1 for rd, c in paired if rd.regime == c)
        confusion = {c: {r: 0 for r in REGIMES} for c in REGIMES}
        for rd, c in paired:
            if c in confusion and rd.raw_regime in confusion[c]:
                confusion[c][rd.raw_regime] += 1
        result["cluster_comparison"] = {
            "paired_windows": len(paired),
            "agreement_raw": round(agree_raw / len(paired), 3) if paired else None,
            "agreement_debounced": round(agree / len(paired), 3) if paired else None,
            "confusion_cluster_rows_rule_cols": confusion,
        }
    return result


# ---------------------------------------------------------------------------
# 取数装配层
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegimeState:
    """某一日的赚钱效应状态（日报 / CLI 消费的形状）。"""

    available: bool
    reason: str | None
    today: RegimeDay | None
    forward_facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "today": self.today.to_dict() if self.today else None,
            "run_length": self.run_length,
            "forward_facts": self.forward_facts,
            "parameters": {
                "window": WINDOW,
                "percentile_lookback": PERCENTILE_LOOKBACK,
                "min_history": MIN_HISTORY,
                "debounce_days": DEBOUNCE_DAYS,
                "threshold_quantiles": {k: {"axis": a, "q": q} for k, (a, q) in THRESHOLD_QUANTILES.items()},
            },
        }


def _unavailable(reason: str) -> RegimeState:
    return RegimeState(available=False, reason=reason, today=None)


def regime_state_from_vectors(vectors: list[dict[str, Any]], missing: list[str]) -> RegimeState:
    """从（已按 as_of 截断的）向量算「最后一天」的状态。"""
    missing_required = [f for f in missing if f in REQUIRED_FEATURES]
    if missing_required:
        return _unavailable(f"情绪向量缺维（辅表不可读）：{', '.join(missing_required)}")
    series = compute_regime_series(vectors)
    if not series:
        return _unavailable(f"可用交易日不足 {WINDOW} 天，无法构成窗口")
    today = series[-1]
    if today.regime is None:
        return _unavailable(
            f"分位阈值样本不足：可用窗口 {len(series)} 个 < MIN_HISTORY {MIN_HISTORY}"
        )
    run_length = 0
    for rd in reversed(series):
        if rd.regime != today.regime:
            break
        run_length += 1
    facts = forward_facts_by_regime(series, vectors, before_index=len(series) - 1)
    return RegimeState(available=True, reason=None, today=today, forward_facts=facts, run_length=run_length)


def load_regime_state(con: Any, as_of: str | None = None) -> RegimeState:
    """只读连接 → as_of（默认库内最新日）的赚钱效应状态。"""
    vectors, missing = load_market_regime_vectors(con, as_of=as_of)
    if not vectors:
        return _unavailable("fact_market_daily 无数据或不可读")
    return regime_state_from_vectors(vectors, missing)


# ---------------------------------------------------------------------------
# 文本渲染（CLI 与日报共用的措辞）
# ---------------------------------------------------------------------------


def format_axis_value(axis: str, value: float) -> str:
    label, unit = AXIS_LABELS[axis]
    if axis == "total_amount":
        return f"{label} {value:,.0f} {unit}"
    if axis == "max_boards":
        return f"{label} {value:.1f} {unit}"
    return f"{label} {value:.0f} {unit}"


def axis_rows(day: RegimeDay) -> list[list[str]]:
    """日报表格行：轴 / 5 日均值 / 阈值（分位）/ 命中。"""
    assert day.thresholds is not None
    hits = rule_hits(day.means, day.thresholds)
    rows: list[list[str]] = []
    for key, (axis, q) in THRESHOLD_QUANTILES.items():
        label, unit = AXIS_LABELS[axis]
        value = day.means[axis]
        thr = day.thresholds[key]
        op = "≤" if key == "new_high_low" else ">"
        fmt = "{:,.0f}" if axis == "total_amount" else ("{:.1f}" if axis == "max_boards" else "{:.0f}")
        rows.append([
            f"{label}（{key}）",
            f"{fmt.format(value)} {unit}",
            f"{op} P{int(round(q * 100))} = {fmt.format(thr)} {unit}",
            "命中" if hits[key] else "未命中",
        ])
    return rows


def forward_facts_text(regime: str, facts: dict[str, dict[str, Any]]) -> str:
    entry = facts.get(regime)
    if not entry or not entry.get("entries"):
        return f"历史上此前没有进入「{regime}」的切换记录，无事实走法可列。"
    parts: list[str] = []
    for h in FORWARD_HORIZONS:
        s = entry["horizons"].get(str(h))
        if not s:
            continue
        parts.append(
            f"{h} 日上证累计中位 {s['median_pct']:+.2f}%（p25 {s['p25_pct']:+.2f}% / p75 {s['p75_pct']:+.2f}%），"
            f"{s['n']} 次里 {s['positive']} 次为正"
        )
    body = "；".join(parts) if parts else "样本不足以算任一窗口"
    return f"历史上进入「{regime}」{entry['entries']} 次，之后 {body}——只列事实，不是概率。"


def one_line(state: RegimeState) -> str:
    """非切换日的一行摘要。"""
    if not state.available or state.today is None:
        return f"赚钱效应状态：不可用（{state.reason}）"
    d = state.today
    axes = "、".join(format_axis_value(a, d.means[a]) for a in AXES)
    return (
        f"赚钱效应状态：**{d.regime}**（连续第 {state.run_length} 个窗口；{axes}；"
        f"规则阈值为近 {d.lookback_windows} 个窗口的分位，D 档本地派生）"
    )


def switch_headline(state: RegimeState) -> str | None:
    if not state.available or state.today is None or not state.today.switched:
        return None
    d = state.today
    return f"⚠ 赚钱效应状态切换：{d.prev_regime} → **{d.regime}**（新簇连续第 {DEBOUNCE_DAYS} 日确认）"
