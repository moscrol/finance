"""Index-stage label orchestration over the pure flag and stage-rule functions."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

from .flags import BREADTH_FIELDS, EPISODE_FIELDS, RANGE_SCALAR_STEMS, SECTOR_FIELDS, SOURCE_PREFIX, compute_flags
from .stage_rules import (
    BAND_VIEWS,
    FOUNDER_UNCONFIRMED,
    REFERENCE_STAGE_ALIASES,
    STAGES,
    confidence,
    derive_turns,
    eligible_stages,
    predicate_hits,
    resolve_stage,
    score_flags,
    stage_fine,
    stage_predicates,
    transition_graph,
)

# A day is a teaching gap when any of these ``fact_market_daily`` inputs is NULL.
# Gap days get no stage, no flags and no scalars (spec §1.5); they break the
# stage chain so the next day cannot inherit a stage from a day that was never
# written.
REQUIRED_MARKET_FIELDS = (
    "sh_index_close",
    "sh_index_open",
    "sh_week_ma",
    "sh_deviation_pct",
    "total_amount",
    "amount_ma20",
    "amount_vs_yesterday_pct",
    "top3_industry_ratio",
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _date_key(value: Any) -> str:
    return str(value)[:10]


def build_index_stage(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    calendar: Iterable[Any] | None = None,
    vendor_rows: Iterable[Mapping[str, Any]] | None = None,
    stock_rows: Iterable[Mapping[str, Any]] | None = None,
    amount_rows: Iterable[Mapping[str, Any]] | None = None,
    breadth_rows: Iterable[Mapping[str, Any]] | None = None,
    sector_rows: Iterable[Mapping[str, Any]] | None = None,
    params: Mapping[str, Any] | None = None,
    supplier_normalizer: Callable[[Any], str] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic daily records containing flags, coarse/fine stages and turns.

    This function does not write a database. ``market_rows`` must be ordered by
    ``trade_date`` in the returned result (the helper sorts internally).  Records
    with a non-empty ``gap`` list carry no stage and must not be written as labels.
    """
    market_rows = [dict(row) for row in market_rows]
    market_by_date = {_date_key(row.get("trade_date")): row for row in market_rows}
    flags = compute_flags(
        market_rows,
        calendar=calendar,
        vendor_rows=vendor_rows,
        stock_rows=stock_rows,
        amount_rows=amount_rows,
        breadth_rows=breadth_rows,
        sector_rows=sector_rows,
        params=params,
    )
    out: list[dict[str, Any]] = []
    previous: str | None = None
    for f in flags:
        f = dict(f)
        scalar_gaps = f.pop("scalar_gaps", {})
        raw = market_by_date.get(_date_key(f.get("trade_date")), {})
        missing = [name for name in REQUIRED_MARKET_FIELDS if raw.get(name) is None]
        supplier_stage = f.get(f"{SOURCE_PREFIX}market_stage")
        record: dict[str, Any] = {
            "trade_date": f.get("trade_date"),
            "gap": missing,
            "scalar_gaps": dict(scalar_gaps),
            "supplier_market_stage": supplier_stage,
            "supplier_stage_normalized": supplier_normalizer(supplier_stage)
            if supplier_normalizer
            else supplier_stage,
        }
        if missing:
            record.update(
                {
                    "flags": {},
                    "stage_coarse": None,
                    "stage_fine": None,
                    "stage_scores": {},
                    "stage_evidence": None,
                }
            )
            out.append(record)
            previous = None
            continue
        # ``previous`` is the 来源状态: the last valid stage since the last gap day.  Ambiguous
        # and no-evidence days do not erase it (params ``ambiguity_memory = last_valid_stage``,
        # spec §9.9) — the phase did not end, we just could not read it that day.
        hits = predicate_hits(f, params, previous)
        scores = score_flags(f, params, previous)
        entered = sorted({stage for stage, pid in hits if pid.startswith("E:")})
        eligible = eligible_stages(previous, entered, params)
        coarse, resolution, tied = resolve_stage(scores, previous, params, entered)
        fine = stage_fine(coarse, f, previous, params)
        tier = confidence(coarse, scores, hits, params)
        record.update(
            {
                "flags": {
                    (k if k.startswith(SOURCE_PREFIX) else f"tf.{k}"): v
                    for k, v in f.items()
                    if k != "trade_date"
                },
                "stage_coarse": coarse,
                "stage_fine": fine,
                "stage_scores": scores,
                "predicate_hits": [f"{stage}:{pid}" for stage, pid in hits],
                "confidence": tier,
                "stage_evidence": _json(
                    {
                        "scores": scores,
                        # Fired predicates (one point each) and the inputs they
                        # read, negative branches and text values included.
                        "hits": [{"stage": stage, "predicate": pid} for stage, pid in hits],
                        "inputs": _evidence_inputs(f),
                        # How many of the stage's views fired, which did not, and
                        # by how much it beat the runner-up — the stage is a
                        # count of perspectives, never one condition.
                        "confidence": tier,
                        "from": previous,
                        # Stages allowed to win today: reachable from yesterday or entered
                        # by a turning point (词表「从什么来源状态演变而来」).
                        "eligible": eligible,
                        "entered": entered,
                        "resolution": resolution,
                        "tied": tied,
                    }
                ),
            }
        )
        out.append(record)
        if coarse in STAGES:
            previous = coarse
    turns = derive_turns([r["stage_coarse"] for r in out])
    for record, turn in zip(out, turns):
        if record["gap"]:
            continue
        record.update({f"tf.{k}": v for k, v in turn.items()})
    return out


