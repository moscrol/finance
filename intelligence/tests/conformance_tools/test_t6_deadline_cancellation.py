"""T-6 尊重 stage deadline / 取消信号。

批次共享窗口的强制在 ``episode_tool_batch``（运行时套件 INV-4 已覆盖派发
前拒绝）；注册表层的义务是两条：deadline 与取消谓词**原样传进** runner 的
``AgentToolContext``（下游据此自行让路），以及取消发生时**不交付**观察值。
"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance_tools.baseline import ratchet
from intelligence.tests.conformance_tools.tools import (
    TOOL_NAMES,
    ToolProbe,
    make_tool_context,
    make_tool_registry,
    valid_arguments,
)

INV = "T-6"


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_deadline_and_cancellation_reach_the_runner_context(
    tool_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, tool_name)
    probe = ToolProbe()
    registry = make_tool_registry(probe)
    spec = registry.resolve(tool_name)
    context = make_tool_context(
        task_id=f"conf-t6-{tool_name}",
        allowed_capabilities=(spec.capability,),
    )
    flags: list[bool] = []

    def is_cancelled() -> bool:
        flags.append(True)
        return False

    registry.execute(
        tool_name,
        valid_arguments(spec),
        context=context,
        step_id=f"conf-t6-{tool_name}:tool:1",
        is_cancelled=is_cancelled,
    )

    assert probe.contexts, "runner 没有收到 AgentToolContext"
    tool_context = probe.contexts[0]
    assert tool_context.deadline is context.deadline, (
        f"{tool_name} 的 runner 收到的 deadline 不是 episode 的那一份"
        "（各订阅各的时钟会让共享窗口失效）"
    )
    assert tool_context.is_cancelled is not None
    assert flags, "取消谓词没有被执行链路观测过（信号断线）"


@pytest.mark.parametrize("tool_name", TOOL_NAMES[:1])
def test_cancellation_after_runner_suppresses_delivery(tool_name: str) -> None:
    """取消到达后不交付观察值（对账口径：宁可少一条，不可假装完成）。

    形状由 registry.execute 单点实现，逐工具跑一遍没有增量信息，取首个
    工具作代表（契约单点强制，见 tools.py 模块 docstring）。
    """

    probe = ToolProbe()
    registry = make_tool_registry(probe)
    spec = registry.resolve(tool_name)
    context = make_tool_context(
        task_id=f"conf-t6-cancel-{tool_name}",
        allowed_capabilities=(spec.capability,),
    )

    with pytest.raises(RuntimeError, match="cancelled"):
        registry.execute(
            tool_name,
            valid_arguments(spec),
            context=context,
            step_id=f"conf-t6-cancel-{tool_name}:tool:1",
            is_cancelled=lambda: True,
        )
