"""T-3 参数校验 fail-closed：坏参数抛 ``InvalidResearchToolArguments``，
不静默容错。逐工具按其声明的参数形状分派（query 类 / snapshot 类由
spec.parse_arguments 运行时判定，不写死名单）。
"""

from __future__ import annotations

import pytest

from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments,
    UnknownResearchTool,
)
from intelligence.tests.conformance_tools.baseline import ratchet
from intelligence.tests.conformance_tools.tools import (
    TOOL_NAMES,
    ToolProbe,
    is_goals_tool,
    is_snapshot_tool,
    is_url_tool,
    make_tool_registry,
)

INV = "T-3"


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_bad_arguments_fail_closed(
    tool_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, tool_name)
    registry = make_tool_registry(ToolProbe())
    spec = registry.resolve(tool_name)

    # 通用：参数不是对象 → 拒（所有工具一致）。
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare(tool_name, 123)  # type: ignore[arg-type]
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare(tool_name, ["query"])  # type: ignore[arg-type]

    if is_snapshot_tool(spec):
        # snapshot 契约：不接受任何参数；空参合法（一回合一份完整快照）。
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"query": "多余参数"})
        prepared = registry.prepare(tool_name, {})
        assert prepared.tool == tool_name
        return

    if is_url_tool(spec):
        # url 契约：必须且只能有一个绝对 http(s) URL；检索词、站点名、相对路径一律拒。
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"url": ""})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"url": "贵州茅台 2024 年报"})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"url": "finance.sina.com.cn/600519"})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"query": "https://example.invalid/x"})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"url": "https://example.invalid/x", "extra": 1})
        prepared = registry.prepare(tool_name, {"url": " https://example.invalid/x "})
        assert prepared.display_query == "https://example.invalid/x"
        return

    if is_goals_tool(spec):
        # goals 契约：必须且只能有一个 1–3 条、非空、去重的字符串数组；不静默截断。
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"goals": []})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"goals": "单个字符串"})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"goals": ["甲", ""]})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"goals": ["甲", "甲"]})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"goals": ["甲", "乙", "丙", "丁"]})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"query": "甲"})
        with pytest.raises(InvalidResearchToolArguments):
            registry.prepare(tool_name, {"goals": ["甲"], "extra": 1})
        prepared = registry.prepare(tool_name, {"goals": [" 甲 ", "乙"]})
        assert prepared.display_query == "甲；乙"
        return

    # query 契约：必须且只能有一个非空字符串 query。
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare(tool_name, {})
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare(tool_name, {"query": ""})
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare(tool_name, {"query": 123})
    with pytest.raises(InvalidResearchToolArguments):
        registry.prepare(tool_name, {"query": "x", "extra": "y"})
    prepared = registry.prepare(tool_name, {"query": "合法检索词"})
    assert prepared.display_query == "合法检索词"


def test_unknown_tool_fails_closed_not_silently() -> None:
    registry = make_tool_registry(ToolProbe())
    with pytest.raises(UnknownResearchTool):
        registry.prepare("no_such_tool", {"query": "x"})


def test_prepared_arguments_for_another_tool_are_rejected() -> None:
    """prepare 的产物绑定工具身份，跨工具复用必须拒——防串号执行。"""

    registry = make_tool_registry(ToolProbe())
    query_tools = [
        name
        for name in TOOL_NAMES
        if not is_snapshot_tool(registry.resolve(name))
        and not is_url_tool(registry.resolve(name))
        and not is_goals_tool(registry.resolve(name))
    ]
    first, second = query_tools[0], query_tools[1]
    prepared = registry.prepare(first, {"query": "合法检索词"})
    with pytest.raises(InvalidResearchToolArguments, match="another tool"):
        registry.prepare(second, prepared)
