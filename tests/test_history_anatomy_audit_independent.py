"""Hand-authored inputs/answers; never import product formulas or a database.

These tests challenge the second implementation with independent numeric oracles
and re-sealed mutations, rather than trusting product-generated fixtures alone.
"""

from copy import deepcopy
from datetime import date, timedelta

import pytest

from scripts.audit_historical_research_artifacts import _Audit, _calculate, audit_artifact
from scripts.history_anatomy_arithmetic import NEW_DEFINITIONS, TRACE_DEFINITION, _audit_members, _audit_pairs, _path, _signal
from tests.test_history_artifact_audit import seal, write


RETURN = dict(fields=["pct_chg"], unit="percent", rule="compound every daily percentage in the declared window", version="history-features-v1")
RELATIVE = dict(fields=["pct_chg", "market.sh_index_pct_chg"], unit="percentage_points", rule="entity compounded return minus index compounded return over identical days", version="history-features-v1")


def definitions(names, kind):
    out = {}
    for name in names:
        if name in NEW_DEFINITIONS:
            fields, unit, rule = NEW_DEFINITIONS[name]
            item = dict(fields=fields, unit=unit, rule=rule, version="history-anatomy-features-v1")
        else:
            item = deepcopy(RETURN if name == "return_pct" else RELATIVE)
        item["entity_kind"] = kind
        if kind == "market":
            item["input_mapping"] = {"pct_chg": "fact_market_daily.sh_index_pct_chg", "amount": "fact_market_daily.total_amount"}
        out[name] = item
    return out


def document(kind, op, days, codes, inputs, rows, features, **kw):
    return seal(dict(
        schema_version="historical-research-v1",
        spec=dict(operation=op, entity_kind=kind, entity_codes=codes, start=days[0], end=days[-1], features=list(features)),
        feature_definitions=definitions(features, kind),
        inputs=inputs, calendar_inputs=[dict(stock_dates=days, market_dates=days, start=days[0], end=days[-1])],
        rows=rows, total_matched=len(rows), returned_count=1, truncated=len(rows) > 1,
        **kw,
    ))


def feature_row(code, days, features):
    return dict(entity_code=code, start=days[0], end=days[-1], features=features,
                feature_coverage={name: dict(status="complete" if value is not None else "missing", expected_dates=len(days)) for name, value in features.items()})


@pytest.fixture
def market_doc():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    inputs = {"fact_market_daily": [dict(trade_date=d, sh_index_pct_chg=p, total_amount=a, advancers=n, limit_up=u, limit_down=v)
              for d, p, a, n, u, v in zip(days, [10, -20, 5], [100, 200, 450], [100, 200, 300], [10, 20, 30], [9, 6, 3], strict=True)]}
    values = dict(return_pct=-7.6, max_drawdown_pct=20., up_day_share=2/3, amount_vs_prior_mean=3., advancers_mean=200., limit_up_mean=20., limit_down_mean=6.)
    return document("market", "compute_history", days, ["000001.SH"], inputs, [feature_row("000001.SH", days, values)], values)


def test_market_scalars_use_hand_calculated_answers(tmp_path, market_doc):
    assert write(tmp_path / "market.json", market_doc)["result"] == "checked"
    for field in market_doc["rows"][0]["features"]:
        mutated = deepcopy(market_doc)
        mutated["rows"][0]["features"][field] += 1
        receipt = write(tmp_path / "mutated.json", seal(mutated))
        assert receipt["result"] == "error"
        assert field in {e["field"] for e in receipt["errors"]}