EVIDENCE_INPUTS = (
    "cross_below_kind",
    "below_ma_cycle_retest_seen",
    "deviation_band",
    "days_since_cross_above",
    "volume_expanding",
    "above_week_ma",
    "volume_band",
    "volume_surge",
    "double_volume_day",
    "index_new_high_20d",
    "index_new_high_60d",
) + tuple(view for view, _ in BAND_VIEWS)


def _evidence_inputs(f: Mapping[str, Any]) -> dict[str, Any]:
    """Every value the predicates read today; NULL stays NULL, false stays false."""
    return {name: f.get(name) for name in EVIDENCE_INPUTS}


def to_label_rows(
    records: Iterable[Mapping[str, Any]],
    *,
    framework_version: str = "tf-v0.1",
    computed_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Flatten non-gap records to sidecar label-row shape, leaving evidence as JSON text.

    Teaching-derived values are written as ``tf.*``; copied source values keep
    their ``src.*`` name so no reader can mistake one namespace for the other.
    """
    rows: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("gap"):
            continue
        d = rec.get("trade_date")
        values: dict[str, Any] = {
            "tf.stage_coarse": rec.get("stage_coarse"),
            "tf.stage_fine": rec.get("stage_fine"),
            "tf.stage_evidence": rec.get("stage_evidence"),
            "tf.turn_up": rec.get("tf.turn_up"),
            "tf.turn_top": rec.get("tf.turn_top"),
            "tf.turn_down": rec.get("tf.turn_down"),
        }
        values.update(rec.get("flags", {}))
        for label, value in values.items():
            if isinstance(value, bool):
                value_num, value_text = int(value), None
            elif isinstance(value, (int, float)):
                value_num, value_text = value, None
            elif value is None:
                value_num, value_text = None, None
            else:
                value_num, value_text = None, str(value)
            rows.append(
                {
                    "entity_type": "market",
                    "entity_id": "market",
                    "trade_date": d,
                    "label": label,
                    "value_num": value_num,
                    "value_text": value_text,
                    "label_version": framework_version,
                    "computed_at": computed_at,
                }
            )
    return rows


def supplier_contingency(
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], int]:
    """Counts teaching coarse stage against untouched supplier stage (non-gap days)."""
    c: Counter[tuple[str, str]] = Counter()
    for r in records:
        if r.get("gap"):
            continue
        c[
            (
                str(r.get("stage_coarse")),
                str(
                    r.get("supplier_stage_normalized") or r.get("supplier_market_stage")
                ),
            )
        ] += 1
    return dict(c)


def _is_view_scalar(label: str) -> bool:
    stem = label.removeprefix("tf.")
    if stem in {name for name, _, _ in BREADTH_FIELDS}:
        return True
    if stem in EPISODE_FIELDS and stem not in ("cross_below_kind", "below_ma_cycle_retest_seen"):
        return True
    if stem in ("amount_vs_ma20_pct", "stock_up_ratio_ma5_pct"):  # 量能比与 5 日上涨比例：两条平台维度
        return True
    if stem in {name for name, _ in SECTOR_FIELDS}:  # 板块侧市场级：新高家数 / 双红题材数 / 涨停题材数 / 第一题材份额
        return True
    return any(stem.startswith(f"{prefix}_") and stem.endswith("d") for prefix in RANGE_SCALAR_STEMS)


def _quartiles(values: list[float]) -> dict[str, Any]:
    """n / p25 / median / p75 by nearest-rank on the sorted list; no interpolation, so no float drift."""
    ordered = sorted(values)
    n = len(ordered)

    def rank(q: float) -> float:
        return ordered[min(n - 1, max(0, int(round(q * (n - 1)))))]

    return {
        "n": n,
        "p25": round(rank(0.25), 4),
        "median": round(rank(0.5), 4),
        "p75": round(rank(0.75), 4),
    }


def view_scalars_by_stage(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Distribution of every non-scoring view scalar inside each resolved stage.

    The 水位 columns and the index range / amplitude / deviation-change columns
    are written but do not score.  Showing their quartiles per stage is how the
    founder can see whether, say, 高位震荡 days look different on 区间涨幅 or
    振幅 before deciding any threshold (创始人 09-07 第四段).  Counts and
    quantiles only; nothing here is a verdict.
    """
    grouped: dict[str, dict[str, list[float]]] = {}
    for r in records:
        if r.get("gap"):
            continue
        stage = str(r.get("stage_coarse"))
        for label, value in (r.get("flags") or {}).items():
            if not _is_view_scalar(label) or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            grouped.setdefault(label, {}).setdefault(stage, []).append(float(value))
    return {
        label: {stage: _quartiles(values) for stage, values in sorted(by_stage.items())}
        for label, by_stage in sorted(grouped.items())
    }


def breakout_confirmation(usable: list[Mapping[str, Any]], confirm_days: int, fallback_days: tuple[int, ...] = (3, 5)) -> dict[str, Any]:
    """How cross-above days play out, split by whether volume surged within the confirm window.

    创始人 09-07 第七段：「上穿要配合放量，不然很多上穿基本都是回落，或者上穿后三天内放量」。
    For every observed cross above: did the surge come on the cross day, within
    ``confirm_days`` after it, and did the index fall back below the MA within
    ``fallback_days``?  Counts only; a window truncated by the end of history or a
    gap day is counted as observed as far as it goes.
    """
    flags = [r.get("flags") or {} for r in usable]
    out: dict[str, Any] = {
        "window_days": confirm_days,
        "cross_above_days": 0,
        "surge_on_cross_day": 0,
        "surge_within_window": 0,
        "fell_back_within": {str(k): {"confirmed": 0, "unconfirmed": 0} for k in fallback_days},
        "held_above_through": {str(k): {"confirmed": 0, "unconfirmed": 0} for k in fallback_days},
    }
    for i, f in enumerate(flags):
        if f.get("tf.cross_above_week_ma") is not True:
            continue
        out["cross_above_days"] += 1
        window = flags[i : i + confirm_days + 1]
        confirmed = any(g.get("tf.volume_surge") is True for g in window)
        if f.get("tf.volume_surge") is True:
            out["surge_on_cross_day"] += 1
        if confirmed:
            out["surge_within_window"] += 1
        key = "confirmed" if confirmed else "unconfirmed"
        for k in fallback_days:
            after = flags[i + 1 : i + k + 1]
            fell = any(g.get("tf.above_week_ma") is False for g in after)
            (out["fell_back_within"] if fell else out["held_above_through"])[str(k)][key] += 1
    return out


# Founder-defined anchor events, read off the flags of a day.  创始人 09-07 第八段：
# 「当有计算方法时，可以回溯历史来找出共性区间来判断下次的行情」——for each event the
# receipt gives every view scalar's quartiles on the event days (the 共性区间) and how
# the index moved afterwards, so thresholds come from history rather than from a number
# the founder declined to supply.
EVENT_PREDICATES: dict[str, Any] = {
    "overheated": lambda f, hits: f.get("tf.deviation_band") == "overheated",
    "oversold": lambda f, hits: f.get("tf.deviation_band") == "oversold",
    "cross_above": lambda f, hits: f.get("tf.cross_above_week_ma") is True,
    "breakout_confirmed": lambda f, hits: "共建主线:E:breakout_volume_within_window" in hits,
    "surge_in_trend": lambda f, hits: f.get("tf.surge_in_trend") is True,
    "cross_below_first": lambda f, hits: f.get("tf.cross_below_kind") == "first",
    "cross_below_retest": lambda f, hits: f.get("tf.cross_below_kind") == "retest",
    # 第十三段「印象中跳空低开跌破周均的，后续往往指数是继续向下……其他的规律你可以通过特征回溯来下定义」：
    # 下穿日按 低开 / 开盘已在周均之下（缺口穿过周均）/ 盘中跌破 三种拆开读后续走势。
    "cross_below_gap_down": lambda f, hits: f.get("tf.cross_below_week_ma") is True and f.get("tf.gap_down_open") is True,
    "cross_below_gap_through_ma": lambda f, hits: f.get("tf.cross_below_week_ma") is True and f.get("tf.open_below_week_ma") is True,
    "cross_below_intraday": lambda f, hits: f.get("tf.cross_below_week_ma") is True and f.get("tf.gap_down_open") is False,
    # 第十一段：双量日 + 指数新高（不看来源）与 真正算进升级进入的日子（来源 = 高位震荡）分开读。
    "double_volume_new_high": lambda f, hits: f.get("tf.double_volume_day") is True and f.get("tf.index_new_high_20d") is True,
    "upgrade_entered": lambda f, hits: "主流主升2.0:E:upgrade_double_volume_new_high" in hits,
}
FORWARD_HORIZONS = (3, 5, 10, 20)


def views_by_event(usable: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Per anchor event: view-scalar quartiles on the event days and the index path afterwards.

    Forward numbers are readouts only (they look ahead); labels never do.  ``usable`` is
    the gap-free day sequence, so a horizon spanning a gap day counts trading days that
    were written, which is stated in ``note``.
    """
    flags = [r.get("flags") or {} for r in usable]
    hits = [set(r.get("predicate_hits") or ()) for r in usable]
    closes = [f.get("src.sh_index_close") for f in flags]
    out: dict[str, Any] = {
        "note": "quartiles are nearest-rank; forward horizons count written (gap-free) days; forward numbers are readouts, not labels",
    }
    for event, predicate in EVENT_PREDICATES.items():
        idx = [i for i, f in enumerate(flags) if predicate(f, hits[i])]
        views: dict[str, list[float]] = {}
        forward: dict[str, list[float]] = {str(k): [] for k in FORWARD_HORIZONS}
        min_within_10: list[float] = []
        below_within_5 = above_within_5 = higher_close_within_5 = observed_5 = 0
        for i in idx:
            for label, value in flags[i].items():
                if _is_view_scalar(label) and isinstance(value, (int, float)) and not isinstance(value, bool):
                    views.setdefault(label, []).append(float(value))
            c0 = closes[i]
            if not isinstance(c0, (int, float)) or c0 <= 0:
                continue
            for k in FORWARD_HORIZONS:
                if i + k < len(closes) and isinstance(closes[i + k], (int, float)):
                    forward[str(k)].append((closes[i + k] / c0 - 1) * 100)
            ahead = [c for c in closes[i + 1 : i + 11] if isinstance(c, (int, float))]
            if len(ahead) == 10:
                min_within_10.append((min(ahead) / c0 - 1) * 100)
            window = flags[i + 1 : i + 6]
            if len(window) == 5:
                observed_5 += 1
                if any(g.get("tf.above_week_ma") is False for g in window):
                    below_within_5 += 1
                if any(g.get("tf.above_week_ma") is True for g in window):
                    above_within_5 += 1
                if any(isinstance(g.get("src.sh_index_close"), (int, float)) and g["src.sh_index_close"] > c0 for g in window):
                    higher_close_within_5 += 1
        out[event] = {
            "days": len(idx),
            "views": {label: _quartiles(values) for label, values in sorted(views.items())},
            "forward_pct_chg": {k: (_quartiles(v) if v else None) for k, v in forward.items()},
            "forward_share_negative": {
                k: (round(sum(1 for x in v if x < 0) / len(v), 4) if v else None) for k, v in forward.items()
            },
            "min_close_within_10_pct_chg": _quartiles(min_within_10) if min_within_10 else None,
            "next_5_days": {"observed": observed_5, "below_ma": below_within_5, "above_ma": above_within_5, "higher_close": higher_close_within_5},
        }
    return out


def _agreement(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    resolved = [(ref, ours) for ref, ours in pairs if ours in STAGES]
    agree = sum(1 for ref, ours in resolved if REFERENCE_STAGE_ALIASES.get(ref) == ours)
    return {
        "days": len(pairs),
        "resolved_days": len(resolved),
        "agree_days": agree,
        "rate": round(agree / len(resolved), 4) if resolved else None,
        "unresolved_days": len(pairs) - len(resolved),
    }


def reference_comparison(
    usable: list[Mapping[str, Any]],
    reference: Mapping[str, Mapping[str, Any]],
    train_until: str | None = None,
) -> dict[str, Any]:
    """Compare computed stages with the platform's daily reference stages (创始人：「当参照」).

    ``reference`` maps ``YYYY-MM-DD`` to a row with at least ``cycle_stage``.  The
    contingency table is on raw vocabularies; ``agreement`` folds the platform's
    inner stages onto ours through ``REFERENCE_STAGE_ALIASES`` and, when the
    parameter file records a calibration cut-off, is also split into the days
    the bands were read from and the days they were not (the honest number).
    Per reference stage the receipt also gives the view scalars' quartiles and
    the MA-side / volume-band counts — the 共性区间 of each stage as the
    founder's platform labels it.
    """
    overlap = [(r, reference[str(r.get("trade_date"))[:10]]) for r in usable if str(r.get("trade_date"))[:10] in reference]
    contingency: Counter[str] = Counter()
    pairs_all: list[tuple[str, str]] = []
    pairs_train: list[tuple[str, str]] = []
    pairs_validate: list[tuple[str, str]] = []
    per_stage_views: dict[str, dict[str, list[float]]] = {}
    per_stage_side: dict[str, Counter[str]] = {}
    per_stage_band: dict[str, Counter[str]] = {}
    for r, ref in overlap:
        ref_stage = str(ref.get("cycle_stage"))
        ours = str(r.get("stage_coarse"))
        contingency[f"{ref_stage} × {ours}"] += 1
        pairs_all.append((ref_stage, ours))
        if train_until:
            (pairs_train if str(r.get("trade_date"))[:10] <= train_until else pairs_validate).append((ref_stage, ours))
        flags = r.get("flags") or {}
        views = per_stage_views.setdefault(ref_stage, {})
        for label, value in flags.items():
            if _is_view_scalar(label) and isinstance(value, (int, float)) and not isinstance(value, bool):
                views.setdefault(label, []).append(float(value))
        above = flags.get("tf.above_week_ma")
        per_stage_side.setdefault(ref_stage, Counter())["above" if above is True else "below" if above is False else "unknown"] += 1
        band = flags.get("tf.volume_band")
        if band is not None:
            per_stage_band.setdefault(ref_stage, Counter())[str(band)] += 1
    return {
        "source": "history_reference_stages",
        "overlap_days": len(overlap),
        "reference_stage_days": dict(sorted(Counter(str(ref.get("cycle_stage")) for _, ref in overlap).items())),
        "contingency": dict(sorted(contingency.items())),
        "aliases": dict(REFERENCE_STAGE_ALIASES),
        "agreement": _agreement(pairs_all),
        "train_until": train_until,
        "agreement_train": _agreement(pairs_train) if train_until else None,
        "agreement_validate": _agreement(pairs_validate) if train_until else None,
        "views_by_reference_stage": {
            stage: {
                "days": sum(per_stage_side.get(stage, Counter()).values()),
                "ma_side": dict(sorted(per_stage_side.get(stage, Counter()).items())),
                "volume_band": dict(sorted(per_stage_band.get(stage, Counter()).items())),
                "views": {label: _quartiles(values) for label, values in sorted(views.items())},
            }
            for stage, views in sorted(per_stage_views.items())
        },
    }


def _flag_by_stage(usable: list[Mapping[str, Any]], label: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = {}
    for r in usable:
        value = (r.get("flags") or {}).get(label)
        if value is None:
            continue
        grouped.setdefault(str(r.get("stage_coarse")), Counter())[str(value).lower()] += 1
    return {stage: dict(sorted(c.items())) for stage, c in sorted(grouped.items())}


def label_readouts(
    records: Iterable[Mapping[str, Any]],
    params: Mapping[str, Any] | None = None,
    reference: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Receipt-ready summary: stage distribution, ambiguity, turns, contingency, graph.

    These are counts for the founder to read, not conclusions; ambiguity is
    reported as a rate because the spec treats it as a readout.  ``reference``
    (platform daily stages keyed by date) adds the comparison block when given.
    """
    p = params or {}
    rows = [dict(r) for r in records]
    usable = [r for r in rows if not r.get("gap")]
    stages = Counter(str(r.get("stage_coarse")) for r in usable)
    fine = Counter(str(r.get("stage_fine")) for r in usable)
    resolutions: Counter[str] = Counter()
    for r in usable:
        evidence = r.get("stage_evidence")
        if evidence:
            resolutions[str(json.loads(evidence).get("resolution"))] += 1
    unresolved = stages.get("ambiguous", 0) + stages.get("no_evidence", 0)
    contingency = [
        {"tf_stage_coarse": teaching, "supplier_stage": supplier, "days": days}
        for (teaching, supplier), days in sorted(supplier_contingency(usable).items())
    ]
    disagree_days = sum(
        cell["days"] for cell in contingency if cell["tf_stage_coarse"] != cell["supplier_stage"]
    )
    scalar_gaps: Counter[str] = Counter()
    for r in usable:
        for label, reason in (r.get("scalar_gaps") or {}).items():
            scalar_gaps[f"{label}:{reason}"] += 1
    predicate_days: Counter[str] = Counter()
    for r in usable:
        for hit in r.get("predicate_hits") or ():
            predicate_days[str(hit)] += 1
    margins: Counter[str] = Counter()
    tiers: Counter[str] = Counter()
    for r in usable:
        tier = r.get("confidence")
        if tier:
            margins[str(tier["margin"])] += 1
            tiers[f"{tier['stage']} {tier['hits']}/{tier['possible']}"] += 1
    # Volume band is a view that does not score (创始人 09-07 第四段：温和放量和缩量支持
    # 全周期的观察，不是某个阶段特有); crossing it with the resolved stage still
    # shows where each band actually lands.
    band_by_stage: Counter[str] = Counter()
    for r in usable:
        band = (r.get("flags") or {}).get("tf.volume_band")
        band_by_stage[f"{r.get('stage_coarse')} × {band}"] += 1
    # 创始人 09-07 第五段：「周均上方会比较看量能多一点，周均线下方一般都是缩量行情」。
    # Both volume views crossed with the side of the weekly MA, so that sentence
    # can be read against the data rather than taken on faith.
    by_side: dict[str, Counter[str]] = {}
    for r in usable:
        flags = r.get("flags") or {}
        above = flags.get("tf.above_week_ma")
        side = "above" if above is True else "below" if above is False else "unknown"
        counter = by_side.setdefault(side, Counter())
        counter["days"] += 1
        band = flags.get("tf.volume_band")
        if band is not None:
            counter[f"band_{band}"] += 1
        if flags.get("tf.shrink_day") is True:
            counter["amount_below_ma20"] += 1
    return {
        "days_total": len(rows),
        "days_usable": len(usable),
        "days_gap": len(rows) - len(usable),
        "stage_coarse_distribution": dict(sorted(stages.items())),
        "stage_fine_distribution": dict(sorted(fine.items())),
        "resolution_distribution": dict(sorted(resolutions.items())),
        "unresolved_days": unresolved,
        "unresolved_rate": round(unresolved / len(usable), 4) if usable else None,
        "turn_counts": {
            key: sum(int(r.get(key) or 0) for r in usable)
            for key in ("tf.turn_up", "tf.turn_top", "tf.turn_down")
        },
        "supplier_contingency": contingency,
        "supplier_disagree_days": disagree_days,
        "scalar_gap_counts": dict(sorted(scalar_gaps.items())),
        "predicate_hit_days": dict(sorted(predicate_days.items())),
        "founder_unconfirmed_predicate_days": {
            pid: predicate_days.get(pid, 0) for pid in FOUNDER_UNCONFIRMED
        },
        # Resolved days by winning margin (0 = tie broken by yesterday's stage,
        # 1 = a single view separated winner and runner-up) and by fired/possible
        # views of the winner.  A stage decided at margin 1 with 1/3 views is a
        # weak reading; the receipt says so instead of hiding it in a label.
        "resolved_days_by_margin": dict(sorted(margins.items())),
        "resolved_days_by_confidence": dict(sorted(tiers.items())),
        "volume_band_by_stage": dict(sorted(band_by_stage.items())),
        "volume_by_ma_side": {side: dict(sorted(c.items())) for side, c in sorted(by_side.items())},
        "view_scalars_by_stage": view_scalars_by_stage(usable),
        # 创始人 09-07 第七段的四个口径，各给一张读数：上穿是否在窗口内放量、放量与否
        # 之后是否回落；下穿是「第一次」还是「回踩」；偏离度三种走向达到门槛天数的日子；
        # 「高点不抬高 + 收敛」两旗标按阶段分布。
        "breakout_confirmation": breakout_confirmation(usable, int(p.get("breakout_confirm_days", 3))),
        "cross_below_kind_days": dict(sorted(Counter(
            str((r.get("flags") or {}).get("tf.cross_below_kind"))
            for r in usable if (r.get("flags") or {}).get("tf.cross_below_kind") is not None
        ).items())),
        "deviation_streak_days_at_min": {
            "min_days": int(p.get("deviation_streak_min", 3)),
            **{
                side: {
                    kind: sum(
                        1 for r in usable
                        if (r.get("flags") or {}).get("tf.above_week_ma") is above
                        and isinstance((r.get("flags") or {}).get(f"tf.deviation_{kind}_streak"), (int, float))
                        and (r.get("flags") or {}).get(f"tf.deviation_{kind}_streak") >= int(p.get("deviation_streak_min", 3))
                    )
                    for kind in ("rising", "falling", "toward_ma")
                }
                for side, above in (("above", True), ("below", False))
            },
        },
        "range_structure_by_stage": {
            label: _flag_by_stage(usable, label)
            for label in sorted({
                k for r in usable for k in (r.get("flags") or {})
                if k.removeprefix("tf.").startswith(("index_high_not_rising_", "index_range_converging_"))
            })
        },
        "views_by_event": views_by_event(usable),
        "reference_comparison": (
            reference_comparison(usable, reference, ((p.get("stage_bands_derived_from") or {}).get("train_until")))
            if reference else None
        ),
        "stage_bands": p.get("stage_bands"),
        "stage_bands_derived_from": p.get("stage_bands_derived_from"),
        "stage_predicate_catalog": {stage: list(pids) for stage, pids in stage_predicates(p).items()},
        "transition_graph": transition_graph(p),
        "tie_break": "tie resolved to the unique stage reachable from yesterday's stage, self-loop included; otherwise ambiguous",
    }
