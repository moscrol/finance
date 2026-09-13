"""spec 03 §7 评分：手算 Brier、平局、复制样本不增证据、连续差不得进 bool 统计、依赖不足不支持。"""

from __future__ import annotations

import math

import pytest

from intelligence.services.methodology_backtest.stats import block_bootstrap_readout
from intelligence.services.research_validation import ContractError, DailyDelta, PairSample, brier, daily_deltas, paired_readout, strict_bools
from intelligence.services.research_validation.contracts import default_analysis_policy
from intelligence.services.research_validation.scoring import calibration_buckets
from intelligence.tests.test_research_validation_support import weekdays

POLICY = default_analysis_policy(5)
DAYS = weekdays("2026-03-02", 120)


def _pairs(deltas_by_day, *, per_day=1, y=1):
    """delta > 0 → 候选更好。y=1 时 base p=0.5，候选 p=0.5+sqrt 调整使 Brier 差恰为 delta。"""
    out = []
    for day, delta in deltas_by_day:
        p_base = 0.5
        brier_base = (p_base - y) ** 2
        target = brier_base - delta
        assert 0 <= target <= 1
        p_cand = 1 - math.sqrt(target) if y == 1 else math.sqrt(target)
        for k in range(per_day):
            out.append(PairSample(case_id=f"{day}-{k}", entity_id=f"S{k}", trade_date=day, p_base=p_base, p_candidate=p_cand, y=y))
    return out


def test_brier_hand_calculation_matches_spec_example():
    samples = [(0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0)]
    assert math.fsum(brier(p, y) for p, y in samples) / 4 == pytest.approx(0.025, rel=1e-12)
    assert brier(0.9, 1) == pytest.approx(0.01, rel=1e-12)
    with pytest.raises(ContractError):
        brier(True, 1)
    with pytest.raises(ContractError):
        brier(0.5, 2)


def test_daily_deltas_equal_weight_within_day_then_across_days():
    pairs = [
        PairSample("a", "S1", "2026-03-02", 0.9, 0.6, 1),  # base 0.01 cand 0.16 → delta -0.15
        PairSample("b", "S2", "2026-03-02", 0.1, 0.4, 0),  # base 0.01 cand 0.16 → delta -0.15
        PairSample("c", "S3", "2026-03-03", 0.5, 0.9, 1),  # base 0.25 cand 0.01 → delta +0.24
    ]
    days = daily_deltas(pairs)
    assert [d.trade_date for d in days] == ["2026-03-02", "2026-03-03"]
    assert days[0].n_pairs == 2 and days[0].delta == pytest.approx(-0.15) and days[0].win is False
    assert days[1].n_pairs == 1 and days[1].delta == pytest.approx(0.24) and days[1].win is True
    readout = paired_readout(days, policy=POLICY, comparison_id="cmp")
    # 日期等权：(-0.15 + 0.24) / 2，而不是按 3 个配对加权
    assert readout["mean_brier_difference_descriptive"] == pytest.approx(0.045)


def test_positive_win_rate_and_negative_mean_difference_are_reported_side_by_side():
    deltas = [(DAYS[i], 0.0099) for i in range(12)] + [(DAYS[12 + i], -0.35) for i in range(3)]
    readout = paired_readout(daily_deltas(_pairs(deltas)), policy=POLICY, comparison_id="cmp")
    assert readout["wins"] == 12 and readout["losses"] == 3 and readout["ties"] == 0
    assert readout["mean_brier_difference_descriptive"] < 0
    assert readout["claim_kind"] == "paired_date_win_rate"
    assert readout["status"] == "insufficient"  # n=15 < min_n=20：胜出率高也不是支持
    assert readout["independent"]["verdict"] == "insufficient_n"
    assert any(g["code"] == "insufficient_n" for g in readout["gaps"])


def test_ties_keep_denominator_and_make_test_undefined():
    deltas = [(DAYS[i], 0.05) for i in range(20)] + [(DAYS[20 + i], 0.0) for i in range(5)]
    readout = paired_readout(daily_deltas(_pairs(deltas)), policy=POLICY, comparison_id="cmp")
    assert readout["n_dates"] == 25 and readout["ties"] == 5 and readout["wins"] == 20
    assert readout["status"] == "insufficient"
    assert [g["code"] for g in readout["gaps"]] == ["ties_test_not_defined"]
    assert readout["independent"] is None and readout["dependence"] is None
    assert readout["mean_brier_difference_descriptive"] == pytest.approx(0.05 * 20 / 25)
    all_ties = paired_readout(daily_deltas(_pairs([(DAYS[i], 0.0) for i in range(30)])), policy=POLICY, comparison_id="cmp")
    assert all_ties["ties"] == 30 and any("未观察到增量" in n for n in all_ties["notes"])
    assert all_ties["mean_brier_difference_descriptive"] == 0.0


