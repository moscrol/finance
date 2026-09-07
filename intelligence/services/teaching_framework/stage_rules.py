"""Eight-stage scoring: founder turning points as entry evidence, reference-calibrated common ranges as continuing evidence.

Slice 1.5 (用户 2026-09-07 第九 / 十段).  The stage vocabulary is the platform's eight inner
stages (复盘会 ``cycle_stage``; 「承接盘反复是高位震荡，2.0 是升级」).  A stage no longer
follows the side of the weekly MA: the platform's stages are multi-week phases separated by
volume level, breadth and gain, so continuing evidence is 「this view's value sits inside the
stage's common range」, with the ranges read off the platform's daily labels over a
calibration period and written into the versioned parameter file (``stage_bands``).  Entry
evidence stays the founder's own turning points (first cross below, oversold, retest cross
below, breakout with volume, overheated).  The transition graph is likewise the set of
stage-to-stage moves observed in the platform sequence (``transition_graph``), self-loops
implied.  Counting views, ties broken by the graph, no guessing — unchanged from slice 1.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

STAGES = (
    "左底向下",
    "左底向上",
    "二次探底",
    "缩量右底",
    "共建主线",
    "主流主升",
    "主流主升2.0",
    "高位震荡",
)
# 周期的下半场：从这四段进入共建主线才算 turn_up。
BOTTOM_STAGES = ("左底向下", "左底向上", "二次探底", "缩量右底")

# 复盘会内层阶段 → 本框架八段。除「承接盘反复 = 高位震荡」（创始人 09-07 第十段）外同名。
REFERENCE_STAGE_ALIASES: dict[str, str] = {stage: stage for stage in STAGES}
REFERENCE_STAGE_ALIASES["承接盘反复"] = "高位震荡"

# Stage-to-stage moves observed in the platform sequence 2024-11-15 → 2025-10-31 (the default
# calibration period); ``calibrate-stages`` rewrites this from the reference table and the
# parameter file wins whenever it carries ``transition_graph``.
DEFAULT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "左底向下": ("左底向上", "二次探底"),
    "左底向上": ("二次探底",),
    "二次探底": ("缩量右底", "共建主线"),
    "缩量右底": ("共建主线",),
    "共建主线": ("主流主升", "左底向下"),
    "主流主升": ("高位震荡",),
    "主流主升2.0": ("高位震荡", "左底向下"),
    "高位震荡": ("主流主升2.0", "左底向下"),
}

# Views whose value is tested against each stage's common range.  Keys are flag names as
# they appear in the per-day record (``src.`` values included); names are the founder's
# words for the receipt.  用户第十段：量能 = 20 日量能比；水位 = 个股相对 MA 偏离度的中位数；
# 第四 / 七段：区间涨幅 = 腿；第六段：偏离度水平与走向；平台四维里的「情绪」= 上涨比例。
BAND_VIEWS: tuple[tuple[str, str], ...] = (
    ("amount_vs_ma20_pct", "量能比"),
    ("stock_ma10_deviation_median", "水位·个股MA10偏离度中位"),
    ("stock_up_ratio_ma5_pct", "情绪·5日上涨比例"),
    ("sh_index_pct_chg_10d", "10日涨幅"),
    ("ma_episode_pct_chg", "本腿涨幅"),
    ("src.sh_deviation_pct", "周均线偏离度"),
    # 第二刀（第六段「一体两面」）：板块侧的市场级视角。顶部横盘与底部横盘在指数视角上分不开，
    # 在 1 年以上新高家数上分得开（平台八段：高位震荡 131–217 vs 缩量右底 65–122 / 左底向下 47–76）。
    # 双红题材数与 ≥3 涨停题材数只作视角写出：区间太宽（高位震荡 1–14、共建主线 2–25），进等权
    # 隶属计分后训练期升、验证期降（35.3% → 28.1%），按「前半段选、后半段验」不进。
    ("new_high_1y_count", "宽度·1年以上新高家数"),
    # 第五段「周均线下方赚钱效应不在成交占比前三」：5 日涨幅前 10 板块在前三申万之外的比例。
    # 平台八段上 左底向下 / 缩量右底 0.70 → 共建主线 0.40（主线成形 = 赚钱的与量板块重合）。
    ("rps5_outside_top3_pct", "赚钱效应·5日涨幅前10在前三申万之外的比例"),
)

ENTRY_PREDICATES: dict[str, tuple[str, ...]] = {
    "左底向下": ("E:first_cross_below",),
    "左底向上": ("E:oversold",),
    "二次探底": ("E:retest_cross_below",),
    "缩量右底": (),
    "共建主线": ("E:breakout_volume_within_window",),
    "主流主升": (),
    "主流主升2.0": (),
    "高位震荡": ("E:overheated",),
}

# Continuing predicates that are founder sentences rather than calibrated bands.
# 第六段：「缩量右底是下穿后反弹到周均线那一段，然后又回踩探底」+ 第三轮「二次探底会有个
# 缩量的过程」→ 回踩下穿之后、周期未被放量突破结束之前的缩量日。
CONTINUING_PREDICATES: dict[str, tuple[str, ...]] = {
    "缩量右底": ("H:shrink_after_retest",),
}

# No predicate is an agent invention any more: entries are founder sentences, continuing
# evidence is calibrated on the founder's platform labels and carries its provenance in the
# parameter file.  Kept (empty) so receipts keep the field.
FOUNDER_UNCONFIRMED: tuple[str, ...] = ()


def graph_from_params(params: Mapping[str, Any] | None) -> dict[str, tuple[str, ...]]:
    """Directed graph with self-loops first: parameter file's ``transition_graph`` or the default."""
    raw = (params or {}).get("transition_graph") or DEFAULT_TRANSITIONS
    graph: dict[str, tuple[str, ...]] = {}
    for stage in STAGES:
        targets = tuple(t for t in raw.get(stage, ()) if t in STAGES)
        graph[stage] = tuple(dict.fromkeys((stage,) + targets))
    return graph


