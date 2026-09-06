"""``sub_research`` 作为模型可点的工具（spec ``2026-09-03-subagent-tool-design.md`` §6 验收）。

抄 dsh ``tool-subagent`` 的形状、账本用我们的。每条断言对应 spec §6 的一条：
① 注册表守门（契约存在、参数面只有 goals、地板 = 一支分支的时间上限）；
② 深度 = 1（分支注册表与分支契约都不含 sub_research；嵌套 Episode 没有协调器就不绑）；
③ 证据绑定（父账本铸 hash、E 号进模型消息、finish 能绑分支证据）；
④ 预算（分支 deadline 收在本批工具窗内；不铸新账本）；
⑤ 菜单（standard 小窗藏、max 档可见）；
⑦ 空结果 / 拒绝语义（completed 零证据 = 缺口；refused = error 带原因）。
"""

from __future__ import annotations

import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_tool_batch import ToolBatchExecutor
from intelligence.runtime.sub_research import (
    MAX_SECONDS_PER_BRANCH,
    BranchResult,
    SubResearchCoordinator,
    SubResearchResult,
)
from intelligence.runtime.sub_research_tool import (
    SUB_RESEARCH_TOOL,
    bind_sub_research_tool,
    tool_result_from_branches,
)
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.research_contract import (
    InformationCutoff,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    root_budget_for_policy,
    release_root_budget,
)
from intelligence.services.research_tool_registry import (
    DEFAULT_RESEARCH_CAPABILITIES,
    MIN_WINDOW_SECONDS,
    SUB_RESEARCH_MIN_WINDOW_SECONDS,
    InvalidResearchToolArguments,
    ResearchToolRegistry,
    ToolSpec,
    default_registry,
    parse_sub_research_arguments,
    sub_research_tool_spec,
)

from intelligence.tests.test_agent_episode import (  # noqa: E402  复用既有脚本模型与夹具
    ScriptedModel,
    _finish_turn,
    _frame,
    _market_registry,
    _successful_runner,
)

from datetime import date
from uuid import uuid4


# ---------------------------------------------------------------------------
# ① 注册表守门
# ---------------------------------------------------------------------------


def test_sub_research_is_declared_with_contract_goals_schema_and_branch_floor() -> None:
    spec = sub_research_tool_spec(lambda _goals, _ctx: None)
    assert spec.name == spec.capability == SUB_RESEARCH_TOOL
    assert spec.contract.strip(), "spec §3.6 第 8 条：没有契约不上菜单"
    for clause in ("零证据", "failed", "goals", "不因为经过子研究而升档"):
        assert clause in spec.contract
    assert list(spec.parameters["properties"]) == ["goals"]
    assert tuple(spec.parameters["required"]) == ("goals",)
    assert spec.min_window_seconds == SUB_RESEARCH_MIN_WINDOW_SECONDS == MIN_WINDOW_SECONDS[SUB_RESEARCH_TOOL]
    # 地板 = 一支分支的时间上限，两个常数住在两层，必须相等（spec §4）。
    assert spec.min_window_seconds == MAX_SECONDS_PER_BRANCH == 60.0
    assert SUB_RESEARCH_TOOL in DEFAULT_RESEARCH_CAPABILITIES


def test_goals_argument_is_read_and_rejections_are_loud() -> None:
    runner_input, display = parse_sub_research_arguments({"goals": [" 甲 ", "乙"]})
    assert json.loads(runner_input) == ["甲", "乙"]
    assert display == "甲；乙"
    for bad, reason in (
        ({"goals": []}, "non-empty"),
        ({"goals": ["a", "a"]}, "repeats"),
        ({"goals": ["a", "b", "c", "d"]}, "at most 3"),
        ({"goals": ["a", ""]}, "non-empty string"),
        ({"goals": "a"}, "array"),
        ({"goals": ["a"], "depth": 2}, "exactly one goals"),
        ({"query": "a"}, "exactly one goals"),
    ):
        with pytest.raises(InvalidResearchToolArguments, match=reason):
            parse_sub_research_arguments(bad)


def test_default_registry_only_mounts_sub_research_when_a_runner_is_supplied() -> None:
    without = default_registry({"market_data": _successful_runner})
    assert SUB_RESEARCH_TOOL not in without.names()
    with_runner = default_registry(
        {"market_data": _successful_runner, "sub_research": lambda _g, _c: None}
    )
    assert SUB_RESEARCH_TOOL in with_runner.names()
    assert with_runner.without(SUB_RESEARCH_TOOL).names() == ("market_data",)


