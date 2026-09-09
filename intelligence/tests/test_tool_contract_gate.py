"""§3.6 第 8 条：进注册表的每个工具都要有行为契约，否则装配期抛。

首跑读数（2026-09-03）：生产装配 ``build_episode_registry`` 里 ``evidence_search`` /
``finance_query`` / ``memory_lookup`` 三个 spec 是裸的——``_TOOL_CONTRACTS`` 早为它们写好
了条目（含 2026-08-10 冷调用 28.2s、25 行截断、空命中语义等实测依据），只是装配面自建
spec 时没接 ``contract=``，模型从没见过。下面第三个用例是那次读数的回归钉。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.services import research_tool_registry as reg
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.research_tool_registry import (
    ToolContractMissing,
    ToolSpec,
    default_registry,
    require_tool_contracts,
)
from intelligence.services.task_frame import TaskFrame


def _stub_runner(*_args, **_kwargs):
    return None


def test_require_tool_contracts_names_every_bare_tool() -> None:
    specs = (
        ToolSpec(
            name="bare_a",
            capability="bare_a",
            description="x",
            cost="local",
            freshness="stable",
            runner=_stub_runner,
        ),
        ToolSpec(
            name="dressed",
            capability="dressed",
            description="x",
            contract="空结果=证据缺口；as_of 取披露日；参数必读。",
            cost="local",
            freshness="stable",
            runner=_stub_runner,
        ),
        ToolSpec(
            name="bare_b",
            capability="bare_b",
            description="x",
            contract="   ",
            cost="local",
            freshness="stable",
            runner=_stub_runner,
        ),
    )
    with pytest.raises(ToolContractMissing) as excinfo:
        require_tool_contracts(specs)
    message = str(excinfo.value)
    assert "bare_a, bare_b" in message
    assert "dressed" not in message
    assert "_TOOL_CONTRACTS" in message


def test_default_registry_refuses_a_metadata_entry_without_a_contract(monkeypatch) -> None:
    """有牙：往注册表元数据里塞一个无契约 stub → 装配期红。"""

    monkeypatch.setitem(
        reg._DEFAULT_TOOL_METADATA,
        "finance_shareholders",
        ("finance_shareholders", "十大股东（stub，无源无契约）", "current", frozenset()),
    )
    assert "finance_shareholders" not in reg._TOOL_CONTRACTS
    with pytest.raises(ToolContractMissing, match="finance_shareholders"):
        default_registry({"finance_shareholders": _stub_runner, "market_data": _stub_runner})
    # 不带 stub 时照常装配——门只拦裸的。
    registry = default_registry({"market_data": _stub_runner})
    assert registry.names() == ("market_data",)


def test_every_default_metadata_tool_has_a_contract_entry() -> None:
    bare = sorted(set(reg._DEFAULT_TOOL_METADATA) - set(reg._TOOL_CONTRACTS))
    assert bare == [], f"_DEFAULT_TOOL_METADATA 里无契约的工具：{bare}"


def test_production_episode_registry_ships_no_bare_tool(tmp_path: Path) -> None:
    """回归钉：装配面自建的 finance_query / evidence_search / memory_lookup 要带契约。"""

    frame = TaskFrame(
        raw_question="瑞华泰估值怎么看",
        user_goal="形成直接判断",
        question_type="stock_deep_dive",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_multi_layer_evidence",
        confidence=0.9,
    )
    context = build_episode_context(
        frame,
        task_id="contract-gate-production",
        # capability 全集，不是工具名全集（历史三工具共享 finance_query）。
        capabilities=tuple(reg.DEFAULT_RESEARCH_CAPABILITIES),
        timeout=30.0,
        today="2026-09-02",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        memory_user="contract-gate-user",
        memory_users_root=tmp_path / "users",
    )
    specs = {spec.name: spec for spec in registry.authorized_specs()}
    assert {"finance_query", "evidence_search", "memory_lookup"}.issubset(specs)
    bare = sorted(name for name, spec in specs.items() if not spec.contract.strip())
    assert bare == []
    for name in ("finance_query", "evidence_search", "memory_lookup"):
        assert specs[name].contract == reg._TOOL_CONTRACTS[name]
        definition = next(
            item["function"]
            for item in registry.tool_definitions(context.contract.allowed_capabilities)
            if item["function"]["name"] == name
        )
        # 契约跟着工具描述走进 function-call schema——这才是模型看到的那一份。
        assert reg._TOOL_CONTRACTS[name] in definition["description"]