def transition_graph(params: Mapping[str, Any] | None = None) -> dict[str, list[str]]:
    """Return the complete directed graph (self-loops included) for receipts."""
    return {stage: list(targets) for stage, targets in graph_from_params(params).items()}


def stage_bands(params: Mapping[str, Any] | None) -> dict[str, dict[str, tuple[float, float]]]:
    """``{stage: {view: (lo, hi)}}`` from the parameter file; stages or views without a band score no H."""
    raw = (params or {}).get("stage_bands") or {}
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for stage in STAGES:
        bands = raw.get(stage) or {}
        out[stage] = {
            view: (float(lo), float(hi))
            for view, (lo, hi) in ((v, tuple(b)) for v, b in bands.items() if isinstance(b, (list, tuple)) and len(b) == 2)
            if view in dict(BAND_VIEWS)
        }
    return out


def stage_predicates(params: Mapping[str, Any] | None = None) -> dict[str, tuple[str, ...]]:
    """Every predicate each stage can score on: the denominator of the confidence tier."""
    bands = stage_bands(params)
    return {
        stage: ENTRY_PREDICATES[stage]
        + CONTINUING_PREDICATES.get(stage, ())
        + tuple(f"H:in_band:{view}" for view in bands[stage])
        for stage in STAGES
    }


