"""Compose one canonical turn into the continuous Episode runtime.

The adapter is a strangler seam, not a router: callers pass an already-frozen
``TaskFrame`` and ``TurnControlResult``.  It may decline, preserve a
deterministic fast path, or run exactly one research Episode and its two
verification gates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
import os
import re
from typing import Literal, cast

from intelligence.services.agent_runtime import AgentOutcome, AgentRuntime
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeOutcome,
    SemanticEpisodeVerifier,
)
from intelligence.services.episode_tools import (
    build_episode_registry,
    is_deterministic_fast_path,
    run_deterministic_fast_path,
)
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import redact
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_control_core import TurnControlResult


RuntimeMode = Literal["off", "canary", "on"]
ContinuousTurnStatus = Literal["completed", "degraded", "failed"]


@dataclass(frozen=True)
class ContinuousTurnResult:
    handled: bool
    status: ContinuousTurnStatus
    answer: str
    as_of: str | None
    citations: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    private_artifact: dict[str, object] | None
    events: tuple[dict[str, object], ...]


class ContinuousTurnAdapter:
    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        mode: RuntimeMode | None = None,
        context_factory: Callable[..., object] = build_episode_context,
        registry_factory: Callable[..., object] = build_episode_registry,
        fast_path_runner: Callable[..., object] = run_deterministic_fast_path,
        structural_verifier: Callable[..., object] = verify_episode_outcome,
        semantic_verifier: object | None = None,
        timeout: float = 90.0,
        tier: str = "standard",
        today: str | None = None,
        latest_data_date: str | None = None,
    ) -> None:
        selected_mode = (
            str(os.environ.get("ASK_CONTINUOUS_RUNTIME") or "off").strip().lower()
            if mode is None
            else mode
        )
        if selected_mode not in {"off", "canary", "on"}:
            raise ValueError(f"unsupported continuous runtime mode: {selected_mode}")
        self._runtime = runtime
        self._mode = cast(RuntimeMode, selected_mode)
        self._context_factory = context_factory
        self._registry_factory = registry_factory
        self._fast_path_runner = fast_path_runner
        self._structural_verifier = structural_verifier
        self._semantic_verifier = semantic_verifier or SemanticEpisodeVerifier()
        self._timeout = max(0.0, float(timeout))
        self._tier = str(tier or "standard").strip()
        self._today = today
        self._latest_data_date = latest_data_date

    @property
    def mode(self) -> RuntimeMode:
        return self._mode

    @property
    def canary_id(self) -> str:
        if self._mode != "canary":
            return ""
        return os.environ.get("CONTINUOUS_RUNTIME_CANARY_ID", "").strip()

    def handle(
        self,
        *,
        frame: TaskFrame,
        control: TurnControlResult,
    ) -> ContinuousTurnResult:
        if self._mode == "off" or (
            self._mode == "canary"
            and (
                os.environ.get("ASK_CONTINUOUS_RUNTIME", "").strip().lower() != "canary"
                or not os.environ.get("CONTINUOUS_RUNTIME_CANARY_ID", "").strip()
            )
        ):
            return _declined_result()
        control_frame = getattr(control, "task_frame", None)
        if (
            not isinstance(control_frame, TaskFrame)
            or frame.task_frame_hash != control_frame.task_frame_hash
        ):
            return _control_frame_mismatch_result()
        if control.terminal_kind == "clarification":
            questions = tuple(
                item.strip() for item in control.clarification_questions if item.strip()
            )
            answer = _safe_public_text(
                "\n".join(
                    questions
                    or (
                        frame.clarification_question
                        or "请补充会改变研究主体或结论的关键信息。",
                    )
                )
            )
            if not answer:
                answer = "请补充会改变研究主体或结论的关键信息。"
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer=answer,
                as_of=None,
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(
                    {
                        "type": "progress",
                        "stage": "clarification",
                        "message": "需要补充一项关键信息后继续。",
                    },
                ),
            )
        if control.terminal_kind != "research":
            return _declined_result()
        if is_deterministic_fast_path(frame):
            return self._run_fast_path(frame)
        return self._run_episode(frame, control)

    def _run_fast_path(self, frame: TaskFrame) -> ContinuousTurnResult:
        try:
            raw = self._fast_path_runner(frame, timeout=self._timeout)
            if not isinstance(raw, dict):
                raise TypeError("deterministic fast path must return an object")
            llm_calls = raw.get("llm_calls", 0)
            if (
                isinstance(llm_calls, bool)
                or not isinstance(llm_calls, int)
                or llm_calls != 0
            ):
                raise ValueError("deterministic fast path must use zero LLM calls")
        except Exception as exc:
            return ContinuousTurnResult(
                handled=True,
                status="failed",
                answer="",
                as_of=None,
                citations=(),
                warnings=("结构化行情计算未完成，本轮未生成技术位结论。",),
                private_artifact=cast(
                    dict[str, object],
                    _redact_private(
                        {
                            "schema_version": 1,
                            "execution_kind": "deterministic_fast_path",
                            "failure": {
                                "type": type(exc).__name__,
                                "message": str(exc),
                            },
                        }
                    ),
                ),
                events=_public_events(status="failed", deterministic=True),
            )

        raw_answer = str(raw.get("answer") or "")
        raw_status = str(raw.get("status") or "partial")
        answer = (
            _safe_public_text(raw_answer)
            if raw_status == "completed"
            else (_technical_gap_answer(frame) if raw_answer else "")
        )
        if not answer and raw_answer:
            answer = _technical_gap_answer(frame)
        status: ContinuousTurnStatus
        if raw_status == "completed" and answer:
            status = "completed"
        elif answer:
            status = "degraded"
        else:
            status = "failed"
        return ContinuousTurnResult(
            handled=True,
            status=status,
            answer=answer,
            as_of=_fast_path_as_of(raw),
            citations=(),
            warnings=(
                ()
                if status == "completed"
                else ("结构化行情不足，技术位结论已按数据边界降级。",)
            ),
            private_artifact=cast(
                dict[str, object],
                _redact_private(
                    {
                        "schema_version": 1,
                        "execution_kind": "deterministic_fast_path",
                        "outcome": raw,
                    }
                ),
            ),
            events=_public_events(status=status, deterministic=True),
        )

    def _run_episode(
        self,
        frame: TaskFrame,
        control: TurnControlResult,
    ) -> ContinuousTurnResult:
        outcome: AgentOutcome | None = None
        structural: VerifiedEpisodeOutcome | None = None
        try:
            context = self._context_factory(
                frame,
                task_id=f"continuous:{frame.task_frame_hash[:16]}",
                capabilities=control.capabilities,
                tier=self._tier,
                timeout=self._timeout,
                today=self._today,
                latest_data_date=self._latest_data_date,
            )
            if not isinstance(context, ResearchRunContext):
                raise TypeError("context factory must return ResearchRunContext")
            registry = cast(
                ResearchToolRegistry,
                self._registry_factory(frame, context),
            )
            outcome = self._runtime.run(
                task_frame=frame,
                context=context,
                registry=registry,
            )
            if not isinstance(outcome, AgentOutcome):
                raise TypeError("runtime must return AgentOutcome")
            structural = self._structural_verifier(context.contract, outcome)
            if not isinstance(structural, VerifiedEpisodeOutcome):
                raise TypeError(
                    "structural verifier must return VerifiedEpisodeOutcome"
                )
            method = getattr(self._semantic_verifier, "verify", None)
            if callable(method):
                semantic = method(
                    frame=frame,
                    structurally_verified=structural,
                    deadline=context.deadline,
                )
            elif callable(self._semantic_verifier):
                semantic = self._semantic_verifier(
                    frame=frame,
                    structurally_verified=structural,
                    deadline=context.deadline,
                )
            else:
                raise TypeError("semantic verifier must be callable")
            if not isinstance(semantic, SemanticEpisodeOutcome):
                raise TypeError("semantic verifier must return SemanticEpisodeOutcome")
        except Exception as exc:
            partial_artifact: dict[str, object] = {
                "schema_version": 1,
                "execution_kind": "continuous_episode",
                "failure": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
            if outcome is not None:
                partial_artifact["outcome"] = _private_outcome(outcome)
            if structural is not None:
                partial_artifact["structural_verifier"] = structural.to_dict()
            return ContinuousTurnResult(
                handled=True,
                status="failed",
                answer="",
                as_of=None,
                citations=(),
                warnings=("连续研究执行未完成，本轮未生成可验证答案。",),
                private_artifact=cast(
                    dict[str, object],
                    _redact_private(partial_artifact),
                ),
                events=_public_events(status="failed"),
            )

        final_outcome = semantic.verified.outcome
        private_tokens = _private_tokens(final_outcome)
        answer = _safe_public_text(
            semantic.public_answer,
            private_tokens=private_tokens,
        )
        citations = _public_citation_projection(final_outcome, private_tokens)
        if semantic.status == "completed" and answer:
            status: ContinuousTurnStatus = "completed"
        elif answer or final_outcome.evidence:
            status = "degraded"
        else:
            status = "failed"
        if not answer and final_outcome.evidence:
            answer = _episode_gap_answer(frame, structural)
        artifact = {
            "schema_version": 1,
            "execution_kind": "continuous_episode",
            "contract": context.contract.to_dict(),
            "outcome": _private_outcome(outcome),
            "events": [item.to_dict() for item in outcome.events],
            "traces": [item.to_dict() for item in outcome.traces],
            "structural_verifier": structural.to_dict(),
            "semantic_verifier": semantic.to_dict(),
        }
        return ContinuousTurnResult(
            handled=True,
            status=status,
            answer=answer,
            as_of=_episode_as_of(final_outcome, context),
            citations=citations,
            warnings=_episode_warnings(status),
            private_artifact=cast(
                dict[str, object],
                _redact_private(artifact),
            ),
            events=_public_events(status=status),
        )


def _declined_result() -> ContinuousTurnResult:
    return ContinuousTurnResult(
        handled=False,
        status="failed",
        answer="",
        as_of=None,
        citations=(),
        warnings=(),
        private_artifact=None,
        events=(),
    )


def _control_frame_mismatch_result() -> ContinuousTurnResult:
    return ContinuousTurnResult(
        handled=True,
        status="failed",
        answer="",
        as_of=None,
        citations=(),
        warnings=("本轮任务边界校验失败，未执行研究。",),
        private_artifact={
            "schema_version": 1,
            "execution_kind": "continuous_episode",
            "failure": {"code": "control_frame_mismatch"},
        },
        events=(
            {
                "type": "progress",
                "stage": "failed",
                "message": "本轮任务未执行。",
                "status": "failed",
            },
        ),
    )


_PUBLIC_CONTROL_RE = re.compile(
    r"(?:\b[a-z_]*hash\s*[:=]|"
    r"(?:任务帧|任务框架|证据|内容|控制面)?哈希(?:值)?\s*[:：=]|"
    r"system[_ ]?prompt|"
    r"tool[_ ]?calls?|provider(?:[_ ][a-z0-9_-]+)?|"
    r"\bprovider\s*[:=]|系统提示|工具调用)",
    re.IGNORECASE,
)
_SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|token|secret|password|authorization)",
    re.IGNORECASE,
)


def _contains_public_control(
    value: object,
    private_tokens: frozenset[str],
) -> bool:
    text = str(value or "")
    if not text:
        return False
    if _PUBLIC_CONTROL_RE.search(text):
        return True
    folded = text.casefold()
    return any(token in folded for token in private_tokens)


def _safe_public_text(
    value: str,
    *,
    private_tokens: frozenset[str] = frozenset(),
) -> str:
    lines = []
    for raw in redact(str(value or "")).splitlines():
        line = raw.strip()
        if line and not _contains_public_control(line, private_tokens):
            lines.append(line)
    return "\n".join(lines).strip()


def _fast_path_as_of(raw: dict[str, object]) -> str | None:
    direct = raw.get("as_of")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    traces = raw.get("traces")
    if isinstance(traces, (list, tuple)):
        dates = tuple(
            str(item.get("source_trade_date") or "").strip()
            for item in traces
            if isinstance(item, dict) and item.get("source_trade_date")
        )
        if dates:
            return max(dates)
    return None


def _technical_gap_answer(frame: TaskFrame) -> str:
    subject = _safe_public_text(str(frame.subject or "")) or "该标的"
    return (
        f"当前未取得{subject}可用于计算的完整近期日线行情，"
        "因此暂不能可靠给出支撑位或压力位。请稍后重试。"
    )


def _episode_gap_answer(
    frame: TaskFrame,
    structural: VerifiedEpisodeOutcome,
) -> str:
    subject = _safe_public_text(str(frame.subject or "")) or "当前问题"
    contract = structural.contract
    if contract is None:
        return f"关于{subject}，现有证据不足，暂不能给出可靠结论。"
    status_by_id = {
        item.output_id: item.status for item in structural.completion.outputs
    }
    labels = tuple(
        item.description.strip()
        for item in contract.required_outputs
        if item.required
        and status_by_id.get(item.output_id) != "fulfilled"
        and item.description.strip()
    )
    suffix = f"仍需核验：{'、'.join(labels[:3])}。" if labels else ""
    return f"关于{subject}，现有证据不足，暂不能给出可靠结论。{suffix}"


def _episode_warnings(
    status: ContinuousTurnStatus,
) -> tuple[str, ...]:
    if status == "completed":
        return ()
    if status == "degraded":
        return ("证据或语义核验未完全通过，已按证据边界降级。",)
    return ("本轮未取得可公开的答案或证据。",)


def _redact_private(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            safe_key = redact(str(key))
            redacted[safe_key] = (
                "[REDACTED]"
                if _SECRET_KEY_RE.search(safe_key)
                else _redact_private(item)
            )
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact_private(item) for item in value]
    return value


def _private_outcome(outcome: AgentOutcome) -> dict[str, object]:
    payload = outcome.to_dict()
    payload["evidence"] = [asdict(item) for item in outcome.evidence]
    return payload


def _private_tokens(outcome: AgentOutcome) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in (
            outcome.task_frame_hash,
            *(item.tool for item in outcome.evidence),
            *(item.content_hash for item in outcome.evidence),
            *(item.internal_locator for item in outcome.evidence),
            *(trace.provider for trace in outcome.traces),
        )
        if token
    )


def _public_citation_projection(
    outcome: AgentOutcome,
    private_tokens: frozenset[str],
) -> tuple[dict[str, object], ...]:
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        for content_hash in binding.evidence_hashes
    }
    citations: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in outcome.evidence:
        if item.content_hash not in bound_hashes:
            continue
        values = tuple(
            " ".join(redact(str(value or "")).split())
            for value in (item.title, item.source, item.source_date)
        )
        if any(
            _contains_public_control(value, private_tokens) for value in values if value
        ):
            continue
        if values in seen or not any(values):
            continue
        seen.add(values)
        citations.append(
            {
                "title": values[0],
                "source": values[1],
                "date": values[2],
            }
        )
    return tuple(citations)


def _episode_as_of(
    outcome: AgentOutcome,
    context: ResearchRunContext,
) -> str | None:
    dates = tuple(
        str(item.source_date).strip()
        for item in outcome.evidence
        if item.source_date and str(item.source_date).strip()
    )
    if dates:
        return max(dates)
    return context.latest_data_date


def _public_events(
    *,
    status: ContinuousTurnStatus,
    deterministic: bool = False,
) -> tuple[dict[str, object], ...]:
    if deterministic:
        stages = (
            ("understanding", "已锁定本轮任务边界。"),
            ("structured_data", "已完成结构化行情计算。"),
            ("finalizing", "已按数据边界形成回答。"),
        )
    else:
        stages = (
            ("understanding", "已锁定本轮任务边界。"),
            ("research", "已完成本轮证据收集。"),
            ("verification", "已完成回答核验。"),
            ("finalizing", "已按核验结果形成回答。"),
        )
    return tuple(
        {
            "type": "progress",
            "stage": stage,
            "message": message,
            "status": status if index == len(stages) - 1 else "running",
        }
        for index, (stage, message) in enumerate(stages)
    )


__all__ = [
    "ContinuousTurnAdapter",
    "ContinuousTurnResult",
    "ContinuousTurnStatus",
    "RuntimeMode",
]
