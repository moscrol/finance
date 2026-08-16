"""Longtail answer-skeleton injection (ASK_LONGTAIL_BASELINE, default off).

P0 triggers only:

1. controller safe-fallback (``llm_failure_reason`` or reason contains 安全降级)
2. ``general_finance_qa`` with confidence < 0.6 after resolve

Owner skills in ``RESEARCH_OWNER_IDS`` yield. The skill file is prompt-only
and must not enter ``route_skills``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from intelligence.services.research_contract import RESEARCH_OWNER_IDS
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision

ENV_NAME = "ASK_LONGTAIL_BASELINE"
SKILL_ID = "finance-longtail-baseline"
QUESTION_GENERAL = "general_finance_qa"
CONFIDENCE_THRESHOLD = 0.6
ANALYTICAL_MARKERS = ("据此判断", "这说明", "这意味着")
HEADING = "【长尾回答骨架】"
_SKILL_RELATIVE = Path("skills") / SKILL_ID / "SKILL.md"
_ARABIC_DIGIT = re.compile(r"\d")
_MARKET_NAME_DENYLIST = (
    "半导体",
    "光伏",
    "宁德",
    "茅台",
    "科创",
    "创业板",
    "沪深",
)


def enabled() -> bool:
    raw = os.environ.get(ENV_NAME, "off").strip().lower()
    return raw in {"on", "true", "1", "yes"}


def skill_path() -> Path:
    return Path(__file__).resolve().parents[2] / _SKILL_RELATIVE


def skill_body(path: Path | None = None) -> str:
    text = (path or skill_path()).read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.strip()


def skill_body_is_clean(text: str) -> bool:
    if _ARABIC_DIGIT.search(text):
        return False
    return not any(name in text for name in _MARKET_NAME_DENYLIST)


def assert_skill_contract(text: str | None = None) -> None:
    body = skill_body() if text is None else text
    missing = [marker for marker in ANALYTICAL_MARKERS if marker not in body]
    if missing:
        raise AssertionError(f"skeleton missing analytical markers: {missing}")
    if not skill_body_is_clean(body):
        raise AssertionError("skeleton smuggles digits or market names")


def prompt_block(path: Path | None = None) -> str:
    body = skill_body(path)
    return f"{HEADING}\n{body}"


def _has_specific_owner(owner: str | None) -> bool:
    return owner in RESEARCH_OWNER_IDS


def should_inject_frame(frame: TaskFrame) -> bool:
    if not enabled():
        return False
    if frame.question_type != QUESTION_GENERAL:
        return False
    return frame.confidence < CONFIDENCE_THRESHOLD


def should_inject_decision(decision: TurnDecision) -> bool:
    if not enabled():
        return False
    intent = decision.turn_intent
    owner = None if intent is None else intent.answer_owner
    if _has_specific_owner(owner):
        return False
    if decision.llm_failure_reason or "安全降级" in (decision.reason or ""):
        return True
    if decision.question_type == QUESTION_GENERAL and decision.confidence < CONFIDENCE_THRESHOLD:
        return True
    return False


def episode_rule(frame: TaskFrame) -> str:
    if not should_inject_frame(frame):
        return ""
    return f"{prompt_block()}\n"


def lane_suffix(decision: TurnDecision) -> str:
    if not should_inject_decision(decision):
        return ""
    return prompt_block()
