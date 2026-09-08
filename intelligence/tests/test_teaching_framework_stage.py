from __future__ import annotations

import json

from intelligence.services.teaching_framework.flags import compute_flags
from intelligence.services.teaching_framework.index_stage import (
    REQUIRED_MARKET_FIELDS,
    SEPARATION_METRICS,
    build_index_stage,
    label_readouts,
    stage_separation,
    supplier_contingency,
    to_label_rows,
)
from intelligence.services.teaching_framework.stage_rules import (
    BAND_VIEWS,
    BOTTOM_STAGES,
    CONTINUING_PREDICATES,
    DEFAULT_TRANSITIONS,
    ENTRY_PREDICATES,
    REFERENCE_STAGE_ALIASES,
    STAGES,
    confidence,
    derive_turns,
    eligible_stages,
    graph_from_params,
    predicate_hits,
    resolve_stage,
    stage_bands,
    stage_predicates,
    transition_graph,
)


def _scores(**kw: int) -> dict[str, int]:
    scores = {s: 0 for s in STAGES}
    scores.update(kw)
    return scores


# Synthetic common ranges: 量能比 / 水位 / 情绪 pick the stage cleanly, so the tests are hand-derivable.
BANDS = {
    "stage_bands": {
        "左底向下": {"amount_vs_ma20_pct": [78, 90], "stock_ma10_deviation_median": [-4.0, -1.0]},
        "左底向上": {"amount_vs_ma20_pct": [88, 102], "ma_episode_pct_chg": [1.0, 3.0]},
        "二次探底": {"amount_vs_ma20_pct": [80, 111], "sh_index_pct_chg_10d": [-4.0, 1.0]},
        "缩量右底": {"amount_vs_ma20_pct": [86, 100], "stock_ma10_deviation_median": [-1.2, 0.8]},
        "共建主线": {"amount_vs_ma20_pct": [97, 111], "stock_ma10_deviation_median": [-0.5, 1.8]},
        "主流主升": {"amount_vs_ma20_pct": [115, 135], "stock_ma10_deviation_median": [1.4, 2.5]},
        "主流主升2.0": {"amount_vs_ma20_pct": [108, 126], "stock_ma10_deviation_median": [1.0, 1.7]},
        "高位震荡": {"amount_vs_ma20_pct": [93, 111], "src.sh_deviation_pct": [0.3, 1.4]},
    },
    "transition_graph": {stage: list(targets) for stage, targets in DEFAULT_TRANSITIONS.items()},
    "stage_bands_derived_from": {"train_until": "2025-10-31", "source": "test"},
}


def test_eight_stages_are_the_platform_vocabulary_and_aliases_fold_onto_them():
    assert STAGES == ("左底向下", "左底向上", "二次探底", "缩量右底", "共建主线", "主流主升", "主流主升2.0", "高位震荡")
    assert "回踩周均线" not in STAGES
    assert REFERENCE_STAGE_ALIASES["承接盘反复"] == "高位震荡"
    assert all(REFERENCE_STAGE_ALIASES[s] == s for s in STAGES)
    assert BOTTOM_STAGES == ("左底向下", "左底向上", "二次探底", "缩量右底")


def test_transition_graph_comes_from_params_with_self_loops_first():
    default = transition_graph()
    assert set(default) == set(STAGES)
    for stage, targets in default.items():
        assert targets[0] == stage
    assert default["高位震荡"] == ["高位震荡", "主流主升2.0", "左底向下"]
    custom = graph_from_params({"transition_graph": {"左底向下": ["共建主线", "not-a-stage"]}})
    assert custom["左底向下"] == ("左底向下", "共建主线")  # unknown targets are dropped, self-loop kept
    assert custom["左底向上"] == ("左底向上",)  # stages missing from the file keep only the self-loop


def test_tie_resolution_uses_the_graph_and_never_guesses():
    tie = _scores(左底向下=2, 左底向上=2)
    assert resolve_stage(tie, None, BANDS) == ("ambiguous", "ambiguous", ["左底向上", "左底向下"])
    # From 左底向下, staying and moving to 左底向上 are both legal: still ambiguous.
    assert resolve_stage(tie, "左底向下", BANDS)[0] == "ambiguous"
    # From 高位震荡 only 左底向下 is reachable; 左底向上 is not eligible at all, so 左底向下 wins outright.
    assert resolve_stage(tie, "高位震荡", BANDS) == ("左底向下", "argmax", ["左底向下"])
    assert resolve_stage(_scores(), "共建主线", BANDS) == ("no_evidence", "no_evidence", [])
    assert resolve_stage(_scores(主流主升=3), None, BANDS) == ("主流主升", "argmax", ["主流主升"])


