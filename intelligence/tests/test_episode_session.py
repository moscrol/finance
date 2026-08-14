from dataclasses import replace

import pytest

from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.episode_session import CallbackEpisodeSession, EpisodeSessionError
from intelligence.services.repair_coordinator import RepairGoal, CoverageDelta


def _outcome() -> AgentOutcome:
    return AgentOutcome(
        task_frame_hash="frame-1",
        status="partial",
        draft="缺少反方证据",
        evidence=(),
        traces=(),
        gaps=("counterpoint",),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": "frame-1"}),),
        bindings=(),
        usage=AgentUsage(llm_calls=1),
    )


def _goal(episode_id: str = "episode-1") -> RepairGoal:
    return RepairGoal(
        episode_id=episode_id,
        repair_goal_id="repair-1",
        cycle=1,
        missing_answer_elements=("counterpoint",),
        unsupported_claims=(),
        missing_evidence_modes=("news_search",),
        attempted_actions=("market_data:A股",),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=2,
        remaining_seconds=20,
    )


def test_resume_preserves_episode_identity_and_uses_one_callback() -> None:
    calls = []

    def resume(previous, goal):
        calls.append((previous, goal))
        return replace(
            previous,
            events=previous.events
            + (EpisodeEvent(2, "model_turn", {"phase": "repair"}),),
            draft="已执行同一 episode 的修复动作",
        )

    session = CallbackEpisodeSession(
        episode_id="episode-1",
        outcome=_outcome(),
        resume_callback=resume,
    )
    assert session.resume(_goal()).task_frame_hash == "frame-1"
    assert session.resume_count == 1
    assert calls[0][1].repair_goal_id == "repair-1"


def test_resume_rejects_callback_without_a_new_model_action() -> None:
    session = CallbackEpisodeSession(
        episode_id="episode-1",
        outcome=_outcome(),
        resume_callback=lambda previous, _goal: previous,
    )
    with pytest.raises(EpisodeSessionError, match="model action"):
        session.resume(_goal())


def test_resume_rejects_wrong_episode_and_closed_session() -> None:
    session = CallbackEpisodeSession(
        episode_id="episode-1",
        outcome=_outcome(),
        resume_callback=lambda previous, _goal: previous,
    )
    try:
        session.resume(_goal("episode-2"))
    except EpisodeSessionError:
        pass
    else:
        raise AssertionError("wrong episode must be rejected")
    session.close()
    try:
        session.resume(_goal())
    except EpisodeSessionError:
        pass
    else:
        raise AssertionError("closed session must reject resume")