def test_new_scalar_missing_and_invalid_inputs_are_not_zero():
    days = ["2026-01-05", "2026-01-06", "2026-01-07"]
    facts = {("A", d): dict(pct_chg=p, amount=a) for d, p, a in zip(days, [10, -20, 5], [100, 200, 450], strict=True)}
    markets = {("", d): dict(total_amount=1000) for d in days}
    value, reason = _calculate("amount_share_change_pp", days, facts, markets, "A")
    assert value == pytest.approx(35) and reason is None
    assert _calculate("amount_vs_prior_mean", days[:1], facts, {}, "A") == (None, "insufficient_history")
    invalid = deepcopy(facts)
    invalid["A", days[0]]["pct_chg"] = -100
    assert _calculate("max_drawdown_pct", days, invalid, {}, "A") == (None, "invalid_return")
    invalid["A", days[0]]["amount"] = -1
    assert _calculate("amount_vs_prior_mean", days, invalid, {}, "A") == (None, "negative_input")
    del invalid["A", days[1]]
    assert _calculate("up_day_share", days, invalid, {}, "A") == (None, "missing_input_dates")
    # A negative change of a positive share remains legal.
    reversed_facts = {("A", d): dict(amount=a) for d, a in zip(days, [450, 200, 100], strict=True)}
    assert _calculate("amount_share_change_pp", days, reversed_facts, markets, "A")[0] == pytest.approx(-35)


@pytest.fixture
def rank_doc():
    days = ["2026-01-05", "2026-01-06"]
    facts = [dict(trade_date=d, stock_ts_code=c, pct_chg=p) for c, returns in [("A", [10, -10]), ("B", [0, 0]), ("C", [1, None])]
             for d, p in zip(days, returns, strict=True)]
    rows = [dict(feature_row(c, days, {"return_pct": value}), rank=rank, population_count=3, selection_mode="posthoc_ranked_observed_universe")
            for c, value, rank in [("B", 0., 1), ("A", -1., 2), ("C", None, None)]]
    return document("stock", "rank_history", days, [], {"fact_stock_daily": facts}, rows, ["return_pct"],
                    universe=dict(enumerated=3, entity_codes=["A", "B", "C"], missing_unranked=1))


def test_rank_full_denominator_order_and_missing_are_independently_checked(tmp_path, rank_doc):
    path = tmp_path / "rank.json"
    receipt = write(path, rank_doc)
    assert receipt["result"] == "partial" and not receipt["errors"]
    assert {s["reason"] for s in receipt["skips"]} == {"missing_or_invalid_input_values"}
    for change, expected in [
        (lambda d: d["rows"].reverse(), "rank_order"),
        (lambda d: d["rows"][0].update(rank=2), "rank"),
        (lambda d: d["universe"].update(missing_unranked=0), "missing_unranked"),
        (lambda d: d["rows"].pop(), "rank_population"),
    ]:
        bad = deepcopy(rank_doc)
        change(bad)
        bad.update(total_matched=len(bad["rows"]), truncated=len(bad["rows"]) > 1)
        result = write(path, seal(bad))
        assert expected in {e["field"] for e in result["errors"]}


@pytest.fixture
def stock_trace_doc():
    days = [(date(2026, 1, 5) + timedelta(days=i)).isoformat() for i in range(8)]
    facts = [dict(trade_date=d, stock_ts_code="A", pct_chg=p, amount=a)
             for d, p, a in zip(days, [0, 0, 0, 0, 0, 10, 0, -20], [100]*5 + [200, 100, 100], strict=True)]
    features = dict(return_pct=10., amount_vs_prior_mean=2., max_drawdown_pct=0., up_day_share=1/6, market_relative_return_pct=10.)
    signal = dict(feature_row("A", days[:6], features), record_kind="launch_signal", signal_date=days[5], signal_known_as_of=days[5], signal_status="observed", earlier_signal_gap_dates=[], warmup_dates=days[:5])
    path = dict(entity_code="A", record_kind="price_path", start=days[5], end=days[-1], path_status="complete", missing_dates=[],
                peak_date=days[6], peak_gain_pct=10., days_to_peak=1, confirmation_date=days[7], peak_status="drawdown_confirmed_retrospectively",
                peak_known_as_of=days[-1], confirmation_known_as_of=days[-1], end_drawdown_from_peak_pct=20.,
                path=[dict(trade_date=d, nav=n, pct_chg=p, amount=a, drawdown_pct=dd)
                      for d, n, p, a, dd in zip(days[5:], [1.1, 1.1, .88], [10, 0, -20], [200, 100, 100], [0., 0., 20.], strict=True)])
    doc = document("stock", "trace_history", days, ["A"], {"fact_stock_daily": facts, "fact_market_daily": [dict(trade_date=d, sh_index_pct_chg=0) for d in days]},
                   [signal, path], features, analysis_definition=deepcopy(TRACE_DEFINITION), universe=dict(record_counts=dict(launch_signal=1, price_path=1, member_leader=0, sector_succession=0)))
    doc["feature_definitions"]["trace_history"] = deepcopy(TRACE_DEFINITION)
    return seal(doc)


