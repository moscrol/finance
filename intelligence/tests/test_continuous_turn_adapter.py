from __future__ import annotations

from intelligence.services import ask_synthesis
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.episode_verifier import (
    VerifiedEpisodeOutcome,
    verify_episode_outcome,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_control_core import TurnControlResult


def _frame(
    *,
    question_type: str = "market_forecast",
    required_outputs: tuple[str, ...] = ("direct_assessment",),
    clarification_question: str | None = None,
) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type=question_type,
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=required_outputs,
        assumptions=(),
        ambiguities=(),
        clarification_question=clarification_question,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _control(
    frame: TaskFrame,
    *,
    terminal_kind: str = "research",
    capabilities: tuple[str, ...] = ("market_data",),
    clarification_questions: tuple[str, ...] = (),
) -> TurnControlResult:
    return TurnControlResult(
        task_frame=frame,
        execution_route=(
            "clarify" if terminal_kind == "clarification" else frame.question_type
        ),
        terminal_kind=terminal_kind,  # type: ignore[arg-type]
        needs_retrieval=terminal_kind == "research",
        capabilities=capabilities,
        contract_required=terminal_kind == "research",
        clarification_questions=clarification_questions,
    )


class _RuntimeThatRaises:
    def run(self, **_kwargs):
        raise AssertionError("disabled adapter must not call runtime")


def _raises(*_args, **_kwargs):
    raise AssertionError("dependency must not be called")


def _scripted_episode_result(
    *,
    semantic_status: str,
    public_answer: str,
    evidence: tuple[AgentEvidence, ...],
    bindings: tuple[OutputEvidenceBinding, ...],
    outcome_status: str = "completed",
    draft: str = "当前更接近条件化修复。",
    traces: tuple[ProviderTrace, ...] = (),
):
    frame = _frame()
    capabilities = tuple(dict.fromkeys(item.tool for item in evidence)) or (
        "market_data",
    )
    control = _control(frame, capabilities=capabilities)
    context = build_episode_context(
        frame,
        task_id="adapter-scripted",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status=outcome_status,  # type: ignore[arg-type]
        draft=draft,
        evidence=evidence,
        traces=traces,
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=bindings,
        usage=AgentUsage(llm_calls=1, tool_calls=len(evidence)),
    )

    class Runtime:
        def run(self, **_kwargs):
            return outcome

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status=semantic_status,  # type: ignore[arg-type]
                public_answer=public_answer,
                judge_status=(
                    "passed" if semantic_status == "completed" else "rejected"
                ),
            )

    return ContinuousTurnAdapter(
        runtime=Runtime(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        semantic_verifier=Semantic(),
    ).handle(frame=frame, control=control)


def test_off_mode_always_declines_without_running_anything() -> None:
    frame = _frame()

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="off",
        context_factory=_raises,
        registry_factory=_raises,
        fast_path_runner=_raises,
        structural_verifier=_raises,
        semantic_verifier=_raises,
    ).handle(frame=frame, control=_control(frame))

    assert result.handled is False
    assert result.answer == ""
    assert result.private_artifact is None


def test_clarification_returns_without_registry_model_or_retrieval() -> None:
    frame = _frame(clarification_question="你希望按 A 股还是美股判断？")
    control = _control(
        frame,
        terminal_kind="clarification",
        capabilities=(),
        clarification_questions=("你希望按 A 股还是美股判断？",),
    )

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="on",
        context_factory=_raises,
        registry_factory=_raises,
        fast_path_runner=_raises,
        structural_verifier=_raises,
        semantic_verifier=_raises,
    ).handle(frame=frame, control=control)

    assert result.handled is True
    assert result.status == "completed"
    assert result.answer == "你希望按 A 股还是美股判断？"
    assert result.citations == ()


def test_market_technical_uses_zero_llm_fast_path() -> None:
    frame = _frame(
        question_type="market_technical",
        required_outputs=("technical_levels", "invalidation_conditions", "data_date"),
    )
    calls: list[str] = []

    def run_fast_path(_frame, *, timeout):
        del timeout
        calls.append("fast_path")
        assert _frame is frame
        return {
            "execution_kind": "deterministic_fast_path",
            "status": "completed",
            "answer": "截至 2026-07-22，科创50上方压力区为 1100~1120。",
            "as_of": "2026-07-22",
            "gaps": [],
            "traces": [
                {
                    "provider": "RAW_PROVIDER_SENTINEL",
                    "capability": "market_data",
                    "status": "success",
                    "source_trade_date": "2026-07-22",
                }
            ],
            "llm_calls": 0,
            "tool_calls": 1,
        }

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="on",
        context_factory=_raises,
        registry_factory=_raises,
        fast_path_runner=run_fast_path,
        structural_verifier=_raises,
        semantic_verifier=_raises,
    ).handle(frame=frame, control=_control(frame))

    assert calls == ["fast_path"]
    assert result.handled is True
    assert result.status == "completed"
    assert result.as_of == "2026-07-22"
    assert result.private_artifact is not None
    assert result.private_artifact["outcome"]["llm_calls"] == 0
    assert "RAW_PROVIDER_SENTINEL" not in str(result.events)