def test_transition_constraint_blocks_jumps_without_a_turning_point():
    """词表: a stage must say which state it came from — a non-adjacent stage needs an entry event to win."""
    # 共建主线 scores highest but is not reachable from 高位震荡 and has no entry today: it cannot win.
    scores = _scores(共建主线=3, 高位震荡=1, 左底向下=1)
    assert eligible_stages("高位震荡", (), BANDS) == ["左底向下", "主流主升2.0", "高位震荡"]
    assert resolve_stage(scores, "高位震荡", BANDS) == ("ambiguous", "ambiguous", ["左底向下", "高位震荡"])
    # With its entry event (a breakout) 共建主线 becomes eligible and wins as an ``entry``.
    assert resolve_stage(scores, "高位震荡", BANDS, entered=["共建主线"]) == ("共建主线", "entry", ["共建主线"])
    # Reachable winners are ordinary argmax even when another stage was entered.
    assert resolve_stage(_scores(高位震荡=2, 共建主线=1), "高位震荡", BANDS, entered=["共建主线"]) == ("高位震荡", "argmax", ["高位震荡"])
    # No eligible stage scores: no evidence, even though a non-eligible stage does — that would be a jump.
    assert resolve_stage(_scores(共建主线=2), "高位震荡", BANDS) == ("no_evidence", "no_evidence", [])
    # No valid yesterday: everything is eligible.
    assert eligible_stages(None, (), BANDS) == list(STAGES)
    assert eligible_stages("ambiguous", (), BANDS) == list(STAGES)


def test_breakout_entry_only_counts_when_coming_out_of_the_bottom_cycle():
    """第六段流程: 放量上穿 ends 下穿 → 探底 → 反弹 → 回踩; inside a top range the 5-day MA is crossed every few days."""
    flags = {"days_since_cross_above": 0, "volume_expanding": True, "above_week_ma": True}
    for origin in (None, "左底向下", "左底向上", "二次探底", "缩量右底"):
        assert ("共建主线", "E:breakout_volume_within_window") in predicate_hits(flags, BANDS, origin)
    for origin in ("共建主线", "主流主升", "主流主升2.0", "高位震荡"):
        assert ("共建主线", "E:breakout_volume_within_window") not in predicate_hits(flags, BANDS, origin)


def test_ambiguous_days_keep_the_origin_for_eligibility_and_evidence():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    # Day 1: 量能比 127.8%, 水位 1.5 → 主流主升 (2 bands).  Day 2: 水位 1.0 → 主流主升 1 (量能比), 主流主升2.0 1 (水位; 量能比
    # 127.8 is outside its band), 共建主线 1 (水位), 高位震荡 0 (偏离度 0.1) → eligible from 主流主升 = {主流主升, 高位震荡}: 主流主升 wins.
    # Day 3: 量能比 100% (inside 二次探底 / 缩量右底 / 共建主线 / 高位震荡 / 左底向上 bands) and 偏离度 1.0, 水位 1.0: from
    # 主流主升 only {主流主升, 高位震荡} are eligible; 主流主升 0, 高位震荡 2 (量能比 + 偏离度) → 高位震荡, turn_top from 主流主升.
    rows = [
        _market_row(days[0], total_amount=115.0),
        _market_row(days[1], total_amount=115.0, sh_deviation_pct=0.1),
        _market_row(days[2], total_amount=90.0),
    ]
    breadth = [_breadth(days[0], 1.5), _breadth(days[1], 1.0), _breadth(days[2], 1.0)]
    records = build_index_stage(rows, calendar=days, breadth_rows=breadth, params=BANDS)
    assert [r["stage_coarse"] for r in records] == ["主流主升", "主流主升", "高位震荡"]
    evidence = json.loads(records[2]["stage_evidence"])
    assert evidence["from"] == "主流主升" and evidence["eligible"] == ["主流主升", "高位震荡"]
    assert records[2]["tf.turn_top"] == 1
    # Force an ambiguous middle day and check the origin survives it.
    ambiguous_params = {**BANDS, "stage_bands": {**BANDS["stage_bands"], "高位震荡": {"amount_vs_ma20_pct": [115, 135], "stock_ma10_deviation_median": [1.4, 2.5]}}}
    records = build_index_stage(rows[:2] + [_market_row(days[2], total_amount=115.0)], calendar=days, breadth_rows=[_breadth(d, 1.5) for d in days], params=ambiguous_params)
    # Day 1 ties 主流主升 / 高位震荡 (identical bands) with no yesterday → ambiguous; the origin stays None until a stage resolves.
    assert records[0]["stage_coarse"] == "ambiguous"
    assert json.loads(records[1]["stage_evidence"])["from"] is None


