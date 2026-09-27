"""Semantic judge mode shared by both answer engines (workorder #55).

``ASK_SEMANTIC_JUDGE`` decides whether a draft is judged by a second LLM call
(``llm``) or only by the deterministic gates (``off``). Keep the wire values
stable: receipts carry ``judge_mode`` verbatim.

默认关（2026-09-27 用户决定「判官现在先默认off」）：GLM 判官在 max 档大材料
载荷上一发要 ~93 s（47 条材料结论，glm-5.3；flash 两发 75 s 都答不完），
判官不可用时答案被压 partial 或扣下，弊大于利。只有明确的开启写法才开，
空串、拼错与未设都落回默认的关——配置写错要落在安全的一边，而不是悄悄开着
一个慢判官。开启时配 ``LLM_JUDGE_MODEL=glm-5.3``（独立判官，同端点）。

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

_ON_VALUES = frozenset({JUDGE_MODE_LLM, "on", "1", "true", "yes", "enabled", "enable"})


def semantic_judge_mode() -> str:
    """Return ``llm`` only for an explicit enable spelling; unset / anything else is ``off``."""

    raw = str(os.environ.get(ENV_SEMANTIC_JUDGE, JUDGE_MODE_OFF)).strip().lower()
    return JUDGE_MODE_LLM if raw in _ON_VALUES else JUDGE_MODE_OFF


def judge_mode_label(mode: str) -> str:
    """Receipt wording: ``off`` is recorded as ``deterministic`` (who judged)."""

    return JUDGE_MODE_DETERMINISTIC if mode == JUDGE_MODE_OFF else JUDGE_MODE_LLM
