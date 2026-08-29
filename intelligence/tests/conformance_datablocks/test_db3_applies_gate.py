"""DB-3 门控为假时 collect 零调用；为真时恰好一次并保 (块文本, 引用) 形状。"""

from __future__ import annotations

import pytest

from intelligence.services import ask_planner
from intelligence.tests.conformance_datablocks.baseline import ratchet
from intelligence.tests.conformance_datablocks.blocks import (
    BLOCK_NAMES,
    BlockProbe,
    probe_provider,
)

INV = "DB-3"


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_applies_false_means_collect_is_never_called(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    probe = BlockProbe()
    providers = [
        probe_provider(name, probe, applies=(name != block_name))
        for name in BLOCK_NAMES
    ]
    outcomes = ask_planner.run_providers(providers)
    assert block_name not in probe.collected, (
        f"{block_name} 的 applies() 为假，collect 仍被调用——门控被绕过"
    )
    assert block_name not in {outcome.tag for outcome in outcomes}, (
        "未命中的块不得出现在汇总里（零执行且零占位）"
    )


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_applies_true_collects_exactly_once_with_contract_shape(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    probe = BlockProbe()
    citation = object()
    providers = [
        probe_provider(
            name,
            probe,
            applies=(name == block_name),
            block_text=f"{name} 的证据文本",
            citation=citation,
        )
        for name in BLOCK_NAMES
    ]
    outcomes = ask_planner.run_providers(providers)
    assert probe.collected == [block_name], "命中块必须恰好取数一次"
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.tag == block_name
    assert outcome.block == f"{block_name} 的证据文本"
    assert outcome.citation is citation, "引用必须原样带回（可绑定性的前提）"
    assert outcome.error == ""