def test_market_technical_gap_hides_provider_diagnostic() -> None:
    frame = _frame(
        question_type="market_technical",
        required_outputs=("technical_levels", "invalidation_conditions", "data_date"),
    )

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="on",
        fast_path_runner=lambda *_args, **_kwargs: {
            "status": "partial",
            "answer": "缺口原因：provider_unsupported。",
            "llm_calls": 0,
            "tool_calls": 1,
            "traces": [],
        },
    ).handle(frame=frame, control=_control(frame))

    assert result.status == "degraded"
    assert "provider" not in result.answer.casefold()
    assert "暂不能可靠给出支撑位或压力位" in result.answer


def test_long_tail_runs_gates_without_calling_legacy_presenter(
    monkeypatch,
) -> None:
    frame = _frame()
    control = _control(frame)
    context = build_episode_context(
        frame,
        task_id="adapter-order",
        capabilities=control.capabilities,
        timeout=30.0,
    )
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加，成交保持活跃",
        source="本地行情",
        internal_locator="/private/market/window.json",
        source_date="2026-07-22",
        evidence_tier="L4",
        content_hash="PRIVATE_HASH_SENTINEL",
    )
    outcome = AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft="当前更接近条件化修复，持续性取决于量能。",
        evidence=(evidence,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": frame.task_frame_hash},
            ),
        ),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("PRIVATE_HASH_SENTINEL",)),
        ),
        usage=AgentUsage(llm_calls=2, tool_calls=1),
    )
    calls: list[str] = []
    presenter_calls: list[str] = []

    def legacy_presenter(*_args, **_kwargs):
        presenter_calls.append("legacy_presenter")
        raise AssertionError("Episode-owned answer must not enter legacy presenter")

    monkeypatch.setattr(
        ask_synthesis,
        "synthesize_prepared_answer",
        legacy_presenter,
    )

    class Runtime:
        def run(self, *, task_frame, context, registry):
            calls.append("runtime")
            assert task_frame is frame
            assert context is not None
            assert registry == "registry"
            return outcome

    def structural(contract, candidate):
        calls.append("structural")
        assert contract is context.contract
        assert candidate is outcome
        return verify_episode_outcome(contract, candidate)

    class Semantic:
        def verify(self, *, frame, structurally_verified, deadline):
            calls.append("semantic")
            assert frame is not None
            assert isinstance(structurally_verified, VerifiedEpisodeOutcome)
            assert deadline is context.deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer="当前更接近条件化修复，持续性取决于量能。",
                judge_status="passed",
            )

    result = ContinuousTurnAdapter(
        runtime=Runtime(),
        mode="on",
        context_factory=lambda *_args, **_kwargs: context,
        registry_factory=lambda *_args, **_kwargs: "registry",
        structural_verifier=structural,
        semantic_verifier=Semantic(),
    ).handle(frame=frame, control=control)

    assert calls == ["runtime", "structural", "semantic"]
    assert presenter_calls == []
    assert result.status == "completed"
    assert result.answer.startswith("当前更接近条件化修复")
    assert result.citations == (
        {
            "title": "A股市场总览",
            "source": "本地行情",
            "date": "2026-07-22",
        },
    )
    assert result.private_artifact is not None
    assert result.private_artifact["outcome"]["draft"].startswith("当前更接近")
    assert (
        result.private_artifact["outcome"]["evidence"][0]["internal_locator"]
        == "/private/market/window.json"
    )
    assert result.private_artifact["events"] == [
        {
            "sequence": 1,
            "kind": "task",
            "payload": {"task_frame_hash": frame.task_frame_hash},
        }
    ]
    assert result.private_artifact["traces"] == []
    assert "structural_verifier" in result.private_artifact
    assert "semantic_verifier" in result.private_artifact
    assert "PRIVATE_HASH_SENTINEL" not in str(result.events)


