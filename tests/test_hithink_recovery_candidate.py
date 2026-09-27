"""Synthetic inputs only: no providers, databases, credentials or real captures."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
from decimal import Inexact, ROUND_DOWN, Rounded, localcontext
import json

import pytest

from market_feature_store.hithink_recovery_candidate import (
    CANDIDATE_20260921, CandidateRefused, RecoverySpec, Resumption, RoundingDifference,
    build_candidate, scope_fingerprint,
)

TD, PREV = date(2026, 9, 21), date(2026, 9, 18)
CODE, STOP, RESUME = "600001.SH", "300082.SZ", "600825.SH"


def bar(code=CODE, day=TD, close=10.25):
    return {"stock_ts_code": code, "trade_date": day, "open": 10., "high": 11., "low": 9.,
            "close": close, "volume": 1234567., "turnover": 12345500.,
            "adjusted": "none", "source": "hithink:daily-k-10d", "updated_at": datetime(2026, 9, 22)}


def quote(code=CODE):
    return {"name": "Captured Name", "quote_timestamp": "20260921161401", "open": 10., "high": 11.,
            "low": 9., "close": 10.25, "pre_close": 10., "pct_chg": 2.5,
            "volume_shares": 1234567., "amount_yuan": 12345500., "turnover_pct": 2.2,
            "raw_volume_unit": "shares" if code.startswith(("688", "689")) else "hands"}


def event(code, start="2026-09-21 09:30:00", end=None, resume=None):
    return {"SECUCODE": code, "SECURITY_CODE": code[:6], "SECURITY_TYPE_CODE": "058001001",
            "SUSPEND_START_TIME": start, "SUSPEND_END_TIME": end, "PREDICT_RESUME_DATE": resume}


def action(code=CODE, day=TD, cash=0.5):
    return {"stock_ts_code": code, "ex_date": day, "dividend_per_share": cash, "per_share_bonus": 0.,
            "allotment_ratio": 0., "allotment_price": 0., "currency": "CNY",
            "source": "hithink:adjustment-factors", "updated_at": datetime(2026, 9, 22)}


@pytest.fixture
def inputs():
    spec = RecoverySpec(TD, scope_fingerprint(TD, [CODE]), (), (), ())
    return {"spec": spec, "stock_codes": [CODE], "bars": [bar(day=PREV, close=10.), bar()],
            "actions": [], "quotes": {CODE: quote()}, "suspensions": [], "historical_witnesses": []}


def add_suspended(inputs):
    inputs["stock_codes"].append(STOP)
    inputs["spec"] = replace(inputs["spec"], scope_sha256=scope_fingerprint(TD, inputs["stock_codes"]),
                             suspended_codes=(STOP,))
    inputs["quotes"][STOP] = {**quote(), "open": 0., "high": 0., "low": 0., "close": 10.,
                             "volume_shares": 0., "amount_yuan": 0., "pct_chg": 0., "turnover_pct": 0.}
    inputs["suspensions"].append(event(STOP))


def add_resumption(inputs):
    ref = Resumption(RESUME, date(2026, 9, 4), 10., date(2026, 9, 7))
    inputs["stock_codes"].append(RESUME)
    inputs["spec"] = replace(inputs["spec"], scope_sha256=scope_fingerprint(TD, inputs["stock_codes"]),
                             resumptions=(ref,))
    inputs["bars"] += [bar(RESUME, ref.last_trade_date, 10.), bar(RESUME)]
    inputs["quotes"][RESUME] = quote()
    inputs["suspensions"].append(event(RESUME, "2026-09-07 09:30:00", "2026-09-18 15:00:00", "2026-09-21 00:00:00"))
    inputs["historical_witnesses"].append({"stock_ts_code": RESUME, "trade_date": ref.last_trade_date,
        "open": 10., "high": 11., "low": 9., "close": 10., "volume": 1234567., "amount": 12345500.,
        "source": "sina:historical:unadjusted", "raw_sha256": "a" * 64})


def test_reuses_units_and_never_grants_write_authority(inputs):
    add_suspended(inputs)
    add_resumption(inputs)
    original = deepcopy(inputs)
    result = build_candidate(**inputs)
    assert inputs == original
    assert result["candidate_constructed"] is True
    assert result["declared_scope_count"] == 3
    assert result["candidate_row_count"] == 2 and result["excluded_count"] == 1
    assert result["exclusions"] == [{"stock_ts_code": STOP, "reason": "provider_suspension_and_zero_activity",
                                      "synthetic_bar": False, "official_status_verified": False}]
    row = result["rows"][0]
    assert (row["amount"], row["volume"], row["pct_chg"]) == (0.1235, 12346., 2.5)
    assert row["stock_name"] == "Captured Name" and row["name_observed_at"] == "20260921161401"
    assert row["turnover"] is None and row["observed_turnover_pct"] == 2.2
    assert result["rows"][1]["previous_observation_date"] == "2026-09-04"
    assert result["rows"][1]["reference_basis"] == "named_resumption_no_recorded_interval_action"
    for field in ("production_ready", "database_writes", "publication_attempted"):
        assert result[field] is False
    assert "nontrading_denominator_policy" in result["blockers"]
    assert "adjustment_completeness_unverified" in result["blockers"]
    json.dumps(result, allow_nan=False)


def test_no_file_network_or_database_side_effects(inputs, monkeypatch):
    import builtins
    import socket
    import duckdb

    def forbidden(*args, **kwargs):
        pytest.fail("candidate construction attempted IO")

    add_resumption(inputs)
    add_suspended(inputs)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(duckdb, "connect", forbidden)
        assert build_candidate(**inputs)["candidate_constructed"]


def test_fixed_september_contract_is_not_the_september_11_writer():
    assert CANDIDATE_20260921.trade_date == TD
    assert CANDIDATE_20260921.scope_sha256 == "f4e2568884bcfdc2bf0f80681995f76faaed813527bc9f61d88c426cdf276cd7"
    assert len(CANDIDATE_20260921.suspended_codes) == 12
    assert "605303.SH" in CANDIDATE_20260921.suspended_codes
    assert CANDIDATE_20260921.resumptions == (
        Resumption("600301.SH", date(2026, 9, 11), 45.43, date(2026, 9, 14)),
        Resumption("600825.SH", date(2026, 9, 4), 5.31, date(2026, 9, 7)),
    )


def test_fingerprint_alone_binds_the_declared_scope(inputs):
    inputs["spec"] = replace(inputs["spec"], scope_sha256="0" * 64)
    with pytest.raises(CandidateRefused, match="scope fingerprint changed"):
        build_candidate(**inputs)


def test_order_independent_and_fingerprint_binds_evidence(inputs):
    add_resumption(inputs)
    expected = build_candidate(**inputs)
    for key in ("stock_codes", "bars", "historical_witnesses"):
        inputs[key].reverse()
    assert build_candidate(**inputs) == expected
    inputs["bars"][0]["updated_at"] = datetime(2026, 9, 22, 1)
    changed = build_candidate(**inputs)
    assert changed["input_fingerprint"] != expected["input_fingerprint"]
    assert changed["candidate_fingerprint"] != expected["candidate_fingerprint"]


@pytest.mark.parametrize("change", ["date", "scope", "extra_quote", "missing_quote", "missing_current", "missing_previous"])
def test_closed_scope_and_adjacent_day_requirements(inputs, change):
    if change == "date":
        inputs["spec"] = replace(inputs["spec"], trade_date=date(2026, 9, 22))
    elif change == "scope":
        inputs["stock_codes"].append(STOP)
    elif change == "extra_quote":
        inputs["quotes"][STOP] = quote()
    elif change == "missing_quote":
        inputs["quotes"].clear()
    else:
        inputs["bars"].pop(1 if change == "missing_current" else 0)
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)


@pytest.mark.parametrize("field,value", [
    ("missing", None), ("quote_timestamp", "20261321161400"),
    ("quote_timestamp", "20260922161400"), ("quote_timestamp", "20260921145959"),
    ("quote_timestamp", "2026921161400"), ("name", ""), ("name", "a\nb"),
    ("close", float("nan")), ("pre_close", 0), ("high", float("inf")), ("open", None),
    ("volume_shares", -1), ("volume_shares", 0.5), ("volume_shares", 0),
    ("turnover_pct", True), ("pct_chg", float("nan")), ("raw_volume_unit", "shares"),
    ("amount_yuan", 12345502.), ("volume_shares", 1234767.), ("pct_chg", 2.51), ("close", 10.26),
])
def test_quote_failures_are_not_tolerated(inputs, field, value):
    if field == "missing":
        del inputs["quotes"][CODE]["name"]
    else:
        inputs["quotes"][CODE][field] = value
    with pytest.raises((CandidateRefused, ValueError)):
        build_candidate(**inputs)


@pytest.mark.parametrize("collection", ["bars", "actions", "suspensions", "historical_witnesses"])
def test_duplicate_inputs_rejected(inputs, collection):
    add_resumption(inputs)
    if collection == "actions":
        inputs["actions"].append(action(day=PREV))
    inputs[collection].append(deepcopy(inputs[collection][0]))
    with pytest.raises(CandidateRefused, match="duplicate"):
        build_candidate(**inputs)


@pytest.mark.parametrize("field,value", [
    ("SECURITY_TYPE_CODE", "B-share"), ("SECURITY_CODE", "600000"),
    ("SUSPEND_START_TIME", "2026-09-21 13:00:00"), ("SUSPEND_START_TIME", "2026-09-22 09:30:00"),
    ("SUSPEND_END_TIME", "2026-09-21 14:59:59"), ("SUSPEND_START_TIME", "2026-09-21 09:30:00+08:00"),
])
def test_suspension_requires_full_session_and_matching_security(inputs, field, value):
    add_suspended(inputs)
    inputs["suspensions"][0][field] = value
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)


@pytest.mark.parametrize("change", ["no_event", "activity", "synthetic_bar", "unlisted_missing", "stale_quote"])
def test_missing_bars_cannot_disappear_or_be_synthesized(inputs, change):
    add_suspended(inputs)
    if change == "no_event":
        inputs["suspensions"].clear()
    elif change == "activity":
        inputs["quotes"][STOP]["amount_yuan"] = 1
    elif change == "synthetic_bar":
        inputs["bars"].append(bar(STOP))
    elif change == "unlisted_missing":
        inputs["spec"] = replace(inputs["spec"], suspended_codes=())
    else:
        inputs["quotes"][STOP]["quote_timestamp"] = "20260918161401"
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)


@pytest.mark.parametrize("change", ["action", "gap_bar", "no_witness", "witness_close", "witness_source", "witness_hash",
                                    "previous_close", "predicted_resume", "interval_start", "interval_end", "no_event",
                                    "unexplained_day", "no_previous", "extra_witness", "witness_volume", "witness_amount"])
def test_named_resumption_is_not_generic_backwards_lookup(inputs, change):
    add_resumption(inputs)
    if change == "action":
        inputs["actions"].append(action(RESUME, date(2026, 9, 10)))
    elif change == "gap_bar":
        inputs["bars"].append(bar(RESUME, PREV))
    elif change == "no_witness":
        inputs["historical_witnesses"].clear()
    elif change.startswith("witness_"):
        key, value = {"witness_close": ("close", 9.), "witness_source": ("source", "canonical"),
                      "witness_hash": ("raw_sha256", "changed"), "witness_volume": ("volume", 1234566.),
                      "witness_amount": ("amount", 12345502.)}[change]
        inputs["historical_witnesses"][0][key] = value
    elif change == "previous_close":
        inputs["bars"][-2]["close"] = 10.01
    elif change == "predicted_resume":
        inputs["suspensions"][0]["PREDICT_RESUME_DATE"] = "2026-09-22 00:00:00"
    elif change == "interval_start":
        inputs["suspensions"][0]["SUSPEND_START_TIME"] = "2026-09-08 09:30:00"
    elif change == "interval_end":
        inputs["suspensions"][0]["SUSPEND_END_TIME"] = "2026-09-21 15:00:00"
    elif change == "no_event":
        inputs["suspensions"].clear()
    elif change == "no_previous":
        inputs["bars"].pop(-2)
    elif change == "extra_witness":
        inputs["historical_witnesses"].append({**inputs["historical_witnesses"][0], "stock_ts_code": CODE})
    else:
        ref = replace(inputs["spec"].resumptions[0], last_trade_date=date(2026, 9, 3))
        inputs["spec"] = replace(inputs["spec"], resumptions=(ref,))
        inputs["historical_witnesses"][0]["trade_date"] = ref.last_trade_date
        inputs["bars"][-2]["trade_date"] = ref.last_trade_date
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)


@pytest.mark.parametrize("collection,field", [
    ("suspensions", "SECUCODE"), ("suspensions", "PREDICT_RESUME_DATE"),
    ("historical_witnesses", "stock_ts_code"), ("historical_witnesses", "amount"),
])
def test_missing_resumption_fields_have_contract_failure(inputs, collection, field):
    add_resumption(inputs)
    del inputs[collection][0][field]
    with pytest.raises(CandidateRefused, match="missing"):
        build_candidate(**inputs)


@pytest.mark.parametrize("collection,field,value", [
    ("bars", "trade_date", "2026-13-18"),
    ("suspensions", "SUSPEND_START_TIME", "invalid"),
    ("historical_witnesses", "raw_sha256", None),
])
def test_malformed_resumption_values_have_contract_failure(inputs, collection, field, value):
    add_resumption(inputs)
    inputs[collection][0][field] = value
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)


def test_cash_action_set_is_named_not_counted(inputs):
    inputs["spec"] = replace(inputs["spec"], adjustment_codes=(CODE,))
    inputs["actions"].append(action())
    inputs["bars"][-1]["close"] = 9.69
    inputs["quotes"][CODE].update(close=9.69, pre_close=9.5, pct_chg=2.)
    result = build_candidate(**inputs)
    assert result["rows"][0]["reference_basis"] == "cash_dividend_reference"
    assert result["rows"][0]["pre_close"] == 9.5
    inputs["actions"].clear()
    with pytest.raises(CandidateRefused, match="adjustment set"):
        build_candidate(**inputs)


@pytest.mark.parametrize("field,value", [("per_share_bonus", .1), ("currency", "USD"),
                                         ("dividend_per_share", None), ("source", "snapshot")])
def test_unsupported_or_unknown_actions_refuse(inputs, field, value):
    inputs["spec"] = replace(inputs["spec"], adjustment_codes=(CODE,))
    inputs["actions"].append(action())
    inputs["actions"][0][field] = value
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)


@pytest.mark.parametrize("code", ["688001.SH", "689009.SH"])
def test_share_unit_is_exact(inputs, code):
    inputs["stock_codes"] = [code]
    inputs["spec"] = replace(inputs["spec"], scope_sha256=scope_fingerprint(TD, [code]))
    inputs["bars"] = [{**row, "stock_ts_code": code} for row in inputs["bars"]]
    inputs["quotes"] = {code: quote(code)}
    assert build_candidate(**inputs)["candidate_row_count"] == 1
    inputs["quotes"][code]["volume_shares"] += 1
    with pytest.raises(CandidateRefused, match="volume mismatch"):
        build_candidate(**inputs)


def test_price_range_detects_joint_volume_error(inputs):
    inputs["bars"][-1]["volume"] *= 100
    inputs["quotes"][CODE]["volume_shares"] *= 100
    with pytest.raises(CandidateRefused, match="price range"):
        build_candidate(**inputs)


def tie_inputs(inputs, close, pre, pct, quoted):
    for row in inputs["bars"]:
        row.update(open=close, high=200., low=1., close=close, turnover=123456700.)
    inputs["bars"][0]["close"] = pre
    inputs["quotes"][CODE].update(open=close, high=200., low=1., close=close, pre_close=pre,
                                  pct_chg=quoted, amount_yuan=123456700.)
    inputs["spec"] = replace(inputs["spec"], rounding_differences=(RoundingDifference(CODE, close, pre, pct, quoted),))


@pytest.mark.parametrize("close,pre,pct,quoted", [(21.08, 21.76, -3.13, -3.12), (167.96, 160., 4.98, 4.97)])
def test_only_named_exact_half_cent_differences_are_preserved(inputs, close, pre, pct, quoted):
    tie_inputs(inputs, close, pre, pct, quoted)
    result = build_candidate(**inputs)
    assert result["rows"][0]["pct_chg"] == pct
    with localcontext() as ctx:
        ctx.prec = 6
        ctx.rounding = ROUND_DOWN
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        assert build_candidate(**inputs) == result
    inputs["spec"] = replace(inputs["spec"], rounding_differences=())
    with pytest.raises(CandidateRefused, match="unapproved"):
        build_candidate(**inputs)


def test_a_one_cent_difference_is_not_automatically_rounding(inputs):
    tie_inputs(inputs, 10.25, 10., 2.5, 2.49)
    with pytest.raises(CandidateRefused, match="not a one-cent rounding tie"):
        build_candidate(**inputs)


def test_unused_rounding_whitelist_rejected(inputs):
    inputs["spec"] = replace(inputs["spec"], rounding_differences=(RoundingDifference(CODE, 10.25, 10., 2.5, 2.49),))
    with pytest.raises(CandidateRefused, match="unused rounding"):
        build_candidate(**inputs)


@pytest.mark.parametrize("field,value", [("missing", None), ("source", "eastmoney:snapshot"), ("adjusted", "qfq"),
                                         ("close", float("nan")), ("volume", 0), ("updated_at", None)])
def test_bad_bar_provenance_and_numbers_refuse(inputs, field, value):
    if field == "missing":
        del inputs["bars"][-1]["close"]
    else:
        inputs["bars"][-1][field] = value
    with pytest.raises(CandidateRefused):
        build_candidate(**inputs)
