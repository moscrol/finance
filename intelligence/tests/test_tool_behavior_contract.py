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
from intelligence.services.research_tool_registry import default_registry


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
    """每条契约各自钉住它要防的那个误读。

    这里**故意没有**「每个工具都必须有契约」那条不变量。它看着像自然的下一步，
    但会和本模块的纪律正面冲突：纪律是「没依据宁可留空」，而一条全覆盖门禁会让
    下一个加工具的人为了让测试变绿去**编一句**——正好是纪律要防的那件事。
    覆盖率要看的是「有依据的都写了没有」，那个只能靠人判断，不能靠断言。
    """

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

    def test_market_data_tells_overnight_forecasts_to_prefer_structured_us_quotes(
        self,
    ) -> None:
        contract = reg._TOOL_CONTRACTS["market_data"]

        assert "结构化报价" in contract
        assert "新闻标题里的数字不作为精确行情" in contract

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

    def test_finance_query_warns_that_rows_are_truncated(self) -> None:
        """``_AGENT_FINANCE_QUERY_MAX_ROWS = 25`` 会压 limit，而 observation 只在
        **拿到结果之后**才追一句「已截断」。模型下单时看不到，于是可能把 25 行的
        截断结果当全集，写出「全市场最高」这类全称断言。
        """
        contract = reg._TOOL_CONTRACTS["finance_query"]

        assert "截断" in contract
        assert "全称断言" in contract

    def test_finance_query_states_the_two_rejected_shapes(self) -> None:
        """两种写法 runner 会直接退回而不是查了没有：日期写进 filters
        （``validation_retry_hint`` 逐字有这条）、未授权时查历史窗口。
        后者实测会让模型对同一个窗口反复重试。
        """
        contract = reg._TOOL_CONTRACTS["finance_query"]

        assert "time_range" in contract
        assert "不要反复重试" in contract

    def test_evidence_search_flags_the_mixed_stance_list(self) -> None:
        """``_project_evidence`` 把 conclusion 与 counter_clues 合成同一个列表，
        立场只在 observation 的 ``[支持]``/``[反方]`` 前缀里，AgentEvidence 不带该字段。

        只从证据列表引用就会把反证当成支持性证据——这是本工具独有的误读。
        """
        contract = reg._TOOL_CONTRACTS["evidence_search"]

        assert "反方" in contract
        assert "不要把反证当成支持性证据" in contract

    def test_evidence_search_declares_its_cost(self) -> None:
        """2026-08-10 实测冷调用 28.2s，占满当时 30s 工具批次的 94%。"""
        assert "28 秒" in reg._TOOL_CONTRACTS["evidence_search"]

    def test_kb_search_carries_the_ingest_layering(self) -> None:
        """复述 CLAUDE.md 的 PDF ingest 红线：券商材料只进「高信度研究线索」
        或「观察列表」，不进「边际变化」。检索命中不带 section 标记。
        """
        contract = reg._TOOL_CONTRACTS["kb_search"]

        assert "高信度研究线索" in contract
        assert "边际变化" in contract
        assert "l3_lookup" in contract

    def test_graph_lookup_separates_match_score_from_business_strength(self) -> None:
        """概念项 detail 逐字是 f"匹配分 {score}"——文本匹配分，不是业务关联度。"""
        contract = reg._TOOL_CONTRACTS["graph_lookup"]

        assert "匹配分" in contract
        assert "不代表业务关联强度" in contract

    def test_graph_lookup_downgrades_peripheral_mappings(self) -> None:
        """CLAUDE.md 规定研报级产业链归类降级 graph_only（strength=peripheral），
        即图谱里本来就混着大量未确认映射。公司项 detail 带 strength/evidence_layer。
        """
        contract = reg._TOOL_CONTRACTS["graph_lookup"]

        assert "peripheral" in contract
        assert "线索" in contract

    def test_evidence_lookup_requires_carrying_the_quality_markers(self) -> None:
        """每条 detail 逐字带（来源，日期，质量 X）三项，但没人说过该怎么用它们。"""
        contract = reg._TOOL_CONTRACTS["evidence_lookup"]

        assert "质量" in contract
        assert "二手材料" in contract
        assert "无日期" in contract

    def test_mainline_context_warns_about_uneven_coverage(self) -> None:
        """2026-08-10 实测：题材/个股两张主线表各 35 个交易日，起点晚于板块表
        （88 天），早期日期查不到。空结果不是「当天没有主线」。

        契约刻意不写死日期——覆盖会随回填推进，写死当天就过期。
        """
        contract = reg._TOOL_CONTRACTS["mainline_context"]

        assert "不是每个交易日都齐全" in contract
        assert "不能据此说当天没有主线" in contract


def test_contracts_only_cover_tools_that_exist() -> None:
    """契约表不能引用已经不存在的工具名，否则它会静默失效。"""
    assert set(reg._TOOL_CONTRACTS) <= set(reg._DEFAULT_TOOL_METADATA)