def test_valuation_contract_requires_current_anchor_scenarios_and_assumptions() -> None:
    frame = TaskFrame(
        raw_question="瑞华泰的合理估值是多少",
        user_goal="估算瑞华泰当前合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=(
            "valuation_assessment",
            "scenario_range",
            "evidence_boundary",
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_valuation_evidence",
        confidence=0.95,
    )
    control = _control(frame, capabilities=("evidence_lookup",))
    captured: dict[str, object] = {}

    class InspectingRuntime:
        def run(self, *, task_frame, context, registry):
            del task_frame, registry
            captured["contract"] = context.contract
            raise RuntimeError("stop after inspecting the contract")

    result = ContinuousTurnAdapter(
        runtime=InspectingRuntime(),
        mode="on",
        registry_factory=lambda *_args, **_kwargs: "registry",
    ).handle(frame=frame, control=control)

    assert result.status == "failed"
    contract = captured["contract"]
    outputs = {item.output_id: item.description for item in contract.required_outputs}
    assert {
        "valuation_assessment",
        "scenario_range",
        "evidence_boundary",
        "invalidation_conditions",
    }.issubset(outputs)
    assert "当前市场锚点" in outputs["valuation_assessment"]
    assert "方法" in outputs["valuation_assessment"]
    assert "假设" in outputs["valuation_assessment"]
    assert "market_data" in contract.allowed_capabilities
    assert "market_data" in contract.evidence_plan.mandatory_capabilities


def test_semantic_partial_returns_degraded_useful_gap() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="当前数据只覆盖最近交易日",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="market-gap-1",
    )

    result = _scripted_episode_result(
        semantic_status="partial",
        public_answer="现有证据只支持最近交易日，持续性仍需补量能验证。",
        evidence=(evidence,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-gap-1",)),),
    )

    assert result.status == "degraded"
    assert "持续性仍需补量能验证" in result.answer
    assert result.warnings == ("证据或语义核验未完全通过，已按证据边界降级。",)


def test_no_answer_and_no_evidence_returns_failed() -> None:
    result = _scripted_episode_result(
        semantic_status="failed",
        public_answer="",
        evidence=(),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                gap="仍缺最新市场证据",
            ),
        ),
        outcome_status="failed",
        draft="",
    )

    assert result.status == "failed"
    assert result.answer == ""
    assert result.citations == ()


def test_public_projection_hides_control_plane_fields_and_private_tokens() -> None:
    evidence = AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加",
        source="本地行情",
        source_date="2026-07-22",
        content_hash="PRIVATE_HASH_SENTINEL",
    )
    trace = ProviderTrace(
        provider="RAW_PROVIDER_SENTINEL",
        capability="market_data",
        status="success",
        result_count=1,
    )

    result = _scripted_episode_result(
        semantic_status="completed",
        public_answer=(
            "可公开结论。\n"
            "content_hash=PRIVATE_HASH_SENTINEL\n"
            "provider=RAW_PROVIDER_SENTINEL\n"
            "system_prompt=PRIVATE_PROMPT_SENTINEL\n"
            "market_data"
        ),
        evidence=(evidence,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("PRIVATE_HASH_SENTINEL",)),
        ),
        traces=(trace,),
        draft="api_key=sk-abcdefghijk",
    )

    public_payload = {
        "answer": result.answer,
        "citations": result.citations,
        "warnings": result.warnings,
        "events": result.events,
    }
    assert result.answer == "可公开结论。"
    for sentinel in (
        "PRIVATE_HASH_SENTINEL",
        "RAW_PROVIDER_SENTINEL",
        "PRIVATE_PROMPT_SENTINEL",
        "market_data",
    ):
        assert sentinel not in str(public_payload)
    assert result.private_artifact is not None
    assert "sk-abcdefghijk" not in str(result.private_artifact)
    assert "[REDACTED]" in str(result.private_artifact)


def test_canary_requires_isolated_runtime_identifier(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    monkeypatch.delenv("CONTINUOUS_RUNTIME_CANARY_ID", raising=False)
    frame = _frame()

    result = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="canary",
    ).handle(frame=frame, control=_control(frame))

    assert result.handled is False
    assert result.answer == ""


def test_canary_handles_only_with_matching_environment_and_identifier(
    monkeypatch,
) -> None:
    frame = _frame(clarification_question="请确认市场。")
    control = _control(
        frame,
        terminal_kind="clarification",
        capabilities=(),
        clarification_questions=("请确认市场。",),
    )
    monkeypatch.setenv("CONTINUOUS_RUNTIME_CANARY_ID", "candidate-sha")
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "off")

    mismatched = ContinuousTurnAdapter(
        runtime=_RuntimeThatRaises(),
        mode="canary",
    ).handle(frame=frame, control=control)

    assert mismatched.handled is False

    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    adapter = ContinuousTurnAdapter(runtime=_RuntimeThatRaises())
    handled = adapter.handle(frame=frame, control=control)

    assert adapter.mode == "canary"
    assert adapter.canary_id == "candidate-sha"
    assert handled.handled is True
    assert handled.answer == "请确认市场。"
