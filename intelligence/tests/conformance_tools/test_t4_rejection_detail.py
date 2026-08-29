"""T-4 拒绝时 detail 非空且可操作。

出处：``episode_tool_batch.ToolCallResult.detail`` 的注释与 2026-08-12 事故
——15 次失败 14 次同形状重复，因为模型收到的 detail 恒空（字段早就在，
从没被填过）。批次层的 detail 来自 ``str(InvalidResearchToolArguments)``，
所以本条钉住：注册表层抛出的每个拒绝，消息文本必须非空、不等于分类码
本身、且指得出问题所在。
"""

from __future__ import annotations

import pytest

from intelligence.services.research_tool_registry import InvalidResearchToolArguments
from intelligence.tests.conformance_tools.baseline import ratchet
from intelligence.tests.conformance_tools.tools import (
    TOOL_NAMES,
    ToolProbe,
    is_snapshot_tool,
    make_tool_registry,
)

INV = "T-4"


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_rejection_message_is_actionable(
    tool_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, tool_name)
    registry = make_tool_registry(ToolProbe())
    spec = registry.resolve(tool_name)

    bad_arguments: dict[str, object] = (
        {"query": "多余参数"} if is_snapshot_tool(spec) else {"query": ""}
    )
    with pytest.raises(InvalidResearchToolArguments) as excinfo:
        registry.prepare(tool_name, bad_arguments)

    detail = str(excinfo.value)
    code = excinfo.value.code
    assert detail.strip(), f"{tool_name} 的拒绝消息为空——模型只能盲目重试同一形状"
    assert detail != code, f"{tool_name} 的拒绝消息就是分类码本身，不可操作"
    # 可操作性的最低线：消息里指得出参数或约束（query / argument / snapshot）。
    lowered = detail.lower()
    assert any(
        keyword in lowered for keyword in ("query", "argument", "snapshot", "object")
    ), f"{tool_name} 的拒绝消息指不出哪个参数错在哪：{detail!r}"
    assert isinstance(code, str) and code.strip(), "分类码必须存在（供按类归并）"
