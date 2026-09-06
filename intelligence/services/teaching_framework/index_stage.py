"""Index-stage label orchestration over the pure flag and stage-rule functions."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

from .flags import compute_flags
from .stage_rules import STAGES, derive_turns, resolve_stage, score_flags, stage_fine


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_index_stage(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    calendar: Iterable[Any] | None = None,
    vendor_rows: Iterable[Mapping[str, Any]] | None = None,
    stock_rows: Iterable[Mapping[str, Any]] | None = None,
    amount_rows: Iterable[Mapping[str, Any]] | None = None,
    params: Mapping[str, Any] | None = None,
    supplier_normalizer: Callable[[Any], str] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic daily records containing flags, coarse/fine stages and turns.

    This function does not write a database. ``market_rows`` must be ordered by
    ``trade_date`` in the returned result (the helper sorts internally).
    """
    flags = compute_flags(
        market_rows,
        calendar=calendar,
        vendor_rows=vendor_rows,
        stock_rows=stock_rows,
        amount_rows=amount_rows,
        params=params,
    )
    out: list[dict[str, Any]] = []
    previous: str | None = None
    for f in flags:
        scores = score_flags(f, params)
        coarse, resolution, tied = resolve_stage(scores, previous)
        fine = stage_fine(coarse, f, previous)
        hits = _evidence_hits(f, scores, params)
        # A day with any required core input missing gets a teaching gap marker.
        missing = _missing_core(f)
        record = {
            "trade_date": f.get("trade_date"),
            "flags": {f"tf.{k}": v for k, v in f.items() if k != "trade_date"},
            "stage_coarse": coarse,
            "stage_fine": fine,
            "stage_scores": scores,
            "stage_evidence": _json(
                {
                    "scores": scores,
                    "hits": hits,
                    "from": previous,
                    "resolution": resolution,
                    "tied": tied,
                }
            ),
            "supplier_market_stage": f.get("market_stage"),
            "supplier_stage_normalized": supplier_normalizer(f.get("market_stage"))
            if supplier_normalizer
            else f.get("market_stage"),
            "gap": missing,
        }
        out.append(record)
        previous = coarse if coarse in STAGES else None
    turns = derive_turns([r["stage_coarse"] for r in out])
    for record, turn in zip(out, turns):
        record.update({f"tf.{k}": v for k, v in turn.items()})
    return out


def _missing_core(f: Mapping[str, Any]) -> list[str]:
    # NULL only means a source field needed by at least one predicate is absent;
    # no inference from false is made. A fully empty market row is a gap.
    required = ("sh_index_close", "sh_week_ma", "sh_deviation_pct")
    # compute_flags intentionally retains only derived values; all core values
    # unavailable manifests as no evidence rather than a guessed stage.
    if all(f.get(k) is None for k in ("above_week_ma", "deviation_band", "shrink_day")):
        return list(required)
    return []


def _evidence_hits(
    f: Mapping[str, Any], scores: Mapping[str, int], params: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    """Structured predicate evidence; false and unknown predicates are retained."""
    names = (
        "cross_below_week_ma",
        "volume_surge",
        "gap_down_open",
        "above_week_ma",
        "deviation_band",
        "deviation_narrowing",
        "volume_shrink_streak",
        "cross_above_week_ma",
        "mainline_amount_stepping_up.volume_top3",
        "mainline_share_expanding.volume_top3",
        "mainline_amount_stepping_up.vendor",
        "mainline_share_expanding.vendor",
        "shrink_day",
    )
    return [
        {"flag": name, "result": f.get(name), "value": f.get(name)} for name in names
    ]


def to_label_rows(
    records: Iterable[Mapping[str, Any]],
    *,
    framework_version: str = "tf-v0.1",
    computed_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Flatten records to sidecar label-row shape, leaving evidence as JSON text."""
    rows: list[dict[str, Any]] = []
    for rec in records:
        d = rec.get("trade_date")
        values: dict[str, Any] = {
            "stage_coarse": rec.get("stage_coarse"),
            "stage_fine": rec.get("stage_fine"),
            "stage_evidence": rec.get("stage_evidence"),
            "turn_up": rec.get("tf.turn_up"),
            "turn_top": rec.get("tf.turn_top"),
            "turn_down": rec.get("tf.turn_down"),
        }
        values.update(rec.get("flags", {}))
        for label, value in values.items():
            if isinstance(value, bool):
                value_num, value_text = int(value), None
            elif isinstance(value, (int, float)):
                value_num, value_text = value, None
            elif value is None:
                value_num, value_text = None, None
            else:
                value_num, value_text = None, str(value)
            rows.append(
                {
                    "entity_type": "market",
                    "entity_id": "market",
                    "trade_date": d,
                    "label": label if label.startswith("tf.") else f"tf.{label}",
                    "value_num": value_num,
                    "value_text": value_text,
                    "label_version": framework_version,
                    "computed_at": computed_at,
                }
            )
    return rows


def supplier_contingency(
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], int]:
    """Counts teaching coarse stage against untouched supplier stage."""
    c: Counter[tuple[str, str]] = Counter()
    for r in records:
        c[
            (
                str(r.get("stage_coarse")),
                str(
                    r.get("supplier_stage_normalized") or r.get("supplier_market_stage")
                ),
            )
        ] += 1
    return dict(c)
