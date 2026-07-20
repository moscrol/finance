from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

from intelligence.services import llm_refine
from intelligence.services.lane_generation import generate_lane_answer
from intelligence.services.turn_controller import TurnDecision


def _methodology_decision() -> TurnDecision:
    return TurnDecision(
        lane="knowledge",
        needs_retrieval=False,
        needs_memory=False,
        needs_template=False,
        question_type="methodology_discussion",
        confidence=1.0,
        reason="fixture",
    )


def test_methodology_prompt_preserves_model_reasoning_without_financial_rag() -> None:
    observed: list[dict[str, str]] = []

    def complete(messages: list[dict[str, str]]):
        observed.extend(messages)
        return (
            "模板化来自表达约束占用了模型注意力，而不是工具本身。",
            SimpleNamespace(name="fixture", model="fixture-model"),
            "",
        )

    answer = generate_lane_answer(
        "编排层为什么会导致模板化？",
        _methodology_decision(),
        llm_complete=complete,
    )

    assert answer.provider == "fixture"
    assert "通用原理做因果分析" in observed[0]["content"]
    assert "不要套金融研究模板" in observed[0]["content"]
    payload = json.loads(observed[1]["content"])
    assert payload["retrieved_material"] is None


def test_lane_generation_uses_runtime_llm_timeout_by_default() -> None:
    default = inspect.signature(generate_lane_answer).parameters["timeout"].default

    assert default == llm_refine.DEFAULT_LLM_TIMEOUT


def test_methodology_timeout_retries_once_within_same_wall_budget(
    monkeypatch,
) -> None:
    calls: list[int] = []

    def complete(messages, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            return None, None, "LLM 调用失败（TimeoutError）"
        return (
            "约束应放在出口 verifier，而不是把展示 prompt 写成模板。",
            SimpleNamespace(name="fixture", model="fixture-model"),
            "",
        )

    monkeypatch.setattr(llm_refine, "complete", complete)

    answer = generate_lane_answer(
        "编排层为什么会导致模板化？",
        _methodology_decision(),
        timeout=180,
    )

    assert calls == [90, 90]
    assert answer.provider == "fixture"
    assert "出口 verifier" in answer.answer
