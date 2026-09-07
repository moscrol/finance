"""P2 存储侧：``EpisodeState`` 程序计数器、两个 store 同形、撕裂末行、版本 / 未知 kind。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_store import (
    EPISODE_LOG_VERSION,
    EPISODE_STORE_ENV,
    EpisodeLogCorrupt,
    EpisodeState,
    JsonlEpisodeStore,
    MemoryEpisodeStore,
    UnknownRequiredKind,
    require_known_kinds,
    resolve_episode_store_root,
)


def _events(*kinds: str, start: int = 1) -> tuple[EpisodeEvent, ...]:
    return tuple(
        EpisodeEvent(start + index, kind, {"n": start + index})
        for index, kind in enumerate(kinds)
    )


# ── EpisodeState ─────────────────────────────────────────────────────────────


def test_state_round_trips_through_dict_and_freezes_mappings() -> None:
    state = EpisodeState(
        episode_id="ep-1",
        phase="model_pending",
        turn_index=2,
        reserved_ids=("turn-3",),
        consumed_seconds=12.5,
        deadline_at="2026-09-07T16:00:00.000+08:00",
        retry={"remaining": 1},
        contract_snapshot={"task_id": "ep-1", "tier": "quick"},
        cancel=None,
        last_sequence=7,
        updated_at="2026-09-07T15:59:00.000+08:00",
    )
    assert state.log_version == EPISODE_LOG_VERSION
    assert not state.terminal
    restored = EpisodeState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored == state
    with pytest.raises(TypeError):
        state.retry["remaining"] = 0  # type: ignore[index]


def test_state_rejects_unknown_phase_and_missing_id() -> None:
    with pytest.raises(ValueError):
        EpisodeState(episode_id="ep", phase="sleeping")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EpisodeState(episode_id="  ", phase="planning")


def test_done_state_is_terminal() -> None:
    assert EpisodeState(episode_id="ep", phase="done").terminal


# ── EpisodeEvent.ignorable ───────────────────────────────────────────────────


def test_event_to_dict_only_carries_ignorable_when_set() -> None:
    plain = EpisodeEvent(1, "task", {"a": 1})
    flagged = EpisodeEvent(2, "brand_new_kind", {"a": 1}, ignorable=True)
    assert "ignorable" not in plain.to_dict()
    assert flagged.to_dict()["ignorable"] is True


def test_require_known_kinds_accepts_registered_and_ignorable_only() -> None:
    require_known_kinds(_events("task", "model_turn"))
    require_known_kinds((EpisodeEvent(1, "future_kind", {}, ignorable=True),))
    with pytest.raises(UnknownRequiredKind) as excinfo:
        require_known_kinds(_events("task", "future_kind"))
    assert excinfo.value.kind == "future_kind"
    assert excinfo.value.sequence == 2


# ── 两个 store 同形 ──────────────────────────────────────────────────────────


def _drive(store) -> None:
    store.append("ep:1", _events("task", "prompt_assembled"))
    store.put_state("ep:1", EpisodeState(episode_id="ep:1", phase="planning", last_sequence=2))
    store.append("ep:1", _events("model_intent", start=3), sync=True)
    store.put_state(
        "ep:1",
        EpisodeState(
            episode_id="ep:1", phase="model_pending", reserved_ids=("turn-1",), last_sequence=3
        ),
    )
    store.append("ep:2", _events("task"))
    store.put_state("ep:2", EpisodeState(episode_id="ep:2", phase="done", last_sequence=1))


def _dump(store, episode_id: str) -> dict[str, object]:
    events, state = store.load(episode_id)
    return {
        "events": [event.to_dict() for event in events],
        "state": state.to_dict() if state is not None else None,
    }


def test_memory_and_jsonl_stores_give_byte_identical_reads(tmp_path: Path) -> None:
    memory = MemoryEpisodeStore()
    jsonl = JsonlEpisodeStore(tmp_path / "episodes")
    _drive(memory)
    _drive(jsonl)
    for episode_id in ("ep:1", "ep:2", "ep:missing"):
        assert json.dumps(_dump(memory, episode_id), sort_keys=True) == json.dumps(
            _dump(jsonl, episode_id), sort_keys=True
        )
    assert memory.list_open() == jsonl.list_open() == ("ep:1",)


def test_memory_store_records_sync_flag_per_append() -> None:
    store = MemoryEpisodeStore()
    _drive(store)
    assert store.append_log == [
        ("ep:1", (1, 2), False),
        ("ep:1", (3,), True),
        ("ep:2", (1,), False),
    ]


def test_jsonl_directory_name_is_filesystem_safe_and_injective(tmp_path: Path) -> None:
    store = JsonlEpisodeStore(tmp_path)
    plain = store.episode_dir("run_20260907_133930_566612")
    colon = store.episode_dir("run_20260907_133930_566612:msg_ab")
    slash = store.episode_dir("run_20260907_133930_566612/msg_ab")
    assert plain.name == "run_20260907_133930_566612"
    assert ":" not in colon.name and "/" not in slash.name
    assert colon.name != slash.name
    store.append("run_x:msg_1", _events("task"))
    store.put_state("run_x:msg_1", EpisodeState(episode_id="run_x:msg_1", phase="planning"))
    assert store.list_open() == ("run_x:msg_1",)


def test_jsonl_put_state_leaves_no_temporary_file_and_overwrites_whole(tmp_path: Path) -> None:
    store = JsonlEpisodeStore(tmp_path)
    store.put_state("ep", EpisodeState(episode_id="ep", phase="planning", turn_index=1))
    store.put_state("ep", EpisodeState(episode_id="ep", phase="model_pending", turn_index=2))
    directory = store.episode_dir("ep")
    assert sorted(path.name for path in directory.iterdir()) == ["state.json"]
    _, state = store.load("ep")
    assert state is not None and state.phase == "model_pending" and state.turn_index == 2


def test_jsonl_drops_torn_last_line_but_refuses_corrupt_middle(tmp_path: Path) -> None:
    store = JsonlEpisodeStore(tmp_path)
    store.append("ep", _events("task", "prompt_assembled", "model_intent"))
    log = store.episode_dir("ep") / "events.jsonl"
    with open(log, "a", encoding="utf-8") as handle:
        handle.write('{"sequence": 4, "kind": "model_turn", "pay')
    events, _ = store.load("ep")
    assert [event.sequence for event in events] == [1, 2, 3]

    lines = log.read_text(encoding="utf-8").split("\n")
    lines[1] = '{"sequence": 2, "kind": "prompt_assembled"'
    log.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(EpisodeLogCorrupt):
        store.load("ep")


def test_jsonl_refuses_non_contiguous_sequence(tmp_path: Path) -> None:
    store = JsonlEpisodeStore(tmp_path)
    store.append("ep", _events("task"))
    store.append("ep", _events("model_turn", start=3))
    with pytest.raises(EpisodeLogCorrupt):
        store.load("ep")


def test_jsonl_list_open_skips_done_and_missing_state(tmp_path: Path) -> None:
    store = JsonlEpisodeStore(tmp_path)
    store.append("no-state", _events("task"))
    store.put_state("open-a", EpisodeState(episode_id="open-a", phase="tools_pending"))
    store.put_state("done-b", EpisodeState(episode_id="done-b", phase="done"))
    assert store.list_open() == ("open-a",)
    assert JsonlEpisodeStore(tmp_path / "absent").list_open() == ()


def test_memory_state_id_must_match_key() -> None:
    store = MemoryEpisodeStore()
    with pytest.raises(ValueError):
        store.put_state("ep-a", EpisodeState(episode_id="ep-b", phase="planning"))


# ── 根目录解析 ───────────────────────────────────────────────────────────────


def test_resolve_root_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(EPISODE_STORE_ENV, raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    assert resolve_episode_store_root().name == "episodes"
    assert resolve_episode_store_root().parent.name == ".finance-runtime"
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "ws"))
    assert resolve_episode_store_root() == tmp_path / "ws" / "state" / "episodes"
    monkeypatch.setenv(EPISODE_STORE_ENV, str(tmp_path / "override"))
    assert resolve_episode_store_root() == tmp_path / "override"