def test_switch_margin_hysteresis_is_off_by_default_and_exempts_entries():
    """``stage_switch_margin``: leaving the current stage on band evidence needs a lead of k points; turning points are exempt."""
    scores = {**_scores(高位震荡=1), "主流主升2.0": 2}  # both reachable from 高位震荡
    assert resolve_stage(scores, "高位震荡", BANDS)[0] == "主流主升2.0"  # k = 1: plain argmax
    k2 = {**BANDS, "stage_switch_margin": 2}
    assert resolve_stage(scores, "高位震荡", k2) == ("高位震荡", "argmax", ["高位震荡"])  # lead of 1 is not enough
    assert resolve_stage({**_scores(高位震荡=1), "主流主升2.0": 3}, "高位震荡", k2)[0] == "主流主升2.0"
    # A stage entered by a turning point is exempt from the margin: a lead of 1 switches; without the entry it is held.
    lead_one = _scores(高位震荡=1, 左底向下=2)
    assert resolve_stage(lead_one, "高位震荡", k2, entered=["左底向下"]) == ("左底向下", "argmax", ["左底向下"])
    assert resolve_stage(lead_one, "高位震荡", k2) == ("高位震荡", "argmax", ["高位震荡"])
    # With the current stage at zero, a band-only switch still needs the full margin.
    assert resolve_stage(_scores(左底向下=1), "高位震荡", k2) == ("no_evidence", "no_evidence", [])
    assert resolve_stage(_scores(左底向下=2), "高位震荡", k2) == ("左底向下", "argmax", ["左底向下"])


def test_shrink_after_retest_is_a_continuing_view_for_缩量右底():
    hits = predicate_hits({"below_ma_cycle_retest_seen": True, "volume_band": "shrink"}, BANDS)
    assert ("缩量右底", "H:shrink_after_retest") in hits
    assert predicate_hits({"below_ma_cycle_retest_seen": False, "volume_band": "shrink"}, BANDS) == []
    assert predicate_hits({"below_ma_cycle_retest_seen": True, "volume_band": "moderate"}, BANDS) == []
    assert stage_predicates(BANDS)["缩量右底"][0] == "H:shrink_after_retest"


def test_bands_and_catalog_follow_the_parameter_file():
    bands = stage_bands(BANDS)
    assert bands["主流主升"] == {"amount_vs_ma20_pct": (115.0, 135.0), "stock_ma10_deviation_median": (1.4, 2.5)}
    assert stage_bands(None) == {stage: {} for stage in STAGES}
    catalog = stage_predicates(BANDS)
    assert catalog["共建主线"] == ("E:breakout_volume_within_window", "H:in_band:amount_vs_ma20_pct", "H:in_band:stock_ma10_deviation_median")
    assert catalog["缩量右底"] == ("H:shrink_after_retest", "H:in_band:amount_vs_ma20_pct", "H:in_band:stock_ma10_deviation_median")
    assert stage_predicates(None) == {stage: ENTRY_PREDICATES[stage] + CONTINUING_PREDICATES.get(stage, ()) for stage in STAGES}
    assert {view for view, _ in BAND_VIEWS} >= {"amount_vs_ma20_pct", "stock_ma10_deviation_median", "stock_up_ratio_ma5_pct", "src.sh_deviation_pct"}


