"""Producer-only witnesses: means own their denominators; coverage != eligibility.

No prose validator and no model calls. Pure rows and the two existing synthetic
fixtures; independently decode model columns and count original loaded rows.
"""
from __future__ import annotations

import json

import duckdb
import pytest

from intelligence.services import market_regime_analogs as regime, river_lens as lens
from intelligence.tests.test_river_history_consumption import _apply_changed_gap, _make_db


@pytest.mark.parametrize("values,mean,count", [
    ([1.0, 1.0, 1.0, 1.0], 1.0, 4),
    ([1.0, None, None, None], 1.0, 1),
    ([None, None, None, None], None, 0),
    ([0.0, None, None, None], 0.0, 1),
    ([], None, 0),
])
def test_raw_mean_keeps_its_own_observation_denominator(values, mean, count):
    rows = [{"double_red_theme_count": value} for value in values]
    summary, coverage = regime._raw_window_summary_with_coverage(rows)
    assert summary["double_red_theme_count"] == mean
    assert coverage["input_days"] == len(values)
    assert coverage["non_null_days"]["double_red_theme_count"] == count
    assert summary == regime._raw_window_summary(rows)  # old Python value read remains compatible
    assert coverage["non_null_days"]["total_amount"] == 0


@pytest.mark.parametrize("n", [1, 2, 6, 7, 20, 21])
def test_signature_thresholds_are_actual_integer_rules_not_full_coverage(n):
    minimum = max(1, int(n * 0.6))
    segment = max(1, n // 3)
    indices = {0, n - 1}
    indices.update(range(max(0, minimum - len(indices)) + 1))
    # n=2 has a minimum of one observation but still requires both end segments.
    values = [float(i) if i in indices else None for i in range(n)]
    signature = regime.window_signature([{"x": v} for v in values], ("x",))
    original = signature.to_payload()
    assert original["window_days"] == n
    assert original["eligibility"] == {
        "min_non_null_days": minimum, "segment_days": segment,
        "min_head_days": 1, "min_tail_days": 1,
    }
    assert "x" in signature.stats
    table = regime.signature_table([("current", original)])
    assert table["window_days"]["current"] == n
    assert table["eligibility_by_window_days"][str(n)] == original["eligibility"]


@pytest.mark.parametrize("missing_head", [False, True])
def test_ineligible_signature_still_carries_input_size_and_requirements(missing_head):
    # 14/20 is enough globally; a wholly missing head segment still excludes x.
    values = [None] * 6 + list(range(14)) if missing_head else [None] * 20
    signature = regime.window_signature([{"x": v} for v in values], ("x",))
    assert signature.stats == {}
    table = regime.signature_table([("current", signature.to_payload())])
    assert table["windows"]["current"] == []
    assert table["window_days"]["current"] == 20
    assert table["eligibility_by_window_days"]["20"]["min_non_null_days"] == 12


def test_legacy_signature_does_not_invent_window_size_or_eligibility():
    original = regime.RegimeSignature({"x": (0.0, 0.0)}).to_payload()
    assert original["window_days"] is None and original["eligibility"] is None
    table = regime.signature_table([("current", original)])
    assert table["window_days"]["current"] is None
    assert table["eligibility_by_window_days"] == {}


def test_legacy_serialized_signature_without_new_metadata_stays_readable():
    table = regime.signature_table([("old", {
        "features": {"x": {"raw_mean": 1.0, "z_mean": 0.0, "end_segment_delta": 0.0}},
    })])
    assert table["window_days"]["old"] is None
    assert table["eligibility_by_window_days"] == {}
    assert table["windows"]["old"][0][0] == "x"


def _decode(table, ref):
    return [{**table.get("defaults", {}), **dict(zip(table["columns"], row, strict=True))}
            for row in table["windows"][ref]]


@pytest.mark.parametrize("sample,cutoff", [("normal", "2025-04-10"), ("changed-gap", "2025-04-02")])
def test_full_and_model_summaries_retain_counts_even_for_exited_dimensions(tmp_path, sample, cutoff):
    db = tmp_path / "synthetic.duckdb"
    _make_db(db)
    if sample == "changed-gap":
        _apply_changed_gap(db)
    artifact = regime.load_market_regime_artifact(db, as_of=cutoff)
    with duckdb.connect(str(db), read_only=True) as con:
        vectors, _ = regime.load_market_regime_vectors(con, as_of=cutoff, knowledge_cutoff=cutoff)
    full = artifact.to_payload()
    payload = artifact.model_payload()
    table = payload["raw_summaries"]
    assert table["aggregation"] == "mean_over_non_null"
    assert table["scope"] == "signature_supplement"
    assert "current_summary" not in payload  # no unqualified duplicate model-facing scalar map
    assert "raw_summary" not in payload["candidates"]["columns"]
    windows = {"current": (artifact.current_window, full["current_summary"], full["current_summary_coverage"])}
    for ref, dates in payload["windows"].items():
        original = next(a for a in full["analogs"] if [a["start_date"], a["end_date"]] == dates)
        windows[ref] = (dates, original["raw_summary"], original["raw_summary_coverage"])
    assert set(table["windows"]) == set(windows)
    for ref, (dates, means, coverage) in windows.items():
        raw = [v for v in vectors if dates[0] <= v["trade_date"] <= dates[1]]
        assert coverage["input_days"] == table["window_days"][ref] == len(raw)
        extra = {payload["feature_keys"][r["feature"]]: r for r in _decode(table, ref)}
        signed = {payload["feature_keys"][r["feature"]]: r for r in _decode(payload["signatures"], ref)}
        assert not (set(extra) & set(signed))
        decoded = {**signed, **extra}
        assert set(means) == set(coverage["non_null_days"])
        assert set(means) <= set(decoded)
        for feature, mean in means.items():
            observations = [v[feature] for v in raw if v.get(feature) is not None]
            assert coverage["non_null_days"][feature] == decoded[feature]["non_null_days"] == len(observations)
            assert mean == (sum(observations) / len(observations) if observations else None)
            assert decoded[feature]["raw_mean"] == (round(mean, 3) if mean is not None else None)
        # D10's globally constant dimension has real raw observations, not zero or no-data.
        assert decoded["double_red_theme_count"]["raw_mean"] == 1
        assert 0 < decoded["double_red_theme_count"]["non_null_days"] < len(raw)
        assert "双红题材数" not in {r["feature"] for r in _decode(payload["signatures"], ref)}
    block = regime.regime_block_for_llm(db, as_of=cutoff)
    assert json.loads(block.split("```json\n")[1].split("\n```")[0])["raw_summaries"] == table
    if sample == "changed-gap":
        first = full["analogs"][0]["signature"]
        assert first["features"]["advancers"]["tail_days"] == 4
        assert first["eligibility"]["min_tail_days"] == 1  # partial is eligible, not full


def test_legacy_artifact_counts_stay_unknown_instead_of_assumed_complete():
    artifact = regime.MarketRegimeArtifact(20, {"total_amount": 1.0}, ({
        "start_date": "2025-01-01", "end_date": "2025-01-20",
        "raw_summary": {"total_amount": 0.0}, "forwards": {},
    },), ())
    table = artifact.model_payload()["raw_summaries"]
    for ref in ("current", "d10.1"):
        assert _decode(table, ref)[0]["non_null_days"] is None
        assert table["window_days"][ref] is None


@pytest.mark.parametrize("observations", [
    {},
    {"x": {}},
    {"x": {"read_status": "queried", "missing_policy": "null_unknown"},
     "y": {"read_status": "not_requested", "missing_policy": None},
     "z": {"read_status": "query_failed", "missing_policy": "observed_source_rows_only"}},
])
def test_observation_defaults_round_trip_exceptions_and_unknowns(observations):
    table = regime.observation_table(observations)
    decoded = {
        feature: {**table["defaults"], **dict(zip(table["columns"], values, strict=True)),
                  **{key: by_feature[feature] for key, by_feature in table["overrides"].items() if feature in by_feature}}
        for feature, values in table["features"].items()
    }
    expected = {feature: {key: original.get(key) for key in (
        "source", "unit", "read_status", "non_null_days", "comparison_status", "missing_policy",
    )} for feature, original in observations.items()}
    assert decoded == expected


def test_river_uses_same_signature_eligibility_without_a_second_algorithm():
    daily = [{"trade_date": f"2025-01-{i + 1:02d}", "x": float(i % 3)} for i in range(30)]
    result = lens.build_lens(daily, ("x",), current=("2025-01-21", "2025-01-30"),
                             candidates=[("prior", "2025-01-01", "2025-01-10")])
    requirements = result.model_payload()["signatures"]["eligibility_by_window_days"]
    assert requirements == {"10": {
        "min_non_null_days": 6, "segment_days": 3, "min_head_days": 1, "min_tail_days": 1,
    }}
