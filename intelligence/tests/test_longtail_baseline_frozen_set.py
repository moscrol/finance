"""冻结 15 题对照集：锁题面、分层、触发与护栏。不跑 live。"""

from __future__ import annotations

import hashlib

from intelligence.eval.longtail_baseline_frozen_set import (
    FORBIDDEN_QUESTIONS,
    LIVE_PAIR_QUESTION,
    LIVE_PAIR_RUN_IDS,
    THRESHOLD_PP,
    default_frozen_fifteen_path,
    load_longtail_frozen_set,
)
from intelligence.services.longtail_baseline import (
    ENV_NAME,
    should_inject_decision,
    should_inject_frame,
)
from intelligence.services.research_contract import RESEARCH_OWNER_IDS, TurnIntent
from intelligence.services.task_frame import TaskFrame
from intelligence.services.trading_calendar import (
    non_trading_day_note,
    question_non_trading_note,
)
from intelligence.services.turn_controller import TurnDecision

FROZEN_FIFTEEN_SHA256 = (
    "9b43354b2d9af669634d87df6f1e8ae219ebb751156694d0e01dc65a948b3fd8"
)


def _frame_from_case(case: dict) -> TaskFrame:
    observed = case["observed"]
    return TaskFrame(
        raw_question=case["question"],
        user_goal="形成条件化判断",
        question_type=observed["question_type"],
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe=case.get("as_of") or "最近交易日",
        required_outputs=tuple(case["required_outputs"]),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="general_finance_evidence",
        confidence=float(observed["confidence"]),
    )


def _decision_from_case(case: dict) -> TurnDecision:
    observed = case["observed"]
    owner = observed.get("answer_owner")
    intent = None
    if owner:
        intent = TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type=observed["question_type"],
            answer_owner=owner,
            comparison_entities=(),
            inherited_from_turn=None,
        )
    return TurnDecision(
        lane="research",
        needs_retrieval=True,
        needs_memory=False,
        needs_template=False,
        question_type=observed["question_type"],
        confidence=float(observed["confidence"]),
        reason="",
        llm_failure_reason="",
        turn_intent=intent,
    )


def test_frozen_set_invariants() -> None:
    loaded = load_longtail_frozen_set()
    assert loaded["longtail_count"] == 15
    assert loaded["guard_count"] == 5
    assert loaded["outlook_count"] == 5
    assert loaded["residual_count"] == 10
    assert loaded["case_ids"][:15] == [f"L{index:02d}" for index in range(1, 16)]
    assert loaded["case_ids"][15:] == [f"G{index:02d}" for index in range(1, 6)]


def test_fixture_bytes_are_frozen() -> None:
    digest = hashlib.sha256(
        default_frozen_fifteen_path().read_bytes()
    ).hexdigest()
    assert digest == FROZEN_FIFTEEN_SHA256


def test_live_pair_and_exclusions_are_pinned() -> None:
    loaded = load_longtail_frozen_set()
    first = loaded["longtail"][0]
    assert first["question"] == LIVE_PAIR_QUESTION
    assert first["as_of"] == "2026-08-14"
    assert loaded["longtail"][9]["question"] == (
        "2026-07-21 到 07-24 量能和情绪是怎么演化的"
    )
    run_ids = {item["run_id"] for item in first["source_runs"]}
    assert set(LIVE_PAIR_RUN_IDS) <= run_ids
    questions = {case["question"] for case in loaded["cases"]}
    assert questions.isdisjoint(FORBIDDEN_QUESTIONS)
    design = loaded["payload"]["sample_design"]
    assert design["threshold_pp"] == THRESHOLD_PP
    assert design["repeats"] == 3
    assert design["nr_longtail"] == 90
    assert design["live_ab_ran"] is False


def test_observed_frames_match_injection_contract(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    loaded = load_longtail_frozen_set()
    for case in loaded["longtail"]:
        assert should_inject_frame(_frame_from_case(case)) is True
        assert should_inject_decision(_decision_from_case(case)) is True
    for case in loaded["guards"]:
        assert case["observed"]["answer_owner"] in RESEARCH_OWNER_IDS
        assert should_inject_frame(_frame_from_case(case)) is False
        assert should_inject_decision(_decision_from_case(case)) is False


def test_set_avoids_non_trading_day_guard() -> None:
    from datetime import date

    loaded = load_longtail_frozen_set()
    for case in loaded["cases"]:
        assert question_non_trading_note(case["question"]) is None
        assert non_trading_day_note(date.fromisoformat(case["as_of"])) is None


def test_flag_still_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    loaded = load_longtail_frozen_set()
    assert should_inject_frame(_frame_from_case(loaded["longtail"][0])) is False
    assert should_inject_decision(_decision_from_case(loaded["guards"][0])) is False