def test_hand_trace_last_tied_peak_confirmation_and_clocks(tmp_path, stock_trace_doc):
    path = tmp_path / "trace.json"
    assert write(path, stock_trace_doc)["result"] == "checked"
    for change, expected in [
        (lambda d: d["rows"][0].update(signal_date="2026-01-09"), "signal_date"),
        (lambda d: d["rows"][1].update(peak_date="2026-01-10"), "peak_date"),
        (lambda d: d["rows"][1].update(confirmation_known_as_of="2026-01-11"), "confirmation_known_as_of"),
        (lambda d: d["rows"][1]["path"][2].update(nav=1), "path.nav"),
    ]:
        bad = deepcopy(stock_trace_doc)
        change(bad)
        result = write(path, seal(bad))
        assert result["result"] == "error"
        assert expected in {e["field"] for e in result["errors"]}
    bad = deepcopy(stock_trace_doc)
    bad["feature_definitions"]["trace_history"]["version"] = "unknown"
    receipt = write(path, seal(bad))
    assert receipt["result"] == "unsupported"
    assert not receipt["calculation_checks"]


def test_signal_boundary_and_missing_path_have_independent_oracles():
    days = [str(i) for i in range(8)]
    facts = {("A", d): dict(pct_chg=0, amount=100) for d in days}
    facts["A", "5"].update(pct_chg=7, amount=150)
    assert _signal("stock", "A", days, facts) == (5, "observed", [])
    facts["A", "5"]["amount"] = 149.99
    assert _signal("stock", "A", days, facts) == (None, "not_observed", [])
    del facts["A", "6"]
    assert _signal("stock", "A", days, facts)[1] == "missing"
    assert _path(days[5:], "A", facts)["missing_dates"] == ["6"]
    assert _path(days[5:], "A", facts)["peak_status"] == "unverifiable"


@pytest.mark.parametrize("state", ["observed", "not_observed", "missing", "immature", "outside", "not_supported"])
def test_succession_pair_oracles_keep_nonwinners_and_unconfirmed_peak(tmp_path, state):
    days = [str(i) for i in range(7 if state == "immature" else 8)]
    signals = {"A": ("1", "observed"), "B": (None, state) if state in {"not_observed", "missing"} else ("1" if state == "outside" else "3", "observed")}
    paths = {"A": dict(peak_date="1", peak_status="window_peak_unconfirmed", confirmation_date=None)}
    facts = {(c, d): dict(pct_chg=1 if state == "not_supported" or c == "B" else -1) for c in ("A", "B") for d in days}
    markets = {("", d): dict(sh_index_pct_chg=0) for d in days}
    if state == "immature":
        paths["A"]["peak_date"] = "3"
    expected_status = {"observed": "candidate_not_causal", "outside": "outside_succession_window"}.get(state, state)
    has_returns = state in {"observed", "not_supported"}
    anchor = paths["A"]["peak_date"]
    row = dict(source_sector="A", entity_code="B", anchor_peak_date=anchor,
               start="4" if state == "immature" else "2", end="6", source_peak_status="window_peak_unconfirmed", source_peak_confirmation_date=None,
               succession_known_as_of=days[-1], target_signal_date=signals["B"][0], lag_trading_days=2 if has_returns else None,
               succession_status=expected_status, causal_status="not_established",
               evidence=dict(source_return_pct=(5.10100501 if state == "not_supported" else -4.90099501) if has_returns else None,
                             target_return_pct=5.10100501 if has_returns else None, target_relative_return_pct=5.10100501 if has_returns else None))
    audit = _Audit(tmp_path)
    _audit_pairs(days, ["A", "B"], facts, markets, signals, paths, [row], _calculate, audit)
    assert not audit.receipt["errors"]
    bad = _Audit(tmp_path)
    _audit_pairs(days, ["A", "B"], facts, markets, signals, paths, [], _calculate, bad)
    assert "succession_population" in {e["field"] for e in bad.receipt["errors"]}
    if has_returns:
        row["succession_status"] = "not_observed"
        wrong = _Audit(tmp_path)
        _audit_pairs(days, ["A", "B"], facts, markets, signals, paths, [row], _calculate, wrong)
        assert "succession.succession_status" in {e["field"] for e in wrong.receipt["errors"]}


