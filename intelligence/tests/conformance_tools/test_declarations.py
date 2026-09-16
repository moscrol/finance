"""能力声明表自身的完整性——声明表是三件之一，必须有消费者。

（「写了没人读」是本仓 unread-fields 门禁点名的失败形状；声明表若没有
任何断言消费它，漂移时无人知晓。）
"""

from __future__ import annotations

from intelligence.tests.conformance_tools.baseline import BASELINE
from intelligence.tests.conformance_tools.tools import (
    T_INVARIANT_IDS,
    TOOL_DECLARATIONS,
    TOOL_NAMES,
    TOOL_NOTES,
)


def test_declaration_table_covers_every_tool_and_invariant() -> None:
    assert set(TOOL_DECLARATIONS) == set(TOOL_NAMES)
    for tool_name, verdicts in TOOL_DECLARATIONS.items():
        assert set(verdicts) == set(T_INVARIANT_IDS), (
            f"{tool_name} 的声明缺不变量：{set(T_INVARIANT_IDS) - set(verdicts)}"
        )
        for invariant, verdict in verdicts.items():
            assert verdict == "supported", (
                f"{tool_name}:{invariant} 声明为 {verdict!r}——注册表层契约由 "
                "ResearchToolRegistry 单点强制，出现非 supported 声明说明装配"
                "面发生了分叉，先在 TOOL_NOTES 写清出处再改这里"
            )


def test_notes_reference_known_tools_only() -> None:
    unknown = set(TOOL_NOTES) - set(TOOL_NAMES)
    assert not unknown, f"notes 引用了不存在的工具：{sorted(unknown)}"


def test_baseline_keys_reference_known_tools_and_invariants() -> None:
    for key, reason in BASELINE.items():
        invariant, _, tool_name = key.partition(":")
        assert invariant in T_INVARIANT_IDS, f"baseline key 不合法：{key}"
        assert tool_name in TOOL_NAMES, f"baseline key 指向未知工具：{key}"
        assert reason.strip(), f"baseline 条目缺原因：{key}"
