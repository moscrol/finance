#!/usr/bin/env python3
"""只读计分：长尾 15 题 live A/B。不碰 8792/8793，不改 runner/夹具。

对照窗目录：~/.finance-runtime/longtail-ab-20260816/
workbench runs：~/.local/share/finance-workbench/users/longtail-ab-0816/runs/

清污：progress.jsonl 前 8 行与 12:45/12:49/13:07/13:10 孤儿不入对照。
护栏：按 FREEZE_ONLY 已登记口径——只查 on 臂 5 题，确认【长尾回答骨架】不出现。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.episode_bindings_rate import legacy_bindings_rate  # noqa: E402

FIXTURE = REPO / (
    "intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json"
)
LIVE_ROOT = Path.home() / ".finance-runtime" / "longtail-ab-20260816"
WB_RUNS = (
    Path.home()
    / ".local/share/finance-workbench/users/longtail-ab-0816/runs"
)
HEADING = "【长尾回答骨架】"
MARKERS = ("据此判断", "这说明", "这意味着")
HONEST_MARKERS = ("未取得", "现有证据不足，暂不能可靠回答", "暂不能可靠回答")
JUDGE_OUTAGE_PREFIXES = (
    "结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成",
    "本次未完成独立复核（复核服务超时）",
)
CLEAN_AFTER = "run_20260816_131941_597875"
POLLUTED_PROGRESS_RUN_IDS = (
    "run_20260816_125145_832107",
    "run_20260816_125416_980000",
    "run_20260816_125649_486360",
    "run_20260816_125920_927309",
    "run_20260816_125957_959190",
    "run_20260816_130231_231445",
    "run_20260816_130403_960625",
    "run_20260816_130525_453745",
)
ORPHAN_RUN_IDS = (
    "run_20260816_124504_615880",
    "run_20260816_124957_138951",
    "run_20260816_131020_573635",
)
KICKSTART_INTERRUPTED = "run_20260816_130709_427017"
OWNER_IDS = {
    "stock-deep-dive",
    "financial-analysis",
    "news-impact",
    "theme-research",
}
HIGHWAY_TYPES = {
    "market_forecast",
    "market_watch",
    "market_cause",
    "dated_market_review",
}
SENTENCE_SPLIT = re.compile(r"(?<=[。！？])")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _plan(payload: dict[str, Any]) -> list[str]:
    longtail = [c for c in payload["cases"] if c.get("role") == "longtail"]
    guards = [c for c in payload["cases"] if c.get("role") == "guard"]
    slots: list[str] = []
    for repeat in range(1, 4):
        for case in longtail:
            slots.append(f"off:{case['id']}:r{repeat}")
        for case in longtail:
            slots.append(f"on:{case['id']}:r{repeat}")
    for case in guards:
        slots.append(f"on:{case['id']}:r1")
    return slots


def _read_answer(run_id: str) -> str:
    path = WB_RUNS / run_id / "answer.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _episode(run_id: str) -> dict[str, Any] | None:
    path = WB_RUNS / run_id / "continuous-episode.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _report(run_id: str) -> dict[str, Any]:
    path = WB_RUNS / run_id / "report.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _artifact_has_heading(run_id: str) -> bool:
    root = WB_RUNS / run_id
    if not root.is_dir():
        return False
    for path in root.iterdir():
        if path.suffix not in {".json", ".jsonl", ".md"}:
            continue
        try:
            if HEADING in path.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def _honest_gap(text: str) -> bool:
    return any(marker in text for marker in HONEST_MARKERS)


def _judge_outage_candidate(text: str) -> bool:
    return any(prefix in text for prefix in JUDGE_OUTAGE_PREFIXES)


def _empty_shell(text: str, honest: bool, delivered: bool, outage: bool) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if honest or delivered or outage:
        return False
    return True


def _bindings_rate(episode: dict[str, Any] | None) -> float | None:
    # 长尾默认仍走旧口径（全槽哈希）。分层口径见 episode_bindings_rate.stratified_evidence_bound_rate。
    return legacy_bindings_rate(episode)


def _judge_peel(episode: dict[str, Any] | None) -> dict[str, Any]:
    if episode is None:
        return {
            "judge_status": "not_applicable",
            "rejected": None,
            "total": None,
            "peel_rate": None,
        }
    semantic = episode.get("semantic_verifier")
    status = None
    if isinstance(semantic, dict):
        status = semantic.get("judge_status")
    metrics = episode.get("metrics")
    if status is None and isinstance(metrics, dict):
        status = metrics.get("semantic_status")
    if status in {None, "unavailable"}:
        return {
            "judge_status": status or "unavailable",
            "rejected": None,
            "total": None,
            "peel_rate": None,
        }
    report = {}
    if isinstance(semantic, dict):
        report = semantic.get("judge_report") or semantic.get("report") or {}
    rejected = None
    if isinstance(report, dict):
        indexes = report.get("rejected_sentence_indexes")
        if isinstance(indexes, list):
            rejected = len(indexes)
    draft = ""
    outcome = episode.get("outcome")
    if isinstance(outcome, dict):
        draft = str(outcome.get("draft") or "")
    if not draft and isinstance(semantic, dict):
        draft = str(semantic.get("public_answer") or "")
    sentences = [part for part in SENTENCE_SPLIT.split(draft) if part.strip()]
    total = len(sentences) if sentences else (None if rejected is None else 0)
    peel = None
    if rejected is not None and total:
        peel = rejected / total
    return {
        "judge_status": status,
        "rejected": rejected,
        "total": total,
        "peel_rate": peel,
    }


def _routing(report: dict[str, Any]) -> dict[str, Any]:
    frame = report.get("task_frame") if isinstance(report.get("task_frame"), dict) else {}
    intent = report.get("turn_intent") if isinstance(report.get("turn_intent"), dict) else {}
    qtype = frame.get("question_type") or intent.get("question_type")
    owner = intent.get("answer_owner")
    confidence = frame.get("confidence")
    absorbed = qtype in HIGHWAY_TYPES or owner in OWNER_IDS
    return {
        "question_type": qtype,
        "answer_owner": owner,
        "confidence": confidence,
        "routing_absorbed": bool(absorbed),
    }


def _tokens(report: dict[str, Any]) -> int | None:
    growth = report.get("context_growth")
    if not isinstance(growth, dict):
        return None
    value = growth.get("cumulative_input_tokens")
    return int(value) if isinstance(value, (int, float)) else None


def _coverage(payload: dict[str, Any]) -> dict[str, Any]:
    expected = _plan(payload)
    present: dict[str, dict[str, Any]] = {}
    for path in sorted((LIVE_ROOT / "runs").glob("*.json")):
        try:
            data = _load_json(path)
        except (OSError, ValueError):
            continue
        slot = str(data.get("slot") or "")
        if not slot:
            continue
        present[slot] = data
    missing = [slot for slot in expected if slot not in present]
    extra = sorted(set(present) - set(expected))
    outcomes = Counter(str(data.get("terminal_outcome") or "unknown") for data in present.values())
    log_path = LIVE_ROOT / "runner.out.log"
    log_tail = ""
    all_processed = False
    if log_path.is_file():
        lines = [line.rstrip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        log_tail = lines[-1] if lines else ""
        all_processed = any(line == "all slots processed" for line in lines)
    return {
        "expected": 95,
        "planned": expected,
        "present_count": len(present),
        "missing": missing,
        "extra": extra,
        "outcomes": dict(outcomes),
        "all_slots_processed_log": all_processed,
        "log_tail": log_tail,
        "complete": all_processed and not missing and len(present) == 95,
        "slots": present,
    }


def _score_slot(slot: str, smoke: dict[str, Any], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    run_id = str(smoke.get("run_id") or "")
    case_id = str(smoke.get("case_id") or "")
    case = cases.get(case_id, {})
    answer = _read_answer(run_id) if run_id else ""
    report = _report(run_id) if run_id else {}
    episode = _episode(run_id) if run_id else None
    coverage = report.get("answer_marker_coverage")
    present_outputs = []
    if isinstance(coverage, dict) and isinstance(coverage.get("present"), list):
        present_outputs = [str(item) for item in coverage["present"]]
    delivered = "direct_answer" in present_outputs and bool(answer.strip())
    honest = _honest_gap(answer)
    outage = _judge_outage_candidate(answer)
    empty = _empty_shell(answer, honest, delivered, outage)
    compliant = (delivered or honest) and not outage
    routing = _routing(report)
    peel = _judge_peel(episode)
    return {
        "slot": slot,
        "arm": smoke.get("arm"),
        "case_id": case_id,
        "role": smoke.get("role") or case.get("role"),
        "stratum": smoke.get("stratum") or case.get("stratum"),
        "repeat": smoke.get("repeat"),
        "run_id": run_id,
        "terminal_outcome": smoke.get("terminal_outcome"),
        "elapsed_s": smoke.get("elapsed_s"),
        "answer_chars": len(answer),
        "direct_answer_delivered": delivered,
        "honest_gap": honest,
        "judge_outage_candidate": outage,
        "empty_shell": empty,
        "compliant_delivery": compliant,
        "heading_in_artifacts": _artifact_has_heading(run_id) if run_id else False,
        "marker_in_answer": {marker: marker in answer for marker in MARKERS},
        "evidence_bound_rate": _bindings_rate(episode),
        "input_tokens": _tokens(report),
        **routing,
        **peel,
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pp(delta: float | None) -> float | None:
    return None if delta is None else round(delta * 100, 2)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    longtail = [row for row in rows if row.get("role") == "longtail" and not row.get("routing_absorbed")]
    absorbed = [row for row in rows if row.get("role") == "longtail" and row.get("routing_absorbed")]
    guards = [row for row in rows if row.get("role") == "guard"]
    layers = {
        "all": longtail,
        "outlook": [row for row in longtail if row.get("stratum") == "outlook"],
        "residual": [row for row in longtail if row.get("stratum") == "residual"],
    }
    summary: dict[str, Any] = {"routing_absorbed": [row["slot"] for row in absorbed]}
    for name, subset in layers.items():
        by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in subset:
            by_arm[str(row.get("arm"))].append(row)
        layer: dict[str, Any] = {}
        for arm, items in by_arm.items():
            peelable = [row for row in items if row.get("peel_rate") is not None]
            bound = [float(row["evidence_bound_rate"]) for row in items if row.get("evidence_bound_rate") is not None]
            tokens = [float(row["input_tokens"]) for row in items if row.get("input_tokens") is not None]
            elapsed = [float(row["elapsed_s"]) for row in items if row.get("elapsed_s") is not None]
            layer[arm] = {
                "n": len(items),
                "completed": sum(1 for row in items if row.get("terminal_outcome") == "completed"),
                "degraded": sum(1 for row in items if row.get("terminal_outcome") == "degraded"),
                "failed": sum(1 for row in items if row.get("terminal_outcome") == "failed"),
                "direct_answer_rate": _mean([1.0 if row["direct_answer_delivered"] else 0.0 for row in items]),
                "compliant_delivery_rate": _mean([1.0 if row["compliant_delivery"] else 0.0 for row in items]),
                "empty_shell_rate": _mean([1.0 if row["empty_shell"] else 0.0 for row in items]),
                "honest_gap_rate": _mean([1.0 if row["honest_gap"] else 0.0 for row in items]),
                "judge_outage_candidate_rate": _mean(
                    [1.0 if row.get("judge_outage_candidate") else 0.0 for row in items]
                ),
                "judge_unavailable": sum(1 for row in items if row.get("judge_status") in {None, "unavailable"}),
                "peel_n": len(peelable),
                "peel_rate": _mean([float(row["peel_rate"]) for row in peelable]),
                "evidence_bound_rate": _mean(bound),
                "mean_input_tokens": _mean(tokens),
                "mean_elapsed_s": _mean(elapsed),
            }
        off = layer.get("off") or {}
        on = layer.get("on") or {}
        layer["delta"] = {
            "compliant_delivery_pp": _pp(
                (on.get("compliant_delivery_rate") or 0) - (off.get("compliant_delivery_rate") or 0)
                if on.get("compliant_delivery_rate") is not None and off.get("compliant_delivery_rate") is not None
                else None
            ),
            "peel_pp": _pp(
                (on.get("peel_rate") or 0) - (off.get("peel_rate") or 0)
                if on.get("peel_rate") is not None and off.get("peel_rate") is not None
                else None
            ),
            "evidence_bound_pp": _pp(
                (on.get("evidence_bound_rate") or 0) - (off.get("evidence_bound_rate") or 0)
                if on.get("evidence_bound_rate") is not None and off.get("evidence_bound_rate") is not None
                else None
            ),
            "elapsed_s": (
                (on.get("mean_elapsed_s") or 0) - (off.get("mean_elapsed_s") or 0)
                if on.get("mean_elapsed_s") is not None and off.get("mean_elapsed_s") is not None
                else None
            ),
            "input_tokens": (
                (on.get("mean_input_tokens") or 0) - (off.get("mean_input_tokens") or 0)
                if on.get("mean_input_tokens") is not None and off.get("mean_input_tokens") is not None
                else None
            ),
        }
        summary[name] = layer
    summary["guards"] = {
        "n": len(guards),
        "heading_hits": [row["slot"] for row in guards if row.get("heading_in_artifacts")],
        "routing": [
            {
                "slot": row["slot"],
                "run_id": row["run_id"],
                "question_type": row.get("question_type"),
                "answer_owner": row.get("answer_owner"),
                "confidence": row.get("confidence"),
                "terminal_outcome": row.get("terminal_outcome"),
                "elapsed_s": row.get("elapsed_s"),
            }
            for row in guards
        ],
    }
    return summary


def build_receipt_payload() -> dict[str, Any]:
    payload = _load_json(FIXTURE)
    if payload.get("baseline", {}).get("tip") != "773b3d7e":
        raise SystemExit("fixture tip drifted; refuse to score")
    if payload.get("sample_design", {}).get("threshold_pp") != 5.0:
        raise SystemExit("5pp lock drifted; refuse to score")
    cases = {str(case["id"]): case for case in payload["cases"]}
    coverage = _coverage(payload)
    rows = [
        _score_slot(slot, smoke, cases)
        for slot, smoke in sorted(coverage["slots"].items())
    ]
    return {
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fixture": str(FIXTURE),
        "fixture_tip": "773b3d7e",
        "threshold_pp": 5.0,
        "clean_after_run_id": CLEAN_AFTER,
        "excluded": {
            "polluted_progress_run_ids": list(POLLUTED_PROGRESS_RUN_IDS),
            "orphan_run_ids": list(ORPHAN_RUN_IDS),
            "kickstart_interrupted": KICKSTART_INTERRUPTED,
        },
        "coverage": {
            "expected": coverage["expected"],
            "present_count": coverage["present_count"],
            "missing": coverage["missing"],
            "extra": coverage["extra"],
            "outcomes": coverage["outcomes"],
            "all_slots_processed_log": coverage["all_slots_processed_log"],
            "log_tail": coverage["log_tail"],
            "complete": coverage["complete"],
        },
        "summary": _summarize(rows),
        "slots": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print full JSON")
    parser.add_argument(
        "--out",
        type=Path,
        help="write JSON receipt payload",
    )
    args = parser.parse_args()
    data = build_receipt_payload()
    cov = data["coverage"]
    print(f"coverage {cov['present_count']}/95 complete={cov['complete']} log={cov['log_tail']!r}")
    print(f"missing {len(cov['missing'])} outcomes={cov['outcomes']}")
    for layer in ("all", "outlook", "residual"):
        block = data["summary"][layer]
        print(f"\n## {layer}")
        for arm in ("off", "on"):
            stats = block.get(arm)
            if not stats:
                print(f"  {arm}: no rows yet")
                continue
            print(
                f"  {arm}: n={stats['n']} completed={stats['completed']} "
                f"degraded={stats['degraded']} failed={stats['failed']} "
                f"compliant={stats['compliant_delivery_rate']} "
                f"empty={stats['empty_shell_rate']} "
                f"outage={stats['judge_outage_candidate_rate']} "
                f"peel_n={stats['peel_n']} peel={stats['peel_rate']} "
                f"eb={stats['evidence_bound_rate']} "
                f"judge_unavail={stats['judge_unavailable']}"
            )
        print(f"  delta={block.get('delta')}")
    guards = data["summary"]["guards"]
    print(f"\n## guards n={guards['n']} heading_hits={guards['heading_hits']}")
    if args.out:
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if cov["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
