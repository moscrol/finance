"""Independent saved-fact checks for anatomy-v1. Standard library only.

This is an auditor, not an alternative product engine: it never reads a database,
imports application formulas, or emits query artifacts. The contract is frozen
here deliberately; unrecognised definitions must not be signed off.
"""

from collections import Counter, defaultdict
from itertools import accumulate
import math

ANATOMY_FEATURE_VERSION = "history-anatomy-features-v1"
NEW_DEFINITIONS = {
    "max_drawdown_pct": (["pct_chg"], "percent", "maximum (1 - compounded NAV / running peak NAV) * 100; includes pre-window NAV=1; positive loss depth"),
    "up_day_share": (["pct_chg"], "ratio", "positive-return dates / all declared trading dates"),
    "amount_vs_prior_mean": (["amount"], "ratio", "last amount / mean of all earlier amounts in this window; at least 2 dates; not MA20 unless 21 dates"),
    "amount_share_change_pp": (["amount", "market.total_amount"], "percentage_points", "100 * (last sector amount / last market amount - first sector amount / first market amount); both in yi yuan"),
    "advancers_mean": (["advancers"], "stocks", "mean market advancers over all declared dates; count, not breadth ratio"),
    "limit_up_mean": (["limit_up"], "stocks", "mean market limit-up count over all declared dates"),
    "limit_down_mean": (["limit_down"], "stocks", "mean market limit-down count over all declared dates"),
}
TRACE_DEFINITION = {
    "version": "history-anatomy-v1",
    "unit": "descriptive_daily_path",
    "clocks": "known_as_of=calculation cutoff, NOT proof of recorded-time availability; all results remain hindsight_reconstruction.",
    "selection_bias": "Trigger conditions shared by selected cases are NOT discovered commonalities. Changing window changes first signal. Include failures with compare_cases.",
    "rule": "5 warmup dates inside start..end. First signal: sector=strict double red; stock=pct>=7 & amount/prior5_mean>=1.5. No lookback expansion.",
    "peak": "Last maximum return-NAV since signal. Confirmation date=first later >=10% drawdown; link to chosen peak is known only at window end. Not intraday/predicted top.",
    "leaders": "Signal-date members ranked by return through sector peak; posthoc, not a forecast or whole-market winners. Ties by code; incomplete unranked.",
    "succession": "Declared codes: target first signal in (source peak, peak+5]; target next5 return>0, source<=0. Missing/immature/failed pairs retained; not fund-transfer evidence.",
    "path": "NAV=1 before signal, compounds daily pct_chg; missing/duplicate/invalid return => unverifiable. Descriptive, not adjusted candle shapes.",
}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def calculate_new(name, rows, market_rows):
    """Called only after complete finite field checks by the parent auditor."""
    field = NEW_DEFINITIONS[name][0][0]
    vals = [r[field] for r in rows]
    if name == "max_drawdown_pct":
        if min(vals) <= -100:
            return None, "invalid_return"
        nav = list(accumulate((1 + x / 100 for x in vals), lambda a, b: a * b, initial=1.0))
        highs = list(accumulate(nav, max))
        return max(100 * (1 - n / h) for n, h in zip(nav, highs)), None
    if name == "up_day_share":
        return sum(x > 0 for x in vals) / len(vals), None
    if min(vals) < 0:
        return None, "negative_input"
    if name == "amount_vs_prior_mean":
        if len(vals) < 2:
            return None, "insufficient_history"
        if sum(vals[:-1]) <= 0:
            return None, "zero_denominator"
        return vals[-1] * (len(vals) - 1) / sum(vals[:-1]), None
    if name == "amount_share_change_pp":
        if any(r["total_amount"] <= 0 for r in market_rows):
            return None, "zero_denominator"
        return 100 * (vals[-1] / market_rows[-1]["total_amount"] - vals[0] / market_rows[0]["total_amount"]), None
    return sum(vals) / len(vals), None


