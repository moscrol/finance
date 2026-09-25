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

from typing import Any, Callable, Iterable, Mapping

# 第二十一段（09-08）：二次探底与缩量右底「应该是一个东西」——赚钱/亏钱效应上两两 η² 只有 0.060，与主升 vs 2.0 同级。
# stage_coarse 七段；二次探底降为 stage_fine（回踩下穿当日）。平台仍可能标「二次探底」，折到缩量右底。
STAGES = (
    "左底向下",
    "左底向上",
    "缩量右底",
    "共建主线",
    "主流主升",
    "主流主升2.0",
    "高位震荡",
)
# 周期的下半场：从这三段进入共建主线才算 turn_up。
BOTTOM_STAGES = ("左底向下", "左底向上", "缩量右底")

# 复盘会内层阶段 → 本框架粗段。承接盘反复 = 高位震荡（第十段）；二次探底 = 缩量右底（第二十一段）。
REFERENCE_STAGE_ALIASES: dict[str, str] = {stage: stage for stage in STAGES}
REFERENCE_STAGE_ALIASES["承接盘反复"] = "高位震荡"
REFERENCE_STAGE_ALIASES["二次探底"] = "缩量右底"

# Stage-to-stage moves observed in the platform sequence 2024-11-15 → 2025-10-31 (the default
# calibration period); ``calibrate-stages`` rewrites this from the reference table and the
# parameter file wins whenever it carries ``transition_graph``.
DEFAULT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "左底向下": ("左底向上", "缩量右底"),
    "左底向上": ("缩量右底",),
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
    # 题材层第二轮「先量再建」：承接 = 昨日涨停股今日平均涨幅的 5 日均值（平台「承接盘反复」的字面对象；
    # 平台八段中位 主流主升2.0 2.65 / 主流主升 2.33 > 承接盘反复 1.90 / 共建主线 1.87 > 二次探底 1.58 /
    # 缩量右底 1.25 / 左底向下 1.19）。同时试过的 负溢价天数 / 正负翻转次数 / 双红申万一级数 / 涨停领涨集合
    # 持续度 只作视角写出：单独或合并进带区都是训练期升、验证期降（详见 slice2 spec §6）。
    ("limit_premium_ma5_pct", "承接·昨日涨停股今日均涨幅5日均值"),
)

ENTRY_PREDICATES: dict[str, tuple[str, ...]] = {
    "左底向下": ("E:first_cross_below",),
    "左底向上": ("E:oversold",),
    # 第二十一段：回踩下穿是缩量右底（粗段）的进入；当日 fine = 二次探底。
    "缩量右底": ("E:retest_cross_below",),
    "共建主线": ("E:breakout_volume_within_window",),
    # 第十九段（09-08）「共建主线到主流主升，就是成交占比不断放大，量能也逐步放大的过程……不是按日期来看，单日可能小缩量」：
    # 来源是共建主线、成交占比前三的 n 日均在升、成交额的 n 日均在升（窗口均值比窗口均值，单日缩量不翻它）。
    "主流主升": ("E:share_and_volume_trend_up",),
    # 第十一段「升级 2.0，大概率是进一步放量指数进一步走强」：高位震荡（承接盘反复）之后的双量日 + 指数新高。
    # 第二十一段「2.0 也是看一段」：过程口径（upgrade_entry_mode / upgrade_process_continuing）是参数可选项，默认仍是单日。
    "主流主升2.0": ("E:upgrade_double_volume_new_high",),
    "高位震荡": ("E:overheated",),
}

UPGRADE_ORIGIN = "高位震荡"  # 平台序列里 2.0 三次都紧跟承接盘反复；第一腿从底部起的新高不算升级
MAIN_RISE_ORIGIN = "共建主线"  # 第十九段：主流主升是从共建主线升级上来的过程
DEFAULT_UPGRADE_NEW_HIGH_WINDOW = 20

# 创始人的结构性硬条件（A 类，不是校准出来的）：某段只能在满足它时得分。第十九段：「缩量右底是在周均线的下方」。
STAGE_GATES: dict[str, Callable[[Callable[[str], Any]], bool]] = {
    "缩量右底": lambda v: v("above_week_ma") is False,
}