# ---------------------------------------------------------------------------
# ⑦ 结果翻译：空结果 / 拒绝 / 失败 / 成功
# ---------------------------------------------------------------------------


def _branch(
    branch_id: str,
    goal: str,
    *,
    status: str = "completed",
    evidence: tuple[AgentEvidence, ...] = (),
    gaps: tuple[str, ...] = (),
    error: str = "",
) -> BranchResult:
    return BranchResult(
        branch_id=branch_id,
        goal=goal,
        status=status,  # type: ignore[arg-type]
        evidence=evidence,
        traces=(),
        gaps=gaps,
        llm_calls=1,
        tool_calls=1,
        error=error,
    )


_EVIDENCE = AgentEvidence(
    tool="news_search",
    title="反方驱动证据",
    detail="同一窗口存在反向资金流证据",
    source="公开来源",
    source_date="2026-07-21",
    evidence_tier="public_web",
    content_hash="branch-evidence-1",
)


def test_refusal_is_an_error_with_reason_not_a_silent_empty() -> None:
    result = tool_result_from_branches(
        ("甲", "乙"), SubResearchResult((), refused_reason="deep_mode_required")
    )
    assert result.trace.status == "error"
    assert "deep_mode_required" in result.trace.detail
    assert "子研究未执行：deep_mode_required" in result.observation
    assert result.evidence == ()
    assert len(result.gaps) == 2 and all("未执行" in gap for gap in result.gaps)
    assert result.telemetry["refused_reason"] == "deep_mode_required"


def test_completed_with_zero_evidence_reads_as_gap_not_negation() -> None:
    result = tool_result_from_branches(
        ("甲",), SubResearchResult((_branch("branch-1", "甲"),))
    )
    assert result.trace.status == "empty"
    assert "缺口不是否定结论" in result.observation
    assert result.gaps == ("子研究分支「甲」本轮未找到可绑定证据",)


def test_failed_branch_says_unresearched_and_all_failed_is_error() -> None:
    result = tool_result_from_branches(
        ("甲",),
        SubResearchResult((_branch("branch-1", "甲", status="failed", error="branch_worker_exception:X"),)),
    )
    assert result.trace.status == "error"
    assert "该子问题未被研究，不是没有答案" in result.observation
    assert result.gaps[0].startswith("子研究分支「甲」未完成（branch_worker_exception:X）")


def test_evidence_passes_through_with_its_own_tier_and_date() -> None:
    result = tool_result_from_branches(
        ("甲", "乙"),
        SubResearchResult(
            (
                _branch("branch-1", "甲", evidence=(_EVIDENCE,)),
                _branch("branch-2", "乙", status="failed", error="cancelled"),
            )
        ),
    )
    assert result.trace.status == "success"
    assert result.evidence == (_EVIDENCE,)
    # 来源分档与 as_of 继承自分支里的工具：public_web 仍是 public_web，不升档。
    assert result.evidence[0].evidence_tier == "public_web"
    assert result.evidence[0].source_date == "2026-07-21"
    assert result.telemetry["branches"][1]["status"] == "failed"
    assert "已并入本轮证据表" in result.observation


# ---------------------------------------------------------------------------
# ②④ 绑定：深度 1 与窗内 deadline
# ---------------------------------------------------------------------------


def _contract(task_id: str, *, tier: str, allowed: tuple[str, ...]) -> ResearchTaskContract:
    frame = _frame()
    return ResearchTaskContract(
        task_id=task_id,
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(item, item, ("market_data",), True) for item in frame.required_outputs
        ),
        allowed_capabilities=allowed,
        research_tier=tier,
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )


def _context(tier: str, *, allowed: tuple[str, ...]) -> ResearchRunContext:
    policy = ResearchPolicy.for_tier(tier)
    task_id = f"sub-research-tool-{tier}-{uuid4().hex[:8]}"
    return ResearchRunContext(
        contract=_contract(task_id, tier=tier, allowed=allowed),
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds, synthesis_reserve=policy.synthesis_reserve
        ),
        policy=policy,
        trace_parent_id=task_id,
        today="2026-07-22",
        latest_data_date="2026-07-21",
        information_cutoff=InformationCutoff(date(2026, 7, 22), "requested"),
        root_budget=root_budget_for_policy(policy, episode_id=task_id),
    )


