"""Whose episode is this? A checkpoint cannot answer that about itself.

Authorization already re-asks "what may this run do". These tests pin the other
half: "who is this run for". The interrupted run records the entry identity the
door verified; recovery only proceeds when the door presents the same identity
again. Absence is a value, not a wildcard -- an unbound checkpoint and a bound
caller are a mismatch in both directions.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_authorization import capture_authorization_snapshot
from intelligence.services.episode_entry_identity import (
    EntryIdentity,
    EpisodeEntryIdentity,
    capture_entry_identity,
)
from intelligence.services.episode_restore import RestoreUnavailable, restore_episode
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.tests.conformance.fixtures import (
    ScenarioProbe, make_context, make_frame, make_registry,
)
from intelligence.tests.conformance.races._drive import build_rig

# run_id / assistant_message_id 故意与 episode_id 同源（生产就是 f"{run_id}:{message_id}"），
# 用户与会话 id 则刻意取不同前缀——「身份不进提示词」那条断言要能分辨谁是谁。
OWNER = EntryIdentity(
    entry="workbench_conversation",
    user_id="user-alpha",
    conversation_id="conv-alpha",
    run_id="run-alpha",
    assistant_message_id="msg-alpha",
)
EPISODE_ID = "run-alpha:msg-alpha"
NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


def _authority(identity: EntryIdentity | None = OWNER, *, episode_id: str = EPISODE_ID):
    context = make_context(make_frame(), task_id=episode_id)
    context = replace(
        context,
        contract=replace(context.contract, task_frame_hash="tf"),
        entry_identity=None if identity is None else identity.bind(episode_id),
    )
    return {"context": context, "registry": make_registry(ScenarioProbe())}


def _crashed(store, identity: EntryIdentity | None = OWNER):
    """A model request went out, the process died before the settlement landed."""

    authority = _authority(identity)
    events = (
        EpisodeEvent(1, "task", {"task_frame_hash": "tf", "question": "q"}),
        EpisodeEvent(2, "prompt_assembled", {"system": "s", "user": "u"}),
        EpisodeEvent(3, "model_intent", {"turn_id": "turn-1", "phase": "planning"}),
    )
    cutoff = authority["context"].information_cutoff.as_of_date
    state = EpisodeState(
        episode_id=EPISODE_ID,
        phase="model_pending",
        reserved_ids=("turn-1",),
        deadline_at=(NOW + timedelta(minutes=2)).isoformat(),
        retry={"remaining": 0},
        last_sequence=len(events),
        authorization_snapshot=capture_authorization_snapshot(**authority),
        evidence_snapshot=EvidenceLedger(information_cutoff=cutoff).to_recovery_snapshot(
            episode_id=EPISODE_ID, presented_evidence=(),
        ),
        evidence_snapshot_sequence=len(events),
        entry_identity=capture_entry_identity(authority["context"]),
    )
    store.append(EPISODE_ID, events, sync=True)
    store.put_state(EPISODE_ID, state)
    return state


# ── 恢复门禁 ─────────────────────────────────────────────────────────────────


def test_the_entry_that_started_the_episode_gets_its_plan(tmp_path):
    store = JsonlEpisodeStore(tmp_path)
    _crashed(store)

    result = restore_episode(EPISODE_ID, store, now=NOW, **_authority())

    assert result.plan is not None and result.plan.action == "finalize"
    assert result.entry_identity_bound is True
    assert result.to_dict()["entry_identity_bound"] is True


@pytest.mark.parametrize("field", ["user_id", "conversation_id", "run_id", "assistant_message_id"])
def test_another_user_conversation_or_run_may_not_recover_the_episode(tmp_path, field):
    store = JsonlEpisodeStore(tmp_path)
    _crashed(store)
    intruder = replace(OWNER, **{field: f"other-{field}"})

    with pytest.raises(RestoreUnavailable, match="entry identity"):
        restore_episode(EPISODE_ID, store, now=NOW, **_authority(intruder))


def test_an_unbound_caller_may_not_recover_a_bound_episode(tmp_path):
    """CLI / 离线驱动没有门，就不能接管从门口进来的那一轮。"""

    store = JsonlEpisodeStore(tmp_path)
    _crashed(store)

    with pytest.raises(RestoreUnavailable, match="entry identity"):
        restore_episode(EPISODE_ID, store, now=NOW, **_authority(None))


def test_a_bound_caller_may_not_recover_an_unbound_episode(tmp_path):
    """反向同样拒绝：旧检查点没记主人，不等于「随便哪扇门都算它的主人」。"""

    store = JsonlEpisodeStore(tmp_path)
    _crashed(store, identity=None)

    with pytest.raises(RestoreUnavailable, match="entry identity"):
        restore_episode(EPISODE_ID, store, now=NOW, **_authority())

    unbound = restore_episode(EPISODE_ID, store, now=NOW, **_authority(None))
    assert unbound.entry_identity_bound is False


@pytest.mark.parametrize("expired", [False, True])
def test_identity_refusal_writes_nothing_even_when_the_deadline_has_passed(tmp_path, expired):
    """拒绝发生在合成之前：过期本会合成 finish 并覆写 done，错的身份一个字节也不许写。"""

    store = JsonlEpisodeStore(tmp_path)
    _crashed(store)
    before = store.load(EPISODE_ID)
    moment = NOW + timedelta(hours=1) if expired else NOW

    with pytest.raises(RestoreUnavailable, match="entry identity"):
        restore_episode(EPISODE_ID, store, now=moment, **_authority(replace(OWNER, user_id="user-beta")))

    assert JsonlEpisodeStore(tmp_path).load(EPISODE_ID) == before


@pytest.mark.parametrize("expired", [False, True])
def test_recovery_never_unbinds_the_episode_it_just_read(tmp_path, expired):
    """恢复自己写回去的检查点也得带主人：丢了就等于下一次谁都能接管。"""

    store = JsonlEpisodeStore(tmp_path)
    _crashed(store)
    moment = NOW + timedelta(hours=1) if expired else NOW

    result = restore_episode(EPISODE_ID, store, now=moment, **_authority())
    assert (result.outcome is not None) is expired

    _events, after = JsonlEpisodeStore(tmp_path).load(EPISODE_ID)
    assert dict(after.entry_identity) == OWNER.bind(EPISODE_ID).to_dict()
    if not expired:
        # resumable 分支只在有合成事件时重写检查点；没重写过，上面那句就是空跑。
        assert result.synthesized
        with pytest.raises(RestoreUnavailable, match="entry identity"):
            restore_episode(EPISODE_ID, store, now=moment, **_authority(None))


def test_a_forged_checkpoint_identity_cannot_authorize_itself(tmp_path):
    """篡改落盘身份（改成入侵者）也过不去：比对的是入口现场提供的那份。"""

    store = JsonlEpisodeStore(tmp_path)
    state = _crashed(store)
    forged = replace(OWNER, user_id="user-beta").bind(EPISODE_ID)
    store.put_state(EPISODE_ID, replace(state, entry_identity=forged.to_dict()))

    with pytest.raises(RestoreUnavailable, match="entry identity"):
        restore_episode(EPISODE_ID, store, now=NOW, **_authority())
    # 入侵者拿自己的身份也不行：授权快照仍是原主人那份合同/注册表，不因身份对上而放行。
    result = restore_episode(EPISODE_ID, store, now=NOW, **_authority(replace(OWNER, user_id="user-beta")))
    assert result.plan is not None


# ── 检查点侧：真跑一轮 ────────────────────────────────────────────────────────


def _rig_with_owner():
    rig = build_rig(EPISODE_ID)
    rig.context = replace(rig.context, entry_identity=OWNER.bind(EPISODE_ID))
    return rig


def test_every_checkpoint_of_a_live_episode_records_its_owner():
    rig = _rig_with_owner()
    rig.start()
    rig.run_until("tools_settled")
    mid = rig.stored_state()
    outcome = rig.finish()

    assert outcome.status == "completed"
    assert dict(mid.entry_identity) == OWNER.bind(EPISODE_ID).to_dict()
    assert dict(rig.stored_state().entry_identity) == OWNER.bind(EPISODE_ID).to_dict()


def test_owner_identity_never_reaches_the_model_or_the_event_stream():
    """身份是控制面事实：既不进提示词，也不进 durable 事件与实时出口。"""

    rig = _rig_with_owner()
    emitted: list[EpisodeEvent] = []
    rig.episode._event_sink = emitted.append
    rig.start()
    outcome = rig.finish()

    wire = json.dumps(
        [event.to_dict() for event in outcome.events] + [event.to_dict() for event in emitted],
        ensure_ascii=False,
    )
    # run_id / message_id 本来就是 episode_id 的组成部分，验不了；用户与会话 id 可以。
    assert OWNER.user_id not in wire
    assert OWNER.conversation_id not in wire
    assert dict(rig.stored_state().entry_identity)["user_id"] == OWNER.user_id


@pytest.mark.parametrize("successor", [replace(OWNER, user_id="user-beta"), None])
def test_an_episode_may_not_change_owner_midway(successor):
    """同一 episode 只有一个主人：中途换门（或没了门）算保存失败，不静默降级成未绑定。"""

    rig = _rig_with_owner()
    rig.start()
    rig.run_until("tools_settled")
    assert rig.episode._active_inbox is not None
    ledger = rig.episode._active_inbox._ledger
    ledger.active_context = replace(
        ledger.active_context,
        entry_identity=None if successor is None else successor.bind(EPISODE_ID),
    )

    outcome = rig.finish()

    assert outcome.persistence == "failed" and outcome.stop_reason == "storage_failed"
    # 落盘的那份身份仍是原主人，没被新 context 覆写。
    assert dict(rig.stored_state().entry_identity) == OWNER.bind(EPISODE_ID).to_dict()


# ── 概念自身的边界 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["", " ", "user alpha", "user\nalpha", "x" * 201])
def test_identity_fields_must_be_bare_tokens(value):
    with pytest.raises(ValueError):
        replace(OWNER, user_id=value)


def test_unknown_entry_points_are_refused():
    with pytest.raises(ValueError, match="entry point"):
        EntryIdentity(
            entry="whatever_door", user_id="u", conversation_id="c",
            run_id="r", assistant_message_id="m",
        )


def test_a_captured_identity_cannot_be_moved_onto_another_episode():
    context = _authority()["context"]
    moved = replace(context, entry_identity=OWNER.bind("run-beta:msg-beta"))
    with pytest.raises(ValueError, match="episode mismatch"):
        capture_entry_identity(moved)


# ── 入口：身份从服务端记录核出来，不是调用方自报 ────────────────────


def _isolate(monkeypatch, tmp_path):
    """装配期会碰真目录（行情库 / 知识库 / episode store），全改指一次性目录。"""

    (tmp_path / "finance").mkdir(exist_ok=True)
    (tmp_path / "wiki").mkdir(exist_ok=True)
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "finance"))
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wiki"))
    monkeypatch.delenv("AGENT_RUNTIME_BACKEND", raising=False)


def _door(monkeypatch, tmp_path, *, owner="entry-user", session="conv-alpha"):
    import intelligence.api.app as app_module
    from intelligence.services.run_store import RunStore

    _isolate(monkeypatch, tmp_path)
    run_store = RunStore(user_id=owner, root=tmp_path / "runs")
    run = run_store.create_run("目前市场结构如何", "ask", session_id=session)
    providers = (
        app_module.LLMProvider(
            "zhipu", "primary-secret", "https://glm.example.invalid/v1", "glm-5.2",
        ),
    )
    return app_module, run_store, run, providers


def test_the_workbench_door_binds_identity_from_the_stored_run(monkeypatch, tmp_path):
    app_module, run_store, run, providers = _door(monkeypatch, tmp_path)

    adapter = app_module._build_continuous_turn_adapter(
        providers=providers, run_id=run.run_id, assistant_message_id="msg-alpha",
        run_store=run_store, conversation_id="conv-alpha",
    )

    assert adapter._entry_identity == EntryIdentity(
        entry="workbench_conversation", user_id="entry-user",
        conversation_id="conv-alpha", run_id=run.run_id,
        assistant_message_id="msg-alpha",
    )


def test_the_door_refuses_a_run_that_belongs_to_another_conversation(monkeypatch, tmp_path):
    app_module, run_store, run, providers = _door(monkeypatch, tmp_path, session="conv-alpha")

    with pytest.raises(ValueError, match="another conversation"):
        app_module._build_continuous_turn_adapter(
            providers=providers, run_id=run.run_id, assistant_message_id="msg-alpha",
            run_store=run_store, conversation_id="conv-beta",
        )


def test_the_door_refuses_a_run_that_belongs_to_another_user(monkeypatch, tmp_path):
    from intelligence.services.run_store import RunStore

    app_module, _run_store, run, providers = _door(monkeypatch, tmp_path)
    intruder_store = RunStore(user_id="user-beta", root=tmp_path / "runs")

    with pytest.raises(ValueError, match="another user"):
        app_module._build_continuous_turn_adapter(
            providers=providers, run_id=run.run_id, assistant_message_id="msg-alpha",
            run_store=intruder_store, conversation_id="conv-alpha",
        )


def test_a_doorless_assembly_stays_unbound(monkeypatch, tmp_path):
    """没有 RunStore 就没有可核对的归属；宁可未绑定，不凭参数自封主人。"""

    app_module, _run_store, _run, providers = _door(monkeypatch, tmp_path)

    adapter = app_module._build_continuous_turn_adapter(
        providers=providers, run_id="run-alpha", assistant_message_id="msg-alpha",
    )

    assert adapter._entry_identity is None


@pytest.mark.parametrize("stamped", [OWNER, None])
def test_only_the_door_may_stamp_identity_onto_the_episode_context(stamped):
    """context 工厂（含注入替身）自己填的身份不算数，一律被入口那份覆写。"""

    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.tests.test_continuous_turn_adapter import _control, _frame

    forged = replace(OWNER, user_id="user-beta")

    def forging_context_factory(frame, **kwargs):
        built = build_episode_context(frame, **kwargs)
        return replace(built, entry_identity=forged.bind(str(kwargs["task_id"])))

    seen: dict[str, object] = {}

    class _Stop(Exception):
        pass

    def registry_factory(_frame_arg, context):
        seen["context"] = context
        raise _Stop()

    class _UnusedVerifier:
        def verify(self, **_kwargs):
            raise AssertionError("semantic verification is out of scope here")

    adapter = ContinuousTurnAdapter(
        runtime=object(), semantic_verifier=_UnusedVerifier(), mode="on",
        context_factory=forging_context_factory, registry_factory=registry_factory,
        task_id_factory=lambda: "run-beta:msg-beta", entry_identity=stamped,
        repair_seconds_cap=30.0, timeout=30.0,
    )
    frame = _frame()
    try:
        adapter._run_episode(frame, _control(frame))
    except _Stop:
        pass

    context = seen["context"]
    assert context.entry_identity == (None if stamped is None else stamped.bind("run-beta:msg-beta"))


def test_the_adapter_refuses_a_bound_identity_of_the_wrong_type():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter

    class _UnusedVerifier:
        def verify(self, **_kwargs):
            raise AssertionError("unreachable")

    with pytest.raises(TypeError, match="EntryIdentity"):
        ContinuousTurnAdapter(
            runtime=object(), semantic_verifier=_UnusedVerifier(), mode="on",
            entry_identity=OWNER.bind(EPISODE_ID), repair_seconds_cap=30.0,
        )


@pytest.mark.parametrize("mutate", [
    lambda payload: payload | {"schema_version": 2},
    lambda payload: payload | {"kind": "episode_authorization"},
    lambda payload: payload | {"extra": "x"},
    lambda payload: {k: v for k, v in payload.items() if k != "user_id"},
    lambda payload: payload | {"user_id": ""},
])
def test_stored_identity_payloads_are_validated_not_trusted(mutate):
    payload = mutate(OWNER.bind(EPISODE_ID).to_dict())
    with pytest.raises(ValueError):
        EpisodeEntryIdentity.from_dict(payload, episode_id=EPISODE_ID)
