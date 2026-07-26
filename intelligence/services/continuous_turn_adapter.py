"""Compose one canonical turn into the continuous Episode runtime.

The adapter is a strangler seam, not a router: callers pass an already-frozen
``TaskFrame`` and ``TurnControlResult``.  It may decline, preserve a
deterministic fast path, or run exactly one research Episode and its two
verification gates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import date
import os
import re
import time
from typing import Literal, Protocol, cast
from uuid import uuid4

from intelligence.services import llm_refine
from intelligence.services.agent_runtime import AgentOutcome, AgentRuntime
from intelligence.services.evidence_ledger import EvidenceLedger, EvidenceLedgerSnapshot
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.episode_tools import (
    build_episode_registry,
    run_deterministic_fast_path,
)
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.research_contract import ResearchDeadline, ResearchRunContext
from intelligence.services.repair_coordinator import (
    build_repair_goal,
    grant_for_progress,
    max_repair_cycles_for_tier,
    progress_from_ledger,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import redact, redact_value
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_control_core import TurnControlResult


RuntimeMode = Literal["off", "canary", "on"]
ContinuousTurnStatus = Literal["completed", "partial", "degraded", "failed"]
CONTINUOUS_FAST_PATH_TYPES = frozenset({"market_technical"})
DEFAULT_VERIFICATION_RESERVE_SECONDS = 30.0
LEGACY_DETERMINISTIC_OWNER_TYPES = frozenset(
    {"external_market", "quick_fact", "dated_market_review"}
)


def _new_task_id() -> str:
    return str(uuid4())


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
    llm_provider: str | None = None


class SemanticVerifier(Protocol):
    def verify(
        self,
        *,
        frame: TaskFrame,
        structurally_verified: VerifiedEpisodeOutcome,
        deadline: ResearchDeadline,
    ) -> SemanticEpisodeOutcome: ...


class ContinuousTurnAdapter:
    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        semantic_verifier: SemanticVerifier,
        runtime_name: str = "continuous_glm",
        mode: RuntimeMode | None = None,
        context_factory: Callable[..., object] = build_episode_context,
        registry_factory: Callable[..., object] = build_episode_registry,
        fast_path_runner: Callable[..., object] = run_deterministic_fast_path,
        structural_verifier: Callable[..., object] = verify_episode_outcome,
        task_id_factory: Callable[[], str] = _new_task_id,
        timeout: float = 90.0,
        verification_reserve: float = DEFAULT_VERIFICATION_RESERVE_SECONDS,
        synthesis_reserve_for_task: Callable[..., float] | None = None,
        tier: str = "standard",
        today: str | None = None,
        latest_data_date: str | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        deadline_expires_at: float | None = None,
    ) -> None:
        selected_mode = (
            str(os.environ.get("ASK_CONTINUOUS_RUNTIME") or "off").strip().lower()
            if mode is None
            else mode
        )
        if selected_mode not in {"off", "canary", "on"}:
            raise ValueError(f"unsupported continuous runtime mode: {selected_mode}")
        if not callable(getattr(semantic_verifier, "verify", None)):
            raise TypeError("semantic verifier must provide callable verify(...)")
        cleaned_runtime_name = str(runtime_name or "").strip()
        if not cleaned_runtime_name:
            raise ValueError("runtime_name must be non-empty")
        if not callable(task_id_factory):
            raise TypeError("task_id_factory must be callable")
        if synthesis_reserve_for_task is not None and not callable(
            synthesis_reserve_for_task
        ):
            raise TypeError("synthesis_reserve_for_task must be callable")
        self._runtime = runtime
        self._runtime_name = cleaned_runtime_name
        self._mode = cast(RuntimeMode, selected_mode)
        self._context_factory = context_factory
        self._registry_factory = registry_factory
        self._fast_path_runner = fast_path_runner
        self._structural_verifier = structural_verifier
        self._semantic_verifier = semantic_verifier
        self._task_id_factory = task_id_factory
        self._timeout = max(0.0, float(timeout))
        self._verification_reserve = max(0.0, float(verification_reserve))
        self._synthesis_reserve_for_task = synthesis_reserve_for_task
        self._tier = str(tier or "standard").strip()
        self._today = today
        self._latest_data_date = latest_data_date
        self._is_cancelled = is_cancelled or (lambda: False)
        self._deadline_expires_at = (
            None if deadline_expires_at is None else float(deadline_expires_at)
        )

    @property
    def mode(self) -> RuntimeMode:
        return self._mode

    @property
    def canary_id(self) -> str:
        if self._mode != "canary":
            return ""
        return os.environ.get("CONTINUOUS_RUNTIME_CANARY_ID", "").strip()

    def _remaining_timeout(self) -> float:
        if self._deadline_expires_at is None:
            return self._timeout
        return max(
            0.0,
            min(
                self._timeout,
                self._deadline_expires_at - time.monotonic(),
            ),
        )

    def handle(
        self,
        *,
        frame: TaskFrame,
        control: TurnControlResult,
    ) -> ContinuousTurnResult:
        if self._is_cancelled():
            return _cancelled_result()
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
            return _control_frame_mismatch_result(self._runtime_name)
        if frame.question_type in LEGACY_DETERMINISTIC_OWNER_TYPES:
            return _declined_result()
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
        if frame.question_type in CONTINUOUS_FAST_PATH_TYPES:
            return self._run_fast_path(frame)
        return self._run_episode(frame, control)

    def _run_fast_path(self, frame: TaskFrame) -> ContinuousTurnResult:
        try:
            raw = self._fast_path_runner(
                frame,
                timeout=self._remaining_timeout(),
            )
            if self._is_cancelled():
                return _cancelled_result()
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
                            "runtime_backend": self._runtime_name,
                            "failure": {
                                "type": type(exc).__name__,
                                "message": str(exc),
                            },
                            "metrics": {
                                "provider_attempts": 0,
                                "tool_calls": 0,
                                "duplicate_queries": 0,
                                "structural_status": "failed",
                                "semantic_status": "unavailable",
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
                        "runtime_backend": self._runtime_name,
                        "outcome": raw,
                        "metrics": {
                            "provider_attempts": 0,
                            "tool_calls": _non_negative_int(raw.get("tool_calls")),
                            "duplicate_queries": 0,
                            "structural_status": (
                                raw_status
                                if raw_status in {"completed", "partial", "failed"}
                                else "partial"
                            ),
                            "semantic_status": (
                                "passed"
                                if raw_status == "completed" and answer
                                else "unavailable"
                            ),
                        },
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
        context: ResearchRunContext | None = None
        outcome: AgentOutcome | None = None
        structural: VerifiedEpisodeOutcome | None = None
        semantic: SemanticEpisodeOutcome | None = None
        session: object | None = None
        repair_cycles = 0
        semantic_verifier_stale = False
        attempts_before = _ledger_attempt_count()
        try:
            root_timeout = self._remaining_timeout()
            root_deadline = ResearchDeadline.from_timeout(root_timeout)
            verification_reserve = min(
                self._verification_reserve,
                root_timeout / 3.0,
            )
            runtime_timeout = max(0.0, root_timeout - verification_reserve)
            task_id = str(self._task_id_factory() or "").strip()
            if not task_id:
                raise ValueError("task_id_factory must return a non-empty identity")
            context_kwargs: dict[str, object] = {
                "task_id": task_id,
                "capabilities": control.capabilities,
                "tier": self._tier,
                "timeout": runtime_timeout,
                "today": self._today,
                "latest_data_date": self._latest_data_date,
                "conversation_context": control.conversation_context,
            }
            if self._synthesis_reserve_for_task is not None:
                context_kwargs["synthesis_reserve"] = max(
                    0.0,
                    float(
                        self._synthesis_reserve_for_task(
                            tier=self._tier,
                            question_type=frame.question_type,
                        )
                    ),
                )
            context_candidate = self._context_factory(frame, **context_kwargs)
            if not isinstance(context_candidate, ResearchRunContext):
                raise TypeError("context factory must return ResearchRunContext")
            context = context_candidate
            registry = cast(
                ResearchToolRegistry,
                self._registry_factory(frame, context),
            )
            if self._is_cancelled():
                return _cancelled_result()
            start = getattr(self._runtime, "start", None)
            if callable(start):
                session = start(frame, context=context, registry=registry)
                outcome_candidate = getattr(session, "outcome", None)
            else:
                outcome_candidate = self._runtime.run(
                    task_frame=frame,
                    context=context,
                    registry=registry,
                )
            if not isinstance(outcome_candidate, AgentOutcome):
                raise TypeError("runtime must return AgentOutcome")
            outcome = outcome_candidate
            if self._is_cancelled():
                return _cancelled_result()
            structural_candidate = self._structural_verifier(
                context.contract,
                outcome,
            )
            if not isinstance(structural_candidate, VerifiedEpisodeOutcome):
                raise TypeError(
                    "structural verifier must return VerifiedEpisodeOutcome"
                )
            structural = structural_candidate
            episode_evidence_ledger = (
                getattr(session, "evidence_ledger", None)
                if session is not None
                else None
            )
            if not isinstance(episode_evidence_ledger, EvidenceLedger):
                episode_evidence_ledger = EvidenceLedger(
                    information_cutoff=context.information_cutoff.as_of_date,
                )
            initial_snapshot = (
                getattr(session, "initial_evidence_snapshot", None)
                if session is not None
                else None
            )
            previous_snapshot = (
                initial_snapshot
                if isinstance(initial_snapshot, EvidenceLedgerSnapshot)
                else _empty_repair_snapshot(context)
            )
            current_snapshot = _repair_snapshot(
                outcome,
                structural,
                context,
                ledger=episode_evidence_ledger,
            )
            max_repair_cycles = max_repair_cycles_for_tier(
                context.contract.research_tier
            )
            repair_terminal = False
            while (
                session is not None
                and structural.missing_outputs
                and repair_cycles < max_repair_cycles
                and not repair_terminal
                and not self._is_cancelled()
                and not context.deadline.expired
            ):
                repaired = self._resume_for_gap(
                    session=session,
                    context=context,
                    outcome=outcome,
                    structural=structural,
                    previous_snapshot=previous_snapshot,
                    current_snapshot=current_snapshot,
                    cycle=repair_cycles + 1,
                    rejected_claims=(),
                )
                if repaired is None:
                    break
                previous_snapshot = current_snapshot
                outcome, structural = repaired
                current_snapshot = _repair_snapshot(
                    outcome,
                    structural,
                    context,
                    ledger=episode_evidence_ledger,
                )
                repair_terminal = outcome.stop_reason in {
                    "repair_deadline_exhausted",
                    "repair_model_stop",
                }
                if outcome.stop_reason != "repair_model_stop":
                    repair_cycles += 1
            if self._is_cancelled():
                return _cancelled_result()
            if root_deadline.expired:
                raise TimeoutError("research deadline exhausted before semantic verification")
            semantic_candidate = self._semantic_verifier.verify(
                frame=frame,
                structurally_verified=structural,
                deadline=root_deadline,
            )
            if not isinstance(semantic_candidate, SemanticEpisodeOutcome):
                raise TypeError("semantic verifier must return SemanticEpisodeOutcome")
            semantic = semantic_candidate
            while (
                session is not None
                and (
                    semantic.gap_output_ids
                    or semantic.rejected_claim_indexes
                    or semantic.verified.missing_outputs
                )
                and repair_cycles < max_repair_cycles
                and not repair_terminal
                and not self._is_cancelled()
                and not context.deadline.expired
            ):
                repaired = self._resume_for_gap(
                    session=session,
                    context=context,
                    outcome=outcome,
                    structural=semantic.verified,
                    previous_snapshot=previous_snapshot,
                    current_snapshot=current_snapshot,
                    cycle=repair_cycles + 1,
                    rejected_claims=tuple(
                        f"claim_index:{index}"
                        for index in semantic.rejected_claim_indexes
                    ),
                    semantic_gap_outputs=semantic.gap_output_ids,
                )
                if repaired is None:
                    break
                previous_snapshot = current_snapshot
                outcome, structural = repaired
                current_snapshot = _repair_snapshot(
                    outcome,
                    structural,
                    context,
                    ledger=episode_evidence_ledger,
                )
                repair_terminal = outcome.stop_reason in {
                    "repair_deadline_exhausted",
                    "repair_model_stop",
                }
                if outcome.stop_reason != "repair_model_stop":
                    repair_cycles += 1
                if (
                    repair_terminal
                    or self._is_cancelled()
                    or context.deadline.expired
                ):
                    semantic_verifier_stale = True
                    break
                semantic_candidate = self._semantic_verifier.verify(
                    frame=frame,
                    structurally_verified=structural,
                    deadline=root_deadline,
                )
                if not isinstance(semantic_candidate, SemanticEpisodeOutcome):
                    raise TypeError(
                        "semantic verifier must return SemanticEpisodeOutcome"
                    )
                semantic = semantic_candidate
            if self._is_cancelled():
                return _cancelled_result()
        except Exception as exc:
            partial_artifact: dict[str, object] = {
                "schema_version": 1,
                "execution_kind": "continuous_episode",
                "runtime_backend": self._runtime_name,
                "failure": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                "metrics": _episode_metrics(
                    outcome,
                    attempts_before=attempts_before,
                    structural_status=(
                        structural.verified_status
                        if structural is not None
                        else "failed"
                    ),
                    semantic_status=(
                        semantic.judge_status if semantic is not None else "unavailable"
                    ),
                ),
            }
            if outcome is not None:
                partial_artifact["outcome"] = _private_outcome(outcome)
            partial_artifact["structural_verifier"] = (
                structural.to_dict() if structural is not None else None
            )
            if outcome is not None and outcome.evidence and context is not None:
                partial_artifact["contract"] = context.contract.to_dict()
                trusted_structural = (
                    structural
                    if structural is not None
                    and _verified_boundary_matches(
                        structural,
                        frame=frame,
                        context=context,
                    )
                    else None
                )
                trusted_outcome = (
                    trusted_structural.outcome
                    if trusted_structural is not None
                    else None
                )
                fulfilled_output_ids = (
                    _fulfilled_output_ids(trusted_structural)
                    if trusted_structural is not None
                    else frozenset()
                )
                private_tokens = (
                    _private_tokens(trusted_outcome)
                    if trusted_outcome is not None
                    else frozenset()
                )
                return ContinuousTurnResult(
                    handled=True,
                    status="degraded",
                    answer=_verification_failure_gap_answer(
                        frame,
                        context,
                        trusted_structural,
                    ),
                    as_of=(
                        _episode_as_of(
                            trusted_outcome,
                            context,
                            allowed_output_ids=fulfilled_output_ids,
                        )
                        if trusted_outcome is not None
                        else None
                    ),
                    citations=(
                        _public_citation_projection(
                            trusted_outcome,
                            private_tokens,
                            allowed_output_ids=fulfilled_output_ids,
                        )
                        if trusted_outcome is not None
                        else ()
                    ),
                    warnings=("核验阶段未完成，已保留现有证据并按任务契约降级。",),
                    private_artifact=cast(
                        dict[str, object],
                        _redact_private(partial_artifact),
                    ),
                    events=_public_events(status="degraded"),
                )
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
        fulfilled_output_ids = _fulfilled_output_ids(
            semantic.verified,
            excluded_output_ids=frozenset(semantic.gap_output_ids),
        )
        answer = _safe_public_text(
            semantic.public_answer,
            private_tokens=private_tokens,
        )
        citations = _public_citation_projection(
            final_outcome,
            private_tokens,
            allowed_output_ids=fulfilled_output_ids,
        )
        if semantic.status == "completed" and answer:
            status: ContinuousTurnStatus = "completed"
        elif (
            semantic.status == "partial"
            and semantic.judge_status in {"passed", "repaired"}
            and answer
        ):
            status = "partial"
        elif answer or final_outcome.evidence:
            status = "degraded"
        else:
            status = "failed"
        if not answer and final_outcome.evidence:
            answer = _episode_gap_answer(frame, structural)
        semantic_verifier_stale = semantic_verifier_stale or (
            semantic.verified.outcome.events != outcome.events
        )
        artifact = {
            "schema_version": 1,
            "execution_kind": "continuous_episode",
            "runtime_backend": self._runtime_name,
            "contract": context.contract.to_dict(),
            "outcome": _private_outcome(outcome),
            "events": [item.to_dict() for item in outcome.events],
            "traces": [item.to_dict() for item in outcome.traces],
            "structural_verifier": structural.to_dict(),
            "semantic_verifier": semantic.to_dict(),
            "semantic_verifier_stale": semantic_verifier_stale,
            "repair_cycles": repair_cycles,
            "metrics": _episode_metrics(
                outcome,
                attempts_before=attempts_before,
                structural_status=structural.verified_status,
                semantic_status=semantic.judge_status,
            ),
        }
        return ContinuousTurnResult(
            handled=True,
            status=status,
            answer=answer,
            as_of=_episode_as_of(
                final_outcome,
                context,
                allowed_output_ids=fulfilled_output_ids,
            ),
            citations=citations,
            warnings=_episode_warnings(status),
            private_artifact=cast(
                dict[str, object],
                _redact_private(artifact),
            ),
            events=_public_events(status=status),
            llm_provider=_episode_llm_provider(
                outcome,
                runtime_name=self._runtime_name,
            ),
        )

    def _resume_for_gap(
        self,
        *,
        session: object,
        context: ResearchRunContext,
        outcome: AgentOutcome,
        structural: VerifiedEpisodeOutcome,
        previous_snapshot: EvidenceLedgerSnapshot,
        current_snapshot: EvidenceLedgerSnapshot,
        cycle: int,
        rejected_claims: tuple[str, ...],
        semantic_gap_outputs: tuple[str, ...] = (),
    ) -> tuple[AgentOutcome, VerifiedEpisodeOutcome] | None:
        root_budget = context.root_budget
        resume = getattr(session, "resume", None)
        episode_id = str(getattr(session, "episode_id", "") or "").strip()
        if root_budget is None or not callable(resume) or not episode_id:
            return None
        progress = progress_from_ledger(previous_snapshot, current_snapshot)
        remaining_calls = max(0, int(root_budget.remaining_calls))
        remaining_seconds = min(
            max(0.0, float(root_budget.remaining_seconds)),
            max(0.0, float(context.deadline.remaining())),
        )
        goal = build_repair_goal(
            episode_id=episode_id,
            missing_outputs=tuple(
                dict.fromkeys((*structural.missing_outputs, *semantic_gap_outputs))
            ),
            missing_capabilities=structural.mandatory_missing_capabilities,
            rejected_claims=rejected_claims,
            attempted_actions=tuple(
                f"{trace.capability}:{trace.provider}" for trace in outcome.traces
            ),
            previous_progress=progress,
            remaining_calls=remaining_calls,
            remaining_seconds=remaining_seconds,
            cycle=cycle,
        )
        grant = grant_for_progress(
            goal,
            progress,
            root_budget=root_budget,
            research_tier=context.contract.research_tier,
        )
        if grant is None:
            return None
        granted_goal = replace(
            goal,
            remaining_calls=grant.calls_granted,
            remaining_seconds=grant.seconds_granted,
        )
        candidate = resume(granted_goal)
        if not isinstance(candidate, AgentOutcome):
            raise TypeError("episode session resume must return AgentOutcome")
        verified = self._structural_verifier(context.contract, candidate)
        if not isinstance(verified, VerifiedEpisodeOutcome):
            raise TypeError("structural verifier must return VerifiedEpisodeOutcome")
        return candidate, verified


def _empty_repair_snapshot(context: ResearchRunContext) -> EvidenceLedgerSnapshot:
    ledger = EvidenceLedger(
        information_cutoff=context.information_cutoff.as_of_date,
    )
    for required in context.contract.required_outputs:
        if required.required and required.grounding_mode == "evidence":
            ledger.open_gap(required.output_id)
    return ledger.snapshot()


def _repair_snapshot(
    outcome: AgentOutcome,
    structural: VerifiedEpisodeOutcome,
    context: ResearchRunContext,
    *,
    ledger: EvidenceLedger | None = None,
) -> EvidenceLedgerSnapshot:
    ledger = ledger or EvidenceLedger(
        information_cutoff=context.information_cutoff.as_of_date,
    )
    missing = set(structural.missing_outputs)
    targets_by_hash: dict[str, list[str]] = {}
    for binding in outcome.bindings:
        if binding.gap or not binding.evidence_hashes:
            continue
        for content_hash in binding.evidence_hashes:
            targets_by_hash.setdefault(content_hash, []).append(binding.output_id)
    for item in outcome.evidence:
        targets = tuple(targets_by_hash.get(item.content_hash, ()))
        ledger.append(item, covered_outputs=targets)
    for required in context.contract.required_outputs:
        if not required.required or required.grounding_mode != "evidence":
            continue
        if required.output_id in missing:
            ledger.open_gap(required.output_id)
            continue
        flattened = tuple(
            content_hash
            for binding in outcome.bindings
            if binding.output_id == required.output_id and not binding.gap
            for content_hash in binding.evidence_hashes
        )
        if flattened:
            covered = ledger.mark_output_covered(
                required.output_id,
                evidence_ids=flattened,
            )
            if covered:
                ledger.close_gap(required.output_id)
                continue
        ledger.open_gap(required.output_id)
    return ledger.snapshot()


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _ledger_attempt_count() -> int:
    ledger = llm_refine.current_call_ledger()
    if ledger is None:
        return 0
    summary = ledger.summary()
    return _non_negative_int(summary.get("call_count"))


def _duplicate_query_count(outcome: AgentOutcome | None) -> int:
    if outcome is None:
        return 0
    return sum(
        1
        for event in outcome.events
        if event.kind == "tool_error"
        and str(event.payload.get("error") or "") == "duplicate_query"
    )


def _episode_llm_provider(
    outcome: AgentOutcome,
    *,
    runtime_name: str,
) -> str | None:
    """Return a stable provider label only for a successful observable turn."""

    for event in outcome.events:
        if event.kind != "model_turn":
            continue
        payload = event.payload
        provider = str(payload.get("provider_name") or "").strip()
        error = str(payload.get("error") or "").strip()
        content = str(payload.get("content") or "").strip()
        tool_calls = payload.get("tool_calls")
        has_tool_calls = isinstance(tool_calls, (list, tuple)) and bool(tool_calls)
        if provider and not error and (content or has_tool_calls):
            return provider
    if outcome.usage.llm_calls > 0:
        return {
            "sdk_gpt": "openai",
            "sdk_glm": "zhipu",
        }.get(runtime_name)
    return None


def _episode_metrics(
    outcome: AgentOutcome | None,
    *,
    attempts_before: int,
    structural_status: str,
    semantic_status: str,
) -> dict[str, object]:
    provider_attempts = max(0, _ledger_attempt_count() - attempts_before)
    if outcome is not None:
        provider_attempts = max(provider_attempts, outcome.usage.llm_calls)
    return {
        "provider_attempts": provider_attempts,
        "tool_calls": outcome.usage.tool_calls if outcome is not None else 0,
        "duplicate_queries": _duplicate_query_count(outcome),
        "structural_status": (
            structural_status
            if structural_status in {"completed", "partial", "failed"}
            else "failed"
        ),
        "semantic_status": (
            semantic_status
            if semantic_status in {"passed", "repaired", "rejected", "unavailable"}
            else "unavailable"
        ),
    }


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


def _cancelled_result() -> ContinuousTurnResult:
    return ContinuousTurnResult(
        handled=True,
        status="failed",
        answer="",
        as_of=None,
        citations=(),
        warnings=(),
        private_artifact=None,
        events=(),
    )


def _control_frame_mismatch_result(runtime_name: str) -> ContinuousTurnResult:
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
            "runtime_backend": runtime_name,
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
    r"tool[_ ]?calls?|"
    r"\bprovider\s*[:=]|\bprovider_(?:trace|attempts?)\b\s*[:=]?|"
    r"\bendpoint\s*[:=]|系统提示|工具调用)",
    re.IGNORECASE,
)


def _contains_public_control(
    value: object,
    private_tokens: frozenset[str],
) -> bool:
    text = str(value or "")
    if not text:
        return False
    if redact(text) != text:
        return True
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
    for raw in str(value or "").splitlines():
        line = raw.strip()
        if line and not _contains_public_control(line, private_tokens):
            lines.append(redact(line))
    return "\n".join(lines).strip()


def _fast_path_as_of(raw: dict[str, object]) -> str | None:
    direct = _parse_iso_date(raw.get("as_of"))
    if direct is not None:
        return direct.isoformat()
    traces = raw.get("traces")
    if isinstance(traces, (list, tuple)):
        dates = tuple(
            parsed
            for item in traces
            if isinstance(item, dict)
            and (parsed := _parse_iso_date(item.get("source_trade_date"))) is not None
        )
        if dates:
            return max(dates).isoformat()
    return None


def _technical_gap_answer(frame: TaskFrame) -> str:
    subject = _safe_public_text(str(frame.subject or "")) or "该标的"
    return (
        f"当前未取得{subject}可用于计算的完整近期日线行情，"
        "因此暂不能可靠给出支撑位或压力位。请稍后重试。"
    )


def _safe_gap_answer(
    value: str,
    *,
    frame: TaskFrame,
) -> str:
    safe = _safe_public_text(value)
    if safe:
        return safe
    subject = _safe_public_text(str(frame.subject or "")) or "当前问题"
    return f"关于{subject}，本轮证据或核验不足，暂不能给出可靠结论。"


def _episode_gap_answer(
    frame: TaskFrame,
    structural: VerifiedEpisodeOutcome,
) -> str:
    subject = _safe_public_text(str(frame.subject or "")) or "当前问题"
    contract = structural.contract
    if contract is None:
        return _safe_gap_answer(
            f"关于{subject}，现有证据不足，暂不能给出可靠结论。",
            frame=frame,
        )
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
    return _safe_gap_answer(
        f"关于{subject}，现有证据不足，暂不能给出可靠结论。{suffix}",
        frame=frame,
    )


def _verification_failure_gap_answer(
    frame: TaskFrame,
    context: ResearchRunContext,
    structural: VerifiedEpisodeOutcome | None,
) -> str:
    subject = _safe_public_text(str(frame.subject or "")) or "当前问题"
    contract = (
        structural.contract
        if structural is not None and structural.contract is not None
        else context.contract
    )
    status_by_id = (
        {item.output_id: item.status for item in structural.completion.outputs}
        if structural is not None
        else {}
    )
    labels = tuple(
        item.description.strip()
        for item in contract.required_outputs
        if item.required
        and (structural is None or status_by_id.get(item.output_id) != "fulfilled")
        and item.description.strip()
    )
    if not labels:
        labels = tuple(
            item.description.strip()
            for item in contract.required_outputs
            if item.required and item.description.strip()
        )
    suffix = f"仍需重新核验：{'、'.join(labels[:3])}。" if labels else ""
    return _safe_gap_answer(
        f"关于{subject}，本轮核验未完成，现有证据仅作为候选参考。{suffix}",
        frame=frame,
    )


def _episode_warnings(
    status: ContinuousTurnStatus,
) -> tuple[str, ...]:
    if status == "completed":
        return ()
    if status == "partial":
        return ()
    if status == "degraded":
        return ("证据或语义核验未完全通过，已按证据边界降级。",)
    return ("本轮未取得可公开的答案或证据。",)


def _redact_private(value: object) -> object:
    return redact_value(value)


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
        )
        if token
    )


def _fulfilled_output_ids(
    structural: VerifiedEpisodeOutcome,
    *,
    excluded_output_ids: frozenset[str] = frozenset(),
) -> frozenset[str]:
    return frozenset(
        item.output_id
        for item in structural.completion.outputs
        if item.status == "fulfilled"
        and item.output_id not in excluded_output_ids
    )


def _verified_boundary_matches(
    structural: VerifiedEpisodeOutcome,
    *,
    frame: TaskFrame,
    context: ResearchRunContext,
) -> bool:
    expected = frame.task_frame_hash
    contract = structural.contract
    return bool(
        expected
        and context.contract.task_frame_hash == expected
        and structural.outcome.task_frame_hash == expected
        and contract is not None
        and contract.task_frame_hash == expected
    )


def _public_citation_projection(
    outcome: AgentOutcome,
    private_tokens: frozenset[str],
    *,
    allowed_output_ids: frozenset[str],
) -> tuple[dict[str, object], ...]:
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        if binding.output_id in allowed_output_ids
        for content_hash in binding.evidence_hashes
    }
    citations: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in outcome.evidence:
        if item.content_hash not in bound_hashes:
            continue
        raw_values = tuple(
            str(value or "") for value in (item.title, item.source, item.source_date)
        )
        if any(
            _contains_public_control(value, private_tokens)
            for value in raw_values
            if value
        ):
            continue
        values = tuple(
            " ".join(redact(str(value or "")).split()) for value in raw_values
        )
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
    *,
    allowed_output_ids: frozenset[str],
) -> str | None:
    bound_hashes = {
        content_hash
        for binding in outcome.bindings
        if binding.output_id in allowed_output_ids
        for content_hash in binding.evidence_hashes
    }
    if not bound_hashes:
        return None
    dates = tuple(
        parsed
        for item in outcome.evidence
        if item.content_hash in bound_hashes
        and (parsed := _parse_iso_date(item.source_date)) is not None
    )
    if dates:
        return max(dates).isoformat()
    fallback = _parse_iso_date(context.latest_data_date)
    return fallback.isoformat() if fallback is not None else None


def _parse_iso_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text or redact(text) != text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _public_events(
    *,
    status: ContinuousTurnStatus,
    deterministic: bool = False,
) -> tuple[dict[str, object], ...]:
    terminal_status = "completed" if status == "partial" else status
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
            "status": terminal_status if index == len(stages) - 1 else "running",
        }
        for index, (stage, message) in enumerate(stages)
    )


__all__ = [
    "CONTINUOUS_FAST_PATH_TYPES",
    "ContinuousTurnAdapter",
    "ContinuousTurnResult",
    "ContinuousTurnStatus",
    "LEGACY_DETERMINISTIC_OWNER_TYPES",
    "RuntimeMode",
    "SemanticVerifier",
]