def audit_rank(doc, facts, audit):
    """Population is derived from saved facts/spec, not the supplied output list."""
    spec, rows = doc["spec"], doc["rows"]
    expected = sorted(spec["entity_codes"] or {c for c, d in facts if spec["start"] <= d <= spec["end"]})
    audit.check("rank_population", sorted(r["entity_code"] for r in rows), expected, calculation=True)
    ordered = sorted(rows, key=lambda r: (r["features"]["return_pct"] is None, -(r["features"]["return_pct"] or 0), r["entity_code"]))
    audit.check("rank_order", [r["entity_code"] for r in rows], [r["entity_code"] for r in ordered], calculation=True)
    for i, row in enumerate(ordered, 1):
        audit.check("rank", row["rank"], i if row["features"]["return_pct"] is not None else None, row=row["entity_code"], calculation=True)
        audit.check("rank_population_count", row["population_count"], len(expected))
        audit.check("rank_selection_mode", row["selection_mode"], "posthoc_ranked_observed_universe")
        audit.check("rank_start", row["start"], spec["start"])
        audit.check("rank_end", row["end"], spec["end"])
    audit.check("universe_enumerated", doc["universe"]["enumerated"], len(expected))
    audit.check("universe_codes", sorted(doc["universe"]["entity_codes"]), expected)
    audit.check("missing_unranked", doc["universe"]["missing_unranked"], sum(r["features"]["return_pct"] is None for r in rows), calculation=True)


def _signal(kind, code, days, facts):
    uncertain = []
    for i in range(5, len(days)):
        row = facts.get((code, days[i]), {})
        required = ("pct_chg", "amount", "diff_ratio") if kind == "sector" else ("pct_chg",)
        if not all(finite(row.get(k)) for k in required):
            uncertain.append(days[i])
            continue
        if kind == "sector":
            yes = row["pct_chg"] > 0 and row["amount"] > 500 and row["diff_ratio"] > 10
        else:
            amounts = [facts.get((code, d), {}).get("amount") for d in days[i-5:i+1]]
            if not all(finite(x) and x >= 0 for x in amounts) or sum(amounts[:-1]) <= 0:
                uncertain.append(days[i])
                continue
            yes = row["pct_chg"] >= 7 and amounts[-1] * 5 / sum(amounts[:-1]) >= 1.5
        if yes:
            return i, "observed_with_earlier_gaps" if uncertain else "observed", uncertain
    return None, "insufficient_history" if len(days) <= 5 else "missing" if uncertain else "not_observed", uncertain


def _path(days, code, facts):
    missing = [d for d in days if not finite(facts.get((code, d), {}).get("pct_chg")) or facts[code, d]["pct_chg"] <= -100]
    if missing or not days:
        return dict(path_status="missing", missing_dates=missing, path=[], peak_date=None,
                    peak_status="unverifiable", confirmation_date=None)
    factors = [1 + facts[code, d]["pct_chg"] / 100 for d in days]
    navs = [math.prod(factors[:i+1]) for i in range(len(days))]
    top = max(navs)
    peak = max(i for i, n in enumerate(navs) if n == top)
    confirm = next((d for i, d in enumerate(days) if i > peak and (1 - navs[i] / top) * 100 >= 10), None)
    return dict(
        path_status="complete", missing_dates=[],
        path=[dict(trade_date=d, nav=n, pct_chg=facts[code, d]["pct_chg"], amount=facts[code, d].get("amount"),
                   drawdown_pct=(1-n / max(1, *navs[:i+1])) * 100) for i, (d, n) in enumerate(zip(days, navs))],
        peak_date=days[peak], peak_gain_pct=(top-1)*100, days_to_peak=peak,
        confirmation_date=confirm, peak_status="drawdown_confirmed_retrospectively" if confirm else "window_peak_unconfirmed",
        peak_known_as_of=days[-1], confirmation_known_as_of=days[-1] if confirm else None,
        end_drawdown_from_peak_pct=(1-navs[-1]/top)*100,
    )


def _check_path(observed, expected, audit, label):
    for k, v in expected.items():
        if k != "path":
            audit.check(k, observed.get(k), v, row=label, calculation=True)
    actual = observed.get("path", [])
    audit.check("path_length", len(actual), len(expected["path"]), row=label, calculation=True)
    for i, (a, e) in enumerate(zip(actual, expected["path"])):
        for k, v in e.items():
            audit.check("path." + k, a.get(k), v, row=f"{label}:{i}", calculation=True)


