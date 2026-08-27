"""``produces`` 声明 + 事前可满足性预检（fail-open）的测试。

核心不变量：**声明不全只会漏抓，不会误拦**。一个不完整的 produces 表如果能
造成误拦，它就成了新的静默失败源，比不做更糟。

预检的三种状态：
- ``covered``：至少一个工具声明了该 output_id → 放行
- ``unknown``：没有工具声明过它，也没人有非空 produces → 放行
- ``suspicious``：有工具声明了 produces，但没人含这个 id → 送裁定，不拦
"""
from __future__ import annotations


from intelligence.services import research_tool_registry as reg


def _spec(
    name: str,
    *,
    produces: frozenset[str] = frozenset(),
) -> reg.ToolSpec:
    return reg.ToolSpec(
        name=name,
        capability=name,
        description=f"test {name}",
        cost="local",
        freshness="stable",
        runner=lambda *a, **k: None,
        produces=produces,
    )


# ---------------------------------------------------------------------------
# produces 字段
# ---------------------------------------------------------------------------


class TestProducesField:
    def test_default_produces_is_empty_frozenset(self) -> None:
        spec = reg.ToolSpec(
            name="t",
            capability="t",
            description="d",
            cost="local",
            freshness="stable",
            runner=lambda *a, **k: None,
        )
        assert spec.produces == frozenset()

    def test_produces_accepts_frozenset(self) -> None:
        spec = _spec("t", produces=frozenset({"a", "b"}))
        assert spec.produces == frozenset({"a", "b"})

    def test_produces_coerces_set_to_frozenset(self) -> None:
        """传 set 进来会被自动冻结——和 parameters 的 _freeze_json 一致。"""
        spec = reg.ToolSpec(
            name="t",
            capability="t",
            description="d",
            cost="local",
            freshness="stable",
            runner=lambda *a, **k: None,
            produces={"a", "b"},  # type: ignore[arg-type]
        )
        assert isinstance(spec.produces, frozenset)
        assert spec.produces == frozenset({"a", "b"})

    def test_produces_itself_is_hashable(self) -> None:
        """produces 字段本身是 frozenset，可哈希。

        ToolSpec 整体因为 parameters(MappingProxyType) 不可哈希——那是既有约束，
        不在本轮修改范围。这里只钉 produces 字段本身的可哈希性。
        """
        spec = _spec("t", produces=frozenset({"a"}))
        assert hash(spec.produces) == hash(frozenset({"a"}))


class TestDefaultRegistryCarriesProduces:
    """default_registry 必须把 _DEFAULT_TOOL_METADATA 里的 produces 传进 ToolSpec。"""

    def test_all_default_tools_have_produces(self) -> None:
        registry = reg.default_registry(
            {name: lambda *a, **k: None for name in reg._DEFAULT_TOOL_METADATA}
        )
        for spec in registry.authorized_specs():
            # 每个默认工具都必须有 produces 字段（可以是空 frozenset，但字段必须存在）
            assert isinstance(spec.produces, frozenset)

    def test_market_data_declares_expected_outputs(self) -> None:
        """market_data 的 runner 代码路径确认它输出盘面快照和行情事实。"""
        registry = reg.default_registry(
            {name: lambda *a, **k: None for name in reg._DEFAULT_TOOL_METADATA}
        )
        market_spec = registry.resolve("market_data")
        assert "current_baseline" in market_spec.produces
        assert "market_summary" in market_spec.produces
        assert "supporting_evidence" in market_spec.produces

    def test_graph_lookup_declares_chain_mapping(self) -> None:
        """graph_lookup 的 runner 返回概念匹配和公司暴露——chain_mapping 的来源。"""
        registry = reg.default_registry(
            {name: lambda *a, **k: None for name in reg._DEFAULT_TOOL_METADATA}
        )
        graph_spec = registry.resolve("graph_lookup")
        assert "chain_mapping" in graph_spec.produces
        assert "company_mapping" in graph_spec.produces

    def test_financial_data_declares_financial_assessment(self) -> None:
        """financial_data 的 runner 返回逐季财报——financial_assessment 的来源。"""
        registry = reg.default_registry(
            {name: lambda *a, **k: None for name in reg._DEFAULT_TOOL_METADATA}
        )
        fin_spec = registry.resolve("financial_data")
        assert "financial_assessment" in fin_spec.produces
        assert "metric_evidence" in fin_spec.produces

    def test_memory_lookup_declares_prime_memory_only(self) -> None:
        """memory_lookup 只声明先验槽，不声明市场事实类产出。

        旧词表里的条目全是市场事实（supporting_evidence / event_facts /
        fact_value / market_summary…），本工具按定义只回用户自己过去的判断。
        残差地板给了它一格 ``prime_memory`` 之后，produces 必须声明这一格，
        否则可满足性预检会把它当成漏抓；仍然不能填市场事实 id。
        """
        registry = reg.default_registry(
            {name: lambda *a, **k: None for name in reg._DEFAULT_TOOL_METADATA}
        )
        spec = registry.resolve("memory_lookup")
        assert spec.produces == frozenset({"prime_memory"})
        assert "supporting_evidence" not in spec.produces