def test_entry_predicates_are_the_founders_turning_points_and_bands_score_membership():
    flags = {
        "cross_below_kind": "first", "below_ma_cycle_day": 1, "below_ma_cycle_retest_seen": False, "gap_down_open": True,
        "deviation_band": "below", "days_since_cross_above": None, "volume_band": "shrink",
        "volume_expanding": False, "above_week_ma": False, "amount_vs_ma20_pct": 84.0, "stock_ma10_deviation_median": -1.9,
        "stock_up_ratio_ma5_pct": 40.0, "sh_index_pct_chg_10d": -2.4, "ma_episode_pct_chg": -1.9, "src.sh_deviation_pct": -1.2,
    }
    hits = predicate_hits(flags, BANDS)  # BANDS carries the 09-06 口径: day 1, 放量 or 跳空
    assert ("左底向下", "E:first_cross_below") in hits  # 跳空低开跌破周均
    # 09-06: a first cross below on shrinking volume without a gap down is not the start of the decline.
    quiet = {**flags, "gap_down_open": False}
    assert ("左底向下", "E:first_cross_below") not in predicate_hits(quiet, BANDS)
    assert ("左底向下", "E:first_cross_below") in predicate_hits({**quiet, "volume_expanding": True}, BANDS)
    # 第十二段 family: persist_days delays the entry to the k-th day below; volume = shrink / any are the other 口径.
    shrink3 = {**BANDS, "left_down_entry": {"persist_days": 3, "volume": "shrink"}}
    assert ("左底向下", "E:first_cross_below") not in predicate_hits(quiet, shrink3)  # day 1 of the cycle
    assert ("左底向下", "E:first_cross_below") in predicate_hits({**quiet, "below_ma_cycle_day": 3}, shrink3)
    assert ("左底向下", "E:first_cross_below") not in predicate_hits({**quiet, "below_ma_cycle_day": 3, "volume_band": "moderate"}, shrink3)
    assert ("左底向下", "E:first_cross_below") not in predicate_hits({**quiet, "below_ma_cycle_day": 3, "above_week_ma": True}, shrink3)  # popped back above
    assert ("左底向下", "E:first_cross_below") not in predicate_hits({**quiet, "below_ma_cycle_day": 3, "below_ma_cycle_retest_seen": True}, shrink3)
    assert ("左底向下", "E:first_cross_below") in predicate_hits(
        {**quiet, "below_ma_cycle_day": 2, "volume_band": "surge"}, {**BANDS, "left_down_entry": {"persist_days": 2, "volume": "any"}}
    )
    assert ("左底向下", "H:in_band:amount_vs_ma20_pct") in hits and ("左底向下", "H:in_band:stock_ma10_deviation_median") in hits
    assert ("二次探底", "H:in_band:amount_vs_ma20_pct") in hits  # 84 also sits inside 二次探底's wide band
    assert not any(stage == "主流主升" for stage, _ in hits)
    scores = {s: 0 for s in STAGES}
    for stage, _ in hits:
        scores[stage] += 1
    assert scores["左底向下"] == 3 and resolve_stage(scores, None, BANDS)[0] == "左底向下"
    # Retest cross below opens 二次探底; overheated opens 高位震荡; a breakout with volume opens 共建主线.
    assert ("二次探底", "E:retest_cross_below") in predicate_hits({"cross_below_kind": "retest"}, BANDS)
    assert ("高位震荡", "E:overheated") in predicate_hits({"deviation_band": "overheated"}, BANDS)
    assert ("共建主线", "E:breakout_volume_within_window") in predicate_hits(
        {"days_since_cross_above": 2, "volume_expanding": True, "above_week_ma": True}, {**BANDS, "breakout_confirm_days": 3}
    )
    assert not any(pid.startswith("E:breakout") for _, pid in predicate_hits(
        {"days_since_cross_above": 4, "volume_expanding": True, "above_week_ma": True}, {**BANDS, "breakout_confirm_days": 3}
    ))
    # NULL and boolean inputs never fall inside a band.
    assert predicate_hits({"amount_vs_ma20_pct": None, "volume_expanding": True}, BANDS) == []


def test_every_catalogued_predicate_can_fire_and_nothing_else_does():
    seen: set[tuple[str, str]] = set()
    for kind in ("first", "retest", None):
        for band in ("oversold", "below", "above", "overheated"):
            for since in (0, 5, None):
                for ratio in (84.0, 95.0, 105.0, 120.0, 130.0):
                    # 水位 tracks the volume level so that every stage's second band is reachable.
                    level = -1.5 if ratio < 90 else 0.5 if ratio < 100 else 1.2 if ratio < 115 else 1.5
                    seen.update(predicate_hits({
                        "cross_below_kind": kind, "deviation_band": band, "days_since_cross_above": since,
                        "volume_expanding": True, "above_week_ma": True, "amount_vs_ma20_pct": ratio,
                        "below_ma_cycle_retest_seen": kind == "retest", "volume_band": "shrink" if ratio < 100 else "moderate",
                        "stock_ma10_deviation_median": level, "stock_up_ratio_ma5_pct": 55.0,
                        "sh_index_pct_chg_10d": -1.0, "ma_episode_pct_chg": 2.0, "src.sh_deviation_pct": 1.0,
                    }, BANDS))
    # 第十一段 upgrade entry: only from 高位震荡, on a 双量日 that closes at a new high of the configured window.
    upgrade = {"double_volume_day": True, "index_new_high_20d": True, "index_new_high_60d": False}
    seen.update(predicate_hits(upgrade, BANDS, origin="高位震荡"))
    # 左底向下 entry lives in the first phase of a below-MA cycle (the generated grid above stays above the MA).
    seen.update(predicate_hits({"below_ma_cycle_day": 1, "below_ma_cycle_retest_seen": False, "above_week_ma": False, "gap_down_open": True}, BANDS))
    catalog = {(stage, pid) for stage, pids in stage_predicates(BANDS).items() for pid in pids}
    assert seen == catalog
    assert confidence("ambiguous", {s: 0 for s in STAGES}, [], BANDS) is None


def test_upgrade_entry_needs_top_origin_double_volume_and_new_high_of_the_configured_window():
    hit = ("主流主升2.0", "E:upgrade_double_volume_new_high")
    base = {"double_volume_day": True, "index_new_high_20d": True, "index_new_high_60d": False}
    assert hit in predicate_hits(base, BANDS, origin="高位震荡")
    # The first leg out of the bottom also makes 20-day highs on volume: not an upgrade.
    for origin in ("主流主升", "共建主线", "左底向下", None):
        assert hit not in predicate_hits(base, BANDS, origin=origin)
    assert hit not in predicate_hits({**base, "double_volume_day": False}, BANDS, origin="高位震荡")
    assert hit not in predicate_hits({**base, "index_new_high_20d": None}, BANDS, origin="高位震荡")
    # The window is a B-class parameter: with 60 the same day is not a new high.
    assert hit not in predicate_hits(base, {**BANDS, "upgrade_new_high_window": 60}, origin="高位震荡")
    assert hit in predicate_hits({**base, "index_new_high_60d": True}, {**BANDS, "upgrade_new_high_window": 60}, origin="高位震荡")