# 左底向下进入口径（参数 ``left_down_entry``）：``persist_days`` = 首次下穿后第几天起算（1 = 下穿当天），
# ``volume`` = 当日量能条件：expanding_or_gap（09-06 第三轮「放量跌破或跳空低开跌破」）/ shrink（平台起点
# 的形状：缩量）/ any。哪一组是 B 类候选，按训练期选、验证期验。
LEFT_DOWN_VOLUME_RULES = ("expanding_or_gap", "shrink", "shrink_or_gap", "any")
# ``gap_through_ma_day1``（可选，缺省 False）：第十三段「印象中跳空低开跌破周均的，后续往往指数是继续向下」——
# 首次下穿当天开盘就已在周均线之下（缺口穿过周均）时，不等 persist_days、不看量能，当天就算进入。
# 真库（09-07，固定快照）：16 次这样的下穿 20 日后 64% 收在下方（全部交易日基准 36%），但作进入证据时一致率
# 训练期持平 50.5、验证期 40.0 → 39.1，多判的 4 天平台都不叫左底向下，所以只作可选项，不是默认。
DEFAULT_LEFT_DOWN_ENTRY = {"persist_days": 1, "volume": "expanding_or_gap", "gap_through_ma_day1": False}


def left_down_entry(params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = (params or {}).get("left_down_entry") or {}
    return {
        "persist_days": int(raw.get("persist_days", DEFAULT_LEFT_DOWN_ENTRY["persist_days"])),
        "volume": str(raw.get("volume", DEFAULT_LEFT_DOWN_ENTRY["volume"])),
        "gap_through_ma_day1": bool(raw.get("gap_through_ma_day1", DEFAULT_LEFT_DOWN_ENTRY["gap_through_ma_day1"])),
    }


def _left_down_volume_ok(v: Callable[[str], Any], rule: str) -> bool:
    if rule == "expanding_or_gap":
        return v("volume_expanding") is True or v("gap_down_open") is True
    if rule == "shrink":
        return v("volume_band") == "shrink"
    if rule == "shrink_or_gap":
        return v("volume_band") == "shrink" or v("gap_down_open") is True
    return rule == "any"

# Continuing predicates that are founder sentences rather than calibrated bands.
# 第六段：「缩量右底是下穿后反弹到周均线那一段，然后又回踩探底」+ 第三轮「二次探底会有个
# 缩量的过程」→ 回踩下穿之后、周期未被放量突破结束之前的缩量日。
CONTINUING_PREDICATES: dict[str, tuple[str, ...]] = {
    "缩量右底": ("H:shrink_after_retest",),
    # 第十九段：主流主升是「成交占比不断放大、量能逐步放大的过程」——过程在持续，就是这一段的持续证据。
    "主流主升": ("H:share_and_volume_trend_up",),
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
    extra: dict[str, tuple[str, ...]] = {}
    if (params or {}).get("upgrade_process_continuing"):
        extra["主流主升2.0"] = ("H:share_and_volume_trend_up",)
    return {
        stage: ENTRY_PREDICATES[stage]
        + CONTINUING_PREDICATES.get(stage, ())
        + extra.get(stage, ())
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
    # 第六段「左底向下是第一次从周均线下穿」。创始人第十二段：定义不精确、结合特征值定——平台的左底向下
    # 在下穿后第 2–3 天、缩量（量能比 84–97）时才开始，高位横盘里带量的短促下穿（中位 2.5 天就收回）不算。
    # 落法：首次下穿周期（未见回踩）的第 persist_days 天起、仍在周均线下方、量能满足 volume 口径的每一天都算进入。
    entry = left_down_entry(params)
    cycle_day = v("below_ma_cycle_day")
    in_first_phase = (
        isinstance(cycle_day, (int, float)) and cycle_day >= entry["persist_days"]
        and v("below_ma_cycle_retest_seen") is False and v("above_week_ma") is False
    )
    gap_through_ma = (
        entry["gap_through_ma_day1"] and v("cross_below_kind") == "first" and v("open_below_week_ma") is True
        and v("above_week_ma") is False
    )
    if (in_first_phase and _left_down_volume_ok(v, entry["volume"])) or gap_through_ma:
        hits.append(("左底向下", "E:first_cross_below"))
    if v("cross_below_kind") == "retest":
        hits.append(("缩量右底", "E:retest_cross_below"))
    # 词表「偏离度接近 −2.5 更容易进入左底向上」；「接近 +1.5 更容易进入高位震荡」。
    if v("deviation_band") == "oversold":
        hits.append(("左底向上", "E:oversold"))
    if v("deviation_band") == "overheated":
        hits.append(("高位震荡", "E:overheated"))
    # 第七段「上穿要配合放量……或者上穿后三天内放量」；放量 = 量能比 ≥ 100（第十段尺子）。
    # 来源限制是 B 类候选（参数 breakout_entry_origin）：bottom = 只从周期下半场来算（第六段流程的读法）；
    # any = 顶部横盘里的放量上穿也算（创始人 09-08 第二十段「应该是算的」，让数据定）。
    confirm_days = int((params or {}).get("breakout_confirm_days", 3))
    since_cross = v("days_since_cross_above")
    in_window = isinstance(since_cross, (int, float)) and since_cross <= confirm_days
    origin_policy = str((params or {}).get("breakout_entry_origin", "bottom"))
    from_bottom = origin_policy == "any" or origin is None or origin in BOTTOM_STAGES
    if from_bottom and in_window and v("volume_expanding") is True and v("above_week_ma") is True:
        hits.append(("共建主线", "E:breakout_volume_within_window"))
    # 第十一段「升级 2.0，大概率是进一步放量指数进一步走强」：来源是高位震荡（承接盘反复），当日是双量日
    # （每日复盘口径：环比 > 10% 且量能比 > 120），且收盘创前 n 日新高；n 是 B 类候选（upgrade_new_high_window）。
    upgrade_window = int((params or {}).get("upgrade_new_high_window", DEFAULT_UPGRADE_NEW_HIGH_WINDOW))
    trend_up = v("mainline_share_trend_up") is True and v("volume_trend_up") is True
    new_high = v(f"index_new_high_{upgrade_window}d") is True
    # 2.0 的起点（第二十一段「2.0 也是看一段吧」，B 类候选 upgrade_entry_mode）：day = 双量日 + 新高那一天（第十一段原话的
    # 单日读法）；process = 成交占比与量能的窗口均值都在升 + 新高（看一段）；either = 两者任一。来源都必须是高位震荡。
    upgrade_mode = str((params or {}).get("upgrade_entry_mode", "day"))
    day_trigger = v("double_volume_day") is True and new_high
    process_trigger = trend_up and new_high
    if origin == UPGRADE_ORIGIN and (
        (upgrade_mode == "day" and day_trigger) or (upgrade_mode == "process" and process_trigger)
        or (upgrade_mode == "either" and (day_trigger or process_trigger))
    ):
        hits.append(("主流主升2.0", "E:upgrade_double_volume_new_high"))
    # 「升级往往伴随放量和主流板块的放量」（第十九段）：过程在持续也是 2.0 的持续证据（参数 upgrade_process_continuing）。
    if trend_up and (params or {}).get("upgrade_process_continuing"):
        hits.append(("主流主升2.0", "H:share_and_volume_trend_up"))
    # 第十九段：成交占比与量能的 n 日均都在升（过程，不是单日）。从共建主线来算进入；已在主升里算持续。
    if trend_up and origin == MAIN_RISE_ORIGIN:
        hits.append(("主流主升", "E:share_and_volume_trend_up"))
    if trend_up:
        hits.append(("主流主升", "H:share_and_volume_trend_up"))
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
    # 创始人的结构性硬条件：不满足的段今天一分都不得（第十九段：缩量右底在周均线下方）。
    gated = {stage for stage, gate in STAGE_GATES.items() if not gate(v)}
    # 对照口径（参数 mainline_build_from_bottom_only = true）：共建主线只能从周期下半场进入——来源是顶部段时它一分不得。
    # 与 breakout_entry_origin = any 是同一问题的两端，供 stage_separation 靶子比较。
    if (params or {}).get("mainline_build_from_bottom_only") and origin is not None and origin not in BOTTOM_STAGES + (MAIN_RISE_ORIGIN,):
        gated.add("共建主线")
    return [(stage, pid) for stage, pid in hits if stage not in gated]


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
    """Fine stage: 见顶 marks the entry day of 高位震荡；二次探底 marks the retest-cross day inside 缩量右底."""
    if coarse not in STAGES:
        return "unassigned"
    if coarse == "高位震荡" and previous != coarse:
        return "见顶"
    # 第二十一段：二次探底是缩量右底的前段细标——回踩下穿当日。
    if coarse == "缩量右底" and flags.get("cross_below_kind") == "retest":
        return "二次探底"
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
