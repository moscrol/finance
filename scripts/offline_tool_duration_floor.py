#!/usr/bin/env python3
"""Offline tool-duration census from existing continuous-episode.json.

Does not call any LLM. Does not change production timeouts.

Answers the tool half of budget P1 ("reserve 不可侵犯 vs 工具有地板"):
how long do tool calls actually take when they succeed, how much were they
granted, and when they time out, how much had they been granted.

Duration source is ``elapsed_ms`` on ``tool_result`` / ``tool_error`` events.
It is written by the worker thread itself (``_ToolTiming`` in
``episode_tool_batch.py``), so unlike event ``at`` deltas it is not polluted
by ledger persistence order. Calls rejected before dispatch carry no
``elapsed_ms`` and are counted separately, never as zero.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

USERS_ROOT = Path.home() / ".local/share/finance-workbench/users"
# finance-base-ab 是家目录下的同级实验仓，不在本仓内；允许用环境变量指到别处。
AB_ROOT = Path(os.environ.get("FINANCE_BASE_AB_USERS", str(Path.home() / "finance-base-ab" / "out" / "users")))
OUT_DIR = Path(os.environ.get("OFFLINE_CENSUS_OUT_DIR", str(Path(__file__).resolve().parents[1] / "docs" / "verification")))
PRODUCTION_USER = "linxiaoqi5111"
RECENT_DAYS = 14
CANDIDATE_FLOORS = (5.0, 10.0, 15.0, 20.0, 30.0)
# 零授权假超时：派发点实授 ≤ 0，工具压根没跑（P0/P0.1 让模型看见的那一格）。
ZERO_GRANT_EPS = 1e-9
TIME_GATE_ERRORS = frozenset({"tool_timeout", "tool_not_dispatched"})


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
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def extract_tool_rows(path: Path, source: str, user: str) -> list[dict[str, Any]]:
    try:
        episode = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(episode, dict):
        return []
    rows: list[dict[str, Any]] = []
    for event in _events(episode):
        kind = event.get("kind")
        if kind not in {"tool_result", "tool_error"}:
            continue
        payload = _payload(event)
        elapsed_ms = _num(payload.get("elapsed_ms"))
        granted = _num(payload.get("stage_timeout_granted"))
        rows.append(
            {
                "source": source,
                "user": user,
                "run": path.parent.name,
                "kind": kind,
                "tool": str(payload.get("tool") or ""),
                "error": str(payload.get("error") or ""),
                "elapsed_s": elapsed_ms / 1000.0 if elapsed_ms is not None else None,
                "queued_s": (_num(payload.get("queued_ms")) or 0.0) / 1000.0
                if payload.get("queued_ms") is not None
                else None,
                "asked": _num(payload.get("batch_grant_asked")),
                "granted": granted,
                "remaining_at_dispatch": _num(payload.get("episode_remaining_at_dispatch")),
                "at": _parse_at(payload.get("at")) or _parse_at(event.get("at")),
                "production": user == PRODUCTION_USER,
            }
        )
    return rows


def _coverage(values: list[float], floor: float) -> dict[str, Any]:
    if not values:
        return {"floor": floor, "n": 0}
    covered = sum(1 for item in values if item <= floor)
    return {
        "floor": floor,
        "n": len(values),
        "covered": covered,
        "share_covered": round(covered / len(values), 4),
        "cut_if_floor_were_cap": len(values) - covered,
    }


def cohort_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    success = [row for row in rows if row["kind"] == "tool_result" and row["elapsed_s"] is not None]
    errors = [row for row in rows if row["kind"] == "tool_error"]
    # 两代词表并存：工单 #28（INV-R4）起零授权未派发写 tool_not_dispatched；更早的产物
    # 把它也写成 tool_timeout，只能靠 granted<=ε 分。两种都当时间闸收进来。
    timeouts = [row for row in errors if row["error"] in TIME_GATE_ERRORS]
    zero_grant = [
        row
        for row in timeouts
        if row["error"] == "tool_not_dispatched"
        or (row["granted"] is not None and row["granted"] <= ZERO_GRANT_EPS)
    ]
    real_timeouts = [row for row in timeouts if row not in zero_grant]
    granted_unknown = [row for row in timeouts if row["granted"] is None]

    success_elapsed = [float(row["elapsed_s"]) for row in success]
    success_granted = [float(row["granted"]) for row in success if row["granted"] is not None]
    # 成功但已吃掉 ≥80% 实授窗：再紧一点就会被切，这是「地板」真正要保护的样本。
    near_cut = [
        row
        for row in success
        if row["granted"] is not None
        and row["granted"] > 0
        and float(row["elapsed_s"]) >= 0.8 * float(row["granted"])
    ]
    real_timeout_granted = [float(row["granted"]) for row in real_timeouts if row["granted"] is not None]

    per_tool: dict[str, dict[str, Any]] = {}
    by_tool_success: dict[str, list[float]] = defaultdict(list)
    by_tool_timeout: Counter[str] = Counter()
    by_tool_zero: Counter[str] = Counter()
    by_tool_timeout_granted: dict[str, list[float]] = defaultdict(list)
    for row in success:
        by_tool_success[row["tool"]].append(float(row["elapsed_s"]))
    for row in real_timeouts:
        by_tool_timeout[row["tool"]] += 1
        if row["granted"] is not None:
            by_tool_timeout_granted[row["tool"]].append(float(row["granted"]))
    for row in zero_grant:
        by_tool_zero[row["tool"]] += 1
    for tool in sorted(set(by_tool_success) | set(by_tool_timeout) | set(by_tool_zero)):
        values = by_tool_success.get(tool, [])
        per_tool[tool] = {
            "success": _summary(values),
            "real_timeouts": by_tool_timeout.get(tool, 0),
            "real_timeout_granted": _summary(by_tool_timeout_granted.get(tool, [])),
            "zero_grant_timeouts": by_tool_zero.get(tool, 0),
            "coverage": {str(int(floor)): _coverage(values, floor) for floor in CANDIDATE_FLOORS},
        }

    return {
        "n_rows": len(rows),
        "n_success_with_elapsed": len(success),
        "n_errors": len(errors),
        "errors_by_code": dict(Counter(row["error"] for row in errors)),
        "n_timeouts": len(timeouts),
        "n_zero_grant_timeouts": len(zero_grant),
        "n_real_timeouts": len(real_timeouts),
        "n_timeouts_granted_unknown": len(granted_unknown),
        "success_elapsed": _summary(success_elapsed),
        "success_granted": _summary(success_granted),
        "success_near_cut_ge_80pct_of_grant": len(near_cut),
        "real_timeout_granted": _summary(real_timeout_granted),
        "real_timeouts_granted_below_floor": {
            str(int(floor)): sum(1 for value in real_timeout_granted if value < floor)
            for floor in CANDIDATE_FLOORS
        },
        "coverage": {str(int(floor)): _coverage(success_elapsed, floor) for floor in CANDIDATE_FLOORS},
        "per_tool": per_tool,
    }


def main() -> None:
    paths = iter_episode_paths()
    rows: list[dict[str, Any]] = []
    n_files = 0
    for source, user, path in paths:
        n_files += 1
        rows.extend(extract_tool_rows(path, source, user))

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)
    prod_rows = [row for row in rows if row["production"]]
    prod_recent = [row for row in prod_rows if row["at"] is not None and row["at"] >= recent_cutoff]

    def _strip(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key != "at"}

    payload = {
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "roots": [str(USERS_ROOT), str(AB_ROOT)],
        "n_episode_files": n_files,
        "n_tool_events": len(rows),
        "method": {
            "duration_field": "payload.elapsed_ms / 1000 (worker-thread monotonic, not event at)",
            "grant_field": "payload.stage_timeout_granted at dispatch",
            "zero_grant_rule": (
                f"error == tool_not_dispatched (>= #28) or tool_timeout with "
                f"stage_timeout_granted <= {ZERO_GRANT_EPS} (legacy artifacts)"
            ),
            "near_cut_rule": "success with elapsed >= 0.8 * granted",
            "candidate_floors_s": list(CANDIDATE_FLOORS),
            "production_user": PRODUCTION_USER,
            "recent_days": RECENT_DAYS,
        },
        "cohorts": {
            "production": cohort_stats(prod_rows),
            f"production_recent_{RECENT_DAYS}d": cohort_stats(prod_recent),
            "all": cohort_stats(rows),
        },
        "real_timeouts_listing_production": [
            _strip(row)
            for row in prod_rows
            if row["kind"] == "tool_error"
            and row["error"] == "tool_timeout"
            and row["granted"] is not None
            and row["granted"] > ZERO_GRANT_EPS
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "2026-09-03-tool-duration-floor-offline.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = {
        cohort: {
            "success_n": stats["n_success_with_elapsed"],
            "success_p50": stats["success_elapsed"].get("p50"),
            "success_p95": stats["success_elapsed"].get("p95"),
            "success_max": stats["success_elapsed"].get("max"),
            "granted_p50": stats["success_granted"].get("p50"),
            "near_cut": stats["success_near_cut_ge_80pct_of_grant"],
            "timeouts": stats["n_timeouts"],
            "zero_grant": stats["n_zero_grant_timeouts"],
            "real_timeouts": stats["n_real_timeouts"],
            "real_timeout_granted_p50": stats["real_timeout_granted"].get("p50"),
            "coverage": {k: v.get("share_covered") for k, v in stats["coverage"].items()},
        }
        for cohort, stats in payload["cohorts"].items()
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    print("per-tool (production):")
    for tool, stats in payload["cohorts"]["production"]["per_tool"].items():
        s = stats["success"]
        print(
            f"  {tool:18s} n={s.get('n', 0):4d} p50={s.get('p50')} p95={s.get('p95')} max={s.get('max')}"
            f" real_to={stats['real_timeouts']} zero_to={stats['zero_grant_timeouts']}"
            f" to_granted_p50={stats['real_timeout_granted'].get('p50')}"
        )
    print("wrote", json_path, "rows", len(rows))


if __name__ == "__main__":
    main()
