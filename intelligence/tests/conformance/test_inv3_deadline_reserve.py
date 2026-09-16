"""INV-3 绝对 deadline + 合成保底。

检索窗被 reserve 挤压后，合成仍拿到 ≥ reserve 量级的窗口（continuous 全量）；
SDK 档按自己声明的缩减语义断言（只扣 verifier/delivery 小窗，合成保底归
adapter 层且给零）；codex 声明式不支持——断言机制确实不在场，防止有人加了
机制却不改声明表。修复轮 reserve=0 的半条也在 continuous 里断言。
"""

from __future__ import annotations

import inspect

import pytest

from intelligence.runtime.codex_headless_runtime import CodexHeadlessRuntime
from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    ScenarioProbe,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
    make_repair_goal,
)

INV = "INV-3"


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_synthesis_survives_a_burned_research_window(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    if verdict is Verdict.UNSUPPORTED_DECLARED:
        # codex：声明式不支持。断言机制确实不在场——构造面没有任何合成保底
        # 参数，也没有会话缝可分窗。若这条开始失败，说明有人给 codex 加了
        # reserve 机制：先改 backends.py 的声明再来改这里。
        parameters = inspect.signature(CodexHeadlessRuntime.__init__).parameters
        assert not any("reserve" in name for name in parameters), (
            "CodexHeadlessRuntime 构造面出现了 reserve 参数，声明表已过期"
        )
        assert getattr(CodexHeadlessRuntime, "synthesis_reserve_for_task", None) is None
        return

    probe = ScenarioProbe()
    frame = make_frame()
    registry = make_registry(probe)

    if verdict is Verdict.REDUCED:
        # SDK 缩减语义（抄 test_sdk_runtime_reserves_part_of_synthesis_budget_
        # for_verifier 的判据）：runner 拿到的窗口扣掉的是 SDK 自己的
        # verifier/delivery 小窗（2-20s 夹层），不是完整 synthesis_reserve。
        context = make_context(
            frame,
            task_id=f"conf-inv3-{backend.name}",
            timeout=30.0,
            synthesis_reserve=10.0,
        )
        run = backend.build_driver().run(
            initial=(
                ScriptedTurn(
                    tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
                ),
                ScriptedTurn(finish=completed_finish()),
            ),
            frame=frame,
            context=context,
            registry=registry,
            probe=probe,
        )
        assert run.outcome.status == "completed"
        assert len(probe.model_timeouts) == 1
        granted = probe.model_timeouts[0]
        assert 20.0 < granted < 30.0, (
            f"SDK 缩减版窗口预期在 (总窗-reserve, 总窗) 之间，实得 {granted}"
        )
        return

    # continuous 全量，两个子场景（零 sleep，全部由 deadline 数学决定）。
    #
    # 子场景 A ── 检索窗彻底烧穿（total=7s，常规切法只剩 2s，连 opening 借
    # 余量也不够 MIN_PLANNING_TURN_SECONDS=8s）：首轮即强制 finalization，
    # 工具面必须为空，合成轮拿到含保留段的**全部剩余**（synthesis_timeout
    # ≈7s，而 stage 切法只有 2s）。
    context_burned = make_context(
        frame,
        task_id=f"conf-inv3-{backend.name}-burned",
        timeout=7.0,
        synthesis_reserve=5.0,
    )
    run_burned = backend.build_driver().run(
        initial=(ScriptedTurn(finish=completed_finish(evidence_hashes=(), gap="窗口烧穿")),),
        frame=frame,
        context=context_burned,
        registry=make_registry(ScenarioProbe()),
        probe=probe,
    )
    finalizations = [
        dict(event.payload)
        for event in run_burned.outcome.events
        if event.kind == "finalization"
    ]
    assert finalizations, "检索窗烧穿后没有进入显式 finalization"
    assert finalizations[0].get("reason") == "retrieval_deadline_closed"
    assert probe.visible_tools[0] == (), "烧穿后模型仍看得到工具"
    synthesis_window = probe.model_timeouts[0]
    stage_residual = 7.0 - 5.0
    assert synthesis_window >= 6.0 > stage_residual, (
        f"合成轮只拿到 {synthesis_window:.2f}s（stage 切法 {stage_residual}s），"
        "reserve 没有在烧穿时兑现为合成窗口"
    )

    # 子场景 B ── 残窗不足一次写作（total=32s、reserve=30s）：首轮 opening
    # 向 reserve 借超出 20s 合成地板的余量（≈10s），取证轮正常跑；第二轮
    # followup 常规切法只剩 ≈1.9s，向 reserve 借到地板但**保住 20s**——
    # 窗口 ≈ remaining−20 ≈ 11.9s，明显大于 1.9s 又不吞掉整段 reserve
    # （_followup_planning_timeout 的「借完至少留一截合成地板」不变量）。
    probe_soft = ScenarioProbe()
    context_soft = make_context(
        frame,
        task_id=f"conf-inv3-{backend.name}-soft",
        timeout=32.0,
        synthesis_reserve=30.0,
    )
    run_soft = backend.build_driver().run(
        initial=(
            ScriptedTurn(
                tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
            ),
            ScriptedTurn(finish=completed_finish()),
        ),
        frame=frame,
        context=context_soft,
        registry=make_registry(probe_soft),
        probe=probe_soft,
    )
    assert run_soft.outcome.status == "completed"
    assert probe_soft.executed, "opening 借窗失败，取证轮没有跑成"
    assert len(probe_soft.model_timeouts) >= 2
    followup_window = probe_soft.model_timeouts[1]
    stage_residual_soft = 32.0 - 30.0
    assert followup_window >= 10.0 > stage_residual_soft, (
        f"followup 轮只拿到 {followup_window:.2f}s，没有向 reserve 借到合成地板"
    )
    assert followup_window <= 12.5, (
        f"followup 轮拿到 {followup_window:.2f}s，把合成地板吞掉了"
    )


@pytest.mark.parametrize(
    "backend",
    [item for item in BACKENDS if item.verdict(INV) is Verdict.SUPPORTED],
    ids=lambda item: item.name,
)
def test_repair_round_runs_on_pure_residual_clock(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    """修复轮 reserve=0：granted 秒数不打 reserve 折扣（continuous 半条）。"""

    ratchet(request, INV, backend.name)
    if backend.name != "continuous_glm":
        pytest.skip("修复轮时钟账收据（repair_reentry.timeout_asked）是 continuous 档专属观测面")

    probe = ScenarioProbe()
    frame = make_frame()
    task_id = f"conf-inv3-repair-{backend.name}"
    context = make_context(frame, task_id=task_id, timeout=30.0)
    registry = make_registry(probe)
    run = backend.build_driver().start(
        initial=(
            ScriptedTurn(
                tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
            ),
            ScriptedTurn(finish=completed_finish()),
        ),
        repairs=((ScriptedTurn(finish=completed_finish()),),),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )
    try:
        assert run.session is not None
        updated = run.session.resume(make_repair_goal(task_id))
    finally:
        run.close()
    reentries = [
        dict(event.payload)
        for event in updated.events
        if event.kind == "repair_reentry"
    ]
    assert reentries, "resume 没有留下 repair_reentry 时钟账"
    granted = float(reentries[0]["granted_seconds"])
    asked = float(reentries[0]["timeout_asked"])
    # goal.remaining_seconds=5.0；修复 deadline 的 synthesis_reserve=0，
    # 所以 asked = min(llm_timeout, 残余) ≈ granted，不出现 reserve 折扣。
    assert granted == pytest.approx(5.0, abs=0.2)
    assert asked == pytest.approx(granted, abs=0.5), (
        f"修复轮窗口被打了折扣：granted={granted} asked={asked}（reserve 应为 0）"
    )
