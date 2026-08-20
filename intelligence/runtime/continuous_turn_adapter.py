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
from intelligence.services.episode_issues import (
    Issue,
    IssueCode,
    plan_issue_backfill,
)
from intelligence.services.episode_phase import PhaseRecorder
from intelligence.services.episode_projection import project_durable_events
from intelligence.services.episode_progress import EpisodeProgress
from intelligence.services.episode_semantic_verifier import (
    DEFAULT_JUDGE_TIMEOUT_SECONDS,
    SemanticEpisodeOutcome,
    draft_sentence_count,
    numeric_condition_unsupported,
)
from intelligence.services.rejudge_pending import append_pending_from_artifact
from intelligence.services.episode_tools import (
    build_episode_registry,
    run_deterministic_fast_path,
)
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.honesty_gates import with_calendar_disclosure
from intelligence.services.provider_latency import (
    provider_name_from,
    repair_seconds_cap_for,
)
from intelligence.services.repair_coordinator import (
    admit_backfill_repair,
    admit_repair,
    max_repair_cycles_for_tier,
    progress_from_ledger,
)
from intelligence.services.research_contract import ResearchDeadline, ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    SatisfiabilityCheck,
    check_satisfiability,
)
from intelligence.services.run_store import redact, redact_value
from intelligence.services.task_frame import TaskFrame
from intelligence.services.track_contract import (
    contract_receipt,
    is_contract_rewrite_only,
    merge_track_missing_outputs,
)
from intelligence.runtime.turn_control_core import TurnControlResult


