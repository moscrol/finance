#!/usr/bin/env python3
"""Offline abstain-rate baseline from the 2026-08-27 four-arm 38-question artifacts.

Does not call any LLM. Spec §3.2 (P1) wants an abstain-rate baseline on the frozen
set (knevo28 + D-group 10) before judging whether P0/P2/P3 moved it. The four arms
already ran that exact set on 08-27; this reads their answers back with the same
classifier the ablation harness now uses, so the number is comparable to whatever
the next live run produces.

Abstention != wrong: six cases expect a refusal (C1/C2/C3/C8/D7/D8). Both rates are
reported; neither is folded into any score.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.abstention import (  # noqa: E402
    abstain_rate,
    classify_episode,
    classify_probe_receipt,
    classify_text,
)

FOUR_ARM_ROOT = Path(os.environ.get("FOUR_ARM_ROOT", str(Path.home() / ".finance-runtime" / "four-arm-20260827")))
# 8792 / 8796 探针把答案写进各自服务的 users 目录，四臂目录里只有 run_id。
USERS_ROOTS = {
    "8792": Path(os.environ.get("FOUR_ARM_8792_USERS", str(Path.home() / ".local/share/finance-workbench/users/fourarm0827-8792"))),
    "8796": Path(
        os.environ.get(
            "FOUR_ARM_8796_USERS",
            str(Path.home() / ".local/share/finance-workbench-capability-sidecar/users/fourarm0827-8796"),
        )
    ),
}
OUT_DIR = Path(os.environ.get("OFFLINE_CENSUS_OUT_DIR", str(REPO / "docs" / "verification")))
ARMS = ("react-claude", "component", "8792", "8796")
UNSEEN_PREFIX = "D"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_cases() -> list[dict[str, Any]]:
    return list(_load_json(FOUR_ARM_ROOT / "frozen" / "all38-questions.json")["cases"])


def expect_refusal_ids() -> set[str]:
    ids: set[str] = set()
    for path in (
        REPO / "intelligence" / "eval" / "cases" / "acceptance_cases.json",
        FOUR_ARM_ROOT / "frozen" / "rewrite_acceptance_cases.json",
    ):
        if not path.exists():
            continue
        data = _load_json(path)
        cases = data.get("cases") if isinstance(data, dict) else data
        for case in cases or []:
            if case.get("expect_refusal"):
                ids.add(str(case.get("id") or case.get("case_id")))
    return ids


def read_arm_case(arm: str, case_id: str) -> dict[str, Any] | None:
    case_dir = FOUR_ARM_ROOT / "arms" / arm / case_id
    if not case_dir.is_dir():
        return None
    if arm == "component":
        answer_path = case_dir / "turn-01" / "answer.md"
        if not answer_path.exists():
            return {"case_id": case_id, "arm": arm, "state": "unreadable"}
        verdict = classify_text(answer_path.read_text(encoding="utf-8"))
        return {"case_id": case_id, "arm": arm, "state": "read", **verdict.to_dict()}
    if arm == "react-claude":
        session = _load_json(case_dir / "session.json")
        verdict = classify_text(str(session.get("answer") or ""))
        return {"case_id": case_id, "arm": arm, "state": "read", **verdict.to_dict()}
    probe_path = case_dir / "probe.json"
    if not probe_path.exists():
        return {"case_id": case_id, "arm": arm, "state": "unreadable"}
    probe = _load_json(probe_path)
    run_id = str(probe.get("run_id") or "")
    run_dir = USERS_ROOTS[arm] / "runs" / run_id
    answer_path = run_dir / "answer.md"
    answer = answer_path.read_text(encoding="utf-8") if answer_path.exists() else None
    episode_path = run_dir / "continuous-episode.json"
    if episode_path.exists():
        verdict = classify_episode(_load_json(episode_path), answer=answer, gate_receipt=probe.get("gate_receipt"))
    else:
        verdict = classify_probe_receipt(probe, answer=answer)
    return {
        "case_id": case_id,
        "arm": arm,
        "state": "read" if answer is not None else "no_answer_file",
        "run_id": run_id,
        "has_episode": episode_path.exists(),
        **verdict.to_dict(),
    }


def main() -> None:
    cases = frozen_cases()
    refusal_ids = expect_refusal_ids()
    per_arm: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        arm_rows = [row for row in (read_arm_case(arm, c["id"]) for c in cases) if row is not None]
        readable = [row for row in arm_rows if row.get("state") == "read"]
        rows.extend(arm_rows)

        def _cohort(subset: list[dict[str, Any]]) -> dict[str, Any]:
            return abstain_rate(subset, expect_refusal=[row["case_id"] in refusal_ids for row in subset])

        seen = [row for row in readable if not row["case_id"].startswith(UNSEEN_PREFIX)]
        unseen = [row for row in readable if row["case_id"].startswith(UNSEEN_PREFIX)]
        per_arm[arm] = {
            "n_cases_present": len(arm_rows),
            "n_readable": len(readable),
            "all": _cohort(readable),
            "seen_ABC": _cohort(seen),
            "unseen_D": _cohort(unseen),
            "abstained_case_ids": sorted(row["case_id"] for row in readable if row.get("abstained")),
        }
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(FOUR_ARM_ROOT),
        "n_cases": len(cases),
        "expect_refusal_ids": sorted(refusal_ids),
        "classifier": "intelligence.eval.abstention (episode_events > probe_receipt > text_markers)",
        "per_arm": per_arm,
        "rows": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "2026-09-03-abstain-rate-baseline-offline.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{'arm':14s} {'read':>5s} {'abstain':>8s} {'unexpected':>11s} {'honored':>8s} | unseen D abstain | by_reason")
    for arm, stats in per_arm.items():
        a, d = stats["all"], stats["unseen_D"]
        print(
            f"{arm:14s} {stats['n_readable']:5d} {a['abstained']:3d}/{a['n']:<4d}"
            f" {a['abstained_where_answer_expected']:4d}/{a['n_answer_expected']:<6d}"
            f" {a['refusals_honored']:3d}/{a['n_refusal_expected']:<4d} | {d['abstained']:2d}/{d['n']:<3d}"
            f"          | {a['by_reason']}"
        )
    print("wrote", json_path)


if __name__ == "__main__":
    main()
