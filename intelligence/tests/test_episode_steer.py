"""CLI steer 的两半（工单 #30 范围第 5 条，INV-R5 不变）。

投递槽：``Inbox`` 在认领点吞槽、三事实落账、坏文件隔离、关箱不吞；递话方：找 store、判终局、原子写、
按 ``spool_id`` 对回执；CLI 出口码；loop 级：真 ``GLMAgentRuntime`` + ``JsonlEpisodeStore``，话不经
``runtime.steer`` 只写槽（与 CLI 完全同一条路径），第二次模型请求前被认领。
"""

from __future__ import annotations

import json
import threading

import pytest

from intelligence import cli
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_runtime import EpisodeEvent, ModelTurn
from intelligence.services.episode_inbox import (
    INBOX_SPOOL_DIRNAME,
    Inbox,
    SpoolRecord,
    read_spool_record,
    spool_dir_for,
    write_spool_record,
)
from intelligence.services.episode_messages import derive_messages, user_message
from intelligence.services.episode_steer import (
    EpisodeFinished,
    EpisodeNotFound,
    deliver_steer,
    list_open_episodes,
    read_receipt,
    wait_receipt,
)
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore, now_iso
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


class _Ledger:
    def __init__(self) -> None:
        self.events: list[EpisodeEvent] = []
        self._lock = threading.Lock()

    def add(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        with self._lock:
            event = EpisodeEvent(len(self.events) + 1, kind, dict(payload))
            self.events.append(event)
            return event

    def kinds(self) -> list[str]:
        return [event.kind for event in self.events]


def _record(spool_id: str, content: str, **overrides: object) -> SpoolRecord:
    return SpoolRecord(spool_id=spool_id, content=content, created_at=now_iso(), **overrides)  # type: ignore[arg-type]


def _open_episode(store: JsonlEpisodeStore, episode_id: str, *, phase: str = "model_pending") -> None:
    store.append(episode_id, (EpisodeEvent(1, "task", {"question": "q"}),))
    store.put_state(episode_id, EpisodeState(episode_id=episode_id, phase=phase, updated_at=now_iso()))  # type: ignore[arg-type]


# ── 投递槽 × Inbox ─────────────────────────────────────────────────────────


def test_spool_records_round_trip_and_sort_in_delivery_order(tmp_path) -> None:
    spool = tmp_path / INBOX_SPOOL_DIRNAME
    first = write_spool_record(spool, _record("a1", "先看北向资金"))
    second = write_spool_record(spool, _record("b2", "再看两融", target="next_turn", wakeup=True))

    assert sorted(spool.iterdir()) == [first, second]
    assert first.suffix == ".json" and not list(spool.glob("*.tmp"))
    got = read_spool_record(second)
    assert got is not None
    assert got == SpoolRecord(
        spool_id="b2", content="再看两融", target="next_turn", source="cli", wakeup=True, created_at=got.created_at
    )
    with pytest.raises(ValueError):
        write_spool_record(spool, SpoolRecord(spool_id="x", content="   "))
    with pytest.raises(ValueError):
        write_spool_record(spool, SpoolRecord(spool_id="x", content="y", target="later"))


def test_inbox_ingests_the_spool_at_pending_and_claim_with_facts_and_removes_files(tmp_path) -> None:
    ledger = _Ledger()
    spool = tmp_path / INBOX_SPOOL_DIRNAME
    inbox = Inbox(ledger, spool=spool)
    assert inbox.pending() == 0  # 槽目录还不存在也不抛
    write_spool_record(spool, _record("s1", "先看北向资金"))
    write_spool_record(spool, _record("s2", "再看两融", target="next_turn"))

    assert inbox.pending() == 2 and inbox.pending("next_turn") == 1
    assert list(spool.iterdir()) == []
    assert ledger.kinds() == ["inbox_inserted", "inbox_inserted"]
    inserted = ledger.events[0].payload
    assert inserted["spool_id"] == "s1" and inserted["source"] == "cli"
    assert inserted["content"] == "先看北向资金" and inserted["target"] == "next_step"
    # 入箱 ≠ 模型可见。
    assert derive_messages(ledger.events) == []

    claimed = inbox.claim("next_step")

    assert [message.content for message in claimed] == ["先看北向资金"]
    assert ledger.kinds()[-1] == "inbox_claimed"
    assert [message.content for message in derive_messages(ledger.events)] == ["先看北向资金"]
    # 进程内 send 的 payload 形状不变：没有 spool_id。
    inbox.send(user_message("进程内", source="steer"))
    assert "spool_id" not in ledger.events[-1].payload


def test_invalid_spool_files_are_quarantined_without_facts(tmp_path) -> None:
    ledger = _Ledger()
    spool = tmp_path / INBOX_SPOOL_DIRNAME
    spool.mkdir()
    (spool / "0001-bad.json").write_text("not json", encoding="utf-8")
    (spool / "0002-nocontent.json").write_text(json.dumps({"spool_id": "n", "content": "   "}), encoding="utf-8")
    (spool / "0003-badtarget.json").write_text(
        json.dumps({"spool_id": "t", "content": "x", "target": "later"}), encoding="utf-8"
    )
    write_spool_record(spool, _record("ok", "好的那条"))
    inbox = Inbox(ledger, spool=spool)

    assert inbox.pending() == 1
    assert sorted(path.name for path in spool.iterdir()) == [
        "0001-bad.json.invalid",
        "0002-nocontent.json.invalid",
        "0003-badtarget.json.invalid",
    ]
    assert ledger.kinds() == ["inbox_inserted"] and ledger.events[0].payload["spool_id"] == "ok"
    # 隔离过的不再被看见。
    assert inbox.pending() == 1 and ledger.kinds() == ["inbox_inserted"]


def test_spool_message_arriving_before_finish_is_inserted_then_discarded(tmp_path) -> None:
    ledger = _Ledger()
    spool = tmp_path / INBOX_SPOOL_DIRNAME
    inbox = Inbox(ledger, spool=spool)
    write_spool_record(spool, _record("late", "还来得及吗"))

    assert inbox.discard_all(reason="episode_finished") == 1
    assert ledger.kinds() == ["inbox_inserted", "inbox_discarded"]
    assert ledger.events[1].payload["reason"] == "episode_finished"
    assert list(spool.iterdir()) == []


def test_closed_inbox_leaves_the_spool_alone_until_reopen(tmp_path) -> None:
    ledger = _Ledger()
    spool = tmp_path / INBOX_SPOOL_DIRNAME
    inbox = Inbox(ledger, spool=spool)
    inbox.discard_all(reason="episode_finished")
    path = write_spool_record(spool, _record("after", "收口后到的"))

    assert inbox.pending() == 0 and path.exists() and ledger.kinds() == []
    inbox.reopen()
    assert inbox.pending() == 1 and not path.exists()
    assert ledger.kinds() == ["inbox_inserted"]


def test_harness_rejected_spool_message_is_recorded_and_the_file_removed(tmp_path) -> None:
    ledger = _Ledger()
    spool = tmp_path / INBOX_SPOOL_DIRNAME
    inbox = Inbox(ledger, admit=lambda message: "买入" not in message.content, spool=spool)
    write_spool_record(spool, _record("r", "全仓买入茅台"))

    assert inbox.pending() == 0
    assert ledger.kinds() == ["inbox_inserted", "inbox_discarded"]
    assert ledger.events[1].payload["reason"] == "rejected_by_harness"
    assert list(spool.iterdir()) == []


def test_spool_dir_only_exists_for_on_disk_stores(tmp_path) -> None:
    store = JsonlEpisodeStore(tmp_path)
    assert spool_dir_for(store, "run_1:msg_2") == store.episode_dir("run_1:msg_2") / INBOX_SPOOL_DIRNAME
    assert spool_dir_for(None, "x") is None
    assert spool_dir_for(object(), "x") is None


# ── 递话方 ────────────────────────────────────────────────────────────────


def test_deliver_steer_refuses_unknown_and_finished_episodes(tmp_path) -> None:
    root = tmp_path / "episodes"
    store = JsonlEpisodeStore(root)
    with pytest.raises(EpisodeNotFound) as not_found:
        deliver_steer(store_root=root, episode_id="run_x:msg_y", content="hi")
    assert str(root) in str(not_found.value)

    _open_episode(store, "run_done:msg_1", phase="done")
    with pytest.raises(EpisodeFinished):
        deliver_steer(store_root=root, episode_id="run_done:msg_1", content="hi")

    _open_episode(store, "run_live:msg_1")
    with pytest.raises(ValueError):
        deliver_steer(store_root=root, episode_id="run_live:msg_1", content="   ")
    with pytest.raises(ValueError):
        deliver_steer(store_root=root, episode_id="run_live:msg_1", content="x", target="later")

    delivery = deliver_steer(store_root=root, episode_id="run_live:msg_1", content="先看北向资金", target="next_turn")

    assert delivery.spool_path.parent == store.episode_dir("run_live:msg_1") / INBOX_SPOOL_DIRNAME
    record = read_spool_record(delivery.spool_path)
    assert record is not None
    assert record.content == "先看北向资金" and record.target == "next_turn"
    assert record.spool_id == delivery.spool_id and record.source == "cli"
    assert list_open_episodes(root) == ("run_live:msg_1",)


def test_receipts_are_read_back_from_the_event_log(tmp_path) -> None:
    root = tmp_path / "episodes"
    store = JsonlEpisodeStore(root)
    episode = "run_r:msg_1"
    store.append(episode, (EpisodeEvent(1, "task", {"question": "q"}),))
    assert read_receipt(store_root=root, episode_id=episode, spool_id="s1") is None

    store.append(
        episode,
        (
            EpisodeEvent(
                2,
                "inbox_inserted",
                {"message_id": "inbox-1", "spool_id": "s1", "content": "x", "target": "next_step", "source": "cli"},
            ),
        ),
    )
    receipt = read_receipt(store_root=root, episode_id=episode, spool_id="s1")
    assert receipt is not None and receipt.message_id == "inbox-1" and not receipt.settled

    ticks = iter([0.0, 0.1])
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        store.append(
            episode,
            (EpisodeEvent(3, "inbox_claimed", {"message_id": "inbox-1", "target": "next_step", "source": "cli"}),),
        )

    settled = wait_receipt(
        store_root=root, episode_id=episode, spool_id="s1", timeout_s=3.0, poll_s=0.5,
        clock=lambda: next(ticks), sleep=sleep,
    )
    assert settled is not None and settled.fate == "claimed" and slept == [0.5]
    # 超时且从未入箱：None。
    late_ticks = iter([0.0, 10.0])
    assert (
        wait_receipt(
            store_root=root, episode_id=episode, spool_id="nope", timeout_s=1.0,
            clock=lambda: next(late_ticks), sleep=lambda _seconds: None,
        )
        is None
    )


def test_cli_steer_lists_delivers_and_fails_closed(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "episodes"
    monkeypatch.setenv("FORESIGHT_EPISODE_STORE", str(root))
    store = JsonlEpisodeStore(root)
    _open_episode(store, "run_live:msg_1")
    _open_episode(store, "run_done:msg_1", phase="done")

    assert cli.main(["steer", "--list"]) == 0
    assert json.loads(capsys.readouterr().out.strip()) == {"store_root": str(root), "open_episodes": ["run_live:msg_1"]}

    assert cli.main(["steer", "run_nope:msg_1", "hi"]) == 2
    err = json.loads(capsys.readouterr().err.strip())
    assert err["error"] == "episode_not_found" and str(root) in err["detail"]

    assert cli.main(["steer", "run_done:msg_1", "hi"]) == 1
    assert json.loads(capsys.readouterr().err.strip())["error"] == "episode_finished"

    assert cli.main(["steer", "run_live:msg_1"]) == 2
    assert json.loads(capsys.readouterr().err.strip())["error"] == "usage"

    assert cli.main(["steer", "run_live:msg_1", "先看北向资金", "--target", "next_turn"]) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True and out["target"] == "next_turn" and out["receipt"] is None
    spool_files = list((store.episode_dir("run_live:msg_1") / INBOX_SPOOL_DIRNAME).iterdir())
    assert len(spool_files) == 1
    record = read_spool_record(spool_files[0])
    assert record is not None and record.spool_id == out["spool_id"]

    assert cli.main(["steer", "--wait", "0.01", "run_live:msg_1", "第二句"]) == 0
    waited = json.loads(capsys.readouterr().out.strip())
    assert waited["receipt"] is None and "receipt_note" in waited


# ── loop 级 ──────────────────────────────────────────────────────────────


class _HookedModel:
    """脚本化 client 外包一层：记每次请求的线格式消息；第 N 次请求进行中可触发钩子。"""

    def __init__(self, inner: ScriptedModelClient) -> None:
        self._inner = inner
        self.requests: list[list[dict[str, object]]] = []
        self.on_call: dict[int, object] = {}

    def complete(self, *, messages, tools, timeout) -> ModelTurn:
        self.requests.append([dict(item) for item in messages])
        hook = self.on_call.get(len(self.requests))
        if hook is not None:
            hook()  # type: ignore[operator]
        return self._inner.complete(messages=messages, tools=tools, timeout=timeout)


def test_spool_steer_reaches_the_running_episode_before_its_next_request(tmp_path) -> None:
    root = tmp_path / "episodes"
    probe = ScenarioProbe()
    frame = make_frame()
    context = make_context(frame, task_id="steer-cli-loop")
    model = _HookedModel(
        ScriptedModelClient(
            [
                ScriptedTurn(tool_calls=(ScriptedToolCall(AUTHORIZED_TOOL, "市场宽度"),)),
                ScriptedTurn(finish=completed_finish()),
            ],
            probe,
        )
    )
    runtime = GLMAgentRuntime(client=model, episode_store=JsonlEpisodeStore(root))
    deliveries = []
    # 「另一个进程」：不经 runtime.steer，只写槽——与 CLI 完全同一条路径。
    model.on_call[1] = lambda: deliveries.append(
        deliver_steer(store_root=root, episode_id="steer-cli-loop", content="先看北向资金")
    )

    outcome = runtime.run(task_frame=frame, context=context, registry=make_registry(probe))

    assert outcome.status == "completed"
    assert len(model.requests) == 2
    assert "先看北向资金" not in [item.get("content") for item in model.requests[0]]
    assert model.requests[1][-1] == {"role": "user", "content": "先看北向资金"}
    kinds = [event.kind for event in outcome.events if event.kind.startswith("inbox_")]
    assert kinds == ["inbox_inserted", "inbox_claimed"]
    inserted = next(event for event in outcome.events if event.kind == "inbox_inserted").payload
    assert inserted["spool_id"] == deliveries[0].spool_id and inserted["source"] == "cli"
    # 槽已清空；回执从落盘日志读得回。
    assert list(deliveries[0].spool_path.parent.iterdir()) == []
    receipt = read_receipt(store_root=root, episode_id="steer-cli-loop", spool_id=deliveries[0].spool_id)
    assert receipt is not None and receipt.fate == "claimed"
    # 收口后再投：递话方按 state.json 终局拒投。
    with pytest.raises(EpisodeFinished):
        deliver_steer(store_root=root, episode_id="steer-cli-loop", content="晚了")