def confidence(
    coarse: str, scores: Mapping[str, int], hits: list[tuple[str, str]], params: Mapping[str, Any] | None = None
) -> dict[str, Any] | None:
    """Confidence tier for the resolved stage: fired / possible views, what is missing, margin.

    ``margin`` is the winner's score minus the runner-up's; ``1`` means a single
    view separated them, ``0`` means the tie was broken by yesterday's stage.
    """
    catalog = stage_predicates(params)
    if coarse not in catalog:
        return None
    fired = [pid for stage, pid in hits if stage == coarse]
    possible = catalog[coarse]
    others = [n for s, n in scores.items() if s != coarse]
    runner_up = max(others) if others else 0
    return {
        "stage": coarse,
        "hits": len(fired),
        "possible": len(possible),
        "missing": [pid for pid in possible if pid not in fired],
        "margin": int(scores.get(coarse, 0)) - int(runner_up),
    }


def predicate_hits(
    f: Mapping[str, Any], params: Mapping[str, Any] | None = None, origin: str | None = None
) -> list[tuple[str, str]]:
    """Return ``(stage, predicate_id)`` for every entry / continuing predicate that fires today.

    Unknown (NULL) inputs never fire.  Predicate ids are stable strings so the
    receipt can count them; the scoring is one point per hit.  ``origin`` is the
    last valid stage (the 来源状态): the breakout entry of 共建主线 only counts when
    the market is coming out of the bottom half of the cycle — 第六段流程 puts
    放量上穿 at the end of 下穿 → 探底 → 反弹 → 回踩, not inside a top range where
    the index crosses the 5-day MA every few days.
    """

    def v(k: str) -> Any:
        return f.get(k)

    hits: list[tuple[str, str]] = []
    # 进入证据：创始人的转点原话。
    # 第六段「左底向下是第一次从周均线下穿」+ 09-06 第三轮「放量跌破周均或者跳空低开跌破周均基本
    # 就是要开始向下继续调整了」：第一次下穿还要带量或跳空，顶部区间里缩量的普通下穿不算。
    if v("cross_below_kind") == "first" and (v("volume_expanding") is True or v("gap_down_open") is True):
        hits.append(("左底向下", "E:first_cross_below"))
    if v("cross_below_kind") == "retest":
        hits.append(("二次探底", "E:retest_cross_below"))
    # 词表「偏离度接近 −2.5 更容易进入左底向上」；「接近 +1.5 更容易进入高位震荡」。
    if v("deviation_band") == "oversold":
        hits.append(("左底向上", "E:oversold"))
    if v("deviation_band") == "overheated":
        hits.append(("高位震荡", "E:overheated"))
    # 第七段「上穿要配合放量……或者上穿后三天内放量」；放量 = 量能比 ≥ 100（第十段尺子）。
    confirm_days = int((params or {}).get("breakout_confirm_days", 3))
    since_cross = v("days_since_cross_above")
    in_window = isinstance(since_cross, (int, float)) and since_cross <= confirm_days
    from_bottom = origin is None or origin in BOTTOM_STAGES
    if from_bottom and in_window and v("volume_expanding") is True and v("above_week_ma") is True:
        hits.append(("共建主线", "E:breakout_volume_within_window"))
    # 第六段流程：回踩下穿之后（周期仍在）、放量突破之前的缩量日 = 缩量右底的「缩量的过程」。
    if v("below_ma_cycle_retest_seen") is True and v("volume_band") == "shrink":
        hits.append(("缩量右底", "H:shrink_after_retest"))
    # 持续证据：视角值落在该段的共性区间内（区间从平台参照标注的校准期算出，见参数文件）。
    for stage, bands in stage_bands(params).items():
        for view, (lo, hi) in bands.items():
            value = v(view)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if lo <= float(value) <= hi:
                hits.append((stage, f"H:in_band:{view}"))
    return hits


def score_flags(
    f: Mapping[str, Any], params: Mapping[str, Any] | None = None, origin: str | None = None
) -> dict[str, int]:
    scores = {s: 0 for s in STAGES}
    for stage, _ in predicate_hits(f, params, origin):
        scores[stage] += 1
    return scores


