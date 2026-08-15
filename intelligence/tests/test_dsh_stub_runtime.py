"""第 7 步：scripted dsh stub 验证 Adapter 窄协议。

不连真实 dsh，不跑 A/B。验的是：ResumableAgentRuntime、网关带上
EpisodeScope、tool_call_id 成对、协议收据无私有路径、Handle 门挡住
close/cancel 之后的 resume。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from intelligence.runtime.agent_runtime_factory import resolve_runtime_backend
from intelligence.runtime.dsh_stub_runtime import (
    ADAPTER_PROTOCOL_KEYS,
    DSH_AB_RELAY_KEY_ENV,
    DshAdapterProtocolError,
    DshStubRuntime,
    PINNED_DSH_COMMIT,
    ScriptedDshAction,
    form_step8_decision,
    probe_dsh_checkout,
    relay_key_fingerprint,
)
from intelligence.runtime.headless_tool_gateway import HeadlessToolGateway
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import AgentOutcome, ResumableAgentRuntime
from intelligence.services.episode_event_lanes import DURABLE_EVENT_KINDS, lane_for
from intelligence.services.episode_projection import project_durable_events
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.episode_session import EpisodeSessionError
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_profile import RUNTIME_BACKEND_NAMES
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(
    frame: TaskFrame,
    *,
    allowed_capabilities: tuple[str, ...] = ("market_data",),
) -> ResearchRunContext:
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id="dsh-stub-test",
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    ("market_data",),
                    True,
                ),
            ),
            allowed_capabilities=allowed_capabilities,
            research_tier="quick",
            freshness="current",
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", 3, 30.0, 0.0),
        trace_parent_id="dsh-stub-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry(calls: list[tuple[str, str]] | None = None) -> ResearchToolRegistry:
    recorded = calls if calls is not None else []

    def market_runner(query: str, _context: AgentToolContext):
        recorded.append(("market_data", query))
        evidence = AgentEvidence(
            tool="market_data",
            title="A股市场总览",
            detail=f"{query}：上涨家数增加",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="market-hash",
            internal_locator="/tmp/secret-locator",
        )
        return (
            [evidence],
            "上涨家数增加",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=market_runner,
                query_scope="episode",
            ),
        )
    )


def _script() -> tuple[ScriptedDshAction, ...]:
    return (
        ScriptedDshAction(
            kind="tool_call",
            tool="market_data",
            query="最近交易日市场宽度",
        ),
        ScriptedDshAction(kind="finish", draft="宽度改善，但还缺资金面反证。"),
    )


def _repair_goal(episode_id: str) -> RepairGoal:
    return RepairGoal(
        episode_id=episode_id,
        repair_goal_id="repair-dsh-stub-1",
        cycle=1,
        missing_answer_elements=("direct_assessment",),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=(),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=1,
        remaining_seconds=8.0,
    )


def test_stub_conforms_to_resumable_runtime_contract() -> None:
    runtime = DshStubRuntime(_script())
    assert isinstance(runtime, ResumableAgentRuntime)


def test_factory_does_not_register_dsh_stub_this_round() -> None:
    assert "dsh_stub" not in RUNTIME_BACKEND_NAMES
    with pytest.raises(RuntimeError, match="unsupported agent runtime backend"):
        resolve_runtime_backend("dsh_stub")


def test_start_plays_scripted_tool_call_over_gateway_http() -> None:
    calls: list[tuple[str, str]] = []
    frame = _frame()
    context = _context(frame)
    runtime = DshStubRuntime(_script())

    session = runtime.start(frame, context=context, registry=_registry(calls))
    try:
        outcome = session.outcome
        handle = session.runtime_handle
        assert handle is not None
        receipt = handle.dump()
        protocol = runtime.last_protocol
    finally:
        session.close()

    assert calls == [("market_data", "最近交易日市场宽度")]
    assert outcome.status == "completed"
    assert outcome.evidence[0].content_hash == "market-hash"
    assert outcome.usage.tool_calls == 1
    assert receipt["scope_attached"] is True
    assert receipt["scope"]["invoked_tools"] == ["market_data"]
    assert set(protocol) == set(ADAPTER_PROTOCOL_KEYS)
    json.dumps(protocol, ensure_ascii=False)


def test_protocol_pairs_one_tool_call_id_and_strips_private_fields() -> None:
    frame = _frame()
    runtime = DshStubRuntime(_script())
    session = runtime.start(frame, context=_context(frame), registry=_registry())
    try:
        protocol = runtime.last_protocol
        outcome = session.outcome
    finally:
        session.close()

    calls = protocol["tool_calls"]
    results = protocol["tool_results"]
    assert isinstance(calls, list) and isinstance(results, list)
    assert len(calls) == 1
    assert len(results) == 1
    assert calls[0]["tool_call_id"] == results[0]["tool_call_id"]
    assert calls[0]["tool_call_id"]
    kinds = [event.kind for event in outcome.events]
    assert all(lane_for(kind) == "durable" for kind in kinds)
    assert set(kinds) <= DURABLE_EVENT_KINDS
    assert not project_durable_events(outcome.events).has_anomalies
    public_evidence = protocol["final_outcome"]["evidence"]
    assert isinstance(public_evidence, list)
    assert "internal_locator" not in public_evidence[0]
    assert "internal_locator" not in outcome.to_dict()["evidence"][0]


def test_protocol_rejects_a_private_path_if_someone_adds_one() -> None:
    from intelligence.runtime.dsh_stub_runtime import _scan_private_leak

    with pytest.raises(DshAdapterProtocolError, match="duckdb"):
        _scan_private_leak(
            {"task_frame": {"db": "warehouse.duckdb"}},
            path="adapter_protocol",
        )


def test_gateway_without_scope_stays_unattached() -> None:
    frame = _frame()
    context = _context(frame)
    with HeadlessToolGateway(registry=_registry(), context=context) as gateway:
        assert gateway.scope_attached is False
        result = gateway.call("market_data", "最近交易日市场宽度")
    assert result["status"] == "success"


def test_gateway_rejects_a_scope_from_another_episode() -> None:
    frame = _frame()
    context = _context(frame)
    foreign = EpisodeScope(
        episode_id="someone-else",
        user_id="",
        context=context,
        registry=_registry(),
    )
    with pytest.raises(ValueError, match="episode_id mismatch"):
        HeadlessToolGateway(registry=_registry(), context=context, scope=foreign)


def test_gateway_scope_can_deny_a_contract_authorized_tool() -> None:
    frame = _frame()
    context = _context(frame)
    narrow = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=context.contract.task_id,
            question=context.contract.question,
            subject=context.contract.subject,
            subject_kind=context.contract.subject_kind,
            question_type=context.contract.question_type,
            required_outputs=context.contract.required_outputs,
            allowed_capabilities=(),
            research_tier="quick",
            freshness="current",
            evidence_plan=EvidencePlan(),
            task_frame_hash=context.contract.task_frame_hash,
        ),
        deadline=context.deadline,
        policy=context.policy,
        trace_parent_id=context.trace_parent_id,
        today=context.today,
        latest_data_date=context.latest_data_date,
    )
    scope = EpisodeScope(
        episode_id=context.contract.task_id,
        user_id="",
        context=narrow,
        registry=_registry(),
    )
    with HeadlessToolGateway(
        registry=_registry(),
        context=context,
        scope=scope,
    ) as gateway:
        result = gateway.call("market_data", "最近交易日市场宽度")
    assert result["status"] == "rejected"
    assert result["error"] == "unknown_or_unauthorized_tool"
    assert "market_data" not in scope.invoked_tools


def test_resume_keeps_event_prefix_and_adds_model_turn() -> None:
    frame = _frame()
    runtime = DshStubRuntime(_script())
    session = runtime.start(frame, context=_context(frame), registry=_registry())
    try:
        previous = session.outcome
        updated = session.resume(_repair_goal(session.episode_id))
        assert updated.events[: len(previous.events)] == previous.events
        assert updated.events[-1].kind == "model_turn"
        assert updated.stop_reason == "repair_reentry"
    finally:
        session.close()


def test_close_blocks_resume() -> None:
    frame = _frame()
    runtime = DshStubRuntime(_script())
    session = runtime.start(frame, context=_context(frame), registry=_registry())
    session.close()
    with pytest.raises(EpisodeSessionError, match="already closed"):
        session.resume(_repair_goal(session.episode_id))


def test_cancel_blocks_a_new_resume() -> None:
    frame = _frame()
    runtime = DshStubRuntime(_script())
    session = runtime.start(frame, context=_context(frame), registry=_registry())
    try:
        assert session.runtime_handle is not None
        session.runtime_handle.request_cancel("user_cancel")
        with pytest.raises(EpisodeSessionError, match="已请求取消"):
            session.resume(_repair_goal(session.episode_id))
    finally:
        session.close()


def test_cancelled_stub_does_not_touch_the_registry() -> None:
    calls: list[tuple[str, str]] = []
    frame = _frame()
    runtime = DshStubRuntime(_script(), is_cancelled=lambda: True)
    outcome = runtime.run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(calls),
    )
    assert calls == []
    assert outcome.status == "failed"
    assert outcome.stop_reason == "cancelled"
    assert outcome.evidence == ()


def test_run_closes_the_handle() -> None:
    frame = _frame()
    runtime = DshStubRuntime(_script())
    outcome = runtime.run(task_frame=frame, context=_context(frame), registry=_registry())
    assert isinstance(outcome, AgentOutcome)
    assert outcome.status == "completed"
    assert runtime.last_protocol["final_outcome"]["draft"] == (
        "宽度改善，但还缺资金面反证。"
    )


def test_injected_tool_failure_stays_structured() -> None:
    calls: list[tuple[str, str]] = []

    def boom(query: str, _context: AgentToolContext) -> tuple:
        calls.append(("market_data", query))
        raise RuntimeError("injected boom")

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=boom,
                query_scope="episode",
            ),
        )
    )
    frame = _frame()
    runtime = DshStubRuntime(_script())
    outcome = runtime.run(
        task_frame=frame,
        context=_context(frame),
        registry=registry,
    )
    assert calls == [("market_data", "最近交易日市场宽度")]
    assert outcome.status == "failed"
    assert outcome.stop_reason == "tool_exception"
    assert outcome.evidence == ()
    assert outcome.draft == ""
    errors = [event for event in outcome.events if event.kind == "tool_error"]
    assert len(errors) == 1
    assert errors[0].payload["error"] == "tool_exception"
    assert not project_durable_events(outcome.events).has_anomalies


def test_relay_key_fingerprint_does_not_echo_secret() -> None:
    secret = "relay-secret-for-fingerprint-only"
    digest = relay_key_fingerprint(secret)
    assert digest != secret
    assert secret not in digest
    assert len(digest) == 16
    assert relay_key_fingerprint(secret) == digest


def test_checkout_probe_missing_and_not_git(tmp_path: Path) -> None:
    missing = probe_dsh_checkout(source_index="")
    assert missing["status"] == "missing"
    assert missing["matches_pin"] is False
    assert missing["pinned"] == PINNED_DSH_COMMIT
    empty = probe_dsh_checkout(source_index=str(tmp_path))
    assert empty["status"] == "not_git"
    assert empty["matches_pin"] is False


def test_checkout_probe_matches_and_mismatches_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "index"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@example.com",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-m",
            "pin",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(
        "intelligence.runtime.dsh_stub_runtime.PINNED_DSH_COMMIT",
        head,
    )
    probed = probe_dsh_checkout(source_index=str(repo))
    assert probed["status"] == "ok"
    assert probed["head"] == head
    assert probed["matches_pin"] is True
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init"], cwd=other, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "--allow-empty", "-m", "other"],
        cwd=other,
        check=True,
        capture_output=True,
    )
    other_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=other,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if other_head == head:
        pytest.skip("two empty commits hashed to the same revision")
    mismatched = probe_dsh_checkout(source_index=str(other))
    assert mismatched["matches_pin"] is False


def test_step8_decision_defaults_to_not_retain() -> None:
    decision = form_step8_decision(protocol_ok=True, live_ab_ran=False)
    assert decision["retain_dsh_runtime"] is False
    assert decision["reason"] == "live_ab_not_run"
    assert "--keychain-user" in decision["forbidden_copy"]
    assert "localhost:57244" in decision["forbidden_copy"]
    assert "gpt-5.6-sol" in decision["forbidden_copy"]
    assert decision["credential_env"] == DSH_AB_RELAY_KEY_ENV
    assert decision["pinned_commit"] == PINNED_DSH_COMMIT


def test_step8_decision_retains_only_with_protocol_live_ab_and_benefit() -> None:
    assert form_step8_decision(
        protocol_ok=True, live_ab_ran=True, net_benefit=False
    )["retain_dsh_runtime"] is False
    assert form_step8_decision(
        protocol_ok=False, live_ab_ran=True, net_benefit=True
    )["retain_dsh_runtime"] is False
    kept = form_step8_decision(
        protocol_ok=True, live_ab_ran=True, net_benefit=True
    )
    assert kept["retain_dsh_runtime"] is True
    assert kept["reason"] == "live_ab_showed_net_benefit"