def audit_trace(doc, days, facts, markets, calculate, audit):
    """Reconstruct signal dates, paths, basket population/ranks and ordered pairs."""
    spec, rows = doc["spec"], doc["rows"]
    if doc["feature_definitions"].get("trace_history") != TRACE_DEFINITION:
        audit.skip("unsupported_anatomy_definition")
        return False
    audit.check("analysis_definition", doc.get("analysis_definition"), TRACE_DEFINITION)
    days = [d for d in days if spec["start"] <= d <= spec["end"]]
    codes = spec["entity_codes"]
    groups = defaultdict(list)
    for row in rows:
        groups[row["record_kind"]].append(row)
    audit.check("trace_record_kinds", sorted(groups), sorted(k for k in ("launch_signal", "price_path", "member_leader", "sector_succession") if groups[k]))
    audit.check("launch_population", sorted(r["entity_code"] for r in groups["launch_signal"]), sorted(codes), calculation=True)
    signals, paths = {}, {}
    for code in codes:
        matches = [r for r in groups["launch_signal"] if r["entity_code"] == code]
        if len(matches) != 1:
            continue
        row = matches[0]
        i, status, unknown = _signal(spec["entity_kind"], code, days, facts)
        signal = days[i] if i is not None else None
        signals[code] = (signal, status)
        for k, v in dict(signal_date=signal, signal_known_as_of=signal, signal_status=status,
                         earlier_signal_gap_dates=unknown, warmup_dates=days[:5]).items():
            audit.check(k, row.get(k), v, row=code, calculation=True)
        start, end = (days[i-5], signal) if i is not None else (spec["start"], spec["end"])
        audit.check("signal_feature_start", row["start"], start, row=code)
        audit.check("signal_feature_end", row["end"], end, row=code)
        if i is None:
            audit.check("no_signal_features", row["features"], {}, row=code)
            continue
        if spec["entity_kind"] == "sector":
            audit.check("signal_snapshot", row.get("sector_snapshot_id"), facts[code, signal].get("sector_universe_snapshot_id"), row=code)
        expected = _path(days[i:], code, facts)
        paths[code] = expected
        matching = [r for r in groups["price_path"] if r["entity_code"] == code]
        audit.check("price_path_population", len(matching), 1, row=code, calculation=True)
        if matching:
            audit.check("path_start", matching[0]["start"], signal, row=code)
            audit.check("path_end", matching[0]["end"], spec["end"], row=code)
            _check_path(matching[0], expected, audit, code)
    audit.check("price_path_codes", sorted(r["entity_code"] for r in groups["price_path"]), sorted(paths), calculation=True)
    audit.check("trace_record_counts", doc["universe"]["record_counts"], {k: len(groups[k]) for k in ("launch_signal", "price_path", "member_leader", "sector_succession")})
    if spec["entity_kind"] == "sector":
        _audit_members(doc, days, facts, signals, paths, groups["member_leader"], calculate, audit)
        _audit_pairs(days, codes, facts, markets, signals, paths, groups["sector_succession"], calculate, audit)
    else:
        audit.check("stock_trace_no_members", groups["member_leader"], [])
        audit.check("stock_trace_no_succession", groups["sector_succession"], [])
    return True


