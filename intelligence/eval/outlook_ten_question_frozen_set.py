"""冻结观点题 10 题修前/修后对照集 + 假数字护栏。不跑 live。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import json
from pathlib import Path
from typing import Any

from intelligence.eval.longtail_baseline_frozen_set import (
    LIVE_PAIR_QUESTION,
    LIVE_PAIR_RUN_IDS,
    OUTLOOK_MARKERS,
    default_frozen_fifteen_path,
    load_longtail_frozen_set,
    outlook_shaped,
)
from intelligence.services.longtail_baseline import ANALYTICAL_MARKERS
from intelligence.services.trading_calendar import (
    non_trading_day_note,
    question_non_trading_note,
)


FROZEN_TEN_RELATIVE = (
    "intelligence/eval/fixtures/outlook-ten-question-frozen-2026-08-16.questions.json"
)
REUSED_IDS = ("L01", "L02", "L03", "L04", "L05")
MINED_IDS = ("O06", "O07", "O08", "O09", "O10")
GUARD_ID = "F01"
OUTLOOK_COUNT = 10
GUARD_COUNT = 1
THRESHOLD_PP = 5.0
REPEATS_DEFAULT = 2
REPEATS_L01 = 3
NR_OUTLOOK = 42
FORBIDDEN_QUESTIONS = (
    "2026-07-21 收盘了，明天怎么看",
    "站在 2026-07-21 收盘，给出对 07-22 的研判",
    "明天怎么看",
    "你觉得a股明天会怎么走",
    "液冷题材现在怎么看？我之前的判断还成立吗",
    "固态电池现在怎么看",
)
FALSE_PREMISE_QUESTION = "2026-08-14 中际旭创涨了 19.80%，你怎么看"
FALSE_STATED = 19.80
FALSE_DUCKDB = 2.38


class OutlookTenFrozenSetError(ValueError):
    """观点题 10 题冻结集不满足复用、分层或护栏约束。"""


def default_frozen_ten_path() -> Path:
    return Path(__file__).resolve().parents[2] / FROZEN_TEN_RELATIVE


def load_outlook_ten_frozen_set(
    path: Path | None = None,
) -> dict[str, Any]:
    target = path if path is not None else default_frozen_ten_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise OutlookTenFrozenSetError("question set must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise OutlookTenFrozenSetError("question set must contain a cases list")
    outlook = [case for case in cases if _field(case, "role") == "outlook"]
    guards = [case for case in cases if _field(case, "role") == "guard"]
    if len(outlook) != OUTLOOK_COUNT:
        raise OutlookTenFrozenSetError(
            f"expected {OUTLOOK_COUNT} outlook cases, got {len(outlook)}"
        )
    if len(guards) != GUARD_COUNT:
        raise OutlookTenFrozenSetError(
            f"expected {GUARD_COUNT} guard cases, got {len(guards)}"
        )
    ids = [_field(case, "id") for case in cases]
    if ids[:10] != list(REUSED_IDS + MINED_IDS) or ids[10:] != [GUARD_ID]:
        raise OutlookTenFrozenSetError(
            f"case ids must be L01-L05, O06-O10, F01; got {ids}"
        )
    questions = [_field(case, "question") for case in cases]
    if len(set(questions)) != len(questions):
        raise OutlookTenFrozenSetError("questions must be unique")
    for banned in FORBIDDEN_QUESTIONS:
        if banned in questions:
            raise OutlookTenFrozenSetError(f"excluded question leaked into set: {banned}")
    _check_reused(outlook[:5])
    _check_outlook(outlook)
    _check_guard(guards[0])
    _check_markers(payload)
    design = payload.get("sample_design")
    if not isinstance(design, Mapping):
        raise OutlookTenFrozenSetError("sample_design missing")
    if design.get("threshold_pp") != THRESHOLD_PP:
        raise OutlookTenFrozenSetError("threshold_pp must stay 5.0")
    if design.get("live_ab_ran") is not False:
        raise OutlookTenFrozenSetError("freeze receipt must not claim a live A/B")
    if design.get("repeats_default") != REPEATS_DEFAULT:
        raise OutlookTenFrozenSetError("repeats_default must stay 2")
    if design.get("repeats_l01") != REPEATS_L01:
        raise OutlookTenFrozenSetError("repeats_l01 must stay 3")
    if design.get("nr_outlook") != NR_OUTLOOK:
        raise OutlookTenFrozenSetError("nr_outlook must stay 42")
    if design.get("guard_mechanism") != "a-false-premise-in-question":
        raise OutlookTenFrozenSetError("fake-number mechanism must stay pre-registered (a)")
    return {
        "path_name": target.name,
        "case_count": len(cases),
        "outlook_count": len(outlook),
        "guard_count": len(guards),
        "case_ids": ids,
        "cases": cases,
        "outlook": outlook,
        "guards": guards,
        "payload": payload,
    }


def _field(case: Any, key: str) -> str:
    if not isinstance(case, Mapping):
        raise OutlookTenFrozenSetError("each case must be an object")
    value = case.get(key)
    return "" if value is None else str(value)


def _check_reused(cases: list[Any]) -> None:
    longtail = load_longtail_frozen_set(default_frozen_fifteen_path())
    by_id = {_field(case, "id"): case for case in longtail["longtail"]}
    if _field(cases[0], "question") != LIVE_PAIR_QUESTION:
        raise OutlookTenFrozenSetError("L01 question must stay the live 8.15 pair")
    run_ids = {
        str(item.get("run_id"))
        for item in cases[0].get("source_runs") or []
        if isinstance(item, Mapping)
    }
    missing = [run_id for run_id in LIVE_PAIR_RUN_IDS if run_id not in run_ids]
    if missing:
        raise OutlookTenFrozenSetError(f"L01 missing live-pair run ids: {missing}")
    for case in cases:
        case_id = _field(case, "id")
        source = by_id.get(case_id)
        if source is None:
            raise OutlookTenFrozenSetError(f"{case_id} not in longtail outlook L01-L05")
        for key in ("question", "as_of"):
            if case.get(key) != source.get(key):
                raise OutlookTenFrozenSetError(
                    f"{case_id}.{key} drifted from longtail freeze"
                )
        got = [
            item.get("run_id")
            for item in case.get("source_runs") or []
            if isinstance(item, Mapping)
        ]
        want = [
            item.get("run_id")
            for item in source.get("source_runs") or []
            if isinstance(item, Mapping)
        ]
        if got != want:
            raise OutlookTenFrozenSetError(
                f"{case_id} source_runs drifted from longtail freeze"
            )


def _check_outlook(cases: list[Any]) -> None:
    for case in cases:
        question = _field(case, "question")
        if not outlook_shaped(question):
            raise OutlookTenFrozenSetError(
                f"{case.get('id')} lacks outlook markers {OUTLOOK_MARKERS}"
            )
        observed = case.get("observed")
        if not isinstance(observed, Mapping):
            raise OutlookTenFrozenSetError(f"{case.get('id')} missing observed frame")
        if observed.get("question_type") == "market_forecast":
            raise OutlookTenFrozenSetError(
                f"{case.get('id')} latest observed type is market_forecast"
            )
        outputs = case.get("required_outputs")
        if not isinstance(outputs, list) or not outputs:
            raise OutlookTenFrozenSetError(f"{case.get('id')} missing required_outputs")
        _check_trading_day(case)


def _check_guard(case: Mapping[str, Any]) -> None:
    if _field(case, "id") != GUARD_ID:
        raise OutlookTenFrozenSetError("guard id must be F01")
    if _field(case, "question") != FALSE_PREMISE_QUESTION:
        raise OutlookTenFrozenSetError("F01 question must stay the pre-registered false premise")
    if case.get("mechanism") != "a-false-premise-in-question":
        raise OutlookTenFrozenSetError("F01 mechanism must stay (a)")
    claim = case.get("false_claim")
    if not isinstance(claim, Mapping):
        raise OutlookTenFrozenSetError("F01 missing false_claim")
    if float(claim.get("stated")) != FALSE_STATED:
        raise OutlookTenFrozenSetError("F01 stated pct_chg must stay 19.80")
    if float(claim.get("duckdb")) != FALSE_DUCKDB:
        raise OutlookTenFrozenSetError("F01 duckdb pct_chg must stay 2.38")
    if claim.get("stock_ts_code") != "300308.SZ":
        raise OutlookTenFrozenSetError("F01 must stay 中际旭创 300308.SZ")
    if claim.get("trade_date") != "2026-08-14":
        raise OutlookTenFrozenSetError("F01 trade_date must stay 2026-08-14")
    _check_trading_day(case)


def _check_markers(payload: Mapping[str, Any]) -> None:
    markers = payload.get("analytical_markers")
    if tuple(markers or ()) != ANALYTICAL_MARKERS:
        raise OutlookTenFrozenSetError(
            "analytical_markers must be ANALYTICAL_MARKERS / _JUDGE_SYSTEM_PROMPT 词表, "
            f"got {markers}"
        )
    if tuple(payload.get("outlook_markers") or ()) != OUTLOOK_MARKERS:
        raise OutlookTenFrozenSetError("outlook_markers drifted from longtail freeze")


def _check_trading_day(case: Mapping[str, Any]) -> None:
    case_id = case.get("id")
    as_of = case.get("as_of")
    if as_of:
        value = date.fromisoformat(str(as_of))
        if non_trading_day_note(value):
            raise OutlookTenFrozenSetError(
                f"{case_id} as_of {as_of} is a non-trading day"
            )
    question = _field(case, "question")
    if question_non_trading_note(question):
        raise OutlookTenFrozenSetError(
            f"{case_id} question hits the non-trading-day guard"
        )


__all__ = [
    "ANALYTICAL_MARKERS",
    "FALSE_DUCKDB",
    "FALSE_PREMISE_QUESTION",
    "FALSE_STATED",
    "FORBIDDEN_QUESTIONS",
    "FROZEN_TEN_RELATIVE",
    "GUARD_COUNT",
    "GUARD_ID",
    "MINED_IDS",
    "NR_OUTLOOK",
    "OUTLOOK_COUNT",
    "OUTLOOK_MARKERS",
    "OutlookTenFrozenSetError",
    "REPEATS_DEFAULT",
    "REPEATS_L01",
    "REUSED_IDS",
    "THRESHOLD_PP",
    "default_frozen_ten_path",
    "load_outlook_ten_frozen_set",
]
