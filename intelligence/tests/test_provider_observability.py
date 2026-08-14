from __future__ import annotations

import unittest

from intelligence.services.provider_observability import (
    ProviderTrace,
    provider_trace_tool_name,
)


class ProviderTraceToolNameTests(unittest.TestCase):
    """agent 工具 trace 在成功/失败两条路上把工具名放在不同字段。

    2026-08-14 实测：按 ``capability`` 分组会把所有成功扫进 ``agent_loop``，
    真名下面只剩失败，于是「kb_search 20 次 0% 成功」——那是聚合错位，不是事实。
    """

    def _success(self) -> ProviderTrace:
        # 成功路：真名只在 provider 里，capability 被改写成 agent_loop
        return ProviderTrace(
            provider="agent:kb_search", capability="agent_loop",
            status="success", result_count=5,
        )

    def _failure(self) -> ProviderTrace:
        # 失败路：capability 保留真名
        return ProviderTrace(
            provider="agent:kb_search", capability="kb_search",
            status="request_error", detail="tool_timeout",
        )

    def test_both_paths_resolve_to_the_same_tool(self) -> None:
        self.assertEqual(provider_trace_tool_name(self._success()), "kb_search")
        self.assertEqual(provider_trace_tool_name(self._failure()), "kb_search")

    def test_non_agent_trace_falls_back_to_capability(self) -> None:
        trace = ProviderTrace(provider="cninfo", capability="l3_lookup", status="success")
        self.assertEqual(provider_trace_tool_name(trace), "l3_lookup")

    def test_grouping_by_capability_is_the_bug_being_fixed(self) -> None:
        """变异测试：直接用 capability 分组必然把两条路拆散。

        没有这条，任何人把归一化换回 ``trace.capability`` 都不会有测试变红。
        """
        traces = (self._success(), self._failure())
        by_capability = {t.capability for t in traces}
        by_real_name = {provider_trace_tool_name(t) for t in traces}
        self.assertEqual(len(by_capability), 2)  # 被拆成两个桶 —— 这就是缺陷
        self.assertEqual(by_real_name, {"kb_search"})  # 归一化后合成一个

    def test_empty_agent_suffix_falls_back(self) -> None:
        trace = ProviderTrace(provider="agent:", capability="fallback_cap", status="empty")
        self.assertEqual(provider_trace_tool_name(trace), "fallback_cap")


if __name__ == "__main__":
    unittest.main()