def _replay_turns(sequence: list[str | None]) -> dict[str, int]:
    """Independent re-count: origin = last valid stage; ambiguity keeps it, a gap (None) drops it."""
    counts = {"turn_up": 0, "turn_top": 0, "turn_down": 0}
    origin: str | None = None
    for stage in sequence:
        if stage in STAGES:
            if origin in BOTTOM_STAGES and stage == "共建主线":
                counts["turn_up"] += 1
            if origin in STAGES and origin != stage and stage == "高位震荡":
                counts["turn_top"] += 1
            if origin in STAGES and origin != stage and stage == "左底向下":
                counts["turn_down"] += 1
            origin = stage
        elif stage is None:
            origin = None
    return counts


def test_turns_keep_the_origin_through_ambiguity_but_not_through_gaps():
    seq = ["二次探底", "共建主线", "共建主线", "ambiguous", "高位震荡", "左底向下", None, "左底向下", "高位震荡", "主流主升2.0", "共建主线"]
    turns = derive_turns(seq)
    assert sum(x["turn_up"] for x in turns) == 1  # 主流主升2.0 → 共建主线 is not a turn up: not from a bottom stage
    assert sum(x["turn_top"] for x in turns) == 2  # 共建主线 → (ambiguous) → 高位震荡 counts; 左底向下 → 高位震荡 counts
    assert sum(x["turn_down"] for x in turns) == 1  # the 左底向下 after the gap day has no origin


def test_turn_counts_reconcile_with_sequence_replay():
    cycle = list(STAGES) + ["ambiguous", "no_evidence", None]
    sequence = [cycle[(i * 5) % len(cycle)] for i in range(120)]
    turns = derive_turns(sequence)
    totals = {key: sum(t[key] for t in turns) for key in ("turn_up", "turn_top", "turn_down")}
    assert totals == _replay_turns(sequence)


def _market_row(day: str, **overrides):
    row = {
        "trade_date": day,
        "sh_index_close": 101.0,
        "sh_index_open": 100.5,
        "sh_index_high": 102.0,
        "sh_index_low": 99.5,
        "sh_week_ma": 100.0,
        "sh_deviation_pct": 1.0,
        "total_amount": 100.0,
        "amount_ma20": 90.0,
        "amount_vs_yesterday_pct": 3.0,
        "top3_industry_ratio": 0.3,
        "market_stage": "主升阶段",
        "volume_state": "放量",
        "ice_point": None,
        "sh_week_ma_source": "vendor",
        "limit_up": 40,
        "advancers": 2500,
    }
    row.update(overrides)
    return row


def _breadth(day: str, ma10_dev: float, up_ratio: float = 52.0):
    return {"trade_date": day, "stock_count": 5000, "pct_chg_median": 0.2, "price_mean": 20.0, "up_ratio_pct": up_ratio,
            "ma5_deviation_median": ma10_dev, "ma5_count": 5000, "ma10_deviation_median": ma10_dev, "ma10_count": 5000}


def test_stage_evidence_is_structured_json_and_uses_band_membership():
    """量能比 108.9%, 水位 +1.2: 共建主线, 主流主升2.0, 高位震荡, 二次探底 all have a band containing it; the breakout entry decides."""
    days = ["2026-01-05", "2026-01-06"]
    # Day 1: below the MA with 量能比 88.9% and 水位 −1.5 → 左底向下 (two bands), so day 2 comes out of the bottom cycle.
    rows = [_market_row(days[0], sh_index_close=99.0, sh_deviation_pct=-1.0, total_amount=80.0), _market_row(days[1], total_amount=98.0)]
    breadth = [_breadth(days[0], -1.5), _breadth(days[1], 1.2)]
    records = build_index_stage(rows, calendar=days, breadth_rows=breadth, params={**BANDS, "breakout_confirm_days": 3})
    evidence = json.loads(records[1]["stage_evidence"])
    assert {"scores", "hits", "inputs", "confidence", "from", "resolution", "tied"} <= set(evidence)
    hits = {(h["stage"], h["predicate"]) for h in evidence["hits"]}
    assert ("共建主线", "E:breakout_volume_within_window") in hits  # cross above on day 2 with 量能比 ≥ 100
    assert ("共建主线", "H:in_band:amount_vs_ma20_pct") in hits and ("主流主升2.0", "H:in_band:amount_vs_ma20_pct") in hits
    assert ("左底向上", "H:in_band:ma_episode_pct_chg") in hits  # the leg gained 2.02%: inside 左底向上's band too
    assert evidence["scores"] == {"左底向下": 0, "左底向上": 1, "二次探底": 1, "缩量右底": 0, "共建主线": 3, "主流主升": 0, "主流主升2.0": 2, "高位震荡": 2}
    # Day 1 is 左底向下; 共建主线 is not reachable from it, so day 2 wins through its breakout entry.
    assert records[0]["stage_coarse"] == "左底向下"
    assert records[1]["stage_coarse"] == "共建主线" and evidence["resolution"] == "entry"
    assert evidence["from"] == "左底向下" and evidence["entered"] == ["共建主线"] and "共建主线" in evidence["eligible"]
    assert evidence["inputs"]["amount_vs_ma20_pct"] == round(98 / 90 * 100, 6)
    assert records[1]["confidence"] == {"stage": "共建主线", "hits": 3, "possible": 3, "missing": [], "margin": 1}


