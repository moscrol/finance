#!/usr/bin/env python3
"""Offline: tool success vs answer quality. Zero LLM. Does not change T.

Production runs are almost all standard/90s, so this is a mechanism check
(do successful tools go with better judge?), not a causal test of raising T.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

USERS_ROOT = Path.home() / ".local/share/finance-workbench/users"
# finance-base-ab 是家目录下的同级实验仓，不在本仓内；允许用环境变量指到别处。
AB_ROOT = Path(os.environ.get("FINANCE_BASE_AB_USERS", str(Path.home() / "finance-base-ab" / "out" / "users")))
OUT_DIR = Path(os.environ.get("OFFLINE_CENSUS_OUT_DIR", str(Path(__file__).resolve().parents[1] / "docs" / "verification")))
PRODUCTION_USER = "linxiaoqi5111"


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
    return _as_dict(event.get("payload"))


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


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def iter_run_dirs() -> list[tuple[str, str, Path]]:
    found: list[tuple[str, str, Path]] = []
    for path in sorted(USERS_ROOT.glob("*/runs/*")):
        if path.is_dir():
            found.append(("workbench", path.parent.parent.name, path))
    if AB_ROOT.is_dir():
        for path in sorted(AB_ROOT.glob("*/runs/*")):
            if path.is_dir():
                found.append(("finance-base-ab", path.parent.parent.name, path))
    return found


def extract_run(source: str, user: str, run_dir: Path) -> dict[str, Any] | None:
    report = _load_json(run_dir / "report.json")
    episode = _load_json(run_dir / "continuous-episode.json")
    if report is None and episode is None:
        return None
    report = report or {}
    episode = episode or {}
    gate = _as_dict(report.get("gate_receipt"))
    if not gate:
        gate = _as_dict(episode.get("semantic_verifier"))
    coverage = _as_dict(report.get("answer_marker_coverage"))
    frame = _as_dict(report.get("task_frame")) or _as_dict(episode.get("task_frame"))
    events = _events(episode)
    tool_ok = 0
    tool_timeout = 0
    # 工单 #28（INV-R4）起零授权未派发单独计：它们没被尝试，不进 tool_attempts。
    tool_not_dispatched = 0
    tool_error = 0
    kb_ok = 0
    kb_timeout = 0
    kb_error = 0
    fd_ok = 0
    zero_grant = 0
    granted_positive = 0
    for event in events:
        kind = str(event.get("kind") or "")
        payload = _payload(event)
        tool = str(payload.get("tool") or payload.get("name") or "")
        granted = _num(payload.get("stage_timeout_granted"))
        if kind == "tool_request" and granted is not None:
            if granted <= 0:
                zero_grant += 1
            else:
                granted_positive += 1
        if kind == "tool_result":
            tool_ok += 1
            if tool == "kb_search":
                kb_ok += 1
            if tool == "financial_data":
                fd_ok += 1
        elif kind == "tool_error":
            error = str(payload.get("error") or "")
            if error == "tool_not_dispatched":
                tool_not_dispatched += 1
            elif error == "tool_timeout":
                tool_timeout += 1
                if tool == "kb_search":
                    kb_timeout += 1
            else:
                tool_error += 1
                if tool == "kb_search":
                    kb_error += 1
    finishes = [
        _payload(event)
        for event in events
        if event.get("kind") == "finish"
    ]
    stop = None
    if finishes:
        stop = str(finishes[-1].get("stop_reason") or "") or None
    draft = episode.get("outcome")
    draft_chars = None
    if isinstance(draft, dict):
        text = draft.get("draft")
        if isinstance(text, str):
            draft_chars = len(text)
    answer_path = run_dir / "answer.md"
    answer_chars = None
    reverse_engineered = None
    if answer_path.is_file():
        text = answer_path.read_text(encoding="utf-8")
        answer_chars = len(text)
        reverse_engineered = any(
            marker in text
            for marker in ("反推", "推算", "由此反推", "不能当作已核验")
        )
    tool_attempts = tool_ok + tool_timeout + tool_error
    judge = gate.get("judge_status")
    if judge is not None:
        judge = str(judge)
    return {
        "source": source,
        "user": user,
        "run": run_dir.name,
        "production": user == PRODUCTION_USER,
        "question_type": frame.get("question_type"),
        "research_tier": episode.get("research_tier") or report.get("research_tier"),
        "judge_status": judge,
        "verified_status": gate.get("verified_status") or episode.get("verified_status"),
        "correlated_judge": gate.get("correlated_judge"),
        "marker_absent": len(coverage.get("absent") or []) if coverage else None,
        "stop_reason": stop,
        "used_repair": any(event.get("kind") == "repair_reentry" for event in events),
        "tool_ok": tool_ok,
        "tool_timeout": tool_timeout,
        "tool_not_dispatched": tool_not_dispatched,
        "tool_error": tool_error,
        "tool_attempts": tool_attempts,
        "kb_ok": kb_ok,
        "kb_timeout": kb_timeout,
        "kb_error": kb_error,
        "fd_ok": fd_ok,
        "zero_grant": zero_grant,
        "granted_positive": granted_positive,
        "draft_chars": draft_chars,
        "answer_chars": answer_chars,
        "reverse_engineered": reverse_engineered,
        "has_episode": bool(events),
        "has_report": bool(report),
    }


def _rate(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(n / d, 4)


def _bin_success(row: dict[str, Any]) -> str | None:
    attempts = int(row["tool_attempts"])
    if attempts <= 0:
        return "no_tools"
    rate = row["tool_ok"] / attempts
    if rate < 0.25:
        return "ok_<25%"
    if rate < 0.5:
        return "ok_25-50%"
    if rate < 0.75:
        return "ok_50-75%"
    return "ok_>=75%"


def summarize(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    judgeable = [row for row in rows if row.get("judge_status")]
    with_tools = [row for row in rows if row.get("has_episode")]
    by_judge = Counter(str(row.get("judge_status") or "missing") for row in rows)
    passed = sum(1 for row in judgeable if row["judge_status"] == "passed")
    repaired = sum(1 for row in judgeable if row["judge_status"] == "repaired")
    unavailable = sum(1 for row in judgeable if row["judge_status"] == "unavailable")
    bins: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in with_tools:
        bucket = _bin_success(row)
        if bucket:
            bins[bucket].append(row)
    bin_table = {}
    for name in ("no_tools", "ok_<25%", "ok_25-50%", "ok_50-75%", "ok_>=75%"):
        group = bins.get(name) or []
        g_judge = [row for row in group if row.get("judge_status")]
        bin_table[name] = {
            "n": len(group),
            "judgeable": len(g_judge),
            "passed": sum(1 for row in g_judge if row["judge_status"] == "passed"),
            "repaired": sum(1 for row in g_judge if row["judge_status"] == "repaired"),
            "unavailable": sum(
                1 for row in g_judge if row["judge_status"] == "unavailable"
            ),
            "passed_rate": _rate(
                sum(1 for row in g_judge if row["judge_status"] == "passed"),
                len(g_judge),
            ),
            "mean_answer_chars": (
                round(
                    statistics.fmean(
                        [
                            float(row["answer_chars"])
                            for row in group
                            if row.get("answer_chars")
                        ]
                    ),
                    1,
                )
                if any(row.get("answer_chars") for row in group)
                else None
            ),
        }
    kb_ok = [row for row in with_tools if int(row["kb_ok"]) > 0]
    kb_fail = [row for row in with_tools if int(row["kb_ok"]) == 0]
    zero_grant_rows = [row for row in with_tools if int(row["zero_grant"]) > 0]
    no_zero_grant = [row for row in with_tools if int(row["zero_grant"]) == 0]

    def _judge_rates(group: list[dict[str, Any]]) -> dict[str, Any]:
        g_judge = [row for row in group if row.get("judge_status")]
        return {
            "n": len(group),
            "judgeable": len(g_judge),
            "passed_rate": _rate(
                sum(1 for row in g_judge if row["judge_status"] == "passed"),
                len(g_judge),
            ),
            "repaired_rate": _rate(
                sum(1 for row in g_judge if row["judge_status"] == "repaired"),
                len(g_judge),
            ),
            "unavailable_rate": _rate(
                sum(1 for row in g_judge if row["judge_status"] == "unavailable"),
                len(g_judge),
            ),
        }

    model_finish = sum(1 for row in with_tools if row.get("stop_reason") == "model_finish")
    return {
        "label": label,
        "n": len(rows),
        "with_episode": len(with_tools),
        "judgeable": len(judgeable),
        "judge_counts": dict(by_judge),
        "passed_rate": _rate(passed, len(judgeable)),
        "repaired_rate": _rate(repaired, len(judgeable)),
        "unavailable_rate": _rate(unavailable, len(judgeable)),
        "model_finish_rate": _rate(model_finish, len(with_tools)),
        "repair_rate": _rate(
            sum(1 for row in with_tools if row.get("used_repair")),
            len(with_tools),
        ),
        "mean_tool_ok": (
            round(statistics.fmean(row["tool_ok"] for row in with_tools), 3)
            if with_tools
            else None
        ),
        "mean_tool_timeout": (
            round(statistics.fmean(row["tool_timeout"] for row in with_tools), 3)
            if with_tools
            else None
        ),
        "by_tool_success": bin_table,
        "kb_search_ok": _judge_rates(kb_ok),
        "kb_search_none": _judge_rates(kb_fail),
        "had_zero_grant": _judge_rates(zero_grant_rows),
        "no_zero_grant": _judge_rates(no_zero_grant),
        "tiers": dict(Counter(str(row.get("research_tier") or "missing") for row in rows)),
    }


def main() -> int:
    rows = []
    for source, user, run_dir in iter_run_dirs():
        row = extract_run(source, user, run_dir)
        if row:
            rows.append(row)
    production = [row for row in rows if row["production"]]
    payload = {
        "n_all": len(rows),
        "n_production": len(production),
        "caveat": (
            "Production T is essentially constant (standard/90). "
            "This measures whether tool success co-moves with judge, "
            "not whether raising T causes better answers."
        ),
        "all": summarize(rows, "all_users"),
        "production": summarize(production, "linxiaoqi5111"),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / "2026-09-02-budget-quality-offline.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
