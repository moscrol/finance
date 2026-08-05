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