def test_gap_day_writes_no_labels_and_breaks_the_stage_chain():
    days = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
    # 量能比 127.8% with 水位 +1.5: 主流主升 hits both bands; 主流主升2.0 / 共建主线 / 高位震荡 one each.
    rows = [
        _market_row(days[0], total_amount=115.0),
        _market_row(days[1], total_amount=115.0),
        _market_row(days[2], total_amount=115.0, top3_industry_ratio=None),  # gap day
        _market_row(days[3], total_amount=115.0),
    ]
    breadth = [_breadth(d, 1.5, 55.0) for d in days]
    records = build_index_stage(rows, calendar=days, breadth_rows=breadth, params=BANDS)
    assert records[0]["stage_coarse"] == "主流主升" and records[1]["stage_coarse"] == "主流主升"
    assert records[2]["gap"] == ["top3_industry_ratio"]
    assert records[2]["stage_coarse"] is None and "tf.turn_top" not in records[2]
    assert json.loads(records[3]["stage_evidence"])["from"] is None  # yesterday was a gap
    label_rows = to_label_rows(records, framework_version="tf-v0.2+test")
    assert {str(r["trade_date"]) for r in label_rows} == set(days) - {days[2]}
    assert "top3_industry_ratio" in REQUIRED_MARKET_FIELDS


def test_stage_fine_marks_the_top_entry_day_only():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    # Day 1: 量能比 93.3% (inside 高位震荡 / 左底向上 / 二次探底 / 缩量右底 bands, outside 共建主线's), overheated entry → 高位震荡 2.
    # Days 2-3: 量能比 100%, 偏离度 1.0, 水位 +0.9 → 高位震荡 (量能比 + 偏离度) ties 共建主线 (量能比 + 水位) at 2.
    rows = [_market_row(d, total_amount=84.0 if i == 0 else 90.0, sh_deviation_pct=2.0 if i == 0 else 1.0) for i, d in enumerate(days)]
    breadth = [_breadth(d, 0.9) for d in days]
    records = build_index_stage(rows, calendar=days, breadth_rows=breadth, params=BANDS)
    assert records[0]["stage_coarse"] == "高位震荡" and records[0]["stage_fine"] == "见顶"
    assert json.loads(records[0]["stage_evidence"])["resolution"] == "argmax"
    # From 高位震荡, 共建主线 is not eligible without a breakout: it stays 高位震荡 — no longer the entry day.
    evidence = json.loads(records[1]["stage_evidence"])
    assert records[1]["stage_coarse"] == "高位震荡" and records[1]["stage_fine"] == "高位震荡"
    assert evidence["resolution"] == "argmax" and evidence["eligible"] == ["左底向下", "主流主升2.0", "高位震荡"] and evidence["entered"] == []


def test_source_passthrough_never_enters_tf_namespace():
    records = build_index_stage([_market_row("2026-01-05")], calendar=["2026-01-05"], params=BANDS)
    labels = {r["label"]: r for r in to_label_rows(records)}
    assert "src.market_stage" in labels and labels["src.market_stage"]["value_text"] == "主升阶段"
    assert "src.limit_up" in labels and labels["src.limit_up"]["value_num"] == 40
    assert not any(name.startswith("tf.") and name.removeprefix("tf.") in {
        "market_stage", "volume_state", "ice_point", "sh_week_ma_source", "total_amount", "limit_up", "advancers",
    } for name in labels)
    assert "tf.stage_coarse" in labels and "tf.above_week_ma" in labels


