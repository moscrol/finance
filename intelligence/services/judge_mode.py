"""Semantic judge mode shared by both answer engines (workorder #55).

``ASK_SEMANTIC_JUDGE`` decides whether a draft is judged by a second LLM call
(``llm``, historical default) or only by the deterministic gates (``off``).
Keep the wire values stable: receipts carry ``judge_mode`` verbatim.

No imports from services/runtime on purpose — the verifier (engine A) and
``ask_synthesis`` (engine B) both read this one function instead of each
parsing the environment themselves.
"""

from __future__ import annotations

import os

ENV_SEMANTIC_JUDGE = "ASK_SEMANTIC_JUDGE"
JUDGE_MODE_LLM = "llm"
JUDGE_MODE_DETERMINISTIC = "deterministic"
JUDGE_MODE_OFF = "off"

_OFF_VALUES = frozenset({"0", "false", "off", "no", JUDGE_MODE_DETERMINISTIC})


def semantic_judge_mode() -> str:
    """Return ``llm`` or ``off``; anything not spelled as off keeps the judge."""

    raw = str(os.environ.get(ENV_SEMANTIC_JUDGE, JUDGE_MODE_LLM)).strip().lower()
    return JUDGE_MODE_OFF if raw in _OFF_VALUES else JUDGE_MODE_LLM


def judge_mode_label(mode: str) -> str:
    """Receipt wording: ``off`` is recorded as ``deterministic`` (who judged)."""

    return JUDGE_MODE_DETERMINISTIC if mode == JUDGE_MODE_OFF else JUDGE_MODE_LLM
