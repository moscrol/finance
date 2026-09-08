"""INV-R3 恢复 = 读一份完整 ``EpisodeState`` 并 switch；不重放日志推断、不从缺席推断。

逐 phase × 逐 crash 前缀的 Tier A 套件在 ``intelligence/tests/test_episode_restore.py``；
这里是矩阵那一格：continuous 臂一次真崩溃前缀能恢复出下一动作、截止已过能闭合；
非适用臂验「确实不在场」——它们的 ``configure`` 事件不带 ``log_version`` 快照（没有 store、
没有程序计数器，也就没有可恢复的东西）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.episode_restore import restore_episode
from intelligence.services.episode_store import MemoryEpisodeStore
from intelligence.tests.conformance.backends import BACKENDS, BackendDescriptor, Verdict
from intelligence.tests.conformance.baseline import ratchet
from intelligence.tests.conformance.fixtures import (
    AUTHORIZED_TOOL,
    ScenarioProbe,
    ScriptedModelClient,
    ScriptedToolCall,
    ScriptedTurn,
    completed_finish,
    make_context,
    make_frame,
    make_registry,
)
from intelligence.tests.conformance.oracle import WriteOrderOracle
from intelligence.tests.conformance.races._drive import EffectAwareModel, effect_registry

INV = "INV-R3"

_SCENARIO = (
    ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
    ScriptedTurn(finish=completed_finish()),
)


def _crash_after_tool_intent(task_id: str) -> tuple[MemoryEpisodeStore, str]:
    """跑一遍不间断，再把日志截到「工具意图已落、结算未落」那一刻。

    不间断那一遍用写序 oracle 当 store（P4 公共件，``conformance/oracle.py``）：崩溃现场是从
    它的日志截出来的，所以先断言这份日志本身的写序是对的——三明治不成立的日志截出来的
    「现场」不是任何真实崩溃能留下的现场。
    """

    recording = WriteOrderOracle()
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=task_id, timeout=120.0)
    outcome = GLMAgentRuntime(
        client=EffectAwareModel(ScriptedModelClient(list(_SCENARIO), probe), recording),
        episode_store=recording,
    ).run(task_frame=frame, context=context, registry=effect_registry(recording))
    assert outcome.status == "completed"
    recording.assert_sandwich()
    events, _ = recording.load(task_id)
    intent = next(e for e in events if e.kind == "tool_request")
    # tools_pending 那份状态在意图之后立刻写；崩溃现场 = 意图为末条、状态为 tools_pending。
    crash = MemoryEpisodeStore()
    crash.append(task_id, events[: intent.sequence])
    from intelligence.services.episode_store import EpisodeState

    crash.put_state(
        task_id,
        EpisodeState(
            episode_id=task_id,
            phase="tools_pending",
            reserved_ids=(intent.payload["call_id"],),
            deadline_at=(datetime.now().astimezone() + timedelta(seconds=60)).isoformat(),
            last_sequence=intent.sequence,
            contract_snapshot=dict(events[0].payload),
        ),
    )
    return crash, str(intent.payload["call_id"])


def test_continuous_restores_next_action_from_state_not_from_log_shape() -> None:
    crash, call_id = _crash_after_tool_intent("conf-inv-r3-continuous")
    probe = ScenarioProbe()
    soon = datetime.now().astimezone()
    result = restore_episode(
        "conf-inv-r3-continuous", crash, registry=make_registry(probe), now=soon
    )
    assert result.disposition == "resumable"
    assert result.plan is not None and result.plan.action == "replay_tools"
    assert result.plan.call_ids == (call_id,)
    assert result.synthesized == ()
    assert crash.list_open() == ("conf-inv-r3-continuous",)


def test_continuous_closes_when_deadline_passed_and_lists_nothing_open() -> None:
    crash, call_id = _crash_after_tool_intent("conf-inv-r3-closed")
    later = datetime.now().astimezone() + timedelta(days=1)
    result = restore_episode("conf-inv-r3-closed", crash, now=later)
    assert result.disposition == "closed" and result.outcome is not None
    assert result.outcome.stop_reason == "interrupted"
    assert [e.kind for e in result.synthesized] == ["tool_error", "finish"]
    assert result.synthesized[0].payload["call_id"] == call_id
    assert crash.list_open() == ()


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda item: item.name)
def test_declared_arms_really_have_no_program_counter(
    backend: BackendDescriptor,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, backend.name)
    verdict = backend.verdict(INV)
    if verdict is Verdict.NOT_APPLICABLE:
        pytest.skip(f"declared not applicable: {backend.note(INV)}")

    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id=f"conf-inv-r3-{backend.name}")
    run = backend.build_driver().run(
        initial=_SCENARIO,
        frame=frame,
        context=context,
        registry=make_registry(probe),
        probe=probe,
    )
    configure = [e for e in run.outcome.events if e.kind == "configure"]
    if verdict is Verdict.SUPPORTED:
        assert configure and configure[0].sequence == 1, "支持 R3 的臂首条必须是配置快照"
        assert "log_version" in configure[0].payload and "tool_replay" in configure[0].payload
    else:
        assert all("log_version" not in e.payload for e in configure), (
            f"{backend.name} 声明 {verdict.value} 却带了 log_version 快照——先改 backends.py 声明表"
        )