def test_supplier_contingency_and_readouts_keep_versions_apart():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    rows = [
        _market_row(days[0], total_amount=115.0, market_stage="主升阶段"),
        _market_row(days[1], total_amount=115.0, market_stage="震荡阶段"),
        _market_row(days[2], total_amount=115.0, top3_industry_ratio=None, market_stage="震荡阶段"),
    ]
    breadth = [_breadth(d, 1.5, 55.0) for d in days]
    records = build_index_stage(rows, calendar=days, breadth_rows=breadth, params=BANDS, supplier_normalizer=lambda v: str(v).removesuffix("阶段"))
    assert supplier_contingency(records) == {("主流主升", "主升"): 1, ("主流主升", "震荡"): 1}
    readouts = label_readouts(records, BANDS)
    assert readouts["days_total"] == 3 and readouts["days_usable"] == 2 and readouts["days_gap"] == 1
    assert readouts["stage_coarse_distribution"] == {"主流主升": 2}
    assert readouts["supplier_disagree_days"] == 2 and readouts["unresolved_rate"] == 0.0
    assert set(readouts["transition_graph"]) == set(STAGES)
    assert readouts["stage_predicate_catalog"]["主流主升"] == ["H:in_band:amount_vs_ma20_pct", "H:in_band:stock_ma10_deviation_median"]
    assert readouts["stage_bands_derived_from"] == BANDS["stage_bands_derived_from"]
    assert readouts["founder_unconfirmed_predicate_days"] == {}


def test_confidence_tier_reports_views_fired_missing_and_margin():
    """Skeleton §1.3: a stage is a count of views, so say how many fired and how close the runner-up was."""
    days = ["2026-01-05", "2026-01-06"]
    # Day 2: 水位 drops to 1.3 (outside 主流主升's band) and 偏离度 to 0.1 (outside 高位震荡's band).
    rows = [_market_row(days[0], total_amount=115.0), _market_row(days[1], total_amount=115.0, sh_deviation_pct=0.1)]
    breadth = [_breadth(days[0], 1.5), _breadth(days[1], 1.3)]
    records = build_index_stage(rows, calendar=days, breadth_rows=breadth, params=BANDS)
    assert records[0]["confidence"] == {"stage": "主流主升", "hits": 2, "possible": 2, "missing": [], "margin": 1}
    # Day 2: 主流主升 / 主流主升2.0 / 共建主线 tie at one view each; only the self-loop is reachable from 主流主升 → margin 0.
    assert records[1]["stage_coarse"] == "主流主升" and records[1]["confidence"]["margin"] == 0
    assert records[1]["confidence"]["missing"] == ["H:in_band:stock_ma10_deviation_median"]
    readouts = label_readouts(records, BANDS)
    assert readouts["resolved_days_by_margin"] == {"0": 1, "1": 1}
    assert readouts["resolved_days_by_confidence"] == {"主流主升 1/2": 1, "主流主升 2/2": 1}


def test_views_by_event_reports_common_ranges_and_forward_path():
    """创始人 09-07 第八段: thresholds come from history — per event, view quartiles and what followed."""
    days = [f"2026-01-{d:02d}" for d in (5, 6, 7, 8, 9, 12, 13, 14, 15)]
    closes = [99.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0, 103.0, 99.0]
    rows = []
    for i, (day, close) in enumerate(zip(days, closes)):
        rows.append(_market_row(
            day, sh_index_close=close, sh_index_open=close - 0.2, sh_index_high=close + 0.5, sh_index_low=close - 0.5,
            sh_deviation_pct=close - 100,
            total_amount=125.0 if i in (1, 5) else 80.0,  # 暴量 on the cross day and again on day 6 (in trend); 缩量 otherwise
        ))
    params = {**BANDS, "breakout_confirm_days": 3}
    records = build_index_stage(rows, calendar=days, params=params)
    events = label_readouts(records, params)["views_by_event"]
    assert events["breakout_confirmed"]["days"] == 1 and events["surge_in_trend"]["days"] == 1
    trend = events["surge_in_trend"]
    assert trend["forward_pct_chg"]["3"]["median"] == round((99 / 105 - 1) * 100, 4)
    assert trend["forward_pct_chg"]["5"] is None and trend["next_5_days"]["observed"] == 0
    breakout = events["breakout_confirmed"]
    assert breakout["next_5_days"] == {"observed": 1, "below_ma": 0, "above_ma": 1, "higher_close": 1}
    assert breakout["views"]["tf.ma_episode_pct_chg"]["n"] == 1
    assert breakout["forward_share_negative"]["3"] == 0.0 and breakout["forward_pct_chg"]["20"] is None
    assert events["overheated"]["days"] == 6
    # 第十三段: cross-below days split by how they opened.  The only cross below (day 9, open 98.8 < close 99 ≤ MA 100)
    # gapped down and opened under the MA; there is no intraday cross.
    assert events["cross_below_gap_down"]["days"] == 1 and events["cross_below_gap_through_ma"]["days"] == 1
    assert events["cross_below_intraday"]["days"] == 0 and events["cross_below_gap_down"]["min_close_within_10_pct_chg"] is None


