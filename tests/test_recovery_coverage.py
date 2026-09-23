from copy import deepcopy

import pytest

from market_feature_store.recovery_coverage import market_breadth, partition_scope, sector_coverage

A, B, C = "600001.SH", "300002.SZ", "920003.BJ"


def test_scope_explained_coverage_is_not_bar_or_official_coverage():
    result = partition_scope(declared=[A, B, C], observed=[A, B], suspended=[C])
    assert result["bar_coverage_denominator"] == 3
    assert result["observed_bar_fraction"] == 2 / 3
    assert result["disposition_coverage_fraction"] == 1
    assert result["official_historical_universe_verified"] is False


@pytest.mark.parametrize("changes", [
    {"declared": []}, {"declared": [A, A, B]}, {"observed": [A, C]},
    {"observed": []}, {"observed": [A, B]}, {"suspended": [B, B]},
    {"suspended": [C]}, {"declared": ["600001.BOGUS", B]}, {"observed": A},
])
def test_partition_never_shrinks_or_synthesizes(changes):
    values = {"declared": [A, B], "observed": [A], "suspended": [B], **changes}
    with pytest.raises(ValueError):
        partition_scope(**values)


def test_suspended_is_not_flat_breadth():
    rows = [{"stock_ts_code": c, "pct_chg": p, "amount": 1.0}
            for c, p in ((A, 1.0), (B, -1.0), (C, 0.0))]
    assert market_breadth(rows, ["600004.SH"]) == {
        "advancers": 1, "decliners": 1, "unchanged_traded": 1,
        "nontrading_not_flat": 1, "observed_denominator": 3,
    }


@pytest.mark.parametrize("field,value", [("pct_chg", None), ("pct_chg", float("nan")),
    ("pct_chg", True), ("amount", 0), ("amount", -1), ("amount", float("inf"))])
def test_unknown_values_not_counted_as_unchanged(field, value):
    row = {"stock_ts_code": A, "pct_chg": 0., "amount": 1., field: value}
    with pytest.raises(ValueError):
        market_breadth([row], [])


def test_sector_total_includes_nontrading_but_has_no_synthetic_rows():
    kwargs = {"declared_members": {"sector": [A, B]}, "expected_counts": {"sector": 2},
              "observed_members": {"sector": [A]}, "suspended": [B]}
    before = deepcopy(kwargs)
    result = sector_coverage(**kwargs)["sector"]
    assert kwargs == before
    assert result["ratio_denominator"] == 2
    assert result["observed_count"] == 1 and result["synthetic_rows"] == 0
    assert result["nontrading_codes"] == [B]


@pytest.mark.parametrize("changes", [
    {"expected_counts": {"sector": 1}}, {"expected_counts": {"sector": True}},
    {"expected_counts": {"sector": 2, "other": 1}},
    {"observed_members": {"sector": [C]}}, {"observed_members": {}},
    {"observed_members": {"sector": [A, B]}},
    {"observed_members": {"sector": [A], "other": [C]}},
    {"suspended": []}, {"declared_members": {"sector": [A, A]}},
])
def test_unexplained_member_gap_surplus_and_hidden_sector_refused(changes):
    kwargs = {"declared_members": {"sector": [A, B]}, "expected_counts": {"sector": 2},
              "observed_members": {"sector": [A]}, "suspended": [B], **changes}
    with pytest.raises(ValueError):
        sector_coverage(**kwargs)


def test_all_suspended_sector_still_has_identity_denominator():
    result = sector_coverage(declared_members={"sector": [B]}, expected_counts={"sector": 1},
                             observed_members={}, suspended=[B])["sector"]
    assert result["observed_count"] == 0 and result["ratio_denominator"] == 1
