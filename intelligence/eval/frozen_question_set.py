"""冻结 30 题分层集：九题原样作子集，不改判据表达力。"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from intelligence.eval.arm_a_calibration import FROZEN_NINE_CASE_IDS


FROZEN_THIRTY_RELATIVE = (
    "intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json"
)
PROFILE_LAYERS: tuple[str, ...] = (
    "quick-research",
    "daily-review",
    "deep-research",
)
PROFILE_TO_TIER = {
    "quick-research": "quick",
    "daily-review": "standard",
    "deep-research": "deep",
}
LAYER_SIZE = 10


class FrozenQuestionSetError(ValueError):
    """三十题冻结集不满足分层或九题子集约束。"""


def default_frozen_thirty_path() -> Path:
    return Path(__file__).resolve().parents[2] / FROZEN_THIRTY_RELATIVE


def load_frozen_question_set(
    path: Path | None = None,
) -> dict[str, Any]:
    target = path if path is not None else default_frozen_thirty_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise FrozenQuestionSetError("question set must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 30:
        raise FrozenQuestionSetError("question set must contain exactly 30 cases")
    ids = [str(case.get("id") or "") for case in cases]
    if len(set(ids)) != 30 or any(not item for item in ids):
        raise FrozenQuestionSetError("case ids must be 30 unique non-empty strings")
    nine = {str(case.get("id") or "") for case in cases[:9]}
    if tuple(ids[:9]) != FROZEN_NINE_CASE_IDS:
        raise FrozenQuestionSetError("first nine cases must be the frozen nine in order")
    if nine != set(FROZEN_NINE_CASE_IDS):
        raise FrozenQuestionSetError("frozen nine must be a subset")
    counts = {layer: 0 for layer in PROFILE_LAYERS}
    for case in cases:
        if not isinstance(case, Mapping):
            raise FrozenQuestionSetError("each case must be an object")
        profile = str(case.get("profile") or "")
        tier = str(case.get("tier") or "")
        if profile not in PROFILE_TO_TIER:
            raise FrozenQuestionSetError(f"unknown profile {profile!r}")
        if tier != PROFILE_TO_TIER[profile]:
            raise FrozenQuestionSetError(
                f"{case.get('id')} profile {profile} must map to tier {PROFILE_TO_TIER[profile]}"
            )
        counts[profile] += 1
        outputs = case.get("required_outputs")
        if not isinstance(outputs, list) or not outputs:
            raise FrozenQuestionSetError(f"{case.get('id')} missing required_outputs")
    if counts != {layer: LAYER_SIZE for layer in PROFILE_LAYERS}:
        raise FrozenQuestionSetError(f"layers must be 10/10/10, got {counts}")
    return {
        "path_name": target.name,
        "case_count": 30,
        "case_ids": ids,
        "frozen_nine": list(FROZEN_NINE_CASE_IDS),
        "layers": counts,
        "cases": cases,
    }


__all__ = [
    "FROZEN_THIRTY_RELATIVE",
    "FrozenQuestionSetError",
    "LAYER_SIZE",
    "PROFILE_LAYERS",
    "PROFILE_TO_TIER",
    "default_frozen_thirty_path",
    "load_frozen_question_set",
]
