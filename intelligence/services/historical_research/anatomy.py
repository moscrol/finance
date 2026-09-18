"""Bounded, descriptive launch-to-peak anatomy; no new fact store or labels.

All input reads use HistoryQuery's transaction, row limit and deadline. Signals
use prefixes only; a window peak/confirmation is explicitly retrospective.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from market_feature_store.signals import is_double_red
from .features import compute_features, finite

# v1.1 adds explicit observation dates/status; the v1 arithmetic is unchanged.
ANATOMY_VERSION = "history-anatomy-v1.1"
WARMUP = 5
DRAWDOWN_CONFIRM_PCT = 10
TRACE_FEATURES = (
    "return_pct",
    "amount_vs_prior_mean",
    "max_drawdown_pct",
    "up_day_share",
    "market_relative_return_pct",
    "advancer_share",
    "amount_share_change_pp",
)
ANATOMY_DEFINITION = {
    "version": ANATOMY_VERSION,
    "unit": "descriptive_daily_path",
    "clocks": "known_as_of=calculation cutoff, NOT proof of recorded-time availability; all results remain hindsight_reconstruction.",
    "selection_bias": "Trigger conditions shared by selected cases are NOT discovered commonalities. Changing window changes first signal. Include failures with compare_cases.",
    "rule": "5 warmup dates inside start..end. First signal: sector=strict double red; stock=pct>=7 & amount/prior5_mean>=1.5. No lookback expansion.",
    "peak": "Last maximum return-NAV since signal. Confirmation date=first later >=10% drawdown; link to chosen peak is known only at window end. Not intraday/predicted top.",
    "leaders": "Signal-date members ranked by return through sector peak; posthoc, not a forecast or whole-market winners. Ties by code; incomplete unranked.",
    "succession": "Target first signal in (source peak, peak+5 trading dates]; BOTH returns use those same source-peak-next5 dates: target>0, source<=0. No peak-confirmation prerequisite; not causal.",
    "succession_observation": "outcome_dates are the first <=5 saved calendar dates strictly after source peak. Fewer than 5 => immature, NOT failed; calendar maturity does not certify nonmissing prices. target_signal_status is separate.",
    "path": "NAV=1 before signal, compounds daily pct_chg; missing/duplicate/invalid return => unverifiable. Descriptive, not adjusted candle shapes.",
}


def _group(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return groups


def _path(days, rows):
    by_day = _group(rows, "trade_date")
    missing = [
        d
        for d in days
        if len(by_day[d]) != 1
        or not finite(by_day[d][0].get("pct_chg"))
        or by_day[d][0]["pct_chg"] <= -100
    ]
    if not days or missing:
        return {
            "path_status": "missing",
            "missing_dates": missing,
            "path": [],
            "peak_date": None,
            "peak_status": "unverifiable",
            "confirmation_date": None,
        }
    nav = high = 1.0
    path = []
    for day in days:
        row = by_day[day][0]
        nav *= 1 + row["pct_chg"] / 100
        high = max(high, nav)
        path.append(
            {
                "trade_date": day,
                "nav": nav,
                "pct_chg": row["pct_chg"],
                "amount": row.get("amount"),
                "drawdown_pct": (1 - nav / high) * 100,
            }
        )
    # Last tie avoids labelling an intervening dip as the final peak's confirmation.
    peak_i = max(range(len(path)), key=lambda i: (path[i]["nav"], i))
    peak = path[peak_i]
    confirmation = next(
        (
            p["trade_date"]
            for p in path[peak_i + 1 :]
            if (1 - p["nav"] / peak["nav"]) * 100 >= DRAWDOWN_CONFIRM_PCT
        ),
        None,
    )
    return {
        "path_status": "complete",
        "missing_dates": [],
        "path": path,
        "peak_date": peak["trade_date"],
        "peak_gain_pct": (peak["nav"] - 1) * 100,
        "days_to_peak": peak_i,
        "confirmation_date": confirmation,
        "peak_status": "drawdown_confirmed_retrospectively"
        if confirmation
        else "window_peak_unconfirmed",
        "peak_known_as_of": days[-1],
        "confirmation_known_as_of": days[-1] if confirmation else None,
        "end_drawdown_from_peak_pct": (1 - path[-1]["nav"] / peak["nav"]) * 100,
    }


def _first_signal(kind, days, rows, check):
    by_day = _group(rows, "trade_date")
    unknown = []
    for i in range(WARMUP, len(days)):
        check()
        day = days[i]
        candidates = by_day[day]
        if len(candidates) != 1:
            unknown.append(day)
            continue
        row = candidates[0]
        if kind == "sector":
            if not all(finite(row.get(k)) for k in ("pct_chg", "amount", "diff_ratio")):
                unknown.append(day)
                continue
            triggered = is_double_red(row["pct_chg"], row["diff_ratio"], row["amount"])
        else:
            window = days[i - WARMUP : i + 1]
            values, _ = compute_features(
                ("amount_vs_prior_mean",),
                window,
                [r for d in window for r in by_day[d]],
            )
            ratio = values["amount_vs_prior_mean"]
            if not finite(row.get("pct_chg")) or ratio is None:
                unknown.append(day)
                continue
            triggered = row["pct_chg"] >= 7 and ratio >= 1.5
        if triggered:
            return i, "observed_with_earlier_gaps" if unknown else "observed", unknown
    return (
        None,
        "insufficient_history"
        if len(days) <= WARMUP
        else "missing"
        if unknown
        else "not_observed",
        unknown,
    )


def trace_history(spec, reader, check):
    kind = spec.entity_kind
    table, code_key = f"fact_{kind}_daily", f"{kind}_ts_code"
    facts = reader.read(
        table, spec.start, spec.end, codes=spec.entity_codes, code_field=code_key
    )
    market = reader.read("fact_market_daily", spec.start, spec.end)
    days = reader.calendar(spec.start, spec.end, market)
    reader.validate_calendar(days, facts)
    members = (
        reader.read(
            "fact_sector_stock_daily", spec.start, spec.end, codes=spec.entity_codes
        )
        if kind == "sector"
        else []
    )
    grouped = _group(facts, code_key)
    member_groups = _group(members, "sector_ts_code")
    summaries: dict[str, dict[str, Any]] = {}
    signal_statuses = {}
    records = []
    for code in spec.entity_codes:
        check()
        own = grouped[code]
        signal_i, status, missing = _first_signal(kind, days, own, check)
        name = next(
            (r.get(f"{kind}_name") for r in reversed(own) if r.get(f"{kind}_name")),
            None,
        )
        signal_statuses[code] = status
        signal_date = days[signal_i] if signal_i is not None else None
        signal = {
            "record_kind": "launch_signal",
            "entity_kind": kind,
            "entity_code": code,
            "entity_name": name,
            "start": spec.start,
            "end": spec.end,
            "signal_date": signal_date,
            "signal_known_as_of": signal_date,
            "signal_status": status,
            "earlier_signal_gap_dates": missing,
            "warmup_dates": days[:WARMUP],
        }
        if signal_i is not None and kind == "sector":
            signal["sector_snapshot_id"] = next(
                r.get("sector_universe_snapshot_id")
                for r in own
                if r["trade_date"] == signal_date
            )
        if signal_i is None:
            signal.update(features={}, feature_coverage={})
            records.append(signal)
            reader.gaps.append(f"launch:{code}:{status}")
            continue
        feature_days = days[signal_i - WARMUP : signal_i + 1]
        names = TRACE_FEATURES if kind == "sector" else TRACE_FEATURES[:5]
        values, coverage = compute_features(
            names,
            feature_days,
            [r for r in own if r["trade_date"] in feature_days],
            members=[r for r in member_groups[code] if r["trade_date"] in feature_days],
            market=[r for r in market if r["trade_date"] in feature_days],
        )
        signal.update(
            start=feature_days[0],
            end=feature_days[-1],
            features=values,
            feature_coverage=coverage,
        )
        records.append(signal)
        selected_days = days[signal_i:]
        path = _path(selected_days, [r for r in own if r["trade_date"] >= signal_date])
        summary = {
            "record_kind": "price_path",
            "entity_kind": kind,
            "entity_code": code,
            "entity_name": name,
            "start": signal_date,
            "end": spec.end,
            "signal_date": signal_date,
            "signal_status": status,
            "sector_snapshot_id": signal.get("sector_snapshot_id"),
            **path,
        }
        summaries[code] = summary
        records.append(summary)
        if path["path_status"] != "complete":
            reader.gaps.append(f"path:{code}:missing")
        if missing:
            reader.gaps.append(f"launch:{code}:earlier_signal_gaps")

    if kind == "sector":
        records.extend(
            _succession(
                spec.entity_codes,
                summaries,
                signal_statuses,
                grouped,
                days,
                market,
                check,
            )
        )
        # Put pair conclusions before the potentially large member population;
        # interleave sectors by rank so a large basket cannot hide smaller ones.
        leaders = _leaders(summaries, days, member_groups, reader, check)
        leaders.sort(
            key=lambda r: (
                r["rank"] is None,
                r["rank"] or 0,
                r["parent_sector"],
                r["entity_code"],
            )
        )
        records.extend(leaders)
    counts = {
        key: sum(r["record_kind"] == key for r in records)
        for key in ("launch_signal", "price_path", "member_leader", "sector_succession")
    }
    return records, {
        "analysis_definition": ANATOMY_DEFINITION,
        "universe": {
            "entity_kind": kind,
            "entity_codes": spec.entity_codes,
            "start": spec.start,
            "end": spec.end,
            "record_counts": counts,
            "selection": "declared codes; first signal after in-window warmup; no winner prefilter",
            "membership": "sector signal-date snapshot only, never current membership",
        },
        "matching_use": "descriptive_reconstruction_not_method_validation",
        "independence_policy": "same stock may belong to multiple launch baskets; rankings and pairs are not independent samples",
    }


def _leaders(summaries, days, member_groups, reader, check):
    populations = {}
    codes = set()
    for code, summary in summaries.items():
        if summary["peak_date"] is None:
            continue
        selected = [
            r for r in member_groups[code] if r["trade_date"] == summary["signal_date"]
        ]
        populations[code] = selected
        codes.update(r["stock_ts_code"] for r in selected if r.get("stock_ts_code"))
        if not selected:
            reader.gaps.append(f"launch_members:{code}:missing")
        elif not summary.get("sector_snapshot_id"):
            reader.gaps.append(f"launch_members:{code}:snapshot_unknown")
    if not codes:
        return []
    # Bounded by the same input-row cap; no top-N clipping before ranking.
    stocks = reader.read(
        "fact_stock_daily",
        days[0],
        days[-1],
        codes=tuple(sorted(codes)),
        code_field="stock_ts_code",
    )
    grouped = _group(stocks, "stock_ts_code")
    records = []
    for code, selected in populations.items():
        check()
        summary = summaries[code]
        window = [
            d for d in days if summary["signal_date"] <= d <= summary["peak_date"]
        ]
        members = _group(selected, "stock_ts_code")
        leaders = []
        for stock in sorted(k for k in members if k):
            check()
            member = members[stock][0]
            own = [r for r in grouped[stock] if r["trade_date"] in window]
            values, coverage = compute_features(
                ("return_pct", "max_drawdown_pct", "up_day_share"), window, own
            )
            ambiguous = len(members[stock]) != 1 or any(
                r.get("sector_universe_snapshot_id")
                != summary.get("sector_snapshot_id")
                for r in selected
            )
            if ambiguous:
                values = {k: None for k in values}
                coverage = {
                    k: dict(v, status="ambiguous_membership")
                    for k, v in coverage.items()
                }
            leaders.append(
                {
                    "record_kind": "member_leader",
                    "entity_kind": "stock",
                    "entity_code": stock,
                    "entity_name": member.get("stock_name"),
                    "parent_sector": code,
                    "membership_date": summary["signal_date"],
                    "membership_snapshot_id": member.get("sector_universe_snapshot_id"),
                    "start": window[0],
                    "end": window[-1],
                    "features": values,
                    "feature_coverage": coverage,
                    "rank": None,
                    "selection_mode": "posthoc_launch_members_only",
                    "population_count": len(members),
                    "membership_status": "ambiguous"
                    if ambiguous
                    else "snapshot_unknown"
                    if not summary.get("sector_snapshot_id")
                    else "observed",
                    # Rank ends at the sector peak; the separate stock path follows
                    # the whole observation window, still anchored on SECTOR signal.
                    "path_anchor": "sector_signal_not_stock_launch",
                    **_path(
                        [d for d in days if d >= summary["signal_date"]],
                        []
                        if ambiguous
                        else [
                            r
                            for r in grouped[stock]
                            if r["trade_date"] >= summary["signal_date"]
                        ],
                    ),
                    "path_end": days[-1],
                }
            )
        leaders.sort(
            key=lambda r: (
                r["features"]["return_pct"] is None,
                -(r["features"]["return_pct"] or 0),
                r["entity_code"],
            )
        )
        for i, leader in enumerate(leaders):
            if leader["path_status"] != "complete":
                reader.gaps.append(
                    f"member_path:{code}:{leader['entity_code']}:missing"
                )
            if leader["features"]["return_pct"] is not None:
                leader["rank"] = i + 1
        records.extend(leaders)
    return records


def _succession(codes, summaries, signal_statuses, grouped, days, market, check):
    records = []
    for source in codes:
        before = summaries.get(source)
        if (
            not before
            or not before["peak_date"]
            or before["signal_status"] != "observed"
        ):
            continue
        peak_i = days.index(before["peak_date"])
        outcome_days = days[peak_i + 1 : peak_i + 6]
        for target in codes:
            if target == source:
                continue
            check()
            after = summaries.get(target)
            status = "not_observed"
            lag = None
            evidence = {
                "source_return_pct": None,
                "target_return_pct": None,
                "target_relative_return_pct": None,
            }
            if len(outcome_days) != 5:
                status = "immature"
            elif signal_statuses[target] == "not_observed":
                status = "not_observed"
            elif after is None or after["signal_status"] != "observed":
                status = "missing"
            elif not before["peak_date"] < after["signal_date"] <= outcome_days[-1]:
                status = "outside_succession_window"
            else:
                lag = days.index(after["signal_date"]) - peak_i
                results = []
                for code in (source, target):
                    values, _ = compute_features(
                        ("return_pct", "market_relative_return_pct"),
                        outcome_days,
                        [r for r in grouped[code] if r["trade_date"] in outcome_days],
                        market=[r for r in market if r["trade_date"] in outcome_days],
                    )
                    results.append(values)
                a, b = results
                evidence.update(
                    source_return_pct=a["return_pct"],
                    target_return_pct=b["return_pct"],
                    target_relative_return_pct=b["market_relative_return_pct"],
                )
                if a["return_pct"] is None or b["return_pct"] is None:
                    status = "missing"
                elif a["return_pct"] <= 0 < b["return_pct"]:
                    status = "candidate_not_causal"
                else:
                    status = "not_supported"
            records.append(
                {
                    "record_kind": "sector_succession",
                    "entity_kind": "sector",
                    "entity_code": target,
                    "source_sector": source,
                    "anchor_peak_date": before["peak_date"],
                    "start": outcome_days[0] if outcome_days else before["peak_date"],
                    "end": outcome_days[-1] if outcome_days else before["peak_date"],
                    "source_peak_status": before["peak_status"],
                    "source_peak_confirmation_date": before["confirmation_date"],
                    "succession_known_as_of": before["peak_known_as_of"],
                    "target_signal_date": after["signal_date"] if after else None,
                    "target_signal_status": signal_statuses[target],
                    "outcome_dates": outcome_days,
                    "outcome_required_days": 5,
                    "lag_trading_days": lag,
                    "succession_status": status,
                    "evidence": evidence,
                    "causal_status": "not_established",
                }
            )
    return records
