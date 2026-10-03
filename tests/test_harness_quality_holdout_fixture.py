"""Guard the frozen, evaluation-only content holdout manifest."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "intelligence/eval/fixtures/harness_quality_holdout_20261004.json"


def _gold(case: dict[str, object]) -> bytes:
    return json.dumps(
        {
            "gold_points": case["gold_points"],
            "hard_errors": case["hard_errors"],
            "scoring_dimensions": case["scoring_dimensions"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_holdout_is_frozen_and_hash_bound() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["status"] == "holdout_frozen_not_run"
    assert payload["evaluation_only"] is True
    assert payload["tuning_case_ids"] == []
    cases = payload["cases"]
    assert len(cases) == 12
    assert len({case["id"] for case in cases}) == 12
    assert Counter(case["type"] for case in cases) == {
        "news": 2,
        "financial": 2,
        "transmission": 2,
        "method": 2,
        "rewrite": 2,
        "multiturn": 2,
    }
    for case in cases:
        question = case["question"].encode("utf-8")
        assert hashlib.sha256(question).hexdigest() == case["question_sha256"]
        turns = json.dumps(
            case["turns"], ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        assert hashlib.sha256(turns).hexdigest() == case["turns_sha256"]
        assert (
            hashlib.sha256(case["materials"].encode("utf-8")).hexdigest()
            == case["materials_sha256"]
        )
        assert hashlib.sha256(_gold(case)).hexdigest() == case["gold_sha256"]
        assert len(case["turns"]) == (2 if case["type"] == "multiturn" else 1)
        assert case["tuning"] is False
        assert case["semantic_status"] == "not_evaluated"
