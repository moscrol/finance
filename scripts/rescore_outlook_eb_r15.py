#!/usr/bin/env python3
"""R-15 离线重算：旧口径 vs 分层 evidence_bound。只读，不写 score.json。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from intelligence.eval.episode_bindings_rate import (  # noqa: E402
    judgment_hash_rate,
    legacy_bindings_rate,
    stratified_evidence_bound_rate,
)

FROZEN_PAIRS = (
    ("L01", "r3", "run_20260816_184616_575486", "run_20260816_184718_305950"),
    ("L03", "r2", "run_20260816_185728_883724", "run_20260816_185901_871285"),
    ("L05", "r2", "run_20260816_190515_806994", "run_20260816_190657_142513"),
)
SCORE_JSON = Path.home() / ".finance-runtime/outlook-ab-20260816/score.json"
WB_RUNS = Path.home() / ".local/share/finance-workbench/users/outlook-ab-0816/runs"
FORBIDDEN_OUTPUT = SCORE_JSON


def _load_episode(run_id: str) -> dict[str, Any] | None:
    path = WB_RUNS / run_id / "continuous-episode.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _mean(values: list[float | None]) -> float | None:
    present = [float(item) for item in values if item is not None]
    return sum(present) / len(present) if present else None


def _pp(pre: float | None, post: float | None) -> float | None:
    if pre is None or post is None:
        return None
    return round((post - pre) * 100, 1)


def _layer_pred(name: str, row: dict[str, Any]) -> bool:
    role = row.get("role")
    if name == "main42":
        return role == "outlook"
    if name == "core_unabsorbed":
        return role == "outlook" and not row.get("routing_absorbed") and row.get("case_id") != "O06"
    if name == "l01":
        return role == "outlook" and row.get("case_id") == "L01"
    if name == "absorbed":
        return role == "outlook" and (row.get("routing_absorbed") or row.get("case_id") == "O06")
    if name == "guards":
        return role == "guard"
    return False


def build(score: dict[str, Any]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    triples_ok = True
    for case_id, repeat, pre_id, post_id in FROZEN_PAIRS:
        row: dict[str, Any] = {"case_id": case_id, "repeat": repeat}
        for arm, run_id in (("pre", pre_id), ("post", post_id)):
            episode = _load_episode(run_id)
            legacy = legacy_bindings_rate(episode)
            stratified = stratified_evidence_bound_rate(episode)
            row[arm] = {
                "run_id": run_id,
                "legacy": legacy,
                "stratified": stratified,
                "judgment_hash_rate": judgment_hash_rate(episode),
            }
        if row["post"]["stratified"] != 1.0 or row["pre"]["stratified"] != 1.0:
            triples_ok = False
        pairs.append(row)

    layers: dict[str, Any] = {}
    for name in ("main42", "core_unabsorbed", "l01", "absorbed", "guards"):
        by_legacy: dict[str, list[float | None]] = defaultdict(list)
        by_strat: dict[str, list[float | None]] = defaultdict(list)
        for slot in score.get("slots") or []:
            if not isinstance(slot, dict) or not _layer_pred(name, slot):
                continue
            arm = str(slot.get("arm") or "")
            episode = _load_episode(str(slot.get("run_id") or ""))
            by_legacy[arm].append(legacy_bindings_rate(episode))
            by_strat[arm].append(stratified_evidence_bound_rate(episode))
        pre_legacy, post_legacy = _mean(by_legacy["pre"]), _mean(by_legacy["post"])
        pre_strat, post_strat = _mean(by_strat["pre"]), _mean(by_strat["post"])
        layers[name] = {
            "legacy": {
                "pre": pre_legacy,
                "post": post_legacy,
                "pp": _pp(pre_legacy, post_legacy),
                "n_pre": sum(1 for item in by_legacy["pre"] if item is not None),
                "n_post": sum(1 for item in by_legacy["post"] if item is not None),
            },
            "stratified": {
                "pre": pre_strat,
                "post": post_strat,
                "pp": _pp(pre_strat, post_strat),
                "n_pre": sum(1 for item in by_strat["pre"] if item is not None),
                "n_post": sum(1 for item in by_strat["post"] if item is not None),
            },
        }

    main_pp = (layers["main42"]["stratified"] or {}).get("pp")
    window_within_5 = main_pp is not None and abs(main_pp) <= 5.0
    return {
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_score_json": "~/.finance-runtime/outlook-ab-20260816/score.json",
        "source_scored_at": score.get("scored_at"),
        "wrote_score_json": False,
        "frozen_pairs": pairs,
        "triples_stratified_1": triples_ok,
        "layers": layers,
        "window_main42_stratified_pp": main_pp,
        "window_within_pm5": window_within_5,
        "r15_prediction": {
            "triples": "confirmed" if triples_ok else "refuted",
            "window_pm5": "confirmed" if window_within_5 else "not_met",
            "overall": "pending",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/verification/2026-08-16-outlook-eb-r15-rescore.json"),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output == FORBIDDEN_OUTPUT.resolve():
        raise SystemExit("refuse to overwrite frozen score.json")
    score = json.loads(SCORE_JSON.read_text(encoding="utf-8"))
    if score.get("fixture_sha256") != "ac464158a724c6312b373b59a4bae2ebc1f81925b5c6e284e85c22547bc7d608":
        raise SystemExit("score.json fixture hash drifted; refuse")
    payload = build(score)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"triples_ok={payload['triples_stratified_1']} main42_pp={payload['window_main42_stratified_pp']} within_5={payload['window_within_pm5']}")
    print(f"wrote {output} (score.json untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
