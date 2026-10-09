"""Root-cause witnesses: estimator domain, lossy summaries and window identity.

Pure functions and the existing synthetic fixture only; no production sources.
"""
from __future__ import annotations

from datetime import date, timedelta
import json
import yaml

import pytest

from intelligence.services import market_regime_analogs as regime, river_lens as lens
from intelligence.tests.test_river_history_consumption import CUTOFF, _make_db


def _rows(values):
    return [{"trade_date": (date(2025, 1, 1) + timedelta(days=i)).isoformat(), "x": v}
            for i, v in enumerate(values)]


@pytest.mark.parametrize("n", [1, 2, 3, 6, 7, 20, 21, 200])
def test_distance_distribution_has_no_uncalibrated_standout_class(n):
    result = lens.landscape([0.0] + [100.0] * (n - 1))
    payload = result.to_dict()
    assert "standout" not in payload, "legacy estimator cannot be a model-facing qualification"
    assert payload["interpretation"] == "descriptive_only"
    assert payload["quantile_method"] == "linear_at_p_times_n_minus_1"
    assert payload["candidates"] == n
    assert not any(word in result.reading for word in ("排名相对突出", "候选排名不突出", "身位"))


def test_distribution_empty_equal_and_affine_properties():
    assert lens.landscape([]).to_dict()["status"] == "no_candidates"
    assert lens.landscape([0.0] * 7).to_dict()["status"] == "available"
    values = [0.0, 1.0, 3.0, 5.0, 9.0, 11.0, 100.0]
    a = lens.landscape(values)
    b = lens.landscape([7 + 3 * v for v in values])
    assert a.quantiles["p5"] == pytest.approx(0.3)
    for key, value in a.quantiles.items():
        assert b.quantiles[key] == pytest.approx(7 + 3 * value)
    assert b.nearest == 7


@pytest.mark.parametrize("current,candidate,relation", [
    (-0.31, 0.31, "opposite"), (-0.51, 0.06, "one_near_zero"),
    (0.3, -0.3, "both_near_zero"), (0.31, 0.8, "same"),
])
def test_distance_contribution_is_not_direction(current, candidate, relation):
    result = lens.decompose(regime.RegimeSignature({"x": (0.0, current)}),
                            regime.RegimeSignature({"x": (0.0, candidate)}), 1)
    dim = result.to_dict()["per_dim"][0]
    assert dim["contribution"] == pytest.approx(0.5 * abs(current - candidate))
    assert dim["direction_relation"] == relation
    assert dim["current_end_segment_delta"] == current
    assert dim["candidate_end_segment_delta"] == candidate
    assert dim["contribution_band"] == "low"
    assert "verdict" not in dim


def test_signature_is_not_injective_and_never_certifies_a_path():
    daily = _rows([0, 0, 0, 0, 0, 0, 0, 0, 10, -10, 0, 0])
    z, _ = regime.standardize_vectors(daily, ("x",))
    a = regime.window_signature(z[:6], ("x",))
    b = regime.window_signature(z[6:], ("x",))
    assert a.stats == b.stats
    assert regime.signature_distance(a, b, 1) == 0
    for signature in (a, b):
        payload = signature.to_payload()
        assert payload["representation"] == "mean_and_end_segments"
        assert payload["path_evidence"] == "not_provided"
        assert payload["features"]["x"]["head_mean"] == 0
        assert payload["features"]["x"]["tail_mean"] == 0
        assert payload["features"]["x"]["non_null_days"] == 6