# ---------------------------------------------------------------------------
# check_satisfiability — fail-open 核心
# ---------------------------------------------------------------------------


class TestCheckSatisfiability:
    """钉住 fail-open 行为：声明不全只会漏抓，不会误拦。"""

    def test_covered_output_is_covered(self) -> None:
        """有工具声明该 output_id → covered。"""
        specs = (
            _spec("market_data", produces=frozenset({"current_baseline"})),
            _spec("web_search", produces=frozenset({"event_facts"})),
        )
        results = reg.check_satisfiability(("current_baseline",), specs)

        assert len(results) == 1
        assert results[0].status == "covered"
        assert results[0].contributing_tools == ("market_data",)

    def test_covered_by_multiple_tools(self) -> None:
        """多个工具声明同一个 output → 全列出来。"""
        specs = (
            _spec("a", produces=frozenset({"supporting_evidence"})),
            _spec("b", produces=frozenset({"supporting_evidence"})),
        )
        results = reg.check_satisfiability(("supporting_evidence",), specs)

        assert results[0].status == "covered"
        assert set(results[0].contributing_tools) == {"a", "b"}

    # ── fail-open 的核心测试 ──────────────────────────────────────────

    def test_unknown_output_is_not_blocked_when_no_tool_declares_anything(self) -> None:
        """所有工具的 produces 都留空 → 完全未知 → unknown（放行）。

        这就是 fail-open 的核心：一个保守的（全空的）声明表不能造成误拦。
        """
        specs = (
            _spec("a"),
            _spec("b"),
        )
        results = reg.check_satisfiability(
            ("some_output_nobody_declares",), specs
        )

        assert results[0].status == "unknown"

    def test_unknown_output_is_not_blocked_when_partially_declared(self) -> None:
        """有工具声明了 produces，但没人声明这个 id → suspicious（送裁定，不拦）。

        suspicious 不是 fail——它只是标记「可能需要额外工具」，交由调用方裁定。
        预检函数本身不做任何拦截。
        """
        specs = (
            _spec("a", produces=frozenset({"x", "y"})),
            _spec("b", produces=frozenset({"z"})),
        )
        results = reg.check_satisfiability(
            ("some_output_nobody_declares",), specs
        )

        # suspicious 是送裁定的信号，不是 fail-open 的反面
        assert results[0].status == "suspicious"
        # 但它绝对不应该是 covered
        assert results[0].status != "covered"

    def test_mixed_covered_and_unknown(self) -> None:
        """一批 required_outputs 里有些 covered、有些 unknown/suspicious。"""
        specs = (
            _spec("market_data", produces=frozenset({"current_baseline"})),
            _spec("web_search", produces=frozenset({"event_facts"})),
        )
        results = reg.check_satisfiability(
            ("current_baseline", "counterpoint"), specs
        )

        assert results[0].output_id == "current_baseline"
        assert results[0].status == "covered"
        assert results[1].output_id == "counterpoint"
        assert results[1].status == "suspicious"

    def test_blank_produces_tool_neither_contributes_nor_suppresses(self) -> None:
        """空 produces 工具「没表态」：既不当贡献者，也不把 unknown 推成 suspicious。

        判据看的是 ``declared_specs``——有没有工具真表过态，不是并集内容。
        空声明工具若被算作表过态，「全场无人表态」就会被误判成「所有人都说
        不产出它」，于是一个保守留空的注册表会把每个 output 都标可疑。那正是
        fail-open 要防的噪声源。

        第一段断言是这条的变异闸门：把 ``declared_specs`` 的过滤去掉，它立刻
        翻成 suspicious。
        """
        blank = _spec("memory_lookup")

        alone = reg.check_satisfiability(("anything",), (blank,))
        assert alone[0].status == "unknown"

        # 一旦有工具真表了态，判据由它决定；空声明工具不混进贡献者名单
        mixed = reg.check_satisfiability(
            ("y",), (blank, _spec("a", produces=frozenset({"x"})))
        )
        assert mixed[0].status == "suspicious"
        assert "memory_lookup" not in mixed[0].contributing_tools

    def test_default_registry_never_produces_a_blocking_status(self) -> None:
        """端到端不变量：真实注册表下，任何 output 都不会得到拦截性状态。

        covered / unknown / suspicious 三者都放行。这条测试的作用是：将来
        有人给 check_satisfiability 加第四种状态（比如 blocked）时，必须先
        回来面对「fail-open 是否还成立」这个问题，而不是悄悄改变语义。
        """
        registry = reg.default_registry(
            {name: lambda *a, **k: None for name in reg._DEFAULT_TOOL_METADATA}
        )
        specs = registry.authorized_specs()
        probes = ("supporting_evidence", "fact_value", "output_nobody_will_ever_declare")

        statuses = {
            check.status
            for output_id in probes
            for check in reg.check_satisfiability((output_id,), specs)
        }
        assert statuses <= {"covered", "unknown", "suspicious"}

    def test_empty_required_outputs_returns_empty(self) -> None:
        specs = (_spec("a", produces=frozenset({"x"})),)
        assert reg.check_satisfiability((), specs) == ()

    def test_empty_authorized_specs_makes_everything_unknown(self) -> None:
        """没有授权工具 → 所有 output 都是 unknown（放行）。"""
        results = reg.check_satisfiability(("x", "y"), ())
        assert all(r.status == "unknown" for r in results)


