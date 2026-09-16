"""DB-5 截止窗已烧穿时零取数，且降级出口如实留痕（不造文本）。"""

from __future__ import annotations

import pytest

from intelligence.services import ask_planner
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.conformance_datablocks.baseline import ratchet
from intelligence.tests.conformance_datablocks.blocks import (
    BLOCK_NAMES,
    BlockProbe,
    probe_provider,
)

INV = "DB-5"


@pytest.mark.parametrize("parallel", (True, False), ids=("parallel", "serial"))
@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_expired_deadline_means_zero_collect_and_honest_error(
    block_name: str,
    parallel: bool,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    probe = BlockProbe()
    providers = [
        probe_provider(name, probe, applies=(name == block_name))
        for name in BLOCK_NAMES
    ]
    expired = ResearchDeadline.from_timeout(0.0)
    assert expired.expired
    outcomes = ask_planner.run_providers(
        providers, parallel=parallel, deadline=expired
    )
    assert probe.collected == [], "窗已烧穿仍取数——deadline 未被尊重"
    assert len(outcomes) == 1 and outcomes[0].tag == block_name
    assert outcomes[0].error == "ResearchDeadlineExceeded", "超窗必须显式留痕"
    assert outcomes[0].block == "" and outcomes[0].citation is None, (
        "超窗块不得携带文本/引用——不静默造文本"
    )
