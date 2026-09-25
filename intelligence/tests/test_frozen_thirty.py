"""第 8 步：30 题分层冻结集 + 样本量锁。不跑 live，不连 dsh。"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from intelligence.eval.ab_sample_design import (
    DROPPED_DRAFT_VARIANCE,
    MEASURED_POOLED_VARIANCE,
    recommend_design,
)
from intelligence.eval.arm_a_calibration import (
    FROZEN_NINE_CASE_IDS,
    THRESHOLD_PP,
    THRESHOLD_RATE,
    projected_ci_half_width,
    required_nr,
)
from intelligence.eval.frozen_question_set import (
    load_frozen_question_set,
)
from scripts import run_agent_runtime_benchmark as benchmark

NINE_FIXTURE = Path(__file__).parent / "fixtures" / "runtime_backend_cases.json"


def test_official_variance_is_receipt_not_draft_ghost() -> None:
    assert MEASURED_POOLED_VARIANCE == 0.1375
    assert DROPPED_DRAFT_VARIANCE == 0.125
    assert MEASURED_POOLED_VARIANCE != DROPPED_DRAFT_VARIANCE
    assert required_nr(MEASURED_POOLED_VARIANCE) == pytest.approx(422.6, abs=0.1)


def test_locked_design_resolves_5pp_at_30x15() -> None:
    design = recommend_design(MEASURED_POOLED_VARIANCE)
    assert design["question_count"] == 30
    assert design["repeats"] == 15
    assert design["nr"] == 450
    assert design["nr"] >= design["required_nr"]
    assert design["can_resolve_5pp"] is True
    assert design["threshold_pp"] == THRESHOLD_PP == 5.0
    assert design["retain_dsh_runtime"] is False
    assert design["live_ab_ran"] is False
    assert design["next_action"] == "run_locked_window"
    assert design["ci95_half_width"] < THRESHOLD_RATE


def test_draft_30x13_cannot_resolve_true_variance() -> None:
    half = projected_ci_half_width(
        MEASURED_POOLED_VARIANCE, question_count=30, repeats=13
    )
    assert 30 * 13 < required_nr(MEASURED_POOLED_VARIANCE)
    assert half > THRESHOLD_RATE


def test_threshold_is_not_a_design_knob() -> None:
    assert "threshold" not in inspect.signature(recommend_design).parameters
    assert recommend_design()["threshold_pp"] == 5.0


def test_thirty_set_keeps_frozen_nine_verbatim() -> None:
    loaded = load_frozen_question_set()
    assert loaded["case_count"] == 30
    assert loaded["layers"] == {
        "quick-research": 10,
        "daily-review": 10,
        "deep-research": 10,
    }
    assert loaded["case_ids"][:9] == list(FROZEN_NINE_CASE_IDS)
    canonical = {
        case["id"]: case
        for case in json.loads(NINE_FIXTURE.read_text(encoding="utf-8"))["cases"]
    }
    for case in loaded["cases"][:9]:
        original = canonical[case["id"]]
        assert case["question"] == original["question"]
        assert case["as_of"] == original["as_of"]
        assert case["required_outputs"] == original["required_outputs"]
        assert case.get("conversation_context", []) == original.get(
            "conversation_context", []
        )
        assert case["profile"] == "daily-review"
        assert case["tier"] == "standard"


def test_fixture_sample_design_matches_lock() -> None:
    from intelligence.eval.frozen_question_set import default_frozen_thirty_path

    payload = json.loads(default_frozen_thirty_path().read_text(encoding="utf-8"))
    design = payload["sample_design"]
    assert design["measured_variance"] == 0.1375
    assert design["repeats"] == 15
    assert design["nr"] == 450
    assert design["threshold_pp"] == 5.0
    assert design["measured_variance"] != 0.125


def test_thirty_set_dry_run_has_no_contract_gaps(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        benchmark,
        "_run_runtime_arm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not execute a runtime")
        ),
    )
    output = tmp_path / "thirty-dry.json"
    from intelligence.eval.frozen_question_set import default_frozen_thirty_path

    code = benchmark.main(
        [
            "--dry-run",
            "--backend",
            "continuous_glm",
            "--questions-file",
            str(default_frozen_thirty_path()),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["case_count"] == 30
    assert payload["mode"] == "dry_run"
    assert all(not case["acceptance_contract_gaps"] for case in payload["cases"])
    assert "/Users/" not in json.dumps(
        {key: payload[key] for key in payload if key != "cases"}
    )