# ---------------------------------------------------------------------------
# 声明完整性元测试
# ---------------------------------------------------------------------------


class TestDeclarationCompleteness:
    """_DEFAULT_TOOL_METADATA 的 produces 声明质量检查。"""

    def test_all_metadata_entries_have_four_fields(self) -> None:
        """每个工具的 metadata 元组必须有 4 个字段（capability, desc, freshness, produces）。"""
        for name, entry in reg._DEFAULT_TOOL_METADATA.items():
            assert len(entry) == 4, f"{name} has {len(entry)} fields, expected 4"
            assert isinstance(entry[3], frozenset), f"{name}.produces is not frozenset"

    def test_produces_only_contains_known_output_ids(self) -> None:
        """produces 声明的 id 应该在已知 output_id 词表内。

        词表来自 task_frame.py 题型映射 + query_understanding.py operator 映射。
        如果声明了不在词表里的 id，要么是拼写错误，要么是词表本身需要更新。
        """
        # 这里只做最小校验：produces 里的 id 不应该和工具名/capability 冲突
        for name, (_cap, _desc, _fresh, produces) in reg._DEFAULT_TOOL_METADATA.items():
            for output_id in produces:
                # output_id 不应该等于工具名（那是 capability，不是 output）
                assert output_id != name, (
                    f"{name}.produces contains its own name as output_id"
                )


# ---------------------------------------------------------------------------
# 与 structural_verifier 历史 fulfilled 记录的一致性
# ---------------------------------------------------------------------------
#
# ⚠️ 作用域限定：这一节只约束 **structural_verifier（continuous 壳）** 路径。
# 冻结计数取自 ``structural_verifier.completion.outputs[].status``，不是
# ``task_fulfillment``（ask 路径）。两套门禁用不同的 output_id 词表——SV 里的
# direct_answer / risk_signals 在 TF_hooks 里没有对应条目（见 c13cb788 的三方
# 对比结论）。将来如果 ask 路径也有了可采集的 fulfilled 历史，需要另起一张表，
# 不能把这里的常量扩展成「全局覆盖」。
#
# 这一节回答的是手写 produces 的**唯一可证伪方向**：
#
#   如果某个 output_id 在真实 run 里被判过 fulfilled，那就证明这套工具确实能
#   产出它。此时没有任何工具声明它 —— 那是声明表的一个**可证明的洞**。
#
# 反方向（声明了但历史里没见过）**不是错误**：样本只有 45 个 episode，覆盖不到
# 的题型本来就不会出现。把它断言成错误等于要求声明表不能超前于样本，那会逼着
# 未来的人为了让测试变绿而删掉正确的声明。这就是 fail-open 在测试层的体现。
#
# 归一必须走 ``_LEGACY_OUTPUT_ALIASES``（从 conversation_orchestrator 导入，
# **不抄第二份**）：历史记录里的 direct_answer / evidence_boundary /
# continuation_conditions 等是别名槽位，归一后才能和声明表对齐。抄一份表进来就
# 等于把那边的修改和这里的断言解耦，正是本轮要消除的第二事实源问题。
#
# 数据来源（2026-08-06 采集，45 个 continuous-episode.json，取
# ``structural_verifier.completion.outputs[].status``）：
#
#     direct_answer          fulfilled=4  missing=24
#     direct_assessment      fulfilled=3  missing=11
#     evidence_boundary      fulfilled=5  missing=27
#     risk_signals           fulfilled=3  missing=1
#     supporting_evidence    fulfilled=3  missing=1
#
# 冻结成字面量而不是运行时扫描，因为那些 episode 文件在 tmp/ 和
# ~/agent-memory/.foresight/ 下，既不在仓库里也会被清理——读它们的测试会
# flaky-by-construction。要更新这张表就重跑一次采集并连同计数一起改。
_SV_FULFILLED_OUTPUT_IDS = frozenset(
    {
        "direct_answer",
        "direct_assessment",
        "evidence_boundary",
        "risk_signals",
        "supporting_evidence",
    }
)