def test_same_label_different_windows_keep_identity_and_pairwise_overlap():
    daily = _rows([0, 1, 2] * 10)
    result = lens.build_lens(daily, ("x",), current=("2025-01-25", "2025-01-30"),
        candidates=[("same", "2025-01-01", "2025-01-06"),
                    ("same", "2025-01-04", "2025-01-09"),
                    ("same", "2025-01-07", "2025-01-12")], top=3)
    payload = result.to_dict()
    candidates = payload["candidates"]
    assert len({c["window_id"] for c in candidates}) == 3
    assert {c["start_date"] for c in candidates} == {"2025-01-01", "2025-01-04", "2025-01-07"}
    pairs = payload["candidate_relations"]
    assert len(pairs) == 3
    assert sum(p["overlap"] for p in pairs) == 2
    assert payload["selection"]["comparable_count"] == 3
    assert payload["selection"]["displayed_count"] == 3
    text = lens.lens_block(result)
    for c in candidates:
        assert c["start_date"] in text and c["end_date"] in text
    smaller = lens.build_lens(daily, ("x",), current=("2025-01-25", "2025-01-30"),
        candidates=[("same", "2025-01-01", "2025-01-06"),
                    ("same", "2025-01-04", "2025-01-09"),
                    ("same", "2025-01-07", "2025-01-12")], top=1).to_dict()
    assert smaller["selection"]["comparable_count"] == 3
    assert smaller["selection"]["displayed_count"] == 1
    assert smaller["landscape"]["candidates"] == 3


def test_candidate_identity_not_display_name_controls_duplicate_rejection():
    with pytest.raises(ValueError, match="重复"):
        lens.build_lens(_rows([0, 1] * 10), ("x",), current=("2025-01-15", "2025-01-20"),
            candidates=[("A", "2025-01-01", "2025-01-06"), ("B", "2025-01-01", "2025-01-06")])


@pytest.mark.parametrize("missing", [0, 1, 2, 3, 4])
def test_full_horizon_return_requires_every_daily_return(missing):
    rows = [{"trade_date": f"2025-01-{i + 1:02d}", "sh_index_pct_chg": 1.0} for i in range(5)]
    rows[missing]["sh_index_pct_chg"] = None
    fwd = regime._forward_facts(rows, 5)
    assert fwd["sh_index_cum_pct"] is None
    assert fwd["observed_days"]["sh_index_pct_chg"] == 4
    assert fwd["horizon"] == 5
    assert fwd["start_date"] == "2025-01-01" and fwd["end_date"] == "2025-01-05"
    assert "4/5" in regime._fwd_text(fwd, horizon=5)


def test_signature_raw_metadata_must_have_same_row_count():
    with pytest.raises(ValueError, match="逐日对应"):
        regime.window_signature([{"x": 1.0}] * 6, ("x",), raw_rows=[{"x": 2.0}])


def test_complete_forward_return_keeps_existing_number():
    rows = [{"trade_date": f"2025-01-{i + 1:02d}", "sh_index_pct_chg": 1.0} for i in range(5)]
    fwd = regime._forward_facts(rows, 5)
    assert fwd["sh_index_cum_pct"] == pytest.approx((1.01 ** 5 - 1) * 100)
    assert fwd["observed_days"]["sh_index_pct_chg"] == 5


def test_both_results_expose_scope_and_observed_source_semantics(tmp_path):
    from intelligence.services import river_window

    db = tmp_path / "synthetic.duckdb"
    _make_db(db)
    d10 = regime.load_market_regime_artifact(db, as_of=CUTOFF).to_payload()
    river = lens.lens_from_db(db_path=str(db), knowledge_cutoff=CUTOFF.isoformat(),
                              window=20, step=5, top=3).to_dict()
    assert d10["selection"]["comparable_count"] == river["selection"]["comparable_count"] == 7
    assert d10["selection"]["displayed_count"] == 1
    assert river["selection"]["displayed_count"] == 3
    assert d10["selection"]["strategy"] == "distance_greedy_nonoverlap"
    assert river["selection"]["strategy"] == "distance_top_k_overlap_allowed"
    assert river["feature_observations"]["checkpoints_registered"]["read_status"] == "not_requested"
    assert river["feature_observations"]["theme_net_flow"]["comparison_status"] == "suspended"
    assert river["feature_observations"]["double_red_count"]["non_null_days"] == 72
    assert d10["feature_observations"]["double_red_theme_count"]["non_null_days"] == 48
    assert "无分组为缺失" in d10["feature_observations"]["double_red_theme_count"]["missing_policy"]
    assert "已观测源行" in river["feature_observations"]["double_red_count"]["missing_policy"]
    daily = river_window.build_daily_vectors(knowledge_cutoff=CUTOFF.isoformat(), db_path=db)
    assert sum(row["double_red_count"] == 0 for row in daily) == 24
    json.dumps(d10, allow_nan=False)
    json.dumps(river, allow_nan=False)


