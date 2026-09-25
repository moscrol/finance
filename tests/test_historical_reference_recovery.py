"""Synthetic evidence exercises the dated rule without reading private archives."""
from copy import deepcopy
from datetime import datetime
from decimal import Inexact, ROUND_DOWN, Rounded, localcontext
import json

import pytest

from market_feature_store.historical_reference_recovery import CODES, DAY, PREVIOUS, adjudicate_20260922
from market_feature_store.hithink_recovery_candidate import CandidateRefused


@pytest.fixture
def inputs():
    values = [(57., 58.49, 56.65, 57.86, 24936505., 1441598299.84),
              (267.76, 580., 252.67, 433., 7862089., 2339147535.4),
              (60.9, 150., 54.86, 132., 11234751., 772332912.08)]
    bars = [{"stock_ts_code": code, "trade_date": DAY,
             **dict(zip(("open", "high", "low", "close", "volume", "turnover"), row, strict=True)),
             "adjusted": "none", "source": "hithink:daily-k-10d", "updated_at": datetime(2026, 9, 22, 19)}
            for code, row in zip(CODES, values, strict=True)]
    witnesses = [{"stock_ts_code": bar["stock_ts_code"], "trade_date": str(DAY),
                  **{key: bar[key] for key in ("open", "high", "low", "close", "volume")},
                  "amount": round(bar["turnover"]), "source": "sina:historical:unadjusted",
                  "raw_sha256": str(i + 1) * 64}
                 for i, bar in enumerate(bars)]
    witnesses[0].update(prevclose=56.86, postVol=7805, postAmt=451597)
    witnesses[1].update(prevclose=55.28, postVol=901, postAmt=390133)
    bars.append({**bars[0], "trade_date": PREVIOUS, "open": 82., "high": 83., "low": 80.,
                 "close": 82.45, "volume": 100., "turnover": 8245.})
    actions = [{"stock_ts_code": CODES[0], "ex_date": DAY, "dividend_per_share": 0.,
                "per_share_bonus": 0.45, "allotment_ratio": 0., "allotment_price": 0.,
                "currency": "CNY", "source": "hithink:adjustment-factors", "updated_at": datetime(2026, 9, 22, 19)}]
    listings = [{"stock_ts_code": code, "listing_date": str(DAY), "offer_price": price,
                 "source": "sina:ipo-page", "raw_sha256": str(i + 4) * 64}
                for i, (code, price) in enumerate(zip(CODES[1:], (55.28, 15.67), strict=True))]
    return {"bars": bars, "actions": actions, "witnesses": witnesses, "listings": listings}


def test_only_two_references_are_accepted_without_shrinking_the_denominator(inputs):
    before = deepcopy(inputs)
    result = adjudicate_20260922(**inputs)
    assert inputs == before
    assert result["requested_stock_count"] == 3 and result["reference_accepted_count"] == 2
    first, ipo = result["observations"]
    assert (first["pre_close"], first["pct_chg"], first["amount"], first["volume"]) == (56.86, 1.76, 14.416, 249365.)
    assert (ipo["pre_close"], ipo["pct_chg"], ipo["amount"], ipo["volume"]) == (55.28, 683.29, 23.3915, 78621.)
    assert all(row["stock_name"] is None and row["turnover"] is None for row in result["observations"])
    assert not any(row["post_market_values_added"] for row in result["observations"])
    assert result["gaps"] == [{"stock_ts_code": CODES[2], "reasons": ["missing-explicit-dated-reference"],
                               "observed_offer_price": 15.67, "offer_price_substituted": False}]
    for key in ("reference_complete", "canonical_rows_ready", "production_ready", "database_writes",
                "publication_attempted", "official_listing_status_verified"):
        assert result[key] is False
    assert "rows" not in result
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("collection", ["bars", "actions", "witnesses", "listings"])
@pytest.mark.parametrize("change", ["missing", "duplicate", "foreign"])
def test_rejects_changed_or_duplicate_scope(inputs, collection, change):
    rows = inputs[collection]
    if change == "missing":
        rows.pop(0)
    elif change == "duplicate":
        rows.append(deepcopy(rows[0]))
    else:
        rows[0]["stock_ts_code"] = "600001.SH"
    with pytest.raises(CandidateRefused):
        adjudicate_20260922(**inputs)


@pytest.mark.parametrize("collection,field", [("bars", "trade_date"), ("actions", "ex_date"),
                                               ("witnesses", "trade_date"), ("listings", "listing_date")])
def test_rejects_stale_or_future_witness_dates(inputs, collection, field):
    inputs[collection][0][field] = "2026-09-23"
    with pytest.raises(CandidateRefused):
        adjudicate_20260922(**inputs)


@pytest.mark.parametrize("field,value", [("open", 58.), ("close", 58.), ("volume", 24936506.),
                                         ("amount", 1441598301.), ("volume", True), ("amount", float("nan"))])
def test_cross_source_conflicts_are_rejected(inputs, field, value):
    inputs["witnesses"][0][field] = value
    with pytest.raises(CandidateRefused, match="cross-source"):
        adjudicate_20260922(**inputs)