def _audit_members(doc, days, sectors, signals, paths, rows, calculate, audit):
    stocks = audit.index("fact_stock_daily", doc["inputs"].get("fact_stock_daily", []), "stock_ts_code")
    members = doc["inputs"].get("fact_sector_stock_daily", [])
    expected_keys = []
    for sector, path in paths.items():
        if not path["peak_date"]:
            continue
        signal = signals[sector][0]
        snapshot = sectors[sector, signal].get("sector_universe_snapshot_id")
        basket = [r for r in members if r["sector_ts_code"] == sector and r["trade_date"] == signal]
        counts = Counter(r["stock_ts_code"] for r in basket)
        conflict = any(r.get("sector_universe_snapshot_id") != snapshot for r in basket)
        win = [d for d in days if signal <= d <= path["peak_date"]]
        returns = {}
        for code in sorted(c for c in counts if c):
            expected_keys.append((sector, code))
            ambiguous = counts[code] != 1 or conflict
            selected = [r for r in rows if r["parent_sector"] == sector and r["entity_code"] == code]
            if len(selected) != 1:
                continue
            row = selected[0]
            member = next(r for r in basket if r["stock_ts_code"] == code)
            for k, v in dict(membership_date=signal, membership_snapshot_id=member.get("sector_universe_snapshot_id"),
                             start=win[0], end=win[-1], population_count=len(counts), path_end=days[-1],
                             membership_status="ambiguous" if ambiguous else "snapshot_unknown" if not snapshot else "observed",
                             path_anchor="sector_signal_not_stock_launch", selection_mode="posthoc_launch_members_only").items():
                audit.check("member." + k, row.get(k), v, row=f"{sector}:{code}")
            for name in ("return_pct", "max_drawdown_pct", "up_day_share"):
                val = None if ambiguous else calculate(name, win, stocks, {}, code)[0]
                audit.check("member." + name, row["features"][name], val, row=f"{sector}:{code}", calculation=True)
                if name == "return_pct":
                    returns[code] = val
            _check_path(row, _path([d for d in days if d >= signal], code, {} if ambiguous else stocks), audit, f"{sector}:{code}")
        ranked = sorted((c for c, v in returns.items() if v is not None), key=lambda c: (-returns[c], c))
        for row in (r for r in rows if r["parent_sector"] == sector):
            c = row["entity_code"]
            audit.check("member.rank", row["rank"], ranked.index(c)+1 if c in ranked else None, row=f"{sector}:{c}", calculation=True)
    audit.check("launch_member_population", sorted((r["parent_sector"], r["entity_code"]) for r in rows), sorted(expected_keys), calculation=True)


def _audit_pairs(days, codes, facts, markets, signals, paths, rows, calculate, audit):
    keys = []
    for source in codes:
        before = paths.get(source)
        if not before or not before["peak_date"] or signals[source][1] != "observed":
            continue
        peak_i = days.index(before["peak_date"])
        win = days[peak_i+1:peak_i+6]
        for target in codes:
            if target == source:
                continue
            keys.append((source, target))
            selected = [r for r in rows if r["source_sector"] == source and r["entity_code"] == target]
            if len(selected) != 1:
                continue
            row = selected[0]
            target_day, target_status = signals[target]
            lag, a, b, rel = None, None, None, None
            if len(win) < 5:
                status = "immature"
            elif target_status == "not_observed":
                status = "not_observed"
            elif target_status != "observed":
                status = "missing"
            elif target_day <= before["peak_date"] or target_day > win[-1]:
                status = "outside_succession_window"
            else:
                lag = days.index(target_day) - peak_i
                a = calculate("return_pct", win, facts, markets, source)[0]
                b = calculate("return_pct", win, facts, markets, target)[0]
                rel = calculate("market_relative_return_pct", win, facts, markets, target)[0]
                status = "missing" if a is None or b is None else "candidate_not_causal" if a <= 0 < b else "not_supported"
            expected = dict(anchor_peak_date=before["peak_date"], start=win[0] if win else before["peak_date"],
                            end=win[-1] if win else before["peak_date"], source_peak_status=before["peak_status"],
                            source_peak_confirmation_date=before["confirmation_date"], succession_known_as_of=days[-1],
                            target_signal_date=target_day, lag_trading_days=lag, succession_status=status, causal_status="not_established")
            for k, v in expected.items():
                audit.check("succession."+k, row.get(k), v, row=f"{source}:{target}", calculation=True)
            for k, v in dict(source_return_pct=a, target_return_pct=b, target_relative_return_pct=rel).items():
                audit.check("succession."+k, row["evidence"].get(k), v, row=f"{source}:{target}", calculation=True)
    audit.check("succession_population", sorted((r["source_sector"], r["entity_code"]) for r in rows), sorted(keys), calculation=True)
