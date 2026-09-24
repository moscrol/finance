from copy import deepcopy

import pytest

from scripts.audit_recovery_metadata import assess_metadata

CODE = "600001.SH"


@pytest.fixture
def inputs():
    fields = [""] * 77
    for key, value in {1: "XD示例", 2: "600001", 3: "10", 4: "10", 5: "10", 6: "100",
        30: "20260921150001", 32: "0", 33: "11", 34: "9", 35: "10/100/100000", 38: "1",
        72: "1000000", 73: "3000000", 76: "2000000"}.items():
        fields[key] = value
    return {"candidate": {"trade_date": "2026-09-21", "declared_scope_count": 1,
        "candidate_row_count": 1, "excluded_count": 0, "exclusions": [], "rows": [{
            "stock_ts_code": CODE, "stock_name": "XD示例", "name_observed_at": "20260921150001",
            "name_source": "tencent:captured-dated-quote", "turnover": None,
            "observed_turnover_pct": 1., "pct_chg": 0., "amount": .001}]},
        "raw_batches": [('v_sh600001="' + '~'.join(fields) + '";\n').encode('gbk')],
        "comparison_rows": [{"symbol": "sh600001", "code": "600001", "name": "示例股份公司",
            "turnoverratio": .5, "volume": 10000, "trade": 10, "nmc": 2000}]}


def test_arithmetic_agreement_does_not_select_a_turnover_denominator(inputs):
    before = deepcopy(inputs)
    result = assess_metadata(**inputs)
    assert inputs == before
    assert result["turnover_missing_count"] == 1
    assert result["name_classification_difference_count"] == 0
    assert result["name_differences"][0]["ex_prefix_differs"]
    diff = result["turnover_differences"][0]
    assert diff["both_internally_reproducible"] is True
    assert diff["official_denominator_verified"] is False
    assert diff["raw_quote_denominators"]["72"]["matches_quoted_pct"]
    assert not diff["raw_quote_denominators"]["76"]["matches_quoted_pct"]
    for field in ("production_ready", "database_writes", "publication_attempted", "comparison_has_target_date"):
        assert result[field] is False


def test_st_change_is_not_dismissed_as_cosmetic(inputs):
    inputs["comparison_rows"][0]["name"] = "*ST示例"
    assert assess_metadata(**inputs)["name_classification_difference_count"] == 1


@pytest.mark.parametrize("change", ["duplicate_batch", "duplicate_comparison", "comparison_identity",
    "candidate_name", "candidate_stamp", "candidate_turnover", "candidate_rate", "count", "nan", "stale"])
def test_unbound_or_bad_inputs_refuse(inputs, change):
    if change == "duplicate_batch":
        inputs["raw_batches"] *= 2
    elif change == "duplicate_comparison":
        inputs["comparison_rows"] *= 2
    elif change == "comparison_identity":
        inputs["comparison_rows"][0]["symbol"] = "sz600001"
    elif change.startswith("candidate_"):
        key, val = {"candidate_name": ("stock_name", "旧名"), "candidate_stamp": ("name_observed_at", "20260918"),
            "candidate_turnover": ("turnover", 0), "candidate_rate": ("observed_turnover_pct", 2)}[change]
        inputs["candidate"]["rows"][0][key] = val
    elif change == "count":
        inputs["candidate"]["declared_scope_count"] = 2
    elif change == "nan":
        inputs["comparison_rows"][0]["turnoverratio"] = float("nan")
    else:
        inputs["raw_batches"][0] = inputs["raw_batches"][0].replace(b"20260921150001", b"20260918150001")
    with pytest.raises(ValueError):
        assess_metadata(**inputs)


def test_missing_comparison_is_explicit_not_imputed(inputs):
    inputs["comparison_rows"] = []
    assert assess_metadata(**inputs)["comparison_missing_codes"] == [CODE]


def test_opaque_denominator_fields_are_optional_not_guessed(inputs):
    raw = inputs["raw_batches"][0].decode("gbk")
    inputs["raw_batches"] = [(raw.split('="')[0] + '="' + '~'.join(raw.split('="')[1].split('~')[:58]) + '";\n').encode('gbk')]
    result = assess_metadata(**inputs)
    assert result["turnover_differences"][0]["raw_quote_denominators"]["72"]["raw_denominator"] is None
    assert result["internal_denominator_mismatches"][0]["tencent_field72_matches"] is False


def test_pure_assessment_attempts_no_io(inputs, monkeypatch):
    import builtins
    import socket
    import duckdb

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("unexpected IO")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(duckdb, "connect", forbidden)
    assert assess_metadata(**inputs)["production_ready"] is False
    assert calls == []