RuntimeMode = Literal["off", "canary", "on"]
ContinuousTurnStatus = Literal["completed", "partial", "degraded", "failed"]
CONTINUOUS_FAST_PATH_TYPES = frozenset({"market_technical"})
_SUCCESSFUL_REPAIR_STOP_REASONS = frozenset(
    {"model_finish", "repair_model_finish"}
)
_TERMINAL_REPAIR_STOP_REASONS = frozenset(
    {
        "repair_deadline_exhausted",
        "repair_model_stop",
    }
)
_DELIVERY_REPAIR_STOP_REASONS = frozenset(
    {"sdk_invalid_finish", "sdk_invalid_repair_finish", "sdk_timeout"}
)
# 饿死型冷启动：检索窗烧穿，或主路径 LLM 超时/异常，且零证据。
# A1-R2 是后者——TimeoutError 走 model_unavailable，tools_open 已关，
# delivery 要证据，进度闸要新证据，三条路全死。不能把「模型主动收场」
# （model_finish）算进来，那是零证据降级信号，不是饿死。
_COLD_RESTART_STOP_REASONS = frozenset(
    {"deadline_exhausted", "model_unavailable"}
)
# First judge attempt is the shared window (50s after the 08-20 grok tail
# of 46.7s). OpenAI-compatible transports can return a few seconds after
# their client timeout while the socket unwinds. Reserve judge + 10s grace
# so a full research burn still leaves one dispatchable attempt.
DEFAULT_VERIFICATION_RESERVE_SECONDS = DEFAULT_JUDGE_TIMEOUT_SECONDS + 10.0
DETERMINISTIC_OWNER_TYPES = frozenset(
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
    # 未满足的必需输出（契约描述文案，已是公开口径）。交付层用它把
    # 「缺口声明」镜像成可点击的追问（knevo q12 蒸馏的 suggest_options
    # 形状）：R15 对照 9:2:0 里多题的失分不是缺口本身，而是缺口变成了
    # 句号——追问负担全落在用户身上。
    open_gaps: tuple[str, ...] = ()


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
        progress_sink: Callable[[EpisodeProgress], None] | None = None,
        repair_seconds_cap: float | None = None,
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
        self._progress_sink = progress_sink
        # 修复轮窗口按生效 provider 的延迟地板取，不用全局常数。
        # 显式传参优先；未传时向 runtime 问链首——问 runtime 而不是重新
        # detect_providers()，因为生产在 app.py 注入的才是生效值（BYOK
        # 与 env 可以不一致）。问不到就落默认帽（= 改动前行为）。
        self._repair_seconds_cap = (
            float(repair_seconds_cap)
            if repair_seconds_cap is not None
            else repair_seconds_cap_for(provider_name_from(runtime))
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

    def _publish_progress(
        self,
        *,
        key: str,
        stage: str,
        message: str,
        status: str,
    ) -> None:
        if self._progress_sink is None or self._is_cancelled():
            return
        try:
            self._progress_sink(EpisodeProgress(key, stage, message, status))
        except Exception:
            # Run progress is advisory observability. Truth gates and answer
            # ownership must remain available if the public sink is broken.
            pass

    def _terminal_events(
        self,
        *,
        status: ContinuousTurnStatus,
        deterministic: bool = False,
    ) -> tuple[dict[str, object], ...]:
        if self._progress_sink is not None:
            return ()
        return _public_events(status=status, deterministic=deterministic)

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
        if frame.question_type in DETERMINISTIC_OWNER_TYPES:
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
        self._publish_progress(
            key="adapter:understanding",
            stage="understanding",
            message="已对齐本轮任务并进入研究。",
            status="completed",
        )
        if frame.question_type in CONTINUOUS_FAST_PATH_TYPES:
            return self._run_fast_path(frame)
        return self._run_episode(frame, control)

    def _run_fast_path(self, frame: TaskFrame) -> ContinuousTurnResult:
        try:
            raw = self._fast_path_runner(
                frame,
                timeout=self._remaining_timeout(),
                as_of=self._latest_data_date,
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
                events=self._terminal_events(status="failed", deterministic=True),
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
        fast_as_of = _fast_path_as_of(raw)
        # 快路径现在把本轮锚点传进 resolve_market_technical(as_of=...)。
        # 对账仍留下作兜底：窗口不足等残余情形会继续算最新一根，必须当场声明，
        # 不得再静默以 completed 交付错日期。锚点对得上时不应再触发。
        anchor = (self._latest_data_date or "").strip()
        caliber_warnings: tuple[str, ...] = ()
        if status == "completed" and anchor and fast_as_of and fast_as_of != anchor:
            status = "degraded"
            caliber_warnings = (
                f"技术位按 {fast_as_of} 的日线计算，但本轮口径基准是 {anchor}；"
                "该确定性旁路取的是最新行情、不支持指定历史日期，结论不适用于基准日。",
            )
            answer = (
                f"（口径提示：以下结论按 {fast_as_of} 计算，非基准日 {anchor}。）{answer}"
            )
        return ContinuousTurnResult(
            handled=True,
            status=status,
            answer=answer,
            as_of=fast_as_of,
            citations=(),
            warnings=(
                caliber_warnings
                if caliber_warnings
                else (
                    ()
                    if status == "completed"
                    else ("结构化行情不足，技术位结论已按数据边界降级。",)
                )
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
            events=self._terminal_events(status=status, deterministic=True),
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
        repair_attempts = 0
        backfill_turns = 0
        delivery_repair_attempted = False
        semantic_verifier_stale = False
        attempts_before = _ledger_attempt_count()
        phase_recorder = PhaseRecorder()
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
            # 视角约束只在激活时进 kwargs：neutral 的 context 构造调用保持
            # 逐字节不变，不认识该参数的注入式 factory 也不会在中立轮炸掉。
            perspective_context = str(
                getattr(control, "perspective_context", "") or ""
            )
            if perspective_context:
                context_kwargs["perspective_context"] = perspective_context
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
            # 事前可满足性预检：这套授权工具的 produces 并集能否覆盖每项
            # required_output。**只观测，不参与任何决策**——`check_satisfiability`
            # 自身是 fail-open 的（三态全部放行），这里同样只把结果写进私有
            # artifact，供事后统计 `suspicious` 的真实命中率。
            #
            # 为什么要这一步：契约门是事后判缺，跑完才知道填不上；而误判的
            # required_output（例如把「哪只个股比较有机会」读成对比题而追加
            # comparison_dimensions）在开跑前就已经注定无人能填。预检把这个
            # 信号提到花预算之前，但**先不据此拦人**：produces 表是人手维护的，
            # 让一张不完整的声明表拥有拦截权，就是造一个新的静默失败源。
            satisfiability = _precheck_satisfiability(registry, context)
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
            self._publish_progress(
                key="adapter:verification",
                stage="verification",
                message="正在核验证据绑定与回答完整性。",
                status="running",
            )
            structural_candidate = self._structural_verifier(
                context.contract,
                outcome,
            )
            if not isinstance(structural_candidate, VerifiedEpisodeOutcome):
                raise TypeError(
                    "structural verifier must return VerifiedEpisodeOutcome"
                )
            structural = _with_track_contract_gaps(structural_candidate, context)
            _phase_ingest(
                phase_recorder,
                context=context,
                outcome=outcome,
                repair_attempts=repair_attempts,
            )
            if phase_recorder.current_phase in {None, "planning"}:
                _phase_note(
                    phase_recorder,
                    "research",
                    trigger="episode_returned",
                    reason_code="episode_returned",
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
            _phase_note(
                phase_recorder,
                "structural_verify",
                trigger="structural_verifier",
                reason_code="structural_verify",
                context=context,
                outcome=outcome,
                repair_attempts=repair_attempts,
            )
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
            backfill_plan = _issue_backfill_plan(structural)
            if (
                session is not None
                and backfill_plan is not None
                and not self._is_cancelled()
                and not root_deadline.expired
            ):
                backfill_turns = 1
                _phase_note(
                    phase_recorder,
                    "repair",
                    trigger="resume_for_backfill",
                    reason_code="backfill",
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
                backfilled = self._resume_for_backfill(
                    session=session,
                    context=context,
                    delivery_deadline=root_deadline,
                    outcome=outcome,
                    structural=structural,
                    previous_snapshot=previous_snapshot,
                    current_snapshot=current_snapshot,
                    plan=backfill_plan,
                )
                if backfilled is not None:
                    previous_snapshot = current_snapshot
                    outcome, structural = backfilled
                    current_snapshot = _repair_snapshot(
                        outcome,
                        structural,
                        context,
                        ledger=episode_evidence_ledger,
                    )
                    _phase_ingest(
                        phase_recorder,
                        context=context,
                        outcome=outcome,
                        repair_attempts=repair_attempts,
                    )
                    _phase_note(
                        phase_recorder,
                        "structural_verify",
                        trigger="structural_verifier",
                        reason_code="structural_recheck",
                        context=context,
                        outcome=outcome,
                        repair_attempts=repair_attempts,
                    )
            while (
                session is not None
                and structural.missing_outputs
                and repair_attempts < max_repair_cycles
                and not repair_terminal
                and not self._is_cancelled()
                and not root_deadline.expired
            ):
                repair_attempts += 1
                _phase_note(
                    phase_recorder,
                    "repair",
                    trigger="resume_for_gap",
                    reason_code="structural_gap",
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
                repaired = self._resume_for_gap(
                    session=session,
                    context=context,
                    delivery_deadline=root_deadline,
                    outcome=outcome,
                    structural=structural,
                    previous_snapshot=previous_snapshot,
                    current_snapshot=current_snapshot,
                    cycle=repair_attempts,
                    rejected_claims=(),
                    allow_delivery_repair=not delivery_repair_attempted,
                )
                if repaired is None:
                    repair_attempts -= 1
                    break
                previous_snapshot = current_snapshot
                outcome, structural, delivery_only = repaired
                structural = _with_track_contract_gaps(structural, context)
                delivery_repair_attempted = (
                    delivery_repair_attempted or delivery_only
                )
                current_snapshot = _repair_snapshot(
                    outcome,
                    structural,
                    context,
                    ledger=episode_evidence_ledger,
                )
                repair_terminal = (
                    outcome.stop_reason in _TERMINAL_REPAIR_STOP_REASONS
                )
                if outcome.stop_reason in _SUCCESSFUL_REPAIR_STOP_REASONS:
                    repair_cycles += 1
                _phase_ingest(
                    phase_recorder,
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
                _phase_note(
                    phase_recorder,
                    "structural_verify",
                    trigger="structural_verifier",
                    reason_code="structural_recheck",
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
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
            semantic = replace(
                semantic_candidate,
                verified=_with_track_contract_gaps(
                    semantic_candidate.verified, context
                ),
            )
            _phase_note(
                phase_recorder,
                "semantic_verify",
                trigger="semantic_verifier",
                reason_code=str(semantic.judge_status or "semantic_verify"),
                context=context,
                outcome=outcome,
                repair_attempts=repair_attempts,
            )
            while (
                session is not None
                and (
                    semantic.gap_output_ids
                    or semantic.rejected_claim_indexes
                    or semantic.verified.missing_outputs
                )
                and repair_attempts < max_repair_cycles
                and not repair_terminal
                and not self._is_cancelled()
                and not root_deadline.expired
            ):
                repair_attempts += 1
                _phase_note(
                    phase_recorder,
                    "repair",
                    trigger="resume_for_gap",
                    reason_code="semantic_gap",
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
                repaired = self._resume_for_gap(
                    session=session,
                    context=context,
                    delivery_deadline=root_deadline,
                    outcome=outcome,
                    structural=semantic.verified,
                    previous_snapshot=previous_snapshot,
                    current_snapshot=current_snapshot,
                    cycle=repair_attempts,
                    rejected_claims=tuple(
                        f"claim_index:{index}"
                        for index in semantic.rejected_claim_indexes
                    ),
                    semantic_gap_outputs=semantic.gap_output_ids,
                    allow_delivery_repair=not delivery_repair_attempted,
                )
                if repaired is None:
                    repair_attempts -= 1
                    break
                previous_snapshot = current_snapshot
                outcome, structural, delivery_only = repaired
                structural = _with_track_contract_gaps(structural, context)
                delivery_repair_attempted = (
                    delivery_repair_attempted or delivery_only
                )
                current_snapshot = _repair_snapshot(
                    outcome,
                    structural,
                    context,
                    ledger=episode_evidence_ledger,
                )
                repair_terminal = (
                    outcome.stop_reason in _TERMINAL_REPAIR_STOP_REASONS
                )
                if outcome.stop_reason in _SUCCESSFUL_REPAIR_STOP_REASONS:
                    repair_cycles += 1
                _phase_ingest(
                    phase_recorder,
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
                _phase_note(
                    phase_recorder,
                    "structural_verify",
                    trigger="structural_verifier",
                    reason_code="structural_recheck",
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
                if (
                    repair_terminal
                    or self._is_cancelled()
                    or root_deadline.expired
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
                semantic = replace(
                    semantic_candidate,
                    verified=_with_track_contract_gaps(
                        semantic_candidate.verified, context
                    ),
                )
                _phase_note(
                    phase_recorder,
                    "semantic_verify",
                    trigger="semantic_verifier",
                    reason_code=str(semantic.judge_status or "semantic_verify"),
                    context=context,
                    outcome=outcome,
                    repair_attempts=repair_attempts,
                )
            if self._is_cancelled():
                return _cancelled_result()
            self._publish_progress(
                key="adapter:finalizing",
                stage="finalizing",
                message="核验已完成，正在生成可公开回答。",
                status="running",
            )
        except Exception as exc:
            partial_artifact: dict[str, object] = {
                "schema_version": 1,
                "execution_kind": "continuous_episode",
                "runtime_backend": self._runtime_name,
                "research_context": (
                    _episode_context_provenance(context)
                    if context is not None
                    else None
                ),
                "repair_attempts": repair_attempts,
                "repair_cycles": repair_cycles,
                "backfill_turns": backfill_turns,
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
            _phase_ingest(
                phase_recorder,
                context=context,
                outcome=outcome,
                repair_attempts=repair_attempts,
            )
            degraded_delivery = bool(
                outcome is not None and outcome.evidence and context is not None
            )
            _phase_note(
                phase_recorder,
                "degraded" if degraded_delivery else "failed",
                trigger="public_outcome",
                reason_code=type(exc).__name__,
                context=context,
                outcome=outcome,
                repair_attempts=repair_attempts,
            )
            partial_artifact["phase_trace"] = _phase_trace_payload(phase_recorder)
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
                    answer=_with_calendar_disclosure(
                        _verification_failure_gap_answer(
                            frame,
                            context,
                            trusted_structural,
                        ),
                        frame,
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
                    events=self._terminal_events(status="degraded"),
                    open_gaps=_open_gap_labels(
                        context.contract,
                        fulfilled_output_ids=fulfilled_output_ids,
                    ),
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
                events=self._terminal_events(status="failed"),
            )
        finally:
            # 会话生命周期在此收口（spec §7.3）：无论早退（取消）、异常还是
            # 成功落穿，session 离开本方法后不会再被 resume——不关闭它，
            # RuntimeHandle 的收据就永远停在 running，「close 后不得发布」
            # 也无从谈起。放 finally 而不是各出口各写一遍，是让「没有一条
            # 出口漏关」成为结构事实而不是纪律要求。
            close_session = getattr(session, "close", None)
            if callable(close_session):
                try:
                    close_session()
                except Exception:
                    # close 是收尾观测，不改写主路径：finally 里抛出会顶替
                    # 真正的返回值或异常（与 EpisodeScope.emit 同一条原则）。
                    pass

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
        _phase_note(
            phase_recorder,
            status,
            trigger="public_outcome",
            reason_code=status,
            context=context,
            outcome=outcome,
            repair_attempts=repair_attempts,
        )
        if not answer and final_outcome.evidence:
            answer = _episode_gap_answer(frame, structural)
        answer = _with_calendar_disclosure(answer, frame)
        semantic_verifier_stale = semantic_verifier_stale or (
            semantic.verified.outcome.events != outcome.events
        )
        # 事件数组走唯一投影口径（services 层 ``project_durable_events``）：五个下游
        # 读的就是这个数组，形状与此前逐字段一致，多出来的只有「只投 Durable」这条
        # 被钉住的不变量。异常（Live 漏进来 / kind 未登记）不静默，见下面那行。
        event_projection = project_durable_events(outcome.events)
        artifact = {
            "schema_version": 1,
            "execution_kind": "continuous_episode",
            "runtime_backend": self._runtime_name,
            "research_context": _episode_context_provenance(context),
            "contract": context.contract.to_dict(),
            "outcome": _private_outcome(outcome),
            "events": list(event_projection.events),
            "traces": [item.to_dict() for item in outcome.traces],
            "structural_verifier": structural.to_dict(),
            "satisfiability_precheck": _satisfiability_payload(satisfiability),
            "semantic_verifier": semantic.to_dict(),
            "semantic_verifier_stale": semantic_verifier_stale,
            "repair_attempts": repair_attempts,
            "repair_cycles": repair_cycles,
            "backfill_turns": backfill_turns,
            "track_contract": contract_receipt(
                outcome.draft,
                query=context.contract.question,
                question_type=context.contract.question_type,
                as_of=context.today,
            ),
            "metrics": _episode_metrics(
                outcome,
                attempts_before=attempts_before,
                structural_status=structural.verified_status,
                semantic_status=semantic.judge_status,
            ),
        }
        if event_projection.has_anomalies:
            # 只在真有异常时才出现这个键：常态下 artifact 形状一字不变，出问题时
            # 它自己会说出来（Live 漏进 durable 流 / 有 kind 没在车道表里登记）。
            artifact["events_projection_anomalies"] = (
                event_projection.anomalies_to_dict()
            )
        artifact["phase_trace"] = _phase_trace_payload(phase_recorder)
        if semantic.judge_status == "unavailable":
            artifact["pending_rejudge"] = True
            try:
                append_pending_from_artifact(artifact)
            except Exception:
                pass
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
            events=self._terminal_events(status=status),
            llm_provider=_episode_llm_provider(
                outcome,
                runtime_name=self._runtime_name,
            ),
            open_gaps=_open_gap_labels(
                context.contract,
                fulfilled_output_ids=fulfilled_output_ids,
            ),
        )

    def _resume_for_gap(
        self,
        *,
        session: object,
        context: ResearchRunContext,
        delivery_deadline: ResearchDeadline,
        outcome: AgentOutcome,
        structural: VerifiedEpisodeOutcome,
        previous_snapshot: EvidenceLedgerSnapshot,
        current_snapshot: EvidenceLedgerSnapshot,
        cycle: int,
        rejected_claims: tuple[str, ...],
        semantic_gap_outputs: tuple[str, ...] = (),
        allow_delivery_repair: bool = True,
    ) -> tuple[AgentOutcome, VerifiedEpisodeOutcome, bool] | None:
        root_budget = context.root_budget
        resume = getattr(session, "resume", None)
        episode_id = str(getattr(session, "episode_id", "") or "").strip()
        if root_budget is None or not callable(resume) or not episode_id:
            return None
        progress = progress_from_ledger(previous_snapshot, current_snapshot)
        tools_open = (
            not context.deadline.expired
            and context.deadline.stage_timeout(1.0) > 0.001
        )
        remaining_calls = max(
            0,
            int(root_budget.hard_calls_cap) - int(root_budget.allocated_calls),
        )
        remaining_seconds = min(
            max(
                0.0,
                float(root_budget.hard_seconds_cap)
                - float(root_budget.allocated_seconds),
            ),
            max(0.0, float(delivery_deadline.remaining())),
        )
        structural = _with_track_contract_gaps(structural, context)
        missing_outputs = tuple(
            dict.fromkeys((*structural.missing_outputs, *semantic_gap_outputs))
        )
        contract_rewrite_candidate = is_contract_rewrite_only(
            missing_outputs,
            rejected_claims=rejected_claims,
            semantic_gap_outputs=semantic_gap_outputs,
        )
        delivery_candidate = (
            allow_delivery_repair
            and outcome.stop_reason in _DELIVERY_REPAIR_STOP_REASONS
            and outcome.evidence
            and structural.missing_outputs
            and (not outcome.draft.strip() or not outcome.bindings)
        )
        # 饿死判据：零证据 + 终态是窗烧穿或主路径模型不可用。
        # 生产三种形状：R7-A3 查询烧穿窗口、R9-A3 规划轮吃光窗口零
        # trace、A1-R2 主路径 TimeoutError → model_unavailable。
        # 共同观察量是 stop_reason，不是 trace。
        cold_restart_candidate = (
            outcome.stop_reason in _COLD_RESTART_STOP_REASONS
            and not outcome.evidence
        )
        admission = admit_repair(
            episode_id=episode_id,
            missing_outputs=missing_outputs,
            missing_capabilities=structural.mandatory_missing_capabilities,
            rejected_claims=rejected_claims,
            attempted_actions=tuple(
                f"{trace.capability}:{trace.provider}" for trace in outcome.traces
            ),
            previous_progress=progress,
            remaining_calls=remaining_calls,
            remaining_seconds=remaining_seconds,
            cycle=cycle,
            root_budget=root_budget,
            research_tier=context.contract.research_tier,
            tools_open=tools_open,
            allow_delivery_repair=allow_delivery_repair,
            delivery_candidate=bool(delivery_candidate),
            contract_rewrite_candidate=contract_rewrite_candidate,
            cold_restart_candidate=cold_restart_candidate,
            evidence_count=len(outcome.evidence),
            seconds_cap=self._repair_seconds_cap,
        )
        if admission is None:
            return None
        candidate = resume(admission.goal)
        if not isinstance(candidate, AgentOutcome):
            raise TypeError("episode session resume must return AgentOutcome")
        # 修复不得倒退：修复轮死在 provider 上时，上一轮那份答案并没有因此失效。
        #
        # 下面那行 ``outcome, structural, _ = repaired`` 是无条件替换，所以一个空
        # 草稿的候选会把「partial 但有答案」变成「什么都没有」——2026-08-10 生产线
        # 四个 case 的 ``draft_chars=0`` 就是这么来的。``agent_episode`` 已在源头
        # 结转，但 ``openai_agents_runtime`` / ``codex_headless_runtime`` 各自还有
        # 一个 ``draft=""`` 的失败出口；这里是所有 runtime 的共同下游，放一道就够。
        #
        # 只补草稿与绑定，status/stop_reason/gaps 一律用候选的——失败必须留痕，
        # 不能因为保住了答案就把这一轮伪装成成功。
        if outcome.draft.strip() and not candidate.draft.strip():
            candidate = replace(
                candidate,
                draft=outcome.draft,
                bindings=candidate.bindings or outcome.bindings,
            )
        verified = self._structural_verifier(context.contract, candidate)
        if not isinstance(verified, VerifiedEpisodeOutcome):
            raise TypeError("structural verifier must return VerifiedEpisodeOutcome")
        return candidate, verified, admission.delivery_only

    def _resume_for_backfill(
        self,
        *,
        session: object,
        context: ResearchRunContext,
        delivery_deadline: ResearchDeadline,
        outcome: AgentOutcome,
        structural: VerifiedEpisodeOutcome,
        previous_snapshot: EvidenceLedgerSnapshot,
        current_snapshot: EvidenceLedgerSnapshot,
        plan: object,
    ) -> tuple[AgentOutcome, VerifiedEpisodeOutcome] | None:
        root_budget = context.root_budget
        resume = getattr(session, "resume", None)
        episode_id = str(getattr(session, "episode_id", "") or "").strip()
        if root_budget is None or not callable(resume) or not episode_id:
            return None
        missing_outputs = tuple(getattr(plan, "missing_outputs", ()) or ())
        missing_capabilities = tuple(getattr(plan, "missing_capabilities", ()) or ())
        if not missing_capabilities:
            return None
        tools_open = (
            not context.deadline.expired
            and context.deadline.stage_timeout(1.0) > 0.001
        )
        remaining_calls = max(
            0,
            int(root_budget.hard_calls_cap) - int(root_budget.allocated_calls),
        )
        remaining_seconds = min(
            max(
                0.0,
                float(root_budget.hard_seconds_cap)
                - float(root_budget.allocated_seconds),
            ),
            max(0.0, float(delivery_deadline.remaining())),
        )
        admission = admit_backfill_repair(
            episode_id=episode_id,
            missing_outputs=missing_outputs,
            missing_capabilities=missing_capabilities,
            attempted_actions=tuple(
                f"{trace.capability}:{trace.provider}" for trace in outcome.traces
            ),
            previous_progress=progress_from_ledger(
                previous_snapshot, current_snapshot
            ),
            remaining_calls=remaining_calls,
            remaining_seconds=remaining_seconds,
            cycle=1,
            root_budget=root_budget,
            tools_open=tools_open,
            seconds_cap=self._repair_seconds_cap,
        )
        if admission is None or not admission.backfill:
            return None
        candidate = resume(admission.goal)
        if not isinstance(candidate, AgentOutcome):
            raise TypeError("episode session resume must return AgentOutcome")
        if outcome.draft.strip() and not candidate.draft.strip():
            candidate = replace(
                candidate,
                draft=outcome.draft,
                bindings=candidate.bindings or outcome.bindings,
            )
        if draft_sentence_count(candidate.draft) > draft_sentence_count(outcome.draft):
            return None
        verified = self._structural_verifier(context.contract, candidate)
        if not isinstance(verified, VerifiedEpisodeOutcome):
            raise TypeError("structural verifier must return VerifiedEpisodeOutcome")
        return candidate, verified


def _issue_backfill_plan(
    structural: VerifiedEpisodeOutcome,
):
    items = structural.issue_items
    if numeric_condition_unsupported(structural):
        items = (
            *items,
            Issue(
                IssueCode.NUMERIC_UNSUPPORTED,
                "numeric_condition",
                "unsupported numeric condition without bound evidence",
            ),
        )
    return plan_issue_backfill(items)


def _with_track_contract_gaps(
    structural: VerifiedEpisodeOutcome,
    context: ResearchRunContext,
) -> VerifiedEpisodeOutcome:
    """Merge track-contract expression gaps into missing_outputs only.

    Do not touch ``issues``: the #224 release gate matches issue prefixes.
    """
    merged = merge_track_missing_outputs(
        structural.missing_outputs,
        structural.outcome.draft,
        query=context.contract.question,
        question_type=context.contract.question_type,
    )
    if merged == structural.missing_outputs:
        return structural
    return replace(structural, missing_outputs=merged)


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


def _normalize_output_id(output_id: str) -> str:
    """按 orchestrator 的别名表归一 output_id——那是「output 归一」的唯一事实源。

    延迟 import：`conversation_orchestrator` 顶层已 import 本模块的
    `ContinuousTurnResult`，顶层反向 import 会成环。
    `test_tool_produces_satisfiability.py` 的对账测试用的是同一手法，
    并且明确禁止抄第二份表——抄一份就等于把那边的修改和这里的比对解耦。
    """

    from intelligence.runtime.conversation_orchestrator import (
        _LEGACY_OUTPUT_ALIASES,
    )

    return _LEGACY_OUTPUT_ALIASES.get(output_id, output_id)


def _precheck_satisfiability(
    registry: object,
    context: ResearchRunContext,
) -> tuple[SatisfiabilityCheck, ...]:
    """事前预检，拿不到工具声明就返回空——**registry 是鸭子类型注入点**。

    `registry_factory` 的既有替身有的直接返回字符串 `"registry"`（见
    `test_continuous_turn_adapter.py` 多处），因此这里不能假设 registry 一定
    实现了 `authorized_specs`。第一版实现直接调它，37 条既有测试立刻转红——
    与 `38c06356` 那次在 `ResearchDeadline` 上加方法踩的是同一个坑：
    **在鸭子类型注入点上新增依赖，必须对缺失接口 fail-open。**

    观测手段不允许改变任何执行结果，所以这里对任何异常都吞掉：预检失败的
    代价只是少一条诊断，而让它抛异常就等于让一个观测器有能力杀掉整轮回答。
    """

    accessor = getattr(registry, "authorized_specs", None)
    if not callable(accessor):
        return ()
    try:
        specs = accessor(context.contract.allowed_capabilities)
        return check_satisfiability(
            tuple(item.output_id for item in context.contract.required_outputs),
            specs,
            normalize=_normalize_output_id,
        )
    except Exception:  # noqa: BLE001 — 观测器不得影响执行结果
        return ()


def _satisfiability_payload(
    checks: tuple[SatisfiabilityCheck, ...],
) -> dict[str, object]:
    """把事前预检结果摊平成可统计的私有诊断载荷。

    单独留 `counts` 是为了让「`suspicious` 命中率」可以直接聚合，不必每次
    重新遍历 `checks`——决定这个预检该不该升级为拦截门，靠的就是这个比率。
    """

    counts: dict[str, int] = {"covered": 0, "unknown": 0, "suspicious": 0}
    for check in checks:
        if check.status in counts:
            counts[check.status] += 1
    return {
        "enforced": False,
        "counts": counts,
        "checks": [
            {
                "output_id": check.output_id,
                "status": check.status,
                "contributing_tools": list(check.contributing_tools),
                "reason": check.reason,
            }
            for check in checks
        ],
    }


def _episode_context_provenance(
    context: ResearchRunContext,
) -> dict[str, object]:
    """Persist the single cutoff/freshness context beside private diagnostics."""

    return {
        "information_cutoff": context.information_cutoff.to_dict(),
        "today": context.today,
        "latest_data_date": context.latest_data_date,
        "trace_parent_id": context.trace_parent_id,
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


def _with_calendar_disclosure(answer: str, frame: TaskFrame) -> str:
    return with_calendar_disclosure(answer, frame)


def _open_gap_labels(
    contract,
    *,
    fulfilled_output_ids: frozenset[str],
    limit: int = 3,
) -> tuple[str, ...]:
    """未满足必需输出的描述文案——与公开缺口声明同一套口径。

    只取契约里 ``required`` 且描述非空的项；描述本来就会进公开答案
    （「仍需核验：…」），所以直接复用不需要再脱敏。
    """
    if contract is None:
        return ()
    return tuple(
        item.description.strip()
        for item in contract.required_outputs
        if item.required
        and item.output_id not in fulfilled_output_ids
        and item.description.strip()
    )[:limit]


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


def _phase_note(
    recorder: PhaseRecorder,
    to_phase: str,
    *,
    trigger: str,
    reason_code: str,
    context: ResearchRunContext | None,
    outcome: AgentOutcome | None,
    repair_attempts: int,
) -> None:
    """Observability only: a broken phase seam must not abort research."""

    try:
        root = getattr(context, "root_budget", None) if context is not None else None
        recorder.record(
            to_phase,
            trigger=trigger,
            reason_code=reason_code,
            remaining_calls=int(root.remaining_calls) if root is not None else None,
            remaining_seconds=(
                float(root.remaining_seconds) if root is not None else None
            ),
            evidence_count=len(outcome.evidence) if outcome is not None else 0,
            repair_attempts=repair_attempts,
        )
    except Exception:
        return


def _phase_ingest(
    recorder: PhaseRecorder,
    *,
    context: ResearchRunContext | None,
    outcome: AgentOutcome | None,
    repair_attempts: int,
) -> None:
    if outcome is None:
        return
    try:
        root = getattr(context, "root_budget", None) if context is not None else None
        recorder.ingest_events(
            outcome.events,
            remaining_calls=int(root.remaining_calls) if root is not None else None,
            remaining_seconds=(
                float(root.remaining_seconds) if root is not None else None
            ),
            evidence_count=len(outcome.evidence),
            repair_attempts=repair_attempts,
        )
    except Exception:
        return


def _phase_trace_payload(recorder: PhaseRecorder) -> dict[str, object]:
    try:
        return recorder.trace().to_dict()
    except Exception:
        return {
            "transitions": [],
            "anomalies": {"recorder_failed": ["1"]},
        }


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
    "DETERMINISTIC_OWNER_TYPES",
    "RuntimeMode",
    "SemanticVerifier",
]
