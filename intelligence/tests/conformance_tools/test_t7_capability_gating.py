"""T-7 capability 名与注册表元数据一致；门控裁剪后不可见即不可调。

出处：``episode_tools.py`` 的装配按 contract.allowed_capabilities 分支；
``episode_tool_batch`` 与 ``agent_episode._available_tool_definitions``
都以 ``authorized_specs`` 为可见性事实源。
"""

from __future__ import annotations

import pytest

from intelligence.services.research_tool_registry import (
    _DEFAULT_TOOL_METADATA,
    DEFAULT_RESEARCH_CAPABILITIES,
    UnknownResearchTool,
)
from intelligence.tests.conformance_tools.baseline import ratchet
from intelligence.tests.conformance_tools.tools import (
    TOOL_NAMES,
    ToolProbe,
    make_tool_context,
    make_tool_registry,
    valid_arguments,
)

INV = "T-7"


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_capability_matches_metadata_and_gating_is_total(
    tool_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, tool_name)
    probe = ToolProbe()
    registry = make_tool_registry(probe)
    spec = registry.resolve(tool_name)

    declared_capability = _DEFAULT_TOOL_METADATA[tool_name][0]
    assert spec.capability == declared_capability, (
        f"{tool_name} 装配出的 capability 与元数据声明不一致"
    )
    assert declared_capability in DEFAULT_RESEARCH_CAPABILITIES

    # 授权面：包含该 capability 时可见。
    granted = registry.authorized_specs((declared_capability,))
    assert any(item.name == tool_name for item in granted)
    granted_definitions = registry.tool_definitions((declared_capability,))
    assert any(
        definition["function"]["name"] == tool_name
        for definition in granted_definitions
    )

    # 裁剪面：不授该 capability 时，specs / definitions / prompt 三个可见性
    # 出口同步消失。
    others = tuple(
        capability
        for capability in DEFAULT_RESEARCH_CAPABILITIES
        if capability != declared_capability
    )
    denied = registry.authorized_specs(others)
    assert all(item.name != tool_name for item in denied)
    denied_definitions = registry.tool_definitions(others)
    assert all(
        definition["function"]["name"] != tool_name
        for definition in denied_definitions
    )
    # prompt_block 的条目行以「- 工具名（」开头；其他工具的行为契约散文里
    # 可以**提到**被裁剪的工具（如「需要 l3_lookup 的公告确认」），那不是
    # 暴露。只断言条目行消失。
    assert f"- {tool_name}（" not in registry.prompt_block(others)

    # 不可见即不可调：execute 对未授权 capability 抛显式错误，runner 零触碰。
    context = make_tool_context(
        task_id=f"conf-t7-{tool_name}",
        allowed_capabilities=others,
    )
    with pytest.raises(UnknownResearchTool, match="能力未授权"):
        registry.execute(
            tool_name,
            valid_arguments(spec),
            context=context,
            step_id=f"conf-t7-{tool_name}:tool:1",
        )
    assert probe.invocations == [], "未授权工具的 runner 被执行了"


# 声明共享 capability 的工具：历史发现研究三件按批准 spec（2026-09-09-historical-discovery-
# research-design）复用 finance_query 授权，不新开授权面。除此之外仍是一名一能力；新增共享
# 先改这张表再改元数据，两边都不改就在这里红。
SHARED_CAPABILITY_TOOLS: dict[str, str] = {
    "history_query": "finance_query",
    "read_history_result": "finance_query",
    "save_history_research": "finance_query",
}


def test_metadata_names_and_capabilities_stay_one_to_one() -> None:
    """元数据里工具名即 capability 名（一名一能力），唯一例外是登记在
    ``SHARED_CAPABILITY_TOOLS`` 里、声明复用既有 capability 的工具；共享的目标
    必须本身就是一个已声明的 capability。"""

    for name, (capability, _description, _freshness, _produces) in (
        _DEFAULT_TOOL_METADATA.items()
    ):
        if name in SHARED_CAPABILITY_TOOLS:
            assert capability == SHARED_CAPABILITY_TOOLS[name], (
                f"{name} 声明的共享 capability 与登记表不一致"
            )
            assert capability in _DEFAULT_TOOL_METADATA, (
                f"{name} 共享的 {capability} 不是已声明的 capability"
            )
            continue
        assert capability == name
    assert set(SHARED_CAPABILITY_TOOLS) <= set(_DEFAULT_TOOL_METADATA)
