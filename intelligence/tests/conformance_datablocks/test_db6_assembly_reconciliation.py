"""DB-6 装配对账（AST 只读源码，不执行 ask.py）：注册了 ⇔ 够得着。

这是数据块缝的「tool-reachability」等价物：工具缝的装配一致性有 pre-commit
门禁看守，数据块缝此前没有任何对账面——「注册了但没装配」「装配 label 漂离
注册 label」「注册块绕开 enabled_providers 门控」都只有人读代码才会发现。
首轮即抓到 MARKET_DAILY 绕门控（阳性对照，入 baseline）。
"""

from __future__ import annotations

import pytest

from intelligence.services.evidence_registry import REGISTRY
from intelligence.tests.conformance_datablocks.baseline import ratchet
from intelligence.tests.conformance_datablocks.blocks import (
    BLOCK_NAMES,
    BYPASS_BLOCKS,
    assembled_provider_names_and_labels,
    gate_call_present,
)

INV = "DB-6"


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_registered_block_is_assembled_or_gated_bypass(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    """每个注册块要么走构造面，要么是「留有门控调用」的显式旁路。

    两者都不是 = 注册表对它的 ``enabled_providers`` 承诺落空（裁剪不生效），
    与「授予的额度必须真的传到最下游执行者」同族失败形状。
    """

    ratchet(request, INV, block_name)
    assembled = assembled_provider_names_and_labels()
    constructed = block_name in assembled
    gated_bypass = block_name in BYPASS_BLOCKS and gate_call_present(block_name)
    assert constructed or gated_bypass, (
        f"{block_name} 注册了但既不经 DataBlockProvider 构造、也无"
        " provider_enabled 门控调用——enabled_providers 对它裁剪无效"
    )


def test_no_orphan_constructions() -> None:
    assembled = assembled_provider_names_and_labels()
    orphaned = set(assembled) - set(BLOCK_NAMES)
    assert not orphaned, (
        f"装配了但没注册（enabled_providers 门控 KeyError 炸运行时）：{sorted(orphaned)}"
    )
    doubly = set(assembled) & set(BYPASS_BLOCKS)
    assert not doubly, f"旁路块不得同时出现在构造面（双重取数）：{sorted(doubly)}"


def test_assembled_labels_match_registry_labels() -> None:
    assembled = assembled_provider_names_and_labels()
    registry_labels = {spec.name: spec.label for spec in REGISTRY}
    drifted = {
        name: (label, registry_labels[name])
        for name, label in assembled.items()
        if label != registry_labels[name]
    }
    assert not drifted, f"装配 label 漂离注册 label（trace/引用会认错块）：{drifted}"


def test_assembly_order_follows_registry_order() -> None:
    """构造顺序必须是注册顺序在「构造面块」上的投影。

    「注册顺序即汇总顺序」是注册表的公开承诺（evidence_registry docstring），
    运行器按输入序汇总——装配侧插队会让 evidence_text/引用编号静默漂移。
    """

    assembled_order = tuple(assembled_provider_names_and_labels())
    expected_order = tuple(
        name for name in BLOCK_NAMES if name in set(assembled_order)
    )
    assert assembled_order == expected_order, "ask.py 的构造顺序与注册顺序不一致"


@pytest.mark.parametrize("block_name", BYPASS_BLOCKS)
def test_bypass_blocks_keep_their_gate(block_name: str) -> None:
    assert gate_call_present(block_name), (
        f"旁路块 {block_name} 的 provider_enabled 门控调用消失——"
        "旁路的合法性全靠这条门控"
    )
