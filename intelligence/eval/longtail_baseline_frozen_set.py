"""冻结长尾骨架 15 题 + 5 题 owner 护栏。不跑 live。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import json
from pathlib import Path
from typing import Any

from intelligence.services.trading_calendar import (
    non_trading_day_note,
    question_non_trading_note,
)


FROZEN_FIFTEEN_RELATIVE = (
    "intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json"
)
LIVE_PAIR_RUN_IDS = (
    "run_20260816_102941_554059",
    "run_20260816_103318_230845",
)
LIVE_PAIR_QUESTION = "基于8.15的行情现状，你认为周一的机会在哪"
OUTLOOK_MARKERS = ("你认为", "你觉得", "怎么看", "机会在哪", "会怎么走")
FORBIDDEN_QUESTIONS = (
    "2026-07-21 收盘了，明天怎么看",
    "站在 2026-07-21 收盘，给出对 07-22 的研判",
    "明天怎么看",
    "查一下 sector_marginal 表里 07-23 的边际量",
    "只回复两个字：收到",
    "2026-07-25 市场怎么样",
)
LONGTAIL_COUNT = 15
GUARD_COUNT = 5
THRESHOLD_PP = 5.0


class LongtailFrozenSetError(ValueError):
    """长尾冻结集不满足分层、触发或护栏约束。"""


def default_frozen_fifteen_path() -> Path:
    return Path(__file__).resolve().parents[2] / FROZEN_FIFTEEN_RELATIVE


def outlook_shaped(question: str) -> bool:
    return any(marker in question for marker in OUTLOOK_MARKERS)


def load_longtail_frozen_set(
    path: Path | None = None,
) -> dict[str, Any]:
    target = path if path is not None else default_frozen_fifteen_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise LongtailFrozenSetError("question set must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise LongtailFrozenSetError("question set must contain a cases list")
    longtail = [case for case in cases if _field(case, "role") == "longtail"]
    guards = [case for case in cases if _field(case, "role") == "guard"]
    if len(longtail) != LONGTAIL_COUNT:
        raise LongtailFrozenSetError(
            f"expected {LONGTAIL_COUNT} longtail cases, got {len(longtail)}"
        )
    if len(guards) != GUARD_COUNT:
        raise LongtailFrozenSetError(
            f"expected {GUARD_COUNT} guard cases, got {len(guards)}"
        )
    ids = [_field(case, "id") for case in cases]
    if len(set(ids)) != len(ids) or any(not item for item in ids):
        raise LongtailFrozenSetError("case ids must be unique non-empty strings")
    questions = [_field(case, "question") for case in cases]
    if len(set(questions)) != len(questions):
        raise LongtailFrozenSetError("questions must be unique")
    for banned in FORBIDDEN_QUESTIONS:
        if banned in questions:
            raise LongtailFrozenSetError(f"excluded question leaked into set: {banned}")
    _check_longtail(longtail)
    _check_guards(guards)
    design = payload.get("sample_design")
    if not isinstance(design, Mapping):
        raise LongtailFrozenSetError("sample_design missing")
    if design.get("threshold_pp") != THRESHOLD_PP:
        raise LongtailFrozenSetError("threshold_pp must stay 5.0")
    if design.get("live_ab_ran") is not False:
        raise LongtailFrozenSetError("freeze receipt must not claim a live A/B")
    return {
        "path_name": target.name,
        "case_count": len(cases),
        "longtail_count": len(longtail),
        "guard_count": len(guards),
        "case_ids": ids,
        "outlook_count": sum(
            1 for case in longtail if _field(case, "stratum") == "outlook"
        ),
        "residual_count": sum(
            1 for case in longtail if _field(case, "stratum") == "residual"
        ),
        "cases": cases,
        "longtail": longtail,
        "guards": guards,
        "payload": payload,
    }


def _field(case: Any, key: str) -> str:
    if not isinstance(case, Mapping):
        raise LongtailFrozenSetError("each case must be an object")
    value = case.get(key)
    return "" if value is None else str(value)


def _check_longtail(cases: list[Any]) -> None:
    if _field(cases[0], "id") != "L01":
        raise LongtailFrozenSetError("first longtail case must be L01")
    if _field(cases[0], "question") != LIVE_PAIR_QUESTION:
        raise LongtailFrozenSetError("L01 question must stay the live 8.15 pair")
    run_ids = {
        str(item.get("run_id"))
        for item in cases[0].get("source_runs") or []
        if isinstance(item, Mapping)
    }
    missing = [run_id for run_id in LIVE_PAIR_RUN_IDS if run_id not in run_ids]
    if missing:
        raise LongtailFrozenSetError(f"L01 missing live-pair run ids: {missing}")
    outlook = 0
    residual = 0
    t1 = 0
    for case in cases:
        stratum = _field(case, "stratum")
        question = _field(case, "question")
        if stratum == "outlook":
            outlook += 1
            if not outlook_shaped(question):
                raise LongtailFrozenSetError(
                    f"{case.get('id')} marked outlook but lacks outlook markers"
                )
        elif stratum == "residual":
            residual += 1
            if outlook_shaped(question):
                raise LongtailFrozenSetError(
                    f"{case.get('id')} marked residual but has outlook markers"
                )
        else:
            raise LongtailFrozenSetError(f"{case.get('id')} unknown longtail stratum")
        observed = case.get("observed")
        if not isinstance(observed, Mapping):
            raise LongtailFrozenSetError(f"{case.get('id')} missing observed frame")
        if observed.get("question_type") != "general_finance_qa":
            raise LongtailFrozenSetError(
                f"{case.get('id')} observed type must be general_finance_qa"
            )
        confidence = observed.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence >= 0.6:
            raise LongtailFrozenSetError(
                f"{case.get('id')} observed confidence must be < 0.6"
            )
        triggers = case.get("triggers")
        if not isinstance(triggers, list) or not triggers:
            raise LongtailFrozenSetError(f"{case.get('id')} must declare t1/t2")
        if any(item not in {"t1", "t2"} for item in triggers):
            raise LongtailFrozenSetError(f"{case.get('id')} unknown trigger")
        if "t1" in triggers:
            t1 += 1
        outputs = case.get("required_outputs")
        if not isinstance(outputs, list) or not outputs:
            raise LongtailFrozenSetError(f"{case.get('id')} missing required_outputs")
        _check_trading_day(case)
    if outlook < 1 or residual < 1:
        raise LongtailFrozenSetError("both outlook and residual strata are required")
    if t1 < 1:
        raise LongtailFrozenSetError("at least one t1 (safe-fallback) case is required")


def _check_guards(cases: list[Any]) -> None:
    for case in cases:
        observed = case.get("observed")
        if not isinstance(observed, Mapping):
            raise LongtailFrozenSetError(f"{case.get('id')} missing observed frame")
        owner = observed.get("answer_owner")
        confidence = observed.get("confidence")
        if owner not in {
            "stock-deep-dive",
            "financial-analysis",
            "news-impact",
            "theme-research",
        }:
            raise LongtailFrozenSetError(
                f"{case.get('id')} guard owner must be in RESEARCH_OWNER_IDS"
            )
        if not isinstance(confidence, (int, float)) or confidence < 0.6:
            raise LongtailFrozenSetError(
                f"{case.get('id')} guard confidence must be >= 0.6"
            )
        if case.get("triggers"):
            raise LongtailFrozenSetError(f"{case.get('id')} guard must not declare triggers")
        _check_trading_day(case)


def _check_trading_day(case: Mapping[str, Any]) -> None:
    case_id = case.get("id")
    as_of = case.get("as_of")
    if as_of:
        value = date.fromisoformat(str(as_of))
        if non_trading_day_note(value):
            raise LongtailFrozenSetError(
                f"{case_id} as_of {as_of} is a non-trading day"
            )
    question = _field(case, "question")
    if question_non_trading_note(question):
        raise LongtailFrozenSetError(
            f"{case_id} question hits the non-trading-day guard"
        )


__all__ = [
    "FORBIDDEN_QUESTIONS",
    "FROZEN_FIFTEEN_RELATIVE",
    "GUARD_COUNT",
    "LIVE_PAIR_QUESTION",
    "LIVE_PAIR_RUN_IDS",
    "LONGTAIL_COUNT",
    "LongtailFrozenSetError",
    "OUTLOOK_MARKERS",
    "THRESHOLD_PP",
    "default_frozen_fifteen_path",
    "load_longtail_frozen_set",
    "outlook_shaped",
]