def _model_json(text):
    return yaml.safe_load(text.split("```yaml\n")[1].split("\n```")[0])


def _table_rows(table, rows):
    return [{**table.get("defaults", {}), **dict(zip(table["columns"], row, strict=True))} for row in rows]


def _check_projection(payload, signatures, observations):
    """独立按列解码，与原件逐字段比对；不是仅与同一renderer自比。"""
    names = payload.get("feature_keys", {})
    for ref, signature in signatures.items():
        table = payload["signatures"]
        rows = _table_rows(table, table["windows"][ref])
        by = {names.get(r["feature"], r["feature"]): r for r in rows}
        assert set(by) == set(signature.stats)
        for feature, (mean, delta) in signature.stats.items():
            row = by[feature]
            assert row["z_mean"] == round(mean, 3)
            assert row["end_segment_delta"] == round(delta, 3)
            for key in ("raw_mean", "non_null_days", "head_days", "tail_days"):
                expected = signature.segments.get(feature, {}).get(key)
                assert row[key] == (round(expected, 3) if isinstance(expected, float) else expected)
    table = payload["feature_observations"]
    assert {names.get(label, label): {
                **table["defaults"], **dict(zip(table["columns"], row, strict=True)),
                **{k: overrides[label] for k, overrides in table["overrides"].items() if label in overrides},
            } for label, row in table["features"].items()} == {
                f: {k: o.get(k) for k in (*table["columns"], *table["defaults"])} for f, o in observations.items()}
    assert payload["signatures"]["path_evidence"] == "not_provided"
    assert "head_tail_level_means" in payload["signatures"]["omitted"]


def test_model_projection_retains_values_identities_scopes_and_relations(tmp_path):
    db = tmp_path / "synthetic.duckdb"
    _make_db(db)
    d10 = regime.load_market_regime_artifact(db, as_of=CUTOFF)
    river = lens.lens_from_db(db_path=str(db), knowledge_cutoff=CUTOFF.isoformat(), window=20, step=5, top=3)
    dp = _model_json(regime.regime_block_for_llm(db, as_of=CUTOFF))
    rp = _model_json(lens.lens_block(river))
    assert dp == d10.model_payload() and rp == river.model_payload()
    ds, rs = {"current": d10.current_signature}, {"current": river.current}
    for ref, dates in dp["windows"].items():
        original = next(a for a in d10.analogs if [a["start_date"], a["end_date"]] == dates)
        # 候选原件已序列化，回到同一stats/segments比较具名列。
        features = original["signature"]["features"]
        ds[ref] = regime.RegimeSignature({f: (v["z_mean"], v["end_segment_delta"]) for f, v in features.items()}, features)
        candidate = _table_rows(dp["candidates"], [dp["candidates"]["windows"][ref]])[0]
        assert candidate["distance"] == original["distance"]
        assert candidate["shared_dims"] == original["shared_dims"]
        for row in _table_rows(dp["forwards"], dp["forwards"]["rows"]):
            if row["window_id"] != ref:
                continue
            facts = original["forwards"][row["horizon"]]
            for key in ("start_date", "end_date", "sh_index_cum_pct", "avg_limit_up", "max_boards", "avg_double_red_themes"):
                value = facts[key]
                assert row[key] == (round(value, 3) if isinstance(value, float) else value)
            assert row["index_days"] == facts["observed_days"]["sh_index_pct_chg"]
    for ref, dates in rp["windows"].items():
        original = next(c for c in river.candidates if [c.start_date, c.end_date] == dates)
        rs[ref] = original.signature
        dims = {d.feature: d for d in original.decomposition.dims}
        for row in _table_rows(rp["signatures"], rp["signatures"]["windows"][ref]):
            dim = dims[rp["feature_keys"].get(row["feature"], row["feature"])]
            assert row["contribution"] == round(dim.contribution, 3)
            assert row["contribution_band"] == dim.contribution_band
            assert row["direction_relation"] == {
                "same": "同向", "opposite": "反向", "one_near_zero": "一方近零", "both_near_zero": "双方近零",
            }[dim.direction_relation]
    _check_projection(dp, ds, d10.feature_observations)
    _check_projection(rp, rs, river.feature_observations)
    for payload in (dp, rp):
        assert payload["selection"]["displayed_count"] == len(payload["windows"])
        assert payload["selection"]["comparable_count"] == 7
        for pair in payload["candidate_relations"]:
            a, b = payload["windows"][pair["a"]], payload["windows"][pair["b"]]
            assert pair["overlap"] == (max(a[0], b[0]) <= min(a[1], b[1]))
    assert set(dp["windows"]).isdisjoint(rp["windows"])


