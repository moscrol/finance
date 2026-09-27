"""Offline perspective delivery probe: stop at the first provider callback.

Uses the real GLM episode and serializer, but no provider, tool implementation,
judge, durable store, or model response. This is delivery, not model consumption.
The fixed research frame bypasses routing/API; orchestrator wiring is tested with
synthetic users separately. Private messages stay in memory and are never emitted.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

from intelligence import userspace
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.turn_control_core import project_turn_decision
from intelligence.services import perspective_lab
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision


class RequestCaptured(BaseException):
    """Bypass normal retry/fallback handlers without fabricating a model result."""


class RequestCapture:
    def __init__(self, *, today: str | None = None) -> None:
        self.today = today or date.today().isoformat()
        self.messages: list[dict] | None = None
        self.calls = 0
        self.tool_count: int | None = None

    def complete(self, *, messages, tools, **_kwargs):
        self.calls += 1
        self.messages = json.loads(json.dumps(messages))
        self.tool_count = len(tools)
        raise RequestCaptured()

    def adapter(self) -> ContinuousTurnAdapter:
        return ContinuousTurnAdapter(
            runtime=GLMAgentRuntime(complete_fn=self.complete),
            mode="on",
            tier="quick",
            today=self.today,
            latest_data_date=None,
            registry_factory=lambda *_args: ResearchToolRegistry(()),
            semantic_verifier=self,
        )

    def verify(self, **_kwargs):
        raise AssertionError("Offline request capture must not reach the judge")

    def payload(self) -> dict:
        if self.calls != 1 or self.messages is None:
            raise ValueError("First provider callback was not captured exactly once")
        candidates = []
        for message in self.messages:
            if message.get("role") != "user":
                continue
            try:
                candidate = json.loads(message.get("content", ""))
            except (TypeError, ValueError):
                continue
            if isinstance(candidate, dict) and "research_contract" in candidate and "task_frame" in candidate:
                candidates.append(candidate)
        if len(candidates) != 1:
            raise ValueError("Expected exactly one serialized research task")
        if self.tool_count != 0:
            raise ValueError("Offline capture unexpectedly exposed tools")
        return candidates[0]


def verify_delivery(us: userspace.UserSpace, pid: str, query: str, expected_prompt: str) -> dict:
    """Compare independent assembly with the first outgoing request, plus neutral."""
    probe_date = date.today().isoformat()
    frame = TaskFrame(
        raw_question=query,
        user_goal="Audit perspective delivery only",
        question_type="market_forecast",
        subject="A-share market",
        subject_kind="market_pattern",
        market_scope="A-share",
        timeframe=probe_date,
        required_outputs=("direct_assessment",),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="current_market_scenarios", confidence=1.0,
    )
    decision = TurnDecision(
        lane="research", needs_retrieval=True, needs_memory=False,
        needs_template=True, question_type=frame.question_type,
        capabilities=("market_data",), task_frame=frame,
    )
    issues: list[str] = []
    modes: dict[str, dict] = {}
    if not expected_prompt.strip():
        raise ValueError("Expected perspective context must not be empty")
    for mode in ("single", "neutral"):
        prompt = perspective_lab.active_runtime_prompt(us, mode=mode, perspective_ids=[pid], query=query)
        control = project_turn_decision(decision, task_frame=frame, perspective_context=prompt)
        capture = RequestCapture(today=probe_date)
        try:
            capture.adapter().handle(frame=frame, control=control)
        except RequestCaptured:
            pass
        payload = capture.payload()
        actual = payload.get("perspective_context", "")
        if mode == "single":
            if actual != expected_prompt:
                issues.append("Selected perspective changed or disappeared before provider callback")
            if not payload.get("perspective_context_rule"):
                issues.append("Perspective evidence boundary missing from provider request")
        elif "perspective_context" in payload or "perspective_context_rule" in payload:
            issues.append("Neutral request contains perspective fields")
        modes[mode] = {
            "callback_count": capture.calls,
            "tool_count": capture.tool_count,
            "context_chars": len(actual),
            "context_sha256": hashlib.sha256(actual.encode()).hexdigest(),
            "request_sha256": hashlib.sha256(json.dumps(capture.messages, ensure_ascii=False).encode()).hexdigest(),
            "perspective_rule_present": bool(payload.get("perspective_context_rule")),
        }
    return {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
        "scope": "fixed_frame_to_first_glm_provider_callback; no_api_router_tools_model_or_answer",
        "probe_date": probe_date,
        "market_facts_supplied": False,
        "modes": modes,
    }