def test_perturbing_a_future_day_leaves_earlier_flags_and_stages_untouched():
    """Spec §8.2: a day's flags and stage depend only on that day and before."""
    days = [f"2026-01-{d:02d}" for d in range(5, 17) if d not in (10, 11)]
    base = []
    for i, day in enumerate(days):
        base.append(_market_row(
            day,
            sh_index_close=100.0 + ((i * 7) % 5) - 2,
            sh_deviation_pct=((i * 3) % 7) - 3,
            total_amount=80.0 + (i % 3) * 15,
        ))
    breadth = [_breadth(d, ((i * 3) % 7) - 3) for i, d in enumerate(days)]
    k = 6
    perturbed = [dict(r) for r in base]
    perturbed[k]["sh_index_close"] = 150.0
    perturbed[k]["sh_deviation_pct"] = 9.0
    perturbed[k]["total_amount"] = 140.0
    before = build_index_stage(base, calendar=days, breadth_rows=breadth, params=BANDS)
    after = build_index_stage(perturbed, calendar=days, breadth_rows=breadth, params=BANDS)
    for i in range(k):
        assert before[i] == after[i], f"day {days[i]} changed when only {days[k]} was perturbed"
    assert before[k]["flags"] != after[k]["flags"]


def test_null_inputs_do_not_infer_flags():
    got = compute_flags([{"trade_date": "2026-01-01", "sh_index_close": None, "sh_week_ma": 1, "sh_deviation_pct": None}], calendar=["2026-01-01"])[0]
    assert got["above_week_ma"] is None and got["deviation_band"] is None and got["amount_vs_ma20_pct"] is None


def _sep_record(day: str, stage: str, **flags):
    return {"trade_date": day, "stage_coarse": stage, "flags": {f"tf.{k}" if not k.startswith("src_") else "src." + k[4:]: v for k, v in flags.items()}}


def test_stage_separation_is_the_calibration_target_not_platform_agreement():
    """创始人 09-08：校准的靶子是赚钱 / 亏钱效应和资金的区分力。η² 按阶段分组；训练 / 验证两半分开报；平台阶段只在同一组天上作参考。"""
    days = [f"2026-01-{d:02d}" for d in range(1, 31)]
    # 前 15 天我们判「左底向下」、后 15 天判「主流主升」；承接与上涨比例在两段之间分得很开，涨停家数完全分不开。
    records = []
    for i, d in enumerate(days):
        ours = "左底向下" if i < 15 else "主流主升"
        records.append(_sep_record(d, ours, limit_premium_ma5_pct=1.0 + (i % 3) * 0.1 if i < 15 else 2.5 + (i % 3) * 0.1,
                                   stock_up_ratio_ma5_pct=38.0 + (i % 4) if i < 15 else 56.0 + (i % 4),
                                   src_limit_up=60 + (i % 5), money_losing_day=1.0 if i % 3 == 0 and i < 15 else 0.0))
    # 平台把同一段历史切成前 10 / 后 20：它的分界比我们的偏早 5 天，所以承接在它的两组里混得更多。
    reference = {d: {"cycle_stage": "左底向下" if i < 10 else "主流主升"} for i, d in enumerate(days)}
    out = stage_separation(records, reference, train_until="2026-01-15")
    assert out["train_until"] == "2026-01-15" and out["summary"]["resolved_days"] == 30
    prem = out["metrics"]["承接 5 日均 %"]
    assert prem["family"] == "赚钱效应" and prem["days"] == 30
    assert prem["eta2"]["all"] > 0.9 and prem["level_by_stage"]["左底向下"]["median"] == 1.1 and prem["level_by_stage"]["主流主升"]["median"] == 2.6
    # 训练期（前 15 天）只有一个阶段 → η² 算不出（None），验证期同理；「all」才有——两半都单段的读数不能拿来吹。
    assert prem["eta2"]["train"] is None and prem["eta2"]["validate"] is None
    assert out["metrics"]["涨停家数"]["eta2"]["all"] < 0.05  # 分不开就是分不开
    assert out["metrics"]["亏钱效应日"]["level_by_stage"]["主流主升"]["median"] == 0.0
    # 同一组天上：我们的分界让承接分得更开（平台的分界偏了 5 天）；涨停家数两边都分不开 → tie。
    vs = out["summary"]["vs_platform_same_days"]
    assert vs["days"] == 30 and vs["metrics_compared"] == 4 and vs["ours_separates_better"] >= 2 and vs["platform_separates_better"] == 0
    assert prem["eta2_same_days"]["all"] > prem["eta2_platform_same_days"]["all"]
    # 没在标签里的指标：days 0、η² None，不报错。
    assert out["metrics"]["平均股价"]["days"] == 0 and out["metrics"]["平均股价"]["eta2"]["all"] is None
    assert len(out["metrics"]) == len(SEPARATION_METRICS)
    # 未决日（ambiguous）不进分组。
    out2 = stage_separation(records + [_sep_record("2026-02-01", "ambiguous", limit_premium_ma5_pct=9.0)], None)
    assert out2["summary"]["resolved_days"] == 30 and "vs_platform_same_days" not in out2["summary"]
