"""INV-1 未授权工具不可见 / 不可调。

契约不含 capability X → 模型可见工具面无 X；脚本化模型强行调 X →
落 invalid_actions / 显式拒绝收据，且 X 的 runner 一次都不被执行。
"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    FORBIDDEN_TOOL,
    ScenarioProbe,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)

INV = "INV-1"


def _scenario() -> tuple[ScriptedTurn, ...]:
    """先强行调未授权工具 + 正常调授权工具，再收尾。"""

    return (
        ScriptedTurn(
            tool_calls=(
                ScriptedToolCall(FORBIDDEN_TOOL, "强行越权查询"),
                ScriptedToolCall(AUTHORIZED_TOOL, "最近交易日市场宽度"),
            ),
        ),
        ScriptedTurn(finish=completed_finish()),
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_unauthorized_tool_is_invisible_and_uncallable(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv1-{backend.name}")
    registry = make_registry(probe)
    run = backend.build_driver().run(
        initial=_scenario(),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )

    # 不可调：未授权 runner 一次都没执行；授权 runner 正常执行。
    executed_tools = [name for name, _query in probe.executed]
    assert FORBIDDEN_TOOL not in executed_tools, (
        f"{backend.name} 执行了未授权工具：{probe.executed}"
    )
    assert AUTHORIZED_TOOL in executed_tools, (
        f"{backend.name} 授权工具也没执行，场景没跑起来：{probe.executed}"
    )

    # 不可见：模型可见工具面（有该观测面的后端）不含未授权工具。
    for turn_index, visible in enumerate(probe.visible_tools):
        assert FORBIDDEN_TOOL not in visible, (
            f"{backend.name} 第 {turn_index + 1} 轮把未授权工具暴露给了模型：{visible}"
        )
    if backend.name == "codex_headless":
        # codex 的工具菜单在 prompt 文本里；工具名是本套件自造的唯一串。
        joined_args = "\n".join(" ".join(args) for args in probe.codex_args)
        assert FORBIDDEN_TOOL not in joined_args, (
            "codex prompt 把未授权工具写进了工具菜单"
        )
        rejected = [
            result
            for result in probe.codex_tool_results
            if result.get("status") == "rejected"
        ]
        assert rejected, "codex 网关对越权调用没有返回显式 rejected 收据"
    if backend.name == "dsh_stub":
        scope_dump = run.runtime.last_protocol["tool_definitions"]
        names = {
            str(item.get("function", {}).get("name", ""))
            for item in scope_dump
            if isinstance(item, dict)
        }
        assert FORBIDDEN_TOOL not in names, "stub 的模型可见定义含未授权工具"

    # 强行调的显式痕迹：continuous / stub 走批次拒绝（invalid_actions 或
    # tool_error 收据）；SDK 形状下强行调不可表达（provider 只能调注册进
    # FunctionTool 表的名字），裁剪即拒绝，由 driver 如实登记。
    if backend.name == "continuous_glm":
        assert run.outcome.usage.invalid_actions >= 1, (
            "越权调用没有计入 invalid_actions"
        )
    elif backend.name in {"sdk_glm", "sdk_gpt"}:
        assert FORBIDDEN_TOOL in probe.denied_tool_requests, (
            "SDK 可见工具面裁剪未生效（脚本竟然找到了未授权工具）"
        )
    elif backend.name == "dsh_stub":
        errors = [
            event
            for event in run.outcome.events
            if event.kind == "tool_error"
            and event.payload.get("error") == "unknown_or_unauthorized_tool"
        ]
        assert errors, "stub 越权调用没有留下显式 tool_error 收据"
