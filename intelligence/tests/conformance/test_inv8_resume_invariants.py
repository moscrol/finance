"""INV-8 resume 五不变量（仅对声明 resumable 的后端）。

episode 身份不变 / task_frame_hash 校验 / 事件不丢 / 前缀不改写 / 必产新
model_turn。五不变量的唯一拥有点是 ``CallbackEpisodeSession._resume_validated``
（episode_session.py）；本条逐后端验证「真实 session 走 resume 后不变量
可观测地成立」，并对声明不支持的后端验证「机制确实不在场」。
"""

from __future__ import annotations

import pytest

from intelligence.services.agent_runtime import ResumableAgentRuntime
from intelligence.services.episode_session import EpisodeSessionError
from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    ScenarioProbe,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
    make_repair_goal,
)

INV = "INV-8"


def _scenario() -> tuple[ScriptedTurn, ...]:
    return (
        ScriptedTurn(
            tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),),
        ),
        ScriptedTurn(finish=completed_finish()),
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_resume_preserves_identity_history_and_produces_a_new_turn(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    task_id = f"conf-inv8-{backend.name}"
    context = make_context(frame, task_id=task_id)
    registry = make_registry(probe)
    driver = backend.build_driver()

    if verdict is Verdict.UNSUPPORTED_DECLARED:
        # codex：单发 run 上不造会话状态机是设计决定。断言机制确实不在场；
        # 若哪天它长出 start()，这条会红，逼人先更新能力声明表。
        run = driver.run(
            initial=_scenario(),
            frame=frame,
            context=context,
            registry=registry,
            probe=probe,
        )
        assert getattr(run.runtime, "start", None) is None, (
            f"{backend.name} 长出了 start()，声明表已过期"
        )
        assert not isinstance(run.runtime, ResumableAgentRuntime)
        return

    run = driver.start(
        initial=_scenario(),
        repairs=((ScriptedTurn(finish=completed_finish()),),),
        frame=frame,
        context=context,
        registry=registry,
        probe=probe,
    )
    try:
        session = run.session
        assert session is not None
        assert isinstance(run.runtime, ResumableAgentRuntime), (
            f"{backend.name} 声明 resumable 但不满足协议"
        )
        # 五不变量之一：episode 身份 = contract.task_id（仓内约定）。
        assert session.episode_id == task_id
        previous = session.outcome

        # 身份校验：goal 指向别的 episode 必须被拒。
        with pytest.raises(EpisodeSessionError, match="identity mismatch"):
            session.resume(make_repair_goal("someone-else"))

        updated = session.resume(make_repair_goal(task_id))
    finally:
        run.close()

    assert updated.task_frame_hash == previous.task_frame_hash, (
        "resume 改写了 task frame 身份"
    )
    assert len(updated.events) >= len(previous.events), "resume 丢弃了事件"
    assert tuple(updated.events[: len(previous.events)]) == previous.events, (
        "resume 改写了历史前缀"
    )
    new_events = updated.events[len(previous.events) :]
    assert any(event.kind == "model_turn" for event in new_events), (
        "resume 没有产生新的 model_turn"
    )
    assert getattr(run.session, "resume_count", 1) == 1