def test_membership_is_launch_date_not_later_winners(tmp_path):
    days = ["2026-01-05", "2026-01-06"]
    doc = {"inputs": {
        "fact_sector_stock_daily": [dict(sector_ts_code="A", stock_ts_code="S", trade_date=days[0], sector_universe_snapshot_id="launch"),
                                    dict(sector_ts_code="A", stock_ts_code="WINNER", trade_date=days[1], sector_universe_snapshot_id="later")],
        "fact_stock_daily": [dict(stock_ts_code="S", trade_date=days[0], pct_chg=10, amount=100), dict(stock_ts_code="S", trade_date=days[1], pct_chg=-20, amount=200)],
    }}
    row = dict(parent_sector="A", entity_code="S", membership_date=days[0], membership_snapshot_id="launch", start=days[0], end=days[0],
               population_count=1, path_end=days[-1], membership_status="observed", path_anchor="sector_signal_not_stock_launch", selection_mode="posthoc_launch_members_only",
               features=dict(return_pct=10., max_drawdown_pct=0., up_day_share=1.), rank=1,
               path_status="complete", missing_dates=[], peak_date=days[0], peak_gain_pct=10., days_to_peak=0,
               confirmation_date=days[1], peak_status="drawdown_confirmed_retrospectively", peak_known_as_of=days[1], confirmation_known_as_of=days[1], end_drawdown_from_peak_pct=20.,
               path=[dict(trade_date=days[0], nav=1.1, pct_chg=10, amount=100, drawdown_pct=0.), dict(trade_date=days[1], nav=.88, pct_chg=-20, amount=200, drawdown_pct=20.)])
    sectors = {("A", days[0]): {"sector_universe_snapshot_id": "launch"}}
    signals = {"A": (days[0], "observed")}
    paths = {"A": {"peak_date": days[0]}}
    audit = _Audit(tmp_path)
    _audit_members(doc, days, sectors, signals, paths, [row], _calculate, audit)
    assert not audit.receipt["errors"]
    row["entity_code"] = "WINNER"
    bad = _Audit(tmp_path)
    _audit_members(doc, days, sectors, signals, paths, [row], _calculate, bad)
    assert "launch_member_population" in {e["field"] for e in bad.receipt["errors"]}


def test_auditor_never_loads_product_or_io_dependencies():
    import ast
    from pathlib import Path

    for name in ("audit_historical_research_artifacts.py", "history_anatomy_arithmetic.py"):
        tree = ast.parse((Path(__file__).parents[1] / "scripts" / name).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names]
        assert not any(s.startswith(("intelligence", "market_feature_store", "duckdb", "requests", "httpx")) for s in imports)
        assert callable(audit_artifact)