def _normalize_output_id(output_id: str) -> str:
    from intelligence.runtime.conversation_orchestrator import (
        _LEGACY_OUTPUT_ALIASES,
    )

    return _LEGACY_OUTPUT_ALIASES.get(output_id, output_id)


def _declared_output_ids() -> frozenset[str]:
    return frozenset(
        _normalize_output_id(output_id)
        for _cap, _desc, _fresh, produces in reg._DEFAULT_TOOL_METADATA.values()
        for output_id in produces
    )


class TestProducesMatchesHistory:
    def test_every_historically_fulfilled_output_is_declared(self) -> None:
        """真实 run 里 fulfilled 过的 output，必须有工具声明能产出它。

        这是手写 produces 唯一能被历史证伪的方向。实测抓到过一个真洞：
        risk_signals 在三个 market_watch episode 里 fulfilled，绑定它的
        provider 是 duckdb_semantic_query（finance_query）、agent:market_data、
        agent:mainline_context，而这三个工具当时都没声明它。
        """
        declared = _declared_output_ids()
        undeclared = sorted(
            _normalize_output_id(output_id)
            for output_id in _SV_FULFILLED_OUTPUT_IDS
            if _normalize_output_id(output_id) not in declared
        )

        assert not undeclared, (
            "这些 output 在真实 run 里 fulfilled 过，但没有任何工具声明能产出："
            f"{undeclared}。要么补上对应工具的 produces，要么说明是哪个工具真的"
            "产出了它。"
        )

    def test_declaring_more_than_history_is_allowed(self) -> None:
        """声明超前于样本不是错误——这是 fail-open 在测试层的体现。

        45 个 episode 覆盖不到的题型（估值、财务、产业链映射）本来就不会出现在
        历史里。把「声明了但没见过」断言成错误，会逼着后来的人为了让测试变绿而
        删掉正确的声明。
        """
        declared = _declared_output_ids()
        normalized_history = {
            _normalize_output_id(item) for item in _SV_FULFILLED_OUTPUT_IDS
        }

        # 确实存在「声明了但历史样本里没有」的 id，且这不导致失败。
        assert declared - normalized_history

    def test_alias_table_is_imported_not_copied(self) -> None:
        """归一必须用 orchestrator 那张表，不能在测试里抄第二份。

        抄一份就等于把 legacy_aliases 的修改和这里的断言解耦——那正是本轮
        要消除的第二事实源问题。
        """
        from intelligence.runtime.conversation_orchestrator import (
            _LEGACY_OUTPUT_ALIASES,
        )

        # 别名真的在起作用：历史里的 direct_answer 归一到 direct_assessment。
        assert _LEGACY_OUTPUT_ALIASES["direct_answer"] == "direct_assessment"
        assert _normalize_output_id("direct_answer") == "direct_assessment"

    def test_normalization_is_what_makes_evidence_boundary_align(self) -> None:
        """evidence_boundary fulfilled 过 5 次，但没有工具直接声明这个 id。

        它归一到 counterpoint，而 evidence_search 声明了 counterpoint。这条钉住
        「归一是对齐的必要条件」——去掉归一，这个 output 会变成假阳性的洞。
        """
        assert _normalize_output_id("evidence_boundary") == "counterpoint"

        raw_declared = frozenset(
            output_id
            for _cap, _desc, _fresh, produces in reg._DEFAULT_TOOL_METADATA.values()
            for output_id in produces
        )
        assert "evidence_boundary" not in raw_declared
        assert "counterpoint" in raw_declared
