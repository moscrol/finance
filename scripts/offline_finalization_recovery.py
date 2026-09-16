#!/usr/bin/env python3
"""离线普查：合成失败后的「抢救一次」（``_recover_finalization``）在生产上多常触发、结局如何。

零 LLM，零生产改动。给 `2026-09-02-repair-policy-state-machine.md` §2.2 那台独立状态机的
拍板（要不要并进 repair cycle 的账）提供频次与结局分布——没有频次，「并不并」只是口味。

读什么：每份 ``continuous-episode.json`` 的事件流。
- ``finalization_recovery_started``（payload.failure_reason）= 抢救被触发；
- ``finalization_recovery_outcome``（status ∈ {recovered, failed}，failed 带 reason）= 结局；
- 同一 episode 里有没有 ``repair_goal``（修复轮）= 两台状态机是否同场出现；
- 顶层 ``repair_cycles`` / ``repair_attempts`` = adapter 侧修复账。

输出：``docs/verification/2026-09-03-finalization-recovery-offline.json``（可用
``OFFLINE_CENSUS_OUT_DIR`` 改目录）+ stdout 同一份。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any

USERS_ROOT = Path.home() / ".local/share/finance-workbench/users"
# finance-base-ab 是家目录下的同级实验仓，不在本仓内；允许用环境变量指到别处。
AB_ROOT = Path(os.environ.get("FINANCE_BASE_AB_USERS", str(Path.home() / "finance-base-ab" / "out" / "users")))
OUT_DIR = Path(os.environ.get("OFFLINE_CENSUS_OUT_DIR", str(Path(__file__).resolve().parents[1] / "docs" / "verification")))
PRODUCTION_USER = "linxiaoqi5111"
RECENT_DAYS = 14


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
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _episode_time(episode: dict[str, Any], events: list[dict[str, Any]]) -> datetime | None:
    for event in events:
        stamp = _parse_at(_payload(event).get("at")) or _parse_at(event.get("at"))
        if stamp is not None:
            return stamp
    return None


def _find_episodes() -> list[tuple[str, str, Path]]:
    found: list[tuple[str, str, Path]] = []
    for path in sorted(USERS_ROOT.glob("*/runs/*/continuous-episode.json")):
        found.append(("production", path.parent.parent.parent.name, path))
    if AB_ROOT.is_dir():
        for path in sorted(AB_ROOT.glob("*/runs/*/continuous-episode.json")):
            found.append(("finance-base-ab", path.parent.parent.parent.name, path))
    return found


def _summarize(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    attempted = [row for row in rows if row["recovery_attempted"]]
    recovered = [row for row in attempted if row["recovery_status"] == "recovered"]
    failed = [row for row in attempted if row["recovery_status"] == "failed"]
    with_repair = [row for row in attempted if row["has_repair_goal"]]
    return {
        "label": label,
        "n_episodes": len(rows),
        "n_recovery_attempted": len(attempted),
        "attempt_rate": round(len(attempted) / len(rows), 4) if rows else None,
        "n_recovered": len(recovered),
        "n_failed": len(failed),
        "recovered_rate_given_attempt": (
            round(len(recovered) / len(attempted), 4) if attempted else None
        ),
        "failure_reason_at_trigger": dict(Counter(row["failure_reason"] for row in attempted)),
        "failed_recovery_reason": dict(Counter(row["failed_reason"] for row in failed)),
        "recovered_answer_status": dict(
            Counter(row["recovered_answer_status"] for row in recovered)
        ),
        "attempted_and_also_repair_goal": len(with_repair),
        "attempted_with_adapter_repair_cycles": dict(
            Counter(str(row["repair_cycles"]) for row in attempted)
        ),
        "final_stop_reason_of_attempted": dict(
            Counter(row["stop_reason"] for row in attempted)
        ),
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)
    rows: list[dict[str, Any]] = []
    unreadable = 0
    for source, user, path in _find_episodes():
        try:
            episode = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unreadable += 1
            continue
        if not isinstance(episode, dict):
            unreadable += 1
            continue
        events = _events(episode)
        started = [e for e in events if e.get("kind") == "finalization_recovery_started"]
        outcomes = [e for e in events if e.get("kind") == "finalization_recovery_outcome"]
        outcome = episode.get("outcome") if isinstance(episode.get("outcome"), dict) else {}
        last_outcome = _payload(outcomes[-1]) if outcomes else {}
        rows.append(
            {
                "source": source,
                "user": user,
                "run": path.parent.name,
                "at": _episode_time(episode, events),
                "recovery_attempted": bool(started),
                "recovery_started_count": len(started),
                "failure_reason": str(_payload(started[0]).get("failure_reason", ""))
                if started
                else "",
                "recovery_status": str(last_outcome.get("status", "")) if outcomes else "",
                "failed_reason": str(last_outcome.get("reason", ""))
                if last_outcome.get("status") == "failed"
                else "",
                "recovered_answer_status": str(last_outcome.get("answer_status", ""))
                if last_outcome.get("status") == "recovered"
                else "",
                "has_repair_goal": any(e.get("kind") == "repair_goal" for e in events),
                "repair_cycles": episode.get("repair_cycles"),
                "stop_reason": str(outcome.get("stop_reason", "")),
            }
        )

    production = [r for r in rows if r["source"] == "production" and r["user"] == PRODUCTION_USER]
    production_recent = [
        r for r in production if r["at"] is not None and r["at"] >= recent_cutoff
    ]
    payload: dict[str, Any] = {
        "generated_at": now.isoformat(timespec="seconds"),
        "roots": [str(USERS_ROOT), str(AB_ROOT)],
        "n_episode_files": len(rows),
        "n_unreadable": unreadable,
        "invariant_started_at_most_once": all(r["recovery_started_count"] <= 1 for r in rows),
        "queues": [
            _summarize(production, f"production · {PRODUCTION_USER}"),
            _summarize(
                production_recent, f"production · {PRODUCTION_USER} · last {RECENT_DAYS}d"
            ),
            _summarize(rows, "all users (incl. probes / finance-base-ab)"),
        ],
        "attempted_production_runs": [
            {
                "run": r["run"],
                "at": r["at"].isoformat(timespec="seconds") if r["at"] else None,
                "failure_reason": r["failure_reason"],
                "recovery_status": r["recovery_status"],
                "failed_reason": r["failed_reason"],
                "stop_reason": r["stop_reason"],
                "has_repair_goal": r["has_repair_goal"],
                "repair_cycles": r["repair_cycles"],
            }
            for r in production
            if r["recovery_attempted"]
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / "2026-09-03-finalization-recovery-offline.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
