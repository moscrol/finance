"""T-1 返回形状守 ``ToolObservation`` 契约（公共字段齐全、类型正确）。

逐工具经 ``registry.execute`` 跑探针 runner，断言归一化后的观察对象；
另断言 ``ToolRunnerAdapter`` 对 legacy 元组 / ``ToolRunResult`` / 非法返回
的归一化契约（它是「N 个 runner 形状 → 一个真类型」的收口点）。
"""

from __future__ import annotations

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import (
    ToolObservation,
    ToolRunnerAdapter,
    ToolRunResult,
)
from intelligence.tests.conformance_tools.baseline import ratchet
from intelligence.tests.conformance_tools.tools import (
    TOOL_EVIDENCE_HASH,
    TOOL_NAMES,
    ToolProbe,
    make_tool_context,
    make_tool_registry,
    valid_arguments,
)

INV = "T-1"


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_execute_returns_a_well_formed_observation(
    tool_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, tool_name)
    probe = ToolProbe()
    registry = make_tool_registry(probe)
    spec = registry.resolve(tool_name)
    context = make_tool_context(
        task_id=f"conf-t1-{tool_name}",
        allowed_capabilities=(spec.capability,),
    )

    observation = registry.execute(
        tool_name,
        valid_arguments(spec),
        context=context,
        step_id=f"conf-t1-{tool_name}:tool:1",
    )

    assert isinstance(observation, ToolObservation)
    assert observation.tool == tool_name
    assert isinstance(observation.query, str)
    assert isinstance(observation.observation, str) and observation.observation
    assert isinstance(observation.evidence, tuple)
    assert all(isinstance(item, AgentEvidence) for item in observation.evidence)
    assert isinstance(observation.trace, ProviderTrace)
    assert isinstance(observation.gaps, tuple)
    assert isinstance(observation.evidence_hashes, tuple)
    assert isinstance(observation.dataset, str) and observation.dataset
    assert isinstance(observation.telemetry, dict)
    assert probe.invocations and probe.invocations[0][0] == tool_name


def _context_stub() -> AgentToolContext:
    from intelligence.services.research_contract import ResearchDeadline

    return AgentToolContext(
        ResearchDeadline.from_timeout(5.0),
        lambda: False,
        None,
    )


def test_adapter_normalizes_legacy_three_tuple() -> None:
    trace = ProviderTrace("double:x", "x", "success")
    adapter = ToolRunnerAdapter(lambda _value, _context: ([], "观察", trace))
    result = adapter("q", _context_stub())
    assert isinstance(result, ToolRunResult)
    assert result.observation == "观察"
    assert result.gaps == ()


def test_adapter_normalizes_legacy_four_tuple_with_gaps() -> None:
    trace = ProviderTrace("double:x", "x", "success")
    adapter = ToolRunnerAdapter(
        lambda _value, _context: ([], "观察", trace, ["缺口A", "缺口A", ""])
    )
    result = adapter("q", _context_stub())
    assert result.gaps == ("缺口A",)


def test_adapter_passes_through_tool_run_result() -> None:
    trace = ProviderTrace("double:x", "x", "success")
    payload = ToolRunResult(evidence=(), observation="原样", trace=trace)
    adapter = ToolRunnerAdapter(lambda _value, _context: payload)
    assert adapter("q", _context_stub()) is payload


def test_adapter_rejects_an_invalid_runner_return_shape() -> None:
    adapter = ToolRunnerAdapter(lambda _value, _context: "not-a-result")
    with pytest.raises(TypeError, match="must return ToolRunResult"):
        adapter("q", _context_stub())


def test_evidence_hash_constant_matches_probe() -> None:
    """探针发的 hash 与常量一致——其他 T 文件的断言以它为锚。"""

    probe = ToolProbe()
    registry = make_tool_registry(probe)
    spec = registry.resolve(TOOL_NAMES[0])
    context = make_tool_context(
        task_id="conf-t1-anchor",
        allowed_capabilities=(spec.capability,),
    )
    observation = registry.execute(
        TOOL_NAMES[0],
        valid_arguments(spec),
        context=context,
        step_id="conf-t1-anchor:tool:1",
    )
    assert TOOL_EVIDENCE_HASH in observation.evidence_hashes