class _CapturingCoordinator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        sink = kwargs["evidence_sink_factory"]("branch-1")
        sink.append(_EVIDENCE)
        return SubResearchResult((_branch("branch-1", "查找反方驱动", evidence=(_EVIDENCE,)),))


def test_bound_runner_enforces_depth_one_and_stays_inside_the_batch_window() -> None:
    context = _context("max", allowed=("market_data", SUB_RESEARCH_TOOL))
    try:
        coordinator = _CapturingCoordinator()
        base = _market_registry(_successful_runner).with_specs(
            sub_research_tool_spec(lambda _g, _c: None)
        )
        ledger = EvidenceLedger(information_cutoff=date(2026, 7, 22))
        spec = bind_sub_research_tool(
            coordinator=coordinator,  # type: ignore[arg-type]
            task_frame=_frame(),
            current_context=lambda: context,
            base_registry=base,
            evidence_ledger=ledger,
        )
        result = spec.runner(
            json.dumps(["查找反方驱动"]),
            AgentToolContext(context.deadline, lambda: False, context.information_cutoff),
        )
        assert result.trace.status == "success"
        call = coordinator.calls[0]
        # 深度 = 1：分支注册表与分支契约都看不见 sub_research。
        assert SUB_RESEARCH_TOOL not in call["registry"].names()
        assert SUB_RESEARCH_TOOL not in call["context"].contract.allowed_capabilities
        assert "market_data" in call["context"].contract.allowed_capabilities
        # 分支 deadline 收在本批工具窗内（max 档 540s × 0.9），不是 episode 的 600s。
        branch_remaining = call["context"].deadline.remaining()
        assert branch_remaining <= 540.0 * 0.9 + 1e-6
        assert branch_remaining > 400.0
        # 不铸新账本：分支用父账本。
        assert call["context"].root_budget is context.root_budget
        # 分支证据经父账本 branch_sink 进账，owner 是分支。
        owners = dict(ledger.snapshot().evidence_branch_owners)
        assert owners["branch-evidence-1"] == "branch-1"
    finally:
        release_root_budget(context.contract.task_id)


def test_coordinator_accepts_max_tier_and_still_refuses_standard() -> None:
    class _Worker:
        def run(self, request):  # pragma: no cover - refused before worker runs
            raise AssertionError("worker must not run")

    coordinator = SubResearchCoordinator(_Worker())
    for tier, expect_refused in (("standard", "deep_mode_required"), ("quick", "deep_mode_required")):
        context = _context(tier, allowed=("market_data",))
        try:
            result = coordinator.run(
                goals=("甲",),
                task_frame=_frame(),
                context=context,
                registry=_market_registry(_successful_runner),
                evidence_sink_factory=EvidenceLedger(information_cutoff=date(2026, 7, 22)).branch_sink,
            )
            assert result.refused_reason == expect_refused
        finally:
            release_root_budget(context.contract.task_id)
    # max 档过门：走到起分支那一步（这里 worker 会被调，用一个记录型 worker 证明）。
    calls = []

    class _RecordingWorker:
        def run(self, request):
            calls.append(request.branch_id)
            return _branch(request.branch_id, request.goal)

    context = _context("max", allowed=("market_data",))
    try:
        result = SubResearchCoordinator(_RecordingWorker()).run(
            goals=("甲",),
            task_frame=_frame(),
            context=context,
            registry=_market_registry(_successful_runner),
            evidence_sink_factory=EvidenceLedger(information_cutoff=date(2026, 7, 22)).branch_sink,
        )
        assert result.refused_reason == "" and calls == ["branch-1"]
    finally:
        release_root_budget(context.contract.task_id)


# ---------------------------------------------------------------------------
# ③ Episode 集成：模型点 sub_research → 分支证据进账、进消息、可绑；无协调器则不存在
# ---------------------------------------------------------------------------


def _sub_research_turn(goals: list[str]) -> ModelTurn:
    return ModelTurn(
        "",
        (ModelToolCall("call-sub", SUB_RESEARCH_TOOL, {"goals": goals}),),
        "scripted",
        "",
    )