class TestDoubleEncodedQueryIsUnwrappedAndDeclared:
    """模型把参数对象又 JSON 编码一遍时，拆回来**并且说出来**。

    失败形状（2026-08-12 历史对账，扫 44564 份 run 产物）：``query`` 的值本身
    又是一个 JSON 串，检索器拿着那串花括号做全文检索，必然空手。
    **551 次 query 类调用里 276 次（50%）是这个形状**，kb_search 高达 83%。

    同工具内部的对照（聚合相关性会误导，必须按工具分开看）：
    evidence_search 包了 100% 空手 (14/14) vs 没包 37% (7/19)；
    web_search 100% (4/4) vs 14% (4/28)；
    但 news_search 46% vs 55%——**它解释不了 news_search**，别当成万能解释。

    ⚠ 只拆不说就是 ai-agent-book ch4 点名的**静默输入转换**（Cursor 静默转换
    弯引号那个案例）：模型反复失败且无法自行诊断。书里的要求是「必须在工具描述
    中加以说明，并在工具返回中明确告知模型」——所以本类的断言是**成对的**。
    """

    def test_single_key_wrapper_is_unwrapped(self) -> None:
        raw, note = reg.unwrap_double_encoded_query(
            {"query": '{"query":"瑞华泰 688323 聚酰亚胺薄膜"}'}
        )

        assert raw == {"query": "瑞华泰 688323 聚酰亚胺薄膜"}
        assert note

    def test_plain_query_is_untouched_and_silent(self) -> None:
        """常态是不转换。误拆会把模型真想搜的内容改掉，比不拆更糟。"""
        raw, note = reg.unwrap_double_encoded_query({"query": "瑞华泰 产能"})

        assert raw == {"query": "瑞华泰 产能"}
        assert note == ""

    def test_unrecognised_shapes_are_left_alone(self) -> None:
        """认不出来就别动（BUILD 模式 7）：多键、非 query 键、坏 JSON 一律原样退回。"""
        for payload in (
            {"query": '{"q":"瑞华泰"}'},
            {"query": '{"query":"a","extra":1}'},
            {"query": "{不是合法 JSON}"},
            {"query": "{}"},
        ):
            raw, note = reg.unwrap_double_encoded_query(payload)
            assert raw == payload
            assert note == ""

    def test_the_note_tells_the_model_what_to_do_next(self) -> None:
        """告知不能只说「改过了」，要说下次该怎么写——否则模型下一轮照旧。"""
        _raw, note = reg.unwrap_double_encoded_query({"query": '{"query":"x"}'})

        assert "不要再包一层" in note

    def test_the_schema_declares_the_normalization(self) -> None:
        """描述那一半：只做转换不声明，就是书里点名的静默输入转换。"""
        description = reg.QUERY_TOOL_PARAMETERS["properties"]["query"]["description"]

        assert "不要再包一层 JSON" in description
        assert "检索词本身" in description


class TestEvidenceLookupDeclaresItsExactMatchBoundary:
    """evidence_lookup 要的是**登记名本身**，不是检索短语。

    2026-08-12 历史对账 + 代码核对：``KnowledgeAdapter.get_evidence`` 的判据是
    ``item.get("target") != target``——**精确字符串相等**，无归一、无分词、无模糊。
    索引里有 23942 条、17.9MB，**一点都不空**；28/28 空手全部是形状不匹配。
    实测「瑞华泰」→3 条，「瑞华泰 688323 估值 PB 情景 保守 中性 乐观」→0 条。

    对照组证明这是形状问题而非数据问题：``graph_lookup`` 空手率 **0%**，
    因为它走 ``get_concept_matches`` 的打分模糊匹配，长 query 也能命中。

    ch4 §工具描述的艺术：「清晰列出工具的边界条件——做不到什么、不接受什么输入
    ——往往比描述能力本身更重要」。这条正是「不接受什么输入」。
    """

    def test_hint_states_the_exact_match_requirement(self) -> None:
        description = reg.query_parameters("evidence_lookup")["properties"]["query"][
            "description"
        ]

        assert "精确字符串匹配" in description
        assert "不要传检索短语" in description

    def test_hint_points_at_the_tool_that_resolves_names(self) -> None:
        """只说「不行」不够，要说「那该怎么办」——否则模型只能放弃。"""
        description = reg.query_parameters("evidence_lookup")["properties"]["query"][
            "description"
        ]

        assert "graph_lookup" in description

    def test_tools_without_a_special_shape_keep_the_generic_description(self) -> None:
        """只给形状确实不同的那几个写专属提示。

        每个工具都写一句会稀释掉真正重要的差异——这与契约表「没依据宁可留空」
        是同一条纪律。
        """
        generic = reg.query_parameters("kb_search")

        assert generic == dict(reg.QUERY_TOOL_PARAMETERS)

    def test_registry_actually_ships_the_per_tool_schema(self) -> None:
        """活性检查：提示写了但没接进 registry，等于没写。"""
        registry = default_registry(
            {
                "evidence_lookup": lambda *a, **k: None,
                "kb_search": lambda *a, **k: None,
            }
        )

        shipped = registry.resolve("evidence_lookup").parameters["properties"]["query"]

        assert "精确字符串匹配" in shipped["description"]