def eligible_stages(
    previous: str | None, entered: Iterable[str] = (), params: Mapping[str, Any] | None = None
) -> list[str]:
    """Stages allowed to win today: those reachable from yesterday's stage, plus any with an entry event.

    词表「指数阶段判定必须回答……从什么来源状态演变而来」：a phase does not jump to a
    non-adjacent phase without a turning point.  With no valid yesterday (first day, gap,
    ambiguous) every stage is eligible — the chain is broken and origin is unknown.
    """
    graph = graph_from_params(params)
    if previous not in graph:
        return list(STAGES)
    allowed = set(graph[previous]) | {s for s in entered if s in STAGES}
    return [s for s in STAGES if s in allowed]


def resolve_stage(
    scores: Mapping[str, int],
    previous: str | None,
    params: Mapping[str, Any] | None = None,
    entered: Iterable[str] = (),
) -> tuple[str, str, list[str]]:
    """Argmax over the eligible stages; ties broken by reachability; no guessing.

    ``resolution`` is ``argmax`` (unique top among eligible, reachable or no yesterday),
    ``entry`` (unique top that is only eligible through its entry event), ``graph``
    (tie broken because exactly one tied stage is reachable), ``ambiguous`` or
    ``no_evidence`` (no eligible stage scored — a non-eligible stage scoring does not
    count, that would be a jump without a turning point).
    """
    graph = graph_from_params(params)
    eligible = eligible_stages(previous, entered, params)
    entered = {s for s in entered if s in STAGES}
    # Hysteresis (创始人：流程是「大致的」，中间有「数据的残差」): leaving the current stage on
    # band evidence alone needs a lead of ``stage_switch_margin`` points over it; a stage
    # entered by a turning point is exempt.  1 = plain argmax.
    switch_margin = max(1, int((params or {}).get("stage_switch_margin", 1)))
    hold = scores.get(previous, 0) if previous in graph else None
    if hold is not None and switch_margin > 1:
        eligible = [
            s for s in eligible
            if s == previous or s in entered or scores.get(s, 0) >= hold + switch_margin
        ]
    top = max((scores.get(s, 0) for s in eligible), default=0)
    if top == 0:
        return "no_evidence", "no_evidence", []
    tied = sorted(s for s in eligible if scores.get(s, 0) == top)
    reachable = [s for s in tied if previous in graph and s in graph[previous]]
    if len(tied) == 1:
        winner = tied[0]
        return winner, ("entry" if previous in graph and winner not in graph[previous] else "argmax"), tied
    if len(reachable) == 1:
        return reachable[0], "graph", tied
    return "ambiguous", "ambiguous", tied


def stage_fine(
    coarse: str,
    flags: Mapping[str, Any],
    previous: str | None = None,
    params: Mapping[str, Any] | None = None,
) -> str:
    """Fine stage: the eight stages are already the platform's inner vocabulary; 见顶 marks the entry day of 高位震荡."""
    if coarse not in STAGES:
        return "unassigned"
    if coarse == "高位震荡" and previous != coarse:
        return "见顶"
    return coarse


def derive_turns(sequence: list[str | None]) -> list[dict[str, int]]:
    """Emit turn events for entries from the last valid coarse stage.

    Ambiguous / no-evidence days keep the origin (``ambiguity_memory =
    last_valid_stage``: the phase did not end, we just could not read it that
    day); a gap day (``None``) breaks the chain, and the next valid stage after
    it is a re-entry with unknown origin, not a turn.  A repeated stage after
    ambiguity is persistence, not a turn.
    """
    out = []
    origin: str | None = None
    for stage in sequence:
        valid = stage in STAGES
        from_valid = origin in STAGES and origin != stage
        out.append(
            {
                "turn_up": int(valid and stage == "共建主线" and origin in BOTTOM_STAGES),
                "turn_top": int(valid and from_valid and stage == "高位震荡"),
                "turn_down": int(valid and from_valid and stage == "左底向下"),
            }
        )
        if valid:
            origin = stage
        elif stage is None:
            origin = None
    return out
