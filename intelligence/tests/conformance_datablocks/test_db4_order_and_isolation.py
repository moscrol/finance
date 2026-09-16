"""DB-4 汇总顺序=注册顺序（与完成顺序无关）+ 单块失败只降级 + 串并行等价。"""

from __future__ import annotations

import time

import pytest

from intelligence.services import ask_planner
from intelligence.tests.conformance_datablocks.baseline import ratchet
from intelligence.tests.conformance_datablocks.blocks import (
    BLOCK_NAMES,
    BlockProbe,
    probe_provider,
)

INV = "DB-4"


def test_summary_order_ignores_completion_order() -> None:
    """注册靠前的块故意最后完成：汇总仍须按注册顺序（无隐式顺序依赖）。"""

    probe = BlockProbe()
    total = len(BLOCK_NAMES)
    providers = [
        probe_provider(
            name,
            probe,
            # 注册序第 i 位睡 (total-i)ms：完成顺序恰与注册顺序相反。
            on_collect=(lambda wait_ms: lambda: time.sleep(wait_ms / 1000.0))(
                total - index
            ),
        )
        for index, name in enumerate(BLOCK_NAMES)
    ]
    outcomes = ask_planner.run_providers(providers)
    assert tuple(item.tag for item in outcomes) == BLOCK_NAMES, (
        "汇总顺序漂离注册顺序——evidence_text/引用编号将不再确定"
    )


def test_parallel_and_serial_summaries_are_identical() -> None:
    def build(probe: BlockProbe) -> list[ask_planner.DataBlockProvider]:
        return [probe_provider(name, probe) for name in BLOCK_NAMES]

    parallel = ask_planner.run_providers(build(BlockProbe()), parallel=True)
    serial = ask_planner.run_providers(build(BlockProbe()), parallel=False)
    assert [(o.tag, o.block, o.error) for o in parallel] == [
        (o.tag, o.block, o.error) for o in serial
    ], "并行只许是快，不许改变汇总内容"


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_one_block_failure_degrades_only_itself(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    probe = BlockProbe()
    providers = [
        probe_provider(
            name,
            probe,
            collect_error=(
                RuntimeError("探针下游故障") if name == block_name else None
            ),
        )
        for name in BLOCK_NAMES
    ]
    outcomes = ask_planner.run_providers(providers)
    assert tuple(item.tag for item in outcomes) == BLOCK_NAMES, "失败块不得挤掉别人"
    failed = next(item for item in outcomes if item.tag == block_name)
    assert failed.error == "RuntimeError: 探针下游故障", "错误必须留痕且带类型"
    assert failed.block == "" and failed.citation is None, (
        "失败块不得携带文本/引用——不静默造文本"
    )
    for outcome in outcomes:
        if outcome.tag != block_name:
            assert outcome.error == "" and outcome.block, "无辜块不得被拖垮"
