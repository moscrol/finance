"""Independent boundary witnesses for the vidio transfer; no production data."""

from __future__ import annotations

import math

import pytest

from intelligence.services.market_regime_analogs import RegimeSignature
from intelligence.services.regime_script import build_scripts, evaluate_gate, match_script, mint_scripts
from intelligence.services.river_lens import decompose, landscape


def _training():
    assignments = {f"t{i}": i % 2 for i in range(20)}
    signatures = {k: RegimeSignature({"x": (float(c * 10), 0.0)}) for k, c in assignments.items()}
    return signatures, assignments


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_regime_gate_rejects_nonfinite_outcomes(invalid):
    assign = {f"h{i}": i % 2 for i in range(20)}
    outcomes = {k: float(c * 10) for k, c in assign.items()}
    outcomes["h0"] = invalid
    gate = evaluate_gate(assign, outcomes)
    assert not gate.passed
    assert any("有限" in r for r in gate.reasons)


def test_regime_gate_checks_every_holdout_cluster_not_just_total_size():
    assignments = {str(i): int(i == 39) for i in range(40)}
    outcomes = {str(i): float(i == 39) * 100 for i in range(40)}
    gate = evaluate_gate(assignments, outcomes)
    assert not gate.passed, "one outlier must not certify a 39/1 split"
    assert any("簇" in r and "不足" in r for r in gate.reasons)


def test_regime_mint_rejects_overlapping_train_and_holdout():
    train, assign = _training()
    with pytest.raises(ValueError, match="重叠"):
        mint_scripts(train=train, train_assignments=assign, holdout_assignments=assign,
                     holdout_outcomes={k: float(c * 10) for k, c in assign.items()}, features=("x",))


def test_regime_mint_rejects_holdout_labels_not_defined_by_training():
    train, assign = _training()
    hold = {f"h{i}": 10 + i % 2 for i in range(20)}
    with pytest.raises(ValueError, match="训练簇"):
        mint_scripts(train=train, train_assignments=assign, holdout_assignments=hold,
                     holdout_outcomes={k: float(c * 10) for k, c in hold.items()}, features=("x",))


def test_regime_pipeline_rejects_duplicate_window_ids():
    train, assign = _training()
    with pytest.raises(ValueError, match="重复"):
        build_scripts(signatures=train, outcomes={k: float(c * 10) for k, c in assign.items()},
                      order=list(train) * 3, features=("x",))


def test_regime_single_comparable_script_is_not_confident_by_default():
    train, assign = _training()
    hold = {f"h{i}": i % 2 for i in range(20)}
    scripts, gate = mint_scripts(
        train=train, train_assignments=assign, holdout_assignments=hold,
        holdout_outcomes={k: float(c * 10) for k, c in hold.items()}, features=("x",))
    assert gate.passed and scripts
    result = match_script(RegimeSignature({"x": (1000.0, 0.0)}), scripts[:1], total_dims=1)
    assert not result.confident, "absence of a runner-up is not evidence of membership"


def test_river_lens_large_opposite_deltas_have_high_contribution():
    result = decompose(RegimeSignature({"x": (0.0, 4.0)}),
                       RegimeSignature({"x": (0.0, -4.0)}), 1)
    assert not result.low_contribution
    assert [d.feature for d in result.high_contribution] == ["x"]
    assert result.dims[0].direction_relation == "opposite"
    assert result.total == 4.0  # decomposition must keep the original metric


def test_river_lens_equal_distances_are_not_no_candidates():
    result = landscape([0.0] * 10)
    assert result.n == 10 and result.nearest == 0.0
    assert "无候选" not in result.reading
    assert "无法区分" in result.reading


def test_river_lens_relative_rank_does_not_claim_absolute_similarity():
    result = landscape([100.0] + [200.0 + i for i in range(200)])
    assert "真正突出的相似窗口" not in result.reading
    assert "绝对相似" in result.reading


def test_river_lens_earlier_asof_has_no_later_candidates(monkeypatch):
    from intelligence.services import river_lens, river_window

    daily = [{"trade_date": f"2026-04-{i + 1:02d}",
              **{f: float(i % 7) for f in river_window.COMPARABLE_FEATURE_NAMES}}
             for i in range(30)]
    monkeypatch.setattr(river_window, "build_daily_vectors", lambda **kw: daily)
    result = river_lens.lens_from_db(knowledge_cutoff="2026-04-30", as_of="2026-04-15",
                                       window=5, step=1, top=100)
    assert result.candidates
    assert all(c.end_date < "2026-04-11" for c in result.candidates)


def test_regime_does_not_mint_a_training_cluster_without_holdout_support():
    train, assign = _training()
    for i in range(6):
        train[f"third{i}"] = RegimeSignature({"x": (100.0, 0.0)})
        assign[f"third{i}"] = 2
    hold = {f"h{i}": i % 2 for i in range(20)}
    scripts, gate = mint_scripts(train=train, train_assignments=assign, holdout_assignments=hold,
        holdout_outcomes={k: float(c * 10) for k, c in hold.items()}, features=("x",))
    assert gate.passed
    assert len(scripts) == 2
    assert all(s.forward.n >= 4 for s in scripts)


def test_regime_distant_window_is_not_confident_just_because_runnerup_is_farther():
    train, assign = _training()
    hold = {f"h{i}": i % 2 for i in range(20)}
    scripts, gate = mint_scripts(train=train, train_assignments=assign, holdout_assignments=hold,
        holdout_outcomes={k: float(c * 10) for k, c in hold.items()}, features=("x",))
    assert gate.passed
    result = match_script(RegimeSignature({"x": (-10.0, 0.0)}), scripts, total_dims=1)
    assert not result.confident
    assert "训练" in result.note


def test_regime_train_outcome_nan_cannot_enter_forward_facts():
    train, assign = _training()
    hold = {f"h{i}": i % 2 for i in range(20)}
    with pytest.raises(ValueError, match="有限"):
        mint_scripts(train=train, train_assignments=assign, holdout_assignments=hold,
            train_outcomes={"t0": math.nan},
            holdout_outcomes={k: float(c * 10) for k, c in hold.items()}, features=("x",))


def test_regime_gate_computation_is_safe_at_large_finite_scales():
    assign = {f"h{i}": i % 2 for i in range(20)}
    gate = evaluate_gate(assign, {k: (1e308 if c else -1e308) for k, c in assign.items()})
    assert gate.passed and math.isfinite(gate.observed)


def test_teaching_first_known_at_normalizes_aware_build_time_to_utc():
    from datetime import datetime, timedelta, timezone
    from intelligence.services.teaching_framework.pit_identity import first_known_at

    actual = first_known_at(label="tf.stage_coarse", entity_type="market", entity_id="market",
        trade_date="2026-03-31", value_num=None, value_text="example", previous={},
        build_time=datetime(2026, 4, 1, 1, tzinfo=timezone(timedelta(hours=8))))
    assert actual == datetime(2026, 3, 31, 17)


@pytest.mark.parametrize("window", [0, -1])
def test_river_lens_rejects_nonpositive_window(window):
    from intelligence.services.river_lens import lens_from_db

    with pytest.raises(ValueError, match="window"):
        lens_from_db(knowledge_cutoff="2026-04-30", window=window, db_path="must-not-open.duckdb")