@pytest.mark.parametrize("labels", [{"x": "y"}, {"x": "same", "y": "same"}, {"x": "windows", "y": "current"}])
def test_feature_labels_cannot_overwrite_identity_or_schema(labels):
    daily = [{**r, "y": r["x"] * 2} for r in _rows([0, 1, 2] * 10)]
    result = lens.build_lens(daily, ("x", "y"), current=("2025-01-25", "2025-01-30"),
        candidates=[("x", "2025-01-01", "2025-01-06")], labels=labels)
    payload = _model_json(lens.lens_block(result))
    ref = next(iter(payload["windows"]))
    _check_projection(payload, {"current": result.current, ref: result.candidates[0].signature}, result.feature_observations)
    assert payload["windows"][ref] == ["2025-01-01", "2025-01-06"]
    assert _table_rows(payload["candidates"], [payload["candidates"]["windows"][ref]])[0]["label"] == "x"


def test_projection_keeps_direction_relation_before_display_rounding():
    from dataclasses import replace

    result = lens.build_lens(_rows([0, 1, 2] * 10), ("x",), current=("2025-01-25", "2025-01-30"),
        candidates=[("same", "2025-01-01", "2025-01-06")])
    result.current = regime.RegimeSignature({"x": (0.0, -0.30001)})
    candidate = regime.RegimeSignature({"x": (0.0, 0.30001)})
    result.candidates[0] = replace(result.candidates[0], signature=candidate,
        decomposition=lens.decompose(result.current, candidate, 1))
    payload = result.model_payload()
    ref = next(iter(payload["windows"]))
    row = _table_rows(payload["signatures"], payload["signatures"]["windows"][ref])[0]
    assert row["end_segment_delta"] == 0.3  # 显示舍入不能反向修改已算方向
    assert row["direction_relation"] == "反向"


@pytest.mark.parametrize("sample,day", [("normal", "2025-04-01"), ("normal", "2025-04-10"), ("changed-gap", "2025-04-02")])
def test_complete_pair_fits_existing_b_registry_budget(tmp_path, sample, day):
    from intelligence.history_context_cli import history_payload, encode_payload
    from intelligence.services import answer_model
    from intelligence.tests.test_river_history_consumption import _offline_ask, _apply_changed_gap, QUESTION

    db = tmp_path / "synthetic.duckdb"
    _make_db(db)
    if sample == "changed-gap":
        _apply_changed_gap(db)
    with pytest.MonkeyPatch.context() as patch:
        result = _offline_ask(db, tmp_path, patch, options_date=day)
    registry = answer_model.grounded_claim_registry_block(result.answer_spec, query=QUESTION, max_chars=12_000,
        required_claim_ids=("data:D10:context",))
    claim = next(json.loads(line) for line in registry.splitlines() if json.loads(line).get("claim_id") == "data:D10:context")
    payload = history_payload(db, as_of=day)
    assert len(registry) <= 12_000
    assert len(encode_payload(payload).encode()) <= 48_000
    for block in payload["blocks"]:
        assert block["detail"] in claim["text"]
    if sample == "changed-gap":
        d10, river = [_model_json(b["detail"]) for b in payload["blocks"]]
        assert d10["current_gap_days"]["涨家数"] == river["current_gap_days"]["涨家数"] == 0
        assert len(d10["windows"]) == 2 and len(river["windows"]) == 3
        assert d10["candidate_relations"][0]["overlap"] is False
        assert sum(p["overlap"] for p in river["candidate_relations"]) == 2
