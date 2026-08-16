"""冻结观点题 10 题对照集：锁题面、复用、护栏。不跑 live。"""

from __future__ import annotations

import hashlib

from intelligence.eval.longtail_baseline_frozen_set import (
    LIVE_PAIR_QUESTION,
    LIVE_PAIR_RUN_IDS,
)
from intelligence.eval.outlook_ten_question_frozen_set import (
    ANALYTICAL_MARKERS,
    FALSE_DUCKDB,
    FALSE_PREMISE_QUESTION,
    FALSE_STATED,
    FORBIDDEN_QUESTIONS,
    THRESHOLD_PP,
    default_frozen_ten_path,
    load_outlook_ten_frozen_set,
)
from intelligence.services.episode_semantic_verifier import _JUDGE_SYSTEM_PROMPT
from intelligence.services.trading_calendar import (
    non_trading_day_note,
    question_non_trading_note,
)

FROZEN_TEN_SHA256 = (
    "ac464158a724c6312b373b59a4bae2ebc1f81925b5c6e284e85c22547bc7d608"
)


def test_frozen_set_invariants() -> None:
    loaded = load_outlook_ten_frozen_set()
    assert loaded["outlook_count"] == 10
    assert loaded["guard_count"] == 1
    assert loaded["case_ids"] == [
        "L01",
        "L02",
        "L03",
        "L04",
        "L05",
        "O06",
        "O07",
        "O08",
        "O09",
        "O10",
        "F01",
    ]


def test_fixture_bytes_are_frozen() -> None:
    digest = hashlib.sha256(default_frozen_ten_path().read_bytes()).hexdigest()
    assert digest == FROZEN_TEN_SHA256


def test_reused_l01_l05_and_exclusions_are_pinned() -> None:
    loaded = load_outlook_ten_frozen_set()
    first = loaded["outlook"][0]
    assert first["question"] == LIVE_PAIR_QUESTION
    assert first["as_of"] == "2026-08-14"
    run_ids = {item["run_id"] for item in first["source_runs"]}
    assert set(LIVE_PAIR_RUN_IDS) <= run_ids
    questions = {case["question"] for case in loaded["cases"]}
    assert questions.isdisjoint(FORBIDDEN_QUESTIONS)
    design = loaded["payload"]["sample_design"]
    assert design["threshold_pp"] == THRESHOLD_PP
    assert design["repeats_default"] == 2
    assert design["repeats_l01"] == 3
    assert design["nr_outlook"] == 42
    assert design["live_ab_ran"] is False


def test_analytical_markers_are_judge_prompt_verbatim() -> None:
    loaded = load_outlook_ten_frozen_set()
    assert tuple(loaded["payload"]["analytical_markers"]) == ANALYTICAL_MARKERS
    for marker in ANALYTICAL_MARKERS:
        assert f"“{marker}”" in _JUDGE_SYSTEM_PROMPT or f"「{marker}」" in _JUDGE_SYSTEM_PROMPT
    assert "“据此判断”“这说明”“这意味着”" in _JUDGE_SYSTEM_PROMPT


def test_set_avoids_non_trading_day_guard() -> None:
    from datetime import date

    loaded = load_outlook_ten_frozen_set()
    for case in loaded["cases"]:
        assert question_non_trading_note(case["question"]) is None
        assert non_trading_day_note(date.fromisoformat(case["as_of"])) is None


def test_false_number_guard_is_preregistered_mechanism_a() -> None:
    loaded = load_outlook_ten_frozen_set()
    guard = loaded["guards"][0]
    assert guard["question"] == FALSE_PREMISE_QUESTION
    assert guard["mechanism"] == "a-false-premise-in-question"
    assert guard["false_claim"]["stated"] == FALSE_STATED
    assert guard["false_claim"]["duckdb"] == FALSE_DUCKDB
    assert loaded["payload"]["sample_design"]["live_ab_ran"] is False
