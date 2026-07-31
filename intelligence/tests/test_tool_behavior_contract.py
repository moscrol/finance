"""工具提示词是行为契约，不是功能文档。

马书 ch08 的结论：「优秀的工具提示词不是功能文档，而是行为契约——它不仅告诉
模型这个工具能做什么，更告诉它在什么条件下用、怎样用才安全、什么时候该用其他
工具。」ch27 模式六给了理由——**时序对齐**：模型决定调用某工具时，该工具的约束
正好在它的注意力焦点内；同一句话写在系统提示词里，模型需要在数万 token 的上下文
里「回忆」，长会话中不可靠。CC 的 BashTool 光提示词就约 370 行。

我们原先只有 ``description`` 那句名词短语（「结构化行情与市场时序」），
模型无从知道它拿到的是哪一天的数据、返回为空意味着什么。

这跟本轮修的 required_outputs 是**同构**的问题：``evidence_capabilities.py``
里有一整张「什么需求该用哪些工具」的路由表，但那张表只在 harness 内部用，
模型从没见过——就像 task_fulfillment 逐条打分的那份清单从没进过 prompt 一样。

契约内容的纪律：**只写验证过的**。每条要么来自线上实测的失败模式，
要么是复述 CLAUDE.md 里已有的红线。没依据的宁可留空——编一句进去比不写更糟。
"""
from __future__ import annotations

import pytest

from intelligence.services import research_tool_registry as reg


def _spec(name: str, contract: str = "") -> reg.ToolSpec:
    return reg.ToolSpec(
        name=name,
        capability=name,
        description="工具描述",
        cost="local",
        freshness="stable",
        runner=lambda *a, **k: None,
        contract=contract,
    )


class TestContractReachesTheModel:
    """契约必须真的到模型面前——两个出口都要带上。"""

    def test_function_schema_carries_the_contract(self) -> None:
        registry = reg.ResearchToolRegistry((_spec("t", "别把它当实时数据"),))

        description = registry.tool_definitions()[0]["function"]["description"]

        assert "工具描述" in description
        assert "别把它当实时数据" in description

    def test_prompt_block_carries_the_contract(self) -> None:
        registry = reg.ResearchToolRegistry((_spec("t", "别把它当实时数据"),))

        assert "别把它当实时数据" in registry.prompt_block()

    def test_empty_contract_adds_no_noise(self) -> None:
        """没契约的工具输出必须跟以前一模一样，不能多出空行或分隔符。"""
        registry = reg.ResearchToolRegistry((_spec("t"),))

        assert registry.tool_definitions()[0]["function"]["description"] == "工具描述"
        assert registry.prompt_block() == "- t（t，local，stable）：工具描述"


class TestShippedContracts:
    """已写的四条各自钉住它要防的那个误读。"""

    def test_market_data_warns_about_the_snapshot_date(self) -> None:
        """实测 degrade：「盘面快照回退到 2026-07-30（2026-07-31 尚无候选）」。

        模型原先看到的只有「结构化行情与市场时序」，无从知道拿到的可能是昨天。
        """
        contract = reg._TOOL_CONTRACTS["market_data"]

        assert "不是实时" in contract
        assert "上一交易日" in contract

    def test_market_data_explains_the_us_session_boundary(self) -> None:
        """美股日期不是 bug（上一份 handoff §7 已定论），但系统从没解释过为什么。

        美股夏令时按北京时间 21:30→次日 04:00，凌晨 02:41 看到「前一天」
        是因为那一场还在进行。
        """
        contract = reg._TOOL_CONTRACTS["market_data"]

        assert "21:30" in contract
        assert "不是数据过期" in contract

    def test_l3_lookup_separates_success_from_evidence(self) -> None:
        """实测 degrade：「l3-evidence：company 查询成功但没有解析到可用证据」。

        空结果只能说明没检索到，不能推出「该公司没有相关公告」——
        这正是把缺口写成否定结论的那类错误。
        """
        contract = reg._TOOL_CONTRACTS["l3_lookup"]

        assert "查询成功不等于查到了证据" in contract
        assert "证据缺口" in contract

    @pytest.mark.parametrize("tool", ["web_search", "news_search"])
    def test_secondary_sources_are_marked_as_such(self, tool: str) -> None:
        """复述 CLAUDE.md 的红线：二手材料不直接写成公司级硬事实。"""
        contract = reg._TOOL_CONTRACTS[tool]

        assert "二手材料" in contract
        assert "l3_lookup" in contract
        assert "待验证线索" in contract

    def test_news_contract_blocks_the_circular_confirmation_fallacy(self) -> None:
        """多家转载同一条消息不构成交叉验证——web-access skill 里写过同一条。"""
        assert "不构成交叉验证" in reg._TOOL_CONTRACTS["news_search"]


def test_contracts_only_cover_tools_that_exist() -> None:
    """契约表不能引用已经不存在的工具名，否则它会静默失效。"""
    assert set(reg._TOOL_CONTRACTS) <= set(reg._DEFAULT_TOOL_METADATA)