@pytest.mark.parametrize("field,value", [("dividend_per_share", 0.1), ("per_share_bonus", 0.46),
                                         ("allotment_ratio", 0.1), ("allotment_price", 5.),
                                         ("per_share_bonus", True), ("per_share_bonus", float("nan"))])
def test_noncash_exception_does_not_admit_other_corporate_actions(inputs, field, value):
    inputs["actions"][0][field] = value
    with pytest.raises(CandidateRefused, match="named pure bonus"):
        adjudicate_20260922(**inputs)


@pytest.mark.parametrize("value", [None, 0, -1, True, "56.86", float("nan"), float("inf"), 56.861, 56.85])
def test_reference_must_be_explicit_finite_and_match_the_formula(inputs, value):
    inputs["witnesses"][0]["prevclose"] = value
    with pytest.raises(CandidateRefused):
        adjudicate_20260922(**inputs)


def test_changed_previous_close_is_not_hidden_by_a_valid_current_witness(inputs):
    inputs["bars"][-1]["close"] = 82.55
    with pytest.raises(CandidateRefused, match="bonus reference"):
        adjudicate_20260922(**inputs)


def test_ipo_offer_price_cannot_replace_missing_explicit_prevclose(inputs):
    inputs["witnesses"][1].pop("prevclose")
    with pytest.raises(CandidateRefused, match="reference price"):
        adjudicate_20260922(**inputs)


def test_new_beijing_reference_requires_new_review(inputs):
    inputs["witnesses"][2]["prevclose"] = 15.67
    with pytest.raises(CandidateRefused, match="unreviewed Beijing"):
        adjudicate_20260922(**inputs)


def test_missing_previous_bar_cannot_classify_another_security_as_ipo(inputs):
    inputs["bars"].pop()
    with pytest.raises(CandidateRefused, match="not IPO proof"):
        adjudicate_20260922(**inputs)


def test_does_not_synthesize_a_previous_bar_for_the_ipo(inputs):
    inputs["bars"].append({**inputs["bars"][1], "trade_date": PREVIOUS, "close": 55.28})
    with pytest.raises(CandidateRefused, match="bar scope"):
        adjudicate_20260922(**inputs)


@pytest.mark.parametrize("collection,field,value", [
    ("bars", "adjusted", "qfq"), ("bars", "source", "canonical:old"),
    ("bars", "updated_at", "2026-09-22"), ("actions", "currency", "USD"),
    ("actions", "source", "unverified"), ("actions", "updated_at", None),
    ("witnesses", "source", "sina:current"), ("witnesses", "raw_sha256", "not-a-hash"),
    ("listings", "source", "exchange:announcement"), ("listings", "raw_sha256", None),
    ("listings", "offer_price", 55.29), ("listings", "offer_price", True),
])
def test_rejects_unqualified_provenance_or_listing_claims(inputs, collection, field, value):
    inputs[collection][0][field] = value
    with pytest.raises(CandidateRefused):
        adjudicate_20260922(**inputs)


def test_post_market_values_are_not_added_again(inputs):
    inputs["witnesses"][0]["volume"] += inputs["witnesses"][0]["postVol"]
    with pytest.raises(CandidateRefused, match="cross-source"):
        adjudicate_20260922(**inputs)


def test_order_invariant_fingerprint_binds_unused_evidence(inputs):
    expected = adjudicate_20260922(**inputs)
    for rows in inputs.values():
        rows.reverse()
    assert adjudicate_20260922(**inputs) == expected
    inputs["witnesses"][0]["raw_sha256"] = "f" * 64
    changed = adjudicate_20260922(**inputs)
    assert changed["input_fingerprint"] != expected["input_fingerprint"]
    assert changed["adjudication_fingerprint"] != expected["adjudication_fingerprint"]
    assert changed["observations"] == expected["observations"]


def test_decimal_context_cannot_change_the_result(inputs):
    expected = adjudicate_20260922(**inputs)
    with localcontext() as context:
        context.prec, context.rounding, context.Emax = 2, ROUND_DOWN, 2
        context.traps[Inexact] = context.traps[Rounded] = True
        assert adjudicate_20260922(**inputs) == expected


@pytest.mark.parametrize("mode", ["quote", "candidate"])
def test_adjudication_is_not_a_manifest_for_either_preparation_mode(inputs, tmp_path, mode):
    import hashlib
    from scripts import dated_quote_recovery, historical_candidate_recovery

    path = tmp_path / "not-a-preparation-manifest.json"
    raw = json.dumps(adjudicate_20260922(**inputs)).encode()
    path.write_bytes(raw)
    loader = dated_quote_recovery if mode == "quote" else historical_candidate_recovery
    with pytest.raises(ValueError, match="contract|manifest"):
        loader.load_manifest(path, hashlib.sha256(raw).hexdigest())


def test_no_file_database_or_network_io(inputs, monkeypatch):
    import builtins
    import socket
    import duckdb

    def forbidden(*args, **kwargs):
        pytest.fail("pure adjudication attempted IO")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(duckdb, "connect", forbidden)
    assert adjudicate_20260922(**inputs)["reference_accepted_count"] == 2