def test_strict_bools_rejects_continuous_deltas_that_stats_would_silently_coerce():
    with pytest.raises(TypeError, match="连续差"):
        strict_bools([0.1, -0.1])
    with pytest.raises(TypeError):
        strict_bools([1, 0])
    with pytest.raises(TypeError):
        strict_bools([True, None])
    assert strict_bools([True, False]) == [True, False]
    # 反例记录：既有 block_bootstrap_readout 会把 +0.1 与 −0.1 都当命中——这正是守卫存在的理由。
    coerced = block_bootstrap_readout(
        [("c", "2026-03-02", 0.1), ("c", "2026-03-03", -0.1)], p0=0.5, block_len=1, min_blocks=1, n_boot=20
    )
    assert coerced.boot_p_lo == 1.0 and coerced.boot_p_hi == 1.0 and coerced.verdict == "supported"


def test_duplicated_same_day_cases_and_extra_sectors_do_not_add_evidence():
    deltas = [(DAYS[i], 0.05) for i in range(60)]
    single = paired_readout(daily_deltas(_pairs(deltas, per_day=1)), policy=POLICY, comparison_id="cmp")
    crowded = paired_readout(daily_deltas(_pairs(deltas, per_day=40)), policy=POLICY, comparison_id="cmp")
    assert single["n_dates"] == crowded["n_dates"] == 60
    assert single["independent"] == crowded["independent"]
    assert single["dependence"]["n_dates"] == crowded["dependence"]["n_dates"] == 60
    assert single["dependence"]["n_blocks"] == crowded["dependence"]["n_blocks"] == 12
    assert single["dependence"]["n_events"] == crowded["dependence"]["n_events"] == 60
    assert single["verdict"] == crowded["verdict"] == "supported"


def test_dependence_insufficient_blocks_blocks_support_even_when_wilson_says_yes():
    deltas = [(DAYS[i], 0.05) for i in range(25)]  # 25 个日期 // 块长 5 = 5 块 < 10
    readout = paired_readout(daily_deltas(_pairs(deltas)), policy=POLICY, comparison_id="cmp")
    assert readout["independent"]["verdict"] == "supported"
    assert readout["dependence"]["verdict"] == "insufficient_blocks"
    assert readout["verdict"] == "insufficient_n" and readout["status"] == "insufficient"
    assert any(g["code"] == "insufficient_blocks" for g in readout["gaps"])
    assert any("不以事件数冒充 N" in n or "有效日期块不足" in n for n in readout["notes"])


def test_symmetric_refuted_when_candidate_loses_every_date():
    deltas = [(DAYS[i], -0.05) for i in range(60)]
    readout = paired_readout(daily_deltas(_pairs(deltas)), policy=POLICY, comparison_id="cmp")
    assert readout["verdict"] == "refuted" and readout["losses"] == 60
    assert readout["mean_brier_difference_descriptive"] == pytest.approx(-0.05)


def test_block_length_is_frozen_from_policy_and_seed_makes_readout_deterministic():
    deltas = [(DAYS[i], 0.05 if i % 4 else -0.02) for i in range(60)]
    days = daily_deltas(_pairs(deltas))
    a = paired_readout(days, policy=POLICY, comparison_id="cmp")
    b = paired_readout(days, policy=POLICY, comparison_id="cmp")
    assert a == b
    assert a["dependence"]["block_len"] == POLICY["block_len"] == 5
    assert a["dependence"]["seed"] == POLICY["seed"]


def test_calibration_buckets_sparse_reports_insufficient_only_and_never_rounds():
    samples = [(0.85, 1), (0.9, 1), (0.95, 0)] + [(0.41 + 0.01 * i, i % 2) for i in range(12)]
    buckets = calibration_buckets(samples, min_n=10)
    assert [b["bucket"] for b in buckets] == [[0.0, 0.2], [0.2, 0.4], [0.4, 0.6], [0.6, 0.8], [0.8, 1.0]]
    top = buckets[4]
    assert top["count"] == 3 and top["sufficient"] is False and top["mean_p"] is None and "insufficient_n" in top["reason"]
    mid = buckets[2]
    assert mid["count"] == 12 and mid["sufficient"] is True
    assert mid["mean_p"] == math.fsum(0.41 + 0.01 * i for i in range(12)) / 12
    assert mid["observed_rate"] == 0.5


def test_daily_delta_dict_roundtrip():
    d = DailyDelta("2026-03-02", 2, 0.1, 0.05, 0.05, True)
    assert d.to_dict()["win"] is True and d.to_dict()["n_pairs"] == 2
