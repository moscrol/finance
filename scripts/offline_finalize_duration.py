#!/usr/bin/env python3
"""Offline finalize-duration census from existing continuous-episode.json.

Does not call any LLM. Does not change production timeouts.

Wall-clock for a compose turn is inferred as persist-delta:
``finalization.at`` (or previous event) → following ``model_turn.at``.
``model_elapsed`` is computed in agent_episode.py but never persisted.
Tool-event ``at`` is still untrusted for tool duration; this delta is the
ledger.add sandwich around a blocking ``complete()``.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

USERS_ROOT = Path.home() / ".local/share/finance-workbench/users"
# finance-base-ab 是家目录下的同级实验仓，不在本仓内；允许用环境变量指到别处。
AB_ROOT = Path(os.environ.get("FINANCE_BASE_AB_USERS", str(Path.home() / "finance-base-ab" / "out" / "users")))
OUT_DIR = Path(os.environ.get("OFFLINE_CENSUS_OUT_DIR", str(Path(__file__).resolve().parents[1] / "docs" / "verification")))
PRODUCTION_USER = "linxiaoqi5111"


def _events(episode: dict[str, Any]) -> list[dict[str, Any]]:
    raw = episode.get("events")
    if not isinstance(raw, list):
        outcome = episode.get("outcome")
        if isinstance(outcome, dict):
            raw = outcome.get("events")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _parse_at(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _at(event: dict[str, Any]) -> datetime | None:
    payload = _payload(event)
    return _parse_at(payload.get("at")) or _parse_at(event.get("at"))


def _num(raw: object) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _window_kind(asked: float | None, remaining: float | None) -> str:
    if asked is None or remaining is None:
        return "unknown"
    gap = remaining - asked
    if gap <= 1.0:
        return "synthesis"
    if 15.0 <= gap <= 28.0:
        return "opening_borrow"
    if 50.0 <= gap <= 72.0:
        return "stage_reserve60"
    return f"other_gap_{int(round(gap))}"


def _is_timeout(error: object) -> bool:
    return "TimeoutError" in str(error or "")


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p / 100.0
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": round(min(values), 3),
        "p50": round(_pct(values, 50) or 0.0, 3),
        "p90": round(_pct(values, 90) or 0.0, 3),
        "p95": round(_pct(values, 95) or 0.0, 3),
        "p99": round(_pct(values, 99) or 0.0, 3),
        "max": round(max(values), 3),
        "mean": round(statistics.fmean(values), 3),
        "n_gt_20": sum(1 for item in values if item > 20.0),
        "n_gt_35": sum(1 for item in values if item > 35.0),
        "n_gt_60": sum(1 for item in values if item > 60.0),
    }


def iter_episode_paths() -> list[tuple[str, str, Path]]:
    found: list[tuple[str, str, Path]] = []
    for path in sorted(USERS_ROOT.glob("*/runs/*/continuous-episode.json")):
        user = path.parent.parent.parent.name
        found.append(("workbench", user, path))
    if AB_ROOT.is_dir():
        for path in sorted(AB_ROOT.glob("*/runs/*/continuous-episode.json")):
            user = path.parent.parent.parent.name
            found.append(("finance-base-ab", user, path))
    return found


def extract_compose(path: Path, source: str, user: str) -> dict[str, Any] | None:
    try:
        episode = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(episode, dict):
        return None
    events = _events(episode)
    fin_index = next(
        (index for index, event in enumerate(events) if event.get("kind") == "finalization"),
        None,
    )
    if fin_index is None:
        return None
    fin = events[fin_index]
    compose = next(
        (
            event
            for event in events[fin_index + 1 :]
            if event.get("kind") == "model_turn"
        ),
        None,
    )
    if compose is None:
        return {
            "source": source,
            "user": user,
            "run": path.parent.name,
            "path": str(path),
            "reason": str(_payload(fin).get("reason") or ""),
            "missing_compose": True,
        }
    payload = _payload(compose)
    asked = _num(payload.get("timeout_asked"))
    remaining = _num(payload.get("remaining_seconds_at_entry"))
    error = str(payload.get("error") or "")
    started = _at(fin)
    ended = _at(compose)
    persist_s = None
    if started is not None and ended is not None:
        persist_s = (ended - started).total_seconds()
    return {
        "source": source,
        "user": user,
        "run": path.parent.name,
        "path": str(path),
        "reason": str(_payload(fin).get("reason") or ""),
        "asked": asked,
        "remaining_at_entry": remaining,
        "window": _window_kind(asked, remaining),
        "error": error,
        "timed_out": _is_timeout(error),
        "persist_s": persist_s,
        "missing_compose": False,
        "production": user == PRODUCTION_USER,
    }


def extract_synthesis_turns(path: Path, source: str, user: str) -> list[dict[str, Any]]:
    try:
        episode = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(episode, dict):
        return []
    events = _events(episode)
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if event.get("kind") != "model_turn":
            continue
        payload = _payload(event)
        asked = _num(payload.get("timeout_asked"))
        remaining = _num(payload.get("remaining_seconds_at_entry"))
        kind = _window_kind(asked, remaining)
        if kind != "synthesis":
            continue
        prev = events[index - 1] if index else None
        persist_s = None
        if prev is not None:
            started = _at(prev)
            ended = _at(event)
            if started is not None and ended is not None:
                persist_s = (ended - started).total_seconds()
        error = str(payload.get("error") or "")
        rows.append(
            {
                "source": source,
                "user": user,
                "run": path.parent.name,
                "prev_kind": (prev or {}).get("kind"),
                "asked": asked,
                "remaining_at_entry": remaining,
                "error": error,
                "timed_out": _is_timeout(error),
                "persist_s": persist_s,
                "phase": payload.get("phase") or "",
                "production": user == PRODUCTION_USER,
            }
        )
    return rows


def cohort_stats(rows: list[dict[str, Any]], *, persist_max: float = 180.0) -> dict[str, Any]:
    usable = [
        row
        for row in rows
        if isinstance(row.get("persist_s"), float)
        and 0.0 <= row["persist_s"] <= persist_max
        and not row.get("missing_compose")
    ]
    finished = [row for row in usable if not row.get("timed_out")]
    timed_out = [row for row in usable if row.get("timed_out")]
    asked_ok = [_num(row.get("asked")) for row in finished]
    asked_vals = [item for item in asked_ok if item is not None]
    persist_ok = [float(row["persist_s"]) for row in finished]
    persist_to = [float(row["persist_s"]) for row in timed_out]
    reasons = Counter(str(row.get("reason") or "") for row in usable)
    prev = Counter(str(row.get("prev_kind") or "") for row in usable)
    over_asked = 0
    for row in finished:
        asked = _num(row.get("asked"))
        persist = float(row["persist_s"])
        if asked is not None and persist > asked + 1.0:
            over_asked += 1
    return {
        "n_rows": len(rows),
        "n_usable_persist": len(usable),
        "n_finished": len(finished),
        "n_timed_out": len(timed_out),
        "timeout_rate": round(len(timed_out) / len(usable), 4) if usable else None,
        "persist_finished": _summary(persist_ok),
        "persist_timed_out": _summary(persist_to),
        "asked_finished": _summary(asked_vals),
        "n_finished_persist_gt_asked_plus_1s": over_asked,
        "reasons": dict(reasons),
        "prev_kind": dict(prev),
        "floor_checks": {
            "finished_p95_vs_20": _cmp_p95(persist_ok, 20.0),
            "finished_p95_vs_35": _cmp_p95(persist_ok, 35.0),
            "share_finished_gt_20": round(
                sum(1 for item in persist_ok if item > 20.0) / len(persist_ok), 4
            )
            if persist_ok
            else None,
            "share_finished_gt_35": round(
                sum(1 for item in persist_ok if item > 35.0) / len(persist_ok), 4
            )
            if persist_ok
            else None,
        },
    }


def _cmp_p95(values: list[float], floor: float) -> dict[str, Any] | None:
    p95 = _pct(values, 95)
    if p95 is None:
        return None
    return {"p95": round(p95, 3), "floor": floor, "p95_le_floor": p95 <= floor}


def main() -> None:
    paths = iter_episode_paths()
    compose_rows: list[dict[str, Any]] = []
    synthesis_rows: list[dict[str, Any]] = []
    n_files = 0
    n_bad = 0
    for source, user, path in paths:
        n_files += 1
        row = extract_compose(path, source, user)
        if row is not None:
            compose_rows.append(row)
        try:
            synthesis_rows.extend(extract_synthesis_turns(path, source, user))
        except Exception:
            n_bad += 1

    prod_compose = [row for row in compose_rows if row.get("production")]
    prod_synth = [
        row
        for row in synthesis_rows
        if row.get("production") and row.get("prev_kind") == "finalization"
    ]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "roots": [str(USERS_ROOT), str(AB_ROOT)],
        "n_episode_files": n_files,
        "n_extract_errors": n_bad,
        "n_with_finalization": len(compose_rows),
        "n_synthesis_shaped_model_turns": len(synthesis_rows),
        "method": {
            "duration_field": "persist_delta_seconds",
            "from": "finalization.at or previous event at",
            "to": "following model_turn.at",
            "not_used": [
                "tool event at",
                "model_elapsed (computed, never persisted)",
            ],
            "window_synthesis": "remaining - asked <= 1s",
            "production_user": PRODUCTION_USER,
        },
        "compose_after_finalization": {
            "all": cohort_stats(compose_rows),
            "production": cohort_stats(prod_compose),
        },
        "synthesis_shaped_after_finalization": {
            "all": cohort_stats(
                [row for row in synthesis_rows if row.get("prev_kind") == "finalization"]
            ),
            "production": cohort_stats(prod_synth),
        },
        "synthesis_shaped_all_prev": {
            "all": cohort_stats(synthesis_rows),
            "production": cohort_stats(
                [row for row in synthesis_rows if row.get("production")]
            ),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "2026-09-02-finalize-duration-offline.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("wrote", json_path, "compose", len(compose_rows), "synthesis_turns", len(synthesis_rows))


if __name__ == "__main__":
    main()