def test_episode_mounts_sub_research_only_with_a_coordinator_and_binds_branch_evidence() -> None:
    context = _context("max", allowed=("market_data", SUB_RESEARCH_TOOL))
    try:
        coordinator = _CapturingCoordinator()
        model = ScriptedModel(
            [
                _sub_research_turn(["查找反方驱动"]),
                _finish_turn(hashes=("branch-evidence-1",)),
            ]
        )
        outcome = ContinuousAgentEpisode(
            model,
            sub_research_coordinator=coordinator,  # type: ignore[arg-type]
        ).run(
            task_frame=_frame(),
            context=context,
            registry=_market_registry(_successful_runner),
        )
        assert outcome.status == "completed", outcome.stop_reason
        # 模型第一轮就看见了这个工具（schema 里有 goals）。
        first_tools = {tool["function"]["name"] for tool in model.calls[0]["tools"]}
        assert SUB_RESEARCH_TOOL in first_tools
        # 分支证据以 E 号进了下一轮消息，且 finish 绑到它的 hash 通过了终局门。
        assert "反方驱动证据" in str(model.calls[1]["messages"][-1])
        assert any("branch-evidence-1" in str(binding) for binding in outcome.bindings)
        kinds = [event.kind for event in outcome.events]
        assert "branch_started" in kinds and "branch_completed" in kinds
        started = next(e for e in outcome.events if e.kind == "branch_started")
        assert started.payload["origin"] == "tool"
        # 分支事件在 runner 里（批执行器线程）记，先于批结束后才落的 tool_request / tool_result。
        assert kinds.index("model_turn") < kinds.index("branch_started") < kinds.index("tool_result")
    finally:
        release_root_budget(context.contract.task_id)


def test_episode_without_coordinator_does_not_offer_sub_research() -> None:
    """分支里的嵌套 Episode / 参考 loop 都没有协调器：工具不存在，而不是存在但报错。"""

    context = _context("max", allowed=("market_data", SUB_RESEARCH_TOOL))
    try:
        model = ScriptedModel([_finish_turn(hashes=("evidence-1",))])
        registry = _market_registry(_successful_runner)
        # 先让 market_data 有证据可绑：走一次开场预取等价物——这里直接用 finish 前的工具轮。
        model = ScriptedModel(
            [
                ModelTurn("", (ModelToolCall("c1", "market_data", {"query": "总览"}),), "scripted", ""),
                _finish_turn(hashes=("evidence-1",)),
            ]
        )
        outcome = ContinuousAgentEpisode(model, sub_research_coordinator=None).run(
            task_frame=_frame(), context=context, registry=registry
        )
        assert outcome.status == "completed"
        first_tools = {tool["function"]["name"] for tool in model.calls[0]["tools"]}
        assert SUB_RESEARCH_TOOL not in first_tools
    finally:
        release_root_budget(context.contract.task_id)


# ---------------------------------------------------------------------------
# ⑤ 菜单：小窗藏、max 档可见
# ---------------------------------------------------------------------------


def test_menu_hides_sub_research_in_a_narrow_window_and_shows_it_in_max() -> None:
    spec = sub_research_tool_spec(lambda _g, _c: None)
    registry = _market_registry(_successful_runner).with_specs(spec)
    session = ToolBatchExecutor().new_session()

    # quick 档总窗 30 / reserve 20 → 本轮工具窗 10s，装不下一支 60s 的分支 → 藏。
    # （standard 在无 env 保险丝时派生窗 70s ≥ 60，本来就装得下，不是藏的对象。）
    narrow = _context("quick", allowed=("market_data", SUB_RESEARCH_TOOL))
    try:
        menu = session.menu(registry=registry, context=narrow)
        assert (SUB_RESEARCH_TOOL, 60.0) in menu.hidden
        assert menu.would_grant < 60.0
    finally:
        release_root_budget(narrow.contract.task_id)

    maximal = _context("max", allowed=("market_data", SUB_RESEARCH_TOOL))
    try:
        menu = ToolBatchExecutor().new_session().menu(registry=registry, context=maximal)
        assert SUB_RESEARCH_TOOL in menu.visible and menu.hidden == ()
    finally:
        release_root_budget(maximal.contract.task_id)


def test_with_specs_keeps_the_original_registry_untouched() -> None:
    base = _market_registry(_successful_runner)
    extended = base.with_specs(sub_research_tool_spec(lambda _g, _c: None))
    assert base.names() == ("market_data",)
    assert set(extended.names()) == {"market_data", SUB_RESEARCH_TOOL}
    assert isinstance(extended.resolve(SUB_RESEARCH_TOOL), ToolSpec)
    assert isinstance(extended, ResearchToolRegistry)
