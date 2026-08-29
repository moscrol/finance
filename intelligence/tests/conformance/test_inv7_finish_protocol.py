"""INV-7 finish 协议：悬空引用被拒绝 / 修复，不直出。

脚本模型先输出 bindings 指向不存在证据 hash 的 FINAL_JSON → 后端必须拒绝
（留下显式拒绝痕迹）并给修复机会；无论走到哪个终态，completed 的 outcome
不得携带悬空绑定。
"""

from __future__ import annotations

import pytest

from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    MISSING_EVIDENCE_HASH,
    ScenarioProbe,
    ScriptedToolCall,
    ScriptedTurn,
    assert_no_dangling_bindings,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)

INV = "INV-7"


def _dangling_finish() -> dict[str, object]:
    return completed_finish(evidence_hashes=(MISSING_EVIDENCE_HASH,))


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_dangling_evidence_binding_is_rejected_not_shipped(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv7-{backend.name}")
    registry = make_registry(probe)

    # 轮1 取证；轮2 交悬空 finish（应被拒）；轮3 交合法 finish（修复机会）。
    # codex 的修复是 runtime 内的第二次命令 → repairs 里再给一份合法脚本。
    run = backend.build_driver().run(
        initial=(
            ScriptedTurn(
                tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
            ),
            ScriptedTurn(finish=_dangling_finish()),
            ScriptedTurn(finish=completed_finish()),
        ),
        repairs=((ScriptedTurn(finish=completed_finish()),),),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )

    # 无论后端把它修好（completed）还是压级（partial/invalid），悬空引用
    # 都不得出现在最终 outcome 里。
    assert_no_dangling_bindings(run.outcome)
    for binding in run.outcome.bindings:
        assert MISSING_EVIDENCE_HASH not in binding.evidence_hashes, (
            f"{backend.name} 把悬空引用原样带出了终态"
        )

    # 拒绝必须显式：要么 invalid_actions 计数，要么终态如实降级/带修复痕迹。
    explicitly_rejected = (
        run.outcome.usage.invalid_actions >= 1
        or run.outcome.status != "completed"
        or run.outcome.usage.llm_calls >= 2
    )
    assert explicitly_rejected, (
        f"{backend.name} 悬空 finish 没有任何显式拒绝/修复痕迹："
        f"status={run.outcome.status} invalid_actions="
        f"{run.outcome.usage.invalid_actions} llm_calls={run.outcome.usage.llm_calls}"
    )
