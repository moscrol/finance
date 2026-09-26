"""Launch-rule comparison: the controls are windows that did not launch back then.

Picking today's winners and reading their launch features back is survivorship
bias. These tests pin the opposite: one versioned rule labels every declared
window, non-launches stay in the denominator, and undecidable windows are never
silently demoted into "did not launch".
"""

from datetime import date

import duckdb
import pytest

from intelligence.services.historical_research.anatomy import (
    ANATOMY_VERSION,
    LAUNCH_RULE,
    WARMUP,
)
from intelligence.services.historical_research.query import (
    HistoryQuery,
    HistoryQueryError,
    HistoryQuerySpec,
)
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from tests.test_history_market_anatomy import anatomy_db as _anatomy_db


@pytest.fixture
def anatomy_db(tmp_path):
    return _anatomy_db.__wrapped__(tmp_path)


def compare(path, **changes):
    args = dict(
        operation="compare_cases",
        entity_kind="sector",
        entity_codes=["A.FP", "B.FP"],
        start="2026-01-05",
        end="2026-01-11",
        search_start="2026-01-05",
        search_end="2026-01-29",
        window_days=7,
        step_days=7,
        features=["return_pct", "amount_vs_prior_mean"],
        preview_limit=25,
        condition={"rule": LAUNCH_RULE},
        outcome={"horizon_days": 3, "threshold_pct": 0},
    )
    args.update(changes)
    return HistoryQuery(path).run(
        HistoryQuerySpec.from_arguments(args),
        information_cutoff=InformationCutoff(date(2026, 1, 29), "requested"),
        deadline=ResearchDeadline.from_timeout(20),
    )


def window(result, code, start):
    return next(
        r for r in result["rows"] if r["entity_code"] == code and r["start"] == start
    )


def test_control_windows_are_kept_and_the_denominator_stays_whole(anatomy_db):
    result = compare(anatomy_db)
    launched = window(result, "A.FP", "2026-01-05")
    control = window(result, "B.FP", "2026-01-05")
    assert launched["launch_state"] == "observed"
    assert launched["launch_date"] == "2026-01-10"
    assert launched["x"] is True
    # Same window, same rule, no launch: this is the control, not an exclusion.
    assert control["launch_state"] == "not_observed"
    assert control["launch_date"] is None
    assert control["x"] is False
    comparison = result["comparison"]
    assert sum(comparison["four_cells"].values()) + comparison["missing"] + comparison[
        "immature"
    ] == comparison["enumerated"] == result["total_matched"]
    assert comparison["launch_states"]["not_observed"] >= 1
    assert sum(comparison["launch_states"].values()) == comparison["enumerated"]
    assert comparison["independence_status"] == "not_established"
    assert comparison["certification_eligible"] is False
    assert result["promotion_eligible"] is False


def test_launch_label_matches_trace_history_on_the_same_dates(anatomy_db):
    traced = HistoryQuery(anatomy_db).run(
        HistoryQuerySpec.from_arguments(dict(
            operation="trace_history", entity_kind="sector",
            entity_codes=["A.FP"], start="2026-01-05", end="2026-01-11",
        )),
        information_cutoff=InformationCutoff(date(2026, 1, 29), "requested"),
        deadline=ResearchDeadline.from_timeout(20),
    )
    signal = next(r for r in traced["rows"] if r["record_kind"] == "launch_signal")
    compared = window(compare(anatomy_db), "A.FP", "2026-01-05")
    assert signal["signal_date"] == compared["launch_date"] == "2026-01-10"
    assert signal["signal_status"] == compared["launch_state"] == "observed"


def test_undecidable_window_is_not_counted_as_a_control(anatomy_db):
    with duckdb.connect(str(anatomy_db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET diff_ratio=NULL "
            "WHERE sector_ts_code='A.FP' AND trade_date='2026-01-10'"
        )
    row = window(compare(anatomy_db), "A.FP", "2026-01-05")
    assert row["launch_state"] == "missing"
    assert row["x"] is None
    assert row["comparison_state"] == "missing_feature"
    assert row["launch_unknown_days"] >= 1
    comparison = compare(anatomy_db)["comparison"]
    assert comparison["launch_states"].get("missing", 0) >= 1
    assert "not_observed" not in {
        r["launch_state"]
        for r in compare(anatomy_db)["rows"]
        if r["entity_code"] == "A.FP" and r["start"] == "2026-01-05"
    }
    assert "comparison:missing_feature" in compare(anatomy_db)["gaps"]


def test_rule_never_looks_back_before_the_window_it_judges(anatomy_db):
    # B.FP launches on 2026-01-15, inside the warmup prefix of this window.
    result = compare(anatomy_db, search_start="2026-01-12", search_end="2026-01-18",
                     start="2026-01-12", end="2026-01-18")
    row = window(result, "B.FP", "2026-01-12")
    assert row["launch_state"] == "not_observed"
    assert row["launch_date"] is None
    definition = result["feature_definitions"][LAUNCH_RULE]
    assert definition["warmup_days"] == WARMUP
    assert "No lookback expansion" in definition["rule"]


def test_the_rule_that_labelled_x_travels_with_the_artifact(anatomy_db):
    result = compare(anatomy_db)
    assert f"{LAUNCH_RULE}@{ANATOMY_VERSION}" in result["definition_refs"]
    assert result["analysis_definition"]["version"] == ANATOMY_VERSION
    assert "not_observed=control" in result["analysis_definition"]["states"]
    assert "undecidable" in result["analysis_definition"]["states"]
    assert "x=null undecidable" in result["comparison"]["x_definition"]
    assert result["spec"]["condition"] == {"rule": LAUNCH_RULE}
    # A different rule version must not reuse this selection fingerprint.
    assert result["selection_fingerprint"] != compare(
        anatomy_db, condition={"feature": "return_pct", "op": "gte", "value": 0}
    )["selection_fingerprint"]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"window_days": WARMUP, "step_days": WARMUP}, "warmup dates inside"),
        ({"operation": "compute_history"}, "belongs to compare_cases"),
        ({"condition": {"rule": "made_up_rule"}}, "only rule condition"),
        ({"condition": {"rule": LAUNCH_RULE, "op": "gte"}}, "unsupported_definition"),
    ],
)
def test_rule_condition_refuses_shapes_it_cannot_honour(anatomy_db, changes, message):
    with pytest.raises(HistoryQueryError, match=message):
        compare(anatomy_db, **changes)


def test_market_has_no_launch_rule(anatomy_db):
    with pytest.raises(HistoryQueryError, match="sector/stock, not market"):
        compare(anatomy_db, entity_kind="market", entity_codes=["000001.SH"],
                features=["return_pct"])
