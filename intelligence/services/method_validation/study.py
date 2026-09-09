"""Freeze sector membership first; compare five-day returns on common dates."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path

from intelligence.services.methodology_backtest.store import open_labels_db, read_meta

from .protocol import (
    ARMS,
    BOUNDARY,
    SHANGHAI,
    canonical_bytes,
    clock_now,
    iso_date,
    validate_protocol,
)


def _timestamp(value) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _finite(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _mean(values) -> float:
    numbers = list(values)
    return math.fsum(number / len(numbers) for number in numbers)


def _meta(con, path, protocol, *, outcomes=False) -> dict:
    meta = read_meta(con)
    for kind in ("labels", "outcomes") if outcomes else ("labels",):
        item = meta.get(kind)
        if not item or item.get("label_version") != protocol["label_version"]:
            raise ValueError(f"{kind} metadata label version mismatch or absent")
        if (
            not item.get("source_db")
            or not item.get("source_max_trade_date")
            or not item.get("computed_at")
        ):
            raise ValueError(f"{kind} source metadata incomplete")
        iso_date(item["source_max_trade_date"])
        _timestamp(item["computed_at"])
    if (
        meta["labels"].get("source_row_counts", {}).get("label_spec")
        != protocol["label_spec"]
    ):
        raise ValueError("labels metadata spec mismatch or absent")
    if outcomes:
        for key in ("source_db", "source_max_trade_date", "label_version"):
            if meta["labels"][key] != meta["outcomes"][key]:
                raise ValueError(f"labels/outcomes {key} mismatch")
        if 5 not in (meta["outcomes"].get("horizons") or []):
            raise ValueError("outcomes metadata lacks horizon 5")
        offset = (
            meta["outcomes"].get("source_row_counts", {}).get("window_start_offset")
        )
        if offset != 1:
            raise ValueError("outcomes window must start on D+1")
    return {
        "labels_db": str(Path(path).expanduser().resolve()),
        "labels": meta["labels"],
        **({"outcomes": meta["outcomes"]} if outcomes else {}),
        "point_in_time": "reconstructed_labels_not_strict_pit",
    }


def _members(strict, streak) -> tuple[list, list]:
    reasons = []
    if not _finite(strict) or strict not in (0, 1):
        reasons.append("unknown_dual_red_strict")
    if not _finite(streak) or streak < 0 or int(streak) != streak:
        reasons.append("unknown_dual_red_streak")
    arms = ["universe"]
    if strict == 1:
        arms.append("dual_red")
        if _finite(streak) and streak >= 3:
            arms.append("streak3")
    return arms, reasons


def read_features(labels_db, protocol, *, start, end) -> dict:
    validate_protocol(protocol)
    start, end = iso_date(start), iso_date(end)
    if start > end:
        raise ValueError("start must not follow end")
    con = open_labels_db(labels_db, read_only=True)
    try:
        con.execute("BEGIN TRANSACTION")
        metadata = _meta(con, labels_db, protocol)
        calendar = [
            str(row[0])
            for row in con.execute(
                "SELECT trade_date FROM history_calendar WHERE trade_date <= ? ORDER BY trade_date",
                [end],
            ).fetchall()
        ]
        labels = con.execute(
            """SELECT entity_type, entity_id, trade_date, label, value_num, value_text,
                      label_version, computed_at FROM history_labels
               WHERE trade_date BETWEEN ? AND ? AND
                     (entity_type = 'sector' OR
                      (entity_type = 'market' AND entity_id = 'market' AND label = 'market_stage'))
               ORDER BY trade_date, entity_type, entity_id, label""",
            [start, end],
        ).fetchall()
    finally:
        con.close()
    sectors, stages = {}, {}
    for kind, entity, day, label, number, text, version, computed in labels:
        if version != protocol["label_version"]:
            raise ValueError("feature row label version mismatch")
        day = str(day)
        stamp = (
            _timestamp(computed).astimezone(timezone.utc).isoformat(timespec="seconds")
        )
        if kind == "market":
            stages[day] = {"stage": text, "computed_at": stamp}
        else:
            item = sectors.setdefault((day, entity), {"values": {}, "computed_at": []})
            if label in ("dual_red_strict", "dual_red_streak"):
                item["values"][label] = number if _finite(number) else None
            item["computed_at"].append(stamp)
    rows = []
    for (day, entity), item in sorted(sectors.items()):
        strict, streak = (
            item["values"].get(key) for key in ("dual_red_strict", "dual_red_streak")
        )
        arms, reasons = _members(strict, streak)
        stage = stages.get(day, {}).get("stage")
        if stage is None:
            reasons.append("unknown_market_stage")
        elif stage not in protocol["market_stages"]:
            reasons.append("stage_not_applicable")
        if day not in calendar:
            reasons.append("missing_calendar")
        rows.append(
            {
                "trade_date": day,
                "entity_id": entity,
                "stage": stage,
                "dual_red_strict": strict,
                "dual_red_streak": streak,
                "arms": arms,
                "exclusion_reasons": reasons,
                "computed_at": sorted(set(item["computed_at"])),
                "stage_computed_at": stages.get(day, {}).get("computed_at"),
            }
        )
    return {
        "protocol_id": protocol["protocol_id"],
        "start": start,
        "end": end,
        "calendar": calendar,
        "rows": rows,
        "metadata": metadata,
    }


def _validate_features(protocol, features) -> None:
    validate_protocol(protocol)
    if set(features) != {"protocol_id", "start", "end", "calendar", "rows", "metadata"}:
        raise ValueError(
            "invalid feature fields; observations must not contain outcomes"
        )
    if features["protocol_id"] != protocol["protocol_id"]:
        raise ValueError("features protocol mismatch")
    start, end = iso_date(features["start"]), iso_date(features["end"])
    if start > end or features["calendar"] != sorted(set(features["calendar"])):
        raise ValueError("invalid feature range/calendar")
    for day in features["calendar"]:
        if iso_date(day) > end:
            raise ValueError("future calendar in features")
    meta = features["metadata"]
    if (
        meta["labels"]["label_version"] != protocol["label_version"]
        or meta["labels"].get("source_row_counts", {}).get("label_spec")
        != protocol["label_spec"]
    ):
        raise ValueError("frozen features label version/spec mismatch")
    seen = set()
    for row in features["rows"]:
        day = iso_date(row["trade_date"])
        key = (day, row["entity_id"])
        if key in seen or not start <= day <= end or not row["entity_id"]:
            raise ValueError("invalid or duplicate feature member")
        seen.add(key)
        arms, reasons = _members(row["dual_red_strict"], row["dual_red_streak"])
        if row["arms"] != arms or not set(reasons).issubset(row["exclusion_reasons"]):
            raise ValueError("frozen membership differs from frozen labels")
    canonical_bytes(features)


def _check_sources(protocol, features, metadata) -> None:
    frozen = features["metadata"]
    if metadata["labels_db"] != frozen["labels_db"]:
        raise ValueError("outcomes must come from the frozen labels database")
    for kind in ("labels", "outcomes"):
        current = metadata[kind]
        if (
            current["label_version"] != protocol["label_version"]
            or current["source_db"] != frozen["labels"]["source_db"]
        ):
            raise ValueError(
                "outcomes source or label version differs from frozen features"
            )
        if current["source_max_trade_date"] < frozen["labels"]["source_max_trade_date"]:
            raise ValueError("outcomes source watermark regressed")
    if (
        metadata["labels"]["source_row_counts"].get("label_spec")
        != protocol["label_spec"]
    ):
        raise ValueError("outcomes current label spec mismatch")
    if any(
        metadata["labels"][k] != metadata["outcomes"][k]
        for k in ("source_db", "source_max_trade_date", "label_version")
    ):
        raise ValueError("labels/outcomes metadata mismatch")


def _outcome_status(
    row, day, calendar, watermark, *, integrity=True
) -> tuple[str, list]:
    if day not in calendar or not integrity:
        return "invalid", ["missing_calendar"]
    available = [d for d in calendar if day < d <= watermark]
    if len(available) < 5:
        return "pending", ["pending"]
    if row is None or row["status"] == "missing":
        return "missing", ["missing"]
    if row["status"] in ("pending", "pending_window"):
        return "pending", ["pending"]
    if row["status"] != "ok":
        return "invalid", ["invalid"]
    if not _finite(row["fwd_return"]) or row["fwd_return"] <= -100:
        return "invalid", ["invalid"]
    drawdown = row["drawdown_after_peak"]
    if drawdown is not None and (not _finite(drawdown) or not -100 < drawdown <= 0):
        return "invalid", ["invalid"]
    return "ok", []


def read_outcomes(labels_db, protocol, features, *, now=None) -> dict:
    _validate_features(protocol, features)
    current = clock_now(now)
    con = open_labels_db(labels_db, read_only=True)
    try:
        con.execute("BEGIN TRANSACTION")
        metadata = _meta(con, labels_db, protocol, outcomes=True)
        _check_sources(protocol, features, metadata)
        watermark = metadata["outcomes"]["source_max_trade_date"]
        close = datetime.combine(
            date.fromisoformat(watermark), time(15), tzinfo=SHANGHAI
        )
        if close > current:
            raise ValueError(
                "outcomes source watermark has not reached its real market close"
            )
        if _timestamp(metadata["outcomes"]["computed_at"]) < close:
            raise ValueError("outcomes were built before source watermark market close")
        for item in (
            metadata["labels"],
            metadata["outcomes"],
            features["metadata"]["labels"],
        ):
            if _timestamp(item["computed_at"]) > current:
                raise ValueError("future metadata construction time")
        calendar_rows = con.execute(
            "SELECT idx, trade_date FROM history_calendar ORDER BY idx"
        ).fetchall()
        calendar = [str(row[1]) for row in calendar_rows]
        indices = [row[0] for row in calendar_rows]
        if any(day > watermark for day in calendar):
            raise ValueError("calendar exceeds source watermark")
        metadata["calendar_integrity"] = calendar == sorted(set(calendar)) and all(
            b == a + 1 for a, b in zip(indices, indices[1:])
        )
        data = con.execute(
            """SELECT entity_id, trade_date, status, fwd_return, drawdown_after_peak
               FROM history_outcomes WHERE entity_type = 'sector' AND horizon = 5
               AND trade_date BETWEEN ? AND ? ORDER BY trade_date, entity_id""",
            [features["start"], features["end"]],
        ).fetchall()
    finally:
        con.close()
    by_key = {
        (str(day), entity): {
            "status": status,
            "fwd_return": ret,
            "drawdown_after_peak": dd,
        }
        for entity, day, status, ret, dd in data
    }
    rows = []
    for member in features["rows"]:
        day, entity = member["trade_date"], member["entity_id"]
        raw = by_key.get((day, entity))
        status, reasons = _outcome_status(
            raw,
            day,
            calendar,
            metadata["outcomes"]["source_max_trade_date"],
            integrity=metadata["calendar_integrity"],
        )
        rows.append(
            {
                "trade_date": day,
                "entity_id": entity,
                "horizon": 5,
                "status": status,
                "source_status": raw["status"] if raw else None,
                "fwd_return": raw["fwd_return"]
                if raw and _finite(raw["fwd_return"])
                else None,
                "drawdown_after_peak": raw["drawdown_after_peak"]
                if raw and _finite(raw["drawdown_after_peak"])
                else None,
                "exclusion_reasons": reasons,
            }
        )
    return {
        "protocol_id": protocol["protocol_id"],
        "calendar": calendar,
        "rows": rows,
        "metadata": metadata,
    }


def compare(protocol, features, outcomes) -> dict:
    _validate_features(protocol, features)
    if outcomes["protocol_id"] != protocol["protocol_id"]:
        raise ValueError("outcomes protocol mismatch")
    _check_sources(protocol, features, outcomes["metadata"])
    calendar = outcomes["calendar"]
    if calendar != sorted(set(calendar)):
        raise ValueError("outcomes calendar must be ordered and unique")
    for day in calendar:
        iso_date(day)
    if [day for day in calendar if day <= features["end"]] != features["calendar"]:
        # A changed historical calendar cannot silently change a frozen horizon.
        raise ValueError("outcome calendar prefix differs from frozen features")
    members = defaultdict(list)
    for row in features["rows"]:
        members[row["trade_date"]].append(row)
    outcome_map = {}
    keys = {(r["trade_date"], r["entity_id"]) for r in features["rows"]}
    for row in outcomes["rows"]:
        key = (row["trade_date"], row["entity_id"])
        if key in outcome_map or key not in keys or row["horizon"] != 5:
            raise ValueError("outcomes contain duplicate, foreign member, or horizon")
        outcome_map[key] = row
    days = sorted(
        set(
            d for d in features["calendar"] if features["start"] <= d <= features["end"]
        )
        | set(members)
    )
    daily = []
    for day in days:
        rows = members[day]
        stages = {r["stage"] for r in rows}
        if len(stages) > 1:
            raise ValueError("same date has conflicting frozen market stages")
        stage = next(iter(stages), None)
        reasons = set()
        if not rows:
            reasons.add("no_sector_labels")
        if day not in features["calendar"]:
            reasons.add("missing_calendar")
        if stage is None and rows:
            reasons.add("unknown_label")
        elif stage is not None and stage not in protocol["market_stages"]:
            reasons.add("stage_not_applicable")
        arms = {
            name: [r["entity_id"] for r in rows if name in r["arms"]] for name in ARMS
        }
        if rows and any(not arms[name] for name in ARMS):
            reasons.add("no_event")
        preserved = []
        for member in rows:
            key = (day, member["entity_id"])
            raw = outcome_map.get(key)
            status, excluded = _outcome_status(
                raw,
                day,
                calendar,
                outcomes["metadata"]["outcomes"]["source_max_trade_date"],
                integrity=outcomes["metadata"].get("calendar_integrity", True),
            )
            if any(r.startswith("unknown_") for r in member["exclusion_reasons"]):
                reasons.add("unknown_label")
            reasons.update(excluded)
            preserved.append(
                {
                    **member,
                    "outcome": raw,
                    "outcome_status": status,
                    "outcome_exclusion_reasons": excluded,
                }
            )
        paired = bool(rows) and not reasons
        means = {name: None for name in ARMS}
        secondary = {name: None for name in ARMS}
        if paired:
            for name in ARMS:
                selected = [outcome_map[(day, entity)] for entity in arms[name]]
                means[name] = _mean(r["fwd_return"] for r in selected)
                if all(r["drawdown_after_peak"] is not None for r in selected):
                    secondary[name] = _mean(r["drawdown_after_peak"] for r in selected)
        daily.append(
            {
                "trade_date": day,
                "stage": stage,
                "status": "paired" if paired else "not_evaluated",
                "reasons": sorted(reasons),
                "arms": arms,
                "means": means,
                "drawdown_after_peak": secondary,
                "members": preserved,
            }
        )
    paired_days = [d for d in daily if d["status"] == "paired"]
    means = {
        name: _mean(d["means"][name] for d in paired_days) if paired_days else None
        for name in ARMS
    }
    result = {
        "protocol_id": protocol["protocol_id"],
        **BOUNDARY,
        "daily": daily,
        "summary": {
            "paired_dates": len(paired_days),
            "means": means,
            "streak3_minus_dual_red_pp": _mean(
                d["means"]["streak3"] - d["means"]["dual_red"] for d in paired_days
            )
            if paired_days
            else None,
            "streak3_minus_universe_pp": _mean(
                d["means"]["streak3"] - d["means"]["universe"] for d in paired_days
            )
            if paired_days
            else None,
        },
        "coverage": {
            "calendar_dates": len(days),
            "raw_entity_dates": len(features["rows"]),
            "raw_arm_entity_dates": {
                name: sum(len(d["arms"][name]) for d in daily) for name in ARMS
            },
            "paired_dates": len(paired_days),
            "exclusions": dict(
                Counter(reason for d in daily for reason in d["reasons"])
            ),
        },
        "limitations": [
            "overlapping five-day outcomes are dependent",
            "reconstructed labels are not strict point-in-time evidence",
            "descriptive research only; no confidence, significance, or promotion claims",
        ],
    }
    canonical_bytes(result)
    return result


def validate_capture(protocol, features, *, now=None) -> None:
    _validate_features(protocol, features)
    current = clock_now(now)
    today = current.date().isoformat()
    if features["start"] != today or features["end"] != today:
        raise ValueError(
            "capture requires start=end=today; unsynchronized past dates cannot be registered"
        )
    if current.time() < time(15) or today < protocol["forward_start"]:
        raise ValueError("capture must follow market close and forward_start")
    meta = features["metadata"]["labels"]
    if (
        meta["source_max_trade_date"] != today
        or not features["calendar"]
        or features["calendar"][-1] != today
    ):
        raise ValueError(
            "capture requires source watermark and final calendar date equal D0"
        )
    if not features["rows"]:
        raise ValueError("capture requires sector labels on D0")
    stamps = [meta["computed_at"]]
    for row in features["rows"]:
        if not row["computed_at"]:
            raise ValueError("capture lacks label timestamps")
        stamps.extend(row["computed_at"])
        if row["stage_computed_at"] is not None:
            stamps.append(row["stage_computed_at"])
    for value in stamps:
        computed = _timestamp(value).astimezone(SHANGHAI)
        if (
            computed.date().isoformat() != today
            or computed.time() < time(15)
            or computed > current
        ):
            raise ValueError(
                "capture labels must be computed on D0 after close and no later than now"
            )
