"""T-5 证据发射契约：产出可绑定的证据（带来源 / hash），供 grounding 对账。

evidence ledger 与 finish bindings 认的是 ``content_hash``；工具经注册表
执行后，带 hash 的证据必须出现在 ``ToolObservation.evidence_hashes``，
且 hash 集与 evidence 对齐（不多发、不漏发）。
"""

from __future__ import annotations

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.tests.conformance_tools.baseline import ratchet
from intelligence.tests.conformance_tools.tools import (
    TOOL_EVIDENCE_HASH,
    TOOL_NAMES,
    ToolProbe,
    make_tool_context,
    make_tool_registry,
    valid_arguments,
)

INV = "T-5"

_HASHLESS = AgentEvidence(
    tool="conformance",
    title="无 hash 的证据",
    detail="不可绑定，只作观察背景",
    source="conformance-double",
    source_date="2026-07-24",
    evidence_tier="L4",
    content_hash="",
)


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_bindable_evidence_carries_its_hash_into_the_observation(
    tool_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, tool_name)
    probe = ToolProbe()
    registry = make_tool_registry(probe, extra_evidence=(_HASHLESS,))
    spec = registry.resolve(tool_name)
    context = make_tool_context(
        task_id=f"conf-t5-{tool_name}",
        allowed_capabilities=(spec.capability,),
    )

    observation = registry.execute(
        tool_name,
        valid_arguments(spec),
        context=context,
        step_id=f"conf-t5-{tool_name}:tool:1",
    )

    assert TOOL_EVIDENCE_HASH in observation.evidence_hashes, (
        f"{tool_name} 带 hash 的证据没有进入 evidence_hashes，"
        "finish bindings 将无从引用它"
    )
    delivered_hashes = {
        item.content_hash for item in observation.evidence if item.content_hash
    }
    assert set(observation.evidence_hashes) == delivered_hashes, (
        f"{tool_name} 的 evidence_hashes 与实际交付证据不对齐："
        f"{observation.evidence_hashes} vs {sorted(delivered_hashes)}"
    )
    for item in observation.evidence:
        assert item.source, f"{tool_name} 交付了无来源证据"
