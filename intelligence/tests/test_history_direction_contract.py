"""Shared end-segment directions belong to the producer, not to prose repair.

Pure signed rows exercise actual D10 selection. Relations are decided before
rounding; missing operands never become a flat path or an observed zero.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import math

import pytest

from intelligence.services import market_regime_analogs as regime, river_lens as lens


MODEL_RELATIONS = {"same": "同向", "opposite": "反向", "one_near_zero": "一方近零", "both_near_zero": "双方近零"}

CASES = [
    (-0.31, 0.31, "opposite"),
    (-0.51, 0.06, "one_near_zero"),
    (0.3, -0.3, "both_near_zero"),
    (0.31, 0.8, "same"),
    (-0.31, -0.8, "same"),
    (0.0, -0.0, "both_near_zero"),
    (math.nextafter(0.3, math.inf), -0.3, "one_near_zero"),
    (math.nextafter(-0.3, -math.inf), math.nextafter(0.3, math.inf), "opposite"),
]


def _artifact(current, candidate):
    """3-day windows retain exact tail operands without sum/mean roundoff."""
    features = set(current) | set(candidate)
    rows = []
    for window in (candidate, candidate, current):
        for i in range(3):
            rows.append({
                "trade_date": (date(2025, 1, 1) + timedelta(days=len(rows))).isoformat(),
                **{feature: (window[feature] if i == 2 else 0.0)
                   if feature in window else None for feature in features},
            })
    active = tuple(f for f in regime.FEATURES if f in features)
    signature, analogs, dropped = regime._find_regime_analogs(
        rows, rows, [f for f in regime.FEATURES if f not in active],
        window=3, stride=3, top_k=1,
    )
    assert len(analogs) == 1
    return regime.MarketRegimeArtifact(
        3, {}, tuple(analogs), tuple(dropped), current_signature=signature,
        active_features=active, current_window=(rows[-3]["trade_date"], rows[-1]["trade_date"]),
    )


def _rows(table, ref):
    return [{**table.get("defaults", {}), **dict(zip(table["columns"], values, strict=True))}
            for values in table["windows"][ref]]


@pytest.mark.parametrize("current,candidate,expected", CASES)
def test_d10_relations_are_owned_by_selected_window_before_model_rounding(current, candidate, expected):
    artifact = _artifact({"advancers": current}, {"advancers": candidate})
    original = deepcopy(artifact.to_payload())
    analog = original["analogs"][0]
    assert analog["direction_relations"] == {"advancers": expected}
    assert analog["signature"]["features"]["advancers"]["end_segment_delta"] == candidate
    payload = artifact.model_payload()
    table = payload["signatures"]
    ref = next(iter(payload["windows"]))
    assert payload["windows"][ref] == [analog["start_date"], analog["end_date"]]
    row = _rows(table, ref)[0]
    assert payload["feature_keys"][row["feature"]] == "advancers"
    assert row["direction_relation"] == MODEL_RELATIONS[expected]
    assert row["end_segment_delta"] == round(candidate, 3)
    assert _rows(table, "current")[0]["direction_relation"] is None
    assert table["path_evidence"] == "not_provided"
    assert artifact.to_payload() == original  # projection never rewrites source values
    assert lens.decompose(
        regime.RegimeSignature({"advancers": (0.0, current)}),
        regime.RegimeSignature({"advancers": (0.0, candidate)}), 1,
    ).dims[0].direction_relation == expected


def test_only_shared_eligible_dimensions_have_pair_relations():
    artifact = _artifact(
        {"advancers": -0.5, "total_amount": 1.0},
        {"advancers": 0.0, "limit_up": 1.0},
    )
    analog = artifact.to_payload()["analogs"][0]
    assert analog["direction_relations"] == {"advancers": "one_near_zero"}
    assert analog["shared_features"] == ["advancers"]
    payload = artifact.model_payload()
    table = payload["signatures"]
    candidate = {payload["feature_keys"][r["feature"]]: r for r in _rows(table, "d10.1")}
    assert candidate["limit_up"]["direction_relation"] is None
    assert candidate["advancers"]["direction_relation"] == "一方近零"
    assert "total_amount" not in candidate


def test_legacy_candidate_without_pair_readout_stays_unknown():
    artifact = regime.MarketRegimeArtifact(20, {}, ({
        "start_date": "2025-01-01", "end_date": "2025-01-20", "forwards": {},
        "signature": regime.RegimeSignature({"advancers": (0.0, 1.0)}).to_payload(),
    },), (), current_signature=regime.RegimeSignature({"advancers": (0.0, -1.0)}))
    payload = artifact.model_payload()
    assert _rows(payload["signatures"], "d10.1")[0]["direction_relation"] is None
    assert "direction_relations" not in artifact.to_payload()["analogs"][0]


@pytest.mark.parametrize("delta,expected", [
    (-0.31, "decrease"), (-0.3, "near_zero"), (0.0, "near_zero"),
    (0.3, "near_zero"), (0.31, "increase"),
])
def test_both_producers_use_one_direction_rule(delta, expected):
    assert regime.end_segment_direction is lens.end_segment_direction
    assert regime.END_SEGMENT_EPSILON == lens.END_SEGMENT_EPSILON == 0.3
    assert regime.end_segment_direction(delta) == expected


@pytest.mark.parametrize("value", [None, math.nan, math.inf, -math.inf])
def test_missing_or_nonfinite_direction_does_not_become_near_zero(value):
    assert regime.end_segment_direction(value) is None
    for known in (-1.0, 0.0, 1.0):
        assert regime.end_segment_direction_relation(value, known) is None
        assert regime.end_segment_direction_relation(known, value) is None


@pytest.mark.parametrize("a,b,expected", CASES)
def test_pair_rule_is_symmetric_and_invariant_under_common_sign_reversal(a, b, expected):
    for left, right in ((a, b), (b, a), (-a, -b), (-b, -a)):
        assert regime.end_segment_direction_relation(left, right) == expected


def test_model_labels_are_bijective_with_full_object_categories_and_keep_unknown():
    assert {key: regime.direction_relation_label(key) for key in MODEL_RELATIONS} == MODEL_RELATIONS
    assert len(set(MODEL_RELATIONS.values())) == len(MODEL_RELATIONS)
    assert regime.direction_relation_label(None) is None


@pytest.mark.parametrize("counts", [
    [(20, 6, 6), (20, 6, 6), (20, 6, 6)],
    [(20, 6, 6), (18, 6, 4), (20, 6, 6)],
    [(20, 6, 6), (None, None, None), (0, 0, 0)],
    [(None, None, None), (None, None, None)],
    [],
])
def test_signature_count_defaults_round_trip_without_guessing_coverage(counts):
    columns = ("non_null_days", "head_days", "tail_days")
    signatures = [(f"window{i}", {"features": {
        "x": {"raw_mean": 1.0, "z_mean": 0.0, "end_segment_delta": 0.0,
              **dict(zip(columns, values, strict=True))},
    }}) for i, values in enumerate(counts)]
    originals = deepcopy(signatures)
    table = regime.signature_table(signatures)
    assert "defaults" in table
    for i, values in enumerate(counts):
        row = _rows(table, f"window{i}")[0]
        assert tuple(row[c] for c in columns) == values
    assert signatures == originals
    for c in columns:
        if len(counts) >= 2 and len({values[columns.index(c)] for values in counts}) == 1:
            assert c in table["defaults"] and c not in table["columns"]
        else:
            assert c in table["columns"] and c not in table["defaults"]


@pytest.mark.parametrize("raw_count", [3, 2, 0, None])
def test_default_signature_count_cannot_erase_a_different_raw_mean_denominator(raw_count):
    raw = [{"total_amount": 1.0, "advancers": 1.0}] * 3
    artifact = regime.MarketRegimeArtifact(
        3, {"total_amount": 1.0}, (), (),
        current_signature=regime.window_signature(raw, raw_rows=raw),
        current_summary_coverage={"input_days": 3, "non_null_days": {"total_amount": raw_count}},
    )
    payload = artifact.model_payload()
    assert payload["signatures"]["defaults"]["non_null_days"] == 3
    supplement = _rows(payload["raw_summaries"], "current")
    if raw_count == 3:
        assert supplement == []
    else:
        assert len(supplement) == 1
        assert supplement[0]["raw_mean"] == 1.0
        assert supplement[0]["non_null_days"] == raw_count


def test_same_summary_with_different_daily_paths_has_same_relation_not_path_evidence():
    a = regime.window_signature([{"advancers": v} for v in (0, 0, 0, 0, 0, 0)])
    b = regime.window_signature([{"advancers": v} for v in (0, 0, 10, -10, 0, 0)])
    assert a.stats == b.stats
    assert regime.end_segment_direction_relation(a.stats["advancers"][1], b.stats["advancers"][1]) == "both_near_zero"
    assert a.to_payload()["path_evidence"] == b.to_payload()["path_evidence"] == "not_provided"
